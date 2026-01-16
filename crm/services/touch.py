from __future__ import annotations

from datetime import date
from uuid import uuid4

from crm.domain import rules
from crm.domain.stages import TouchChannel, TouchDirection
from crm.services.utils import utc_now_iso
from crm.store.sqlite import SqliteStore


class TouchError(RuntimeError):
    pass


def log_touch(
    store: SqliteStore,
    record_id: str,
    channel: str,
    direction: str,
    subject: str | None,
    note: str | None,
    next_action: str | None,
    due: date | None,
) -> str:
    rules.validate_enum(channel, [c.value for c in TouchChannel], "channel")
    rules.validate_enum(direction, [d.value for d in TouchDirection], "direction")

    now = utc_now_iso()
    touch_id = str(uuid4())

    target = _resolve_target(store, record_id)
    if target is None:
        raise TouchError("Lead ID not found in sponsor_opps or campaign_members.")

    with store.session() as session:
        session.execute(
            "INSERT INTO touches (touch_id, occurred_at, channel, direction, subject, body_snippet, org_id, person_id, "
            "opp_id, member_id, external_ref, notes, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                touch_id,
                now,
                channel,
                direction,
                subject,
                None,
                target.get("org_id"),
                target.get("person_id"),
                target.get("opp_id"),
                target.get("member_id"),
                None,
                note,
                now,
                now,
            ),
        )

        due_value = due.isoformat() if due else None
        if target.get("opp_id"):
            session.execute(
                "UPDATE sponsor_opps SET last_touch_at = ?, last_touch_channel = ?, next_action = ?, "
                "next_action_due = ?, updated_at = ? WHERE opp_id = ?",
                (now, channel, next_action, due_value, now, target["opp_id"]),
            )
        if target.get("member_id"):
            session.execute(
                "UPDATE campaign_members SET last_touch_at = ?, last_touch_channel = ?, next_action = ?, "
                "next_action_due = ?, updated_at = ? WHERE member_id = ?",
                (now, channel, next_action, due_value, now, target["member_id"]),
            )

    return touch_id


def _resolve_target(store: SqliteStore, record_id: str) -> dict[str, str] | None:
    opp = store.fetch_one(
        "SELECT opp_id, org_id, primary_person_id FROM sponsor_opps WHERE opp_id = ?",
        (record_id,),
    )
    if opp:
        return {
            "opp_id": opp["opp_id"],
            "org_id": opp["org_id"],
            "person_id": opp["primary_person_id"],
        }

    member = store.fetch_one(
        "SELECT member_id, person_id, campaign_id FROM campaign_members WHERE member_id = ?",
        (record_id,),
    )
    if member:
        return {
            "member_id": member["member_id"],
            "person_id": member["person_id"],
            "org_id": None,
        }
    return None
