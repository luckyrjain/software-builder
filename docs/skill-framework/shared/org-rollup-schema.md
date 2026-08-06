# Org rollup schema (shared)

**Normative.** Implemented by all three skills it was designed for: migration-program-manager (#8,
produces `pg_migration_gate` items), cost-optimization-sprint-planner (#10, produces `k8s_waste` items),
and weekly-squad-digest (#11, the sole consumer that reads and combines both). Written once, ahead of any
of the three, per the
[team-facing agents roadmap](../../superpowers/plans/2026-08-05-team-facing-agents-roadmap.md)'s own
suggested build order.
**Design spec:** [2026-08-05-org-rollup-aggregation-layer-design.md](../../superpowers/specs/2026-08-05-org-rollup-aggregation-layer-design.md).

## 1. Purpose

Two skills (migration-program-manager, cost-optimization-sprint-planner) each need to turn many
single-service reports into one org-wide, squad-grouped view; a third (weekly-squad-digest) combines both
into one digest. None of the three source skills they wrap (mysql-to-postgres-sql,
k8s-overprovisioning-datadog, squad-map) has an org-wide aggregation concept of its own, and this repo has
no cross-skill code-sharing mechanism — every skill directory installs standalone. This file is the **one
normalized shape** each aggregator independently maps its source artifact into, so #8/#10/#11 don't each
invent a different rollup schema.

## 2. The `org_rollup_item` shape

One item per `(service, source_skill, metric_type)` tuple:

```yaml
org_rollup_item:
  service: "<name>"                    # from the source artifact — see § Adapters for the exact field
  squad: "<squad name>" | "UNKNOWN"    # from SQUAD_MAP.md — never from a source artifact's own free-text owner field
  squad_confidence: HIGH | MEDIUM | LOW | UNKNOWN   # squad-map's own confidence band, carried through unchanged
  source_skill: mysql-to-postgres-sql | k8s-overprovisioning-datadog
  metric_type: pg_migration_gate | k8s_waste        # extend this enum per future skill, don't overload existing values
  status: <metric-type-specific enum — see § Adapters>
  priority: P0 | P1 | P2 | null        # null when the source artifact has no priority concept for this metric
  value: <metric-type-specific payload — see § Adapters>
  evidence_ref: "<path or URL back to the source artifact this item was derived from>"
  last_updated: "<ISO-8601>"
```

`squad_confidence` exists so a consuming skill can decide whether to trust squad-only routing at LOW
confidence or fall back to a human-review queue — mirrors [confidence-bands.md](confidence-bands.md)'s
own HIGH/MEDIUM/LOW/UNKNOWN vocabulary, reused here rather than inventing a parallel one.

## 3. Join key — squad-map is the only authoritative source

**Never trust a source artifact's own free-text ownership field** (e.g. `MIGRATION_STATUS.yaml`'s
`services[].owner` is a hand-typed string, not derived from squad-map, and may be stale or wrong). Always
resolve `squad`/`squad_confidence` by matching the source artifact's service/repo identifier against
`SQUAD_MAP.md`'s `Repo` or `Datadog service` column (per
[squad-map/reference/squad-mapping.md](../../../squad-map/reference/squad-mapping.md)). When no match is
found, `squad: UNKNOWN`, `squad_confidence: UNKNOWN` — never silently drop the item, never guess.

**On a row in `SQUAD_MAP.md`'s own Conflicts table** (GitLab squad ≠ Datadog team for that repo/service),
`squad` takes **squad-map's own documented tiebreak** — "Datadog team (runtime); note GitLab in conflict
table" (`squad-mapping.md` § Reconciliation) — never invent a different tiebreak here; this schema reuses
squad-map's existing rule rather than layering a second one on top.

**The name doesn't always match verbatim — this is a real, not hypothetical, mismatch.** Confirmed
directly against k8s-overprovisioning-datadog's own canonical example:
[decision-graph.example.yaml](../../../k8s-overprovisioning-datadog/reference/decision-graph.example.yaml)'s
`metadata.service` (`example-payment-consumer`) differs from its own `scope`'s `kube_deployment:` tag
(`payment-consumer`).
Per adapter:
- **k8s items:** match against `SQUAD_MAP.md`'s `Datadog service` column (both Datadog-side identifiers);
  when it still doesn't match verbatim, use squad-map's own `ownership.datadog.service_aliases` config
  ([squad-map/reference/config-schema.md](../../../squad-map/reference/config-schema.md)) — an aggregator
  is a *consumer* of that existing alias mechanism, never a place to build a second one.
- **mysql-to-postgres-sql items:** match `services[].path` against `SQUAD_MAP.md`'s `Repo` column first
  (a folder name is more likely to equal a repo name than a free-form `services[].name`), falling back to
  `services[].name` if `path` doesn't match.

