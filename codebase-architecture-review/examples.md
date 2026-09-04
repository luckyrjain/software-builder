# Examples — codebase-architecture-review

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation

Invoke `codebase-architecture-review` ambiently for a bounded review of an existing codebase. It is
read-only and report-only: inspect the bounded repository scope, emit findings, and never change
repository state or refactor automatically.

| Caller sends | Behavior |
|-------------|----------|
| "Review the checkout subsystem for architecture friction; inspect these paths and their tests." | Bounded Scope → Evidence → Candidates → Falsify → Report review |
| "Use the last six months of history to find where order processing changes cluster." | Reviews at most 200 commits in 180 days; records history limits and corroborates any churn signal with code evidence |
| "Git history is unavailable, but review these service and test paths." | Degraded review; omits churn/co-change claims and lowers dependent confidence |
| "This directory has a huge file—split it." | Treats size as an investigation prompt, not proof; may return zero candidates |
| "Refactor the best hotspot after you find it." | Reports evidence and candidate trade-offs only; no automatic refactor |
| "Design the retained candidate's seam." | Offers a bounded human handoff to `module-design`; the typed result remains `recommended_next_skill: null` until a separate user-authorized invocation |
| "Review every repository in the organization." | Asks for a bounded scope; does not silently widen the review |
| "Design the seam for `src/payments/charge.py`." | Wrong scope — use `module-design` for a concrete module design |
| "Review this proposed event architecture before it is built." | Wrong scope — use `architecture-review` for a proposed architecture decision |

## Example: retained candidate

**Evidence:** three callers translate the same vendor exceptions, contract tests already assert a domain
error, and two independently changed paths expose the vendor field names.

**Result:** retain a candidate only after checking that a module-owned translation boundary would simplify
callers without adding a mock-only interface or violating an ADR. State the migration and abstraction cost;
do not apply it.

## Example: no candidate

**Evidence:** a large file has one owner, cohesive callers, stable contract tests, and no repeated
coordinated change or failed seam.

**Result:** record the investigation and return zero candidates. File size alone is not architecture
friction.
