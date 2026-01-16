from __future__ import annotations

from enum import Enum


class SponsorStage(str, Enum):
    TARGETED = "targeted"
    CONTACT_FOUND = "contact_found"
    CONTACTED = "contacted"
    ENGAGED = "engaged"
    CALL_SCHEDULED = "call_scheduled"
    PROPOSAL_SENT = "proposal_sent"
    NEGOTIATION = "negotiation"
    COMMITTED = "committed"
    INVOICING = "invoicing"
    PAID = "paid"
    CLOSED_LOST = "closed_lost"


class SponsorTier(str, Enum):
    PLATINUM = "platinum"
    GOLD = "gold"
    SILVER = "silver"
    OTHER = "other"


class CampaignKind(str, Enum):
    ATTENDEE_OUTREACH = "attendee_outreach"
    SPEAKER_OUTREACH = "speaker_outreach"
    OTHER = "other"


class CampaignMemberStatus(str, Enum):
    IDENTIFIED = "identified"
    INVITED = "invited"
    INTERESTED = "interested"
    REGISTERED = "registered"
    ATTENDING = "attending"
    DECLINED = "declined"
    UNRESPONSIVE = "unresponsive"


class TouchChannel(str, Enum):
    EMAIL = "email"
    CALL = "call"
    MEETING = "meeting"
    LINKEDIN = "linkedin"
    OTHER = "other"


class TouchDirection(str, Enum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class TaskStatus(str, Enum):
    OPEN = "open"
    DONE = "done"
    CANCELED = "canceled"
