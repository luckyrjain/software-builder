# Shared cross-repo aggregation layer: design

**Date:** 2026-08-05
**Status:** Approved design — **design only, no implementation in this phase**
**Source:** [team-facing-agents-roadmap.md](../plans/2026-08-05-team-facing-agents-roadmap.md) suggested
build order: *"Design the shared cross-repo aggregation layer once, informed by what #8, #10, #11 all
need, before building any of them individually."* This phase produces the design; items #8 (Migration
Program Manager), #10 (Cost Optimization Sprint Planner), and #11 (Weekly Squad Digest) each implement
against it later, per the roadmap's own sequencing.

## Problem

Three future roadmap items all need the same missing capability: turning **many single-service reports**
into **one org-wide, squad-grouped view**. None of the three skills they'd wrap has this today:

| Skill | Current shape | Gap |
|-------|----------------|-----|
| mysql-to-postgres-sql | `MIGRATION_STATUS.yaml` — already a fleet rollup, but **one file per single workspace**, hand-maintained, `owner` is a free-text string (not squad-map-derived) | No cross-workspace aggregation; ownership isn't authoritative |
| k8s-overprovisioning-datadog | Strictly **one deployment per run**; produces a `decision_graph` YAML per run, no fleet artifact at all | No org-wide sweep exists in any form |
| squad-map | `SQUAD_MAP.md` — a **markdown table**, not machine-parseable YAML/JSON | Correct join key for ownership, but no script can read it without a parser |

Researched and confirmed against the actual live artifacts (not assumed) — see § Source artifacts below.

## Approach

