# Section triggers

Generate **only** triggered sections. Never output empty or N/A sections.

In **Lite** depth, the Lite preferred section list in [depth.md](depth.md) guides compression, but it does
not waive mandatory measurable success metrics, material `FR-* -> AC-* -> TR-*` traceability, or an
engineering section whose trigger is required for correctness/safety/compatibility/operability.

Full section × trigger matrix: [output-tables.md](output-tables.md) § Section triggers.

Key engineering triggers from [current-state-evidence-contract.yaml](current-state-evidence-contract.yaml):

| Section | Trigger |
|---|---|
| Success Metrics | PRD/Review Mode; material metrics use baseline + target + timeframe + measurement source |
| Requirements Traceability | Material functional requirements exist |
| Assumption Register | Consequential assumptions exist |
| Rollout / Rollback | Production/existing-system change where staged delivery or reversal materially affects risk |
| Operational Readiness | Production change |
| Migration / Backward Compatibility | Existing system or API/event/schema/data/config/client behavior changes |
| API / Event / Schema Impact | API, event, or schema changes |
| Data / Privacy Impact | Personal/sensitive data, retention, or access changes |
| Cost Impact | New infra, material traffic/storage growth, or paid dependency |
| Observability Requirements | Production change |

| Appendix | Trigger |
|---|---|
| Build Readiness | Always (PRD/Review) |
| Decisions & Constraints | Resolved decisions and mandatory constraints only |
| Adversarial Review Summary | Material findings add useful context beyond repaired PRD |
| Gap Analysis | Material gaps add useful context beyond repaired PRD |
| Material Changes | Review Mode |
| Change Impact | Review Mode on existing product/system |
| Research provenance | External research materially influenced requirements or recommendations |

Appendix table schemas: [output-tables.md](output-tables.md).
