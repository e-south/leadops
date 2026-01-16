from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

EXCLUDED_FIELDS = {"created_at", "updated_at"}


@dataclass(frozen=True)
class PullDecision:
    action: str
    changed_fields: list[str]
    reason: str | None = None


def diff_fields(
    *,
    local_row: dict[str, Any] | None,
    remote_fields: dict[str, Any],
    field_map: dict[str, str],
    schema_fields: dict[str, Any],
) -> list[str]:
    changed: list[str] = []
    for local_field, airtable_field in field_map.items():
        if local_field in EXCLUDED_FIELDS:
            continue
        spec = schema_fields.get(local_field) or {}
        field_type = spec.get("type")
        local_value = local_row.get(local_field) if local_row else None
        remote_value = remote_fields.get(airtable_field)
        if not _values_equal(local_value, remote_value, field_type):
            changed.append(local_field)
    return changed


def has_local_changes(local_row: dict[str, Any] | None, mirror_state: dict[str, Any] | None) -> bool:
    if local_row is None:
        return False
    if mirror_state is None:
        return True
    local_updated_at = _parse_datetime(local_row.get("updated_at"))
    mirror_updated_at = _parse_datetime(mirror_state.get("mirror_updated_at"))
    if mirror_updated_at is None:
        return True
    if local_updated_at is None:
        return False
    return local_updated_at > mirror_updated_at


def decide_pull_action(
    *,
    local_row: dict[str, Any] | None,
    mirror_state: dict[str, Any] | None,
    changed_fields: list[str],
    remote_modified_at: datetime | str | None = None,
) -> PullDecision:
    if not changed_fields:
        return PullDecision(action="skip", changed_fields=[])
    if local_row is None:
        return PullDecision(action="create", changed_fields=changed_fields)

    local_changed = has_local_changes(local_row, mirror_state)
    remote_changed = has_remote_changes(remote_modified_at, mirror_state)

    if remote_changed is False and local_changed:
        return PullDecision(action="skip", changed_fields=changed_fields, reason="local_changes")
    if local_changed and remote_changed in {True, None}:
        return PullDecision(action="conflict", changed_fields=changed_fields, reason="local_changes")
    return PullDecision(action="apply", changed_fields=changed_fields)


def _values_equal(local_value: Any, remote_value: Any, field_type: str | None) -> bool:
    return _normalize_value(local_value, field_type) == _normalize_value(remote_value, field_type)


def _normalize_value(value: Any, field_type: str | None) -> Any:
    if value is None or value == "":
        return None
    if isinstance(value, list):
        normalized = [_normalize_value(item, field_type) for item in value]
        return tuple(str(item) for item in normalized if item is not None)
    if isinstance(value, dict):
        if "name" in value:
            return str(value.get("name"))
        return str(value)

    if field_type in {"uuid", "text", "enum"}:
        return str(value)
    if field_type == "number":
        try:
            return float(value)
        except (TypeError, ValueError):
            return str(value)
    if field_type == "bool":
        if isinstance(value, str):
            return value.lower() in {"true", "1", "yes"}
        return bool(value)
    if field_type == "date":
        return _parse_date(value)
    if field_type == "datetime":
        return _parse_datetime(value)
    return str(value)


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.split("T")[0])
        except ValueError:
            return None
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        cleaned = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(cleaned)
        except ValueError:
            return None
    return None


def has_remote_changes(
    remote_modified_at: datetime | str | None,
    mirror_state: dict[str, Any] | None,
) -> bool | None:
    if remote_modified_at is None:
        return None
    remote_dt = _parse_datetime(remote_modified_at)
    if remote_dt is None:
        return None
    mirror_updated_at = _parse_datetime(mirror_state.get("mirror_updated_at")) if mirror_state else None
    if mirror_updated_at is None:
        return True
    return remote_dt > mirror_updated_at
