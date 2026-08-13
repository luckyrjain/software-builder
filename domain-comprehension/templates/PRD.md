# As-Built Product Requirements Document

> This PRD describes the **observed current-state behavior** of the in-scope service(s) and/or domain. It is reverse-engineered from implementation evidence. It does **not** claim undocumented product intent.

## Document status

| Field | Value |
|---|---|
| Scope | UNKNOWN |
| PRD type | As-built / current-state |
| Generated from | Domain-comprehension evidence set |
| Overall confidence | UNKNOWN |
| Product intent gaps | See `UNKNOWNS.md` |

## 1. Purpose and scope

Describe what the service/domain demonstrably does, who or what interacts with it, and the boundaries of this PRD. Mark unevidenced product rationale as `UNKNOWN`.

## 2. Actors and consumers

| Actor / consumer | Interaction | Evidence | Confidence |
|---|---|---|---|
| UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |

## 3. Current capabilities

| Capability ID | Capability | Service / bounded context | Evidence | Implementation status | Exercise status | Confidence |
|---|---|---|---|---|---|---|
| CAP-001 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |

## 4. Functional requirements

State requirements as behavior the implementation demonstrably enforces or supports. Do not convert naming, comments, README prose, or runtime frequency into intent without corroboration.

| ID | Requirement | Scope | Evidence | Status | Confidence |
|---|---|---|---|---|---|
| FR-001 | UNKNOWN | UNKNOWN | UNKNOWN | Observed / Inferred / Unknown | UNKNOWN |

## 5. Business rules and invariants

| ID | Rule / invariant | Trigger / precondition | Outcome | Evidence | Confidence |
|---|---|---|---|---|---|
| BR-001 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |

## 6. Journeys and workflows

Summarize the evidence-backed journeys in `BUSINESS_FLOWS.md`, including happy paths, failure paths, retries, compensation, and asynchronous boundaries where known.

| Journey | Entry point | Key states / steps | Failure behavior | Evidence | Confidence |
|---|---|---|---|---|---|
| UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |

## 7. State and lifecycle model

Summarize states and transitions from `STATE_MACHINE.md`. Call out unreachable, contradictory, or only-inferred transitions.

## 8. Interfaces and contracts

### APIs

Summarize relevant rows from `API_CATALOG.md`: method/path or operation, producer/owner, consumers, auth, request/response semantics, errors, implementation status, and exercise status.

### Events and asynchronous contracts

Summarize relevant rows from `EVENT_CATALOG.md`: topic/event, producer, consumers, schema, delivery/retry semantics, ordering/idempotency expectations, and exercise status.

### Scheduled / batch / CLI / file interfaces

Document only when evidenced. Otherwise state `UNKNOWN` or `N/A` with reason.

## 9. Data model and ownership

Summarize authoritative entities, repositories/stores, replicas, caches, lifecycle, and ownership from `DATA_OWNERSHIP.md`. Distinguish source of truth from derived/read models.

## 10. Dependencies and integrations

| Dependency | Direction | Contract / purpose | Failure behavior | Evidence | Confidence |
|---|---|---|---|---|---|
| UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |

## 11. Authorization, security, fraud, and compliance controls

Document evidenced authentication, authorization, role/permission rules, sensitive-data handling, fraud controls, compliance checks, audit behavior, and known gaps. Do not infer a control merely because a framework or library is present.

## 12. Non-functional requirements

Record only properties enforced by code/config/contracts or corroborated by runtime evidence. Runtime observations validate current behavior; they do not by themselves establish intended SLOs.

| ID | Area | Requirement / observed constraint | Evidence | Status | Confidence |
|---|---|---|---|---|---|
| NFR-001 | Availability / latency / throughput / consistency / durability / idempotency / scalability / rate limit / recovery | UNKNOWN | UNKNOWN | Observed / Inferred / Unknown | UNKNOWN |

## 13. Configuration and deployment behavior

Document environments, feature flags, routing, deployment topology, scaling/config surfaces, base URLs, and operational dependencies that materially affect product/service behavior.

## 14. Observability and operations

Document logs, metrics, traces, correlation IDs, alerts, dashboards, runbook coverage, operational controls, and runtime-confirmed critical paths. Keep observed telemetry separate from intended requirements.

## 15. Error and failure semantics

| Failure / error | Trigger | User/system-visible behavior | Retry / compensation | Evidence | Confidence |
|---|---|---|---|---|---|
| UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |

## 16. Constraints and architectural decisions

Summarize verified constraints and relevant decisions from `ARCHITECTURE_DECISIONS.md`. Label inferred decisions explicitly.

## 17. Known gaps, contradictions, and risks

Link or summarize material items from `UNKNOWNS.md`, `KNOWN_OMISSIONS.md`, and `RISK_MAP.md`. Product-intent questions belong here when implementation evidence cannot answer them.

## 18. Success measures and analytics

Include KPIs, SLOs, product success measures, funnels, or analytics only when explicitly evidenced by source/config/contracts or authoritative supplied documentation. Otherwise state `UNKNOWN — product intent not recoverable from implementation evidence`.

## 19. Requirement traceability

Every `FR-*`, `BR-*`, and `NFR-*` above must appear here. A requirement without evidence is `Unknown`/`Inferred`, never silently presented as fact.

| Requirement ID | Evidence source(s) | Evidence type | Confidence | Notes / contradiction |
|---|---|---|---|---|
| FR-001 | UNKNOWN | Code / contract / config / test / runtime / authoritative doc | UNKNOWN | UNKNOWN |

## 20. Open product-intent questions

List questions that code and runtime evidence cannot answer: why behavior exists, desired future behavior, business priority, target KPI/SLO, roadmap, or deliberate-vs-accidental constraints. Cross-reference `UNKNOWNS.md` rather than inventing answers.
