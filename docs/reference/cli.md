# CLI Reference

All commands are exposed via `crm` (e.g., `pixi run crm ...`).

## Workspace
- `crm init`
- `crm workspace add <name> --base app...`
- `crm workspace use <name>`
  - Use `--force` to overwrite an existing workspace config.

## Schema
- `crm schema apply`
- `crm schema apply --mirror airtable`

## Mirror
- `crm mirror doctor airtable`
- `crm mirror bootstrap airtable --dry-run`
- `crm mirror bootstrap airtable --apply --write-workspace-ids` (writes table IDs in apply mode)

## Leads
- `crm lead add sponsor ...`
- `crm lead add attendee ...`
- `crm lead list --pipeline sponsor --stage contacted`
- `crm lead list --pipeline attendee --status invited`
- `crm lead next`
- `crm lead touch <id> --channel email --direction outbound --next "Follow up" --due 2026-01-27`
  - Omitting `--next`/`--due` preserves existing values.

## Sync
- `crm sync push` (validates Airtable schema by default; use `--no-validate` to skip)
- `crm sync pull --dry-run`
- `crm sync pull --apply`
- `crm sync pull --accept-remote <ExternalId>`

## Open
- `crm open airtable <ExternalId> [--open]`
