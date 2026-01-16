from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from crm.adapters.airtable.client import AirtableClient
from crm.adapters.airtable.mirror import (
    MODIFIED_TIME_FIELD,
    AirtableMapping,
    SchemaDiff,
    bootstrap_schema,
    diff_schema,
    expected_tables,
)
from crm.store.migrations import Schema


class BootstrapError(RuntimeError):
    pass


@dataclass(frozen=True)
class BootstrapResult:
    actions: list[str]
    discovered_table_ids: dict[str, str]
    missing_modified_time: list[str]


@dataclass(frozen=True)
class DoctorResult:
    ok: bool
    exit_code: int
    messages: list[str]
    diff: SchemaDiff


def doctor(
    client: AirtableClient,
    mapping: AirtableMapping,
    schema: Schema,
    table_ids: dict[str, str],
    include_modified_time: bool = True,
) -> DoctorResult:
    diff = diff_schema(client.list_tables(), mapping, schema, table_ids, include_modified_time)
    messages: list[str] = []
    exit_code = 0

    if diff.missing_table_ids:
        messages.append(f"Missing table IDs: {', '.join(sorted(diff.missing_table_ids))}")
        exit_code = 1
    if diff.missing_tables:
        messages.append(f"Missing Airtable tables: {', '.join(sorted(diff.missing_tables))}")
        exit_code = 1
    for table_key, fields in diff.missing_fields.items():
        messages.append(f"{table_key} missing fields: {', '.join(sorted(fields))}")
        exit_code = 1
    for table_key, mismatches in diff.type_mismatches.items():
        details = ", ".join(
            f"{field} (expected {expected}, got {actual})" for field, expected, actual in mismatches
        )
        messages.append(f"{table_key} type mismatches: {details}")
        exit_code = 1

    if diff.missing_modified_time:
        messages.append(
            "Missing AirtableModifiedAt fields: " + ", ".join(sorted(diff.missing_modified_time))
        )
        if exit_code == 0:
            exit_code = 1
    for table_key, missing_fields in diff.misconfigured_modified_time.items():
        messages.append(
            f"{table_key} AirtableModifiedAt missing watched fields: {', '.join(sorted(missing_fields))}"
        )
        if exit_code == 0:
            exit_code = 1

    if exit_code == 0:
        messages.append("Airtable mirror schema looks OK.")
    return DoctorResult(ok=exit_code == 0, exit_code=exit_code, messages=messages, diff=diff)


def bootstrap(
    client: AirtableClient,
    mapping: AirtableMapping,
    schema: Schema,
    table_ids: dict[str, str],
    apply: bool = False,
    include_modified_time: bool = True,
) -> BootstrapResult:
    actions, discovered = bootstrap_schema(
        client,
        mapping,
        schema,
        table_ids,
        apply=apply,
        include_modified_time=include_modified_time,
    )
    diff = diff_schema(client.list_tables(), mapping, schema, table_ids, include_modified_time)
    return BootstrapResult(
        actions=actions,
        discovered_table_ids=discovered,
        missing_modified_time=diff.missing_modified_time,
    )


def configure_modified_time_fields(
    client: AirtableClient,
    mapping: AirtableMapping,
    schema: Schema,
    table_ids: dict[str, str],
    apply: bool,
) -> list[str]:
    actions: list[str] = []
    tables = client.list_tables()
    tables_by_id = {table["id"]: table for table in tables}
    expected = expected_tables(mapping, schema, include_modified_time=True)

    for table_key, expectation in expected.items():
        table_id = table_ids.get(table_key)
        if not table_id:
            continue
        table_meta = tables_by_id.get(table_id)
        if not table_meta:
            continue
        fields = table_meta.get("fields", [])
        fields_by_name = {field["name"]: field for field in fields}
        modified_field = fields_by_name.get(MODIFIED_TIME_FIELD)
        if not modified_field:
            continue
        missing_watch = _missing_watch_fields(
            fields_by_name, expectation.human_fields, modified_field
        )
        if missing_watch:
            actions.append(
                f"CONFIGURE FIELD: {expectation.display_name} -> {MODIFIED_TIME_FIELD} watches "
                f"{', '.join(sorted(expectation.human_fields))}"
            )
            if apply:
                field_ids = _watch_field_ids(fields_by_name, expectation.human_fields)
                if field_ids:
                    client.update_field(
                        table_id,
                        modified_field["id"],
                        options=build_modified_time_options(field_ids),
                    )
    return actions


def expected_modified_watch_fields(
    mapping: AirtableMapping, schema: Schema, table_key: str
) -> list[str]:
    tables = expected_tables(mapping, schema, include_modified_time=True)
    expectation = tables.get(table_key)
    if not expectation:
        return []
    return sorted(expectation.human_fields)


def build_modified_time_options(field_ids: list[str]) -> dict[str, Any]:
    return {"isValid": True, "recordFields": field_ids}


def modified_time_field_name() -> str:
    return MODIFIED_TIME_FIELD


def _watch_field_ids(
    fields_by_name: dict[str, dict[str, Any]], field_names: list[str]
) -> list[str]:
    ids = []
    for name in field_names:
        field = fields_by_name.get(name)
        if field and field.get("id"):
            ids.append(field["id"])
    return ids


def _missing_watch_fields(
    fields_by_name: dict[str, dict[str, Any]],
    expected_names: list[str],
    modified_field: dict[str, Any],
) -> list[str]:
    options = modified_field.get("options") or {}
    record_fields = options.get("recordFields")
    if not isinstance(record_fields, list) or not record_fields:
        return expected_names
    missing = []
    for name in expected_names:
        field = fields_by_name.get(name)
        if not field:
            continue
        field_id = field.get("id")
        if field_id and field_id not in record_fields:
            missing.append(name)
    return missing
