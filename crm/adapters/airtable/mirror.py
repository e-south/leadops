from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import yaml

from crm.adapters.airtable.client import AirtableClient, AirtableError
from crm.store.sqlite import SqliteStore


class _StoreLike(Protocol):
    def fetch_all(self, query: str, params: list[object] | None = None): ...

    def get_mirror_state(self, table_name: str, external_id: str): ...

    def upsert_mirror_state(
        self,
        table_name: str,
        external_id: str,
        record_id: str | None,
        mirror_version: int,
        mirror_updated_at: str,
    ) -> None: ...


@dataclass(frozen=True)
class AirtableMapping:
    mirror_fields: dict[str, dict[str, Any]]
    tables: dict[str, dict[str, dict[str, str]]]


class MirrorError(RuntimeError):
    pass


def load_mapping(mapping_path: Path) -> AirtableMapping:
    data = yaml.safe_load(mapping_path.read_text(encoding="utf-8")) or {}
    mirror_fields = data.get("mirror_fields", {})
    tables = data.get("tables", {})
    if not isinstance(tables, dict):
        raise MirrorError("Airtable mapping tables must be a mapping.")
    return AirtableMapping(mirror_fields=mirror_fields, tables=tables)


def validate_schema(client: AirtableClient, mapping: AirtableMapping, table_ids: dict[str, str]) -> None:
    tables = client.list_tables()
    tables_by_id = {table["id"]: table for table in tables}

    for table_name, table_def in mapping.tables.items():
        table_id = table_ids.get(table_name)
        if not table_id:
            raise MirrorError(f"Missing table id for {table_name} in workspace config.")
        meta = tables_by_id.get(table_id)
        if not meta:
            raise MirrorError(f"Airtable table id not found: {table_name} ({table_id})")
        existing_fields = {field["name"] for field in meta.get("fields", [])}
        required_fields = set(table_def.get("fields", {}).values()) | set(mapping.mirror_fields.keys())
        missing = required_fields - existing_fields
        if missing:
            raise MirrorError(
                f"Airtable table {table_name} is missing fields: {', '.join(sorted(missing))}"
            )


def push_all(
    store: SqliteStore,
    client: AirtableClient,
    mapping: AirtableMapping,
    table_ids: dict[str, str],
) -> None:
    for table_name, table_def in mapping.tables.items():
        table_id = table_ids.get(table_name)
        if not table_id:
            raise MirrorError(f"Missing table id for {table_name} in workspace config.")
        with store.session() as session:
            _push_table(session, client, table_name, table_id, table_def)


def _push_table(
    store: _StoreLike,
    client: AirtableClient,
    table_name: str,
    table_id: str,
    table_def: dict[str, Any],
) -> None:
    fields_map = table_def.get("fields", {})
    external_id_field = _find_external_id_field(fields_map)
    if not external_id_field:
        raise MirrorError(f"Table {table_name} mapping must map a field to ExternalId.")

    rows = store.fetch_all(f"SELECT * FROM {table_name}")
    for row in rows:
        external_id = row[external_id_field]
        mirror_state = store.get_mirror_state(table_name, external_id)
        next_version = int(mirror_state["mirror_version"]) + 1 if mirror_state else 1
        now = datetime.now(UTC).replace(microsecond=0).isoformat()

        airtable_fields = {}
        for field_name, airtable_field in fields_map.items():
            airtable_fields[airtable_field] = _serialize_value(row[field_name])
        airtable_fields["ExternalId"] = external_id
        airtable_fields["MirrorVersion"] = next_version
        airtable_fields["MirrorUpdatedAt"] = now

        record_id = None
        try:
            existing = client.find_record_by_external_id(table_id, external_id)
            if existing:
                record = client.update_record(table_id, existing.record_id, airtable_fields)
                record_id = record.record_id
            else:
                record = client.create_record(table_id, airtable_fields)
                record_id = record.record_id
        except AirtableError as exc:
            raise MirrorError(str(exc)) from exc

        store.upsert_mirror_state(table_name, external_id, record_id, next_version, now)


def _find_external_id_field(fields_map: dict[str, str]) -> str | None:
    for field_name, airtable_field in fields_map.items():
        if airtable_field == "ExternalId":
            return field_name
    return None


def _serialize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, float, str)):
        return value
    return str(value)
