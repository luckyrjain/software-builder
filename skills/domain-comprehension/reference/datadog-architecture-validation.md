# Datadog architecture validation

**Normative.** P2b validates domain architecture against Datadog APM runtime dependencies.

## Purpose

Code (P2) and knowledge graphs show **intent**. Datadog shows **observed** service-to-service calls in prod.
Use both — neither alone is sufficient.

| Gap type | Meaning |
|----------|---------|
| Queue/async hops | May appear in code but not as synchronous APM edges |
| Wrong service name | Repo name ≠ Datadog `service` — check `service_aliases` first |
| Low traffic | Edge exists in code but no spans in window → `CODE_ONLY`, not proof of absence |

## Config

```yaml
architecture_validation:
  enabled: true
  span_window: now-7d
  dependency_depth: 2
  entry_services: []              # default: Tier 0/1 from SQUAD_MAP
  critical_paths:
    - name: <path-label>
      services: [service-a, service-b, service-c]   # ordered happy path
```

## MCP tools

| Tool | When | Notes |
|------|------|-------|
| `search_datadog_service_dependencies` | Every entry service | `direction`: `downstream` + `upstream`; `service` OR `team` (not both) |
| `search_datadog_services` | Confirm service exists | Before dependency lookup |
| `aggregate_spans` | Disputed edges only | `group_by` service / peer; window from config |
| `search_datadog_spans` | Sample trace for one hop | Max 2–3 traces per disputed edge |

**Required:** `telemetry.intent` on every Datadog call.

### Dependency query pattern

```
search_datadog_service_dependencies(
  service: "<datadog-service-name>",
  direction: "downstream",
  telemetry: { intent: "Validate domain downstream architecture for P2b" }
)
```

Paginate with `start_at` if truncated. Build adjacency list for Mermaid `graph LR`.

### Optional span aggregation

For entry service only when dependency API is ambiguous:

```
aggregate_spans(
  query: "service:<entry> ",
  from: "<span_window start>",
  to: "now",
  group_by: ["service", "peer.service"],
  computes: [{ aggregation: "COUNT", field: "*", output: "count" }],
  telemetry: { intent: "Top downstream peers for domain validation" }
)
```

## Entry service resolution

1. `architecture_validation.entry_services` if non-empty
2. Else Datadog service names from `SQUAD_MAP.md` for Tier 0 + Tier 1 repos
3. Apply `ownership.datadog.service_aliases` (repo → service)
4. Skip repos with no Datadog service — note in validation table as `SERVICE_UNKNOWN`

## Critical path validation

For each `critical_paths[].services` ordered list `[S0, S1, …, Sn]`:

- For each `Si → Si+1`, check dependency graph within `dependency_depth`
- **CONFIRMED** — direct downstream edge or 1-hop path in graph
- **PARTIAL** — reachable within depth but not direct
- **BROKEN** — no path within depth
- **UNKNOWN** — service not in Datadog

## Verdicts

Three-way comparison per hop `A → B`:

| Verdict | Code (P2) | Graph | Datadog | Confidence |
|---------|-----------|-------|---------|------------|
| `CONFIRMED` | ✓ | ✓ | ✓ | HIGH |
| `CONFIRMED_RUNTIME` | ✓ | ✗ | ✓ | MEDIUM (graph gap) |
| `RUNTIME_ONLY` | ✗ | ✗ | ✓ | MEDIUM + `⚠️` undocumented runtime hop |
| `CODE_ONLY` | ✓ | ✓ | ✗ | MEDIUM — batch/async/alias/low traffic |
| `GRAPH_CODE_MISMATCH` | ✓ | ✗ | — | From P2 graph gate |
| `SERVICE_UNKNOWN` | — | — | B missing | LOW |
| `UNKNOWN` | — | — | — | Insufficient data |

**Never HIGH** on `RUNTIME_ONLY` or `CODE_ONLY` alone.

## Deliverables

### `{map_file}` § Flow → Runtime validation (Datadog)

1. Summary — `X/Y hops CONFIRMED`, window, entry services queried
2. Validation table (all P2 happy-path hops + critical paths)
3. Mermaid `graph LR` — Datadog dependency subgraph (domain services only)
4. Conflicts — `RUNTIME_ONLY` and `CODE_ONLY` ranked

### `.understand-anything/diagrams/datadog-service-deps.md`

Per entry service: downstream/upstream lists + query timestamp.

## Degraded mode

| Condition | Behavior |
|-----------|----------|
| Datadog ❌ | Section header + "Skipped — Datadog MCP unavailable" |
| Service not in catalog | `SERVICE_UNKNOWN`; try alias; do not invent |
| Empty dependencies | Note zero rows; widen window or flag `CODE_ONLY` vs inactive service |
| Pagination truncated | Document partial graph; continue |

## Honest limitations

State in Mechanical Insights or validation summary:

- APM does not capture Kafka/queue handoffs as sync edges
- Sampling may hide low-volume paths
- `dependency_depth` truncates long chains
