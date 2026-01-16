from pathlib import Path

import yaml

from crm.adapters.airtable.mirror import AirtableMapping
from crm.adapters.airtable.pull import pull_records
from crm.store.migrations import load_schema
from crm.store.sqlite import SqliteStore


class FakeClient:
    def __init__(self) -> None:
        self.calls = []

    def list_records(self, table_id, fields=None, filter_formula=None):
        self.calls.append(
            {"table_id": table_id, "fields": fields, "filter_formula": filter_formula}
        )
        return []


def _schema_path(tmp_path: Path) -> Path:
    schema = {
        "version": 1,
        "enums": {},
        "tables": {
            "widgets": {
                "primary_key": "widget_id",
                "fields": {
                    "widget_id": {"type": "uuid", "required": True},
                    "name": {"type": "text"},
                    "created_at": {"type": "datetime", "required": True},
                    "updated_at": {"type": "datetime", "required": True},
                },
            },
            "mirror_state": {
                "primary_key": ["table_name", "external_id"],
                "fields": {
                    "table_name": {"type": "text", "required": True},
                    "external_id": {"type": "text", "required": True},
                    "record_id": {"type": "text"},
                    "mirror_version": {"type": "number"},
                    "mirror_updated_at": {"type": "datetime"},
                },
            },
        },
    }
    path = tmp_path / "schema.yaml"
    path.write_text(yaml.safe_dump(schema, sort_keys=False), encoding="utf-8")
    return path


def _mapping() -> AirtableMapping:
    return AirtableMapping(
        mirror_fields={
            "ExternalId": {"type": "text"},
            "MirrorVersion": {"type": "number"},
            "MirrorUpdatedAt": {"type": "datetime"},
        },
        tables={
            "widgets": {
                "fields": {
                    "widget_id": "ExternalId",
                    "name": "Name",
                    "created_at": "Created At",
                    "updated_at": "Updated At",
                }
            }
        },
    )


def test_pull_omits_modified_field_when_missing(tmp_path: Path) -> None:
    schema_path = _schema_path(tmp_path)
    schema = load_schema(schema_path)
    store = SqliteStore(tmp_path / "test.sqlite")
    store.apply_schema(schema_path)
    client = FakeClient()
    tables_meta = {
        "tblWidgets": {
            "id": "tblWidgets",
            "name": "Widgets",
            "fields": [
                {"id": "fldExternal", "name": "ExternalId", "type": "singleLineText"},
                {"id": "fldName", "name": "Name", "type": "singleLineText"},
            ],
        }
    }

    pull_records(
        store,
        client,
        _mapping(),
        schema,
        {"widgets": "tblWidgets"},
        tables_meta,
        last_pull_at={"widgets": "2026-01-01T00:00:00+00:00"},
        apply=False,
    )

    call = client.calls[0]
    assert "AirtableModifiedAt" not in call["fields"]
    assert call["filter_formula"] is None


def test_pull_uses_modified_field_when_present(tmp_path: Path) -> None:
    schema_path = _schema_path(tmp_path)
    schema = load_schema(schema_path)
    store = SqliteStore(tmp_path / "test.sqlite")
    store.apply_schema(schema_path)
    client = FakeClient()
    tables_meta = {
        "tblWidgets": {
            "id": "tblWidgets",
            "name": "Widgets",
            "fields": [
                {"id": "fldExternal", "name": "ExternalId", "type": "singleLineText"},
                {"id": "fldName", "name": "Name", "type": "singleLineText"},
                {
                    "id": "fldModified",
                    "name": "AirtableModifiedAt",
                    "type": "lastModifiedTime",
                },
            ],
        }
    }

    pull_records(
        store,
        client,
        _mapping(),
        schema,
        {"widgets": "tblWidgets"},
        tables_meta,
        last_pull_at={"widgets": "2026-01-01T00:00:00+00:00"},
        apply=False,
    )

    call = client.calls[0]
    assert "AirtableModifiedAt" in call["fields"]
    assert call["filter_formula"] is not None
