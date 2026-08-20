---
workflow_version: 2.6
phase: delegate
produces:
  - level_reports
consumes:
  - test_plan
  - implementation_task
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

Reject an unknown planned level rather than silently skipping it. Record an unknown planned level as
`BLOCKED` with an explicit fixed-vocabulary `blocked_reason` rather than fabricating a specialist report.

## 2. Dispatch independently

For each planned level in `test_plan.levels`, dispatch a **fresh specialist context** using the
canonical handoff envelope below. The typed `implementation_task` and ordinary caller inputs remain
unchanged, including target/run flags/budgets/output hints and level-specific fields such as `role` or
`journeys`. Inputs unchanged means the router does not translate, default, or pre-answer
specialist-owned inputs.

### Canonical handoff envelope

```yaml
handoff:
  target_skill: <specialist skill id>
  reason: execute the planned <level> test surface
  inputs:
    implementation_task: <unchanged typed scope envelope>
    request: <unchanged request>
    repo_root: <unchanged repo_root>
    target: <unchanged target>
    test_framework_hint: <unchanged, including explicit null>
    run_tests: <unchanged, including explicit false>
    max_files_per_run: <unchanged, including explicit zero>
    deadline: <unchanged, including explicit null>
    session_token_budget: <unchanged, including explicit null>
    output_dir: <unchanged, including explicit null>
    specialist_inputs: <unchanged optional specialist fields>
  evidence_refs: []
  assumptions: []
  unresolved: []
  execution_context: <fresh child context>
```

The executable handoff guard is:
`python3 -m scripts.registry.cli check-handoff <target_skill> --depth <parent.depth> --visited <comma-separated parent.visited_skills>`.

`execution_context` is the required exception to unchanged pass-through. Before each child dispatch,
apply the inherited recursion protection in
[runtime-contract.md §8](../../docs/skill-framework/shared/runtime-contract.md#8-recursion-protection).
If the handoff guard rejects the child, do not dispatch it. Record that planned level with
`dispatch_status: BLOCKED` and `blocked_reason: recursion_guard_rejected`, while preserving the guard's
human-readable reason in the enclosing canonical result blockers. Do not invent a specialist `report` for
a child that never ran.

Otherwise derive a fresh child context from the parent context: preserve the same invocation id, set
`parent_skill` to `test-writer`, add `test-writer` to the visited-skill history, and set `depth` to
`parent.depth + 1`. Increment depth once.
If there is no
root execution context, the direct host supplies a stable invocation id, `parent: null`, an empty
`visited_skills` list, and depth `0`; test-writer must not invent the repository path or invocation id.

Each planned specialist gets its own child context derived from the same parent context. One sibling's
dispatch must not increase another sibling's depth or leak sibling-specific visited state. Do not mutate
any other caller-supplied field while advancing this framework-owned context.

Specialists may run sequentially when shared repository writes require serialization. Fresh context means
independent instructions/evidence, not necessarily concurrent execution.

**Do not feed one specialist's report** into a later specialist as hidden framing. If a prior specialist
changed the repository, give the later specialist the same caller request plus the current repository
state it would normally inspect; do not convert the earlier report into new caller requirements.

## 3. Preserve per-level reports and status

Record outputs as `level_reports`, keyed by planned level. For a child that ran, store its canonical
`skill_result` status and raw specialist report verbatim; preserve blockers, artifacts, confidence,
evidence status, write-guard details, and recommended next skill. The child `skill_result` is the
authority for the child's outcome; the router may only apply the documented portable status alias and
must not rewrite a child `BLOCKED`, `FAILED`, or `ESCALATED` result. Do not derive status from a report
heading or from files written. For a child blocked before dispatch, store an explicit fixed-vocabulary
`blocked_reason` instead of a fake report.

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
    report: <verbatim specialist report when dispatched>
  integration:
    dispatch_status: BLOCKED
    blocked_reason: recursion_guard_rejected
```

If a specialist asks a required question or hits its own HARD STOP after dispatch, preserve its result and
report as `BLOCKED`/`PARTIAL`; never answer on the specialist's behalf. If the specialist returns `FAILED`
or `ESCALATED`, preserve that result exactly and let Aggregate propagate it according to its precedence
rules.

Proceed to Aggregate after every planned level has either produced a report/status or been explicitly
recorded as blocked with a reason. Do not silently drop an unfinished level.
