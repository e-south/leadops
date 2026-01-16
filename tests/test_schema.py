from pathlib import Path

from crm.store.sqlite import SqliteStore


def test_apply_schema_creates_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite"
    store = SqliteStore(db_path)
    schema_path = (
        Path(__file__).resolve().parents[1] / "resources" / "schema" / "canonical.yaml"
    )
    store.apply_schema(schema_path)

    row = store.fetch_one(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='organizations'"
    )
    assert row is not None
