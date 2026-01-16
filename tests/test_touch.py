from datetime import date
from pathlib import Path

from crm.services import leads, touch
from crm.store.sqlite import SqliteStore


def _store(tmp_path: Path) -> SqliteStore:
    db_path = tmp_path / "test.sqlite"
    store = SqliteStore(db_path)
    schema_path = (
        Path(__file__).resolve().parents[1] / "resources" / "schema" / "canonical.yaml"
    )
    store.apply_schema(schema_path)
    return store


def test_touch_does_not_clear_next_action(tmp_path: Path) -> None:
    store = _store(tmp_path)
    opp_id = leads.add_sponsor_lead(
        store,
        org_name="Acme Bio",
        domain="acmebio.com",
        contact=None,
        stage="contacted",
        value=None,
        tier=None,
        next_action="Send deck",
        due=date(2026, 1, 20),
        notes=None,
    )
    touch.log_touch(
        store,
        record_id=opp_id,
        channel="email",
        direction="outbound",
        subject="Sponsor intro",
        note=None,
        next_action=None,
        due=None,
    )
    row = store.fetch_one(
        "SELECT next_action, next_action_due FROM sponsor_opps WHERE opp_id = ?",
        (opp_id,),
    )
    assert row["next_action"] == "Send deck"
    assert row["next_action_due"] == "2026-01-20"
