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

## Leads
- `crm lead add sponsor ...`
- `crm lead add attendee ...`
- `crm lead list --pipeline sponsor --stage contacted`
- `crm lead list --pipeline attendee --status invited`
- `crm lead next`
- `crm lead touch <id> --channel email --direction outbound --next "Follow up" --due 2026-01-27`

## Sync
- `crm sync push` (validates Airtable schema by default; use `--no-validate` to skip)
