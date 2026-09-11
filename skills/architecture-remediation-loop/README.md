# architecture-remediation-loop

**Autonomous whole-codebase architecture remediation loop, built entirely from existing skills.** Every
cycle: **codebase-architecture-review** discovers candidates, **engineering-decision-discovery** grills and
disposes each one, **module-design** designs the ones that need it, **loop-task-implementer** implements,
tests, reviews, commits, pushes, and opens a PR per batch — never merges — and once every batch's PR is
merge-confirmed, **production-readiness-review** holistically checks the resulting state. Repeats with a
fresh architecture pass until both gates hit zero. No external architecture tool —
codebase-architecture-review is the sole discovery engine.

## What it does

1. **Discovers** architecture friction in a bounded `review_scope`, using this repo's own
   codebase-architecture-review, never an outside tool.
2. **Grills every candidate** via engineering-decision-discovery until it has a terminal disposition
   (ACCEPT / ACCEPT WITH MODIFICATION / ALREADY SATISFIED / DUPLICATE / REJECT / OUT OF SCOPE).
3. **Designs** a concrete module/interface/seam via module-design only for candidates that need one before
   implementation.
4. **Batches** accepted candidates by risk, size, and cohesion — large/high-risk ones get their own PR,
   small cohesive ones share one.
5. **Implements each batch** via loop-task-implementer — its own Builder/Reviewer lens loop, adjudication,
   commit/push/PR, unedited. Never merges; a batch's PR waits at `HUMAN_ACTION_REQUIRED`.
6. **Confirms each merge, then runs a holistic gate** — once every batch's PR is confirmed merged (checked
   directly against the PR's own status, per backlog-runner's own precedent), production-readiness-review
   checks the resulting state, fixing every accepted finding before re-checking the architecture gate. PRs
   still pending pause the cycle at `AWAITING_MERGE` rather than scanning unfixed code.
7. **Reconverges** — repeats from step 1 with a fresh architecture scan until both gates return zero
   actionable findings, or a circuit breaker stops the loop.

## When to use

This skill is for the **repeated, whole-scope convergence loop** — pointing it at a subsystem and letting
it cycle discovery → disposition → implementation → holistic review → rediscovery until clean. A single
bounded architecture review with no implementation intent routes to **codebase-architecture-review**
directly; one already-scoped task routes to **loop-task-implementer** directly; one PR's own readiness
verdict routes to **production-readiness-review** directly. Full routing table:
[SKILL.md](SKILL.md#when-to-use-not-to-use).

## Invocation examples

```
review_scope: services/billing, repo_context: <repo, base branch>, max_cycles: 3
review_scope: "payment retry/idempotency path", repo_context: <repo, base branch>, max_candidates_per_cycle: 10
```

## What you get

`architecture_remediation_report` — a full candidate ledger with terminal dispositions, every batch's PR
link, cycle count, and both gates' final status. Nothing is ever merged automatically; every PR is left
`HUMAN_ACTION_REQUIRED`, unchanged from loop-task-implementer's own contract.

## Install

```bash
cd software-builder
make install-architecture-remediation-loop
```

Restart Cursor. Requires **codebase-architecture-review**, **engineering-decision-discovery**,
**module-design**, **loop-task-implementer**, and **production-readiness-review** installed and configured
(the make target chains them) — see [SETUP.md](SETUP.md).

## Related skills

- **codebase-architecture-review** — sole discovery engine for every cycle; this skill adds the loop,
  ledger, and PR-batching policy on top, no new review logic
- **engineering-decision-discovery** — grills and disposes every candidate; no new grilling logic here
- **module-design** — designs the module/interface/seam for candidates that need one
- **loop-task-implementer** — does the actual implementation, test, review, commit, push, and PR; this
  skill only decides batch composition and when to stop
- **production-readiness-review** — the holistic multi-dimension gate each cycle must clear before
  rediscovery
- **backlog-runner** — the same "thin orchestration layer over an existing loop" pattern, applied to a
  ticket queue instead of an architecture ledger

Agent instructions: [SKILL.md](SKILL.md).
