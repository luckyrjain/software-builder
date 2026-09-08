# As-built PRD synthesis

`PRD.md` is a **current-state/as-built** product and system requirements reconstruction produced from completed domain-comprehension evidence. It supports a single service, bounded context, or multi-service domain.

## Boundary

- Describe behavior the implementation demonstrably supports, enforces, or depends on.
- Do not convert implementation accidents into desired product intent.
- Do not invent personas, business rationale, roadmap, KPIs, SLOs, acceptance criteria, or future behavior.
- When product intent is not recoverable, mark it `Unknown` and add the question to `UNKNOWNS.md`.
- Use **prd-architect** for future-state/MVP/build-readiness work, with this PRD and its supporting evidence as grounded input.

## Sources

Synthesize from `BUSINESS_FLOWS.md`, `STATE_MACHINE.md`, `API_CATALOG.md`, `EVENT_CATALOG.md`, `DATA_OWNERSHIP.md`, `{map_file}`, `DEPENDENCY_GRAPH.md`, `ARCHITECTURE_DECISIONS.md`, `RISK_MAP.md`, `RUNBOOK.md`, tests/configuration, runtime validation, and authoritative supplied documentation under the normal evidence-precedence rules.

Runtime telemetry may corroborate exercised behavior and operational constraints. Observed traffic, latency, throughput, replica count, or error rate is **not** automatically an intended requirement, KPI, or SLO.

## Requirement contract

Every requirement must have:

- stable ID: `FR-*`, `BR-*`, or `NFR-*`
- concise requirement statement
- scope/component
- status: `Observed | Inferred | Unknown`
- confidence: `HIGH | MEDIUM | LOW | UNKNOWN`
- evidence reference(s)

Use `Observed` only when implementation/contracts directly establish the behavior. Use `Inferred` only when multiple corroborating signals support the conclusion. Use `Unknown` when evidence is insufficient or contradictory.

Contradictory evidence must remain visible in `PRD.md` and `UNKNOWNS.md`; never resolve it by selecting the convenient interpretation.

## Required PRD coverage

Populate the template sections when evidence exists:

1. scope and system/domain purpose
2. actors/integrations actually evidenced
3. business flows and functional requirements
4. business rules, validation, limits, state transitions, and failure semantics
5. APIs/events and sync/async boundaries
6. data ownership and authoritative state
7. auth/security/fraud/compliance controls
8. configuration, deployment, dependencies, and operational behavior
9. observable non-functional behavior and constraints
10. risks, known omissions, unresolved product intent, and traceability

A required section with no supporting evidence must say `UNKNOWN` with the reason; never silently omit it.

## Delivery modes

- `FULL`: `PRD.md` is required in P5.
- `QUICK`: optional.
- `DELTA`: update only when affected requirements/behavior changed.
- `ADD_REPO`: re-synthesize after affected phases merge.
- `COMPLIANCE_RETROFIT`: normalize existing PRD structure without inventing evidence.
- `PROPOSAL_CHECK`: do not create or merge `PRD.md`.
