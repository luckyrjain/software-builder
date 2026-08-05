# Completion report — template

The Orchestrator reports this after every task, whether it completes, stops at verified readiness, or
escalates.

```markdown
**Task:** `<task_id>` — `<repository>`
**Branch / PR:** `<branch>` — `<pull_request_url>`
**Head commit:** `<head_commit>` (diff fingerprint `<diff_fingerprint>`)

**Lens A (Safety and State):** CLEAN | FINDINGS — `<summary>` (isolation: `<SUBAGENT|FRESH_SESSION|WORKTREE|SEQUENTIAL_SIMULATION>`)
**Lens B (Contracts and Operations):** CLEAN | FINDINGS — `<summary>` (isolation: `<same>`)

**Accepted findings:** `<count>` — `<one line per finding: id, status>`
**Contested findings:** `<count>` — `<one line per finding: id, reason>`

**Authoritative checks:** `<name>: PASS|FAIL|PENDING (commit <sha>)` — one row per required check

**Completion state:** NONE | MERGED | HUMAN_ACTION_REQUIRED — matches `completion.repository_action`
in [reference/state-schema.yaml](reference/state-schema.yaml) exactly. `HUMAN_ACTION_REQUIRED` covers
both "verified ready, waiting for authorized merge" and "escalated" — check `escalation.active` to
tell them apart.

**Human action required:** `<exact action, or "none">`
```

## Escalation variant

When stopping via a circuit breaker, use the `escalation` block from
[reference/state-schema.yaml](reference/state-schema.yaml) instead of the completion state line above:

```yaml
task_id:
pull_request:
current_head_commit:
diff_fingerprint:
dirty_review_count:
review_run_count:
accepted_findings:
contested_findings:
fix_attempts:
rebuttal_log:
authoritative_checks:
third_party_changes:
budget_consumed:
escalation_reason:
required_human_decision:
required_access:
supporting_evidence:
```

This mirrors `workflow/orchestrator.md` §19 exactly — the escalation report is not a separate format,
it's this template's `completion` and `escalation` fields filled in from state.

## Cross-skill handoff block

When escalating or handing off to another skill (see `SKILL.md` § Cross-skill escalation), use the
shared handoff block format from
[cross-skill-escalation.md §3](../docs/skill-framework/shared/cross-skill-escalation.md#3-handoff-block-required-fields).
