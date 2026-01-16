# Demo: SynbioGRS27 End-to-End Walkthrough

This guide is a **didactic, end-to-end demo** of Leadops using a **synthetic** synbioGRS27 workspace. It is safe to run in a public repo because it uses fake organizations and contacts. Do **not** add real CRM data here.

## 0) Create the Airtable base (manual, one-time)

Leadops can **create tables and fields**, but it **cannot create a base** via the API. Create an empty base in Airtable UI named `synbioGRS27`, then copy the base ID (`app...`).

```bash
# If you need to set/overwrite the base ID in your workspace:
pixi run crm workspace add synbiogrs27 --base appXXXXXXXXXXXXXX --use --force
```

## 0.5) Add AirtableModifiedAt fields (manual, one-time)

Airtable does **not** allow creating `lastModifiedTime` fields via the API, so you must add them in the UI:

1) For each table, add a field named **AirtableModifiedAt**
2) Type: **Last modified time**
3) (Optional) Restrict which fields are tracked to exclude mirror metadata

Then run:

```bash
pixi run crm mirror bootstrap airtable --apply
```

## 1) Initialize leadops and select the workspace

```bash
pixi run crm init
pixi run crm workspace use synbiogrs27
```

This creates `workspaces/synbiogrs27/local.sqlite` as the canonical database.

## 2) Apply the schema locally

```bash
pixi run crm schema apply
```

## 3) Add sponsor + attendee leads (synthetic)

```bash
pixi run crm lead add sponsor \
  --org "HelixFoundry" \
  --domain helixfoundry.com \
  --contact "Ava Kim <ava@helixfoundry.com>" \
  --stage contacted \
  --value 20000 \
  --tier gold \
  --next "Send sponsor deck + tiers" \
  --due 2026-02-05

pixi run crm lead add attendee \
  --campaign "SynBio GRS 2027 Outreach" \
  --person "Dr. Priya Rao <priya.rao@uni.edu>" \
  --status invited \
  --segment academia \
  --next "Send invite + registration link" \
  --due 2026-02-10
```

## 4) Review pipeline state and next actions

```bash
pixi run crm lead list --pipeline sponsor --stage contacted
pixi run crm lead list --pipeline attendee --status invited
pixi run crm lead next
```

## 5) Log a touch and advance the next action

```bash
pixi run crm lead touch <opp_id_or_member_id> \
  --channel email \
  --direction outbound \
  --subject "SynBio GRS 2027 sponsorship deck" \
  --note "Sent deck and tier options; awaiting response" \
  --next "Follow up in one week" \
  --due 2026-02-12
```

## 6) Export and snapshot

```bash
pixi run crm export excel --out exports/synbiogrs27-leads.xlsx
pixi run crm snapshot
```

## 7) Push to the Airtable mirror

```bash
export AIRTABLE_API_KEY="patXXXXXXXXXXXXXX"
pixi run crm sync push
```

At this point Airtable is updated for sharing views, while the local SQLite DB remains canonical.

## 8) Pull Airtable edits back (safe pull)

1) Edit a field in Airtable (e.g., change a sponsor stage).
2) Run a dry-run pull to see diffs:

```bash
pixi run crm sync pull --dry-run
```

3) Apply non-conflicting changes:

```bash
pixi run crm sync pull --apply
```

4) If a record has local + remote edits, resolve explicitly:

```bash
pixi run crm sync pull --apply --accept-remote <ExternalId>
```

## Notes
- Use table IDs (not names) in `workspace.yaml` for stability.
- Do not commit `workspace.yaml` with real base/table IDs.
- Keep demo data synthetic only.
