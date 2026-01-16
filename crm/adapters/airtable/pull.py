from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from crm.adapters.airtable.client import AirtableClient
from crm.adapters.airtable.mirror import AirtableMapping
from crm.services.pull import PullDecision, decide_pull_action, diff_fields
from crm.services.utils import utc_now_iso
from crm.store.migrations import Schema
from crm.store.sqlite import SqliteSession, SqliteStore

MODIFIED_FIELD = "AirtableModifiedAt"



@dataclass
class PullSummary:
    scanned: int
    skipped: int
    applied: int
    conflicts: int
    created: int
    ignored: int


@dataclass
class PullChange:
    table: str
    external_id: str
    action: str
    changed_fields: list[str]
    reason: str | None = None


class PullError(RuntimeError):
    pass


def pull_records(
    store: SqliteStore,
    client: AirtableClient,
    mapping: AirtableMapping,
    schema: Schema,
    table_ids: dict[str, str],
    tables_meta: dict[str, dict[str, Any]] | None,
    last_pull_at: dict[str, str] | None,
    apply: bool,
    accept_remote: set[str] | None = None,
    logger: Any | None = None,
) -> tuple[PullSummary, list[PullChange]]:
    summary = PullSummary(scanned=0, skipped=0, applied=0, conflicts=0, created=0, ignored=0)
    changes: list[PullChange] = []
    accept_remote = accept_remote or set()

    for table_name, table_def in mapping.tables.items():
        table_id = table_ids.get(table_name)
        if not table_id:
            raise PullError(f"Missing table id for {table_name} in workspace config.")
        fields_map = table_def.get("fields", {})
        external_id_field = _find_external_id_field(fields_map)
        if not external_id_field:
            raise PullError(f"Table {table_name} mapping must map a field to ExternalId.")

        schema_fields = (schema.tables.get(table_name) or {}).get("fields", {})
        query_fields = [fields_map[field] for field in fields_map] + [
            "ExternalId",
            "MirrorVersion",
            "MirrorUpdatedAt",
            MODIFIED_FIELD,
        ]
        filter_formula = None
        if last_pull_at and last_pull_at.get(table_name):
            table_meta = tables_meta.get(table_id) if tables_meta else None
            if table_meta and _has_modified_field(table_meta):
                filter_formula = _modified_since_formula(last_pull_at[table_name])
        records = client.list_records(table_id, fields=query_fields, filter_formula=filter_formula)

        with store.session() as session:
            for record in records:
                summary.scanned += 1
                external_id = record.fields.get("ExternalId")
                if not external_id:
                    summary.ignored += 1
                    continue
                remote_fields = record.fields
                local_row = session.fetch_one(
                    f"SELECT * FROM {table_name} WHERE {external_id_field} = ?",
                    (external_id,),
                )
                local_dict = dict(local_row) if local_row else None
                mirror_state = session.get_mirror_state(table_name, external_id)
                mirror_dict = dict(mirror_state) if mirror_state else None
                changed_fields = diff_fields(
                    local_row=local_dict,
                    remote_fields=remote_fields,
                    field_map=fields_map,
                    schema_fields=schema_fields,
                )
                decision = decide_pull_action(
                    local_row=local_dict,
                    mirror_state=mirror_dict,
                    changed_fields=changed_fields,
                )
                if decision.action == "skip":
                    summary.skipped += 1
                    continue
                if decision.action == "conflict" and external_id in accept_remote:
                    decision = PullDecision(action="apply", changed_fields=changed_fields)

                changes.append(
                    PullChange(
                        table=table_name,
                        external_id=external_id,
                        action=decision.action,
                        changed_fields=changed_fields,
                        reason=decision.reason,
                    )
                )
                if decision.action == "conflict":
                    summary.conflicts += 1
                    if logger is not None:
                        logger.log(
                            event_type="pull_conflict",
                            entity_type=table_name,
                            external_id=external_id,
                            changed_fields=changed_fields,
                            conflict=True,
                        )
                    continue

                if apply:
                    if decision.action == "create":
                        _insert_local(session, table_name, external_id_field, fields_map, remote_fields, schema_fields)
                        summary.created += 1
                    elif decision.action == "apply":
                        _update_local(session, table_name, external_id_field, fields_map, remote_fields, schema_fields)
                        summary.applied += 1
                    remote_version = remote_fields.get("MirrorVersion")
                    if remote_version is not None:
                        try:
                            mirror_version = int(remote_version)
                        except (TypeError, ValueError):
                            mirror_version = mirror_dict["mirror_version"] if mirror_dict else 0
                    else:
                        mirror_version = mirror_dict["mirror_version"] if mirror_dict else 0
                    session.upsert_mirror_state(
                        table_name,
                        external_id,
                        record.record_id,
                        mirror_version,
                        utc_now_iso(),
                    )
                    if logger is not None:
                        logger.log(
                            event_type="pull_apply",
                            entity_type=table_name,
                            external_id=external_id,
                            changed_fields=changed_fields,
                            conflict=False,
                        )
                else:
                    if decision.action == "create":
                        summary.created += 1
                    elif decision.action == "apply":
                        summary.applied += 1

    return summary, changes


