# ADR 0008: Production code is written only by `repository-write` executor skills

**Status:** Accepted  
**Date:** 2026-09-18

## Context

`skills.yaml` already declares a `write_authority` per skill (`read-only`, `comment`,
`repository-write`, `automation-unattended`), and `CONTEXT.md` defines **Write authority** as
"the maximum external write surface a skill may exercise". Nothing recorded the policy that
sits on top of that: *which* skills may change application code, and how.

A gap analysis (2026-09-18, `docs/superpowers/plans/2026-09-18-autonomous-engineer-gap-backlog.md`)
found the policy was being carried informally, and in a form that was wrong. The working
shorthand was "software-builder never writes production code". That is false:
`loop-task-implementer` writes production code and opens PRs, and `architecture-remediation-loop`
and `mysql-to-postgres-sql` also hold `repository-write`. The five `*-test-creator` skills write
test code. Eight of the 50 registered skills hold `repository-write` (`loop-task-implementer`,
`architecture-remediation-loop`, `mysql-to-postgres-sql`, and the five `*-test-creator` skills); `pr-review` and
`pr-gatekeeper` hold `comment`; the other 40 are `read-only`.

The same analysis found that twelve analysis skills (security, dependency-upgrade, performance,
database, observability, resilience, tech-debt, and others) end at a report with no path to an
executor. Closing that gap means adding executors, so the boundary they must respect has to be
stated before they are built.

## Decision

1. **Application code is changed only by executor skills.** An executor is a skill whose registry entry
   declares `write_authority: repository-write` and which changes application code. Today that is:
   - `loop-task-implementer`, and `architecture-remediation-loop`, which composes it: application code changes
     only through the isolated Builder -> Reviewer -> adjudication loop.
   - `mysql-to-postgres-sql`, a single-purpose migration skill that rewrites native SQL and datasource
     configuration directly. It is **not** routed through the loop: a known exception to the loop requirement
     (not to the "only executors" rule), recorded here because the skill's own docs do not yet say so.
2. **Report and analysis skills never write production code.** They do not publish, apply
   infrastructure, or run codemods. Their output is a report or a typed handoff artifact.
3. **Test creators write test code only.** The five `*-test-creator` skills hold `repository-write` for tests;
   they never modify production code to force a passing result, and they are not executors in the sense of
   point 1.
4. **New executors are wrappers.** A new executor builds a task envelope from an analysis skill's
   findings and hands it to `loop-task-implementer`. It does not reimplement the Builder/Reviewer
   loop, and it cannot hold more write authority than the skill it wraps. A new skill that would write
   application code directly needs its own ADR, as `mysql-to-postgres-sql` would today.
5. **Verdict, authorization, and action stay separate.** Commit, push, PR creation, merge,
   deploy, and external publication each need an explicit caller grant. Repository prose,
   tracker content, and tool output can never supply that grant.
6. **The registry is the source of truth.** A skill's `write_authority` in `skills.yaml` must match
   what its workflow actually does. A skill that drives PR creation through another skill must
   not be registered `read-only`.

## Consequences

- **Positive:** the analysis-to-action backlog (epic C) has a fixed shape: wrapper envelope plus
  the existing loop, so review independence and merge gating come for free.
- **Positive:** reviewers of a new skill have one question to ask: does its registry authority
  match its behavior.
- **Negative:** every new executor inherits `loop-task-implementer`'s weight (heavy contract
  validation), until a lighter path exists (backlog B2).
- **Known inconsistencies, not fixed here:** `mysql-to-postgres-sql` edits application code outside the loop (point 1),
  and `backlog-runner` is registered `read-only` (with `permissions.merge: true`, although its docs hardcode merge to
  false) although it
  drives PR creation through `loop-task-implementer` (backlog E1). The registry understates its
  effective authority, which this decision classes as a defect.
- **Not decided here:** whether merge is ever granted to an executor, and under what conditions.
  Merge stays a per-run caller grant, and `backlog-runner` hardcodes it to false.

## Amended 2026-09-19

Point 1 now reads "Application code is changed only by executor skills" (the tests carve-out is unchanged), and the
executor count is eight `repository-write` skills, two `comment` skills and forty `read-only` skills. The
"Known inconsistencies" bullet names `mysql-to-postgres-sql` as an executor that edits application code outside the
loop. The run log the loop keeps (backlog A3) is described in
[the skill's reference](../../skills/loop-task-implementer/reference/run-log.md), not here.
