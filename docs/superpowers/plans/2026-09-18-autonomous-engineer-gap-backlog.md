# Autonomous-engineer gap backlog

Source: gap analysis of 2026-09-18 (three read-only explorer passes over `skills/`, `skills.yaml`,
`agent-hosts.yaml`, `docs/`, and `evals/`). Goal: let software-builder act as a trustworthy
engineer that takes a task from ticket to reviewed PR. Findings were not independently re-verified
line by line; each ticket's first step is to re-confirm its evidence.

## Doctrine (confirmed 2026-09-18)

Production code is written **only** by executor skills that hold `repository-write` authority
(`loop-task-implementer`, `architecture-remediation-loop`, `mysql-to-postgres-sql`, and any new
executor), and only through the isolated Builder -> Reviewer -> adjudication loop. Report and
analysis skills never write production code, never publish, and never apply infra. Test creators
may write test code. Verdict, authorization, and action stay separate. Merge, deploy, and external
publication need an explicit caller grant.

New executors must be wrapper-style: they build a task envelope from an analysis skill's findings
and hand it to `loop-task-implementer`, rather than reimplementing the loop.

## Sizing and ordering

Size: S = under 1 day, M = 1-3 days, L = over 3 days. Priority: P0 blocks trust, P1 missing
engineer behavior, P2 breadth or hygiene. "Route" is the software-builder skill that should
own the planning of the ticket.

Suggested order: E6 -> A2, A3 -> A1 -> A4, A5, A6 -> B* -> C* -> D*. E1-E5 can run any time.

## Epic A: Trust foundation (P0)

| ID | Ticket | Size | Depends | Acceptance |
|----|--------|------|---------|------------|
| A1 | Certified live-eval baseline for `loop-task-implementer`: record 5-10 real tickets, track CI pass, review rounds, tokens, time, merge outcome | L | A2, A3 | Cases live under `evals/live/`, marked certified, run via the existing harness; a results table exists; regression threshold documented |
| A2 (done 2026-09-18, uncommitted) | Non-null default budgets: task token cap, elapsed-time cap, session budget for `backlog-runner` | S | none | `state-schema.yaml` defaults set and documented; orchestrator stops and escalates on breach; test covers breach |
| A3 | Append-only run log and token/cost telemetry for every agent action (PR created, review verdict, CI poll, escalation) | M | none | One structured record per action with run id; redaction applied; documented location; a lint or test validates the schema |
| A4 | Verify the Claude host end to end: skill execution and subagent isolation, not only file placement | M | none | New RUNTIME evidence in `agent-hosts.yaml`; `loop-task-implementer` moves off BLOCKED for role isolation, CI status, PR write on `claude` (or documents the exact remaining block) |
| A5 | Durable run-state store and Builder in-flight checkpoint | M | A3 | State written to a defined location; a crash mid-Builder resumes from the checkpoint instead of restarting; pressure test added |
| A6 | Enforcement layer: host permission templates (allowlist for git/CI commands), atomic lease for run identity | M | none | Shipped `claude` settings template; docs state which gates are enforced vs instruction-level; lease test shows no double execution |

## Epic B: Engineer behaviors (P1)

| ID | Ticket | Size | Depends | Acceptance |
|----|--------|------|---------|------------|
| B1 | Optional clarify step: run `engineering-decision-discovery` before the Builder when acceptance criteria are underspecified, instead of escalating | M | A1 | Selection precondition asks up to N questions; unattended mode still escalates; golden fixture added |
| B2 | Lightweight ticket -> plan path for small tasks, skipping the full design/architecture/impact chain | M | A1 | Size threshold defined; `implementation-planner` accepts a minimal input; bounded by the existing size limits |
| B3 | `bug-diagnosis` -> `loop-task-implementer` handoff with a fail-before / pass-after regression gate | M | A1 | Task envelope template; Reviewer checks the new test fails on the base commit and passes on head; documented in the escalation matrix |
| B4 | Human review-comment loop: ingest reviewer comments on the PR, fix, reply, re-request review | M | A1 | Comments become findings with provenance; Orchestrator resolves only threads it addressed; loop capped |
| B5 | Flaky-CI policy: rerun budget, flake classification, evidence recorded, never bypassed | S | none | Documented rules in orchestrator section on CI; pressure test for a flaky then green run |
| B6 | Cross-run repo-convention capture: propose learned conventions to a human-approved file | M | A3 | Proposals only, never auto-committed; conflicts with repo instructions resolve to the repo instructions |
| B7 | App-run / UI verification tier for the Builder: start the app, smoke test, screenshot | L | A1 | Opt-in per repo policy; results advisory, CI stays authoritative; works for one web stack first |
| B8 | Post-merge verification and tracker write-back (status comment, link PR) | M | A1 | Write-back is separately authorized; verification reads target-branch CI |

