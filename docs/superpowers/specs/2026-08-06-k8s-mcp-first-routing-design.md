# Kubernetes MCP-first routing design

## Goal

Change `k8s-overprovisioning-datadog` from a Datadog-only assessment to capability-by-capability source routing:

1. Prefer a connected Kubernetes MCP for live cluster state and any metrics it can provide.
2. Use Datadog for capabilities the Kubernetes MCP does not expose, including historical telemetry, monitors, incidents, APM, change events, and cost.
3. Use Datadog as the primary telemetry source when no Kubernetes MCP is available.
4. Never invent evidence or recommend a resource change when neither source can provide the minimum evidence for that decision.

The skill remains read-only and recommendation-only.

## Source routing

At DISCOVER_SOURCES start, inventory available tools by capability rather than matching a single server or exact tool name. Record the source profile before RESOLVE and retain provenance for every observation collected later.

| Capability | Preferred source | Fallback | No source behavior |
|---|---|---|---|
| Running Deployment/StatefulSet, resources, replicas, HPA/VPA/KEDA/PDB/ResourceQuota | Kubernetes MCP | Git provider manifest, then user-provided YAML/values | Mark manifest/live-state checks unverified; ask for values when required |
| Current pod status, restarts, OOM, CPU/memory usage when exposed | Kubernetes MCP | Datadog | Mark affected observations missing |
| Seven-day utilization, fleet p95/peak, throttling, Kafka lag | Kubernetes MCP only if equivalent history and aggregation exist | Datadog | Defer the affected dimension; do not size from a point-in-time sample |
| Active incidents, monitors, APM/SLO, deployment/change history | Datadog | Kubernetes events only where they are equivalent | Mark optional signals missing; apply existing safety/confidence gates |
| Cloud cost | Datadog CCM | None | Skip cost output and report resource-only savings |

When both sources provide the same signal, retain both observations, use Kubernetes MCP for live-state truth, use Datadog for historical truth, and surface material disagreement as `conflicting_signals`.

## Degraded modes

- Kubernetes MCP absent, unreachable, or unauthorized: continue with Datadog. The assessment is not blocked solely because Kubernetes MCP is missing.
- Kubernetes MCP lacks one capability: fall back only that capability to Datadog.
- Datadog absent while Kubernetes MCP has sufficient equivalent historical metrics: continue with Kubernetes MCP and mark Datadog-only capabilities unavailable.
- Datadog absent and Kubernetes MCP exposes live state only: provide live-state observations, but block or defer sizing decisions that require historical evidence.
- Both sources insufficient: emit `STOP_REASON: insufficient_metrics` and a blocked assessment with attempted sources and missing capabilities.
- Authentication failures are source-scoped. A failure from one source does not halt collection from the other.

## Documentation changes

Update the skill frontmatter/body, DISCOVER_SOURCES/COLLECT workflows, MCP capability matrix, setup
guide, README, examples, and stop-reason wording so none states that Datadog is always required. Keep
shared phase/error guidance and cross-skill wrappers aligned with the same source-scoped fallback policy;
wrappers may retain a direct Datadog dependency only for a capability they invoke themselves, such as
cost sweep namespace pre-filter discovery. Keep the existing skill directory name for compatibility;
clarify in documentation that the runtime policy is Kubernetes MCP-first despite the legacy name.

## Verification

Add pressure/routing scenarios covering:

1. Kubernetes MCP with complete capabilities: Kubernetes supplies live state; Datadog supplies only unique historical/operational capabilities.
2. Kubernetes MCP with partial capabilities: missing capabilities fall back individually to Datadog.
3. No Kubernetes MCP: Datadog assessment continues.
4. No Datadog with history-capable Kubernetes MCP: assessment continues with explicit gaps.
5. Live-state-only Kubernetes MCP and no Datadog: sizing is deferred.
6. Conflicting live versus historical evidence: preserve both and trigger the existing conflict gate.
7. Neither source sufficient: blocked assessment; no recommendation.

Add repository contract tests for living documentation so phase order, invariant range, inherited
prerequisites, wrapper auth behavior, and delivery-path safety cannot silently drift. Preserve older
dated specifications, plans, and changelogs as historical records.
