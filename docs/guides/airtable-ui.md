# Airtable UI Tips (Mirror Only)

Airtable is a UI surface for the local-first system. Keep workflows in the CLI and treat Airtable as a mirror.

## Recommended views
- **Kanban by Stage** for SponsorOpps and CampaignMembers (group by `Stage` / `Status`).
- **Calendar by Next Action Due** using `Next Action Due`.
- **Follow-ups due**: filter `Next Action Due` is within the next 7 days.
- **Stale**: filter `Last Touch At` is older than 14 days and `Stage` is not `closed_lost`.

## Principles
- No Airtable formulas that define business meaning.
- No automations that mutate core fields.
- Keep edits human and minimal; use `crm sync pull` to bring them into SQLite.
