# Repository-wide phony targets that are easy to miss in the legacy target set.
.PHONY: lint-prd-architect validate-review-contracts lint-loop-task-implementer-tests

# Keep the root Makefile as the stable public entry point. The included core file
# owns the canonical target graph; narrow repository-wide additive gates may live here.
include make/core.mk

# Keep validate-operational-upkeep visible in the first textual lint rule for the
# repository's makefile-graph guard, while adding the review-contract gate. Make
# merges this rule with make/core.mk's canonical lint prerequisites and executes a
# duplicated prerequisite only once.
lint: validate-operational-upkeep validate-review-contracts

# Extend the included skill target without duplicating its recipe: GNU Make merges
# this prerequisite-only rule with make/core.mk's lint-loop-task-implementer rule.
# Every Batch 5.2C regression therefore runs both from the targeted lint command and
# from the repository-wide `make lint` used by CI.
lint-loop-task-implementer: lint-loop-task-implementer-tests

lint-loop-task-implementer-tests:
	@python3 -m pytest -p no:cacheprovider scripts/tests/test_batch5_2c_*.py -q

validate-review-contracts:
	@python3 scripts/validate_review_contracts.py --contracts-only
