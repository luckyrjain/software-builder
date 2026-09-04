.PHONY: install install-incident-rca-deps install-claude lint lint-framework lint-pr-review lint-pr-gatekeeper lint-k8s-skill lint-k8s lint-incident-rca lint-incident-triage-agent lint-domain-comprehension lint-squad-map lint-who-owns-x-bot lint-new-hire-guide lint-release-readiness-checker lint-migration-program-manager lint-cost-optimization-sprint-planner lint-mysql-to-postgres-sql lint-loop-task-implementer lint-backlog-runner lint-weekly-squad-digest lint-unit-test-creator lint-integration-test-creator lint-contract-test-creator lint-e2e-test-creator lint-api-test-creator lint-test-writer lint-architecture-review lint-system-design lint-api-design-review lint-database-review lint-security-review lint-performance-review lint-capacity-planner lint-observability-review lint-deployment-risk-review lint-dependency-upgrade-review lint-tech-debt-assessor lint-module-design lint-codebase-architecture-review setup-hooks setup validate-registry validate-operational-upkeep generate generate-check verify-github-ruleset kubesense-errors
.PHONY: lint-change-impact-analyzer
.PHONY: lint-implementation-planner
.PHONY: lint-resilience-review
.PHONY: lint-production-readiness-review
.PHONY: lint-python
.PHONY: validate-agent-skills
.PHONY: validate-hosts
.PHONY: lint-static lint-suites lint-framework-tests lint-scripts-shellcheck lint-platform-files
.PHONY: lint-loop-task-implementer-skill lint-loop-task-implementer-scripts

# ALL_SKILLS (the full skill roster) and every per-skill install-<skill> /
# install-claude-<skill> rule are generated from skills.yaml -- see
# scripts/registry/generate_makefile_roster.py. Regenerate with `make generate`;
# `make generate-check` (part of lint-static) fails if this file drifts. That
# check is the whole drift guard: a generated rule cannot disagree with the
# registry it is generated from, so no separate Makefile-vs-registry validator
# is needed.
#
# `-include`, not `include`: a plain `include` on a missing file aborts Make
# before any target (even `generate`, the documented recovery command) can
# run at all -- deleting this generated file would then have no working
# recovery path. `-include` lets Make continue with ALL_SKILLS undefined;
# lint-framework's own guard below turns that into a clear, actionable error
# instead of a silent empty-roster no-op.
#
# The default goal is pinned before the include: the generated file now carries
# rules, and Make takes its default goal from the first target it reads.
.DEFAULT_GOAL := install
-include make/generated-roster.mk

# Parallelize the dominant pytest suite (scripts/tests/, ~1500 tests) with pytest-xdist
# when it's installed (it's pinned in requirements.lock). Falls back to serial execution
# so `make lint` still works in a bare pytest environment -- xdist's -n flag would
# otherwise error as unrecognized.
#
# Deliberately NOT reused for the smaller per-skill suites (pr-review/tests/,
# k8s-overprovisioning-datadog/tests/, incident-rca/tests/, squad-map/tests/,
# migration-program-manager/tests/): those targets already run concurrently with each
# other and with this one under `make -j` (lint-suites), so each also spawning its own
# `-n auto` (= nproc) worker pool oversubscribes CI runners by up to 6x and was the
# source of sporadic broken-pipe/flaky failures in the dangling-link checker after
# lint-suites moved to `make -j`. Those suites are small enough that make-level
# parallelism across targets is all the parallelism they need.
#
# This suite itself still spawns "-n auto" (= nproc) workers, and it runs concurrently
# with ~18 other lint-suites targets under `make -j"$(nproc)"` (.github/workflows/lint.yml)
# -- so on a runner with N cores, this one target alone can already claim all N workers
# while several sibling targets are also mid-flight, reproducing the same oversubscription
# class the paragraph above fixed for the smaller suites, just for this one instead.
# PYTEST_XDIST_WORKERS lets a caller that's already parallelizing across lint-suites (the
# CI workflow) cap this suite's own worker count instead of always claiming every core;
# plain local `make lint` (no outer -j) leaves it at "auto" and keeps full parallelism.
PYTEST_XDIST_WORKERS ?= auto
# Recursively (not immediately) expanded: the probe spawns a Python interpreter,
# and only the pytest recipe at lint-framework-tests references this. `:=` made
# every `make` invocation pay it, `make install-pr-review` included.
PYTEST_XDIST_FLAG = $(shell python3 -c "import xdist" >/dev/null 2>&1 && echo "-n $(PYTEST_XDIST_WORKERS)" || true)

install:
	bash scripts/install.sh

install-incident-rca-deps:
	bash scripts/install-incident-rca-deps.sh

install-claude:
	bash scripts/install.sh --agent claude-user

setup:
	@echo "setup: installing Python dev dependencies (requirements.lock)"
	@python3 -m pip install --require-hashes -r requirements.lock 2>/dev/null || \
		python3 -m pip install --user --break-system-packages --require-hashes -r requirements.lock
	@$(MAKE) setup-hooks

lint-platform-files:
	@python3 scripts/check_platform_files.py

lint-requirements-lock:
	@python3 scripts/check_requirements_lock.py

lint-python:
	@echo "lint-python: ruff (pyflakes + syntax errors) over the repository"
	@python3 -m ruff check . && echo "  ok"

lint-actions-pinning:
	@python3 scripts/check_pinned_actions.py

lint-actions-security:
	@if command -v zizmor >/dev/null 2>&1; then \
		if [ -n "$$GH_TOKEN" ] || [ -n "$$GITHUB_TOKEN" ]; then \
			if ! output=$$(zizmor .github/workflows 2>&1); then \
				if printf '%s\n' "$$output" | sed 's/\x1b\[[0-9;]*m//g' | grep -q "fatal: no audit was performed"; then \
					printf '%s\n' "$$output" >&2; \
					echo "note: zizmor's online audit failed to reach the GitHub API (transient network/rate-limit issue, not a code finding) — falling back to --no-online-audits so this doesn't block on infrastructure flakiness" >&2; \
					zizmor --no-online-audits .github/workflows; \
				else \
					printf '%s\n' "$$output" >&2; \
					exit 1; \
				fi; \
			else \
				printf '%s\n' "$$output"; \
			fi; \
		else \
			echo "note: no GH_TOKEN/GITHUB_TOKEN set — running zizmor --no-online-audits (some checks skipped locally; CI runs the full set)" >&2; \
			zizmor --no-online-audits .github/workflows; \
		fi; \
	else \
		echo "SKIPPED: zizmor not installed — Actions-YAML security lint did NOT run. Install with 'python3 -m pip install zizmor' (or 'make setup', which installs it from requirements.lock) and re-run. CI always has it installed via requirements.lock, so this gap is local-only." >&2; \
	fi

verify-install:
	@bash scripts/tests/test_install_integration.sh

verify-install-all:
	@bash scripts/tests/test_install_all_skills.sh

verify-github-ruleset:
	@python3 scripts/check_github_ruleset.py

validate-registry:
	@python3 -m scripts.registry validate

validate-agent-skills:
	@python3 -m scripts.registry validate-agent-skills

validate-hosts:
	@python3 -m scripts.registry validate-hosts

backfill-capabilities-check:
	@python3 -m scripts.registry backfill-capabilities --check


validate-evals:
	@python3 -m scripts.evals

validate-operational-upkeep:
	@python3 scripts/operational_upkeep.py validate
	@python3 -m scripts.deprecation_lifecycle
	@python3 scripts/eval_tier_health.py --format markdown >/dev/null
	@python3 scripts/check_changelog_placement.py
	# Advisory only (ADR-0003/0004): always exits 0, never gates lint-static.
	@python3 scripts/check_golden_staleness.py

doctor:
	@python3 scripts/doctor.py

package-release:
	@python3 scripts/package_release.py --output-dir dist

