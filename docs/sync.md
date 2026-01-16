# Sync Model

Leadops is local-first: SQLite is canonical and Airtable is a mirror.

## Push-only (v0.1)
- `crm sync push` validates Airtable schema, then upserts local records using `ExternalId`.
- Mirror metadata fields (`MirrorVersion`, `MirrorUpdatedAt`) are written on push.
  - Use `crm sync push --no-validate` to skip schema validation.

## Safe pull (v0.1)
- `crm sync pull --dry-run` prints diffs and conflicts without touching local data.
- `crm sync pull --apply` applies non-conflicting changes to SQLite.
- `crm sync pull --accept-remote <ExternalId>` resolves one conflict in favor of Airtable.
- Pull ignores Airtable rows without `ExternalId` by default.
- Incremental pull uses `AirtableModifiedAt` when available; otherwise it scans the full table.
- If `AirtableModifiedAt` is present, conflicts are only raised when *both* local and remote changed
  since the last mirror. Local-only changes are skipped.

## Safety
- Airtable edits are never auto-applied; you must run pull explicitly.
- `crm mirror doctor airtable` checks schema mismatches and modified-time configuration.
- `crm mirror bootstrap airtable` can create missing tables/fields when allowed.

## Environment
- `AIRTABLE_API_KEY` must be set to your Airtable PAT (use `scripts/setup-airtable-pat.sh` or export it).

## FAQ
- Do I need to manually populate Airtable records? **No.** Use `crm sync push` to mirror local data.
- Do I need Airtable schema ready? **Yes**, unless you run `crm mirror bootstrap airtable`.
- Can I pull Airtable edits and track them locally? **Yes**, with `crm sync pull`.
- Can I do near-real-time pull? **Not yet** (future: polling or webhooks).
