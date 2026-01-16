import sqlite3
from pathlib import Path

import pytest

from crm.store.sqlite import SqliteStore


def test_foreign_keys_enforced(tmp_path: Path) -> None:
    store = SqliteStore(tmp_path / "test.sqlite")
    schema_path = (
        Path(__file__).resolve().parents[1] / "resources" / "schema" / "canonical.yaml"
    )
    store.apply_schema(schema_path)

    with pytest.raises(sqlite3.IntegrityError):
        store.execute(
            "INSERT INTO sponsor_opps (opp_id, org_id, stage, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("opp-1", "missing-org", "contacted", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        )
