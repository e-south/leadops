# Architecture

Leadops follows a Ports & Adapters approach with a “thin waist”:

- **Domain (pure)**: entities, invariants, stage rules, and next-action logic.
- **Store (SQLite)**: local source of truth, migrations driven by schema YAML.
- **Adapters**: Airtable mirror adapter; other mirrors can be added without touching domain.
- **CLI**: a small set of verbs that map to daily workflows.

## Design principles
- **Decoupled**: domain logic never references Airtable.
- **Assertive**: validate inputs early; fail fast on invalid state.
- **Robust**: sync is explicit and observable (push-only in v0.1).
- **Extensible**: adapters and services are narrow interfaces to swap later.

## Data flow
1. CLI calls services.
2. Services operate on domain objects and the local store.
3. The mirror adapter pushes local records into Airtable, using `ExternalId` for idempotent upserts.
