from pathlib import Path

from crm.adapters.airtable.mirror import load_mapping


def test_load_mapping_has_tables() -> None:
    mapping = load_mapping(
        Path(__file__).resolve().parents[1]
        / "resources"
        / "schema"
        / "airtable.mapping.yaml"
    )
    assert "organizations" in mapping.tables
    assert "ExternalId" in mapping.mirror_fields
