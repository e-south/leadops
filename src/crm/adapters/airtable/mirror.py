from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import yaml

from crm.adapters.airtable.client import AirtableClient, AirtableError
from crm.store.migrations import Schema
from crm.store.sqlite import SqliteStore

MIRROR_FIELD_NAMES = {"ExternalId", "MirrorVersion", "MirrorUpdatedAt"}
MODIFIED_TIME_FIELD = "AirtableModifiedAt"
LONG_TEXT_FIELDS = {"notes", "details", "body_snippet"}
DATE_OPTIONS = {"dateFormat": {"name": "iso"}}
DATETIME_OPTIONS = {
    "dateFormat": {"name": "iso"},
    "timeFormat": {"name": "24hour"},
    "timeZone": "utc",
}
NUMBER_OPTIONS = {"precision": 0}
DEFAULT_FIELD_OPTIONS = {
    "date": DATE_OPTIONS,
    "dateTime": DATETIME_OPTIONS,
    "number": NUMBER_OPTIONS,
}

TYPE_MAP = {
    "uuid": "singleLineText",
    "text": "singleLineText",
    "number": "number",
    "datetime": "dateTime",
    "date": "date",
    "enum": "singleLineText",
    "bool": "checkbox",
}

COMPATIBLE_TYPES = {
    "singleLineText": {
        "singleLineText",
        "multilineText",
        "richText",
        "singleSelect",
        "multipleSelects",
    },
    "multilineText": {"multilineText", "singleLineText", "richText"},
    "number": {"number", "currency", "percent"},
    "date": {"date", "dateTime"},
    "dateTime": {"dateTime"},
    "checkbox": {"checkbox"},
    "lastModifiedTime": {"lastModifiedTime"},
}


class _StoreLike(Protocol):
    def fetch_all(self, query: str, params: list[object] | None = None): ...

    def get_mirror_state(self, table_name: str, external_id: str): ...

    def upsert_mirror_state(
        self,
        table_name: str,
        external_id: str,
        record_id: str | None,
        mirror_version: int,
        mirror_updated_at: str | None,
    ) -> None: ...


@dataclass(frozen=True)
class AirtableMapping:
    mirror_fields: dict[str, dict[str, Any]]
    tables: dict[str, dict[str, dict[str, str]]]


@dataclass(frozen=True)
class FieldExpectation:
    name: str
    field_type: str
    options: dict[str, Any] | None
    required: bool
    source: str
    domain_field: str | None


@dataclass(frozen=True)
class TableExpectation:
    key: str
    display_name: str
    fields: dict[str, FieldExpectation]
    domain_to_airtable: dict[str, str]
    human_fields: list[str]


@dataclass(frozen=True)
class SchemaDiff:
    missing_table_ids: list[str]
    missing_tables: list[str]
    missing_fields: dict[str, list[str]]
    type_mismatches: dict[str, list[tuple[str, str, str]]]
    missing_modified_time: list[str]
    misconfigured_modified_time: dict[str, list[str]]
    discovered_table_ids: dict[str, str]

    @property
    def has_errors(self) -> bool:
        return bool(
            self.missing_table_ids
            or self.missing_tables
            or self.missing_fields
            or self.type_mismatches
        )


class MirrorError(RuntimeError):
    pass


def load_mapping(mapping_path: Path) -> AirtableMapping:
    data = yaml.safe_load(mapping_path.read_text(encoding="utf-8")) or {}
    mirror_fields = data.get("mirror_fields", {})
    tables = data.get("tables", {})
    if not isinstance(tables, dict):
        raise MirrorError("Airtable mapping tables must be a mapping.")
    return AirtableMapping(mirror_fields=mirror_fields, tables=tables)


def validate_schema(
    client: AirtableClient,
    mapping: AirtableMapping,
    schema: Schema,
    table_ids: dict[str, str],
    include_modified_time: bool = True,
) -> None:
    diff = diff_schema(client.list_tables(), mapping, schema, table_ids, include_modified_time)
    if diff.has_errors:
        raise MirrorError(_format_schema_errors(diff))


