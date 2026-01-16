from crm.adapters.airtable.mirror import AirtableMapping, diff_schema
from crm.store.migrations import Schema


def test_modified_time_misconfigured() -> None:
    mapping = AirtableMapping(
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
                    "notes": "Notes",
                    "created_at": "Created At",
                    "updated_at": "Updated At",
                }
            }
        },
    )
    schema = Schema(
        version=1,
        enums={},
        tables={
            "widgets": {
                "fields": {
                    "widget_id": {"type": "uuid", "required": True},
                    "name": {"type": "text"},
                    "notes": {"type": "text"},
                    "created_at": {"type": "datetime"},
                    "updated_at": {"type": "datetime"},
                }
            }
        },
    )
    tables_meta = [
        {
            "id": "tblWidgets",
            "name": "Widgets",
            "fields": [
                {"id": "fldExternal", "name": "ExternalId", "type": "singleLineText"},
                {"id": "fldName", "name": "Name", "type": "singleLineText"},
                {"id": "fldNotes", "name": "Notes", "type": "multilineText"},
                {"id": "fldCreated", "name": "Created At", "type": "dateTime"},
                {"id": "fldUpdated", "name": "Updated At", "type": "dateTime"},
                {
                    "id": "fldModified",
                    "name": "AirtableModifiedAt",
                    "type": "lastModifiedTime",
                    "options": {"recordFields": ["fldName"]},
                },
            ],
        }
    ]

    diff = diff_schema(tables_meta, mapping, schema, {"widgets": "tblWidgets"}, True)
    assert diff.misconfigured_modified_time["widgets"] == ["Notes"]
