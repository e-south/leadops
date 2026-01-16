Below is a concrete dev spec you can implement with **Airtable as the shareable mirror**, while keeping **your codebase + local DB as the source of truth**. It’s designed so you can drive everything from **Codex in your terminal**, avoid GUI-tinkering, and keep an easy escape hatch (swap Airtable out later without rewriting domain logic).

I’ll anchor this on what you already have working:

* `airtable-mcp-server` via `npx -y airtable-mcp-server` using `AIRTABLE_API_KEY` (a PAT) ([GitHub][1])
* Codex CLI supports STDIO MCP servers with env vars; “Auth: Unsupported” is normal for this style (auth is via env token, not OAuth) ([OpenAI Developers][2])
* Airtable API keys are deprecated; use PATs (and scope them tightly) ([Airtable Support][3])
* Airtable recommends using **table IDs** so renames don’t break requests ([Airtable][4])

---

## 0) Target outcomes

### What “done” looks like (v0.1)

* You can run terminal commands like:

  * `crm lead add sponsor …`
  * `crm lead next`
  * `crm lead touch …`
  * `crm sync push` (mirror local → Airtable)
* Airtable base exists mainly so you can share views / dashboards, but you do **not** depend on Airtable UI logic.
* You can spin up a new workspace later (new Airtable base + new local DB) with near-zero friction.

### Non-goals (initially)

* Perfect email threading / mailbox sync.
* Multi-user conflict-free editing in Airtable.
* Heavy workflow automation. (We’ll keep it minimal and composable.)

---

## 1) Architecture: Ports & Adapters with a “thin waist”

**Design rule:** your **domain model and workflows never mention Airtable**.

### Layers

1. **Domain (pure)**

   * Entities (Org, Person, SponsorOpp, CampaignMember, Touch, Task)
   * Stage transitions and invariants
   * “Next action” logic, scoring, segmentation logic (all in code)

2. **Local Store (source of truth)**

   * SQLite DB (transactional, fast, easy backups)
   * Migrations driven by schema spec (YAML)

3. **Mirror Adapter (Airtable)**

   * Maps domain records ⇄ Airtable tables/fields
   * Airtable-specific metadata stays here (record IDs, field IDs, last-mod markers)

4. **CLI (your interface)**

   * A small set of verbs that match how you operate day-to-day

5. **(Optional later) MCP server for your domain**

   * Codex calls `lead_add`, `lead_next`, etc. as tools
   * Internally uses adapter(s) (Airtable now, Baserow/Grist later)

For now, we can skip (5) and just have Codex run the CLI commands.

---

## 2) Repo: “workbench” layout for many future projects

You want the repo not tied to “synbio GRS”, but able to host multiple outreach projects.

### Repo name ideas (short, pragmatic)

* `leadbench`
* `outreachbench`
* `crm-workbench`
* `leadops`

### Directory structure (concrete)

```text
leadops/
  AGENTS.md
  README.md

  schema/
    canonical.yaml                 # your domain schema + enums + pipelines
    airtable.mapping.yaml          # mapping rules (domain -> Airtable field types/names)

  crm/
    __init__.py
    cli.py                         # Typer/Click entrypoint (crm ...)
    domain/
      models.py
      stages.py
      rules.py                     # invariants + validation
    store/
      sqlite.py
      migrations.py
    adapters/
      airtable/
        client.py                  # REST client (or pyairtable)
        mirror.py                  # push/pull logic
        ids.py                     # resolve base/table/field IDs
    services/
      leads.py                     # lead add/list/next
      touch.py                     # logging interactions
      exports.py                   # excel/csv exports

  workspaces/
    synbiogrs27/
      workspace.yaml               # base_id, table_ids, mapping overrides
      .env.example
    another-project/
      workspace.yaml

  templates/
    email/
      sponsor_intro.md
      sponsor_followup.md
      attendee_invite.md
    snippets/
      talking_points_biopharma.md

  data/
    .gitkeep                        # optional
  exports/
    .gitkeep

  scripts/
    snapshot.sh                     # nightly snapshot helpers

  .gitignore
  pyproject.toml
```

**Key point:** `workspaces/<name>/` isolates per-project config + snapshots without forking the codebase.

---

## 3) Secrets & configuration (no vendor lock-in, no leaking tokens)

### Airtable auth

