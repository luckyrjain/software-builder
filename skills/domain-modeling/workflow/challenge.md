---
workflow_version: 1.0
phase: challenge
produces:
  - terminology_findings
  - scenario_findings
  - code_cross_reference
  - adr_readiness
consumes:
  - domain_focus
  - existing_context
  - change_goal
---

# Challenge — sharpen the domain model from session evidence

Apply the shared [codebase-design-principles.md](../../../docs/skill-framework/shared/codebase-design-principles.md)
AI-navigability doctrine to naming: bounded, intention-revealing terms over incidental or overloaded
ones. For each item below, cite session or repository evidence, mark reasoning as inference where
appropriate, or create an explicit unresolved question. Never silently skip a check.

1. **Challenge against the glossary** — if `existing_context` defines `domain_focus` and the session usage
   conflicts with it, name the conflict directly rather than silently picking a side. If no definition
   exists yet, say so rather than treating silence as agreement.
2. **Sharpen fuzzy language** — if `domain_focus` (or a term used to describe it) is vague, overloaded, or
   used to mean two different things in the same session, propose a precise canonical term for each
   meaning and name which is which.
3. **Concrete edge-case scenarios** — invent at least one specific scenario that probes a boundary of
   `domain_focus` (a partial case, a concurrent case, a cross-context case) and record the answer the
   session gave, or mark it an unresolved question if none was given.
4. **Cross-reference with code** — where the code is inspectable, check whether it agrees with what the
   session stated about `domain_focus`. A contradiction is evidence, not something to resolve silently in
   the code's favor or the session's favor.
5. **ADR readiness** — an ADR is warranted only when a real decision point exists: a choice was made, at
   least one alternative was rejected, and a consequence was stated. A term definition alone, or a
   restatement of existing uncontested code, does not warrant an ADR; record `adr_readiness: false` and
   say why.

If the session evidence requires reconstructing an entire unfamiliar domain from scratch, offer
`domain-comprehension`. If a crystallized decision describes one module's concrete contract or seam,
offer `module-design`. If it needs an architecture-wide risk/scale/trade-off verdict, offer
`architecture-review`. Do not invoke any of them automatically.
