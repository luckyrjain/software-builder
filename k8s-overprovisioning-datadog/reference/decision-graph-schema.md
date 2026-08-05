# Decision graph schema (v3.0)

**Primary artifact.** Markdown/JSON are render outputs — never the source of truth.

```text
schema_version: 3
skill_version: v3.0
```

Full example: [decision-graph.example.yaml](decision-graph.example.yaml). Invariants: [invariants.md](invariants.md).

## Root

| Field | Type | Required |
|-------|------|----------|
| `schema_version` | `3` | yes |
| `skill_version` | string | yes |
| `metadata` | object | yes |
| `assessment` | object | yes |
| `observations` | array | yes |
| `evidence` | array | yes |
| `decisions` | array | yes |
| `recommendations` | array | yes |
| `telemetry` | object | yes |
| `assumptions` | array | no |
| `contradictions` | array | no |
| `interpretations` | array | no |
| `trends` | array | no |
| `stop_reasons` | array | no |
| `decision_history` | object | no |
| `appendix` | object | no |
| `invariant_violations` | array | no — populated only when validation fails |

## Typed objects

### Observation

```yaml
id: OBS_CPU_P95_FLEET          # OBS_* required
value: 152                       # number or null if missing
unit: percent                    # cores | percent | giB | count | msgs_per_s | ...
scope: pod                       # pod | deployment | consumer_group | ...
window: 7d
quality: measured                # measured | inferred | missing | unknown | not_applicable
```

Values live **only** here. Derived observations use `OBS_DERIVED_*` with optional `formula` field.

### Evidence

```yaml
id: EVID_CPU_P95_FLEET
observation_id: OBS_CPU_P95_FLEET   # exactly one OBS_* per EVID_*
source: datadog                     # required unless quality: missing
metric: kubernetes.pod.cpu.usage.dist
aggregation: p95.dist
window: 7d
scope: pod-scoped
quality: measured
weight: critical                    # critical | high | medium | low
```

No `value` field on evidence.

### Decision

```yaml
id: DEC_CPU_REQUEST
status: BLOCKED                     # ALLOW | BLOCKED | DEFER
supports: [OBS_CPU_P95_FLEET, OBS_CPU_MAX_POD]
blocking: [OBS_CPU_P95_FLEET]
missing: [OBS_CPU_THROTTLE_RATE]
reason: fleet_p95_above_trim_threshold   # machine slug from thresholds/stop-reasons
explanation: Fleet p95 exceeds sizing threshold.
```

### Recommendation

```yaml
id: REC_CPU_KEEP
priority: P0
status: BLOCKED                     # READY | BLOCKED | DEFERRED | REJECTED | COMPLETED
depends_on:
  decisions: [DEC_CPU_REQUEST]
  observations: [OBS_CPU_P95_FLEET, OBS_CPU_THROTTLE_RATE]
  assumptions: [ASSUME_P95_REPRESENTATIVE]
recommendation_confidence:
  value: 0.9
  band: Very High
  factors:
    support_completeness: 1.0
    support_quality: 1.0
    contradiction_resolution: 1.0
    telemetry_availability: 0.9
risk:
  likelihood: Low
  impact: Low
  score: Low
  residual: Low
# delivery_pointer — required when status: READY on actionable change recs (INV-12); omit on KEEP/OBSERVE
```

Actionable **READY** change example (`REC_CPU_REDUCE`, `REC_MEMORY_INCREASE`, etc.):

```yaml
id: REC_CPU_REDUCE
priority: P1
status: READY
depends_on:
  decisions: [DEC_CPU_REQUEST]
  observations: [OBS_CPU_P95_FLEET, OBS_CPU_THROTTLE_RATE]
delivery_pointer:
  path: helm/payment/values.yaml
  field: resources.requests.cpu
  format: helm_values              # helm_values | kustomize | manifest | terraform | gitops
  verified: true                   # false when path inferred or unverified
recommendation_confidence:
  value: 0.85
  band: High
  factors:
    support_completeness: 0.9
    support_quality: 0.9
    contradiction_resolution: 1.0
    telemetry_availability: 0.8
risk:
  likelihood: Low
  impact: Medium
  score: Low
  residual: Low
```

Rendered in the Human Report as **Where to apply** — [templates/recommendations.md](../templates/recommendations.md#delivery-pointer-change-recs-only).

### Assessment

```yaml
final_decision: KEEP_CONFIGURATION    # KEEP_CONFIGURATION | TRIM_RESOURCES | SCALE_UP | DEFER
severity: WARNING                       # INFO | WARNING | CRITICAL
severity_reason: replica_optimization_blocked
review_after: 14d
assessment_confidence:
  value: 0.9
  band: Very High
  factors:
    evidence_completeness: 0.9
    evidence_quality: 0.9
    contradiction_resolution: 1.0
    telemetry_availability: 0.9
  arithmetic: "0.35×0.9 + 0.35×0.9 + 0.15×1.0 + 0.15×0.9 = 0.915 → 0.9"
```

Confidence formulas: [confidence-formula.md](confidence-formula.md).

## ID namespaces

[id-namespaces.md](id-namespaces.md) — `OBS_`, `EVID_`, `DEC_`, `REC_`, `ASSUME_`.

## Graph persistence and `decision_history`

`decision_history` stores a reference to the prior graph when this is a re-assessment (e.g. verifying that a right-sizing change applied 7d ago is holding).

```yaml
decision_history:
  prior_graph_path: /path/to/prior_graph.yaml
  prior_assessment_date: 2026-06-22
  prior_final_decision: TRIM_RESOURCES
  prior_confidence: 0.9
  delta_summary: "CPU requests reduced from 500m → 300m; observing p95 stability"
```

**How to populate:**

1. **Locate prior graph** — check in order: user-provided path, session scratchpad, `$PWD/rca_graphs/<service>-latest.yaml`. If none found, omit `decision_history` and note *"No prior graph found — first assessment."*
2. **Extract prior fields** — set `prior_final_decision`, `prior_confidence`, and `prior_assessment_date` from the prior graph's `assessment` block.
3. **Write `delta_summary`** — one sentence describing what changed since the prior run (e.g. which requests were adjusted, current p95 vs prior).

**When absent:** BUILD_GRAPH proceeds normally. The `PostChangeVerification` section in the Human Report is omitted when no prior graph is available.

## Pipeline

```
COLLECT → NORMALIZE → REASON → VALIDATE → BUILD_GRAPH → VALIDATE_INVARIANTS → RENDER
```

Build: [workflow/build-graph.md](../workflow/build-graph.md). Render: [render/README.md](../render/README.md).