* Airtable PATs replace API keys; keys no longer work ([Airtable Support][3])
* `airtable-mcp-server` expects `AIRTABLE_API_KEY` set to a PAT and lists the scopes you should grant (read scopes required; write scopes optional) ([GitHub][1])

### Don’t bake secrets into `~/.codex/config.toml`

Codex supports STDIO MCP servers with `env` vars, but for hygiene I’d shift to:

* Put `AIRTABLE_API_KEY` in your shell environment via `direnv` or your secret manager
* Configure Codex MCP server using `env_vars` forwarding (so config contains no token)

Codex MCP supports env and env forwarding for STDIO servers ([OpenAI Developers][2]).

### Workspace config

`workspaces/synbiogrs27/workspace.yaml`:

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

### SynbioGRS27 workspace scaffold (checked in)

The repo includes a ready-to-edit scaffold:

- `workspaces/synbiogrs27/workspace.yaml`
- `workspaces/synbiogrs27/.env.example`

Update the Airtable IDs in `workspace.yaml` (or run `crm mirror bootstrap airtable --apply --write-workspace-ids`), then load your PAT via environment variables (never commit it).
`store.sqlite_path` is resolved relative to the workspace directory.

---

For a step-by-step walkthrough, see the demo guide: `docs/guides/demo.md`.

---

## 4) Data model: exactly what I’d use

This gives you two pipelines (Sponsors + Attendees) without making the schema conference-specific.

### Core tables

#### 1) `Organizations`

* `org_id` (UUID, canonical key)
* `name` (text)
* `domain` (text)
* `org_type` (enum: `academia`, `biotech`, `biopharma`, `vc`, `nonprofit`, `other`)
* `tags` (multi)
* `notes` (text)
* `created_at`, `updated_at` (datetime)

#### 2) `People`

* `person_id` (UUID)
* `org_id` (FK → Organizations, nullable)
* `full_name`
* `email`
* `title`
* `linkedin_url` (optional)
* `tags` (multi)
* `notes`
* `created_at`, `updated_at`

---

## Sponsor pipeline tables

#### 3) `SponsorOpps`

* `opp_id` (UUID)
* `org_id` (FK required)
* `primary_person_id` (FK nullable)
* `stage` (enum)

  * `targeted`
  * `contact_found`
  * `contacted`
  * `engaged`
  * `call_scheduled`
  * `proposal_sent`
  * `negotiation`
  * `committed`
  * `invoicing`
  * `paid`
  * `closed_lost`
* `expected_value_usd` (number)
* `tier` (enum: `platinum`, `gold`, `silver`, `other`)
* `probability` (0–1)
* **Next-action fields (the heart of the workflow)**

  * `next_action` (text)
  * `next_action_due` (date)
  * `last_touch_at` (datetime)
  * `last_touch_channel` (enum: `email`, `call`, `meeting`, `linkedin`, `other`)
* `notes`
* `created_at`, `updated_at`

---

## Attendee pipeline tables

#### 4) `Campaigns`

* `campaign_id` (UUID)
* `name` (e.g., “Synthetic Biology Outreach 2026”)
* `kind` (enum: `attendee_outreach` | `speaker_outreach` | `other`)
* `start_date`, `end_date`
* `notes`

#### 5) `CampaignMembers`

* `member_id` (UUID)
* `campaign_id` (FK)
* `person_id` (FK)
* `status` (enum)

  * `identified`
  * `invited`
  * `interested`
  * `registered`
  * `attending`
  * `declined`
  * `unresponsive`
* `segment` (enum: `academia`, `industry`, `student`, `pi`, `founder`, etc.)
* Next-action fields:

  * `next_action`
  * `next_action_due`
  * `last_touch_at`
  * `last_touch_channel`
* `notes`
* `created_at`, `updated_at`

---

## Shared “activity log” tables

#### 6) `Touches` (interaction log)

Minimal but powerful.

* `touch_id` (UUID)
* `occurred_at` (datetime)
* `channel` (enum)
* `direction` (`outbound` | `inbound`)
* `subject` (text)
* `body_snippet` (text)
* Links (nullable):

  * `org_id`
  * `person_id`
  * `opp_id`
  * `member_id`
* `external_ref` (optional; e.g., message-id)
* `notes`

#### 7) `Tasks` (optional in v0.1, but I’d include it)

