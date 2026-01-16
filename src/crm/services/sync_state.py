from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SyncState:
    last_pull_at: dict[str, str]
    last_push_at: str | None
    schema_fingerprint: str | None = None


SYNC_STATE_FILE = ".sync_state.json"


def load_sync_state(workspace_path: Path) -> SyncState:
    path = workspace_path / SYNC_STATE_FILE
    if not path.exists():
        return SyncState(last_pull_at={}, last_push_at=None)
    data = json.loads(path.read_text(encoding="utf-8"))
    last_pull_at = data.get("last_pull_at") or {}
    last_push_at = data.get("last_push_at")
    schema_fingerprint = data.get("schema_fingerprint")
    if not isinstance(last_pull_at, dict):
        last_pull_at = {}
    return SyncState(
        last_pull_at={str(k): str(v) for k, v in last_pull_at.items()},
        last_push_at=str(last_push_at) if last_push_at else None,
        schema_fingerprint=str(schema_fingerprint) if schema_fingerprint else None,
    )


def save_sync_state(workspace_path: Path, state: SyncState) -> None:
    path = workspace_path / SYNC_STATE_FILE
    payload: dict[str, Any] = {
        "last_pull_at": state.last_pull_at,
        "last_push_at": state.last_push_at,
    }
    if state.schema_fingerprint:
        payload["schema_fingerprint"] = state.schema_fingerprint
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
