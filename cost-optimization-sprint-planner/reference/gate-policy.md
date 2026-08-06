# Gate policy — k8s-overprovisioning-datadog (normative)

**Every gate k8s-overprovisioning-datadog's own docs document, with a scripted answer reused from its own
documented fallback — never an invented one.** Same standard release-readiness-checker's round-1 review
enforced for its own `gate-policy.md`: read the wrapped skill's actual text, don't assume a gate-free mode
exists.

## Cost-rate gate — resolved once, sweep-wide, before the loop starts

**k8s's own text** ([cost-estimation.md](../../k8s-overprovisioning-datadog/cost-estimation.md)):
*"Always ask the user for their effective $/core rate before citing dollar figures"*; *"before applying
any fallback rate: ask the user to confirm their cloud provider, region, and node type."*

**This skill's scripted answer:** never asked per deployment. `cost_rate` (this skill's own required
input, see [workflow/inputs.md](../workflow/inputs.md)) is resolved **once**, before the sweep loop
starts, and supplied to every k8s-overprovisioning-datadog invocation as the pre-confirmed fallback rate
— the same rate every deployment in one sweep should use, since re-deriving it per deployment would be
both redundant and the single biggest threat to running this skill unattended (the primary ranking key,
`monthly_savings_total`, depends on it). When a deployment's own graph reaches COST with real CCM data
available, **CCM wins for that one deployment** — `cost_rate` is the fallback used only when CCM is empty
for that deployment, per k8s's own documented preference, never a forced override of real cost data. Cite
`cost_rate.cost_basis` verbatim wherever k8s's own report would normally ask the user to confirm
provider/region/node type.

## Per-deployment gates — answered per k8s's own documented fallback, isolated per deployment

| Gate | k8s's own text | This skill's scripted answer |
|---|---|---|
| Ambiguous service→tag confirmation | [resolve-service.md](../../k8s-overprovisioning-datadog/workflow/resolve-service.md): *"Confirm with `get_datadog_metric_context`... If ambiguous, ask the user **or default `env:production` when present**"* | Rely on the documented default — resolve with `sweep_scope.env` (always supplied, see `workflow/inputs.md`) when present; only if genuinely still ambiguous with no matching env scope does this become the next row |
| Service name mismatch (`insufficient_metrics` path) | [resolve-service.md](../../k8s-overprovisioning-datadog/workflow/resolve-service.md): *"Ask the user to confirm the correct deployment name... Only emit `insufficient_metrics` after ≥2 tag strategies and user confirmation (**or explicit "proceed with unknown"**)"* | **"Proceed with unknown."** k8s's own documented non-guessing alternative to a live ask — never invent a deployment/namespace name. Recorded in the sweep as a per-deployment gap (see [reference/sweep-policy.md](sweep-policy.md)), never a sweep-wide stop |
| VPA active, recommendation empty | [collect-metrics.md](../../k8s-overprovisioning-datadog/workflow/collect-metrics.md): *"`STOP_REASON: vpa_active_unconfirmed` — defer cuts until recommendation stabilizes"* | Accept k8s's own deferred-decision graph as-is — a deployment that hits this still produces a real `decision_graph` (with `recommendations[].status: DEFERRED` on that dimension), not a sweep gap; `value.monthly_savings_total` reflects only the dimensions that weren't deferred |
| CCM empty | [cost-analysis.md](../../k8s-overprovisioning-datadog/workflow/cost-analysis.md): *"CCM empty → resource-only; no fallback $ without user confirmation"* | This skill's pre-resolved `cost_rate` **is** that confirmation, supplied up front — CCM-empty deployments fall through to `cost_rate` per the § Cost-rate gate above, never re-prompted |
| Manifest lookup (drift / VPA / PDB / ResourceQuota) not found | [SETUP.md](../../k8s-overprovisioning-datadog/SETUP.md): *"stop and ask the user for the Deployment/Helm values path... Never block the analysis — if git MCP is unavailable or lookup fails, ask the user to paste `resources.requests`/`resources.limits`/`replicas` and continue"* | Skip manifest verification for that one deployment rather than pausing the sweep to ask for a path or pasted values — the resulting graph proceeds with `delivery_pointer` unverified (k8s's own "never block the analysis" fallback), noted in that deployment's rollup item, never a sweep-wide stop |

A deployment that resolves to `insufficient_metrics` this way is recorded in
`COST_OPTIMIZATION_SPRINT_REPORT.md` **as a sweep gap, honestly** — not silently upgraded to a real
waste finding (which would fabricate a recommendation k8s never made) and not treated as `$0` savings
(which would hide a real gap). See [reference/report-format.md](report-format.md).
