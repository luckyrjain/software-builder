# WEEKLY_SQUAD_DIGEST.md format

**Normative.** The exact structure [workflow/run-digest.md](../workflow/run-digest.md) § 4 must produce.

## Structure (order fixed)

```markdown
# Weekly squad digest — <date>

**Rollups read:** `<migration_rollup_path or "not supplied">` · `<cost_rollup_path or "not supplied">`
**Source revisions:** migration `<sha256 prefix or "not supplied">` · cost `<sha256 prefix or "not supplied">`

Compute each revision as the first 12 hex chars of the SHA-256 of the rollup file bytes read in Run digest
§ 1 (or `not supplied` when that rollup path was unset or unreadable). This gives downstream readers a
stable fingerprint without re-deriving squad/status fields.

## <squad name>

### Migration status

| Service | Status | Priority | Confidence | Notes |
|---------|--------|----------|------------|-------|
| <service> | <status> | <priority or —> | <squad_confidence> | <stale-flag branch: if `staleness_days` is present (key exists) and past `staleness_warning_days`, "stale — gate unchanged for N days, re-run migration-program-manager"; else if `staleness_days` is genuinely absent and a `last_updated`-derived age is past `staleness_warning_days`, "stale — last updated N days ago, re-run migration-program-manager"; else no stale flag> <cross-ref branch: "also in Cost optimization under `<other squad>`" if the same service appears in the cost rollup under a different squad> — both branches joined with `; ` if both apply; else —> |

<In migration-program-manager's own order: blocked, then stalled (ranked by `staleness_days` descending,
matching migration-program-manager's own [workflow/run-rollup.md § 2](../../migration-program-manager/workflow/run-rollup.md)
convention — never re-sorted by any other rule), then in_progress, then done.>

### Cost optimization

| Service | Monthly savings | Status | Priority | Confidence | Notes |
|---------|------------------|--------|----------|------------|-------|
| <service> | `$<value.monthly_savings_total>` | <status> | <priority or —> | <squad_confidence> | <"stale — last updated N days ago, re-run cost-optimization-sprint-planner" if past staleness_warning_days; "also in Migration status under `<other squad>`" if the same service appears in the migration rollup under a different squad; both joined with `; ` if both apply; else —> |

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
  confidence band. `squad_confidence` gets its own **Confidence column** in both tables — every item's
  value is shown, not just LOW/UNKNOWN ones — matching cost-optimization-sprint-planner's own report
  structure (a dedicated column, not a Notes-only callout; that skill's report additionally names
  LOW/UNKNOWN matches in its prose Notes section, which this skill's per-item table column already makes
  visible without a separate step).
- **Migration status and Cost optimization are always separate sub-sections, never merged into one
  cross-metric table or ranking** — `pg_migration_gate` and `k8s_waste` items are not comparable, and
  inventing a blended score would be new analysis logic this skill's own design spec rules out.
- **The same `service` appearing in both rollups under different squads is cross-referenced, never
  silently presented as two unrelated rows** — `migration_program_rollup.json` and
  `cost_optimization_sprint_rollup.json` resolve `squad` via different join mechanisms (see
  [org-rollup-schema.md § 3](../../docs/skill-framework/shared/org-rollup-schema.md#3-join-key-squad-map-is-the-only-authoritative-source))
  and can legitimately disagree — a real case, not hypothetical. Each row's own sub-section table gets a
  Notes pointer to the other section/squad; this skill never reconciles which squad is "right," since
  neither rollup's own join is this skill's to override. **The match is exact-string `service` equality
  only, best-effort** — a known, accepted limitation (this skill has no alias/normalization step of its
  own, unlike squad-map's `service_aliases`), not a guarantee that every real same-service pair is caught.
- **A rollup gap is never rendered as `$0` savings or a fabricated "done" migration status** — an absent
  rollup means "not checked this run," not "nothing to report." See Rollup gaps.
- **Staleness is display-only, and its precision differs by rollup — never presented as uniformly
  per-service** — migration-program-manager's own `last_updated` is stamped at aggregation-run time, not
  per-service (see [workflow/inputs.md](../workflow/inputs.md)'s Normalization section), so a migration
  item's staleness flag reflects "how long since migration-program-manager last ran," not "this specific
  service's own data is stale" — prefer that rollup's own `staleness_days` field when computing the
  migration-side flag, since it genuinely does vary per service (persisted `gate_signature` comparison).
  **"Present" means the key exists, regardless of value** — `staleness_days: 0` (the normal case right
  after a gate changes) still counts and must still be used, never treated as absent by a truthiness
  check. Cost items have no `staleness_days` equivalent, so their flag is always `last_updated`-derived
  age — the only staleness signal that rollup carries; neither this skill nor
  cost-optimization-sprint-planner's own docs claim that timestamp is genuinely per-deployment, so it's
  used as the best available signal, not asserted to be as precise as migration's `staleness_days`. **The
  note text differs
  by source** — "gate unchanged for N days" for `staleness_days`, "last updated N days ago" for
  `last_updated` — since the two measure different things and using the wrong wording for the wrong
  source would misrepresent what's actually stale. The re-run pointer always names the **aggregator**
  skill (migration-program-manager / cost-optimization-sprint-planner), never `org_rollup_item`'s own
  `source_skill` field (which names the per-service tool, e.g. `mysql-to-postgres-sql` — re-running that
  alone doesn't regenerate the rollup file this skill reads). Either way, a flagged item's `status` in the
  table is still exactly what the producing skill computed; the staleness note is additive, never a
  status override.
