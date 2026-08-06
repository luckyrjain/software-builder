# migration-program-manager: design

**Date:** 2026-08-05
**Status:** Approved design
**Source:** Item #8 of [team-facing-agents-roadmap.md](../plans/2026-08-05-team-facing-agents-roadmap.md) —
P2, "Migration Program Manager — mysql-to-postgres-sql across many repos/squads, aggregating
`MIGRATION_STATUS.yaml` org-wide, escalating stalled services, tracking migration MRs per team. Needs a
new cross-repo status aggregation layer... the largest new-build item on this list." Implements
[org-rollup-schema.md](../../skill-framework/shared/org-rollup-schema.md) and its `pg_migration_gate`
adapter, designed in Phase 4 ([org-rollup-aggregation-layer-design.md](2026-08-05-org-rollup-aggregation-layer-design.md)).

## Problem

`MIGRATION_STATUS.yaml` is already fleet-shaped, but **one file per workspace**, hand-read. Nobody has one
view across every workspace mid-migration — which services are stuck, which squads are behind, which
gates haven't moved in weeks.

## What's already there vs. genuinely new — researched, not assumed

| Capability | Exists today? |
|---|---|
| Per-service migration gate state | **Yes** — `MIGRATION_STATUS.yaml`, unchanged, one file per workspace |
| Squad ownership join key | **Yes** — `SQUAD_MAP.md`, per Phase 4's design; **read as an existing file, never invoked fresh** — see § Approach |
| Reading `MIGRATION_STATUS.yaml`/`SQUAD_MAP.md` across *multiple* workspaces in one pass | **No** — every existing skill in this repo operates on one `workspace_root` at a time; this is the first "list of workspaces" input concept in the repo |
| A markdown-table parser for `SQUAD_MAP.md` | **No** — confirmed in Phase 4's research: no existing script in this repo parses `SQUAD_MAP.md` programmatically (`squad_mapping.py` only computes reconciliation, never reads/writes the table itself) |
| Per-gate staleness ("unchanged for N days") | **No** — `MIGRATION_STATUS.yaml` has **no per-gate timestamp**, only a whole-file `last_updated`. Confirmed against the real template: `scan_gate`/`shadow_compare`/`config_cutover` are bare enum values with no history. **Genuinely new**: this skill must track its own history across runs (see § Staleness tracking) |
| A skill with real Python scripts + pytest, not pure markdown | **Precedent exists** (squad-map's `squad_mapping.py`, domain-comprehension's `validate_manifest_yaml.py`) — same convention reused, not new to the repo, just new to *this* skill |

## Approach

`migration-program-manager` is a **pure read-only aggregator over already-produced artifacts** — it never
invokes mysql-to-postgres-sql or squad-map live, only reads their existing output files:

1. Takes a `program_manifest` — a list of `{workspace_root, squad_map_path}` (default `squad_map_path`:
   `<workspace_root>/SQUAD_MAP.md`) — the genuinely new "many workspaces at once" input.