def push_all(
    store: SqliteStore,
    client: AirtableClient,
    mapping: AirtableMapping,
    table_ids: dict[str, str],
    logger: Any | None = None,
) -> None:
    for table_name, table_def in mapping.tables.items():
        table_id = table_ids.get(table_name)
        if not table_id:
            raise MirrorError(f"Missing table id for {table_name} in workspace config.")
        with store.session() as session:
            _push_table(session, client, table_name, table_id, table_def, logger)


def diff_schema(
    tables_meta: list[dict[str, Any]],
    mapping: AirtableMapping,
    schema: Schema,
    table_ids: dict[str, str],
    include_modified_time: bool = True,
) -> SchemaDiff:
    expected = _expected_tables(mapping, schema, include_modified_time)
    tables_by_id = {table["id"]: table for table in tables_meta}
    tables_by_name = {table["name"]: table for table in tables_meta}

    missing_table_ids: list[str] = []
    missing_tables: list[str] = []
    missing_fields: dict[str, list[str]] = {}
    type_mismatches: dict[str, list[tuple[str, str, str]]] = {}
    missing_modified_time: list[str] = []
    misconfigured_modified_time: dict[str, list[str]] = {}
    discovered_table_ids: dict[str, str] = {}

    for table_key, expectation in expected.items():
        table_id = (table_ids.get(table_key) or "").strip()
        table_meta = None
        if table_id:
            table_meta = tables_by_id.get(table_id)
            if table_meta is None:
                missing_tables.append(table_key)
                continue
        else:
            missing_table_ids.append(table_key)
            table_meta = _discover_table_by_name(
                tables_by_name, expectation.display_name, table_key
            )
            if table_meta is not None:
                discovered_table_ids[table_key] = table_meta["id"]

        if table_meta is None:
            continue

        existing_fields = {field["name"]: field for field in table_meta.get("fields", [])}
        missing = [
            field_name for field_name in expectation.fields if field_name not in existing_fields
        ]
        if missing:
            missing_fields[table_key] = missing

        mismatches: list[tuple[str, str, str]] = []
        for field_name, spec in expectation.fields.items():
            field = existing_fields.get(field_name)
            if not field:
                continue
            actual_type = field.get("type")
            if actual_type and not _is_type_compatible(spec.field_type, actual_type):
                mismatches.append((field_name, spec.field_type, actual_type))
        if mismatches:
            type_mismatches[table_key] = mismatches

        if include_modified_time:
            modified_field = existing_fields.get(MODIFIED_TIME_FIELD)
            if not modified_field:
                missing_modified_time.append(table_key)
            else:
                missing_watch_fields = _missing_modified_watch_fields(
                    modified_field, existing_fields, expectation.human_fields
                )
                if missing_watch_fields:
                    misconfigured_modified_time[table_key] = missing_watch_fields

    return SchemaDiff(
        missing_table_ids=missing_table_ids,
        missing_tables=missing_tables,
        missing_fields=missing_fields,
        type_mismatches=type_mismatches,
        missing_modified_time=missing_modified_time,
        misconfigured_modified_time=misconfigured_modified_time,
        discovered_table_ids=discovered_table_ids,
    )


def expected_tables(
    mapping: AirtableMapping, schema: Schema, include_modified_time: bool = True
) -> dict[str, TableExpectation]:
    return _expected_tables(mapping, schema, include_modified_time)


