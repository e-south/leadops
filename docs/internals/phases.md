# Phases Checklist

This is the internal delivery tracker for leadops. Each phase lists goals, concrete deliverables, and the validation steps used for sign-off.

## Phase 1 — Local DB + CLI + Push-only mirror (v0.1)

**Goals**
- Local-first workflows are complete and usable without Airtable.
- Airtable acts only as a mirror for sharing and dashboards.
- SynbioGRS27 can be run end-to-end from the CLI.

**Deliverables**
- [ ] `resources/schema/canonical.yaml` + `resources/schema/airtable.mapping.yaml` (versioned schema-as-code)
- [ ] SQLite migrations and `crm schema apply`
- [ ] Airtable schema validation via `crm schema apply --mirror airtable`
- [ ] Workspace scaffolding (`workspaces/synbiogrs27/workspace.yaml` + `.env.example`)
- [ ] CLI commands: `init`, `workspace add/use`, `schema apply`, `lead add/list/next/touch`, `export excel`, `snapshot`, `sync push`
- [ ] Push-only Airtable adapter with `ExternalId` upsert and mirror metadata
- [ ] User docs: `README.md`, `docs/internals/spec.md`, `docs/reference/cli.md`, `docs/guides/sync.md`

**Validation (synbioGRS27 demo)**
- [ ] `pixi run crm init` creates `data/` and `exports/`
- [ ] `pixi run crm workspace use synbiogrs27` selects workspace
- [ ] `pixi run crm schema apply` creates `workspaces/synbiogrs27/local.sqlite`
- [ ] `pixi run crm lead add sponsor ...` writes a sponsor opp
- [ ] `pixi run crm lead add attendee ...` writes a campaign member
- [ ] `pixi run crm lead list --pipeline sponsor` and `--pipeline attendee` return rows
- [ ] `pixi run crm lead next` shows due actions
- [ ] `pixi run crm lead touch <id> ...` logs a touch and updates next action
- [ ] `pixi run crm export excel --out exports/synbiogrs27-leads.xlsx` creates workbook
- [ ] `pixi run crm snapshot` creates `data/snapshots/YYYY-MM-DD/`
- [ ] `pixi run crm sync push` mirrors records to Airtable (with PAT set)

**Risks / edge cases to verify**
- [ ] Missing or invalid Airtable table IDs produce fast, clear errors
- [ ] Duplicate orgs/people are deduped by domain/email where available
- [ ] Invalid enums fail early with actionable errors

---

## Phase 2 — Safe pull + conflict detection

**Goals**
- Detect remote edits without silent overwrites.
- Make merges explicit and auditable.

**Deliverables**
- [ ] Mirror metadata fields verified across tables
- [ ] `crm sync pull --dry-run` shows diffs only
- [ ] `crm sync pull --accept-remote` applies explicit merges
- [ ] Conflict policy documented in `docs/guides/sync.md`

**Validation**
- [ ] Edit a record in Airtable and confirm `--dry-run` reports the diff
- [ ] Accept remote changes and verify local DB updated

---

## Phase 3 — Adapter interface (decouple from Airtable)

**Goals**
- Domain and services never depend on Airtable-specific semantics.
- Adapter contract allows future mirrors (Baserow/Grist) without rewrites.

**Deliverables**
- [ ] Adapter protocol/interface for list/upsert schema validation
- [ ] Airtable adapter implements the interface
- [ ] Placeholder adapter stub for a future mirror
- [ ] Adapter contract tests

**Validation**
- [ ] Services call only the adapter interface, not Airtable code directly

---

## Phase 4 — Domain MCP server (optional)

**Goals**
- Make leadops callable as MCP tools for Codex agents.

**Deliverables**
- [ ] MCP server exposing `lead_add`, `lead_list`, `lead_next`, `lead_touch`, `sync_push`
- [ ] Tools wired to the same service layer used by CLI
- [ ] Security notes on environment-based auth

**Validation**
- [ ] MCP calls perform the same operations as CLI commands

---

## Cross-cutting quality gates

- [ ] Ruff + pytest pass on each change set
- [ ] Docs updated when CLI flags change
- [ ] No secrets in repo; `.env` files ignored
