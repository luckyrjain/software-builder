---
workflow_version: 3.5
phase: stop-reasons
produces: {stop_reason_registry: object}
consumes:
  required: {auth_status: string, validated_signals: object}
  optional: {}
  conditional: {}
---

# Stop reasons

Canonical halt/block registry. **Priority 0** — check before recommendations or cost.

## Severity

| Level | Examples | Report placement |
|-------|----------|------------------|
| **Critical** | `auth_failure` (all viable sources), `insufficient_metrics`, `manifest_drift` | Executive summary + Finding #1 |
| **High** | `oom_kills`, `throttle_high`, `firing_required_monitor`, `active_incident`, `metrics_stale_redeploy`, `projection_failed` | Blockers (P0) |
| **Medium** | `missing_fleet_p95`, `missing_kafka_lag`, `conflicting_signals` | Decision objects |
| **Low** | `missing_dashboard`, `pdb_unverified` | Observations; cap confidence |

## STOP_REASON registry

| STOP_REASON | Severity | Effect | Next action |
|-------------|----------|--------|-------------|
| `auth_failure` | Critical | **Halt** only when every viable source for required evidence is unauthorized | Report attempted sources and auth failures; configure one usable source |
| `insufficient_metrics` | Critical | **Halt** — combined sources cannot support a sizing verdict | Report attempted sources, scopes, and missing capabilities; label **Unknown** |
| `ambiguous_unresolved` | Critical | **Halt** — service→workload/environment identity is ambiguous (multiple candidates, multiple `env` values) and no ask-question tool is available to resolve it (unattended caller) | Report the candidates observed; never silently default to `env:production` or any other environment — see [resolve-service.md § Ambiguous resolution](resolve-service.md#ambiguous-resolution-no-silent-production-default) |
| `manifest_drift` | Critical | **Block optimization** (P0) | Finding #1; cap rec confidence ≤ 0.50 |
| `vpa_active_unconfirmed` | High | Drift may be expected | Confirm VPA bounds before flagging drift |
| `deployment_total_mismatch` | High | Block waste/cost | Reconcile per-pod × replicas |
| `scope_ambiguous` | High | Block sizing | Pin `kube_container_name` |
| `throttle_high` | High | Block CPU trim | Throttle > 5% (7d avg) |
| `oom_kills` | High | Block memory trim | Increase request/limit |
| `restarts_elevated` | High | Block downsizing | Per [thresholds.md](../thresholds.md#container-restarts) |
| `firing_required_monitor` | High | Block affected dimension | Cap confidence ≤ 0.30 |
| `active_incident` | High | **Block all downsizing** | Wait for incident resolution |
| `metrics_stale_redeploy` | High | Block cuts on stale window | Narrow to post-redeploy window or wait 7d |
| `projection_failed` | High | Block affected dimension cut | Proposed request < measured p95/peak |
| `missing_fleet_p95` | Medium | Block CPU trim | Defer or use max-per-pod conservatively |
| `missing_kafka_lag` | Medium | Block replica cut | Instrument lag per group |
| `missing_pdb` | Medium | Cap replica confidence | Ask user for PDB |
| `missing_partition_distribution` | Medium | Block replica cut | Validate assignment |
| `missing_keda_metrics` | Medium | Block replica verdict | Only for confirmed KEDA workloads (`OBS_KEDA_SCALER_ACTIVE`) missing scaler metrics — see [replica-analysis.md](replica-analysis.md#keda) |
| `conflicting_signals` | Medium | **No cut recommendations**; cap assessment confidence at **0.60** | Contradiction table — must show Resolved or Unresolved |
| `scale_down_policy_lag` | Medium | Do not read as overscaled | Note HPA behavior |
| `optimization_not_feasible` | Medium | **Skip cost** | `cost_skipped: <reason>` |

**GitOps note (`manifest_drift`):** ArgoCD/Flux-managed deployments may show transient manifest drift
during sync. Confirm GitOps sync state (healthy, in-sync) before treating drift as Finding #1 — do not
block optimization on a reconciling or out-of-sync controller lag alone.

## When to stop vs continue

An authentication or capability failure from **one source** never halts collection from the **other source**.
Record it in the source profile and continue. Emit `auth_failure` only when authorization
prevents every viable source from supplying required evidence. Emit `insufficient_metrics` when all
attempted sources together still leave required historical or configuration capabilities missing.

```
IF STOP_REASON in {auth_failure, insufficient_metrics}
  → Return blocked report. Do not collect further or recommend.

IF any Critical STOP_REASON
  → Continue observation for context, but no optimization recommendations.

IF any High STOP_REASON on a dimension
  → That dimension: status BLOCKED. Other dimensions may still evaluate.

IF conflicting_signals (Unresolved)
  → No cut recommendations. Observe-first only. Assessment confidence ≤ 0.60.

IF optimization_not_feasible OR any Critical blocker on primary ask
  → Skip [cost-analysis.md](cost-analysis.md) unless user explicitly asked for cost anyway.
```

## Evidence quality labels

Use explicitly — never infer. See [reference/evidence-schema.md](../reference/evidence-schema.md).

| Label | Meaning |
|-------|---------|
| **missing** | Metric not collected / query not attempted |
| **unknown** | Collected but inconclusive |
| **not_applicable** | Workload excludes this metric |
| **Insufficient evidence** | Partial coverage (e.g. 3/8 consumer groups) — use in Missing evidence on decisions |
