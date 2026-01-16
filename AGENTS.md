# Leadops Agent Guidelines

- Local SQLite is canonical. Airtable is a mirror.
- Prefer `crm ...` commands for data changes; avoid direct Airtable mutations unless asked.
- Never write secrets into files. Use environment variables.
- Schema changes must start in `schema/canonical.yaml`.
- Use `crm mirror bootstrap` or `crm mirror doctor` for Airtable schema checks/creation.
- Event logs must be sanitized (no emails or notes); no PII in git.
- Run tests and lint on meaningful changes.
