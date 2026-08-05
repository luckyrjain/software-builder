---
name: software-builder
description: Use when autonomously implementing one or more software tasks through isolated build, evidence-based review, remediation, validation, pull-request, and completion workflows across coding agents.
---

# Software Builder

## Overview

Use this skill to take software tasks from requirements to verified repository completion while separating implementation, review, and orchestration responsibilities.

Core principle: **claims are advisory; repository evidence is authoritative.**

This skill is platform-neutral. The active coding agent may be Cursor, ChatGPT/Codex, Claude Code, Kiro, or another repository-capable agent.

## Natural-language invocation

Users can invoke the skill without memorizing commands:

- “Use software-builder to complete the next task.”
- “Implement issue 42, review it deeply, fix findings, and open a PR.”
- “Work through these tasks one by one and stop when each is ready to merge.”
- “Take this PR through independent review and remediation.”
- “Resume the software-builder workflow for the current branch.”
- “Run only the reviewer lens A on this change.”
- “Adjudicate the review findings instead of blindly fixing them.”

Interpret equivalent natural language as invocation.

## Roles

Use isolated contexts whenever the platform supports subagents, tasks, worktrees, or fresh sessions.

### Orchestrator

Owns workflow state, task selection, policy discovery, dispatch, adjudication, CI evidence, completion gates, and escalation.

It does not write implementation code or act as the independent reviewer.

### Builder

Implements one task, adds tests, runs advisory local checks, commits, pushes, and creates or updates the pull request.

It may fix or rebut review findings with evidence.

### Reviewer

Runs read-only against the exact diff and assigned lens. It may execute checks and perform disposable local mutations, but must not commit, push, or alter shared repository state.

## Workflow

```text
discover policy
→ select one eligible task
→ fresh Builder context
→ verify branch and diff
→ fresh Reviewer Lens A
→ adjudicate findings
→ remediate or rebut accepted findings
→ fresh Reviewer Lens B
→ adjudicate findings
→ rerun affected lenses after content changes
→ verify authoritative checks
→ complete repository action when authorized
→ verify result
→ continue to next eligible task
```

## Review lenses

### Lens A: Safety and State

Focus on authentication, authorization, trust boundaries, secrets, transactions, data integrity, state transitions, idempotency, retries, races, and security-relevant failure handling.

### Lens B: Contracts and Operations

Focus on acceptance criteria, API/event/schema compatibility, one-hop consumers, errors, concurrency, performance, timeouts, deployment, rollback, operability, and test sufficiency.

Both lenses must be clean for the same normalized diff fingerprint.

## Blocking standard

A finding is blocking only when evidence shows at least one of:

1. An explicit acceptance criterion is violated.
2. An enforced repository, security, compatibility, or deployment rule is violated.
3. A demonstrable input, state, race, failure, or deployment path is materially incorrect or unsafe.
4. A reproducible check fails because of the change.
5. The change materially exposes or worsens a pre-existing defect.

Style preferences, optional metrics, speculative risks, and unrelated cleanup are not blocking.

## Adjudication

The Reviewer proposes findings; it does not have an unconditional veto.

The Orchestrator classifies each proposed blocker as:

- `ACCEPTED`
- `REJECTED`
- `NEEDS_EVIDENCE`
- `CONTESTED`

The Builder may return:

- `FIXED`
- `REBUTTED`
- `BLOCKED`

Every rebuttal requires repository evidence. A finding contested twice without decisive evidence must be escalated.

## Evidence priority

Use this order:

1. Required CI for the exact commit
2. Orchestrator-run checks for the exact commit
3. Reviewer-run checks for the exact commit
4. Builder-reported checks

Never treat prose as the sole proof of correctness.

## Circuit breakers

Stop and escalate when any applies:

- More than three dirty review cycles
- Same accepted finding survives two fixes
- Same finding is contested twice without decisive evidence
- Diff exceeds configured hard limits
- Implementation alternates between prior fingerprints
- Required work materially exceeds authorized scope
- Missing product, architecture, access, or destructive-operation decision
- Unrecognized third-party branch changes
- CI cannot be diagnosed within the configured budget
- Time or token budget is exhausted

Clean reviews do not consume the dirty-review budget.

## Base updates

A content-neutral fast-forward, clean rebase, or merge-queue update may preserve lens approvals only when the normalized patch fingerprint is unchanged and no conflict resolution occurred.

Any content change or manual conflict resolution invalidates both lens approvals.

## Platform behavior

Use the strongest isolation primitive available:

1. Native subagents with independent context
2. Separate fresh sessions
3. Separate disposable worktrees
4. Sequential role simulation with explicit context resets as a last resort

Read [references/platform-adapters.md](references/platform-adapters.md) for Cursor, ChatGPT/Codex, Claude Code, and Kiro setup.

## Required state

Initialize state from [templates/state-schema.yaml](templates/state-schema.yaml).

The Orchestrator is the only role allowed to mutate official workflow state.

## Role prompts

Load only the role prompt needed for the active context:

- [references/orchestrator.md](references/orchestrator.md)
- [references/builder.md](references/builder.md)
- [references/reviewer.md](references/reviewer.md)

Do not give the Reviewer the Orchestrator prompt, Builder scratchpad, prior verdicts, PR narrative, branch framing, or commit-message framing.

## Completion response

Report:

- Task and repository
- Branch and pull request
- Current head and diff fingerprint
- Lens A and Lens B status
- Accepted or contested findings
- Authoritative checks
- Completion state
- Any exact human action required
