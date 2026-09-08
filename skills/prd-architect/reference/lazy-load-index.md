# Lazy-load index

Load reference files **only when the active phase needs them**. Do not preload the full reference tree.

| Phase | Load |
|-------|------|
| **Always (after SKILL.md)** | [skill-contract.md](skill-contract.md), [rationalization-guards.md](rationalization-guards.md) |
| **Inputs** | [global-rules.md](global-rules.md) § Clarification, § Conflict |
| **Classify** | [response-modes.md](response-modes.md), [depth.md](depth.md), [phase-index.md](phase-index.md) § Pipeline routing |
| **Validate** | [global-rules.md](global-rules.md) § Evidence, § Research; [phase-index.md](phase-index.md) § Pipeline routing |
| **Specify** | [section-triggers.md](section-triggers.md), [requirements-format.md](requirements-format.md), [correctness-rules.md](correctness-rules.md) when risk triggered |
| **Break** | [adversarial-review.md](adversarial-review.md) |
| **Repair** | [global-rules.md](global-rules.md) § Materiality, § Scope |
| **Gate** | [output-contract.md](output-contract.md), [report-template.md](../report-template.md), [depth.md](depth.md) |

Shared framework (link only — do not duplicate):

- [prompt-injection.md](../../docs/skill-framework/shared/prompt-injection.md)
- [skill-routing.md](../../docs/skill-framework/shared/skill-routing.md)
