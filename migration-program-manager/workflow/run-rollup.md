---
workflow_version: 1.0
phase: run-rollup
produces:
  - migration_program_report
  - migration_program_rollup
consumes:
  - program_manifest
  - staleness_threshold_days
  - state_path
---

# Run rollup — aggregate, rank, render

## 1. Run the aggregator script

Invoke [scripts/aggregate_migration_status.py](../scripts/aggregate_migration_status.py) with
`program_manifest`, `staleness_threshold_days`, and `state_path`:

```bash
python3 scripts/aggregate_migration_status.py \
  --manifest <program_manifest.json> \
  --staleness-threshold-days <N> \
  --state-path <state_path> \
  --out-rollup migration_program_rollup.json
```

The script (see the script's own module docstring for its exact function-level contract):

1. For each manifest entry, reads `MIGRATION_STATUS.yaml` at `workspace_root` — missing file → recorded
   as a gap for that workspace, not a crash, not a silent skip of the whole run.
2. Reads `squad_map_path` if present — missing → every service in that workspace joins as
   `squad: UNKNOWN`, `squad_confidence: UNKNOWN`, noted in the report; **never invokes squad-map itself**
   to fill the gap (see [SKILL.md](../SKILL.md) § Why no gate policy).
3. Joins each `services[]` row into an `org_rollup_item` per
   [org-rollup-schema.md § 4](../../docs/skill-framework/shared/org-rollup-schema.md#4-adapters-per-source-skill) —
   match `path` against `SQUAD_MAP.md`'s `Repo` column first, falling back to `name`.
4. Loads the prior run's state from `state_path` (absent on first run — treat as empty, every service
   starts at staleness 0, not an error). Computes each service's `gate_signature`
   (`scan_gate`/`shadow_compare`/`config_cutover` tuple); unchanged since last run → staleness = now −
   stored `first_observed_at`; changed or new → reset `first_observed_at` to now, staleness 0. The item's
   `status` (per org-rollup-schema.md's `pg_migration_gate` adapter: `blocked` / `stalled` / `in_progress`
   / `done`) is finalized here, not just at render time — `blocked` always wins over staleness; otherwise a
   service whose staleness has reached `staleness_threshold_days` is written as `stalled` directly into
   `migration_program_rollup.json`, so a downstream reader of the JSON never has to re-derive it.
5. Writes the updated state back to `state_path` — **this file belongs to this skill alone**;
   mysql-to-postgres-sql never reads or knows about it.
6. Emits `migration_program_rollup.json` (the full `org_rollup_item` list) and structured rollup data for
   report rendering.

## 2. Rank and group

Per squad: **blocked** (any gate `fail`) first, then **stalled** (staleness ≥ `staleness_threshold_days`)
ranked by staleness descending, then **in_progress**, then **done**. `squad: UNKNOWN` items form their own
group, always rendered last — never silently merged into a named squad's section.

## 3. Render `MIGRATION_PROGRAM_REPORT.md`

Per [reference/report-format.md](../reference/report-format.md). Every `program_manifest` entry appears —
a workspace with a clean `MIGRATION_STATUS.yaml` (nothing blocked or stalled) still gets a summary line;
a workspace with a missing file gets a Notes-section gap entry, never silently dropped from the report.

## Required outputs

| Output | Location | Required fields |
|--------|----------|-----------------|
| Migration program report | `MIGRATION_PROGRAM_REPORT.md` | Per-squad groups (blocked/stalled/in_progress/done), UNKNOWN-squad group, workspace gaps |
| Machine-readable rollup | `migration_program_rollup.json` | Full `org_rollup_item` list per org-rollup-schema.md |
