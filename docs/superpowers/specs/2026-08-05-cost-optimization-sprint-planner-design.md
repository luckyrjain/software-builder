# cost-optimization-sprint-planner: design

**Date:** 2026-08-05
**Status:** Approved design
**Source:** Item #10 of [team-facing-agents-roadmap.md](../plans/2026-08-05-team-facing-agents-roadmap.md) —
P2, "Cost Optimization Sprint Planner — org-wide sweep wrapper around k8s-overprovisioning-datadog: loop
per deployment in scope (using Phase 0b namespace ranking as pre-filter), collect `decision_graphs`,
aggregate to `org_rollup_item` (`k8s_waste`), rank by `monthly_savings_total` descending grouped by squad.
NOT a thin wrapper — explicitly the one piece Phase 4's design flagged as needing its own multi-deployment
sweep loop, modeled on loop-task-implementer's per-task loop pattern." Implements
[org-rollup-schema.md](../../skill-framework/shared/org-rollup-schema.md) and its `k8s_waste` adapter,
designed in Phase 4 ([org-rollup-aggregation-layer-design.md](2026-08-05-org-rollup-aggregation-layer-design.md)).

## Problem

k8s-overprovisioning-datadog assesses **one deployment per conversational run** — there is no org-wide
mode. Nobody has a ranked, org-wide view of "where's the money" across every deployment worth assessing.

## Correcting the roadmap description before designing against it

Two claims in the roadmap item's own wording don't match the actual code, confirmed by direct research —
recording both here so this spec isn't built on a fabricated premise:

1. **"Modeled on loop-task-implementer's per-task loop pattern"** — `loop-task-implementer/workflow/orchestrator.md`
   works **exactly one task at a time**; its own "select next task" step only fires *after an authorized
   merge*, inside a single invocation. It is a single-item state machine, not a multi-item batch loop. The
   actual precedent in this repo for "loop a single-item, conversational, gate-heavy skill over many items,
   with per-item failure isolation and a batch-level stop condition" is **backlog-runner**, which wraps
   loop-task-implementer exactly the way this skill needs to wrap k8s-overprovisioning-datadog. This spec
   models the sweep loop on [backlog-runner/reference/queue-policy.md](../../../backlog-runner/reference/queue-policy.md),
   citing loop-task-implementer only as what backlog-runner itself wraps.