def _find_external_id_field(fields_map: dict[str, str]) -> str | None:
    for field_name, airtable_field in fields_map.items():
        if airtable_field == "ExternalId":
            return field_name
    return None


def _update_local(
    session: SqliteSession,
    table_name: str,
    external_id_field: str,
    fields_map: dict[str, str],
    remote_fields: dict[str, Any],
    schema_fields: dict[str, Any],
) -> None:
    assignments = []
    params: list[Any] = []
    for local_field, airtable_field in fields_map.items():
        if local_field in {"created_at", "updated_at"}:
            continue
        value = remote_fields.get(airtable_field)
        params.append(_convert_value(value, schema_fields.get(local_field)))
        assignments.append(f"{local_field} = ?")
    params.append(utc_now_iso())
    params.append(remote_fields.get("ExternalId"))
    assignments.append("updated_at = ?")
    query = f"UPDATE {table_name} SET {', '.join(assignments)} WHERE {external_id_field} = ?"
    session.execute(query, params)


def _insert_local(
    session: SqliteSession,
    table_name: str,
    external_id_field: str,
    fields_map: dict[str, str],
    remote_fields: dict[str, Any],
    schema_fields: dict[str, Any],
) -> None:
    columns = []
    placeholders = []
    params: list[Any] = []
    now = utc_now_iso()
    for local_field, airtable_field in fields_map.items():
        value = remote_fields.get(airtable_field)
        columns.append(local_field)
        params.append(_convert_value(value, schema_fields.get(local_field)))
        placeholders.append("?")
    if "created_at" in schema_fields:
        columns.append("created_at")
        params.append(now)
        placeholders.append("?")
    if "updated_at" in schema_fields:
        columns.append("updated_at")
        params.append(now)
        placeholders.append("?")
    query = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
    session.execute(query, params)


def _convert_value(value: Any, spec: dict[str, Any] | None) -> Any:
    if value is None:
        return None
    field_type = spec.get("type") if isinstance(spec, dict) else None
    if field_type in {"uuid", "text", "enum"}:
        return str(value)
    if field_type == "number":
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    if field_type == "bool":
        if isinstance(value, str):
            return value.lower() in {"true", "1", "yes"}
        return bool(value)
    if field_type in {"date", "datetime"}:
        if isinstance(value, str):
            return value
        if isinstance(value, (datetime, date)):
            return value.isoformat()
    return value


def _modified_since_formula(iso_value: str) -> str:
    safe_value = iso_value.replace("'", "\\'")
    return f"IS_AFTER({{{MODIFIED_FIELD}}}, '{safe_value}')"


def _has_modified_field(table_meta: dict[str, Any]) -> bool:
    return any(field.get("name") == MODIFIED_FIELD for field in table_meta.get("fields", []))
