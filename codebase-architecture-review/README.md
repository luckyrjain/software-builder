# codebase-architecture-review

Reviews a bounded existing codebase area for evidence-backed architecture friction and refactoring
candidates. It is ambient, read-only, and report-only: it emits
`CODEBASE_ARCHITECTURE_REVIEW.md` / `codebase_architecture_report` without changing repository state.

The shared [codebase design doctrine](../docs/skill-framework/shared/codebase-design-principles.md) is
normative. The review caps itself at 200 fully read files, 3 hotspots, and—when available—200 commits over
180 days. Missing Git history produces a degraded report that omits churn and co-change claims.

Every candidate is evidence-gated and actively falsified. The valid outcome may contain 3–7 candidates,
fewer candidates, or none. The skill never refactors automatically and always returns
`recommended_next_skill: null`.

Every retained candidate states a recommendation strength (`Strong` / `Worth exploring` / `Speculative`), a
dependency category, a deletion-test result, and before/after models. The report may also render as one
ephemeral, self-contained HTML companion that the host writes to OS temporary storage — never into the
repository, and never a new durable artifact — with degraded-but-safe behavior when its CDN dependencies
or a browser are unavailable. See [reference/html-report.md](reference/html-report.md).

Registered `escalation_targets` are optional human-visible handoff offers, not typed report values. A
retained finding may be offered to `module-design` or `domain-comprehension` only for a separate
user-authorized invocation; this report never selects or dispatches a downstream skill.

## Pipeline

`Scope → Evidence → Candidates → Falsify → Report`

See [SKILL.md](SKILL.md) for the contract and [examples.md](examples.md) for invocation patterns.
