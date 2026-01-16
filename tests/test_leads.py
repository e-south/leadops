from datetime import date
from pathlib import Path

from crm.services import leads
from crm.store.sqlite import SqliteStore


def _store(tmp_path: Path) -> SqliteStore:
    db_path = tmp_path / "test.sqlite"
    store = SqliteStore(db_path)
    schema_path = (
        Path(__file__).resolve().parents[1] / "resources" / "schema" / "canonical.yaml"
    )
    store.apply_schema(schema_path)
    return store


def test_add_sponsor_lead(tmp_path: Path) -> None:
    store = _store(tmp_path)
    opp_id = leads.add_sponsor_lead(
        store,
        org_name="Acme Bio",
        domain="acmebio.com",
        contact="Jane Doe <jane@acmebio.com>",
        stage="contacted",
        value=15000,
        tier="gold",
        next_action="Send deck",
        due=date(2026, 1, 20),
        notes=None,
    )
    row = store.fetch_one("SELECT opp_id FROM sponsor_opps WHERE opp_id = ?", (opp_id,))
    assert row is not None


def test_next_actions(tmp_path: Path) -> None:
    store = _store(tmp_path)
    leads.add_sponsor_lead(
        store,
        org_name="Acme Bio",
        domain=None,
        contact=None,
        stage="contacted",
        value=None,
        tier=None,
        next_action="Send deck",
        due=date(2026, 1, 20),
        notes=None,
    )
    actions = leads.next_actions(store, limit=5)
    assert actions