**No changes to any of the three wrapped skills' own internals** — same boundary this repo has held for
every item so far (who-owns-x-bot didn't change squad-map; pr-gatekeeper didn't change pr-review;
incident-triage-agent didn't change incident-rca or squad-map). The aggregation layer is a **new,
independent normative schema** — [org-rollup-schema.md](../../skill-framework/shared/org-rollup-schema.md) —
plus a documented **adapter mapping** per source skill, that items #8/#10/#11 each implement against
independently. This repo has no cross-skill code-sharing mechanism (every skill directory is copied
standalone to `~/.cursor/skills/<name>/`; scripts are never imported across skill directories anywhere in
the existing 10 skills) — so the shared layer is a **schema + convention**, the same way
`review-metadata-schema.md` is shared normatively across pr-review/domain-comprehension/squad-map/
mysql-to-postgres-sql without any of them sharing code.

## Source artifacts (researched, not assumed)

### `MIGRATION_STATUS.yaml` (mysql-to-postgres-sql)

Already fleet-shaped (`services: []` + a `summary:` counts block), written by
`workflow/migrate-service.md` step 4, one file per workspace root
(`mysql-to-postgres-sql/templates/MIGRATION_STATUS.yaml`):

```yaml
schema_version: 1
services:
  - name: "{{SERVICE_NAME}}"
    path: "{{SERVICE_DIR}}"
    tier_focus: P0        # P0 | P1 | P2 | dialect-only
    scan_gate: not_run     # pass | fail | not_run
    shadow_compare: pending
    config_cutover: pending
    mr_url: ""
    owner: ""              # free text — NOT squad-map-derived
    notes: ""
```

### `decision_graph` (k8s-overprovisioning-datadog)

`schema_version: 3`, one graph per single-deployment run
(`k8s-overprovisioning-datadog/reference/decision-graph-schema.md`). Relevant fields per run:
`assessment.final_decision` (`KEEP_CONFIGURATION|TRIM_RESOURCES|SCALE_UP|DEFER`),
`recommendations[].priority` (`P0|P1|P2`), `recommendations[].status`
(`READY|BLOCKED|DEFERRED|REJECTED|COMPLETED`). **Dollar figures are conditionally stored, not always
computed fresh:** the optional COST phase ([workflow/cost-analysis.md](../../../k8s-overprovisioning-datadog/workflow/cost-analysis.md))
populates `appendix.cost` on the graph (`$/core`, `$/GiB`, savings) **when it runs** — it's explicitly
skippable (`cost_skipped: <reason>` on a Critical stop, no savings-relevant dimension, or a
replicas/throttle-only ask). **Prefer `appendix.cost` when present; only fall back to deriving
`freed_cpu_cores`/`freed_giB`/`monthly_savings_total` yourself per `cost-estimation.md`'s formulas when
`appendix.cost` is absent** — never silently re-derive a number the graph already computed, and never
treat `cost_skipped` as "$0 savings" (it means "not assessed," not "no waste").

**k8s-overprovisioning-datadog already has a lightweight cluster-wide sweep — reuse it, don't bypass it.**
Phase 0b "Namespace ranking" ([workflow/resolve-service.md](../../../k8s-overprovisioning-datadog/workflow/resolve-service.md)
§Namespace ranking) runs a namespace-wide waste-% query across multiple deployments (`(reserved − used) /
reserved × 100`, ranks top 5) *before* drilling into one deployment for a full assessment. This is not a
full org-wide sweep — it's a cheap ranking pass over one namespace, capped at the top 5, that doesn't
itself produce full `decision_graph`s with recommendations for every deployment it ranks. Item #10's own
future design should evaluate reusing this ranking pass as a **pre-filter** (rank first, then run full
single-deployment assessments only on the worst offenders across all namespaces in scope) rather than
always running a full assessment on every deployment from scratch — cheaper, and reuses existing machinery
instead of quietly duplicating it.

### `SQUAD_MAP.md` (squad-map)

Markdown table, not YAML/JSON (`squad-map/templates/SQUAD_MAP.md`):

```
| Repo | GitLab namespace | GitLab squad | Datadog service | Datadog team | Confidence | Evidence |
```

`Confidence`: `HIGH|MEDIUM|LOW|UNKNOWN`. This is the **only correct join key for ownership** — never trust
`MIGRATION_STATUS.yaml`'s free-text `owner` field or infer a squad from a decision_graph's metadata.

**The join is a real, unsolved naming problem, not a detail to wave away** — confirmed directly against
squad-map's own canonical k8s example: `decision-graph.example.yaml`'s `metadata.service` is
`example-payment-consumer` while its own `scope` field carries the Datadog tag
`kube_deployment:payment-consumer` — the two don't match verbatim even in the skill's own reference
example. Match against `SQUAD_MAP.md`'s **`Datadog service`** column (not `Repo`) for k8s items, since
both are Datadog-side identifiers — and when they still don't match verbatim, use squad-map's own
`ownership.datadog.service_aliases` config mechanism
([squad-map/reference/config-schema.md](../../../squad-map/reference/config-schema.md)) rather than
inventing a second alias system; a future aggregator is a *consumer* of squad-map's existing alias
config, not a place to duplicate it. For `MIGRATION_STATUS.yaml` rows, match `services[].path` (a folder
name) against `SQUAD_MAP.md`'s **`Repo`** column first, falling back to `services[].name`; when neither
matches, `squad: UNKNOWN` with a note — never guess. See
[org-rollup-schema.md § 3](../../skill-framework/shared/org-rollup-schema.md) for the normative version
of this rule.

## The normalized rollup item — one shape, three adapters

Full schema: [org-rollup-schema.md](../../skill-framework/shared/org-rollup-schema.md). Summary: one
`org_rollup_item` per (service, source skill, metric) — `service`, `squad` (+ `squad_confidence`),
`source_skill`, `metric_type`, `status`, `priority`, `value` (metric-specific), `evidence_ref` (path/URL
back to the source artifact), `last_updated`. Each of the three future skills' own aggregator script maps
its source artifact's rows into this shape:

| Source | `metric_type` | `value` | `status` derivation |
|--------|-----------------|---------|------------------------|
| `MIGRATION_STATUS.yaml` row | `pg_migration_gate` | current gate name (`scan_gate`/`shadow_compare`/`config_cutover`) | `blocked` if any gate is `fail`; `stalled` if `pending` past a configured staleness threshold; else `in_progress`/`done` |
| `decision_graph` (per deployment run) | `k8s_waste` | `{freed_cpu_cores, freed_giB, monthly_savings_total, cost_basis}` derived per `cost-estimation.md` | from `recommendations[].status` |
| squad-map row | (join key only, not itself a rollup item) | — | — |

## Grouping and ranking (per consuming skill — not prescribed here beyond the join)

- **#8 Migration Program Manager** ranks/escalates by staleness (gate unchanged for N days) and blocked
  count per squad — needs a staleness threshold config, not specified here (that skill's own design).
- **#10 Cost Optimization Sprint Planner** ranks by `monthly_savings_total` descending, grouped by squad.
- **#11 Weekly Squad Digest** groups both #8's and #10's rollup items by squad, routes to the channel
  squad-map's own `Datadog team`/`GitLab squad` implies (that routing convention is squad-map's own,
  reused unchanged, same pattern as who-owns-x-bot/incident-triage-agent's ownership lookups).

This design deliberately does **not** prescribe ranking formulas beyond the join/normalization layer —
each future skill owns its own ranking logic against the common `org_rollup_item` shape, same separation
of concerns as `confidence-bands.md` (shared vocabulary) vs. each skill's own confidence-computation
rules (skill-specific).

## Multi-deployment k8s sweep — the one piece #10 must build itself

Because k8s-overprovisioning-datadog has no org-wide mode, "#10 Cost Optimization Sprint Planner" isn't a
thin wrapper the way who-owns-x-bot/pr-gatekeeper are — it must **loop** k8s-overprovisioning-datadog once
per deployment in scope (deployment list from squad-map's `SQUAD_MAP.md` or an explicit config), collect
each run's `decision_graph`, then aggregate. This mirrors loop-task-implementer's own per-task loop
pattern, not a single-invocation wrapper — call this out explicitly in #10's own future design spec so it
isn't scoped as a simple wrapper by mistake.

## Script convention (for #8/#10/#11's own future aggregator scripts)

Each future skill implements its own aggregator script (no shared code across skill directories, per
repo convention) — but all three should follow the same shape, matching
`docs/superpowers/plans/2026-07-02-skills-roadmap.md`'s stated Python convention: stdlib + PyYAML only,
pure functions returning `list[str]` errors where validating, a `main(argv) -> int` CLI entrypoint, pytest
coverage under that skill's own `tests/`. A markdown-table reader for `SQUAD_MAP.md` (needed by all three)
is new territory for this repo — no existing script parses a skill's own markdown table today — so each
implementation should keep that parser small, tested, and tolerant of `SQUAD_MAP.md`'s documented Conflict/
Unmapped/Out-of-scope sections (never crash on them, treat rows outside the main table as absent from the
join).

## Non-goals (explicitly out of scope for this design phase)

- No implementation — no scripts, no new skill directories. That happens when #8/#10/#11 are each built.
- No changes to mysql-to-postgres-sql, k8s-overprovisioning-datadog, or squad-map's own internals.
- No ranking-formula specifics for any individual future skill — each owns its own.
- No live posting/scheduling infrastructure — same "agent instructions, not infrastructure" boundary as
  every webhook-triggered skill built so far.

## Acceptance criteria for this design phase

- [org-rollup-schema.md](../../skill-framework/shared/org-rollup-schema.md) exists as a new shared
  framework doc, cross-referenced from `docs/skill-framework/README.md`'s Shared files table.
- `docs/skill-framework/shared/phase-glossary.md` §6 Artifact glossary gains an `org_rollup_item` row
  (source: none yet — "future: items #8/#10/#11").
- This design doc is registered in `docs/README.md`'s Design specs table.
- `make lint` stays green (no skill-level lint targets are affected by a design-only phase).