You can derive tasks from “next_action”, but a tasks table lets you add standalone to-dos.

* `task_id` (UUID)
* `due_at` (datetime)
* `status` (`open` | `done` | `canceled`)
* `title`
* `details`
* Links (nullable): `opp_id`, `member_id`, `person_id`, `org_id`

---

## 5) Schema-as-code: the YAML spec

You store the canonical truth in `schema/canonical.yaml`, then generate:

* local SQLite migrations
* Airtable base schema creation/upgrades

**Important:** the Airtable mirror schema can include Airtable-only metadata fields (adapter-owned) without contaminating the domain.

### Airtable mirror metadata fields (adapter-owned)

For each Airtable table, add:

* `ExternalId` (UUID string) — the domain primary key
* `MirrorVersion` (int) — optimistic concurrency counter
* `MirrorUpdatedAt` (datetime) — when your code last wrote it

This makes the mirror robust and helps detect “someone edited Airtable”.

---

## 6) Exact CLI verbs (the operational interface)

These are the commands I’d standardize on. They’re intentionally “small surface area” and map to what you do daily.

### Workspace / setup

* `crm init`

  * Creates repo-local folders for workspaces, exports, and snapshots.
* `crm workspace add <name> --base appXXXX`
* `crm workspace use <name>`
  * Add `--force` to overwrite an existing workspace config.
* `crm schema apply`

  * Applies schema to local DB and (optionally) Airtable mirror.

### Lead-centric daily ops (high leverage)

* `crm lead add sponsor --org "Acme Bio" --domain acmebio.com --contact "Jane Doe <jane@acmebio.com>" --stage contacted --value 15000 --tier gold --next "Send sponsor deck" --due 2026-01-20`

* `crm lead add attendee --campaign "SynBio Outreach 2026" --person "Prof X <x@uni.edu>" --status invited --segment academia --next "Send invite w/ reg link" --due 2026-01-18`

* `crm lead list --pipeline sponsor --stage contacted`

* `crm lead list --pipeline attendee --status invited`

* `crm lead next`

  * Prints “what should I do next” across both pipelines:

    * overdue next actions first
    * then due today / this week

> Note: `--due-within` filtering is planned; use `crm lead next` for now.

* `crm lead touch <id> --channel email --direction outbound --subject "Sponsor prospectus" --note "Sent deck + tiers" --next "Follow up" --due 2026-01-27`

### Sync (local-first, Airtable mirror)

* `crm sync push`

  * Validates Airtable schema, then upserts local → Airtable using `ExternalId` as the key
  * Updates `MirrorVersion` and `MirrorUpdatedAt`
  * Use `--no-validate` to skip schema validation
* `crm sync pull --dry-run`

  * Detects Airtable edits and prints diffs (no silent overwrites)
* `crm sync pull --accept-remote`

  * Explicitly accepts remote edits (rare; assertive programming)

### Export / snapshots (Excel-friendly)

* `crm export excel --out exports/synbiogrs27-leads.xlsx`
* `crm snapshot`

  * Dumps SQLite + CSV extracts to `data/snapshots/YYYY-MM-DD/`

---

## 7) How Codex fits (agent proposes changes; you approve)

### Use AGENTS.md to keep Codex aligned

Codex reads `AGENTS.md` guidance automatically (global + repo + nested overrides) ([OpenAI Developers][6]).

Put an `AGENTS.md` at repo root that says (in effect):

* “Local DB is canonical. Airtable is mirror.”
* “Prefer `crm …` commands; do not directly mutate Airtable via MCP unless asked.”
* “Never write secrets into files.”
* “When making schema changes, edit `schema/canonical.yaml` then run `crm schema apply`.”
* “Always run tests.”

### Keep the Airtable MCP server as your “inspection & emergency wrench”

You already have Airtable MCP tools installed (list bases, list tables, create record, etc.).

The `airtable-mcp-server` README explicitly documents the `npx -y airtable-mcp-server` setup and the needed PAT scopes ([GitHub][1]).
Codex supports STDIO MCP servers configured via CLI or `~/.codex/config.toml` ([OpenAI Developers][2]).

**Recommended operating policy:**

* Day-to-day: Codex runs `crm lead …` and `crm sync push`
* When debugging: Codex uses MCP `describe_table`, `list_records`, etc.

This avoids vendor lock-in because your workflows do not depend on Airtable MCP tool semantics—only your adapter does.

