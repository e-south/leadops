from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime


class ValidationError(ValueError):
    pass


def require(value: str | None, field: str) -> None:
    if value is None or str(value).strip() == "":
        raise ValidationError(f"{field} is required.")


def validate_enum(value: str | None, allowed: Iterable[str], field: str) -> None:
    if value is None:
        return
    if value not in allowed:
        raise ValidationError(f"{field} must be one of: {', '.join(sorted(allowed))}")


def parse_date(value: str | None, field: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"{field} must be YYYY-MM-DD.") from exc


def parse_datetime(value: str | None, field: str) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"{field} must be ISO 8601.") from exc
