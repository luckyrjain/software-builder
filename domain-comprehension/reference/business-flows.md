# Business flows (normative)

**Artifact:** `BUSINESS_FLOWS.md`. **Minimum:** 3 journeys. **Produced in:** P2; cross-checked P2b.

Journeys come from `domain-config.yaml` `context.product_lines` or domain pack. Each journey is a
**critical business flow** — more than a single critical path hop list.

## Per-journey template

```markdown
### <Journey name>

| Field | Value |
|-------|-------|
| Trigger | <user action, schedule, webhook> |
| Entry service | <repo/service + evidence> |
| Terminal condition | <success / failure / manual review> |
| Overall confidence | HIGH \| MEDIUM \| LOW \| UNKNOWN |

#### Services (ordered)
| Step | Service | Sync/async | Exercise | Evidence |
|------|---------|------------|----------|----------|

#### Events
| Event | Producer | Consumers | Exercise | Evidence |
|-------|----------|-----------|----------|----------|

#### State changes
| Entity | From → To | Authority | Evidence |
|--------|-----------|-----------|----------|

#### Failure points
| Step | Failure mode | Handler | Evidence |
|------|--------------|---------|----------|
```

## Minimum journeys

| Source | Requirement |
|--------|-------------|
| Domain pack | Use pack examples when present |
| Generic | ≥3 flows covering create / process / reconcile or equivalent |
| Single product line | Still ≥3 distinct triggers or outcomes |

## Diagram

Each journey must include a `sequenceDiagram` or `flowchart TD` in `BUSINESS_FLOWS.md` or link to
`{map_file}` § Flow.

## P2b

Mark hops `CONFIRMED` / `CODE_ONLY` / `RUNTIME_ONLY` per [datadog-architecture-validation.md](datadog-architecture-validation.md).
