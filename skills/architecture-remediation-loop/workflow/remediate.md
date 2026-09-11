---
workflow_version: 1.0
phase: remediate
produces:
  - batch_results
consumes:
  - dispositioned_ledger
---

# Remediate — design where needed, batch, implement via loop-task-implementer

**Goal:** turn every ACCEPT/ACCEPT WITH MODIFICATION row into a merge-ready PR. No new design,
implementation, test, review, commit, push, or PR logic here — module-design's and loop-task-implementer's
own workflows are authoritative; this step only decides **which candidates share a batch** and hands each
batch to loop-task-implementer as one `implementation_task`.

## Steps

1. **Design pass** — for every accepted row flagged `needs_design`, invoke **module-design** with that
   row's resolved `engineering_decision_record`. Attach the resulting `module_design_spec` to the row;
   Remediate never implements a `needs_design` row without one.
2. **Batch** every accepted row (design attached where required) per
   [reference/pr-batching-policy.md](../reference/pr-batching-policy.md) — dedicated PR for large/high-risk
   candidates, grouped PR for small/cohesive ones sharing one architectural story. Classification is
   provisional; re-classify per the policy's escalation/de-escalation rules once implementation scope is
   known.
3. **For each batch**, invoke **loop-task-implementer** exactly once with one `implementation_task`
   describing every candidate in that batch (IDs, evidence, disposition, and any attached
   `module_design_spec`) — same pattern backlog-runner uses for its own queue, one task per invocation, not
   a bulk "implement this list" request. `autonomous_merge_authorized` is never passed `true`.
4. Record the outcome per batch:

   | loop-task-implementer outcome | This skill's action |
   |--------------------------------|-------------------------|
   | `HUMAN_ACTION_REQUIRED` (PR opened, not merged) | Normal, expected — mark every candidate in the batch `COMPLETED`, record the PR link |
   | `ESCALATED` | Mark every candidate in the batch `BLOCKED`, record loop-task-implementer's own escalation report; **do not retry the same batch a third time** — see [SKILL.md § Circuit breakers](../SKILL.md#circuit-breakers) |

5. When every batch has reached a terminal outcome, hand the cumulative branch state to Converge.

## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| `batch_results` | Session state | Per batch: candidate IDs, PR link or escalation report, outcome | Remediate incomplete — do not proceed to Converge |

## Read-only boundary

Design (module-design) is read-only. Implementation (loop-task-implementer) is the only repository-write
step in this whole skill — it always runs with `merge: false`; this skill never merges a PR itself.
