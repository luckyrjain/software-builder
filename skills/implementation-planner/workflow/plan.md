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

Derive the plan-set and repository plan identities from a canonical digest of the immutable source
set, create only repository-grounded tasks, preserve cross-repository work as explicit external
dependencies, and assign task waves deterministically from the dependency DAG — identical inputs must
yield identical identities and identical wave assignments. A Software Builder checkout implements
exactly this as `build_implementation_plan` in `<checkout>/scripts/implementation_plan.py`; that module
is not part of an installed package, so apply the rule directly when it is unavailable.

Unresolved `external_dependencies` keep the plan `PARTIAL` until repository evidence records each
dependency as `READY`, `COMPLETE`, or `SUCCESS`; a requirement declaration is never treated as proof
that the dependency is satisfied.

## 3. Validate

Validate before emitting output — `validate_implementation_plan` in the same checkout module does
this, and the same checks are required without it. Check all dependencies, cycles, wave order,
source traceability, required tests, target paths, executor identity, and size estimates. `READY` is
forbidden for failed/unknown mandatory evidence or unknown estimates.

## 4. Resume handoff

Pass `implementation_plan` to `loop-task-implementer`. The executor validates it, selects one eligible
task, and reconciles `plan_execution_state` against official task/SCM state before any branch or PR
write. Remote branch/ref creation uses the observed head as an expected-head/fast-forward
precondition; after a create conflict, re-read the deterministic branch and PR identity and adopt the
matching execution or return `BLOCKED`. Never force-update a conflicting execution. The canonical
plan is immutable. Task statuses may be supplied to the selector only after this reconciliation; an
unreconciled caller/file status map is rejected.
