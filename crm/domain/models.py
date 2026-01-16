from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class Organization:
    org_id: str
    name: str
    domain: str | None
    org_type: str | None
    tags: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Person:
    person_id: str
    org_id: str | None
    full_name: str
    email: str | None
    title: str | None
    linkedin_url: str | None
    tags: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class SponsorOpp:
    opp_id: str
    org_id: str
    primary_person_id: str | None
    stage: str
    expected_value_usd: float | None
    tier: str | None
    probability: float | None
    next_action: str | None
    next_action_due: date | None
    last_touch_at: datetime | None
    last_touch_channel: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Campaign:
    campaign_id: str
    name: str
    kind: str
    start_date: date | None
    end_date: date | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class CampaignMember:
    member_id: str
    campaign_id: str
    person_id: str
    status: str
    segment: str | None
    next_action: str | None
    next_action_due: date | None
    last_touch_at: datetime | None
    last_touch_channel: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Touch:
    touch_id: str
    occurred_at: datetime
    channel: str
    direction: str
    subject: str | None
    body_snippet: str | None
    org_id: str | None
    person_id: str | None
    opp_id: str | None
    member_id: str | None
    external_ref: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Task:
    task_id: str
    due_at: datetime | None
    status: str
    title: str
    details: str | None
    opp_id: str | None
    member_id: str | None
    person_id: str | None
    org_id: str | None
    created_at: datetime
    updated_at: datetime
