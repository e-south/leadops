# Leadops Agent Guidelines

- Local SQLite is canonical. Airtable is a mirror.
- Prefer `crm ...` commands for data changes; avoid direct Airtable mutations unless asked.
- Never write secrets into files. Use environment variables.
- Schema changes must start in `schema/canonical.yaml`.
- Run tests and lint on meaningful changes.
