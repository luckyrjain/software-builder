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

## Example: retained candidate, before/after models, ephemeral HTML path

**Evidence:** three callers translate the same vendor exceptions, contract tests already assert a domain
error, and two independently changed paths expose the vendor field names.

**Result:** retain the candidate only after checking that a module-owned translation boundary would
simplify callers without adding a mock-only interface or violating an ADR; classify it `ports-and-adapters`
and run the deletion test, which shows provider translation and retry policy would scatter into callers if
removed. The candidate card carries both a before model (`checkout -> charge_service -> provider_client`;
provider errors leak through `charge_service`) and an after model (`checkout -> charge`; `charge ->
provider_adapter`; `charge` owns translation and idempotency policy) — a retained candidate is incomplete
without both. The same evidence may also render as one card in the ephemeral, self-contained HTML companion
the host writes to OS temporary storage (for example
`/tmp/architecture-review-20260905T120000Z.html`); that path is never added to
`codebase_architecture_report` or `skill_result.artifacts`, and it does not change the migration or
abstraction cost stated in the Markdown report.

## Example: cohesive large module, zero candidates

**Evidence:** a 3,000-line module has one owner, a narrow interface, cohesive callers that never reach past
its contract, stable contract tests, and no repeated coordinated change or failed seam in history.

**Result:** treat the size as an investigation prompt, not proof of friction. Record the depth and cohesion
evidence and return zero candidates — a deep module with a narrow interface is not architecture friction
merely because the file is large.

## Example: shallow pass-through becomes `Worth exploring`

**Evidence:** a module forwards each call to another module with the same parameters and error shapes and
adds no policy of its own; two independently changed call sites each reimplement the same retry logic around
the pass-through.

**Result:** the deletion test shows that removing the module by itself is only a rename, but the
falsification pass also surfaces the duplicated caller policy as real, corroborated friction. Classify the
candidate `Worth exploring` rather than `Strong`, and state the evidence limit explicitly: no single
boundary has yet concentrated the duplicated retry policy, so the recommendation is bounded by that gap
rather than a confirmed abstraction.
