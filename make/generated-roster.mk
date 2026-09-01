# GENERATED from skills.yaml — do not edit; run `make generate`.
#
# ALL_SKILLS is the single source of truth for the full skill roster used by
# make/core.mk's lint-framework recipe (previously hardcoded verbatim in three
# separate `for skill in ...; do` loops). `make generate-check` fails if this
# file drifts from skills.yaml -- that's the drift guard, not a separate
# exception (see scripts/registry/generate_makefile_roster.py): a skill added
# to skills.yaml but missing from ALL_SKILLS_ORDER is simply appended after it
# (sorted), so the frozen order only pins the *existing* 38 skills' historical
# positions -- it never has to be hand-updated, and never fails a registry
# (e.g. a test fixture) that doesn't resemble the real repository at all.

ALL_SKILLS := pr-review pr-gatekeeper incident-rca incident-triage-agent k8s-overprovisioning-datadog domain-comprehension squad-map who-owns-x-bot new-hire-guide release-readiness-checker migration-program-manager mysql-to-postgres-sql loop-task-implementer backlog-runner cost-optimization-sprint-planner weekly-squad-digest prd-architect test-writer unit-test-creator integration-test-creator contract-test-creator e2e-test-creator api-test-creator architecture-review system-design api-design-review database-review security-review performance-review capacity-planner observability-review deployment-risk-review dependency-upgrade-review tech-debt-assessor change-impact-analyzer resilience-review implementation-planner production-readiness-review
