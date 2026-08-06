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
4. **Cross-reference a `service` that appears in both rollups under different squads.** After both
   rollups are grouped, check for any `service` value present in both — if its `squad` differs between
   the two, add a Notes pointer on each side ("also in Cost optimization under `<squad>`" / "also in
   Migration status under `<squad>`"), per
   [reference/report-format.md](../reference/report-format.md)'s rule. This is a real, expected case since
   the two rollups resolve `squad` via different join mechanisms
   ([org-rollup-schema.md § 3](../../docs/skill-framework/shared/org-rollup-schema.md#3-join-key-squad-map-is-the-only-authoritative-source))
   — never reconciled into one "correct" squad, never silently left uncross-referenced. **The match is
   exact-string `service` equality only, best-effort** — this skill has no alias/normalization step of
   its own (unlike squad-map's own `service_aliases`, which exists precisely because service/deployment
   identifiers don't reliably match verbatim even within one system, per org-rollup-schema.md § 3 itself).
   A same-service pair whose two rollups happen to record genuinely different identifier strings for it
   will not be detected — a known, accepted limitation, not a guarantee this skill makes.

## 3. Compute staleness (display-only)

For every item, compute age = now − `last_updated`, **except for migration items when `staleness_days`
is present — prefer it instead.** "Present" means **the key exists in the item at all**, regardless of
its value — `staleness_days: 0` (the normal case immediately after a gate signature changes, per
migration-program-manager's own `compute_staleness`) still counts as present and must still be used, never
treated as falsy/absent. Checking key presence, not truthiness, is what keeps this fix from silently
reverting to the rollup-run-level bug it was written to close. `migration_program_rollup.json`'s own
`last_updated` is stamped at aggregation-run time (the same instant for every item that run), not
per-service — so an age computed from it tells you "how long since migration-program-manager last ran,"
not "this specific service's data is stale." `staleness_days` genuinely does vary per service (persisted
`gate_signature` comparison against prior runs). Cost items have no `staleness_days` equivalent (see
[workflow/inputs.md](inputs.md)) — their age is always `last_updated`-derived, which
cost-optimization-sprint-planner's own workflow does set per invocation.

An item whose staleness value (whichever source was used) exceeds `staleness_warning_days` gets a flagged
note in the digest, joined with the cross-rollup pointer from § 2 step 4 when both apply — **worded
differently depending on which source computed it**, since the two mean different things:

- Migration item, `staleness_days` used: `"stale — gate unchanged for <N> days, re-run migration-program-manager"`
- Any item, `last_updated`-derived age used (cost items always; migration items only when `staleness_days`
  is genuinely absent): `"stale — last updated <N> days ago, re-run <aggregator skill>"`, where `<aggregator
  skill>` is **migration-program-manager or cost-optimization-sprint-planner** (whichever produced this
  rollup) — never `org_rollup_item.source_skill` (that field names the per-service/per-deployment tool,
  `mysql-to-postgres-sql` or `k8s-overprovisioning-datadog`; re-running it alone does not regenerate the
  rollup file this skill actually reads).

**This never changes the item's own `status`** — unlike migration-program-manager's own staleness
computation (which escalates `status` to `stalled`), this skill only ever annotates, since it has no
basis to recompute a status a different skill already owns.

## 4. Render `WEEKLY_SQUAD_DIGEST.md`

Per [reference/report-format.md](../reference/report-format.md). Every item from both readable rollups
appears — either in its squad/metric_type section, or (if a whole rollup file was missing) noted in
Rollup gaps. Never silently dropped.

## Required outputs

| Output | Location | Required fields |
|--------|----------|-----------------|
| Weekly squad digest | `WEEKLY_SQUAD_DIGEST.md` | Per-squad sections (Migration status + Cost optimization sub-sections), UNKNOWN-squad group, Rollup gaps, staleness flags |
