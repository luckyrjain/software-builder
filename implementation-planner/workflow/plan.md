---
workflow_version: 1.0
phase: plan
produces:
  - implementation_plan
  - plan_set_id
  - plan_id
consumes:
  - system_design_spec
  - architecture_review_report
  - change_impact_report
  - specialist_reports
---

# Plan workflow

## 1. Inputs

Resolve the immutable source set: system design, architecture review, change impact, and every
design-time specialist named by `review_triggers`. Verify source digests and the canonical target
repository. A missing or stale source is a planning blocker.

## 2. Build

Call `build_implementation_plan` from `scripts/implementation_plan.py`. It derives the plan-set and
repository plan identities, creates only repository-grounded tasks, preserves cross-repository work as
explicit external dependencies, and assigns deterministic task waves.

## 3. Validate

Run `validate_implementation_plan` before emitting output. Check all dependencies, cycles, wave order,
source traceability, required tests, target paths, executor identity, and size estimates. `READY` is
forbidden for failed/unknown mandatory evidence or unknown estimates.

## 4. Resume handoff

Pass `implementation_plan` to `loop-task-implementer`. The executor validates it, selects one eligible
task, and reconciles `plan_execution_state` against official task/SCM state before any branch or PR
write. Remote branch/ref creation uses the observed head as an expected-head/fast-forward
precondition; after a create conflict, re-read the deterministic branch and PR identity and adopt the
matching execution or return `BLOCKED`. Never force-update a conflicting execution. The canonical
plan is immutable.
