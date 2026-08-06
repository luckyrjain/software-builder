# WEEKLY_SQUAD_DIGEST.md format

**Normative.** The exact structure [workflow/run-digest.md](../workflow/run-digest.md) § 4 must produce.

## Structure (order fixed)

```markdown
# Weekly squad digest — <date>

**Rollups read:** `<migration_rollup_path or "not supplied">` · `<cost_rollup_path or "not supplied">`

## <squad name>

### Migration status

| Service | Status | Priority | Notes |
|---------|--------|----------|-------|
| <service> | <status> | <priority or —> | <staleness flag if past staleness_warning_days, else —> |

<In migration-program-manager's own order: blocked, then stalled, then in_progress, then done.>

### Cost optimization

| Service | Monthly savings | Status | Priority | Notes |
|---------|------------------|--------|----------|-------|
| <service> | `$<value.monthly_savings_total>` | <status> | <priority or —> | <staleness flag if past staleness_warning_days, else —> |

<In cost-optimization-sprint-planner's own order: monthly_savings_total descending.>

<A squad with items in only one rollup still gets both sub-headings — the empty one reads "No items in
this rollup for this squad," never silently omitted, so a reader can tell "no data" from "not checked.">

<Repeat per squad, in any stable order. A squad must have at least one item in either rollup to appear.>

## UNKNOWN squad

<Same two sub-sections, for every item that couldn't be joined to a squad by its own producing skill —
always rendered last, never silently merged into a named squad's section.>

## Rollup gaps

| Rollup | Reason |
|--------|--------|
| migration_program_rollup.json | <"Not supplied in rollup_manifest" or "File not found at <path> — run migration-program-manager first"> |
| cost_optimization_sprint_rollup.json | <"Not supplied in rollup_manifest" or "File not found at <path> — run cost-optimization-sprint-planner first"> |

<Omit a rollup's row here if it was actually read successfully — this section is for gaps only, not a
status line for every run.>
```

## Rules

- **Every item from both readable rollups appears somewhere in the digest** — either a row in its
  squad/metric_type sub-section, never silently dropped for being stale, low-priority, or any other
  reason.
- **`squad`, `squad_confidence`, `status`, `priority` are surfaced exactly as each producing skill
  computed them** — this skill never re-labels a status, never re-derives a squad, never recomputes a
  confidence band. `squad_confidence` of `LOW`/`UNKNOWN` is worth a Notes callout, same convention as
  cost-optimization-sprint-planner's own report.
- **Migration status and Cost optimization are always separate sub-sections, never merged into one
  cross-metric table or ranking** — `pg_migration_gate` and `k8s_waste` items are not comparable, and
  inventing a blended score would be new analysis logic this skill's own design spec rules out.
- **A rollup gap is never rendered as `$0` savings or a fabricated "done" migration status** — an absent
  rollup means "not checked this run," not "nothing to report." See Rollup gaps.
- **Staleness is display-only** — a flagged item's `status` in the table is still exactly what the
  producing skill computed; the staleness note is additive, never a status override.
