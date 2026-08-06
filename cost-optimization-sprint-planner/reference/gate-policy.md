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
| Ambiguous service→tag confirmation | [resolve-service.md](../../k8s-overprovisioning-datadog/workflow/resolve-service.md): *"Confirm with `get_datadog_metric_context`... If ambiguous, ask the user **or default `env:production` when present**"* | k8s's own documented default is specifically **production** — rely on it only when `sweep_scope.env == production`. For any other `sweep_scope.env` (e.g. `staging`), k8s's own fallback doesn't cover it; treat a still-ambiguous tag the same as the next row ("proceed with unknown") rather than silently trusting an arbitrary env value as if it were the documented default |
| Service name mismatch (`insufficient_metrics` path) | [resolve-service.md](../../k8s-overprovisioning-datadog/workflow/resolve-service.md): *"Ask the user to confirm the correct deployment name... Only emit `insufficient_metrics` after ≥2 tag strategies and user confirmation (**or explicit "proceed with unknown"**)"* | **"Proceed with unknown."** k8s's own documented non-guessing alternative to a live ask — never invent a deployment/namespace name. Recorded in the sweep as a per-deployment gap (see [reference/sweep-policy.md](sweep-policy.md)), never a sweep-wide stop |
| VPA active, recommendation empty | [collect-metrics.md](../../k8s-overprovisioning-datadog/workflow/collect-metrics.md): *"`STOP_REASON: vpa_active_unconfirmed` — defer cuts until recommendation stabilizes"* | Accept k8s's own deferred-decision graph as-is — a deployment that hits this still produces a real `decision_graph` (with `recommendations[].status: DEFERRED` on that dimension), not a sweep gap; `value.monthly_savings_total` reflects only the dimensions that weren't deferred |
| CCM empty | [cost-analysis.md](../../k8s-overprovisioning-datadog/workflow/cost-analysis.md): *"CCM empty → resource-only; no fallback $ without user confirmation"* | This skill's pre-resolved `cost_rate` **is** that confirmation, supplied up front — CCM-empty deployments fall through to `cost_rate` per the § Cost-rate gate above, never re-prompted |
| Non-AWS CCM metric path | [queries.md](../../k8s-overprovisioning-datadog/queries.md): *"`aws.cost.*` is AWS-specific — for GCP/Azure ask the user for their CCM metric paths"* | Never asked per deployment, and never inferred by parsing `cost_rate.cost_basis`'s free text — driven by the **structured** `cost_rate.provider` field (see [workflow/inputs.md](../workflow/inputs.md)) instead. When `provider != aws`, skip CCM entirely for the whole sweep and use the pre-resolved `cost_rate` fallback for every deployment, unless the caller separately supplies GCP/Azure CCM metric paths as part of `cost_rate` up front |
| Manifest lookup (drift / VPA / PDB / ResourceQuota) not found | [SETUP.md](../../k8s-overprovisioning-datadog/SETUP.md): *"stop and ask the user for the Deployment/Helm values path... Never block the analysis — if git MCP is unavailable or lookup fails, ask the user to paste `resources.requests`/`resources.limits`/`replicas` and continue"* | Skip manifest verification for that one deployment rather than pausing the sweep to ask for a path or pasted values — the resulting graph proceeds with `delivery_pointer` unverified (k8s's own "never block the analysis" fallback), noted in that deployment's rollup item, never a sweep-wide stop |

A deployment that resolves to `insufficient_metrics` this way is recorded in
`COST_OPTIMIZATION_SPRINT_REPORT.md` **as a sweep gap, honestly** — not silently upgraded to a real
waste finding (which would fabricate a recommendation k8s never made) and not treated as `$0` savings
(which would hide a real gap). See [reference/report-format.md](report-format.md).

## Sweep-wide stop, not per-deployment isolation — the auth failure gate

**k8s's own text** ([stop-reasons.md](../../k8s-overprovisioning-datadog/workflow/stop-reasons.md)):
`auth_failure` is **Critical** severity, effect **"Halt — no metrics,"** next action **"Run ddsetup /
ddconfig"** — grouped with `insufficient_metrics` in k8s's own "return blocked report, do not collect
further" branch.

**This skill's scripted answer:** unlike every gate above, `auth_failure` is **not** isolated to one
deployment and continued past — a Datadog MCP auth failure on one deployment means every remaining
candidate in the sweep will hit the identical failure, since it's an environment-level problem (expired
credentials, misconfigured MCP), not a per-deployment data-quality issue. The first `auth_failure`
outcome **stops the sweep immediately** (`stopped_reason: AUTH_FAILURE`, per
[reference/sweep-policy.md § 5](sweep-policy.md#5-session-level-stop-conditions-circuit-breakers)) rather
than being recorded as a per-deployment gap and continuing — running the rest of the candidate list
against a broken credential would only burn the session's time/token budget producing nothing. Report
k8s's own remediation pointer ("run ddsetup/ddconfig") in the sweep report's Notes section.
