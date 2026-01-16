# Leadops

Local-first lead operations with a SQLite source of truth and an Airtable mirror. The domain logic stays decoupled from vendors so you can evolve workflows without rewrites.

## What this gives you
- A small CLI (`crm`) to add leads, log touches, and pull your next actions
- A schema-as-code workflow (YAML -> SQLite) for repeatable setups
- A mirror adapter for Airtable so you can share dashboards without making Airtable the system of record

## Quickstart

### 1) Install dependencies (pixi)

```bash
pixi install
```

### 2) Set your Airtable PAT (optional for sync)

```bash
export AIRTABLE_API_KEY="your_pat_here"
```

### 3) Initialize and create a workspace

```bash
pixi run crm init
pixi run crm workspace add synbiogrs27 --base appXXXXXXXXXXXXXX
pixi run crm workspace use synbiogrs27
```

### 4) Apply schema locally

```bash
pixi run crm schema apply
```

### 5) Add a lead and view next actions

```bash
pixi run crm lead add sponsor \
  --org "Acme Bio" \
  --domain acmebio.com \
  --contact "Jane Doe <jane@acmebio.com>" \
  --stage contacted \
  --value 15000 \
  --tier gold \
  --next "Send sponsor deck" \
  --due 2026-01-20

pixi run crm lead next
```

### 6) Sync to Airtable (push-only)

```bash
pixi run crm sync push
```

## Docs
- `docs/architecture.md` — domain boundaries and adapter design
- `docs/schema.md` — schema-as-code format and conventions
- `docs/workspaces.md` — workspace config and selection
- `docs/cli.md` — CLI reference
- `docs/sync.md` — mirror behavior and Airtable notes
- `docs/internals/phases.md` — phase checklist and roadmap

## Notes
- `crm` is available via `pixi run crm ...` or `uv run crm ...`.
- Airtable is a mirror only; the local SQLite database is canonical.
- Never store secrets in files; use environment variables.
