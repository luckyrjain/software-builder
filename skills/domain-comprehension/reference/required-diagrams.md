# Required diagrams (normative)

Every **first-pass complete** domain comprehension **must** include these diagrams.
Mermaid in the listed file. ~40 nodes max per diagram; split with cross-links if larger.

**Four architecture views** live in `DEPENDENCY_GRAPH.md` — do not merge view types in one graph.

| # | Diagram | File § | Produced in | Minimum content |
|---|---------|--------|-------------|-----------------|
| 1 | **Logical context graph** | `DEPENDENCY_GRAPH.md` § Logical context | P1 | Bounded contexts + external actors |
| 2 | **Service call graph** | `DEPENDENCY_GRAPH.md` § Service call | P0.5 | Repo/service `calls` / `depends_on` from code |
| 3 | **Deployment graph** | `DEPENDENCY_GRAPH.md` § Deployment | P2 | Service → cluster/namespace/ingress from config |
| 4 | **Runtime graph** | `DEPENDENCY_GRAPH.md` § Runtime | P2b | Datadog-confirmed edges (or skip note) |
| 5 | **Sequence (happy path)** | `{map_file}` § Flow | P2 | Trigger → terminal success |
| 6 | **Sequence (failure path)** | `{map_file}` § Flow | P2 | Main failure branch |
| 7 | **State machine** | `STATE_MACHINE.md` | P2 | States + transitions with code refs |
| 8 | **Business flow** | `BUSINESS_FLOWS.md` | P2 | ≥3 journeys — [business-flows.md](business-flows.md) |
| 9 | **Repository ownership** | `BOUNDED_CONTEXTS.md` | P1 | Repo → squad/context map |

Legacy single "context" diagram = **Logical context graph** (row 1).

## If diagram cannot be built

1. Record in `UNKNOWNS.md` or `KNOWN_OMISSIONS.md` — why
2. Mark section confidence **UNKNOWN** or **LOW**
3. Do **not** substitute README/Confluence diagrams without code verification

## Syntax

- Sequence: `sequenceDiagram`
- State: `stateDiagram-v2`
- Dependencies: `graph LR` or `flowchart TD`
- Label edges with transport (HTTP, Kafka, gRPC) when known from evidence
- Prefix Mermaid caption with view name: `Logical context`, `Service call`, etc.
