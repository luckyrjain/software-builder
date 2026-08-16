# Repository-wide phony targets that are easy to miss in the legacy target set.
.PHONY: lint-prd-architect

# Keep the root Makefile as the stable public entry point while the existing
# target definitions remain byte-for-byte in the included core file.
include make/core.mk