---

## 8) Airtable mirror: how we keep it clean and non-locking

### “No Airtable business logic”

Avoid:

* complex Airtable formulas that define meaning
* Airtable automations as your system behavior
* Interface-only workflows

Instead:

* compute scores/segments/due logic in Python
* write results as plain fields

### Use stable IDs everywhere

* Canonical UUID in `ExternalId`
* Airtable record ID stored locally only (as mirror metadata)

Airtable provides ways to find IDs (base/table/field/record IDs from URLs and tools) ([Airtable Support][5]), and they recommend table IDs for maintainability ([Airtable][4]).

### Be honest about Airtable API realities

* You’ll need pagination handling (Airtable uses `offset` style paging) ([Airtable Support][7]).
* Airtable can evolve APIs; you should keep sync adapter isolated and test-covered ([Airtable Support][8]).

---

## 9) Implementation plan (minimal complexity, staged)

### Phase 1 (fast win): local DB + CLI + mirror bootstrap + push

Deliver:

* `crm init`, `crm lead add/list/next/touch`, `crm sync push`
* `crm mirror doctor airtable` for schema diagnostics
* `crm mirror bootstrap airtable` to create missing tables/fields
* snapshots + Excel export

### Phase 2: safe pull + conflict detection

Deliver:

* mirror metadata fields (`ExternalId`, `MirrorVersion`, `MirrorUpdatedAt`)
* `crm sync pull --dry-run` that shows diffs
* `crm sync pull --apply` for non-conflicting changes
* `--accept-remote` for explicit merges

### Phase 3: decouple from Airtable (adapter interface)

Deliver:

* `Adapter` protocol with implementations:

  * `AirtableAdapter`
  * (later) `BaserowAdapter` or `GristAdapter`
* This is the true “no lock-in” point.

### Phase 4: optional domain MCP server

Deliver:

* `leadbench-mcp` server exposing tools:

  * `lead_add`, `lead_list`, `lead_next`, `lead_touch`, `sync_push`
* Codex calls your tools instead of the Airtable MCP tools.
* Airtable becomes one plugin behind the scenes.

---

## 10) Quick note on your current MCP status (“Auth: Unsupported”)

For STDIO servers like `npx -y airtable-mcp-server`, Codex treats auth as “env-based”; OAuth login flows are more relevant to HTTP MCP servers. Codex documents STDIO servers as supporting environment variables directly ([OpenAI Developers][2]). So “Auth: Unsupported” is not, by itself, a red flag.

---

## If you want, I can generate the initial files (spec-first)

If you want the *cleanest jumpstart*, tell Codex (or tell me here) “create the repo skeleton + schema YAML + Typer CLI with those verbs + SQLite store + Airtable push-only adapter”.

To keep it minimal, the very first “walking demo” can be:

1. `crm init`
2. `crm schema apply --mirror airtable`
3. `crm lead add sponsor …`
4. `crm sync push`
5. See it appear in Airtable

And from there, you iterate—without ever becoming dependent on Airtable UI logic.

If you share **nothing sensitive**, just the Airtable table names you want (or even “use defaults”), I can lock the initial `schema/canonical.yaml` to the exact tables above and write the “verbs contract” so your workflows stay stable as you evolve.

[1]: https://github.com/domdomegg/airtable-mcp-server "https://github.com/domdomegg/airtable-mcp-server"
[2]: https://developers.openai.com/codex/mcp/ "https://developers.openai.com/codex/mcp/"
[3]: https://support.airtable.com/docs/creating-personal-access-tokens "https://support.airtable.com/docs/creating-personal-access-tokens"
[4]: https://www.airtable.com/developers/web/api/list-records "https://www.airtable.com/developers/web/api/list-records"
[5]: https://support.airtable.com/docs/finding-airtable-ids "https://support.airtable.com/docs/finding-airtable-ids"
[6]: https://developers.openai.com/codex/guides/agents-md/ "https://developers.openai.com/codex/guides/agents-md/"
[7]: https://support.airtable.com/docs/getting-started-with-airtables-web-api "https://support.airtable.com/docs/getting-started-with-airtables-web-api"
[8]: https://support.airtable.com/docs/airtable-api-deprecation-guidelines "https://support.airtable.com/docs/airtable-api-deprecation-guidelines"
