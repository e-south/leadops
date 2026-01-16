from __future__ import annotations

import shutil
from pathlib import Path

import typer

from crm import __version__
from crm.adapters.airtable.mirror import MirrorError
from crm.config import (
    WorkspaceError,
    ensure_workspaces_dir,
    load_workspace,
    set_current_workspace,
    workspace_config_path,
    write_workspace_config,
)
from crm.domain import rules
from crm.domain.rules import ValidationError
from crm.services import exports, leads, sync, touch
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

app.add_typer(workspace_app, name="workspace")
app.add_typer(lead_app, name="lead")
app.add_typer(schema_app, name="schema")
app.add_typer(sync_app, name="sync")
app.add_typer(export_app, name="export")

SCHEMA_PATH = Path("schema/canonical.yaml")
MAPPING_PATH = Path("schema/airtable.mapping.yaml")


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
        rows = leads.list_sponsor_leads(store, stage)
        for row in rows:
            typer.echo(
                f"{row['opp_id']} | {row['org_name']} | {row['stage']} | {row['next_action']} | {row['next_action_due']}"
            )
        return

    if pipeline == "attendee":
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
    )
) -> None:
    ws = _load_workspace()
    store = SqliteStore(ws.store.sqlite_path)
    if ws.mirror is None:
        raise typer.BadParameter("Workspace mirror config is missing.")
    try:
        sync.push(store, ws.mirror, MAPPING_PATH, validate=validate)
        typer.echo("Sync push complete.")
    except (MirrorError, SyncError) as exc:
        _exit_with_error(str(exc))


@export_app.command("excel")
def export_excel(out: str = typer.Option(..., "--out")) -> None:
    ws = _load_workspace()
    store = SqliteStore(ws.store.sqlite_path)
    exports.export_excel(store, Path(out))
    typer.echo(f"Exported Excel to {out}")


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


if __name__ == "__main__":
    app()
