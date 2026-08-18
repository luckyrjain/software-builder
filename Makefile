# Repository-wide phony targets that are easy to miss in the legacy target set.
.PHONY: lint-prd-architect validate-review-contracts

# Keep the root Makefile as the stable public entry point. The included core file
# owns the canonical target graph; narrow repository-wide additive gates may live here.
include make/core.mk

# Extend the canonical lint target without duplicating make/core.mk's prerequisites.
lint: validate-review-contracts

validate-review-contracts:
	@python3 scripts/validate_review_contracts.py --contracts-only
