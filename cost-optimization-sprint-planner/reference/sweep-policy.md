# Sweep policy (normative)

**The one piece of genuinely new logic in this skill.** Everything about assessing one deployment is
k8s-overprovisioning-datadog's own. This file defines the session-level concerns
k8s-overprovisioning-datadog has no concept of at all (it has **no cross-run state** — every conversational
run is stateless; this is the first skill in this repo that's ever run it more than once in a session) and
is modeled directly on [backlog-runner/reference/queue-policy.md](../../backlog-runner/reference/queue-policy.md)
— not loop-task-implementer's own orchestrator, which works exactly one task at a time and has no
multi-item batch loop of its own (see the
[design spec § Correcting the roadmap description](../../docs/superpowers/specs/2026-08-05-cost-optimization-sprint-planner-design.md#correcting-the-roadmap-description-before-designing-against-it)).

## 1. Session-level state (new — layered outside k8s-overprovisioning-datadog, which has none)

```yaml
sweep_run:
  started_at: "<ISO-8601>"
  sweep_scope: { ... }        # echoed verbatim from workflow/inputs.md
  cost_rate: { ... }          # echoed verbatim, resolved once per § Cost-rate gate
  deployments:
    - name: "<deployment>"
      namespace: "<namespace>"
      env: "<env>"
      outcome: PENDING | ASSESSED | INSUFFICIENT_METRICS | AMBIGUOUS_UNRESOLVED
      decision_graph_ref: null   # path to the produced decision_graph YAML, when ASSESSED
  stopped_reason: null          # MAX_DEPLOYMENTS_REACHED | DEADLINE_REACHED | TOKEN_BUDGET_EXHAUSTED | SCOPE_EXHAUSTED
```

## 2. Candidate deployment list

1. **`sweep_scope.deployments` set → use it verbatim**, no pre-filter query runs at all.
2. **Else `sweep_scope.namespace_prefilter` set → run the namespace/deployment waste-ranking queries
   directly** (the same query definitions k8s-overprovisioning-datadog's own Phase 0b uses —
   [queries.md § Namespace / cluster ranking](../../k8s-overprovisioning-datadog/queries.md#namespace-cluster-ranking-scalar-7d),
   invoked as this skill's own Datadog MCP calls, never a delegated k8s-overprovisioning-datadog
   invocation asked to "just rank and stop" — that mode isn't documented as supported, see the design
   spec's § Correcting the roadmap description):
   - Rank namespaces by wasted CPU cores (`(reserved − used) / reserved × 100`), take the top
     `top_n_namespaces`.
   - Within each of those namespaces, rank deployments by wasted cores, take the top
     `top_n_deployments_per_namespace`.
   - The resulting candidate list is **at most** `top_n_namespaces × top_n_deployments_per_namespace`
     deployments — never more, even if more namespaces/deployments show waste.
3. Apply `max_deployments_per_run` (if set) as a final cap on the candidate list, taking the
   highest-waste-ranked entries first when the pre-filter produced a ranking; taking list order when
   `sweep_scope.deployments` was explicit (caller's own order is authoritative, this skill doesn't
   re-rank a caller-supplied list before assessing it).

## 3. Invoking k8s-overprovisioning-datadog — one deployment per invocation, sequential

**Each candidate deployment is a separate k8s-overprovisioning-datadog invocation, sequential, not a
single "assess all these deployments" request.** k8s-overprovisioning-datadog has no documented
multi-deployment natural-language pattern to defer to in the first place (unlike loop-task-implementer,
which backlog-runner deliberately avoids for a different reason — see queue-policy.md's own §3); this
skill's own sweep loop is simply the only way to cover more than one deployment. Pass each deployment's
name, namespace (when known from the pre-filter), and `sweep_scope.env` exactly as if a human had typed
"assess `<deployment>` in `<env>`" — no invented trailing directives (same lesson as
`pr-gatekeeper`/`incident-triage-agent`/`backlog-runner`: don't invent unverified invocation grammar).
Every live gate that invocation might hit is answered per
[reference/gate-policy.md](gate-policy.md) — never re-derived here.

## 4. The continuation decision

| Deployment outcome | This skill's action |
|---|---|
| Real `decision_graph` produced (any `assessment.final_decision`, including `KEEP_CONFIGURATION`) | `outcome: ASSESSED` — **expected, normal outcome, always joined into the rollup** (per org-rollup-schema.md's own "never omit a rollup item just because a deployment wasn't overprovisioned" rule) — continue to the next candidate |
| `insufficient_metrics` after gate-policy's "proceed with unknown" still yields nothing | `outcome: INSUFFICIENT_METRICS` — recorded as a sweep gap (see [reference/report-format.md](report-format.md)), **continue to the next independent deployment**, never abort the sweep |
| Ambiguous name/tag with no `sweep_scope.env` match and no resolvable default | `outcome: AMBIGUOUS_UNRESOLVED` — same as above, recorded as a gap, continue |

There is no `ESCALATED`-equivalent outcome and therefore **no consecutive-failure circuit breaker** —
unlike loop-task-implementer's gates (which can genuinely fail in a way that signals a systemic problem
worth stopping for), every k8s-overprovisioning-datadog gate this skill can hit resolves to a documented,
non-blocking fallback per `reference/gate-policy.md`. A run of `INSUFFICIENT_METRICS` outcomes signals
noisy Datadog tagging for those specific deployments, not a reason to stop assessing the rest of the
sweep.

## 5. Session-level stop conditions (circuit breakers)

Stop **starting new deployment assessments** — an in-flight assessment always finishes, never aborted
mid-run — when any of:

| Condition | `stopped_reason` |
|-----------|-------------------|
| `max_deployments_per_run` deployments attempted this run | `MAX_DEPLOYMENTS_REACHED` |
| Wall-clock reaches `deadline` (if set) | `DEADLINE_REACHED` |
| `consumed_tokens` reaches `session_token_budget` (if set) | `TOKEN_BUDGET_EXHAUSTED` |
| Candidate list (after § 2's cap) is exhausted | `SCOPE_EXHAUSTED` |

## 6. Report, always produced

Regardless of `stopped_reason`, always render
[`COST_OPTIMIZATION_SPRINT_REPORT.md`](report-format.md) — a sweep that stops early on
`MAX_DEPLOYMENTS_REACHED`/`DEADLINE_REACHED`/`TOKEN_BUDGET_EXHAUSTED` still reports every deployment it
did assess, ranked, plus an explicit note of how many candidates were never reached and why (never a
silent partial sweep presented as complete).