def bootstrap_schema(
    client: AirtableClient,
    mapping: AirtableMapping,
    schema: Schema,
    table_ids: dict[str, str],
    apply: bool = False,
    include_modified_time: bool = True,
) -> tuple[list[str], dict[str, str]]:
    tables_meta = client.list_tables()
    tables_by_id = {table["id"]: table for table in tables_meta}
    tables_by_name = {table["name"]: table for table in tables_meta}
    expected = _expected_tables(mapping, schema, include_modified_time)

    actions: list[str] = []
    discovered_table_ids: dict[str, str] = {}

    for table_key, expectation in expected.items():
        table_id = (table_ids.get(table_key) or "").strip()
        table_meta = None
        if table_id:
            table_meta = tables_by_id.get(table_id)
            if table_meta is None:
                actions.append(f"ERROR: Missing Airtable table for {table_key} ({table_id}).")
                continue
        else:
            table_meta = _discover_table_by_name(
                tables_by_name, expectation.display_name, table_key
            )
            if table_meta is None:
                actions.append(f"CREATE TABLE: {expectation.display_name} ({table_key})")
                if apply:
                    created = client.create_table(
                        expectation.display_name,
                        _table_create_fields(expectation),
                    )
                    table_meta = created
                    table_id = created["id"]
                    tables_by_id[table_id] = created
                    tables_by_name[created["name"]] = created
            else:
                table_id = table_meta["id"]
            if table_meta is not None:
                discovered_table_ids[table_key] = table_id

        if table_meta is None:
            continue

        existing_fields = {field["name"]: field for field in table_meta.get("fields", [])}
        for field_name, spec in expectation.fields.items():
            if field_name in existing_fields:
                continue
            if spec.field_type == "lastModifiedTime":
                continue
            actions.append(
                f"ADD FIELD: {expectation.display_name} -> {field_name} ({spec.field_type})"
            )
            if apply:
                client.create_field(table_id, field_name, spec.field_type, spec.options)

        if include_modified_time and MODIFIED_TIME_FIELD not in existing_fields:
            actions.append(
                f"MANUAL: create {expectation.display_name} -> {MODIFIED_TIME_FIELD} (lastModifiedTime)"
            )

    return actions, discovered_table_ids