verify-release-tag:
	@test -n "$(TAG)" || (echo "error: set TAG=vX.Y.Z" >&2; exit 1)
	@python3 scripts/verify_release_tag.py "$(TAG)"

validate-release-contract:
	@python3 scripts/release_contract.py

verify-release-bundle:
	@test -n "$(ARCHIVE)" || (echo "error: set ARCHIVE=dist/software-builder-X.Y.Z.tar.gz" >&2; exit 1)
	@python3 scripts/verify_release_bundle.py "$(ARCHIVE)"

generate:
	@python3 -m scripts.registry generate

generate-check:
	@python3 -m scripts.registry generate --check

# ---------------------------------------------------------------------------
# Shared lint helpers — used via $(call ...) inside lint-framework below.
#
# The per-skill structural checks that used to live here as macros (SKILL.md
# length, workflow frontmatter, dangling links, required reference files, the
# framework/setup/safe-output/cross-skill-escalation links, the
# disable-model-invocation gate) now live in scripts/lint_skills.py, which
# drives them from the registry instead of from ~34 hand-written call sites.
#
# The three that remain exist so a failing structural assertion says what it
# wanted. A bare `@grep -q PATTERN FILE` recipe line fails with nothing but
# `make: *** [lint-<skill>] Error 1` -- the `@` suppresses the command echo, so
# neither the file, the pattern, nor the rule is named, and an operator has to
# read this file to find out what broke.
# ---------------------------------------------------------------------------

# $(call require_heading,<file>,<quoted grep pattern>,<heading name>)
define require_heading
	@grep -q $(2) $(1) || \
		{ echo "error: $(1) is missing its $(3) heading" >&2; exit 1; }
endef

# $(call require_content,<file>,<quoted grep pattern>,<what the pattern proves>)
define require_content
	@grep -q $(2) $(1) || \
		{ echo "error: $(1) must document $(3)" >&2; exit 1; }
endef

# $(call require_file,<path>,<why it is required>)
define require_file
	@test -f $(1) || \
		{ echo "error: missing $(1) ($(2))" >&2; exit 1; }
endef

lint: lint-static lint-suites

# CI (.github/workflows/lint.yml) runs lint-static and lint-suites as two parallel jobs:
# lint-static is pure grep/structural checks (no pytest) and fails fast; lint-suites is
# every pytest-bearing target -- the dominant test cost -- and parallelizes it two ways,
# across skills via `make -jN` and, only for the dominant scripts/tests/ suite, within
# it via pytest-xdist (see PYTEST_XDIST_FLAG above). `make lint` still runs both groups
# locally, in this order.
lint-static: lint-platform-files validate-registry validate-agent-skills validate-hosts backfill-capabilities-check generate-check validate-evals validate-operational-upkeep lint-framework lint-incident-triage-agent lint-who-owns-x-bot lint-new-hire-guide lint-release-readiness-checker lint-cost-optimization-sprint-planner lint-backlog-runner lint-test-writer lint-prd-architect lint-architecture-review lint-system-design lint-api-design-review lint-database-review lint-security-review lint-performance-review lint-capacity-planner lint-observability-review lint-deployment-risk-review lint-dependency-upgrade-review lint-tech-debt-assessor lint-module-design lint-codebase-architecture-review lint-requirements-lock lint-python lint-actions-pinning lint-actions-security verify-install verify-install-all validate-review-contracts lint-scripts-shellcheck

