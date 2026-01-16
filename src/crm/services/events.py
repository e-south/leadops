from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class EventLogger:
    path: Path
    workspace: str
    enabled: bool = True

    def log(
        self,
        *,
        event_type: str,
        entity_type: str,
        external_id: str,
        changed_fields: Iterable[str] | None = None,
        conflict: bool = False,
    ) -> None:
        if not self.enabled:
            return
        payload = {
            "ts": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "workspace": self.workspace,
            "entity_type": entity_type,
            "external_id": external_id,
            "event_type": event_type,
            "changed_fields": list(changed_fields or []),
            "conflict": conflict,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")
