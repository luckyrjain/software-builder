# Critical path (normative)

**Required in:** `{map_file}` § Flow (P2). Vertical chain from user/system action to terminal state.

## Template

```
User / system action
  ↓  <entry service + evidence>
API / handler
  ↓
Orchestrator / domain service
  ↓
Gate (block / consent / validation)  [if applicable]
  ↓
Side-effect executor (payment / write / publish)
  ↓
Async transport (Kafka / queue)       [if applicable]
  ↓
Worker / consumer
  ↓
Persistence (authoritative DB)
  ↓
Downstream notification / recon
  ↓
Terminal state (success | failure | manual review)
```

## Required outputs

1. **Numbered critical path** — one happy path per product line (if `product_lines` in config)
2. **Mermaid** — `flowchart TD` or `sequenceDiagram`; label each hop with repo + sync/async
3. **Failure cut points** — table: Step | Failure mode | Handler | Evidence
4. **P2b cross-check** — mark hops `CONFIRMED` / `CODE_ONLY` / `RUNTIME_ONLY` when Datadog available

## Tier alignment

Map hops to `critical_path_tiers` from config; Tier 0 hop must appear on every product-line path or explain divergence.
