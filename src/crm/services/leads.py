from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Protocol
from uuid import uuid4

from crm.domain import rules
from crm.domain.stages import CampaignKind, CampaignMemberStatus, SponsorStage, SponsorTier
from crm.services.utils import parse_contact, utc_now_iso
from crm.store.sqlite import SqliteStore


class _StoreLike(Protocol):
    def execute(self, query: str, params: Iterable[object] | None = None) -> None: ...

    def fetch_one(self, query: str, params: Iterable[object] | None = None): ...


@dataclass(frozen=True)
class LeadNextItem:
    pipeline: str
    record_id: str
    org_or_person: str
    next_action: str | None
    next_action_due: str | None


def add_sponsor_lead(
    store: SqliteStore,
    org_name: str,
    domain: str | None,
    contact: str | None,
    stage: str,
    value: float | None,
    tier: str | None,
    next_action: str | None,
    due: date | None,
    notes: str | None,
) -> str:
    rules.require(org_name, "org")
    rules.validate_enum(stage, [s.value for s in SponsorStage], "stage")
    if tier:
        rules.validate_enum(tier, [t.value for t in SponsorTier], "tier")

    now = utc_now_iso()
    with store.session() as session:
        org_id = _get_or_create_org(session, org_name, domain, now)

        person_id = None
        if contact:
            name, email = parse_contact(contact)
            person_id = _get_or_create_person(session, org_id, name, email, now)

        opp_id = str(uuid4())
        session.execute(
            "INSERT INTO sponsor_opps (opp_id, org_id, primary_person_id, stage, expected_value_usd, tier, "
            "probability, next_action, next_action_due, last_touch_at, last_touch_channel, notes, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                opp_id,
                org_id,
                person_id,
                stage,
                value,
                tier,
                None,
                next_action,
                due.isoformat() if due else None,
                None,
                None,
                notes,
                now,
                now,
            ),
        )
        return opp_id


def add_attendee_lead(
    store: SqliteStore,
    campaign_name: str,
    person: str,
    status: str,
    segment: str | None,
    next_action: str | None,
    due: date | None,
    notes: str | None,
) -> str:
    rules.require(campaign_name, "campaign")
    rules.require(person, "person")
    rules.validate_enum(status, [s.value for s in CampaignMemberStatus], "status")

    now = utc_now_iso()
    with store.session() as session:
        campaign_id = _get_or_create_campaign(session, campaign_name, now)
        person_name, email = parse_contact(person)
        person_id = _get_or_create_person(session, None, person_name, email, now)

        member_id = str(uuid4())
        session.execute(
            "INSERT INTO campaign_members (member_id, campaign_id, person_id, status, segment, next_action, "
            "next_action_due, last_touch_at, last_touch_channel, notes, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                member_id,
                campaign_id,
                person_id,
                status,
                segment,
                next_action,
                due.isoformat() if due else None,
                None,
                None,
                notes,
                now,
                now,
            ),
        )
        return member_id


def list_sponsor_leads(store: SqliteStore, stage: str | None) -> list[dict[str, str]]:
    params: list[str] = []
    where = ""
    if stage:
        where = "WHERE sponsor_opps.stage = ?"
        params.append(stage)
    query = (
        "SELECT sponsor_opps.opp_id, organizations.name AS org_name, sponsor_opps.stage, "
        "sponsor_opps.next_action, sponsor_opps.next_action_due "
        "FROM sponsor_opps JOIN organizations ON sponsor_opps.org_id = organizations.org_id "
        f"{where} ORDER BY sponsor_opps.updated_at DESC"
    )
    rows = store.fetch_all(query, params)
    return [dict(row) for row in rows]


def list_attendee_leads(store: SqliteStore, status: str | None) -> list[dict[str, str]]:
    params: list[str] = []
    where = ""
    if status:
        where = "WHERE campaign_members.status = ?"
        params.append(status)
    query = (
        "SELECT campaign_members.member_id, campaigns.name AS campaign_name, people.full_name, "
        "campaign_members.status, campaign_members.next_action, campaign_members.next_action_due "
        "FROM campaign_members "
        "JOIN campaigns ON campaign_members.campaign_id = campaigns.campaign_id "
        "JOIN people ON campaign_members.person_id = people.person_id "
        f"{where} ORDER BY campaign_members.updated_at DESC"
    )
    rows = store.fetch_all(query, params)
    return [dict(row) for row in rows]


def next_actions(store: SqliteStore, limit: int = 10) -> list[LeadNextItem]:
    query = (
        "SELECT 'sponsor' AS pipeline, sponsor_opps.opp_id AS record_id, organizations.name AS name, "
        "sponsor_opps.next_action, sponsor_opps.next_action_due "
        "FROM sponsor_opps JOIN organizations ON sponsor_opps.org_id = organizations.org_id "
        "WHERE sponsor_opps.next_action_due IS NOT NULL "
        "UNION ALL "
        "SELECT 'attendee' AS pipeline, campaign_members.member_id AS record_id, people.full_name AS name, "
        "campaign_members.next_action, campaign_members.next_action_due "
        "FROM campaign_members JOIN people ON campaign_members.person_id = people.person_id "
        "WHERE campaign_members.next_action_due IS NOT NULL "
        "ORDER BY next_action_due ASC LIMIT ?"
    )
    rows = store.fetch_all(query, (limit,))
    return [
        LeadNextItem(
            pipeline=row["pipeline"],
            record_id=row["record_id"],
            org_or_person=row["name"],
            next_action=row["next_action"],
            next_action_due=row["next_action_due"],
        )
        for row in rows
    ]


def _get_or_create_org(store: _StoreLike, name: str, domain: str | None, now: str) -> str:
    if domain:
        row = store.fetch_one("SELECT org_id FROM organizations WHERE domain = ?", (domain,))
        if row:
            return row["org_id"]
    row = store.fetch_one("SELECT org_id FROM organizations WHERE name = ?", (name,))
    if row:
        return row["org_id"]
    org_id = str(uuid4())
    store.execute(
        "INSERT INTO organizations (org_id, name, domain, org_type, tags, notes, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (org_id, name, domain, None, None, None, now, now),
    )
    return org_id


def _get_or_create_person(
    store: _StoreLike, org_id: str | None, name: str, email: str | None, now: str
) -> str:
    if email:
        row = store.fetch_one("SELECT person_id FROM people WHERE email = ?", (email,))
        if row:
            return row["person_id"]
    row = store.fetch_one("SELECT person_id FROM people WHERE full_name = ?", (name,))
    if row:
        return row["person_id"]
    person_id = str(uuid4())
    store.execute(
        "INSERT INTO people (person_id, org_id, full_name, email, title, linkedin_url, tags, notes, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (person_id, org_id, name, email, None, None, None, None, now, now),
    )
    return person_id


def _get_or_create_campaign(store: _StoreLike, name: str, now: str) -> str:
    row = store.fetch_one("SELECT campaign_id FROM campaigns WHERE name = ?", (name,))
    if row:
        return row["campaign_id"]
    campaign_id = str(uuid4())
    store.execute(
        "INSERT INTO campaigns (campaign_id, name, kind, start_date, end_date, notes, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (campaign_id, name, CampaignKind.ATTENDEE_OUTREACH.value, None, None, None, now, now),
    )
    return campaign_id
