# COST_OPTIMIZATION_SPRINT_REPORT.md + cost_optimization_sprint_rollup.json format

**Normative.** The exact structure [workflow/run-sweep.md](../workflow/run-sweep.md) § 5 must produce.

## `COST_OPTIMIZATION_SPRINT_REPORT.md` structure (order fixed)

```markdown
# Cost optimization sprint — <date>

**Sweep config:** `<deployments list>` or `top <top_n_namespaces> namespaces × top
<top_n_deployments_per_namespace> deployments` · **Cost basis:** `<cost_rate.cost_basis>` ·
**Deployments assessed:** `<N of M candidates>` · **Stopped reason:** `<stopped_reason>` (one of
`COMPLETED` / `MAX_DEPLOYMENTS_REACHED` / `DEADLINE_REACHED` / `TOKEN_BUDGET_EXHAUSTED` / `AUTH_FAILURE` /
`SCOPE_EXHAUSTED`, per [reference/sweep-policy.md § 5](../reference/sweep-policy.md#5-session-level-stop-conditions-circuit-breakers)
— never a free-text substitute)

## <squad name>

| Service | Monthly savings | Status | Priority | Confidence | Notes |
|---------|------------------|--------|----------|------------|-------|
| <service> | `$<value.monthly_savings_total>` | <recommendations[].status> | <priority or —> | <squad_confidence> | <"estimated (fallback rate)" when appendix.cost was absent and cost_rate was used, or "CCM" when real cost data was used, or "deferred — VPA active, recommendation unconfirmed" per gate-policy.md> |

<Sorted by monthly savings descending. A `KEEP_CONFIGURATION` deployment still gets a row, `$0`, sorted
to the bottom — never omitted just because it wasn't overprovisioned.>

<Repeat per squad, in any stable order. Squads with zero assessed deployments omit the section entirely
(never render an empty table), but a squad with at least one appears.>

## UNKNOWN squad

<Same table, for every service that couldn't be joined to a squad — always rendered last, never silently
merged into a named squad's section.>

## Sweep gaps

| Deployment | Outcome | Notes |
|------------|---------|-------|
| <deployment> | `INSUFFICIENT_METRICS` \| `AMBIGUOUS_UNRESOLVED` \| `AUTH_FAILURE` | <tag strategies attempted, per gate-policy.md's "proceed with unknown" resolution, or — for `AUTH_FAILURE` — whether direct namespace pre-filter authentication failed or all viable sources were unauthorized, the matching remediation, and a note that the sweep stopped here> |

## Notes

<Any candidate never reached because of a session-level stop condition (§ Sweep config's `stopped_reason`
above) — listed by name, never silently absent from the report; any deployment where CCM disagreed with
the supplied `cost_rate` and CCM was used instead; any deployment whose squad match came from the
`ownership.datadog.service_aliases` reverse lookup (per
[workflow/run-sweep.md § 3](../workflow/run-sweep.md#3-join-each-decisiongraph-into-an-orgrollupitem))
rather than a direct `Datadog service` column match — call out its `MEDIUM` confidence explicitly; any
deployment whose `squad_confidence` is `LOW` or `UNKNOWN`, named individually, not just left to the
table's Confidence column.>
```

## `cost_optimization_sprint_rollup.json` shape

A flat JSON array of `org_rollup_item` objects (per
[org-rollup-schema.md](../../docs/skill-framework/shared/org-rollup-schema.md)'s `k8s_waste` adapter),
`metric_type: "k8s_waste"` for every entry. Written so
[weekly-squad-digest](../../weekly-squad-digest/SKILL.md) can read this file directly instead of
re-running the sweep.

## Rules

- **Every candidate deployment appears somewhere in the report** — either a ranked row in a squad section
  or a row in Sweep gaps; never silently dropped for hitting a gate or for not being overprovisioned.
- **k8s-overprovisioning-datadog's own verdicts are surfaced as-is** — this skill never re-labels a
  `READY`/`BLOCKED`/`DEFERRED`/`REJECTED`/`COMPLETED` recommendation status or invents its own threshold
  on top of it.
- **`monthly_savings_total` is honestly labeled** — `appendix.cost` (when present) is real per-graph cost
  data; a value derived from this skill's own `cost_rate` fallback is labeled "estimated (fallback rate)",
  never presented identically to a CCM-backed figure. This mirrors k8s-overprovisioning-datadog's own
  cost-estimation.md labeling convention, reused here rather than inventing a new one.
- **Ranking is fixed**: sort by `value.monthly_savings_total` descending within each squad group;
  `squad: UNKNOWN` group always rendered last.
- **A sweep-gap deployment is never assigned a `$0` savings row** — `$0` means k8s-overprovisioning-datadog
  actually assessed it and found nothing to cut; a gap means it was never actually assessed. Conflating
  the two would hide real coverage gaps behind what looks like a clean bill of health.
- **`evidence_ref` points at a real file this skill itself wrote** — k8s-overprovisioning-datadog's own
  JSON renderer only ever produces one hardcoded filename (`decision-graph.json`, requested but never
  renamed by the renderer itself); this skill's own workflow moves/renames that file to
  `decision-graph-<deployment>.json` immediately after each invocation returns (see
  [workflow/run-sweep.md § 2](../workflow/run-sweep.md#2-loop-k8s-overprovisioning-datadog-once-per-candidate-sequentially)) —
  `evidence_ref` points at the result of that move, never an assumed path k8s-overprovisioning-datadog
  itself produced directly.
- **`squad_confidence` is carried through, never dropped** — `HIGH`/`MEDIUM`/`LOW` from a direct
  `SQUAD_MAP.md` row, `MEDIUM` from a `service_aliases` reverse-lookup match, `UNKNOWN` when neither
  resolves. A LOW/UNKNOWN match is a real signal a consuming reader should be able to see, not just data
  silently present in the JSON — see the Confidence column and Notes above.
