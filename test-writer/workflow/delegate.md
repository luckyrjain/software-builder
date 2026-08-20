---
workflow_version: 2.3
phase: delegate
produces:
  - level_reports
consumes:
  - test_plan
  - request
  - repo_root
  - execution_context
---

# Delegate — execute the test plan

## 1. Resolve each planned specialist

| level | specialist |
|-------|------------|
| `unit` | **unit-test-creator** |
| `integration` | **integration-test-creator** |
| `contract` | **contract-test-creator** |
| `api` | **api-test-creator** |
| `e2e` | **e2e-test-creator** |

Reject an unknown planned level rather than silently skipping it.

## 2. Dispatch independently

For each planned level in `test_plan.levels`, dispatch a **fresh specialist context**. Pass `repo_root`
and ordinary caller inputs unchanged, including target/run flags/budgets/output hints and level-specific
fields such as `role` or `journeys`. The router does not translate, default, or pre-answer
specialist-owned inputs.

`execution_context` is the required exception to unchanged pass-through. Before each child dispatch,
apply the inherited recursion protection in
[runtime-contract.md §8](../../docs/skill-framework/shared/runtime-contract.md#8-recursion-protection).
If the handoff guard rejects the child, record that planned level as `BLOCKED` and do not dispatch it.
Otherwise derive a fresh child context from the parent context: preserve the same invocation id, set
`parent_skill` to `test-writer`, add `test-writer` to the visited-skill history, and increment depth once.

Each planned specialist gets its own child context derived from the same parent context. One sibling's
dispatch must not increase another sibling's depth or leak sibling-specific visited state. Do not mutate
any other caller-supplied field while advancing this framework-owned context.

Specialists may run sequentially when shared repository writes require serialization. Fresh context means
independent instructions/evidence, not necessarily concurrent execution.

**Do not feed one specialist's report** into a later specialist as hidden framing. If a prior specialist
changed the repository, give the later specialist the same caller request plus the current repository
state it would normally inspect; do not convert the earlier report into new caller requirements.

## 3. Preserve per-level reports and status

Record outputs as `level_reports`, keyed by planned level. The raw specialist report is stored verbatim;
only orchestration metadata may sit beside it.

Use the specialist's canonical `skill_result.status` as the authoritative dispatch result. Preserve the
portable status losslessly instead of inventing a narrower local vocabulary:

| specialist `skill_result.status` | `dispatch_status` |
|----------------------------------|-------------------|
| `SUCCESS` | `COMPLETE` |
| `PARTIAL` | `PARTIAL` |
| `BLOCKED` | `BLOCKED` |
| `FAILED` | `FAILED` |
| `ESCALATED` | `ESCALATED` |

`COMPLETE` is only an internal alias for a specialist `SUCCESS`; every other portable status is retained
unchanged. Never convert `FAILED` or `ESCALATED` into `BLOCKED`/`PARTIAL`, because that loses the
specialist's authoritative outcome.

```yaml
level_reports:
  unit:
    dispatch_status: COMPLETE | PARTIAL | BLOCKED | FAILED | ESCALATED
    report: <verbatim specialist report>
  integration:
    dispatch_status: COMPLETE | PARTIAL | BLOCKED | FAILED | ESCALATED
    report: <verbatim specialist report>
```

If a specialist asks a required question or hits its own HARD STOP, preserve that result and stop that
level as `BLOCKED`/`PARTIAL`; never answer on the specialist's behalf. If the specialist returns `FAILED`
or `ESCALATED`, preserve that result exactly and let Aggregate propagate it according to its precedence
rules.

Proceed to Aggregate after every planned level has either produced a report/status or been explicitly
recorded as blocked. Do not silently drop an unfinished level.
