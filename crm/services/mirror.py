from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from crm.adapters.airtable.client import AirtableClient, AirtableError
from crm.adapters.airtable.mirror import load_mapping
from crm.adapters.airtable.schema import (
    BootstrapResult,
    DoctorResult,
    bootstrap,
    configure_modified_time_fields,
    doctor,
)
from crm.config import MirrorConfig, WorkspaceConfig
from crm.store.migrations import load_schema


class MirrorServiceError(RuntimeError):
    pass


class MirrorAuthError(MirrorServiceError):
    pass


@dataclass(frozen=True)
class MirrorBootstrapResult:
    actions: list[str]
    discovered_table_ids: dict[str, str]
    missing_modified_time: list[str]


@dataclass(frozen=True)
class MirrorDoctorResult:
    exit_code: int
    messages: list[str]
    diff: Any


def _require_api_key() -> str:
    api_key = os.getenv("AIRTABLE_API_KEY")
    if not api_key:
        raise MirrorServiceError("AIRTABLE_API_KEY is not set.")
    return api_key


def _require_airtable_config(mirror: MirrorConfig) -> None:
    if mirror.provider != "airtable":
        raise MirrorServiceError("Only the Airtable mirror provider is supported.")
    if not mirror.base_id:
        raise MirrorServiceError("Workspace mirror.base_id is required.")


def _client(mirror: MirrorConfig) -> AirtableClient:
    api_key = _require_api_key()
    return AirtableClient(api_key=api_key, base_id=mirror.base_id or "")


def doctor_airtable(
    workspace: WorkspaceConfig,
    mapping_path: Path,
    schema_path: Path,
    include_modified_time: bool = True,
) -> MirrorDoctorResult:
    if workspace.mirror is None:
        raise MirrorServiceError("Workspace mirror config is missing.")
    _require_airtable_config(workspace.mirror)
    client = _client(workspace.mirror)
    mapping = load_mapping(mapping_path)
    schema = load_schema(schema_path)
    try:
        result: DoctorResult = doctor(
            client,
            mapping,
            schema,
            workspace.mirror.tables,
            include_modified_time=include_modified_time,
        )
    except AirtableError as exc:
        status = exc.status_code or 0
        if status in {401, 403}:
            raise MirrorAuthError(
                "Airtable auth/permission error; check PAT scopes and base access."
            ) from exc
        raise MirrorServiceError(str(exc)) from exc

    return MirrorDoctorResult(exit_code=result.exit_code, messages=result.messages, diff=result.diff)


def bootstrap_airtable(
    workspace: WorkspaceConfig,
    mapping_path: Path,
    schema_path: Path,
    apply: bool,
    include_modified_time: bool = True,
) -> MirrorBootstrapResult:
    if workspace.mirror is None:
        raise MirrorServiceError("Workspace mirror config is missing.")
    _require_airtable_config(workspace.mirror)
    client = _client(workspace.mirror)
    mapping = load_mapping(mapping_path)
    schema = load_schema(schema_path)
    try:
        result: BootstrapResult = bootstrap(
            client,
            mapping,
            schema,
            workspace.mirror.tables,
            apply=apply,
            include_modified_time=include_modified_time,
        )
        merged_table_ids = {**workspace.mirror.tables, **result.discovered_table_ids}
        config_actions = configure_modified_time_fields(
            client, mapping, schema, merged_table_ids, apply=apply
        )
    except AirtableError as exc:
        status = exc.status_code or 0
        if status in {401, 403}:
            raise MirrorAuthError(
                "Airtable auth/permission error; check PAT scopes and base access."
            ) from exc
        raise MirrorServiceError(str(exc)) from exc

    return MirrorBootstrapResult(
        actions=[*result.actions, *config_actions],
        discovered_table_ids=result.discovered_table_ids,
        missing_modified_time=result.missing_modified_time,
    )