2. **Phase 0b ("Namespace ranking") is not documented as a standalone, report-only mode.** Its own text
   ([resolve-service.md § Namespace ranking](../../../k8s-overprovisioning-datadog/workflow/resolve-service.md#namespace-ranking)):
   *"run namespace ranking queries... rank top 5, **drill into worst deployment, then continue resolve**."*
   That's written as a step feeding into one full single-deployment assessment, not a report-only ranking
   the caller can request and stop. This skill treats Phase 0b as a **query pattern to reuse** (the exact
   `queries.md` § Namespace / cluster ranking scalar queries), invoked directly via Datadog MCP as this
   skill's own pre-filter step — not as an invocation of k8s-overprovisioning-datadog asked to "just rank
   and stop," which isn't a mode that skill documents as supported.

## What's already there vs. genuinely new — researched, not assumed

| Capability | Exists today? |
|---|---|
| Single-deployment waste assessment (`decision_graph`) | **Yes** — k8s-overprovisioning-datadog, unchanged, one conversational run per deployment |
| Namespace/deployment waste-ranking **query pattern** (not a standalone mode) | **Yes** — `queries.md` § Namespace / cluster ranking; reused directly, not reinvented |
| `k8s_waste` → `org_rollup_item` adapter | **Yes, already fully specified** — [org-rollup-schema.md § 4](../../skill-framework/shared/org-rollup-schema.md#4-adapters-per-source-skill), designed in Phase 4, before this skill existed |
| Looping a single-item, gate-heavy, conversational skill over many items with failure isolation + a batch-level stop condition | **Yes, as a pattern** — backlog-runner's `queue-policy.md` wrapping loop-task-implementer; **new to k8s-overprovisioning-datadog specifically**, since nothing has ever looped it before |
| A skill resolving another skill's live conversational gates once, sweep-wide, instead of per-item | **Precedent exists** — release-readiness-checker's `gate-policy.md` (reused pattern, not new to the repo) — **genuinely new instance**: k8s-overprovisioning-datadog's cost-rate confirmation gate has never been resolved this way before |
| `decision_graph`'s exact `appendix.cost` field shape | **Not confirmed** — `decision-graph-schema.md` never formally defines it and no real example graph contains one; only inferred from `cost-estimation.md`'s prose formulas (`freed_cpu_cores`, `freed_giB`, `monthly_savings_total`, `cost_basis`). Treated as **assumed, not guaranteed**, in this skill's own adapter-reading logic — see § Non-goals |
| Squad join for k8s items | **Yes, but genuinely less clean than migration-program-manager's** — `SQUAD_MAP.md`'s `Datadog service` column, with a documented real name mismatch between a graph's `metadata.service` and its own `scope`'s `kube_deployment:` tag; falls back to `ownership.datadog.service_aliases` (squad-map's own existing config field, not invented here) |

## Approach

`cost-optimization-sprint-planner` is a **sweep wrapper that invokes k8s-overprovisioning-datadog once per
in-scope deployment**, sequentially, collecting each run's `decision_graph`, then aggregates:

1. Takes a `sweep_scope` — env + either an explicit deployment list or a namespace-ranking pre-filter
   config (`top_n_namespaces`, `top_n_deployments_per_namespace`) — and a `cost_rate` input (see § Cost-rate
   gate, resolved once, sweep-wide, never per deployment).
2. **Pre-filter (optional but default):** runs the namespace/deployment waste-ranking queries directly
   (the same query definitions k8s-overprovisioning-datadog's own Phase 0b uses, invoked as this skill's
   own Datadog MCP calls — not a delegated k8s-overprovisioning-datadog invocation, since that mode isn't
   documented as standalone) to produce a candidate deployment list ranked by wasted CPU cores, before
   spending a full conversational assessment on every deployment in scope. `sweep_scope.deployments`
   (explicit list) skips this step entirely when provided.
3. **Sweep loop, one k8s-overprovisioning-datadog invocation per deployment, sequential** — modeled on
   backlog-runner's `queue-policy.md` (see § Sweep policy): per-deployment outcome isolation (one
   deployment's `insufficient_metrics` or ambiguous-name gate never aborts the batch), a session-level
   state object layered outside k8s-overprovisioning-datadog's own (which has none to layer over — this
   skill is the first thing that's ever run it more than once in a session), and batch-level stop
   conditions (max deployments, deadline, token budget).
4. **Cost-rate gate resolved once, before the loop starts** — never re-asked per deployment (see
   § Cost-rate gate).
5. Joins each collected `decision_graph` into an `org_rollup_item` (`metric_type: k8s_waste`) per
   [org-rollup-schema.md § 4](../../skill-framework/shared/org-rollup-schema.md#4-adapters-per-source-skill)'s
   already-specified adapter — squad match via `SQUAD_MAP.md`'s `Datadog service` column, falling back to
   `ownership.datadog.service_aliases`.
6. Ranks by `value.monthly_savings_total` descending, grouped by squad; `UNKNOWN` squad group always last,
   same convention as migration-program-manager.
7. Writes **`COST_OPTIMIZATION_SPRINT_REPORT.md`** (human-readable) and
   **`cost_optimization_sprint_rollup.json`** (the computed `org_rollup_item` list, machine-readable) — the
   latter exists for the same reason migration-program-manager's rollup JSON does: so **weekly-squad-digest**
   (item #11, since shipped) can reuse this skill's own computed rollup by reading this file, rather than
   re-running the sweep.

## Cost-rate gate — resolved once, sweep-wide

k8s-overprovisioning-datadog's `cost-estimation.md` has a real, per-run gate: *"Always ask the user for
their effective $/core rate before citing dollar figures"* and *"before applying any fallback rate: ask
the user to confirm their cloud provider, region, and node type."* Unlike the ambiguous-name / insufficient-
metrics gates (which are genuinely per-deployment and get an isolate-and-continue answer, see § Sweep
policy), the cost rate is **the same number for every deployment in one sweep** — asking it once per
deployment would be both wrong (redundant) and the single biggest threat to running this skill unattended,
since the primary ranking key (`monthly_savings_total`) depends on it for every item.

- `cost_rate` (required input, **no default** — same "an operational policy decision this skill won't
  guess" reasoning as migration-program-manager's `staleness_threshold_days`): `{dollars_per_core_month,
  dollars_per_gib_month, cost_basis}` (cloud provider + region + node type, or "CCM" if Cloud Cost
  Management data is available and preferred).
- This skill passes k8s-overprovisioning-datadog's own cost-estimation prompt answer **pre-resolved**, the
  same way release-readiness-checker's `gate-policy.md` reuses pr-gatekeeper's own scripted answers rather
  than re-deriving one — this skill's own `reference/gate-policy.md` documents the exact reused answer for
  every k8s-overprovisioning-datadog gate, cost-rate included.
- When a deployment's own graph reaches COST with CCM data available and CCM disagrees with the supplied
  `cost_rate`, **CCM wins for that one deployment** (k8s-overprovisioning-datadog's own documented
  preference, `cost-estimation.md`) — `cost_rate` is the fallback used only when CCM is empty for that
  deployment, never a forced override of real cost data.

## Sweep policy — the one piece of new logic in this skill

Following backlog-runner's `queue-policy.md` structure exactly (see § Correcting the roadmap description):

- **Session-level state, layered outside k8s-overprovisioning-datadog's own** (which has no cross-run
  state at all — every run is stateless) — `{sweep_run: {started_at, sweep_scope, deployments: [{name,
  namespace, env, outcome, decision_graph_ref}], stopped_reason}}`.
- **Per-deployment outcome isolation:** `insufficient_metrics` (per k8s's own documented "proceed with
  unknown" resolution — never invents a name) and any other single-deployment gate answered per this
  skill's own `reference/gate-policy.md` never aborts the sweep — recorded as a rollup gap, loop continues
  to the next deployment.
- **Batch-level stop conditions, new and distinct from any single deployment's own limits:**
  `max_deployments_per_run`, `deadline`, `session_token_budget` — same three backlog-runner uses, no
  invented fourth condition; **no consecutive-escalation breaker** — unlike loop-task-implementer,
  k8s-overprovisioning-datadog's gates all resolve to a documented non-blocking fallback (§ Gate policy),
  so there is no `ESCALATED`-equivalent outcome that would signal a systemic failure worth an early stop.
- **Always produce a summary regardless of `stopped_reason`** — same as backlog-runner's morning summary.

## Non-goals (explicitly out of scope)

- **No live invocation of squad-map** — same read-only-join principle as migration-program-manager; a
  missing/stale `SQUAD_MAP.md` joins as `squad: UNKNOWN`, never triggers squad-map itself.
- **No changes to k8s-overprovisioning-datadog's own internals, gates, or `decision_graph` schema.**
- **No guaranteed `appendix.cost` shape.** Since `decision-graph-schema.md` never formally defines it and
  no real example graph contains one, this skill's adapter-reading logic must tolerate its absence
  gracefully (fall back to `cost-estimation.md`'s formulas applied to `observations`/`recommendations`
  directly) rather than assume the shape `org-rollup-schema.md` sketches is guaranteed present.
- **No default `cost_rate`.** Same reasoning as migration-program-manager's `staleness_threshold_days` —
  an operational/regional cost decision this skill won't guess.
- **No remediation** (applying a recommended cut) — this skill only plans and ranks; execution stays a
  human/ops decision, same boundary as k8s-overprovisioning-datadog's own `KEEP_CONFIGURATION` /
  read-only stance.
- **No live scheduling infrastructure** — same "agent instructions, not infrastructure" boundary as every
  other item.

## Interface contract

**Input:**

| Field | Required | Notes |
|-------|----------|-------|
| `sweep_scope` | Yes | `{env, deployments?: [...], namespace_prefilter?: {top_n_namespaces, top_n_deployments_per_namespace}}` — **HARD STOP if neither `deployments` nor `namespace_prefilter` is set** |
| `cost_rate` | Yes | `{dollars_per_core_month, dollars_per_gib_month, cost_basis}` — **HARD STOP if absent**, no default |
| `max_deployments_per_run` | No | Default: all in-scope deployments |
| `deadline` / `session_token_budget` | No | Same optional circuit breakers as backlog-runner |

**Output:** `COST_OPTIMIZATION_SPRINT_REPORT.md` + `cost_optimization_sprint_rollup.json` — see
[reference/report-format.md](../../../cost-optimization-sprint-planner/reference/report-format.md).

## Acceptance criteria

- `cost-optimization-sprint-planner/SKILL.md` exists, ≤ 180 lines.
- Given an explicit deployment list, every deployment appears in the rollup — either a real
  `org_rollup_item` or a recorded gap (ambiguous name / insufficient metrics), never silently dropped.
- Given `namespace_prefilter`, the sweep never runs a full k8s-overprovisioning-datadog assessment on more
  than `top_n_namespaces × top_n_deployments_per_namespace` deployments.
- `cost_rate` is asked/resolved exactly once per sweep, never re-derived per deployment, per
  `reference/gate-policy.md`.
- A deployment reaching `insufficient_metrics` or an ambiguous-name gate never aborts the sweep — the next
  deployment still runs.
- `reference/gate-policy.md` covers every live gate k8s-overprovisioning-datadog's own docs document
  (ambiguous service/tag confirmation, insufficient-metrics/name-mismatch, VPA-active-unconfirmed,
  cost-rate confirmation, CCM-empty fallback, manifest-not-found) with a scripted, reused, non-invented
  answer for each — same standard release-readiness-checker's round-1 review enforced for its own
  gate-policy.md.
- `make lint-cost-optimization-sprint-planner` and `make lint-framework` pass; skill wired into root
  README.md, docs/README.md, docs/REPOSITORY.md, `skill-routing.md`, `cross-skill-escalation.md`,
  `prompt-injection.md`, `phase-glossary.md`, `CHANGELOG.md`.

## Implementation plan

1. `cost-optimization-sprint-planner/SKILL.md`, `README.md`, `SETUP.md`, `CHANGELOG.md`, `examples.md`.
2. `workflow/inputs.md` (parse `sweep_scope`, `cost_rate`, `max_deployments_per_run`, `deadline`,
   `session_token_budget`; untrusted-content note) and `workflow/run-sweep.md` (pre-filter step, sweep
   loop invoking k8s-overprovisioning-datadog once per deployment per `reference/gate-policy.md`, join,
   rank, render).
3. `reference/gate-policy.md` (every k8s-overprovisioning-datadog gate, scripted answer, cost-rate
   resolved once) and `reference/sweep-policy.md` (session-level state, per-deployment isolation,
   batch-level stop conditions — modeled on backlog-runner's `queue-policy.md`).
4. `reference/phase-index.md`, `lazy-load-index.md`, `smoke-test.md`, `report-format.md` (normative
   `COST_OPTIMIZATION_SPRINT_REPORT.md` structure + `cost_optimization_sprint_rollup.json` shape).
5. `.cursor/rules/cost-optimization-sprint-planner.mdc`, `.kiro/steering/cost-optimization-sprint-planner.md`.
6. `Makefile`: `install-cost-optimization-sprint-planner` (chains `install-k8s-overprovisioning
   install-squad-map`), `install-claude-cost-optimization-sprint-planner`,
   `lint-cost-optimization-sprint-planner` (SKILL.md line count, workflow frontmatter, dangling links,
   required reference files — **no scripts/pytest**, unlike migration-program-manager, since
   k8s-overprovisioning-datadog itself has no CLI to wrap and this skill is pure markdown-workflow like
   release-readiness-checker), added to `.PHONY`/`lint:` deps and `lint-framework`'s 4 hardcoded per-skill
   loops.
7. Root `README.md`, `docs/README.md`, `docs/REPOSITORY.md`: rows following the established pattern.
8. `docs/skill-framework/shared/skill-routing.md`, `cross-skill-escalation.md`, `prompt-injection.md`,
   `phase-glossary.md`: routing row, escalation rows, mapping subsection (not exempt — has its own Analyze
   logic: the pre-filter ranking, the join, the rank-by-savings).
9. Root `CHANGELOG.md` + `cost-optimization-sprint-planner/CHANGELOG.md`: initial release entry.
10. `make lint` green; deep review pass(es), fixing to 0 issues each round; commit.
