from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

from crm import __version__
from crm.adapters.airtable.client import AirtableClient
from crm.adapters.airtable.mirror import MirrorError
from crm.config import (
    WorkspaceError,
    ensure_workspaces_dir,
    load_workspace,
    set_current_workspace,
    update_workspace_table_ids,
    workspace_config_path,
    write_workspace_config,
)
from crm.domain import rules
from crm.domain.rules import ValidationError
from crm.domain.stages import CampaignMemberStatus, SponsorStage
from crm.services import exports, leads, mirror, pull_service, sync, touch
from crm.services.events import EventLogger
from crm.services.mirror import MirrorAuthError, MirrorServiceError
from crm.services.pull_service import PullServiceError
from crm.services.sync import SyncError
from crm.services.touch import TouchError
from crm.services.utils import today_iso
from crm.store.sqlite import SqliteStore

app = typer.Typer(help="Leadops CLI")
workspace_app = typer.Typer(help="Workspace management")
lead_app = typer.Typer(help="Lead operations")
schema_app = typer.Typer(help="Schema operations")
sync_app = typer.Typer(help="Mirror sync")
export_app = typer.Typer(help="Exports")
mirror_app = typer.Typer(help="Mirror diagnostics and bootstrap")
open_app = typer.Typer(help="Open records in external systems")

app.add_typer(workspace_app, name="workspace")
app.add_typer(lead_app, name="lead")
app.add_typer(schema_app, name="schema")
app.add_typer(sync_app, name="sync")
app.add_typer(export_app, name="export")
app.add_typer(mirror_app, name="mirror")
app.add_typer(open_app, name="open")

SCHEMA_PATH = Path("resources/schema/canonical.yaml")
MAPPING_PATH = Path("resources/schema/airtable.mapping.yaml")


@app.callback()
def version_callback(version: bool = typer.Option(False, "--version", help="Show version and exit.")):
    if version:
        typer.echo(__version__)
        raise typer.Exit()


@app.command("init")
def init() -> None:
    """Initialize directories for workspaces and outputs."""
    ensure_workspaces_dir()
    Path("data").mkdir(exist_ok=True)
    Path("exports").mkdir(exist_ok=True)
    typer.echo("Initialized leadops directories.")


@workspace_app.command("add")
def workspace_add(
    name: str = typer.Argument(...),
    base: str | None = typer.Option(None, "--base", help="Airtable base ID (app...)."),
    use: bool = typer.Option(True, "--use/--no-use", help="Set as current workspace."),
    force: bool = typer.Option(
        False, "--force", help="Overwrite existing workspace config if it exists."
    ),
) -> None:
    config_path = workspace_config_path(name)
    if config_path.exists() and not force:
        raise typer.BadParameter(
            f"Workspace already exists: {config_path}. Use --force to overwrite."
        )
    config_path = write_workspace_config(name, base)
    if use:
        set_current_workspace(name)
    typer.echo(f"Workspace created: {config_path}")


@workspace_app.command("use")
def workspace_use(name: str = typer.Argument(...)) -> None:
    if not workspace_config_path(name).exists():
        raise typer.BadParameter(f"Workspace config not found: {workspace_config_path(name)}")
    set_current_workspace(name)
    typer.echo(f"Active workspace: {name}")


@schema_app.command("apply")
def schema_apply(mirror: str | None = typer.Option(None, "--mirror")) -> None:
    ws = _load_workspace()
    store = SqliteStore(ws.store.sqlite_path)
    store.apply_schema(SCHEMA_PATH)
    typer.echo("Applied schema to local SQLite.")

    if mirror:
        if mirror != "airtable":
            raise typer.BadParameter("Only --mirror airtable is supported.")
        if ws.mirror is None:
            raise typer.BadParameter("Workspace mirror config is missing.")
        try:
            sync.validate_mirror(store, ws.mirror, MAPPING_PATH)
            typer.echo("Validated Airtable schema.")
        except (MirrorError, SyncError) as exc:
            _exit_with_error(str(exc))


