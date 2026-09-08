---
workflow_version: 1.0
phase: analyze
produces:
  - blast_radius_finding
  - migration_risk_finding
  - rollback_complexity_finding
  - dependency_risk_finding
  - traffic_risk_finding
consumes:
  - change_description
  - affected_services
  - migration_steps
  - rollback_plan
  - traffic_pattern
---

# Analyze — evaluate the five deployment-risk dimensions

Run all five checks below over the resolved inputs. Every check produces a finding — including an
explicit evidence-gap finding when a check cannot be completed. Never skip a check silently, and
never let a gap in one dimension silently improve or worsen a different dimension's own finding.

## 1. Blast radius — what breaks if this is wrong

- Identify affected services/users/data paths from `affected_services` and `change_description`.
- Distinguish a critical/customer-facing path (payments, auth, data integrity) from an internal or
  low-traffic one — this distinction feeds the verdict derivation in
  [reference/report-format.md](../reference/report-format.md).
- If `affected_services` is absent and not inferable from `change_description`, record an explicit
  evidence gap ("Unknown — affected_services not supplied and not inferable") rather than assuming
  a narrow or empty blast radius.

## 2. Migration risk — data/schema changes and reversibility

- Read `migration_steps` (and any migration files/scripts visible in the repository, if a repo is
  in scope) for schema changes, backfills, or data transformations.
- Classify reversibility: a migration is **reversible** only if a documented down-migration or
  equivalent revert path exists; an additive, non-destructive change (e.g. a nullable column) is
  reversible by default, a destructive one (dropped column, irreversible backfill, non-idempotent
  transform) is irreversible.
- "None stated" in `migration_steps` is only treated as "no migration" when `change_description`
  itself confirms the change has no data/schema component — otherwise it is an evidence gap.

## 3. Rollback complexity — how fast, how safe

- Read `rollback_plan` for a concrete revert mechanism (feature flag, previous-version redeploy,
  down-migration, config revert) and how quickly it can execute.
- A rollback plan that only reverts code but leaves an irreversible migration's data changes in
  place is **not** a safe rollback for that migration — call this out explicitly rather than
  crediting the rollback plan for a data change it cannot undo.
- If `rollback_plan` is absent and none is discoverable, record an explicit evidence gap — never
  assume rollback is safe or fast by default.

## 4. Dependency risk — what this depends on / what depends on it

- From `change_description` and repository context (if in scope), identify upstream dependencies
  this change requires (a schema version, another service's API, a config flag) and downstream
  dependents that could be affected if this change is wrong or delayed.
- Record "None found" explicitly when no dependency risk is identified — do not omit the section.

## 5. Traffic risk — peak-time exposure, canary coverage

- Read `traffic_pattern` for deploy timing relative to peak load, and for canary/staged-rollout
  coverage.
- When `traffic_pattern` is unstated, apply the conservative default from
  [workflow/inputs.md](inputs.md) — treat as peak-risk, never assumed off-peak/low-traffic.

## Evidence gaps

Any check that cannot be completed (missing input, nothing discoverable in the repository) is
recorded as its own explicit finding — never silently skipped, never folded into a clean/"none
found" result. Gaps feed both the `deployment_confidence` field and the Risk verdict floor per
[reference/report-format.md § Rules](../reference/report-format.md#rules).