lint-scripts-shellcheck:
	@for f in scripts/*.sh; do \
		echo "shellcheck $$f"; \
		if command -v shellcheck >/dev/null 2>&1; then \
			shellcheck "$$f"; \
		elif command -v docker >/dev/null 2>&1; then \
			docker run --rm -v "$(CURDIR):/mnt" -w /mnt koalaman/shellcheck-alpine:stable shellcheck "$$f"; \
		else \
			echo "error: install shellcheck or docker" >&2; \
			exit 1; \
		fi; \
	done

lint-suites: lint-pr-review lint-loop-task-implementer lint-pr-gatekeeper lint-k8s-skill lint-incident-rca lint-domain-comprehension lint-squad-map lint-migration-program-manager lint-mysql-to-postgres-sql lint-weekly-squad-digest lint-unit-test-creator lint-integration-test-creator lint-contract-test-creator lint-e2e-test-creator lint-api-test-creator lint-change-impact-analyzer lint-resilience-review lint-implementation-planner lint-production-readiness-review lint-framework-tests

lint-pr-review: lint-pr-review-skill lint-pr-review-scripts

lint-pr-review-scripts:
	@echo "py_compile pr-review/scripts/diff-to-positions.py pr-review/scripts/github-comment-positions.py pr-review/scripts/github-comment-recovery.py pr-review/scripts/pr_review_policy_guards.py"
	@echo "pytest pr-review/tests/"
	@cache="$(CURDIR)/.pycache-lint-pr-review"; \
	export PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$$cache"; \
	trap 'rm -rf "$$cache"' EXIT; \
	python3 -m py_compile pr-review/scripts/diff-to-positions.py || exit 1; \
	python3 -m py_compile pr-review/scripts/github-comment-positions.py || exit 1; \
	python3 -m py_compile pr-review/scripts/github-comment-recovery.py || exit 1; \
	python3 -m py_compile pr-review/scripts/pr_review_policy_guards.py || exit 1; \
	if python3 -c "import pytest" >/dev/null 2>&1; then \
		python3 -m pytest pr-review/tests/ -q || exit 1; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run script tests" >&2; \
		exit 1; \
	fi

lint-pr-review-skill:
	@python3 scripts/lint_skills.py --skill pr-review
	@echo "lint-pr-review-skill: route-aware workflow contract (workflow_version, phase, produces, consumes checked here too)"
	@python3 -m scripts.validate_workflow_contracts pr-review
	@grep -q 'smoke-test' pr-review/SKILL.md || \
		{ echo "error: pr-review SKILL.md must link to reference/smoke-test.md" >&2; exit 1; }
	@grep -q 'Merge gate' pr-review/workflow/phase-5.md || \
		{ echo "error: phase-5.md must document merge gate checklist" >&2; exit 1; }
	@test -f pr-review/reference/repository-health.md || \
		{ echo "error: missing pr-review/reference/repository-health.md" >&2; exit 1; }
	@test -f pr-review/reference/gold-review-excerpt.md || exit 1
	@test -f pr-review/reference/finding-gates.md || exit 1
	@test -f pr-review/tests/fixtures/phase5-review-metadata.yaml || \
		{ echo "error: missing phase5 review_metadata golden fixture" >&2; exit 1; }
	@grep -q 'Snyk MCP' pr-review/reference/finding-gates.md || \
		{ echo "error: finding-gates.md must document Snyk MCP CVE scan order" >&2; exit 1; }
	@echo "  ok (framework refs)"

lint-pr-gatekeeper:
	@python3 scripts/lint_skills.py --skill pr-gatekeeper
	@echo "lint-pr-gatekeeper: script pytest suite"
	@if python3 -c "import pytest" >/dev/null 2>&1; then \
		python3 -m pytest pr-gatekeeper/tests/ -q || exit 1; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run pr-gatekeeper tests" >&2; \
	fi
	@echo "  ok (framework refs + idempotency tests)"
	@echo "lint-pr-gatekeeper: ask-point drift check (pr-review workflow vs auto-post-policy.md)"
	@python3 pr-gatekeeper/scripts/check-ask-point-drift.py || \
		{ echo "error: pr-review ask-point drift detected — see pr-gatekeeper/reference/auto-post-policy.md" >&2; exit 1; }

lint-k8s-skill:
	@python3 scripts/lint_skills.py --skill k8s-overprovisioning-datadog
	@echo "lint-k8s-skill: route-aware workflow contract (workflow_version, phase, produces, consumes checked here too)"
	@python3 -m scripts.validate_workflow_contracts k8s-overprovisioning-datadog
	@echo "lint-k8s-skill: p95 not positively asserted in memory-sizing section"
	@sec=$$(awk '/^## Memory request utilization/{f=1;next} /^## /{f=0} f' k8s-overprovisioning-datadog/thresholds.md); \
	bad=$$(printf '%s\n' "$$sec" | grep -in 'p95' | grep -ivE 'not|never' || true); \
	if [ -n "$$bad" ]; then \
		echo "error: 'p95' positively asserted in memory-sizing section (memory uses a peak proxy, not p95):" >&2; \
		printf '%s\n' "$$bad" >&2; \
		exit 1; \
	fi; \
	echo "  ok"
	@echo "lint-k8s-skill: decision graph schema (v3)"
	@test -f k8s-overprovisioning-datadog/reference/decision-graph-schema.md || (echo "error: missing decision-graph-schema.md" >&2; exit 1)
	@test -f k8s-overprovisioning-datadog/reference/decision-graph.example.yaml || (echo "error: missing decision-graph.example.yaml" >&2; exit 1)
	@grep -q 'schema_version: 3' k8s-overprovisioning-datadog/reference/decision-graph-schema.md || (echo "error: schema_version 3 not in decision-graph-schema.md" >&2; exit 1)
	@test -f k8s-overprovisioning-datadog/render/markdown.md || (echo "error: missing render/markdown.md" >&2; exit 1)
	@test -f k8s-overprovisioning-datadog/workflow/build-graph.md || (echo "error: missing workflow/build-graph.md" >&2; exit 1)
	@echo "  ok"
	@echo "lint-k8s-skill: report schema + templates"
	@test -f k8s-overprovisioning-datadog/reference/report-schema.md || (echo "error: missing report-schema.md" >&2; exit 1)
	@grep -q 'SCHEMA_VERSION=3' k8s-overprovisioning-datadog/reference/report-schema.md || (echo "error: SCHEMA_VERSION=3 not in report-schema.md" >&2; exit 1)
	@test -f k8s-overprovisioning-datadog/templates/index.md || (echo "error: missing templates/index.md" >&2; exit 1)
	@echo "  ok"
	@echo "lint-k8s-skill: modular templates (Human Report + appendix layouts)"
	@count=$$(ls k8s-overprovisioning-datadog/templates/*.md 2>/dev/null | wc -l | tr -d ' '); \
	if [ "$$count" -lt 14 ]; then \
		echo "error: expected >= 14 template files (incl. human-report.md), found $$count" >&2; exit 1; \
	fi; \
	echo "  ok ($$count files)"
	@grep -q 'assessment_metadata' k8s-overprovisioning-datadog/workflow/report.md || \
		{ echo "error: k8s workflow/report.md must document assessment_metadata footer" >&2; exit 1; }
	@test -f k8s-overprovisioning-datadog/reference/gold-human-report-excerpt.md || exit 1
	@grep -q 'INV-12.*critical' k8s-overprovisioning-datadog/reference/invariants.md || \
		{ echo "error: INV-12 must be critical severity in invariants.md" >&2; exit 1; }
	@grep -q 'delivery_pointer.path' k8s-overprovisioning-datadog/workflow/build-graph.md || \
		{ echo "error: build-graph.md must document delivery_pointer for READY actionable recs" >&2; exit 1; }
	@grep -q 'namespace_ranking' k8s-overprovisioning-datadog/reference/phase-index.md || \
		{ echo "error: phase-index.md must list namespace waste ranking" >&2; exit 1; }
	@grep -q 'APM latency modifier' k8s-overprovisioning-datadog/workflow/reason.md || \
		{ echo "error: reason.md must reference APM latency modifier" >&2; exit 1; }
	@test -f k8s-overprovisioning-datadog/skills-lock.json || exit 1
	@test -f k8s-overprovisioning-datadog/dependencies.md || exit 1
	@grep -q 'next_assessment_due' k8s-overprovisioning-datadog/workflow/report.md || \
		{ echo "error: report.md must document next_assessment_due in history" >&2; exit 1; }
	@echo "  ok"
	@echo "lint-k8s-skill: decision graph invariant validator"
	@cache="$(CURDIR)/.pycache-lint-k8s"; \
	export PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$$cache"; \
	trap 'rm -rf "$$cache"' EXIT; \
	python3 -m py_compile k8s-overprovisioning-datadog/scripts/validate_decision_graph.py || exit 1; \
	for g in k8s-overprovisioning-datadog/reference/decision-graph.example.yaml \
		k8s-overprovisioning-datadog/reference/decision-graph.trim.example.yaml \
		k8s-overprovisioning-datadog/reference/decision-graph.scale-up.example.yaml \
		k8s-overprovisioning-datadog/reference/decision-graph.insufficient-metrics.example.yaml; do \
		python3 k8s-overprovisioning-datadog/scripts/validate_decision_graph.py "$$g" || exit 1; \
	done; \
	if python3 -c "import pytest" >/dev/null 2>&1; then \
		if ! python3 -c "import yaml" >/dev/null 2>&1; then \
			echo "error: PyYAML required for k8s tests — python3 -m pip install pyyaml" >&2; \
			exit 1; \
		fi; \
		python3 -m pytest k8s-overprovisioning-datadog/tests/ -q || exit 1; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run k8s script tests" >&2; \
		exit 1; \
	fi; \
	echo "  ok"

lint-k8s: lint-k8s-skill

lint-incident-rca:
	@python3 scripts/lint_skills.py --skill incident-rca
	@echo "lint-incident-rca: route-aware workflow contract (workflow_version, phase, produces, consumes checked here too)"
	@python3 -m scripts.validate_workflow_contracts incident-rca
	@echo "lint-incident-rca: evidence.example.json parses as JSON"
	@cache="$(CURDIR)/.pycache-lint-rca"; \
	export PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$$cache"; \
	trap 'rm -rf "$$cache"' EXIT; \
	python3 -c "import json,sys; json.load(open('incident-rca/reference/evidence.example.json'))" || \
		{ echo "error: incident-rca/reference/evidence.example.json is not valid JSON" >&2; exit 1; }; \
	echo "  ok"
	@python3 -c "from pathlib import Path; from scripts.registry.schema import load_registry_raw; assert load_registry_raw(Path('skills.yaml'))['skills']['incident-rca']['entrypoint'] == 'SKILL.md'" || \
		{ echo "error: canonical manifest must own incident-rca entrypoint metadata" >&2; exit 1; }
	@grep -q 'dependency_chain' incident-rca/reference/evidence-schema.md || \
		{ echo "error: evidence-schema.md must document dependency_chain" >&2; exit 1; }
	@grep -q 'Body content' incident-rca/report-template.md || \
		{ echo "error: report-template.md Confluence export must map body content" >&2; exit 1; }
	@grep -q 'optionalExternal' incident-rca/skills-lock.json || \
		{ echo "error: incident-rca skills-lock.json must document optional correlator pin" >&2; exit 1; }
	@test -f incident-rca/reference/kubesense-spl.md || \
		{ echo "error: missing incident-rca/reference/kubesense-spl.md" >&2; exit 1; }
	@test -f incident-rca/scripts/kubesense_logs.py || \
		{ echo "error: missing incident-rca/scripts/kubesense_logs.py" >&2; exit 1; }
	@grep -q 'assessment_metadata' incident-rca/workflow/phase-5.md || \
		{ echo "error: incident-rca phase-5 must document assessment_metadata footer" >&2; exit 1; }
	@test -f incident-rca/reference/gold-rca-excerpt.md || exit 1
	@echo "  ok (framework refs)"
	@echo "lint-incident-rca: evidence JSON schema validator"
	@cache="$(CURDIR)/.pycache-lint-rca-schema"; \
	export PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$$cache"; \
	trap 'rm -rf "$$cache"' EXIT; \
	python3 -m py_compile incident-rca/scripts/validate_evidence_json.py || exit 1; \
	python3 -m py_compile incident-rca/scripts/kubesense_logs.py || exit 1; \
	python3 incident-rca/scripts/validate_evidence_json.py \
		incident-rca/reference/evidence.example.json \
		incident-rca/reference/evidence.example.opensearch-query-governance.json || exit 1; \
	python3 -m py_compile incident-rca/scripts/validate_causal_graph.py || exit 1; \
	python3 -m py_compile incident-rca/scripts/incident_rca_policy_guards.py || exit 1; \
	python3 incident-rca/scripts/validate_causal_graph.py \
		incident-rca/reference/causal-graph.example.yaml \
		incident-rca/reference/evidence.example.json || exit 1; \
	python3 -m py_compile incident-rca/scripts/verify_redaction.py || exit 1; \
	python3 incident-rca/scripts/verify_redaction.py \
		incident-rca/reference/evidence.example.json \
		incident-rca/reference/evidence.example.opensearch-query-governance.json || exit 1; \
	if python3 -c "import pytest" >/dev/null 2>&1; then \
		python3 -m pytest incident-rca/tests/ -q || exit 1; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run schema tests" >&2; \
		exit 1; \
	fi; \
	echo "  ok"
	@echo "  ok"

lint-incident-triage-agent:
	@python3 scripts/lint_skills.py --skill incident-triage-agent
	@echo "lint-incident-triage-agent: route-aware workflow contract (workflow_version, phase, produces, consumes checked here too)"
	@python3 -m scripts.validate_workflow_contracts incident-triage-agent

lint-domain-comprehension: lint-domain-comprehension-skill lint-domain-comprehension-scripts

lint-domain-comprehension-scripts:
	@cache="$(CURDIR)/.pycache-lint-dc"; \
	venv="$(CURDIR)/.venv-dc-lint"; \
	export PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$$cache"; \
	trap 'rm -rf "$$cache"' EXIT; \
	if python3 -c "import yaml" >/dev/null 2>&1; then PY=python3; \
	elif [ -x "$(CURDIR)/.venv/bin/python3" ] && "$(CURDIR)/.venv/bin/python3" -c "import yaml" >/dev/null 2>&1; then PY="$(CURDIR)/.venv/bin/python3"; \
	elif [ -x "$$venv/bin/python3" ]; then PY="$$venv/bin/python3"; \
	else python3 -m venv "$$venv" && "$$venv/bin/pip" install -q pyyaml pytest && PY="$$venv/bin/python3"; fi; \
	"$$PY" -m py_compile domain-comprehension/scripts/validate_manifest_yaml.py || exit 1; \
	"$$PY" -m py_compile domain-comprehension/scripts/validate_sub_agent_merge.py || exit 1; \
	"$$PY" domain-comprehension/scripts/validate_manifest_yaml.py \
		domain-comprehension/templates/manifest.yaml || exit 1; \
	echo "lint-domain-comprehension: manifest --check-content fixture"; \
	bash domain-comprehension/tests/fixtures/check-content/prepare.sh; \
	"$$PY" domain-comprehension/scripts/validate_manifest_yaml.py \
		domain-comprehension/tests/fixtures/check-content/manifest.yaml \
		--workspace-root domain-comprehension/tests/fixtures/check-content \
		--check-content || exit 1; \
	"$$PY" domain-comprehension/scripts/validate_sub_agent_merge.py \
		domain-comprehension/tests/fixtures/sub-agent-merge/valid.json || exit 1; \
	if "$$PY" -c "import pytest" >/dev/null 2>&1; then \
		"$$PY" -m pytest domain-comprehension/tests/ -q || exit 1; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run manifest tests" >&2; \
		exit 1; \
	fi; \
	echo "lint-domain-comprehension: shellcheck test scripts"; \
	if command -v shellcheck >/dev/null 2>&1; then \
		shellcheck domain-comprehension/tests/fixtures/check-content/prepare.sh \
			domain-comprehension/tests/run_pressure_tests.sh; \
	elif command -v docker >/dev/null 2>&1; then \
		docker run --rm -v "$(CURDIR):/mnt" -w /mnt koalaman/shellcheck-alpine:stable \
			shellcheck domain-comprehension/tests/fixtures/check-content/prepare.sh \
			domain-comprehension/tests/run_pressure_tests.sh; \
	fi; \
	echo "  ok (manifest validator)"

lint-domain-comprehension-skill:
	@python3 scripts/lint_skills.py --skill domain-comprehension
	@test -f domain-comprehension/templates/manifest.yaml || \
		{ echo "error: missing domain-comprehension/templates/manifest.yaml" >&2; exit 1; }
	@test -f domain-comprehension/templates/BUSINESS_FLOWS.md || exit 1
	@test -f domain-comprehension/templates/KNOWN_OMISSIONS.md || exit 1
	@grep -q 'manifest.yaml' domain-comprehension/SKILL.md || \
		{ echo "error: domain-comprehension SKILL.md must document manifest.yaml" >&2; exit 1; }
	@test -f domain-comprehension/reference/pressure-tests.md || exit 1
	@test -f domain-comprehension/reference/gold-exec-summary-excerpt.md || exit 1
	@test -f domain-comprehension/reference/sub-agent-merge.schema.json || exit 1
	@grep -q 'sub-agent-merge' domain-comprehension/reference/sub-agent-orchestration.md || \
		{ echo "error: sub-agent-orchestration.md must document merge contract" >&2; exit 1; }
	@grep -q 'Runtime validation location' domain-comprehension/workflow/phase-2b.md || \
		{ echo "error: phase-2b.md must normative runtime validation location" >&2; exit 1; }
	@grep -q 'schema_version: 2' domain-comprehension/templates/manifest.yaml || \
		{ echo "error: manifest template must be schema_version 2" >&2; exit 1; }
	@echo "lint-domain-comprehension: pressure harness"
	@bash domain-comprehension/tests/run_pressure_tests.sh
	@echo "  ok"

lint-squad-map:
	@python3 scripts/lint_skills.py --skill squad-map
	@test -f squad-map/templates/SQUAD_MAP.md || \
		{ echo "error: missing squad-map/templates/SQUAD_MAP.md" >&2; exit 1; }
	@test -f squad-map/reference/pressure-tests.md || exit 1
	@test -f squad-map/reference/gold-squad-map-excerpt.md || exit 1
	@grep -q 'monorepo_service_dirs' squad-map/reference/config-schema.md || \
		{ echo "error: config-schema.md must document monorepo_service_dirs mapping" >&2; exit 1; }
	@grep -q '<org_prefix>' squad-map/reference/smoke-test.md || \
		{ echo "error: smoke-test.md must use portable org_prefix placeholder" >&2; exit 1; }
	@grep -q 'Out of scope (archived)' squad-map/workflow/phase-1.md || \
		{ echo "error: phase-1.md must document scope-shrink archival" >&2; exit 1; }
	@test -f squad-map/scripts/squad_mapping.py || exit 1
	@cache="$(CURDIR)/.pycache-lint-squad"; \
	export PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$$cache"; \
	trap 'rm -rf "$$cache"' EXIT; \
	python3 -m py_compile squad-map/scripts/squad_mapping.py || exit 1; \
	if python3 -c "import pytest" >/dev/null 2>&1; then \
		python3 -m pytest squad-map/tests/ -q || exit 1; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run squad-map tests" >&2; \
		exit 1; \
	fi; \
	echo "  ok (framework refs + squad_mapping tests)"

lint-who-owns-x-bot:
	@python3 scripts/lint_skills.py --skill who-owns-x-bot

lint-new-hire-guide:
	@python3 scripts/lint_skills.py --skill new-hire-guide

lint-release-readiness-checker:
	@python3 scripts/lint_skills.py --skill release-readiness-checker

lint-migration-program-manager:
	@python3 scripts/lint_skills.py --skill migration-program-manager
	@test -f migration-program-manager/scripts/aggregate_migration_status.py || \
		{ echo "error: missing migration-program-manager/scripts/aggregate_migration_status.py" >&2; exit 1; }
	@echo "lint-migration-program-manager: aggregator pytest"
	@if python3 -c "import pytest" >/dev/null 2>&1; then \
		python3 -m pytest migration-program-manager/tests/ -q || exit 1; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run migration-program-manager tests" >&2; \
	fi
	@echo "  ok (framework refs + aggregator tests)"

lint-cost-optimization-sprint-planner:
	@python3 scripts/lint_skills.py --skill cost-optimization-sprint-planner

lint-mysql-to-postgres-sql:
	@python3 scripts/lint_skills.py --skill mysql-to-postgres-sql
	@test -f mysql-to-postgres-sql/scripts/scan-mysql-dialect.sh || \
		{ echo "error: missing mysql-to-postgres-sql/scripts/scan-mysql-dialect.sh" >&2; exit 1; }
	@test -f mysql-to-postgres-sql/scripts/scan-report.sh || \
		{ echo "error: missing mysql-to-postgres-sql/scripts/scan-report.sh" >&2; exit 1; }
	@test -f mysql-to-postgres-sql/scripts/mysql-dialect-patterns.sh || \
		{ echo "error: missing mysql-to-postgres-sql/scripts/mysql-dialect-patterns.sh" >&2; exit 1; }
	@test -f mysql-to-postgres-sql/reference/spring-datasource-example.yaml || \
		{ echo "error: missing mysql-to-postgres-sql/reference/spring-datasource-example.yaml" >&2; exit 1; }
	@test -f mysql-to-postgres-sql/reference/skill-contract.md || \
		{ echo "error: missing mysql-to-postgres-sql/reference/skill-contract.md" >&2; exit 1; }
	@test -f mysql-to-postgres-sql/reference/pressure-tests.md || \
		{ echo "error: missing mysql-to-postgres-sql/reference/pressure-tests.md" >&2; exit 1; }
	@test -f mysql-to-postgres-sql/examples.md || \
		{ echo "error: missing mysql-to-postgres-sql/examples.md" >&2; exit 1; }
	@test -f mysql-to-postgres-sql/templates/SERVICE_PG_MIGRATION.md || \
		{ echo "error: missing mysql-to-postgres-sql/templates/SERVICE_PG_MIGRATION.md" >&2; exit 1; }
	@test -f mysql-to-postgres-sql/templates/MIGRATION_STATUS.yaml || \
		{ echo "error: missing mysql-to-postgres-sql/templates/MIGRATION_STATUS.yaml" >&2; exit 1; }
	@test -f mysql-to-postgres-sql/reference/domain-packs/README.md || \
		{ echo "error: missing mysql-to-postgres-sql/reference/domain-packs/README.md" >&2; exit 1; }
	@grep -q 'domain-packs' mysql-to-postgres-sql/SKILL.md || \
		{ echo "error: mysql-to-postgres-sql SKILL.md must reference domain-packs" >&2; exit 1; }
	@grep -q 'MIGRATION_STATUS' mysql-to-postgres-sql/SKILL.md || \
		{ echo "error: mysql-to-postgres-sql SKILL.md must reference MIGRATION_STATUS.yaml" >&2; exit 1; }
	@grep -q 'skill-contract' mysql-to-postgres-sql/SKILL.md || \
		{ echo "error: mysql-to-postgres-sql SKILL.md must link to skill-contract.md" >&2; exit 1; }
	@echo "  ok"
	@echo "lint-mysql-to-postgres-sql: scan fixture + pressure harness"
	@bash mysql-to-postgres-sql/tests/run_pressure_tests.sh
	@cache="$(CURDIR)/.pycache-lint-mysql"; \
	export PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$$cache"; \
	trap 'rm -rf "$$cache"' EXIT; \
	python3 -m py_compile mysql-to-postgres-sql/scripts/ast_check_mysql_dialect.py || exit 1; \
	if python3 -c "import pytest" >/dev/null 2>&1; then \
		python3 -m pytest mysql-to-postgres-sql/tests/test_pressure_policy.py -q || exit 1; \
		if python3 -c "import sqlglot" >/dev/null 2>&1; then \
			python3 -m pytest mysql-to-postgres-sql/tests/test_ast_check_mysql_dialect.py -q || exit 1; \
		else \
			echo "sqlglot not installed — install with 'python3 -m pip install sqlglot' to run the AST secondary-checker tests" >&2; \
			exit 1; \
		fi; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run mysql policy tests" >&2; \
		exit 1; \
	fi; \
	echo "  ok (pressure + pytest + AST checker)"
	@echo "lint-mysql-to-postgres-sql: shellcheck scan + test scripts"
	@if command -v shellcheck >/dev/null 2>&1; then \
		shellcheck -x -P SCRIPTDIR mysql-to-postgres-sql/scripts/scan-mysql-dialect.sh mysql-to-postgres-sql/scripts/scan-report.sh mysql-to-postgres-sql/scripts/mysql-dialect-patterns.sh mysql-to-postgres-sql/tests/run_pressure_tests.sh; \
	elif command -v docker >/dev/null 2>&1; then \
		docker run --rm -v "$(CURDIR):/mnt" -w /mnt koalaman/shellcheck-alpine:stable \
			shellcheck -x -P SCRIPTDIR mysql-to-postgres-sql/scripts/scan-mysql-dialect.sh mysql-to-postgres-sql/scripts/scan-report.sh mysql-to-postgres-sql/scripts/mysql-dialect-patterns.sh mysql-to-postgres-sql/tests/run_pressure_tests.sh; \
	else \
		echo "error: install shellcheck or docker" >&2; exit 1; \
	fi
	@echo "  ok (framework refs + shellcheck)"

lint-loop-task-implementer: lint-loop-task-implementer-skill lint-loop-task-implementer-scripts

# Mirrors lint-pr-review-scripts: the skill ships a validator, so its own tests are
# co-located with it and run from the target that lints it.
lint-loop-task-implementer-scripts:
	@echo "py_compile loop-task-implementer/scripts/validate_loop_lifecycle.py"
	@echo "pytest loop-task-implementer/tests/"
	@cache="$(CURDIR)/.pycache-lint-loop-task-implementer"; \
	export PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$$cache"; \
	trap 'rm -rf "$$cache"' EXIT; \
	python3 -m py_compile loop-task-implementer/scripts/validate_loop_lifecycle.py || exit 1; \
	if python3 -c "import pytest" >/dev/null 2>&1; then \
		python3 -m pytest loop-task-implementer/tests/ -q || exit 1; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run script tests" >&2; \
		exit 1; \
	fi

lint-loop-task-implementer-skill:
	@python3 scripts/lint_skills.py --skill loop-task-implementer
	@echo "lint-loop-task-implementer: required files"
	@for f in SETUP.md README.md examples.md report-template.md; do \
		test -f loop-task-implementer/$$f || \
			{ echo "error: missing loop-task-implementer/$$f" >&2; exit 1; }; \
	done
	@test -f loop-task-implementer/reference/state-schema.yaml || \
		{ echo "error: missing loop-task-implementer/reference/state-schema.yaml" >&2; exit 1; }

lint-backlog-runner:
	@python3 scripts/lint_skills.py --skill backlog-runner

lint-weekly-squad-digest:
	@python3 scripts/lint_skills.py --skill weekly-squad-digest
	@test -f weekly-squad-digest/scripts/digest_grouping.py || \
		{ echo "error: missing weekly-squad-digest/scripts/digest_grouping.py" >&2; exit 1; }
	@echo "lint-weekly-squad-digest: digest_grouping pytest"
	@if python3 -c "import pytest" >/dev/null 2>&1; then \
		python3 -m pytest weekly-squad-digest/tests/ -q || exit 1; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run weekly-squad-digest tests" >&2; \
	fi
	@echo "  ok (framework refs + digest_grouping tests)"

define LINT_TEST_CREATOR_TARGET
lint-$(1):
	@python3 scripts/lint_skills.py --skill $(1)
	@echo "lint-$(1): detection scripts + test-creation-principles contract"
	@for f in $(2); do \
		test -f $(1)/scripts/$$$$f || \
			{ echo "error: missing $(1)/scripts/$$$$f" >&2; exit 1; }; \
	done
	@grep -q 'docs/skill-framework/shared/test-creation-principles.md' $(1)/reference/skill-contract.md || \
		{ echo "error: $(1)/reference/skill-contract.md must link to shared test-creation-principles" >&2; exit 1; }
	@echo "  ok (framework refs)"
	@echo "lint-$(1): shellcheck scan"
	@if command -v shellcheck >/dev/null 2>&1; then \
		shellcheck -x -P SCRIPTDIR $(1)/scripts/*.sh; \
	elif command -v docker >/dev/null 2>&1; then \
		docker run --rm -v "$(CURDIR):/mnt" -w /mnt koalaman/shellcheck-alpine:stable \
			shellcheck -x -P SCRIPTDIR $(1)/scripts/*.sh; \
	else \
		echo "error: install shellcheck or docker" >&2; exit 1; \
	fi
	@echo "  ok (shellcheck)"
	@echo "lint-$(1): detection script pytest suite"
	@cache="$(CURDIR)/.pycache-lint-$(1)"; \
	export PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$$$$cache"; \
	trap 'rm -rf "$$$$cache"' EXIT; \
	if python3 -c "import pytest" >/dev/null 2>&1; then \
		python3 -m pytest $(1)/tests/$(3) -q || exit 1; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run $(1)'s own suite" >&2; \
		exit 1; \
	fi; \
	echo "  ok (pytest)"
endef

$(eval $(call LINT_TEST_CREATOR_TARGET,unit-test-creator,detect-test-framework.sh test-framework-markers.sh,test_detect_test_framework.py))
$(eval $(call LINT_TEST_CREATOR_TARGET,integration-test-creator,detect-integration-setup.sh integration-markers.sh,test_detect_integration_setup.py))
$(eval $(call LINT_TEST_CREATOR_TARGET,contract-test-creator,detect-pact-tooling.sh pact-markers.sh,test_detect_pact_tooling.py))
$(eval $(call LINT_TEST_CREATOR_TARGET,e2e-test-creator,detect-e2e-tooling.sh e2e-markers.sh,test_detect_e2e_tooling.py))
$(eval $(call LINT_TEST_CREATOR_TARGET,api-test-creator,detect-postman-tooling.sh postman-markers.sh,test_detect_postman_tooling.py))

# All five test-creator skills (api, contract, e2e, integration, unit) have a safe-output boundary
# (their own *_TEST_REPORT.md render surface) — these are EXTRA prerequisites on top of the shared
# LINT_TEST_CREATOR_TARGET macro above, not a change to the macro itself.
#
# scripts/lint_skills.py now owns that boundary along with the rest of the shared per-skill set, so
# each of these is a thin alias for it. They are kept as their own targets because the names are
# public API (scripts/README.md) and because a maintainer touching one skill's render surface can
# still run just that skill's checks; the cost is that `make lint-<x>-test-creator` runs the shared
# checker twice, once here and once from the macro-generated recipe.
lint-api-test-creator: lint-api-test-creator-safe-output

lint-api-test-creator-safe-output:
	@python3 scripts/lint_skills.py --skill api-test-creator

lint-contract-test-creator: lint-contract-test-creator-safe-output

lint-contract-test-creator-safe-output:
	@python3 scripts/lint_skills.py --skill contract-test-creator

lint-e2e-test-creator: lint-e2e-test-creator-safe-output

lint-e2e-test-creator-safe-output:
	@python3 scripts/lint_skills.py --skill e2e-test-creator

lint-integration-test-creator: lint-integration-test-creator-safe-output

lint-integration-test-creator-safe-output:
	@python3 scripts/lint_skills.py --skill integration-test-creator

lint-unit-test-creator: lint-unit-test-creator-safe-output

lint-unit-test-creator-safe-output:
	@python3 scripts/lint_skills.py --skill unit-test-creator

lint-test-writer:
	@python3 scripts/lint_skills.py --skill test-writer
	@echo "lint-test-writer: no detection/generation scripts (router only)"
	@if [ -d test-writer/scripts ] || [ -d test-writer/tests ]; then \
		echo "error: test-writer must not have scripts/ or tests/ — it is a router with no detection/generation logic of its own" >&2; exit 1; \
	fi
	@test -f test-writer/examples.md || \
		{ echo "error: missing test-writer/examples.md" >&2; exit 1; }

lint-prd-architect:
	@python3 scripts/lint_skills.py --skill prd-architect
	@echo "lint-prd-architect: route-aware workflow contract (workflow_version, phase, produces, consumes checked here too)"
	@python3 -m scripts.validate_workflow_contracts prd-architect
	@test -f prd-architect/report-template.md || \
		{ echo "error: missing prd-architect/report-template.md" >&2; exit 1; }
	@test -f prd-architect/prd-architect.eval.md || \
		{ echo "error: missing prd-architect/prd-architect.eval.md" >&2; exit 1; }
	@test -f prd-architect/scripts/prd_safe_output.py || \
		{ echo "error: missing prd-architect safe-output renderer" >&2; exit 1; }
	@test -f prd-architect/examples.md || \
		{ echo "error: missing prd-architect/examples.md" >&2; exit 1; }
	@grep -q 'smoke-test' prd-architect/SKILL.md || \
		{ echo "error: prd-architect/SKILL.md must link to reference/smoke-test.md" >&2; exit 1; }

lint-architecture-review:
	@python3 scripts/lint_skills.py --skill architecture-review

lint-system-design:
	@python3 scripts/lint_skills.py --skill system-design

lint-api-design-review:
	@python3 scripts/lint_skills.py --skill api-design-review

lint-database-review:
	@python3 scripts/lint_skills.py --skill database-review

lint-security-review:
	@python3 scripts/lint_skills.py --skill security-review

lint-performance-review:
	@python3 scripts/lint_skills.py --skill performance-review

lint-capacity-planner:
	@python3 scripts/lint_skills.py --skill capacity-planner

lint-observability-review:
	@python3 scripts/lint_skills.py --skill observability-review

lint-deployment-risk-review:
	@python3 scripts/lint_skills.py --skill deployment-risk-review

lint-dependency-upgrade-review:
	@python3 scripts/lint_skills.py --skill dependency-upgrade-review

lint-tech-debt-assessor:
	@python3 scripts/lint_skills.py --skill tech-debt-assessor

lint-module-design:
	@python3 scripts/lint_skills.py --skill module-design
	@echo "lint-module-design: required SKILL.md headings"
	@for heading in \
		"## When to use / NOT to use" "## Deliverable" "## Required inputs" \
		"## Prerequisites" "## Workflow" "## Boundary rules" \
		"## Cross-skill escalation" "## Framework" "## Begin"; do \
		grep -Fqx "$$heading" module-design/SKILL.md || \
			{ echo "error: module-design/SKILL.md must contain heading $$heading" >&2; exit 1; }; \
	done
	@echo "  ok"

lint-codebase-architecture-review:
	@python3 scripts/lint_skills.py --skill codebase-architecture-review
	@echo "lint-codebase-architecture-review: required SKILL.md headings"
	@for heading in \
		"## When to use / NOT to use" "## Deliverable" "## Scope and prerequisites" \
		"## Workflow" "## Candidate rules" "## Cross-skill boundary" \
		"## Framework" "## Begin"; do \
		grep -Fqx "$$heading" codebase-architecture-review/SKILL.md || \
			{ echo "error: codebase-architecture-review/SKILL.md must contain heading $$heading" >&2; exit 1; }; \
	done
	@echo "lint-codebase-architecture-review: balanced report-format fenced code blocks"
	@python3 -c 'import sys; from pathlib import Path; from scripts.reference_utils import has_unclosed_fenced_code_block; path = Path(sys.argv[1]); sys.exit(f"error: {path}: unclosed fenced code block" if has_unclosed_fenced_code_block(path.read_text()) else 0)' codebase-architecture-review/reference/report-format.md
	@echo "  ok"

lint-change-impact-analyzer:
	@python3 scripts/lint_skills.py --skill change-impact-analyzer
	@python3 -m py_compile scripts/change_impact.py
	@python3 -m pytest scripts/tests/test_change_impact_analyzer.py -q
	@echo "  ok"

lint: lint-change-impact-analyzer
lint: lint-resilience-review

lint: lint-implementation-planner

lint-implementation-planner:
	@python3 scripts/lint_skills.py --skill implementation-planner
	@python3 -m py_compile scripts/implementation_plan.py
	@python3 -m pytest scripts/tests/test_implementation_plan.py -q
	@echo "  ok"

lint-resilience-review:
	@python3 scripts/lint_skills.py --skill resilience-review
	@python3 -m py_compile scripts/resilience_review.py
	@python3 -m pytest scripts/tests/test_resilience_review.py -q
	@echo "  ok"

lint: lint-production-readiness-review

lint-production-readiness-review:
	@python3 scripts/lint_skills.py --skill production-readiness-review
	@python3 -m py_compile scripts/production_readiness.py
	@python3 -m pytest scripts/tests/test_production_readiness_contract.py -q
	@echo "  ok"

lint-framework:
	@test -n "$(ALL_SKILLS)" || \
		{ echo "error: ALL_SKILLS is empty/undefined -- make/generated-roster.mk is missing or stale; run 'make generate' to regenerate it" >&2; exit 1; }
	@echo "lint-framework: shared docs present"
	$(call require_file,docs/skill-framework/README.md,the shared framework index)
	@for f in confidence-bands cross-skill-escalation post-action-templates \
		smoke-test-conventions examples-conventions phase-glossary review-metadata-schema \
		skill-routing prompt-injection claude-code-setup org-rollup-schema test-creation-principles \
		setup-freshness; do \
		test -f docs/skill-framework/shared/$$f.md || exit 1; \
		test -s docs/skill-framework/shared/$$f.md || \
			{ echo "error: docs/skill-framework/shared/$$f.md is empty" >&2; exit 1; }; \
	done
	$(call require_content,docs/skill-framework/README.md,'confidence-bands',the confidence-bands contract)
	@echo "lint-framework: required sections"
	$(call require_heading,docs/skill-framework/shared/confidence-bands.md,'^## 1\. Purpose',1. Purpose)
	$(call require_heading,docs/skill-framework/shared/confidence-bands.md,'^## 7\. Anti-patterns',7. Anti-patterns)
	$(call require_heading,docs/skill-framework/shared/cross-skill-escalation.md,'^## 1\. Symmetric matrix',1. Symmetric matrix)
	$(call require_content,docs/skill-framework/shared/cross-skill-escalation.md,'User prompt template',the user prompt template)
	$(call require_heading,docs/skill-framework/shared/post-action-templates.md,'^## 7\. Confirmation gates',7. Confirmation gates)
	$(call require_content,docs/skill-framework/shared/post-action-templates.md,'Jira ticket update fields',the Jira ticket update fields)
	$(call require_heading,docs/skill-framework/shared/smoke-test-conventions.md,'^## 5\. Failure diagnosis',5. Failure diagnosis)
	$(call require_content,docs/skill-framework/shared/smoke-test-conventions.md,'Invocation string',the invocation string convention)
	$(call require_content,docs/skill-framework/shared/examples-conventions.md,'Invocation table template',the invocation table template)
	$(call require_heading,docs/skill-framework/shared/examples-conventions.md,'^## 1\. Required sections',1. Required sections)
	$(call require_heading,docs/skill-framework/shared/examples-conventions.md,'^## 2\. Scenario format',2. Scenario format)
	$(call require_heading,docs/skill-framework/shared/examples-conventions.md,'^## 5\. Anti-patterns',5. Anti-patterns)
	@for skill in $(ALL_SKILLS); do \
		test -f $$skill/examples.md || \
			{ echo "error: missing $$skill/examples.md (examples-conventions)" >&2; exit 1; }; \
		grep -q '## Invocation' $$skill/examples.md || \
			{ echo "error: $$skill/examples.md must have Invocation section" >&2; exit 1; }; \
	done
	$(call require_heading,docs/skill-framework/shared/phase-glossary.md,'^## 5\. Cross-skill analogies',5. Cross-skill analogies)
	$(call require_content,docs/skill-framework/shared/phase-glossary.md,'MCP profile',the MCP profile)
	$(call require_content,docs/skill-framework/shared/phase-glossary.md,'Minimum evidence gate',the minimum evidence gate)
	$(call require_heading,docs/skill-framework/shared/review-metadata-schema.md,'^## 3\. `history` block',3. history block)
	$(call require_heading,docs/skill-framework/shared/review-metadata-schema.md,'^## 8\. `assessment_metadata`',8. assessment_metadata)
	$(call require_content,docs/skill-framework/shared/review-metadata-schema.md,'investigation_quality',the investigation_quality field)
	$(call require_content,docs/skill-framework/shared/review-metadata-schema.md,'repository_health',the repository_health field)
	$(call require_heading,docs/skill-framework/shared/prompt-injection.md,'^## Rule',Rule)
	$(call require_content,docs/skill-framework/shared/review-metadata-schema.md,'incident-rca.*Phase 2',incident-rca's Phase 2 metadata)
	$(call require_content,docs/skill-framework/shared/confidence-bands.md,'domain-comprehension',domain-comprehension's bands)
	$(call require_content,docs/skill-framework/shared/confidence-bands.md,'mysql-to-postgres-sql',mysql-to-postgres-sql's bands)
	$(call require_content,docs/skill-framework/shared/confidence-bands.md,'risk tier',the risk tier mapping)
	$(call require_heading,docs/skill-framework/shared/review-metadata-schema.md,'### 8.3 domain-comprehension',8.3 domain-comprehension)
	$(call require_heading,docs/skill-framework/shared/review-metadata-schema.md,'### 8.4 squad-map',8.4 squad-map)
	$(call require_heading,docs/skill-framework/shared/review-metadata-schema.md,'### 8.5 mysql-to-postgres-sql',8.5 mysql-to-postgres-sql)
	$(call require_content,docs/skill-framework/shared/phase-glossary.md,'mysql-to-postgres-sql mapping',the mysql-to-postgres-sql mapping)
	$(call require_content,docs/skill-framework/shared/post-action-templates.md,'squad map complete',the squad-map completion template)
	@grep -q 'kubesense-alerts' docs/skill-framework/shared/cross-skill-escalation.md || \
		{ echo "error: cross-skill-escalation must include kubesense-alerts handoff" >&2; exit 1; }
	@grep -q 'MYSQL_TO_PG_SQL_REWRITES' docs/skill-framework/shared/cross-skill-escalation.md || \
		{ echo "error: cross-skill-escalation must include mysql artifact handoff block" >&2; exit 1; }
	@grep -q 'Approach B' docs/skill-framework/README.md || \
		{ echo "error: skill-framework README must document deferred Approach B" >&2; exit 1; }
	$(call require_file,domain-comprehension/reference/assessment-metadata.md,assessment-metadata contract)
	$(call require_file,squad-map/reference/assessment-metadata.md,assessment-metadata contract)
	$(call require_file,mysql-to-postgres-sql/reference/assessment-metadata.md,assessment-metadata contract)
	$(call require_content,docs/skill-framework/README.md,'review-metadata-schema',the review-metadata schema)
	@echo "lint-framework: SETUP.md freshness tables"
	@python3 scripts/validate_setup_freshness.py
	@echo "  ok"
	@echo "lint-framework: dangling markdown links"
	@python3 scripts/validate_references.py --files docs/skill-framework/README.md docs/skill-framework/shared/*.md && echo "  ok" || \
		{ echo "error: dangling reference link(s) in docs/skill-framework" >&2; exit 1; }
	@fail=0; \
	for f in confidence-bands cross-skill-escalation post-action-templates \
		smoke-test-conventions examples-conventions phase-glossary; do \
		if grep -qiE 'stub outline|TBD|TODO' docs/skill-framework/shared/$$f.md; then \
			echo "error: docs/skill-framework/shared/$$f.md contains stub/TBD/TODO language" >&2; \
			fail=1; \
		fi; \
	done; \
	if [ "$$fail" -ne 0 ]; then exit 1; fi
	$(call require_content,docs/skill-framework/README.md,'| Complete |',a Complete status row)
	@for skill in $(ALL_SKILLS); do \
		grep -q 'skill-framework' $$skill/SETUP.md || \
			{ echo "error: $$skill/SETUP.md must link to docs/skill-framework" >&2; exit 1; }; \
		grep -q 'docs/skill-framework/shared/skill-routing.md' $$skill/SKILL.md || \
			{ echo "error: $$skill/SKILL.md must link to shared skill-routing" >&2; exit 1; }; \
		grep -q 'docs/skill-framework/shared/prompt-injection.md' $$skill/SKILL.md || \
			{ echo "error: $$skill/SKILL.md must link to shared prompt-injection" >&2; exit 1; }; \
	done
	@echo "lint-framework: first-ingest untrusted-content wiring"
	@fail=0; \
	for pair in \
		"pr-review:workflow/inputs.md" \
		"pr-gatekeeper:workflow/inputs.md" \
		"incident-rca:workflow/inputs.md" \
		"incident-triage-agent:workflow/inputs.md" \
		"k8s-overprovisioning-datadog:workflow/collect-metrics.md" \
		"domain-comprehension:workflow/session-0.md" \
		"squad-map:workflow/inputs.md" \
		"who-owns-x-bot:workflow/inputs.md" \
		"new-hire-guide:workflow/inputs.md" \
		"release-readiness-checker:workflow/inputs.md" \
		"migration-program-manager:workflow/inputs.md" \
		"cost-optimization-sprint-planner:workflow/inputs.md" \
		"mysql-to-postgres-sql:workflow/migrate-service.md" \
		"loop-task-implementer:workflow/orchestrator.md" \
		"backlog-runner:workflow/inputs.md" \
		"weekly-squad-digest:workflow/inputs.md" \
		"test-writer:workflow/inputs.md" \
		"unit-test-creator:workflow/inputs.md" \
		"integration-test-creator:workflow/inputs.md" \
		"contract-test-creator:workflow/inputs.md" \
		"e2e-test-creator:workflow/inputs.md" \
		"api-test-creator:workflow/inputs.md" \
		"architecture-review:workflow/inputs.md" \
		"system-design:workflow/inputs.md" \
		"api-design-review:workflow/inputs.md" \
		"database-review:workflow/inputs.md" \
		"security-review:workflow/inputs.md" \
		"performance-review:workflow/inputs.md" \
		"capacity-planner:workflow/inputs.md" \
		"observability-review:workflow/inputs.md" \
		"deployment-risk-review:workflow/inputs.md" \
		"dependency-upgrade-review:workflow/inputs.md" \
		"tech-debt-assessor:workflow/inputs.md" \
		"change-impact-analyzer:workflow/inputs.md" \
		"resilience-review:workflow/inputs.md" \
		"implementation-planner:workflow/inputs.md" \
		"production-readiness-review:workflow/inputs.md"; do \
		skill=$${pair%%:*}; file=$${pair#*:}; \
		if ! grep -qiE 'untrusted|prompt-injection' $$skill/$$file; then \
			echo "error: $$skill/$$file must declare untrusted-content guard" >&2; fail=1; \
		fi; \
	done; \
	if [ "$$fail" -ne 0 ]; then exit 1; fi
	@echo "lint-framework: PRD rendered-output safety wiring"
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' prd-architect/workflow/gate.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' prd-architect/workflow/gate.md && \
	 grep -qi 'source_material' prd-architect/workflow/gate.md && \
	 grep -qiE 'escape|fence' prd-architect/workflow/gate.md && \
	 grep -qi 'redact' prd-architect/workflow/gate.md || \
		{ echo "error: prd-architect Gate must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "lint-framework: all SETUP.md links ok"
	@echo "lint-framework: cross-agent discovery files (.cursor/rules + .kiro/steering)"
	@fail=0; \
	for skill in $(ALL_SKILLS); do \
		test -f .cursor/rules/$$skill.mdc || \
			{ echo "  missing .cursor/rules/$$skill.mdc" >&2; fail=1; }; \
		test -f .kiro/steering/$$skill.md || \
			{ echo "  missing .kiro/steering/$$skill.md" >&2; fail=1; }; \
	done; \
	if [ "$$fail" -ne 0 ]; then echo "error: every skill needs a Cursor rule and Kiro steering discovery file" >&2; exit 1; fi; \
	echo "  ok"
	@echo "lint-framework: metadata footer examples present"
	@for f in review-metadata.example.yaml assessment-metadata-rca.example.yaml \
		assessment-metadata-k8s.example.yaml; do \
		test -f docs/skill-framework/shared/examples/$$f || exit 1; \
	done
	@echo "lint-framework: metadata footer validator"
	@cache="$(CURDIR)/.pycache-lint-framework"; \
	export PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$$cache"; \
	trap 'rm -rf "$$cache"' EXIT; \
	python3 -m py_compile scripts/validate_metadata_footer.py || exit 1; \
	python3 scripts/validate_metadata_footer.py \
		docs/skill-framework/shared/examples/review-metadata.example.yaml \
		docs/skill-framework/shared/examples/assessment-metadata-rca.example.yaml \
		docs/skill-framework/shared/examples/assessment-metadata-k8s.example.yaml \
		pr-review/tests/fixtures/phase5-review-metadata.yaml || exit 1
	@echo "lint-framework: source-tree reference validation (anchors + local links, cross-cutting docs)"
	@python3 scripts/validate_references.py --source-tree . --exclude docs/superpowers --exclude .claude/worktrees || exit 1
	@echo "lint-framework: ok"

# Split out from lint-framework: this is the repo's dominant test cost (the shared
# scripts/tests/ suite, ~1700 tests covering registry/eval/operational-upkeep/metadata
# logic) so CI can schedule it as its own parallel job instead of serializing it after
# lint-framework's cheap doc/structure checks.
lint-framework-tests:
	@echo "lint-framework-tests: scripts/tests/ suite"
	@if python3 -c "import pytest" >/dev/null 2>&1; then \
		python3 -m pytest $(PYTEST_XDIST_FLAG) scripts/tests/ -q || exit 1; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run metadata footer tests" >&2; \
	fi

# Fetch KubeSense error logs with full body via SPL REST API.
# Example: make kubesense-errors WORKLOAD=autodebit-service CLUSTER=acme-neo-prod-eks-cluster
kubesense-errors:
	@test -n "$(WORKLOAD)" || { echo "error: set WORKLOAD=<k8s-workload>" >&2; exit 1; }
	@args="$(WORKLOAD)"; \
	if [ -n "$(CLUSTER)" ]; then args="$$args --cluster $(CLUSTER)"; fi; \
	if [ -n "$(NAMESPACE)" ]; then args="$$args --namespace $(NAMESPACE)"; fi; \
	if [ -n "$(FROM)" ]; then args="$$args --from $(FROM)"; fi; \
	if [ -n "$(TO)" ]; then args="$$args --to $(TO)"; fi; \
	if [ -n "$(LIMIT)" ]; then args="$$args --limit $(LIMIT)"; fi; \
	if [ -n "$(EVIDENCE)" ]; then args="$$args --evidence"; fi; \
	python3 incident-rca/scripts/kubesense_logs.py $$args

setup-hooks:
	git config core.hooksPath .githooks
	@echo "Git hooks enabled (.githooks/pre-commit runs shellcheck on staged scripts/*.sh)"
