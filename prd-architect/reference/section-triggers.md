# Section triggers

Generate **only** triggered sections. Never output empty or N/A sections.

In **Lite** depth, the Lite preferred section list in [depth.md](depth.md) guides compression, but it does
not waive mandatory measurable success metrics, material `FR-* -> AC-* -> TR-*` traceability, or an
engineering section whose trigger is required for correctness/safety/compatibility/operability.

Full section × trigger matrix — including the engineering triggers (Success Metrics, Requirements
Traceability, Assumption Register, Rollout / Rollback, Operational Readiness, Migration / Backward
Compatibility, API / Event / Schema Impact, Data / Privacy Impact, Cost Impact, Observability Requirements):
[output-tables.md](output-tables.md) § Section triggers. Normative trigger definitions:
[current-state-evidence-contract.yaml](current-state-evidence-contract.yaml).

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
