# Leadops Agent Guidelines

- Local SQLite is canonical. Airtable is a mirror.
- Prefer `crm ...` commands for data changes; avoid direct Airtable mutations unless asked.
- Never commit secrets. Use environment variables or the repo-local `.env` via direnv (gitignored).
- Schema changes must start in `resources/schema/canonical.yaml`.
- Use `crm mirror bootstrap` or `crm mirror doctor` for Airtable schema checks/creation.
- Event logs must be sanitized (no emails or notes); no PII in git.
- Run tests and lint on meaningful changes.
- Airtable base creation is **manual**; API cannot create bases or `AirtableModifiedAt` fields.
  - Create the base in Airtable UI, then run `crm mirror bootstrap airtable --apply`.
  - Add `AirtableModifiedAt` manually per table (Last modified time), then rerun bootstrap to configure.
- When using MCP + Pixi:
  - Ensure `AIRTABLE_API_KEY` (PAT) is in the shell env (direnv recommended).
  - Use `crm sync push` for normal updates; use MCP only for inspection or emergency edits.
  - Keep demo data synthetic (no real emails/notes) and avoid committing workspace IDs or local DBs.
