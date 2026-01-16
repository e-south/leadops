# Leadops Agent Guidelines

- Local SQLite is canonical. Airtable is a mirror.
- Prefer `crm ...` commands for data changes; avoid direct Airtable mutations unless asked.
- Never commit secrets. Use environment variables or the repo-local `.env` via direnv (gitignored).
- Schema changes must start in `schema/canonical.yaml`.
- Use `crm mirror bootstrap` or `crm mirror doctor` for Airtable schema checks/creation.
- Event logs must be sanitized (no emails or notes); no PII in git.
- Run tests and lint on meaningful changes.
