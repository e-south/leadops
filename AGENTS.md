# Leadops Agent Guidelines

## Core posture
- Local SQLite is canonical. Airtable is a mirror.
- Prefer `crm ...` commands for data changes; avoid direct Airtable mutations unless asked.
- Domain logic must stay vendor-agnostic; Airtable-specific behavior lives in adapters only.

## Repo layout
- Source lives in `src/crm/`.
- Schema + mapping live in `resources/schema/`.
- Templates live in `resources/templates/`.
- Docs are under `docs/` with `docs/index.md` as the entry point.

## Workspaces and data hygiene
- Only `workspaces/demo/` is tracked; all other workspaces are gitignored.
- Never commit real workspace IDs, local SQLite DBs, snapshots, or event logs.
- Event logs must be sanitized (no emails, notes, or free-text PII).

## Airtable mirror rules
- Airtable base creation is **manual**; the API cannot create bases or `AirtableModifiedAt` fields.
  - Create the base in Airtable UI, then run `crm mirror bootstrap airtable --apply`.
  - Add `AirtableModifiedAt` manually per table (Last modified time), then rerun `crm mirror doctor airtable`.
- Use `crm mirror bootstrap` and `crm mirror doctor` for schema creation/validation.
- `crm sync push` is the normal flow; `crm sync pull --dry-run/--apply` is explicit and conflict-aware.

## Secrets and environment
- Never commit secrets. Use env vars or repo-local `.env` + direnv (gitignored).
- `AIRTABLE_API_KEY` must be a PAT and present in the shell env for `pixi run crm ...`.
- MCP env does **not** automatically flow into `pixi` commands; set it in the shell or via direnv.
- Use `scripts/setup-airtable-pat.sh` to set up a local `.env`/`.envrc` prompt.
- If detect-secrets updates `.secrets.baseline`, stage and commit it (line numbers drift).

## CI + formatting expectations
- CI required check is **CI / ci** (job name must stay aligned with branch protection).
- CI uses `uv sync --locked --dev` + `ruff` + `pytest` + `uv build`.
- For local validation: `uv sync --dev`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest -q`.
