# Smoke test — expected minimal output

Run after install or any edit to this skill. Use ≥2 workspaces, each with a `MIGRATION_STATUS.yaml` (see
[mysql-to-postgres-sql/reference/smoke-test.md](../../mysql-to-postgres-sql/reference/smoke-test.md) to
set one up), at least one with a `SQUAD_MAP.md` and one without (to exercise both join paths).

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

## Invocation

> `program_manifest: [{workspace_root: <ws1>}, {workspace_root: <ws2>}]`, `staleness_threshold_days: 14`

## Expected first output

Per-workspace read announced (services found, `SQUAD_MAP.md` present or gap noted), before the aggregator
writes any output file.

## A correct minimal output contains

1. **Every service from every workspace's `MIGRATION_STATUS.yaml` appears** in either a squad section or
   the `UNKNOWN squad` section — never dropped.
2. **A workspace without `SQUAD_MAP.md`** produces `squad: UNKNOWN` services plus a Workspace gaps row —
   squad-map is never invoked to fill it.
3. **`MIGRATION_PROGRAM_REPORT.md` and `migration_program_rollup.json` both produced**, per
   [reference/report-format.md](report-format.md).
4. **`scripts/aggregate_migration_status.py` runs standalone** — `python3 scripts/aggregate_migration_status.py --help` exits 0.

## Pass criteria

- No workspace file (`MIGRATION_STATUS.yaml`, `SQUAD_MAP.md`) is modified — read-only throughout.
- `migration_program_state.json` (or the configured `state_path`) is created/updated — this skill's own
  artifact, never written into a migration workspace unless the caller explicitly points `state_path`
  there.
- Re-running immediately (same gate values) shows staleness `0` still climbing correctly from the first
  run's `first_observed_at`, not reset.

## Degraded paths

| Condition | Expected behavior |
|-----------|----------------------|
| A workspace's `MIGRATION_STATUS.yaml` is missing | Recorded as a Workspace gap, that workspace's services simply absent from the rollup — not a HARD STOP for other workspaces |
| `state_path` doesn't exist yet (first run) | Treated as empty state — every service starts at staleness 0, not an error |
| A gate signature changes between runs | Staleness resets to 0 for that service, not carried over |
| `SQUAD_MAP.md` has rows only in its Conflicts/Unmapped/Out-of-scope sections | Parser returns zero main-table rows, not a crash — those sections are never read as join data |
