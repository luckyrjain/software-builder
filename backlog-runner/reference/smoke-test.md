# Smoke test — expected minimal output

Run after install or any edit to this skill. Use a repo with loop-task-implementer already working
interactively (see [loop-task-implementer/reference/smoke-test.md](../../loop-task-implementer/reference/smoke-test.md)
to confirm that first), and an issue-tracker query returning at least 2 tickets, one declaring a
dependency on the other. **Run this smoke test across two separate invocations on two different
"nights"** (not just a single run with both tickets in the same batch) — the single-run case doesn't
exercise the cross-run dependency-satisfaction rule (queue-policy.md § 2 rule 4), which is this skill's
one previously-broken piece of genuinely new logic.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

## Invocation

> `tracker_query: <JQL or GitHub Issues search>`, `max_tasks_per_run: 2`, `repo_context: <repo, base
> branch, repository instructions>`

## Expected first output

Queue pull announced (tickets found, capped at `max_tasks_per_run`, any skipped as already in progress),
then dependency order announced, before the first loop-task-implementer invocation starts.

## A correct minimal output contains

1. **Dependency order respected** — the prerequisite ticket is attempted before its dependent.
2. **`HUMAN_ACTION_REQUIRED` on the first ticket does not stop the run** — the second ticket is still
   attempted (unless a stop condition already fired).
3. **`autonomous_merge_authorized` never `true`** in any loop-task-implementer invocation this skill
   makes — verify by inspecting the invocation, not just the summary.
4. **Morning summary produced** — per [reference/morning-summary-format.md](morning-summary-format.md),
   with correct Shipped/Blocked/Deferred/Skipped sections (empty sections still present).

## Pass criteria

- No merge ever happens.
- No ticket outside `max_tasks_per_run` is attempted.
- A dependent ticket is never attempted before its unresolved prerequisite.
- An in-flight ticket is never aborted mid-Builder-dispatch by a stop condition — it always finishes its
  current step first.

## Degraded paths

| Condition | Expected behavior |
|-----------|----------------------|
| 3 consecutive `ESCALATED` outcomes | Run stops pulling further tickets (`CONSECUTIVE_ESCALATION_BREAKER`); summary still produced |
| A pulled ticket already has an open PR from a prior run | Skipped at the pull step, not re-attempted, recorded in the summary's Skipped section |
| `deadline` reached mid-run | No new ticket started after it; the in-flight one finishes; summary produced with `DEADLINE_REACHED` |
| **Night 2: a dependent ticket's prerequisite reached `HUMAN_ACTION_REQUIRED` on night 1 and no longer matches `tracker_query`** | The dependent is attempted on night 2 (existing-PR evidence satisfies the dependency), **not** left `DEFERRED` — this is the regression case to watch for; see [examples.md § Multi-night dependency](../examples.md) |
