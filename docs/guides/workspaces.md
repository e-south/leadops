# Workspaces

Each workspace is isolated under `workspaces/<name>/` and contains configuration for the local store and mirror.

## Example

```yaml
workspace: synbiogrs27
store:
  sqlite_path: ./local.sqlite

mirror:
  provider: airtable
  base_id: appXXXXXXXXXXXXXX
  tables:
    organizations: tblXXXXXXXXXXXXXX
    people: tblYYYYYYYYYYYYYY
    sponsor_opps: tblZZZZZZZZZZZZZZ
    campaigns: tblAAAAAAAAAAAAAA
    campaign_members: tblBBBBBBBBBBBB
    touches: tblCCCCCCCCCCCCCC
    tasks: tblDDDDDDDDDDDDDD
```

## Commands
- `crm workspace add <name> --base app...` creates a workspace folder and config.
- `crm workspace use <name>` marks it as active.
- `crm mirror bootstrap airtable --apply --write-workspace-ids` can populate table IDs.

## Notes
- The local DB is per-workspace.
- `store.sqlite_path` is resolved relative to the workspace directory.
- Airtable is optional; if unset, sync commands will fail fast.
- `workspaces/<name>/.sync_state.json` stores local sync state (gitignored).
- `workspaces/<name>/events.ndjson` stores sanitized events (gitignored).