## Epic C: Analysis-to-action handoffs (P1)

Twelve analysis skills currently stop at a report. Pattern: wrapper task envelope, then
`loop-task-implementer`, following the B3 template.

| ID | Ticket | Size | Depends | Acceptance |
|----|--------|------|---------|------------|
| C1 | `security-review` -> executor (vulnerability fixes, secret-removal PRs; rotation stays human) | M | B3 | Matrix row; envelope template; Reviewer lens includes security; rotation listed as a human-action gate |
| C2 | `dependency-upgrade-review` -> executor (dependency and framework upgrades) | L | B3 | Stepwise upgrade plan becomes tasks; each PR keeps tests green; rollback note required |
| C3 | `incident-rca` -> executor (post-incident hardening) without needing an existing task branch | M | B3 | Creates the branch; links the RCA as source; alerting/observability changes go through `observability-review` first |
| C4 | `performance-review` -> executor with a benchmark gate | M | B3 | Before/after measurement required in the PR evidence |
| C5 | `tech-debt-assessor` -> `architecture-remediation-loop` or `backlog-runner` handoff | S | B3 | Ranked debt becomes tickets or candidates; no auto-filing without approval |
| C6 | Handoff rows for `database-review`, `observability-review`, `resilience-review` findings | S | B3 | Matrix rows plus a generic template; lint validates the matrix |
| C7 | New executor skill: docs, ADR, and changelog upkeep from merged changes | M | A1 | `repository-write` registry entry; opens a PR only; never edits code |
| C8 | Infra/IaC and Kubernetes manifest change executor | L | C6 | Apply stays human; plan output attached to the PR |

## Epic D: Scope expansion (P2)

| ID | Ticket | Size | Depends | Acceptance |
|----|--------|------|---------|------------|
| D1 | Multi-repo / monorepo change coordination | L | A5 | Cross-repo plan with ordering; each repo gets its own PR and gate |
| D2 | Release execution and post-deploy verification (tag, canary, soak) | L | A4, B8 | Deploy remains explicitly granted; verification reads observability evidence |
| D3 | Stack playbooks: frontend, mobile, data/ML | L | B7 | One playbook per stack with verification steps |
| D4 | `pr-gatekeeper`: GitHub support and auto-fix | M | A1 | GitHub webhook path; auto-fix goes through the executor, not inline |

## Epic E: Hygiene and decisions (P2 unless noted)

| ID | Ticket | Size | Notes |
|----|--------|------|-------|
| E1 | `backlog-runner` is `read-only` in `skills.yaml` but drives PR creation; correct `write_authority` | S | Registry regeneration and lint required |
| E2 | Refresh stale docs: ADR 0003 "38/38" count, spec status lines, unchecked plan boxes | S | Or mark superseded per `docs/history/README.md` |
| E3 | Exercise the signed release pipeline (no tags or releases found) | S | Publishing is outward-facing: needs an explicit go from the owner |
| E4 | Triage open Dependabot PRs #273-#278 | S | Follow the repo's dependency-review process |
| E5 | Decision: consolidate or clarify overlapping readiness skills and architecture skills | M | Route to `engineering-decision-discovery` |
| E6 (P0, done 2026-09-18, uncommitted) | ADR 0008: record the write-authority doctrine above and add it to `CONTEXT.md` | S | Do first; gates all executor work |

## Decisions needed from the owner

1. Target hosts: is `claude` the only host that matters, or should A4-style verification also
   cover Cursor and Codex?
2. Tracker of record (GitHub Issues or Jira) for B8 write-back and `backlog-runner`.
3. Autonomy ceiling: is merge ever granted, and under what conditions (repo, label, CI state)?
4. Budget numbers for A2 (tokens and wall-clock per task).
5. Whether E3 (first signed release) should happen before or after Epic A.
