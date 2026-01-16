# Sync Model

Leadops is local-first: SQLite is canonical and Airtable is a mirror.

## Push-only (v0.1)
- `crm sync push` validates Airtable schema, then upserts local records using `ExternalId`.
- Mirror metadata fields (`MirrorVersion`, `MirrorUpdatedAt`) are written on push.
  - Use `crm sync push --no-validate` to skip schema validation.

## Safety
- Airtable edits are not automatically pulled in v0.1.
- `crm schema apply --mirror airtable` validates that Airtable has the required fields.

## Environment
- `AIRTABLE_API_KEY` must be set when using sync/validation.