`SQUAD_MAP.md` is a **markdown table, not YAML/JSON** — parsing it is new territory in this repo (no
existing script reads it programmatically). A parser must tolerate the file's own Conflicts / Unmapped
repos / Out of scope (archived) sections without treating rows there as part of the main join table.

## 4. Adapters — per source skill

### mysql-to-postgres-sql → `pg_migration_gate`

Source: `MIGRATION_STATUS.yaml` `services[]` rows
([mysql-to-postgres-sql/templates/MIGRATION_STATUS.yaml](../../../mysql-to-postgres-sql/templates/MIGRATION_STATUS.yaml)).
**Implemented by [migration-program-manager](../../../migration-program-manager/SKILL.md)** (item #8),
which reads every workspace's `MIGRATION_STATUS.yaml` directly (mysql-to-postgres-sql itself never
aggregates across workspaces) and additionally persists a `staleness_days` value per service — the
"consuming skill's own staleness threshold" the row below defers to.

| `org_rollup_item` field | Derived from |
|--------------------------|----------------|
| `service` | `services[].name` |
| `status` | `blocked` if any of `scan_gate`/`shadow_compare`/`config_cutover` is `fail`; `stalled` if a gate has been `pending`/`not_run` past a consuming skill's own staleness threshold (not defined here); else `in_progress` or `done` |
| `priority` | `services[].tier_focus` (`P0`/`P1`/`P2`; `dialect-only` maps to `null`) |
| `value` | `{scan_gate, shadow_compare, config_cutover, mr_url}` verbatim |
| `evidence_ref` | The `MIGRATION_STATUS.yaml` path itself |

### k8s-overprovisioning-datadog → `k8s_waste`

Source: one `decision_graph` YAML **per single-deployment run**
([k8s-overprovisioning-datadog/reference/decision-graph-schema.md](../../../k8s-overprovisioning-datadog/reference/decision-graph-schema.md))
— there is no *full-assessment* org-wide k8s mode. **Implemented by
[cost-optimization-sprint-planner](../../../cost-optimization-sprint-planner/SKILL.md)** (item #10),
which loops k8s-overprovisioning-datadog once per deployment in scope, collecting N graphs before this
adapter runs, optionally pre-filtered by k8s-overprovisioning-datadog's own Phase 0b "Namespace ranking"
query pattern (top 5 per namespace, reused directly rather than through a standalone-ranking mode
k8s-overprovisioning-datadog doesn't document — see
[cost-optimization-sprint-planner's design spec](../../superpowers/specs/2026-08-05-cost-optimization-sprint-planner-design.md)).
`appendix.cost`'s exact field shape (assumed by the `value` row below) is not formally defined in
`decision-graph-schema.md` and appears in no real example graph — treat it as assumed, not guaranteed,
same as that design spec's own § Non-goals.

| `org_rollup_item` field | Derived from |
|--------------------------|----------------|
| `service` | The graph's deployment/service identifier (`metadata` block) |
| `status` | `recommendations[].status` (`READY\|BLOCKED\|DEFERRED\|REJECTED\|COMPLETED`) |
| `priority` | `recommendations[].priority` (`P0\|P1\|P2`) |
| `value` | `{freed_cpu_cores, freed_giB, monthly_savings_total, cost_basis}` — **prefer `appendix.cost` when the graph's optional COST phase ran** (it stores `$/core`, `$/GiB`, savings already); only derive these yourself per [k8s-overprovisioning-datadog/cost-estimation.md](../../../k8s-overprovisioning-datadog/cost-estimation.md)'s formulas when `appendix.cost` is absent (COST is skippable — `cost_skipped: <reason>` means "not assessed," never treat it as "$0") |
| `evidence_ref` | The specific `decision_graph` YAML this run produced |

A deployment with `assessment.final_decision: KEEP_CONFIGURATION` still produces an `org_rollup_item`
with `value.monthly_savings_total: 0` — never omit a rollup item just because a deployment wasn't
overprovisioned; item #10's own ranking naturally sorts it to the bottom.

## 5. Grouping (consuming skills own their own ranking)

Group `org_rollup_item`s by `squad` for a per-squad view. Beyond that, this schema does **not** prescribe
ranking formulas (e.g. "sort by `monthly_savings_total` descending") — that's each consuming skill's own
design, the same separation [confidence-bands.md](confidence-bands.md) keeps between shared vocabulary
and each skill's own confidence-computation rules.

## 6. Extending this schema

Adding a fourth source skill later: add a new `metric_type` value and its own `§4 Adapters` subsection
here — never repurpose an existing `metric_type`'s `value` shape for a different source, since consuming
skills key their parsing off `metric_type`.