@mirror_app.command("doctor")
def mirror_doctor(
    provider: str = typer.Argument(..., help="airtable"),
    include_modified_time: bool = typer.Option(
        True, "--modified-time/--no-modified-time", help="Check AirtableModifiedAt fields."
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Check Airtable mirror schema and configuration."""
    if provider != "airtable":
        raise typer.BadParameter("Only the airtable provider is supported.")
    ws = _load_workspace()
    try:
        result = mirror.doctor_airtable(ws, MAPPING_PATH, SCHEMA_PATH, include_modified_time)
    except MirrorAuthError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except MirrorServiceError as exc:
        _exit_with_error(str(exc))
    payload = {
        "exit_code": result.exit_code,
        "messages": result.messages,
        "diff": asdict(result.diff),
    }
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
    else:
        for message in result.messages:
            typer.echo(message)
    raise typer.Exit(code=result.exit_code)


@mirror_app.command("bootstrap")
def mirror_bootstrap(
    provider: str = typer.Argument(..., help="airtable"),
    apply: bool = typer.Option(
        False, "--apply/--dry-run", help="Apply changes to Airtable schema."
    ),
    write_workspace_ids: bool = typer.Option(
        False, "--write-workspace-ids", help="Write discovered table IDs to workspace.yaml."
    ),
    include_modified_time: bool = typer.Option(
        True, "--modified-time/--no-modified-time", help="Ensure AirtableModifiedAt fields exist."
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Create missing Airtable tables/fields for the mirror."""
    if provider != "airtable":
        raise typer.BadParameter("Only the airtable provider is supported.")
    ws = _load_workspace()
    try:
        result = mirror.bootstrap_airtable(
            ws, MAPPING_PATH, SCHEMA_PATH, apply=apply, include_modified_time=include_modified_time
        )
    except MirrorAuthError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except MirrorServiceError as exc:
        _exit_with_error(str(exc))

    actions = list(result.actions)
    if write_workspace_ids:
        if not apply:
            actions.append(
                "SKIP: workspace.yaml not updated (use --apply with --write-workspace-ids)."
            )
        elif result.discovered_table_ids:
            backup_path = update_workspace_table_ids(
                ws.path / "workspace.yaml", result.discovered_table_ids
            )
            actions.append(f"UPDATED workspace.yaml (backup: {backup_path.name})")

    payload = {
        "actions": actions,
        "discovered_table_ids": result.discovered_table_ids,
        "missing_modified_time": result.missing_modified_time,
        "applied": apply,
    }
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
    else:
        if not apply:
            typer.echo("DRY RUN: no Airtable changes were made.")
        for action in actions or ["No changes required."]:
            typer.echo(action)
        if result.missing_modified_time:
            typer.echo(
                "Missing AirtableModifiedAt fields: "
                + ", ".join(sorted(result.missing_modified_time))
            )
    if apply:
        typer.echo("Bootstrap complete.")

@lead_app.command("add")
def lead_add(
    pipeline: str = typer.Argument(..., help="sponsor or attendee"),
    org: str | None = typer.Option(None, "--org"),
    domain: str | None = typer.Option(None, "--domain"),
    contact: str | None = typer.Option(None, "--contact"),
    stage: str | None = typer.Option(None, "--stage"),
    value: float | None = typer.Option(None, "--value"),
    tier: str | None = typer.Option(None, "--tier"),
    campaign: str | None = typer.Option(None, "--campaign"),
    person: str | None = typer.Option(None, "--person"),
    status: str | None = typer.Option(None, "--status"),
    segment: str | None = typer.Option(None, "--segment"),
    next_action: str | None = typer.Option(None, "--next"),
    due: str | None = typer.Option(None, "--due"),
    notes: str | None = typer.Option(None, "--notes"),
) -> None:
    ws = _load_workspace()
    store = SqliteStore(ws.store.sqlite_path)
    try:
        due_date = rules.parse_date(due, "due")
    except ValidationError as exc:
        _exit_with_error(str(exc))

    if pipeline == "sponsor":
        if not org:
            raise typer.BadParameter("--org is required for sponsor pipeline.")
        if not stage:
            raise typer.BadParameter("--stage is required for sponsor pipeline.")
        try:
            opp_id = leads.add_sponsor_lead(
                store,
                org_name=org,
                domain=domain,
                contact=contact,
                stage=stage,
                value=value,
                tier=tier,
                next_action=next_action,
                due=due_date,
                notes=notes,
            )
        except ValidationError as exc:
            _exit_with_error(str(exc))
        typer.echo(f"Created sponsor opp: {opp_id}")
        return

    if pipeline == "attendee":
        if not campaign:
            raise typer.BadParameter("--campaign is required for attendee pipeline.")
        if not person:
            raise typer.BadParameter("--person is required for attendee pipeline.")
        if not status:
            raise typer.BadParameter("--status is required for attendee pipeline.")
        try:
            member_id = leads.add_attendee_lead(
                store,
                campaign_name=campaign,
                person=person,
                status=status,
                segment=segment,
                next_action=next_action,
                due=due_date,
                notes=notes,
            )
        except ValidationError as exc:
            _exit_with_error(str(exc))
        typer.echo(f"Created campaign member: {member_id}")
        return

    raise typer.BadParameter("pipeline must be 'sponsor' or 'attendee'")


@lead_app.command("list")
def lead_list(
    pipeline: str = typer.Option(..., "--pipeline"),
    stage: str | None = typer.Option(None, "--stage"),
    status: str | None = typer.Option(None, "--status"),
) -> None:
    ws = _load_workspace()
    store = SqliteStore(ws.store.sqlite_path)

    if pipeline == "sponsor":
        if stage:
            try:
                rules.validate_enum(stage, [s.value for s in SponsorStage], "stage")
            except ValidationError as exc:
                _exit_with_error(str(exc))
        rows = leads.list_sponsor_leads(store, stage)
        for row in rows:
            typer.echo(
                f"{row['opp_id']} | {row['org_name']} | {row['stage']} | {row['next_action']} | {row['next_action_due']}"
            )
        return

    if pipeline == "attendee":
        if status:
            try:
                rules.validate_enum(status, [s.value for s in CampaignMemberStatus], "status")
            except ValidationError as exc:
                _exit_with_error(str(exc))
        rows = leads.list_attendee_leads(store, status)
        for row in rows:
            typer.echo(
                f"{row['member_id']} | {row['campaign_name']} | {row['full_name']} | {row['status']} | {row['next_action']} | {row['next_action_due']}"
            )
        return

    raise typer.BadParameter("--pipeline must be 'sponsor' or 'attendee'")


@lead_app.command("next")
def lead_next(limit: int = typer.Option(10, "--limit")) -> None:
    ws = _load_workspace()
    store = SqliteStore(ws.store.sqlite_path)
    items = leads.next_actions(store, limit=limit)
    if not items:
        typer.echo("No upcoming actions.")
        return
    for item in items:
        typer.echo(
            f"{item.pipeline} | {item.record_id} | {item.org_or_person} | {item.next_action} | {item.next_action_due}"
        )


@lead_app.command("touch")
def lead_touch(
    record_id: str = typer.Argument(...),
    channel: str = typer.Option(..., "--channel"),
    direction: str = typer.Option(..., "--direction"),
    subject: str | None = typer.Option(None, "--subject"),
    note: str | None = typer.Option(None, "--note"),
    next_action: str | None = typer.Option(None, "--next"),
    due: str | None = typer.Option(None, "--due"),
) -> None:
    ws = _load_workspace()
    store = SqliteStore(ws.store.sqlite_path)
    try:
        due_date = rules.parse_date(due, "due")
        touch_id = touch.log_touch(
            store,
            record_id=record_id,
            channel=channel,
            direction=direction,
            subject=subject,
            note=note,
            next_action=next_action,
            due=due_date,
        )
    except (TouchError, ValidationError) as exc:
        _exit_with_error(str(exc))
    typer.echo(f"Logged touch: {touch_id}")


@sync_app.command("push")
def sync_push(
    validate: bool = typer.Option(
        True, "--validate/--no-validate", help="Validate Airtable schema before push."
    ),
    events: bool = typer.Option(
        True, "--events/--no-events", help="Write sanitized events to the workspace log."
    ),
) -> None:
    """Mirror local records to Airtable (no manual Airtable data entry required)."""
    ws = _load_workspace()
    store = SqliteStore(ws.store.sqlite_path)
    if ws.mirror is None:
        raise typer.BadParameter("Workspace mirror config is missing.")
    try:
        logger = _event_logger(ws, enabled=events)
        sync.push(store, ws.mirror, MAPPING_PATH, validate=validate, logger=logger)
        pull_service.record_push(ws.path)
        typer.echo("Sync push complete.")
    except (MirrorError, SyncError) as exc:
        _exit_with_error(str(exc))


@sync_app.command("pull")
def sync_pull(
    apply: bool = typer.Option(
        False, "--apply/--dry-run", help="Apply Airtable changes to local SQLite."
    ),
    accept_remote: Annotated[
        list[str] | None,
        typer.Option("--accept-remote", help="Accept remote changes for a specific ExternalId."),
    ] = None,
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
    events: bool = typer.Option(
        True, "--events/--no-events", help="Write sanitized events to the workspace log."
    ),
) -> None:
    """Pull Airtable edits back into SQLite with conflict detection."""
    ws = _load_workspace()
    store = SqliteStore(ws.store.sqlite_path)
    if ws.mirror is None:
        raise typer.BadParameter("Workspace mirror config is missing.")
    try:
        logger = _event_logger(ws, enabled=events)
        summary, changes = pull_service.pull(
            store,
            ws.mirror,
            MAPPING_PATH,
            SCHEMA_PATH,
            ws.path,
            apply=apply,
            accept_remote=set(accept_remote or []),
            logger=logger,
        )
    except PullServiceError as exc:
        _exit_with_error(str(exc))
    if json_output:
        payload = {
            "summary": summary.__dict__,
            "changes": [change.__dict__ for change in changes],
            "applied": apply,
        }
        typer.echo(json.dumps(payload, indent=2))
    else:
        for line in pull_service.format_pull_report(summary, changes):
            typer.echo(line)
    if summary.conflicts:
        raise typer.Exit(code=1)


@export_app.command("excel")
def export_excel(out: str = typer.Option(..., "--out")) -> None:
    ws = _load_workspace()
    store = SqliteStore(ws.store.sqlite_path)
    exports.export_excel(store, Path(out))
    typer.echo(f"Exported Excel to {out}")


@open_app.command("airtable")
def open_airtable(
    external_id: str = typer.Argument(..., help="ExternalId / UUID"),
    open_browser: bool = typer.Option(False, "--open", help="Open the record in a browser."),
) -> None:
    ws = _load_workspace()
    if ws.mirror is None:
        raise typer.BadParameter("Workspace mirror config is missing.")
    if ws.mirror.provider != "airtable":
        raise typer.BadParameter("Only the airtable provider is supported.")
    store = SqliteStore(ws.store.sqlite_path)

    records = store.fetch_all(
        "SELECT table_name, record_id FROM mirror_state WHERE external_id = ?",
        (external_id,),
    )
    record_id = None
    table_name = None
    if len(records) > 1:
        _exit_with_error("Multiple mirror records found for this ExternalId.")
    if records:
        record_id = records[0]["record_id"]
        table_name = records[0]["table_name"]

    if not record_id:
        api_key = os.getenv("AIRTABLE_API_KEY")
        if not api_key:
            _exit_with_error(
                "AIRTABLE_API_KEY (Airtable PAT) is not set. "
                "Run scripts/setup-airtable-pat.sh or export it in your shell."
            )
        client = AirtableClient(api_key=api_key, base_id=ws.mirror.base_id or "")
        for candidate_table, table_id in ws.mirror.tables.items():
            if not table_id:
                continue
            found = client.find_record_by_external_id(table_id, external_id)
            if found:
                record_id = found.record_id
                table_name = candidate_table
                store.upsert_mirror_state(candidate_table, external_id, record_id, 0, None)
                break

    if not record_id or not table_name:
        _exit_with_error("Record not found in Airtable mirror.")

    table_id = ws.mirror.tables.get(table_name)
    if not table_id:
        _exit_with_error(f"Missing table id for {table_name} in workspace config.")
    url = f"https://airtable.com/{ws.mirror.base_id}/{table_id}/{record_id}"
    typer.echo(url)
    if open_browser:
        import webbrowser

        webbrowser.open(url)


@app.command("snapshot")
def snapshot() -> None:
    ws = _load_workspace()
    store = SqliteStore(ws.store.sqlite_path)
    snapshot_dir = Path("data") / "snapshots" / today_iso()
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    if ws.store.sqlite_path.exists():
        shutil.copy2(ws.store.sqlite_path, snapshot_dir / "local.sqlite")
    exports.export_csv_tables(store, snapshot_dir)
    typer.echo(f"Snapshot created at {snapshot_dir}")


def _load_workspace():
    try:
        return load_workspace()
    except WorkspaceError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc


def _exit_with_error(message: str) -> None:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=1)


def _event_logger(ws, enabled: bool) -> EventLogger:
    return EventLogger(path=ws.path / "events.ndjson", workspace=ws.name, enabled=enabled)


if __name__ == "__main__":
    app()
