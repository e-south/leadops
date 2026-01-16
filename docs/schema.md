# Schema as Code

The canonical schema lives in `schema/canonical.yaml`. It defines:
- Tables and fields
- Enums
- Required fields
- Foreign keys and indexes

The Airtable mirror mapping lives in `schema/airtable.mapping.yaml`. It maps domain fields to Airtable field names and includes mirror metadata fields (`ExternalId`, `MirrorVersion`, `MirrorUpdatedAt`). The mirror also expects an `AirtableModifiedAt` field (last modified time) for incremental pull.

## Conventions
- UUID primary keys are stored as TEXT in SQLite.
- Dates are ISO strings (YYYY-MM-DD); datetimes are ISO 8601.
- Tags are stored as comma-delimited text for now.
- Mirror metadata is stored locally in `mirror_state`, not in domain tables.

## Applying schema
- `crm schema apply` creates or updates local SQLite tables.
- `crm schema apply --mirror airtable` validates Airtable tables/fields against the mapping.