2. For each workspace, reads `MIGRATION_STATUS.yaml` (skip with a Notes-section entry, not a crash, if
   absent — the skill's own `SETUP.md` documents running `mysql-to-postgres-sql` first) and, if present,
   `SQUAD_MAP.md` (read-only; if absent, every service in that workspace joins as `squad: UNKNOWN` with a
   note to run **squad-map** directly first — this skill never triggers that run itself, avoiding any risk
   of the kind `new-hire-guide`'s round-1 bug demonstrated for live wrapped-skill invocations).
3. Joins each `services[]` row into an `org_rollup_item` (`metric_type: pg_migration_gate`) per
   [org-rollup-schema.md § 4](../../skill-framework/shared/org-rollup-schema.md#4-adapters-per-source-skill)'s
   adapter — `path` matched against `SQUAD_MAP.md`'s `Repo` column first, falling back to `name`.
4. **Computes staleness against this skill's own persisted state** (see § Staleness tracking) — the one
   genuinely new stateful mechanism in this skill.
5. Ranks and groups by squad: blocked (any gate `fail`) first, then stalled (unchanged past the
   configured threshold) ranked by staleness descending, then in-progress, then done.
6. Writes **`MIGRATION_PROGRAM_REPORT.md`** (human-readable) and **`migration_program_rollup.json`** (the
   computed `org_rollup_item` list, machine-readable) — the latter exists specifically so
   **weekly-squad-digest** (item #11, since shipped) can reuse this skill's own computed rollup by
   reading this file, rather than re-implementing the join/aggregation itself.

## Staleness tracking — the one new stateful mechanism

`MIGRATION_STATUS.yaml` has no per-gate timestamp, so "unchanged for N days" cannot be read from the
source artifact alone — this skill must track it itself, across runs:

- Persists a state file (`migration_program_state.json`, path configurable via `program_manifest.state_path`,
  default alongside the report output) mapping `(workspace_root, service_name) → {gate_signature,
  first_observed_at}`, where `gate_signature` is the tuple `(scan_gate, shadow_compare, config_cutover)`.
- Each run: for every service, compare today's `gate_signature` against the stored one.
  - **Signature changed** (or service seen for the first time): reset `first_observed_at` to now — the
    clock restarts, this is forward progress (or new tracking), not staleness.
  - **Signature unchanged**: staleness = now − stored `first_observed_at`. Compare against
    `staleness_threshold_days` (required input, no default — see § Non-goals on why this isn't guessed).
- **This state file is this skill's own artifact, never mysql-to-postgres-sql's** — it lives wherever the
  report is written, not inside any migration workspace, and mysql-to-postgres-sql never reads or knows
  about it. No change to mysql-to-postgres-sql's own files or behavior.
- First run for a given `(workspace_root, service_name)` pair always shows staleness `0` (no prior
  observation to compare against) — this is expected, not a bug; staleness accuracy improves with each
  subsequent run.

## Non-goals (explicitly out of scope)

- **No default `staleness_threshold_days`.** A default staleness threshold is a real operational policy
  decision (how many days is "stuck" varies by org/migration urgency) — this skill asks for it explicitly
  rather than guessing a number that would silently mis-escalate for teams with a different cadence.
- **No live invocation of mysql-to-postgres-sql or squad-map.** Pure aggregation over existing files —
  see § Approach point 2's reasoning. If a workspace's `MIGRATION_STATUS.yaml` or `SQUAD_MAP.md` is
  missing or stale, this skill reports that gap; it never triggers either skill to fill it.
- **No MR tracking beyond `mr_url` passthrough.** `MIGRATION_STATUS.yaml`'s own `mr_url` field is
  surfaced as-is (a link); this skill doesn't query GitLab for MR state itself — that's pr-review's
  domain, cross-referenced via the existing `mysql-to-postgres-sql → pr-review` escalation
  (`cross-skill-escalation.md`), unchanged.
- **No changes to mysql-to-postgres-sql's or squad-map's own internals or file formats.**
- **No live scheduling infrastructure** — same "agent instructions, not infrastructure" boundary as every
  other item.

## Interface contract

**Input:**

| Field | Required | Notes |
|-------|----------|-------|
| `program_manifest` | Yes | List of `{workspace_root, squad_map_path?}` — **HARD STOP if empty** |
| `staleness_threshold_days` | Yes | **HARD STOP if absent** — no default, see Non-goals |
| `state_path` | No | Default alongside the report output |

**Output:** `MIGRATION_PROGRAM_REPORT.md` + `migration_program_rollup.json` — see
[reference/report-format.md](../../../migration-program-manager/reference/report-format.md).

## Acceptance criteria

- `migration-program-manager/SKILL.md` exists, ≤ 180 lines.
- Given N workspaces, every `services[]` row across all N appears in the rollup — none dropped for a
  missing `SQUAD_MAP.md` (falls to `squad: UNKNOWN`, not omitted).
- Given a service whose gate signature is unchanged across 2 runs spanning more than
  `staleness_threshold_days`, it's escalated as stalled on the second run.
- Given a service whose gate signature changed since the last run, staleness resets to 0, never
  carries over stale state from before the change.
- `scripts/aggregate_migration_status.py` has a `main(argv) -> int` CLI entrypoint, pytest coverage under
  `tests/`, stdlib + PyYAML only (matches the repo's stated Python convention).
- The `SQUAD_MAP.md` parser tolerates the Conflicts / Unmapped repos / Out of scope (archived) sections —
  never crashes on them, never treats a row in those sections as part of the main join table.
- `make lint-migration-program-manager` and `make lint-framework` pass; skill wired into root README.md,
  docs/README.md, docs/REPOSITORY.md, `skill-routing.md`, `cross-skill-escalation.md`,
  `prompt-injection.md`, `phase-glossary.md`, `CHANGELOG.md`.

## Implementation plan

1. `migration-program-manager/SKILL.md`, `README.md`, `SETUP.md`, `CHANGELOG.md`, `examples.md`.
2. `workflow/inputs.md` (parse `program_manifest`, `staleness_threshold_days`, `state_path`;
   untrusted-content note) and `workflow/run-rollup.md` (invoke the aggregator script, render the report).
3. `scripts/aggregate_migration_status.py` (parse `MIGRATION_STATUS.yaml` × N, parse `SQUAD_MAP.md`, join,
   compute staleness against persisted state, rank/group, emit report data), `tests/test_aggregate_migration_status.py`.
4. `reference/phase-index.md`, `lazy-load-index.md`, `smoke-test.md`, `report-format.md` (normative
   `MIGRATION_PROGRAM_REPORT.md` structure + `migration_program_rollup.json` shape).
5. `.cursor/rules/migration-program-manager.mdc`, `.kiro/steering/migration-program-manager.md`.
6. `Makefile`: `install-migration-program-manager` (chains `install-mysql-to-postgres-sql install-squad-map`),
   `install-claude-migration-program-manager`, `lint-migration-program-manager` (SKILL.md line count,
   workflow frontmatter, dangling links, required reference files, **pytest run** — new for this skill
   class, matching squad-map's/domain-comprehension's own lint-target pattern), added to `.PHONY`/`lint:`
   deps and `lint-framework`'s 4 hardcoded per-skill loops.
7. Root `README.md`, `docs/README.md`, `docs/REPOSITORY.md`: rows following the established pattern.
8. `docs/skill-framework/shared/skill-routing.md`, `cross-skill-escalation.md`, `prompt-injection.md`,
   `phase-glossary.md`: routing row, escalation rows, mapping subsection (not exempt — has its own
   Analyze logic: join, staleness computation, ranking).
9. Root `CHANGELOG.md` + `migration-program-manager/CHANGELOG.md`: initial release entry.
10. `make lint` green; deep review pass(es), fixing to 0 issues each round; commit.
