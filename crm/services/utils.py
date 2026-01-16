from __future__ import annotations

import re
from datetime import UTC, date, datetime

CONTACT_RE = re.compile(r"^(?P<name>[^<]+?)(?:\s*<(?P<email>[^>]+)>)?$")


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def today_iso() -> str:
    return date.today().isoformat()


def parse_contact(contact: str) -> tuple[str, str | None]:
    match = CONTACT_RE.match(contact.strip())
    if not match:
        return contact.strip(), None
    name = match.group("name").strip()
    email = match.group("email")
    return name, email.strip() if email else None


def normalize_tags(tags: list[str] | None) -> str | None:
    if not tags:
        return None
    cleaned = [tag.strip() for tag in tags if tag.strip()]
    return ", ".join(cleaned) if cleaned else None