def _push_table(
    store: _StoreLike,
    client: AirtableClient,
    table_name: str,
    table_id: str,
    table_def: dict[str, Any],
    logger: Any | None,
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
        if logger is not None:
            logger.log(
                event_type="push",
                entity_type=table_name,
                external_id=external_id,
                changed_fields=list(fields_map.keys()),
                conflict=False,
            )


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


def _expected_tables(
    mapping: AirtableMapping,
    schema: Schema,
    include_modified_time: bool,
) -> dict[str, TableExpectation]:
    expected: dict[str, TableExpectation] = {}
    for table_key, table_def in mapping.tables.items():
        schema_table = schema.tables.get(table_key)
        if not schema_table:
            raise MirrorError(f"Mapping table {table_key} not found in canonical schema.")
        fields_spec = schema_table.get("fields", {})
        fields_map = table_def.get("fields", {})
        if not isinstance(fields_map, dict):
            raise MirrorError(f"Mapping for {table_key} must define fields.")

        fields: dict[str, FieldExpectation] = {}
        domain_to_airtable: dict[str, str] = {}
        human_fields: list[str] = []

        for domain_field, airtable_field in fields_map.items():
            spec = fields_spec.get(domain_field)
            if not spec:
                raise MirrorError(
                    f"Mapping field {table_key}.{domain_field} missing from canonical schema."
                )
            field_type = _airtable_type_for(domain_field, spec)
            fields[airtable_field] = FieldExpectation(
                name=airtable_field,
                field_type=field_type,
                options=None,
                required=spec.get("required", False),
                source="domain",
                domain_field=domain_field,
            )
            domain_to_airtable[domain_field] = airtable_field
            if domain_field not in {"created_at", "updated_at"} and airtable_field != "ExternalId":
                human_fields.append(airtable_field)

        for mirror_name, mirror_spec in mapping.mirror_fields.items():
            mirror_type = _airtable_type_for(mirror_name, mirror_spec)
            fields[mirror_name] = FieldExpectation(
                name=mirror_name,
                field_type=mirror_type,
                options=None,
                required=True,
                source="mirror",
                domain_field=None,
            )

        if include_modified_time:
            fields[MODIFIED_TIME_FIELD] = FieldExpectation(
                name=MODIFIED_TIME_FIELD,
                field_type="lastModifiedTime",
                options=None,
                required=False,
                source="system",
                domain_field=None,
            )

        expected[table_key] = TableExpectation(
            key=table_key,
            display_name=_table_display_name(table_key),
            fields=fields,
            domain_to_airtable=domain_to_airtable,
            human_fields=human_fields,
        )

    return expected


def _table_create_fields(expectation: TableExpectation) -> list[dict[str, Any]]:
    primary_field = _choose_primary_field(expectation)
    ordered_fields = [primary_field] + [
        name for name in expectation.fields if name != primary_field
    ]
    payload: list[dict[str, Any]] = []
    for field_name in ordered_fields:
        spec = expectation.fields[field_name]
        if spec.field_type == "lastModifiedTime":
            continue
        payload.append(_field_payload(spec))
    return payload


def _field_payload(spec: FieldExpectation) -> dict[str, Any]:
    payload: dict[str, Any] = {"name": spec.name, "type": spec.field_type}
    options = spec.options or DEFAULT_FIELD_OPTIONS.get(spec.field_type)
    if options:
        payload["options"] = dict(options)
    return payload


def _choose_primary_field(expectation: TableExpectation) -> str:
    priority = ["name", "full_name", "title"]
    for domain_name in priority:
        airtable_name = expectation.domain_to_airtable.get(domain_name)
        if airtable_name and airtable_name in expectation.fields:
            return airtable_name
    if "ExternalId" in expectation.fields:
        return "ExternalId"
    return next(iter(expectation.fields))


def _table_display_name(table_key: str) -> str:
    return table_key.replace("_", " ").title()


def _airtable_type_for(field_name: str, spec: dict[str, Any]) -> str:
    field_type = spec.get("type") if isinstance(spec, dict) else None
    if field_type not in TYPE_MAP:
        raise MirrorError(f"Unknown field type {field_type} for {field_name}.")
    airtable_type = TYPE_MAP[field_type]
    if airtable_type == "singleLineText" and field_name in LONG_TEXT_FIELDS:
        return "multilineText"
    return airtable_type


def _is_type_compatible(expected: str, actual: str) -> bool:
    if expected == actual:
        return True
    return actual in COMPATIBLE_TYPES.get(expected, set())


def _discover_table_by_name(
    tables_by_name: dict[str, dict[str, Any]], display_name: str, table_key: str
) -> dict[str, Any] | None:
    return tables_by_name.get(display_name) or tables_by_name.get(table_key)


def _missing_modified_watch_fields(
    modified_field: dict[str, Any],
    existing_fields: dict[str, dict[str, Any]],
    expected_field_names: list[str],
) -> list[str]:
    options = modified_field.get("options") or {}
    record_fields = options.get("recordFields")
    if not isinstance(record_fields, list) or not record_fields:
        return expected_field_names
    ids_by_name = {
        field["name"]: field["id"] for field in existing_fields.values() if "id" in field
    }
    missing = []
    for field_name in expected_field_names:
        field_id = ids_by_name.get(field_name)
        if field_id and field_id not in record_fields:
            missing.append(field_name)
    return missing


def _format_schema_errors(diff: SchemaDiff) -> str:
    parts: list[str] = []
    if diff.missing_table_ids:
        parts.append(f"Missing table IDs: {', '.join(sorted(diff.missing_table_ids))}")
    if diff.missing_tables:
        parts.append(f"Unknown Airtable tables: {', '.join(sorted(diff.missing_tables))}")
    for table_key, fields in diff.missing_fields.items():
        parts.append(f"{table_key} missing fields: {', '.join(sorted(fields))}")
    for table_key, mismatches in diff.type_mismatches.items():
        details = ", ".join(
            f"{field} (expected {expected}, got {actual})" for field, expected, actual in mismatches
        )
        parts.append(f"{table_key} type mismatches: {details}")
    for table_key, missing in diff.misconfigured_modified_time.items():
        parts.append(
            f"{table_key} AirtableModifiedAt missing watched fields: {', '.join(sorted(missing))}"
        )
    return "; ".join(parts) if parts else "Airtable schema validation failed."
