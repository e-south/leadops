from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

WORKSPACES_DIR = Path("workspaces")
CURRENT_WORKSPACE_FILE = WORKSPACES_DIR / ".current"
WORKSPACE_FILENAME = "workspace.yaml"


@dataclass(frozen=True)
class StoreConfig:
    sqlite_path: Path


@dataclass(frozen=True)
class MirrorConfig:
    provider: str
    base_id: str | None
    tables: dict[str, str]


@dataclass(frozen=True)
class WorkspaceConfig:
    name: str
    store: StoreConfig
    mirror: MirrorConfig | None
    path: Path


class WorkspaceError(RuntimeError):
    pass


def ensure_workspaces_dir() -> None:
    WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)


def set_current_workspace(name: str) -> None:
    ensure_workspaces_dir()
    CURRENT_WORKSPACE_FILE.write_text(f"{name}\n", encoding="utf-8")


def get_current_workspace_name() -> str:
    if not CURRENT_WORKSPACE_FILE.exists():
        raise WorkspaceError("No active workspace. Run `crm workspace use <name>`.")
    return CURRENT_WORKSPACE_FILE.read_text(encoding="utf-8").strip()


def workspace_path(name: str) -> Path:
    return WORKSPACES_DIR / name


def workspace_config_path(name: str) -> Path:
    return workspace_path(name) / WORKSPACE_FILENAME


def load_workspace(name: str | None = None) -> WorkspaceConfig:
    if name is None:
        name = get_current_workspace_name()
    config_path = workspace_config_path(name)
    if not config_path.exists():
        raise WorkspaceError(f"Workspace config not found: {config_path}")
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    store = _parse_store(data.get("store"), config_path)
    mirror = _parse_mirror(data.get("mirror"))
    return WorkspaceConfig(name=name, store=store, mirror=mirror, path=config_path.parent)


def write_workspace_config(name: str, base_id: str | None) -> Path:
    ensure_workspaces_dir()
    ws_dir = workspace_path(name)
    ws_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path = Path("./local.sqlite")
    config = {
        "workspace": name,
        "store": {"sqlite_path": str(sqlite_path)},
        "mirror": {
            "provider": "airtable",
            "base_id": base_id,
            "tables": {
                "organizations": "",
                "people": "",
                "sponsor_opps": "",
                "campaigns": "",
                "campaign_members": "",
                "touches": "",
                "tasks": "",
            },
        },
    }
    config_path = workspace_config_path(name)
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return config_path


def update_workspace_table_ids(config_path: Path, table_ids: dict[str, str]) -> Path:
    if not config_path.exists():
        raise WorkspaceError(f"Workspace config not found: {config_path}")
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    mirror = payload.get("mirror") or {}
    tables = mirror.get("tables") or {}
    if not isinstance(tables, dict):
        raise WorkspaceError("Workspace mirror.tables must be a mapping.")

    for key, value in table_ids.items():
        if value:
            tables[key] = value
    mirror["tables"] = tables
    payload["mirror"] = mirror

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = config_path.with_suffix(f".bak.{timestamp}")
    backup_path.write_text(config_path.read_text(encoding="utf-8"), encoding="utf-8")
    config_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return backup_path


def _parse_store(store_data: Any, config_path: Path) -> StoreConfig:
    if not isinstance(store_data, dict):
        raise WorkspaceError("Invalid workspace store configuration.")
    sqlite_path_raw = store_data.get("sqlite_path")
    if not sqlite_path_raw:
        raise WorkspaceError("Workspace store.sqlite_path is required.")
    sqlite_path = _resolve_sqlite_path(sqlite_path_raw, config_path)
    if sqlite_path is None:
        raise WorkspaceError("Workspace store.sqlite_path must be a string.")
    return StoreConfig(sqlite_path=sqlite_path)


def _resolve_sqlite_path(sqlite_path_raw: Any, config_path: Path) -> Path | None:
    if not isinstance(sqlite_path_raw, str):
        return None
    raw_path = Path(sqlite_path_raw)
    if raw_path.is_absolute():
        return raw_path
    # Prefer paths relative to the workspace directory.
    workspace_dir = config_path.parent
    if raw_path.parts and raw_path.parts[0] == WORKSPACES_DIR.name:
        # Backward-compat: allow paths that already include "workspaces/..." from repo root.
        return (workspace_dir.parent.parent / raw_path).resolve()
    return (workspace_dir / raw_path).resolve()


def _parse_mirror(mirror_data: Any) -> MirrorConfig | None:
    if mirror_data is None:
        return None
    if not isinstance(mirror_data, dict):
        raise WorkspaceError("Invalid workspace mirror configuration.")
    provider = mirror_data.get("provider")
    base_id = mirror_data.get("base_id")
    tables = mirror_data.get("tables") or {}
    if not isinstance(tables, dict):
        raise WorkspaceError("Workspace mirror.tables must be a mapping.")
    return MirrorConfig(provider=provider or "", base_id=base_id, tables=tables)
