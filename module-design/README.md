# module-design

Designs one bounded module in an existing repository from concrete evidence: callers, implementation,
tests, dependency edges, configuration, and observed change pressure. It produces a report-only
`MODULE_DESIGN_SPEC.md` / `module_design_spec`; it never writes source or repository state.

Use it to make a module's contract, invariants, dependency direction, seams, adapters, errors, state,
concurrency, performance, test surface, migration, rejected alternatives, and open questions explicit.
The shared [codebase design doctrine](../docs/skill-framework/shared/codebase-design-principles.md) is
normative.

## When to use

- A named module/path needs a boundary or contract design before implementation.
- Callers leak an implementation detail, a seam may be warranted, or an adapter may need to translate a
  real external contract.
- A local design needs evidence-backed alternatives, including two materially different options when the
  interface is uncertain.

Do not use it for a multi-module implementation design (`system-design`) or an architecture-wide decision
(`architecture-review`).

## Pipeline

`Inputs → Design → Report`

See [SKILL.md](SKILL.md) for the full contract and [examples.md](examples.md) for invocation patterns.
