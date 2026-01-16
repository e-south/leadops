# Leadops

[![CI](https://github.com/e-south/leadops/actions/workflows/ci.yml/badge.svg)](https://github.com/e-south/leadops/actions/workflows/ci.yml)

Local-first lead operations with a SQLite source of truth and an optional Airtable mirror. Domain logic stays decoupled from vendors so workflows remain portable and easy to change.

## Highlights
- CLI-first workflows for sponsor and attendee pipelines
- Schema-as-code (YAML) driving SQLite structure
- Airtable as a shareable mirror, not the system of record
- Mirror tooling: bootstrap, doctor, and safe pull with conflict detection

## Sync posture
- A) Local-only: use SQLite only.
- B) Push-only mirror: `crm sync push` (Airtable for sharing views).
- C) Safe pull: `crm sync pull --dry-run/--apply` with conflict detection.

## Quickstart

### 1) Install dependencies (pixi)

```bash
pixi install
```

### 2) Initialize and create a workspace

```bash
pixi run crm init
pixi run crm workspace add demo --base appXXXXXXXXXXXXXX
pixi run crm workspace use demo
```

### 3) Apply schema locally

```bash
pixi run crm schema apply
```

### 4) Add a lead and view next actions

```bash
pixi run crm lead add sponsor \
  --org "Acme Bio" \
  --domain acmebio.com \
  --contact "Jane Doe <jane@acmebio.com>" \
  --stage contacted \
  --value 15000 \
  --tier gold \
  --next "Send sponsor deck" \
  --due 2026-02-05

pixi run crm lead next
```

### 5) (Optional) Bootstrap Airtable mirror

```bash
export AIRTABLE_API_KEY="your_pat_here"
pixi run crm mirror bootstrap airtable --dry-run
pixi run crm mirror bootstrap airtable --apply --write-workspace-ids
pixi run crm sync push
```

### 6) (Optional) Pull Airtable edits back

```bash
pixi run crm sync pull --dry-run
pixi run crm sync pull --apply
```

## Documentation
- [Architecture](docs/architecture.md)
- [Schema as Code](docs/schema.md)
- [Workspaces](docs/workspaces.md)
- [CLI Reference](docs/cli.md)
- [Sync Model](docs/sync.md)
- [Airtable UI Tips](docs/airtable-ui.md)

## Notes
- `crm` is available via `pixi run crm ...` or `uv run crm ...`.
- Airtable is a mirror only; the local SQLite database is canonical.
- Never store secrets in files; use environment variables.
- Workspace sync state lives in `workspaces/<name>/.sync_state.json` (gitignored).
- Sanitized events are stored in `workspaces/<name>/events.ndjson` (gitignored).
