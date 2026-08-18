# Repository-wide phony targets that are easy to miss in the legacy target set.
.PHONY: lint-prd-architect validate-review-contracts

# Keep the root Makefile as the stable public entry point; target
# definitions and new additions live in the included core file.
include make/core.mk

# Batch 5.2A shared review contracts are repository-level inputs consumed by
# multiple skills, so validate them as part of the repository lint gate.
lint: validate-review-contracts

validate-review-contracts:
	@python3 scripts/validate_review_contracts.py --contracts-only
