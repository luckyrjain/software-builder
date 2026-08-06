# Smoke test — expected minimal output

Run after install or any edit to this skill. Use real `migration_program_rollup.json` and
`cost_optimization_sprint_rollup.json` files (run migration-program-manager's and
cost-optimization-sprint-planner's own smoke tests first to produce them — see their own
`reference/smoke-test.md`), ideally with at least one squad appearing in both rollups and one appearing
in only one, to exercise both paths.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

## Invocation

> `rollup_manifest: {migration_rollup_path: <path>, cost_rollup_path: <path>}`

## Expected first output

The resolved rollup paths announced (which were supplied, which were found on disk) before the digest is
rendered.

## A correct minimal output contains

1. **Every item from both rollups appears** in its squad's Migration status or Cost optimization
   sub-section — never dropped.
2. **A squad present in only one rollup** still gets both sub-headings, the empty one noted as "No items
   in this rollup for this squad."
3. **`WEEKLY_SQUAD_DIGEST.md` produced**, per [reference/report-format.md](report-format.md).
4. **An item whose staleness value exceeds `staleness_warning_days`** (default 14) is flagged, its own
   `status` unchanged. A migration item **with the `staleness_days` key present — regardless of value,
   including `staleness_days: 0`** — uses that field directly and reads
   `"stale — gate unchanged for <N> days, re-run migration-program-manager"`; a migration item where the
   key is genuinely absent, and every cost item, uses a `last_updated`-derived age and reads
   `"stale — last updated <N> days ago, re-run <aggregator skill>"` (migration-program-manager or
   cost-optimization-sprint-planner — never the item's own `source_skill` field).
5. **Every row shows a Confidence column value** (`squad_confidence`), not just LOW/UNKNOWN ones.
6. **A service present in both rollups under different squads** gets a Notes cross-reference on both
   rows — exact-string `service` match only.
7. **A row that is both stale and cross-referenced** joins both notes in one cell with `; `, staleness
   note first.

## Pass criteria

- Neither migration-program-manager nor cost-optimization-sprint-planner is invoked — this skill only
  reads their existing output files.
- `squad`/`squad_confidence`/`status`/`priority` in the digest match the source rollup JSON exactly, byte
  for byte on the values (only formatting/grouping differs).
- Migration status and Cost optimization are always separate sub-sections, never merged into one table.

## Degraded paths

| Condition | Expected behavior |
|-----------|----------------------|
| Only `migration_rollup_path` supplied | Cost rollup row appears in Rollup gaps ("Not supplied"); digest still renders from migration data alone |
| A supplied path doesn't exist on disk | Recorded in Rollup gaps ("File not found... run `<skill>` first"); the other rollup, if readable, still renders |
| `rollup_manifest` has neither path set | Inputs HARD STOP — no digest produced |
| An item's `squad` is `UNKNOWN` in its source rollup | Rendered in the `UNKNOWN squad` group, always last — never guessed into a named squad |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
