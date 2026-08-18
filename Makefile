# Repository-wide phony targets that are easy to miss in the legacy target set.
.PHONY: lint-prd-architect validate-review-contracts

# Keep the root Makefile as the stable public entry point; target
# definitions and new additions live in the included core file.
include make/core.mk

# Keep this prerequisite list aligned with make/core.mk's canonical lint rule.
# The extra repository-level review-contract validator is additive.
lint: validate-registry backfill-capabilities-check generate-check validate-evals validate-operational-upkeep lint-framework lint-pr-review lint-pr-gatekeeper lint-k8s-skill lint-incident-rca lint-incident-triage-agent lint-domain-comprehension lint-squad-map lint-who-owns-x-bot lint-new-hire-guide lint-release-readiness-checker lint-migration-program-manager lint-cost-optimization-sprint-planner lint-mysql-to-postgres-sql lint-loop-task-implementer lint-backlog-runner lint-weekly-squad-digest lint-unit-test-creator lint-integration-test-creator lint-contract-test-creator lint-e2e-test-creator lint-api-test-creator lint-test-writer lint-prd-architect lint-requirements-lock lint-actions-pinning lint-actions-security verify-install verify-install-all validate-review-contracts

validate-review-contracts:
	@python3 scripts/validate_review_contracts.py --contracts-only
