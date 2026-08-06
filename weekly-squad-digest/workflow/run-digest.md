---
workflow_version: 1.0
phase: run-digest
produces:
  - weekly_squad_digest
consumes:
  - rollup_manifest
  - staleness_warning_days
---

# Run digest — read, group, flag staleness, render

## 1. Read both rollup files

For each path set in `rollup_manifest`:

- File missing or unreadable → record a Rollup gaps entry (see
  [reference/report-format.md](../reference/report-format.md)), skip that rollup entirely, **continue
  with whichever rollup is still readable** — never a HARD STOP for the whole run just because one
  rollup is absent.
- File present → parse as a flat JSON array of `org_rollup_item` objects per
  [org-rollup-schema.md](../../docs/skill-framework/shared/org-rollup-schema.md). **Never re-derive
  `squad`, `squad_confidence`, `status`, or `priority`** — read them exactly as the producing skill wrote
  them.

If both paths were unset, Inputs already HARD STOPped before this phase runs — this step never sees that
case.

## 2. Group by squad, then by `metric_type`

Per [org-rollup-schema.md § 5](../../docs/skill-framework/shared/org-rollup-schema.md#5-grouping-consuming-skills-own-their-own-ranking),
this schema specifies grouping by squad only — ranking within a squad is each consumer's own decision.
This skill's decision:

1. Group every item (from either rollup) by `squad`. `squad: UNKNOWN` forms its own group, always
   rendered last — never silently merged into a named squad's section.
2. **Within each squad, split by `metric_type`** into two sub-sections — `pg_migration_gate` (Migration
   status) and `k8s_waste` (Cost optimization). Their `value` shapes are structurally different (a gate
   status tuple vs. a dollar figure) and not directly comparable — this skill never invents a combined
   cross-metric score or a single merged ranking, per the
   [design spec § Non-goals](../../docs/superpowers/specs/2026-08-05-weekly-squad-digest-design.md#non-goals-explicitly-out-of-scope).
3. **Within each sub-section, keep that producing skill's own sort order** — migration:
   blocked → stalled → in_progress → done (migration-program-manager's own convention); cost:
   `value.monthly_savings_total` descending (cost-optimization-sprint-planner's own convention). Never
   re-sort by a rule this skill invents.

## 3. Compute staleness (display-only)

For every item, compute age = now − `last_updated`. An item whose age exceeds
`staleness_warning_days` gets a flagged note ("stale — last updated `<N>` days ago, re-run
`<source_skill>`") in the digest. **This never changes the item's own `status`** — unlike
migration-program-manager's staleness computation (which escalates `status` to `stalled`), this skill
only ever annotates, since it has no basis to recompute a status a different skill already owns.

## 4. Render `WEEKLY_SQUAD_DIGEST.md`

Per [reference/report-format.md](../reference/report-format.md). Every item from both readable rollups
appears — either in its squad/metric_type section, or (if a whole rollup file was missing) noted in
Rollup gaps. Never silently dropped.

## Required outputs

| Output | Location | Required fields |
|--------|----------|-----------------|
| Weekly squad digest | `WEEKLY_SQUAD_DIGEST.md` | Per-squad sections (Migration status + Cost optimization sub-sections), UNKNOWN-squad group, Rollup gaps, staleness flags |
