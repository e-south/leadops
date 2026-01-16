from __future__ import annotations

import os
from pathlib import Path

from crm.adapters.airtable.client import AirtableClient
from crm.adapters.airtable.mirror import load_mapping, push_all, validate_schema
from crm.config import MirrorConfig
from crm.services.events import EventLogger
from crm.store.migrations import load_schema
from crm.store.sqlite import SqliteStore


class SyncError(RuntimeError):
    pass


def _require_airtable_config(mirror: MirrorConfig) -> None:
    if mirror.provider != "airtable":
        raise SyncError("Only the Airtable mirror provider is supported.")
    if not mirror.base_id:
        raise SyncError("Workspace mirror.base_id is required.")


def _require_api_key() -> str:
    api_key = os.getenv("AIRTABLE_API_KEY")
    if not api_key:
        raise SyncError("AIRTABLE_API_KEY is not set.")
    return api_key


def push(
    store: SqliteStore,
    mirror: MirrorConfig,
    mapping_path: Path,
    validate: bool = True,
    logger: EventLogger | None = None,
) -> None:
    _require_airtable_config(mirror)
    api_key = _require_api_key()
    client = AirtableClient(api_key=api_key, base_id=mirror.base_id or "")
    mapping = load_mapping(mapping_path)
    if validate:
        schema = load_schema(Path("schema/canonical.yaml"))
        validate_schema(client, mapping, schema, mirror.tables)
    push_all(store, client, mapping, mirror.tables, logger=logger)


def validate_mirror(store: SqliteStore, mirror: MirrorConfig, mapping_path: Path) -> None:
    _require_airtable_config(mirror)
    api_key = _require_api_key()
    client = AirtableClient(api_key=api_key, base_id=mirror.base_id or "")
    mapping = load_mapping(mapping_path)
    schema = load_schema(Path("schema/canonical.yaml"))
    validate_schema(client, mapping, schema, mirror.tables)
