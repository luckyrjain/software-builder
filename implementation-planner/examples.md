# Examples

## Invocation

| # | User says | Resolves to | Notes |
|---|---|---|---|
| 1 | “Create an implementation plan from the approved design and impact report.” | implementation-planner | Requires all triggered specialist evidence |
| 2 | “Turn this change impact into an executable task DAG.” | implementation-planner | Single-repository plan with deterministic waves |
| 3 | “Implement the next task from this plan.” | loop-task-implementer | The planner does not execute tasks |
| 4 | “Review the implementation PR for regressions.” | pr-review | The planner does not review code |

## Blocked example

If the impact report triggers a resilience review but no usable resilience artifact is supplied, emit
`BLOCKED` with the missing artifact reference. Never omit the trigger or assume the specialist passed.

## Partial example

If target paths are known but repository scope estimates are unavailable, emit a useful plan with
`PARTIAL` and `estimated_scope.estimate_known: false`; never emit `READY` from guessed bounds.
