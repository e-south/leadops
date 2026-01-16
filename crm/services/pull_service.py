from __future__ import annotations

from pathlib import Path

from crm.adapters.airtable.client import AirtableClient, AirtableError
from crm.adapters.airtable.mirror import load_mapping
from crm.adapters.airtable.pull import PullChange, PullError, PullSummary, pull_records
from crm.config import MirrorConfig
from crm.services.events import EventLogger
from crm.services.sync_state import load_sync_state, save_sync_state
from crm.services.utils import utc_now_iso
from crm.store.migrations import load_schema
from crm.store.sqlite import SqliteStore


class PullServiceError(RuntimeError):
    pass


def _require_airtable_config(mirror: MirrorConfig) -> None:
    if mirror.provider != "airtable":
        raise PullServiceError("Only the Airtable mirror provider is supported.")
    if not mirror.base_id:
        raise PullServiceError("Workspace mirror.base_id is required.")


def _require_api_key() -> str:
    import os

    api_key = os.getenv("AIRTABLE_API_KEY")
    if not api_key:
        raise PullServiceError("AIRTABLE_API_KEY is not set.")
    return api_key


def pull(
    store: SqliteStore,
    mirror: MirrorConfig,
    mapping_path: Path,
    schema_path: Path,
    workspace_path: Path,
    apply: bool,
    accept_remote: set[str] | None = None,
    logger: EventLogger | None = None,
) -> tuple[PullSummary, list[PullChange]]:
    _require_airtable_config(mirror)
    api_key = _require_api_key()
    client = AirtableClient(api_key=api_key, base_id=mirror.base_id or "")
    mapping = load_mapping(mapping_path)
    schema = load_schema(schema_path)
    state = load_sync_state(workspace_path)
    try:
        tables_meta = {table["id"]: table for table in client.list_tables()}
        summary, changes = pull_records(
            store,
            client,
            mapping,
            schema,
            mirror.tables,
            tables_meta,
            last_pull_at=state.last_pull_at,
            apply=apply,
            accept_remote=accept_remote,
            logger=logger,
        )
    except AirtableError as exc:
        status = exc.status_code or 0
        if status in {401, 403}:
            raise PullServiceError("Airtable auth/permission error; check PAT scopes and base access.") from exc
        raise PullServiceError(str(exc)) from exc
    except PullError as exc:
        raise PullServiceError(str(exc)) from exc

    if apply and summary.conflicts == 0:
        now = utc_now_iso()
        state.last_pull_at = {**state.last_pull_at}
        for table_name in mapping.tables:
            state.last_pull_at[table_name] = now
        save_sync_state(workspace_path, state)

    return summary, changes


def record_push(workspace_path: Path) -> None:
    state = load_sync_state(workspace_path)
    state.last_push_at = utc_now_iso()
    save_sync_state(workspace_path, state)


def format_pull_report(summary: PullSummary, changes: list[PullChange]) -> list[str]:
    lines = [
        "summary"
        f" scanned={summary.scanned}"
        f" applied={summary.applied}"
        f" created={summary.created}"
        f" conflicts={summary.conflicts}"
        f" skipped={summary.skipped}"
        f" ignored={summary.ignored}"
    ]
    for change in changes:
        reason = f" reason={change.reason}" if change.reason else ""
        fields = ",".join(sorted(change.changed_fields))
        lines.append(f"{change.table} {change.external_id} {change.action} fields={fields}{reason}")
    return lines
