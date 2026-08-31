.PHONY: install install-pr-review install-pr-gatekeeper install-k8s-overprovisioning install-incident-rca install-incident-rca-deps install-incident-triage-agent install-domain-comprehension install-squad-map install-who-owns-x-bot install-new-hire-guide install-release-readiness-checker install-migration-program-manager install-cost-optimization-sprint-planner install-mysql-to-postgres-sql install-loop-task-implementer install-backlog-runner install-weekly-squad-digest install-unit-test-creator install-integration-test-creator install-contract-test-creator install-e2e-test-creator install-api-test-creator install-test-writer install-prd-architect install-architecture-review install-system-design install-api-design-review install-database-review install-security-review install-performance-review install-capacity-planner install-observability-review install-deployment-risk-review install-dependency-upgrade-review install-tech-debt-assessor install-claude install-claude-pr-review install-claude-pr-gatekeeper install-claude-k8s-overprovisioning install-claude-incident-rca install-claude-incident-triage-agent install-claude-domain-comprehension install-claude-squad-map install-claude-who-owns-x-bot install-claude-new-hire-guide install-claude-release-readiness-checker install-claude-migration-program-manager install-claude-cost-optimization-sprint-planner install-claude-mysql-to-postgres-sql install-claude-loop-task-implementer install-claude-backlog-runner install-claude-weekly-squad-digest install-claude-unit-test-creator install-claude-integration-test-creator install-claude-contract-test-creator install-claude-e2e-test-creator install-claude-api-test-creator install-claude-prd-architect install-claude-test-writer install-claude-architecture-review install-claude-system-design install-claude-api-design-review install-claude-database-review install-claude-security-review install-claude-performance-review install-claude-capacity-planner install-claude-observability-review install-claude-deployment-risk-review install-claude-dependency-upgrade-review install-claude-tech-debt-assessor lint lint-framework lint-pr-review lint-pr-gatekeeper lint-k8s-skill lint-k8s lint-incident-rca lint-incident-triage-agent lint-domain-comprehension lint-squad-map lint-who-owns-x-bot lint-new-hire-guide lint-release-readiness-checker lint-migration-program-manager lint-cost-optimization-sprint-planner lint-mysql-to-postgres-sql lint-loop-task-implementer lint-backlog-runner lint-weekly-squad-digest lint-unit-test-creator lint-integration-test-creator lint-contract-test-creator lint-e2e-test-creator lint-api-test-creator lint-test-writer lint-architecture-review lint-system-design lint-api-design-review lint-database-review lint-security-review lint-performance-review lint-capacity-planner lint-observability-review lint-deployment-risk-review lint-dependency-upgrade-review lint-tech-debt-assessor setup-hooks setup validate-registry validate-operational-upkeep generate generate-check verify-github-ruleset kubesense-errors
.PHONY: install-change-impact-analyzer
.PHONY: lint-change-impact-analyzer
.PHONY: install-implementation-planner
.PHONY: lint-implementation-planner
.PHONY: lint-resilience-review
.PHONY: install-resilience-review
.PHONY: install-production-readiness-review
.PHONY: lint-production-readiness-review
.PHONY: install-claude-production-readiness-review
.PHONY: install-claude-change-impact-analyzer
.PHONY: install-claude-implementation-planner
.PHONY: install-claude-resilience-review
.PHONY: lint-python
.PHONY: validate-agent-skills
.PHONY: validate-hosts
.PHONY: lint-static lint-suites lint-framework-tests lint-scripts-shellcheck

# Parallelize the larger pytest suites with pytest-xdist when it's installed (it's pinned
# in requirements.lock). Falls back to serial execution so `make lint` still works in a
# bare pytest environment -- xdist's -n flag would otherwise error as unrecognized.
PYTEST_XDIST_FLAG := $(shell python3 -c "import xdist" >/dev/null 2>&1 && echo "-n auto" || true)

install:
	bash scripts/install.sh

install-pr-review:
	bash scripts/install.sh pr-review

install-pr-gatekeeper: install-pr-review
	bash scripts/install.sh pr-gatekeeper

install-k8s-overprovisioning:
	bash scripts/install.sh k8s-overprovisioning-datadog

install-incident-rca-deps:
	bash scripts/install-incident-rca-deps.sh

install-incident-rca: install-incident-rca-deps
	bash scripts/install.sh incident-rca

install-incident-triage-agent: install-incident-rca install-squad-map
	bash scripts/install.sh incident-triage-agent

install-domain-comprehension: install-squad-map
	bash scripts/install.sh domain-comprehension

install-squad-map:
	bash scripts/install.sh squad-map

install-who-owns-x-bot: install-squad-map
	bash scripts/install.sh who-owns-x-bot

install-new-hire-guide: install-domain-comprehension install-squad-map
	bash scripts/install.sh new-hire-guide

install-release-readiness-checker: install-pr-review install-k8s-overprovisioning install-incident-rca
	bash scripts/install.sh release-readiness-checker

install-migration-program-manager: install-mysql-to-postgres-sql install-squad-map
	bash scripts/install.sh migration-program-manager

install-cost-optimization-sprint-planner: install-k8s-overprovisioning install-squad-map
	bash scripts/install.sh cost-optimization-sprint-planner

install-mysql-to-postgres-sql:
	bash scripts/install.sh mysql-to-postgres-sql

install-loop-task-implementer:
	bash scripts/install.sh loop-task-implementer

install-backlog-runner: install-loop-task-implementer
	bash scripts/install.sh backlog-runner

install-weekly-squad-digest: install-migration-program-manager install-cost-optimization-sprint-planner
	bash scripts/install.sh weekly-squad-digest

install-unit-test-creator:
	bash scripts/install.sh unit-test-creator

install-integration-test-creator:
	bash scripts/install.sh integration-test-creator

install-contract-test-creator:
	bash scripts/install.sh contract-test-creator

install-e2e-test-creator:
	bash scripts/install.sh e2e-test-creator

install-api-test-creator:
	bash scripts/install.sh api-test-creator

install-prd-architect:
	bash scripts/install.sh prd-architect

install-test-writer: install-unit-test-creator install-integration-test-creator install-contract-test-creator install-e2e-test-creator install-api-test-creator
	bash scripts/install.sh test-writer

install-claude:
	bash scripts/install.sh --agent claude-user

install-claude-pr-review:
	bash scripts/install.sh --agent claude-user pr-review

install-claude-pr-gatekeeper: install-claude-pr-review
	bash scripts/install.sh --agent claude-user pr-gatekeeper

install-claude-k8s-overprovisioning:
	bash scripts/install.sh --agent claude-user k8s-overprovisioning-datadog

install-claude-incident-rca: install-incident-rca-deps
	bash scripts/install.sh --agent claude-user incident-rca

install-claude-incident-triage-agent: install-claude-incident-rca install-claude-squad-map
	bash scripts/install.sh --agent claude-user incident-triage-agent

install-claude-domain-comprehension: install-claude-squad-map
	bash scripts/install.sh --agent claude-user domain-comprehension

install-claude-squad-map:
	bash scripts/install.sh --agent claude-user squad-map

install-claude-who-owns-x-bot: install-claude-squad-map
	bash scripts/install.sh --agent claude-user who-owns-x-bot

install-claude-new-hire-guide: install-claude-domain-comprehension install-claude-squad-map
	bash scripts/install.sh --agent claude-user new-hire-guide

install-claude-release-readiness-checker: install-claude-pr-review install-claude-k8s-overprovisioning install-claude-incident-rca
	bash scripts/install.sh --agent claude-user release-readiness-checker

install-claude-migration-program-manager: install-claude-mysql-to-postgres-sql install-claude-squad-map
	bash scripts/install.sh --agent claude-user migration-program-manager

install-claude-cost-optimization-sprint-planner: install-claude-k8s-overprovisioning install-claude-squad-map
	bash scripts/install.sh --agent claude-user cost-optimization-sprint-planner

install-claude-mysql-to-postgres-sql:
	bash scripts/install.sh --agent claude-user mysql-to-postgres-sql

install-claude-loop-task-implementer:
	bash scripts/install.sh --agent claude-user loop-task-implementer

install-claude-backlog-runner: install-claude-loop-task-implementer
	bash scripts/install.sh --agent claude-user backlog-runner

install-claude-weekly-squad-digest: install-claude-migration-program-manager install-claude-cost-optimization-sprint-planner
	bash scripts/install.sh --agent claude-user weekly-squad-digest

install-claude-unit-test-creator:
	bash scripts/install.sh --agent claude-user unit-test-creator

install-claude-integration-test-creator:
	bash scripts/install.sh --agent claude-user integration-test-creator

install-claude-contract-test-creator:
	bash scripts/install.sh --agent claude-user contract-test-creator

install-claude-e2e-test-creator:
	bash scripts/install.sh --agent claude-user e2e-test-creator

install-claude-api-test-creator:
	bash scripts/install.sh --agent claude-user api-test-creator

install-claude-prd-architect:
	bash scripts/install.sh --agent claude-user prd-architect

install-claude-test-writer: install-claude-unit-test-creator install-claude-integration-test-creator install-claude-contract-test-creator install-claude-e2e-test-creator install-claude-api-test-creator
	bash scripts/install.sh --agent claude-user test-writer

install-claude-change-impact-analyzer:
	bash scripts/install.sh --agent claude-user change-impact-analyzer

install-claude-implementation-planner:
	bash scripts/install.sh --agent claude-user implementation-planner

install-claude-resilience-review:
	bash scripts/install.sh --agent claude-user resilience-review

install-claude-production-readiness-review:
	bash scripts/install.sh --agent claude-user production-readiness-review

install-architecture-review:
	bash scripts/install.sh architecture-review

install-system-design:
	bash scripts/install.sh system-design

install-api-design-review:
	bash scripts/install.sh api-design-review

install-database-review:
	bash scripts/install.sh database-review

install-security-review:
	bash scripts/install.sh security-review

install-performance-review:
	bash scripts/install.sh performance-review

install-capacity-planner:
	bash scripts/install.sh capacity-planner

install-observability-review:
	bash scripts/install.sh observability-review

install-deployment-risk-review:
	bash scripts/install.sh deployment-risk-review

install-dependency-upgrade-review:
	bash scripts/install.sh dependency-upgrade-review

install-tech-debt-assessor:
	bash scripts/install.sh tech-debt-assessor

install-change-impact-analyzer:
	bash scripts/install.sh change-impact-analyzer

install-implementation-planner:
	bash scripts/install.sh implementation-planner

install-resilience-review:
	bash scripts/install.sh resilience-review

install-production-readiness-review: install-pr-review install-change-impact-analyzer install-deployment-risk-review install-security-review install-observability-review install-resilience-review install-api-design-review install-database-review install-performance-review install-capacity-planner install-dependency-upgrade-review
	bash scripts/install.sh production-readiness-review

install-claude-architecture-review:
	bash scripts/install.sh --agent claude-user architecture-review

install-claude-system-design:
	bash scripts/install.sh --agent claude-user system-design

install-claude-api-design-review:
	bash scripts/install.sh --agent claude-user api-design-review

install-claude-database-review:
	bash scripts/install.sh --agent claude-user database-review

install-claude-security-review:
	bash scripts/install.sh --agent claude-user security-review

install-claude-performance-review:
	bash scripts/install.sh --agent claude-user performance-review

install-claude-capacity-planner:
	bash scripts/install.sh --agent claude-user capacity-planner

install-claude-observability-review:
	bash scripts/install.sh --agent claude-user observability-review

install-claude-deployment-risk-review:
	bash scripts/install.sh --agent claude-user deployment-risk-review

install-claude-dependency-upgrade-review:
	bash scripts/install.sh --agent claude-user dependency-upgrade-review

install-claude-tech-debt-assessor:
	bash scripts/install.sh --agent claude-user tech-debt-assessor

setup:
	@echo "setup: installing Python dev dependencies (requirements.lock)"
	@python3 -m pip install --require-hashes -r requirements.lock 2>/dev/null || \
		python3 -m pip install --user --break-system-packages --require-hashes -r requirements.lock
	@$(MAKE) setup-hooks

lint-requirements-lock:
	@python3 scripts/check_requirements_lock.py

lint-python:
	@echo "lint-python: ruff (pyflakes + syntax errors) over scripts/"
	@python3 -m ruff check scripts/ && echo "  ok"

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

# Not wired into `lint` -- catches capability_catalog.yaml drift from what's
# committed in skills.yaml, which is a maintainer-triggered repair, not a
# per-PR gate. Run manually: make backfill-capabilities-drift-check
backfill-capabilities-drift-check:
	@python3 -m scripts.registry backfill-capabilities --check --overwrite

validate-evals:
	@python3 -m scripts.evals

validate-operational-upkeep:
	@python3 scripts/operational_upkeep.py validate
	@python3 -m scripts.deprecation_lifecycle
	@python3 scripts/eval_tier_health.py --format markdown >/dev/null

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
# Shared lint helpers — used via $(call ...) inside per-skill lint targets
# below. Each wraps a check that was previously duplicated verbatim (only
# the skill dir / threshold / file list changed) across ~20 lint-<skill>
# targets. Skill-specific content assertions stay inline at each call site.
# ---------------------------------------------------------------------------

# $(call check_skill_md_length,<skill-dir>,<max-lines>,<optional guidance suffix>)
define check_skill_md_length
	@test -f $(1)/SKILL.md || \
		{ echo "error: missing $(1)/SKILL.md" >&2; exit 1; }
	@lines=$$(wc -l < $(1)/SKILL.md | tr -d ' '); \
	if [ -z "$$lines" ] || [ "$$lines" -eq 0 ]; then \
		echo "error: $(1)/SKILL.md is empty" >&2; exit 1; \
	elif [ "$$lines" -gt $(2) ]; then \
		echo "error: $(1) SKILL.md $$lines lines (> $(2))$(if $(3), — $(3))" >&2; \
		exit 1; \
	fi; \
	echo "  ok ($$lines lines)"
endef

# $(call check_workflow_frontmatter,<skill-dir>)
define check_workflow_frontmatter
	@fail=0; \
	for f in $(1)/workflow/*.md; do \
		fm=$$(awk '/^---$$/{c++; next} c==1' "$$f"); \
		for key in workflow_version phase produces consumes; do \
			if ! printf '%s\n' "$$fm" | grep -q "^$$key:"; then \
				echo "  missing $$key frontmatter: $$f" >&2; fail=1; \
			fi; \
		done; \
	done; \
	if [ "$$fail" -ne 0 ]; then echo "error: $(1) workflow/*.md must declare workflow_version, phase, produces, consumes" >&2; exit 1; fi; \
	echo "  ok"
endef

# $(call check_dangling_links,<space-separated glob(s)>)
define check_dangling_links
	@bash scripts/lint-dangling-md-links.sh $(1) && echo "  ok" || \
		{ echo "error: dangling reference link(s) found" >&2; exit 1; }
endef

# $(call require_ref_files,<dir>,<space-separated basenames, no .md ext>)
define require_ref_files
	@for f in $(2); do \
		test -f $(1)/$$f.md || \
			{ echo "error: missing $(1)/$$f.md" >&2; exit 1; }; \
	done
endef

# $(call require_disable_model_invocation,<skill-dir>)
define require_disable_model_invocation
	@grep -q '^disable-model-invocation: true' $(1)/SKILL.md || \
		{ echo "error: $(1)/SKILL.md must set disable-model-invocation: true" >&2; exit 1; }
endef

# $(call forbid_disable_model_invocation,<skill-dir>)
define forbid_disable_model_invocation
	@grep -q '^disable-model-invocation:' $(1)/SKILL.md && \
		{ echo "error: $(1)/SKILL.md must NOT set disable-model-invocation" >&2; exit 1; } || true
endef

# $(call require_setup_links_framework,<skill-dir>)
define require_setup_links_framework
	@grep -q 'skill-framework' $(1)/SETUP.md || \
		{ echo "error: $(1)/SETUP.md must link to docs/skill-framework" >&2; exit 1; }
endef

# $(call require_cross_skill_escalation,<skill-dir>)
define require_cross_skill_escalation
	@grep -q 'cross-skill-escalation' $(1)/SKILL.md || \
		{ echo "error: $(1) SKILL.md must link to shared cross-skill-escalation" >&2; exit 1; }
endef

# $(call require_safe_output_link,<skill-dir>)
define require_safe_output_link
	@grep -q 'docs/skill-framework/shared/safe-output.md' $(1)/SKILL.md || \
		{ echo "error: $(1)/SKILL.md must link to shared safe-output" >&2; exit 1; }
endef

lint: lint-static lint-suites

# CI (.github/workflows/lint.yml) runs lint-static and lint-suites as two parallel jobs:
# lint-static is pure grep/structural checks (no pytest) and fails fast; lint-suites is
# every pytest-bearing target -- the dominant test cost -- and parallelizes it two ways,
# across skills via `make -jN` and within the larger suites via pytest-xdist (see
# PYTEST_XDIST_FLAG above). `make lint` still runs both groups locally, in this order.
lint-static: validate-registry validate-agent-skills validate-hosts backfill-capabilities-check generate-check validate-evals validate-operational-upkeep lint-framework lint-incident-triage-agent lint-who-owns-x-bot lint-new-hire-guide lint-release-readiness-checker lint-cost-optimization-sprint-planner lint-loop-task-implementer lint-backlog-runner lint-test-writer lint-prd-architect lint-architecture-review lint-system-design lint-api-design-review lint-database-review lint-security-review lint-performance-review lint-capacity-planner lint-observability-review lint-deployment-risk-review lint-dependency-upgrade-review lint-tech-debt-assessor lint-requirements-lock lint-python lint-actions-pinning lint-actions-security verify-install verify-install-all validate-review-contracts lint-scripts-shellcheck

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

lint-suites: lint-pr-review lint-pr-gatekeeper lint-k8s-skill lint-incident-rca lint-domain-comprehension lint-squad-map lint-migration-program-manager lint-mysql-to-postgres-sql lint-weekly-squad-digest lint-unit-test-creator lint-integration-test-creator lint-contract-test-creator lint-e2e-test-creator lint-api-test-creator lint-change-impact-analyzer lint-resilience-review lint-implementation-planner lint-production-readiness-review lint-framework-tests

lint-pr-review: lint-pr-review-skill lint-pr-review-scripts

lint-pr-review-scripts:
	@echo "py_compile pr-review/scripts/diff-to-positions.py pr-review/scripts/github-comment-positions.py pr-review/scripts/github-comment-recovery.py pr-review/scripts/pr_review_policy_guards.py"
	@echo "pytest pr-review/tests/"
	@cache="$(CURDIR)/.pycache-lint"; \
	export PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$$cache"; \
	trap 'rm -rf "$$cache"' EXIT; \
	python3 -m py_compile pr-review/scripts/diff-to-positions.py || exit 1; \
	python3 -m py_compile pr-review/scripts/github-comment-positions.py || exit 1; \
	python3 -m py_compile pr-review/scripts/github-comment-recovery.py || exit 1; \
	python3 -m py_compile pr-review/scripts/pr_review_policy_guards.py || exit 1; \
	if python3 -c "import pytest" >/dev/null 2>&1; then \
		python3 -m pytest -p no:cacheprovider $(PYTEST_XDIST_FLAG) pr-review/tests/ -q || exit 1; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run script tests" >&2; \
		exit 1; \
	fi

lint-pr-review-skill:
	@echo "lint-pr-review-skill: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,pr-review,180,keep orchestrator thin; detail in workflow/)
	@echo "lint-pr-review-skill: route-aware workflow contract (workflow_version, phase, produces, consumes checked here too)"
	@python3 -m scripts.validate_workflow_contracts pr-review
	@echo "lint-pr-review-skill: dangling markdown links"
	$(call check_dangling_links,pr-review/*.md pr-review/reference/*.md pr-review/workflow/*.md)
	$(call require_cross_skill_escalation,pr-review)
	@grep -q 'smoke-test' pr-review/SKILL.md || \
		{ echo "error: pr-review SKILL.md must link to reference/smoke-test.md" >&2; exit 1; }
	$(call require_safe_output_link,pr-review)
	@for f in pr-review/workflow/posting.md pr-review/workflow/phase-5.md; do \
		grep -q 'docs/skill-framework/shared/prompt-injection.md' "$$f" && \
		grep -q 'docs/skill-framework/shared/safe-output.md' "$$f" && \
		grep -qiE 'escape|fence' "$$f" && \
		grep -qi 'redact' "$$f" || \
			{ echo "error: $$f must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }; \
	done
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
	@echo "lint-pr-gatekeeper: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,pr-gatekeeper,180,keep orchestrator thin; detail in workflow/)
	@echo "lint-pr-gatekeeper: disable-model-invocation set (automation entry point, must not compete with pr-review's ambient invocation)"
	$(call require_disable_model_invocation,pr-gatekeeper)
	@echo "  ok"
	@echo "lint-pr-gatekeeper: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	$(call check_workflow_frontmatter,pr-gatekeeper)
	@echo "lint-pr-gatekeeper: dangling markdown links"
	$(call check_dangling_links,pr-gatekeeper/*.md pr-gatekeeper/reference/*.md pr-gatekeeper/workflow/*.md)
	@echo "lint-pr-gatekeeper: required reference files"
	$(call require_ref_files,pr-gatekeeper/reference,phase-index lazy-load-index auto-post-policy smoke-test pressure-tests)
	@grep -q 'pressure-tests' pr-gatekeeper/reference/smoke-test.md || \
		{ echo "error: smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	$(call require_setup_links_framework,pr-gatekeeper)
	$(call require_safe_output_link,pr-gatekeeper)
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' pr-gatekeeper/reference/auto-post-policy.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' pr-gatekeeper/reference/auto-post-policy.md && \
	 grep -qiE 'escape|fence|backtick' pr-gatekeeper/reference/auto-post-policy.md || \
		{ echo "error: auto-post-policy.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "lint-pr-gatekeeper: script pytest suite"
	@if python3 -c "import pytest" >/dev/null 2>&1; then \
		python3 -m pytest -p no:cacheprovider pr-gatekeeper/tests/ -q || exit 1; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run pr-gatekeeper tests" >&2; \
	fi
	@echo "  ok (framework refs + idempotency tests)"
	@echo "lint-pr-gatekeeper: ask-point drift check (pr-review workflow vs auto-post-policy.md)"
	@python3 pr-gatekeeper/scripts/check-ask-point-drift.py || \
		{ echo "error: pr-review ask-point drift detected — see pr-gatekeeper/reference/auto-post-policy.md" >&2; exit 1; }

lint-k8s-skill:
	@echo "lint-k8s-skill: SKILL.md line count (<= 150)"
	$(call check_skill_md_length,k8s-overprovisioning-datadog,150,keep orchestrator thin; detail in workflow/)
	@echo "lint-k8s-skill: route-aware workflow contract (workflow_version, phase, produces, consumes checked here too)"
	@python3 -m scripts.validate_workflow_contracts k8s-overprovisioning-datadog
	@echo "lint-k8s-skill: dangling markdown links"
	$(call check_dangling_links,k8s-overprovisioning-datadog/*.md k8s-overprovisioning-datadog/workflow/*.md k8s-overprovisioning-datadog/reference/*.md k8s-overprovisioning-datadog/render/*.md k8s-overprovisioning-datadog/templates/*.md)
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
	@echo "lint-k8s-skill: framework reference files"
	@for f in phase-index lazy-load-index smoke-test mcp-capabilities; do \
		test -f k8s-overprovisioning-datadog/reference/$$f.md || \
			{ echo "error: missing k8s-overprovisioning-datadog/reference/$$f.md" >&2; exit 1; }; \
	done
	$(call require_setup_links_framework,k8s-overprovisioning-datadog)
	$(call require_cross_skill_escalation,k8s-overprovisioning-datadog)
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
	@echo "lint-k8s-skill: safe rendered-output boundary"
	$(call require_safe_output_link,k8s-overprovisioning-datadog)
	@grep -q 'docs/skill-framework/shared/safe-output.md' k8s-overprovisioning-datadog/render/markdown.md && \
	 grep -qiE 'escape|backtick|code span' k8s-overprovisioning-datadog/render/markdown.md || \
		{ echo "error: render/markdown.md must sanitize untrusted rendered fields per safe-output" >&2; exit 1; }
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
		python3 -m pytest -p no:cacheprovider $(PYTEST_XDIST_FLAG) k8s-overprovisioning-datadog/tests/ -q || exit 1; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run k8s script tests" >&2; \
		exit 1; \
	fi; \
	echo "  ok"

lint-k8s: lint-k8s-skill

lint-incident-rca:
	@echo "lint-incident-rca: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,incident-rca,180,push detail into workflow/ and reference/)
	@echo "lint-incident-rca: route-aware workflow contract (workflow_version, phase, produces, consumes checked here too)"
	@python3 -m scripts.validate_workflow_contracts incident-rca
	@echo "lint-incident-rca: evidence.example.json parses as JSON"
	@cache="$(CURDIR)/.pycache-lint-rca"; \
	export PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$$cache"; \
	trap 'rm -rf "$$cache"' EXIT; \
	python3 -c "import json,sys; json.load(open('incident-rca/reference/evidence.example.json'))" || \
		{ echo "error: incident-rca/reference/evidence.example.json is not valid JSON" >&2; exit 1; }; \
	echo "  ok"
	@echo "lint-incident-rca: dangling markdown links"
	$(call check_dangling_links,incident-rca/*.md incident-rca/reference/*.md incident-rca/workflow/*.md)
	@echo "lint-incident-rca: framework reference files"
	$(call require_ref_files,incident-rca/reference,phase-index lazy-load-index smoke-test mcp-capabilities)
	$(call require_setup_links_framework,incident-rca)
	$(call require_cross_skill_escalation,incident-rca)
	@python3 -c "from pathlib import Path; import yaml; data = yaml.safe_load(Path('skills.yaml').read_text(encoding='utf-8')); assert data['skills']['incident-rca']['entrypoint'] == 'SKILL.md'" || \
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
		python3 -m pytest -p no:cacheprovider $(PYTEST_XDIST_FLAG) incident-rca/tests/ -q || exit 1; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run schema tests" >&2; \
		exit 1; \
	fi; \
	echo "  ok"
	@echo "lint-incident-rca: safe rendered-output boundary"
	$(call require_safe_output_link,incident-rca)
	@grep -q 'docs/skill-framework/shared/safe-output.md' incident-rca/report-template.md && \
	 grep -qiE 'escape|backtick|code span' incident-rca/report-template.md || \
		{ echo "error: report-template.md must sanitize untrusted rendered fields per safe-output" >&2; exit 1; }
	@echo "  ok"

lint-incident-triage-agent:
	@echo "lint-incident-triage-agent: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,incident-triage-agent,180,keep orchestrator thin; detail in workflow/)
	@echo "lint-incident-triage-agent: disable-model-invocation set (automation entry point, must not compete with incident-rca/squad-map's ambient invocation)"
	$(call require_disable_model_invocation,incident-triage-agent)
	@echo "  ok"
	@echo "lint-incident-triage-agent: route-aware workflow contract (workflow_version, phase, produces, consumes checked here too)"
	@python3 -m scripts.validate_workflow_contracts incident-triage-agent
	@echo "lint-incident-triage-agent: dangling markdown links"
	$(call check_dangling_links,incident-triage-agent/*.md incident-triage-agent/reference/*.md incident-triage-agent/workflow/*.md)
	@echo "lint-incident-triage-agent: required reference files"
	$(call require_ref_files,incident-triage-agent/reference,phase-index lazy-load-index unattended-gate-policy triage-doc-format postmortem-format smoke-test pressure-tests)
	@grep -q 'pressure-tests' incident-triage-agent/reference/smoke-test.md || \
		{ echo "error: smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	$(call require_setup_links_framework,incident-triage-agent)
	$(call require_safe_output_link,incident-triage-agent)
	@for f in triage-doc-format postmortem-format; do \
		grep -q 'docs/skill-framework/shared/prompt-injection.md' incident-triage-agent/reference/$$f.md && \
		 grep -q 'docs/skill-framework/shared/safe-output.md' incident-triage-agent/reference/$$f.md && \
		 grep -qiE 'escape|fence|backtick' incident-triage-agent/reference/$$f.md || \
			{ echo "error: reference/$$f.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }; \
	done
	@echo "  ok (framework refs)"

lint-domain-comprehension: lint-domain-comprehension-skill lint-domain-comprehension-scripts

lint-domain-comprehension-scripts:
	@cache="$(CURDIR)/.pycache-lint-dc"; \
	venv="$(CURDIR)/.venv-dc-lint"; \
	export PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$$cache"; \
	trap 'rm -rf "$$cache"' EXIT; \
	if python3 -c "import yaml" >/dev/null 2>&1; then PY=python3; \
	elif [ -x "$(CURDIR)/.venv/bin/python3" ] && "$(CURDIR)/.venv/bin/python3" -c "import yaml" >/dev/null 2>&1; then PY="$(CURDIR)/.venv/bin/python3"; \
	elif [ -x "$$venv/bin/python3" ]; then PY="$$venv/bin/python3"; \
	else python3 -m venv "$$venv" && "$$venv/bin/pip" install -q pyyaml pytest pytest-xdist && PY="$$venv/bin/python3"; fi; \
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
		xdist_flag=""; "$$PY" -c "import xdist" >/dev/null 2>&1 && xdist_flag="-n auto"; \
		"$$PY" -m pytest -p no:cacheprovider $$xdist_flag domain-comprehension/tests/ -q || exit 1; \
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
	@echo "lint-domain-comprehension: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,domain-comprehension,180,keep orchestrator thin; detail in workflow/)
	@echo "lint-domain-comprehension: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	$(call check_workflow_frontmatter,domain-comprehension)
	@echo "lint-domain-comprehension: dangling markdown links"
	$(call check_dangling_links,domain-comprehension/*.md domain-comprehension/reference/*.md domain-comprehension/workflow/*.md domain-comprehension/reference/domain-packs/*.md)
	@echo "lint-domain-comprehension: framework reference files"
	$(call require_ref_files,domain-comprehension/reference,phase-index lazy-load-index smoke-test mcp-capabilities phase-outputs manifest-schema repo-classification evidence-precedence evidence-summary business-flows large-scale-execution)
	@test -f domain-comprehension/templates/manifest.yaml || \
		{ echo "error: missing domain-comprehension/templates/manifest.yaml" >&2; exit 1; }
	@test -f domain-comprehension/templates/BUSINESS_FLOWS.md || exit 1
	@test -f domain-comprehension/templates/KNOWN_OMISSIONS.md || exit 1
	$(call require_setup_links_framework,domain-comprehension)
	$(call require_cross_skill_escalation,domain-comprehension)
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
	@echo "  ok (framework refs)"
	@echo "lint-domain-comprehension: safe rendered-output boundary"
	$(call require_safe_output_link,domain-comprehension)
	@grep -q 'docs/skill-framework/shared/safe-output.md' domain-comprehension/reference/deliverable-templates.md && \
	 grep -qiE 'escape|backtick|code span' domain-comprehension/reference/deliverable-templates.md || \
		{ echo "error: deliverable-templates.md must sanitize untrusted rendered fields per safe-output" >&2; exit 1; }
	@echo "  ok"

lint-squad-map:
	@echo "lint-squad-map: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,squad-map,180,keep orchestrator thin; detail in workflow/)
	@echo "lint-squad-map: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	$(call check_workflow_frontmatter,squad-map)
	@echo "lint-squad-map: dangling markdown links"
	$(call check_dangling_links,squad-map/*.md squad-map/reference/*.md squad-map/workflow/*.md)
	@echo "lint-squad-map: required reference files"
	$(call require_ref_files,squad-map/reference,squad-mapping mcp-capabilities config-schema smoke-test lazy-load-index phase-index)
	@test -f squad-map/templates/SQUAD_MAP.md || \
		{ echo "error: missing squad-map/templates/SQUAD_MAP.md" >&2; exit 1; }
	$(call require_setup_links_framework,squad-map)
	@test -f squad-map/reference/pressure-tests.md || exit 1
	@test -f squad-map/reference/gold-squad-map-excerpt.md || exit 1
	@grep -q 'monorepo_service_dirs' squad-map/reference/config-schema.md || \
		{ echo "error: config-schema.md must document monorepo_service_dirs mapping" >&2; exit 1; }
	$(call require_safe_output_link,squad-map)
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' squad-map/reference/squad-mapping.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' squad-map/reference/squad-mapping.md && \
	 grep -qiE 'escape|fence|backtick' squad-map/reference/squad-mapping.md || \
		{ echo "error: squad-mapping.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
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
		python3 -m pytest -p no:cacheprovider $(PYTEST_XDIST_FLAG) squad-map/tests/ -q || exit 1; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run squad-map tests" >&2; \
		exit 1; \
	fi; \
	echo "  ok (framework refs + squad_mapping tests)"

lint-who-owns-x-bot:
	@echo "lint-who-owns-x-bot: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,who-owns-x-bot,180,keep orchestrator thin; detail in workflow/)
	@echo "lint-who-owns-x-bot: disable-model-invocation set (automation entry point, must not compete with squad-map's ambient invocation)"
	$(call require_disable_model_invocation,who-owns-x-bot)
	@echo "  ok"
	@echo "lint-who-owns-x-bot: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	$(call check_workflow_frontmatter,who-owns-x-bot)
	@echo "lint-who-owns-x-bot: dangling markdown links"
	$(call check_dangling_links,who-owns-x-bot/*.md who-owns-x-bot/reference/*.md who-owns-x-bot/workflow/*.md)
	@echo "lint-who-owns-x-bot: required reference files"
	$(call require_ref_files,who-owns-x-bot/reference,phase-index lazy-load-index slack-format smoke-test pressure-tests)
	@grep -q 'pressure-tests' who-owns-x-bot/reference/smoke-test.md || \
		{ echo "error: smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	$(call require_setup_links_framework,who-owns-x-bot)
	$(call require_safe_output_link,who-owns-x-bot)
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' who-owns-x-bot/reference/slack-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' who-owns-x-bot/reference/slack-format.md && \
	 grep -qiE 'escape|strip' who-owns-x-bot/reference/slack-format.md || \
		{ echo "error: slack-format.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "  ok (framework refs)"

lint-new-hire-guide:
	@echo "lint-new-hire-guide: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,new-hire-guide,180,keep orchestrator thin; detail in workflow/)
	@echo "lint-new-hire-guide: disable-model-invocation NOT set (ambiently invocable, unlike the webhook/schedule wrappers)"
	$(call forbid_disable_model_invocation,new-hire-guide)
	@echo "  ok"
	@echo "lint-new-hire-guide: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	$(call check_workflow_frontmatter,new-hire-guide)
	@echo "lint-new-hire-guide: dangling markdown links"
	$(call check_dangling_links,new-hire-guide/*.md new-hire-guide/reference/*.md new-hire-guide/workflow/*.md)
	@echo "lint-new-hire-guide: required reference files"
	$(call require_ref_files,new-hire-guide/reference,phase-index lazy-load-index tour-format smoke-test pressure-tests)
	@grep -q 'pressure-tests' new-hire-guide/reference/smoke-test.md || \
		{ echo "error: smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	$(call require_setup_links_framework,new-hire-guide)
	$(call require_safe_output_link,new-hire-guide)
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' new-hire-guide/reference/tour-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' new-hire-guide/reference/tour-format.md && \
	 grep -qiE 'escape|fence|backtick' new-hire-guide/reference/tour-format.md && \
	 grep -qi 'redact' new-hire-guide/reference/tour-format.md || \
		{ echo "error: tour-format.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "  ok (framework refs)"

lint-release-readiness-checker:
	@echo "lint-release-readiness-checker: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,release-readiness-checker,180,keep orchestrator thin; detail in workflow/)
	@echo "lint-release-readiness-checker: disable-model-invocation NOT set (ambiently invocable, unlike the webhook/schedule wrappers)"
	$(call forbid_disable_model_invocation,release-readiness-checker)
	@echo "  ok"
	@echo "lint-release-readiness-checker: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	$(call check_workflow_frontmatter,release-readiness-checker)
	@echo "lint-release-readiness-checker: dangling markdown links"
	$(call check_dangling_links,release-readiness-checker/*.md release-readiness-checker/reference/*.md release-readiness-checker/workflow/*.md)
	@echo "lint-release-readiness-checker: required reference files"
	$(call require_ref_files,release-readiness-checker/reference,phase-index lazy-load-index gate-policy report-format smoke-test pressure-tests)
	@grep -q 'pressure-tests' release-readiness-checker/reference/smoke-test.md || \
		{ echo "error: smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	$(call require_setup_links_framework,release-readiness-checker)
	$(call require_safe_output_link,release-readiness-checker)
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' release-readiness-checker/reference/report-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' release-readiness-checker/reference/report-format.md && \
	 grep -qiE 'escape|fence|backtick' release-readiness-checker/reference/report-format.md || \
		{ echo "error: report-format.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "  ok (framework refs)"

lint-migration-program-manager:
	@echo "lint-migration-program-manager: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,migration-program-manager,180,keep orchestrator thin; detail in workflow/)
	@echo "lint-migration-program-manager: disable-model-invocation NOT set (ambiently invocable, no live wrapped-skill invocation to gate)"
	$(call forbid_disable_model_invocation,migration-program-manager)
	@echo "  ok"
	@echo "lint-migration-program-manager: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	$(call check_workflow_frontmatter,migration-program-manager)
	@echo "lint-migration-program-manager: dangling markdown links"
	$(call check_dangling_links,migration-program-manager/*.md migration-program-manager/reference/*.md migration-program-manager/workflow/*.md)
	@echo "lint-migration-program-manager: required reference files"
	$(call require_ref_files,migration-program-manager/reference,phase-index lazy-load-index report-format smoke-test pressure-tests)
	@grep -q 'pressure-tests' migration-program-manager/reference/smoke-test.md || \
		{ echo "error: smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	@test -f migration-program-manager/scripts/aggregate_migration_status.py || \
		{ echo "error: missing migration-program-manager/scripts/aggregate_migration_status.py" >&2; exit 1; }
	$(call require_setup_links_framework,migration-program-manager)
	$(call require_safe_output_link,migration-program-manager)
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' migration-program-manager/reference/report-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' migration-program-manager/reference/report-format.md && \
	 grep -qiE 'escape|fence|backtick' migration-program-manager/reference/report-format.md && \
	 grep -qi 'redact' migration-program-manager/reference/report-format.md || \
		{ echo "error: report-format.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "lint-migration-program-manager: aggregator pytest"
	@if python3 -c "import pytest" >/dev/null 2>&1; then \
		python3 -m pytest -p no:cacheprovider $(PYTEST_XDIST_FLAG) migration-program-manager/tests/ -q || exit 1; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run migration-program-manager tests" >&2; \
	fi
	@echo "  ok (framework refs + aggregator tests)"

lint-cost-optimization-sprint-planner:
	@echo "lint-cost-optimization-sprint-planner: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,cost-optimization-sprint-planner,180,keep orchestrator thin; detail in workflow/)
	@echo "lint-cost-optimization-sprint-planner: disable-model-invocation NOT set (ambiently invocable, unlike the webhook/schedule wrappers)"
	$(call forbid_disable_model_invocation,cost-optimization-sprint-planner)
	@echo "  ok"
	@echo "lint-cost-optimization-sprint-planner: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	$(call check_workflow_frontmatter,cost-optimization-sprint-planner)
	@echo "lint-cost-optimization-sprint-planner: dangling markdown links"
	$(call check_dangling_links,cost-optimization-sprint-planner/*.md cost-optimization-sprint-planner/reference/*.md cost-optimization-sprint-planner/workflow/*.md)
	@echo "lint-cost-optimization-sprint-planner: required reference files"
	$(call require_ref_files,cost-optimization-sprint-planner/reference,phase-index lazy-load-index gate-policy sweep-policy report-format smoke-test pressure-tests)
	@grep -q 'pressure-tests' cost-optimization-sprint-planner/reference/smoke-test.md || \
		{ echo "error: smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	$(call require_setup_links_framework,cost-optimization-sprint-planner)
	$(call require_safe_output_link,cost-optimization-sprint-planner)
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' cost-optimization-sprint-planner/reference/report-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' cost-optimization-sprint-planner/reference/report-format.md && \
	 grep -qiE 'escape|fence|backtick' cost-optimization-sprint-planner/reference/report-format.md || \
		{ echo "error: report-format.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "  ok (framework refs)"

lint-mysql-to-postgres-sql:
	@echo "lint-mysql-to-postgres-sql: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,mysql-to-postgres-sql,180,)
	@echo "lint-mysql-to-postgres-sql: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	$(call check_workflow_frontmatter,mysql-to-postgres-sql)
	@echo "lint-mysql-to-postgres-sql: required reference files"
	$(call require_ref_files,mysql-to-postgres-sql/reference,function-translations collection-domain-files smoke-test org-migration-gaps timestamp-handling data-type-mapping case-sensitivity nodejs-migration python-migration migration-prompts shadow-migration lazy-load-index collection-checklist-refresh migration-edge-cases calibration-snippets)
	@test -f mysql-to-postgres-sql/scripts/scan-mysql-dialect.sh || \
		{ echo "error: missing mysql-to-postgres-sql/scripts/scan-mysql-dialect.sh" >&2; exit 1; }
	@test -f mysql-to-postgres-sql/scripts/scan-report.sh || \
		{ echo "error: missing mysql-to-postgres-sql/scripts/scan-report.sh" >&2; exit 1; }
	@test -f mysql-to-postgres-sql/scripts/mysql-dialect-patterns.sh || \
		{ echo "error: missing mysql-to-postgres-sql/scripts/mysql-dialect-patterns.sh" >&2; exit 1; }
	@test -f mysql-to-postgres-sql/reference/spring-datasource-example.yaml || \
		{ echo "error: missing mysql-to-postgres-sql/reference/spring-datasource-example.yaml" >&2; exit 1; }
	$(call require_setup_links_framework,mysql-to-postgres-sql)
	$(call require_cross_skill_escalation,mysql-to-postgres-sql)
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
	@grep -q 'pressure-tests' mysql-to-postgres-sql/reference/smoke-test.md || \
		{ echo "error: smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	@echo "lint-mysql-to-postgres-sql: safe rendered-output boundary"
	$(call require_safe_output_link,mysql-to-postgres-sql)
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' mysql-to-postgres-sql/workflow/migrate-service.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' mysql-to-postgres-sql/workflow/migrate-service.md && \
	 grep -qiE 'escape|fence|backtick' mysql-to-postgres-sql/workflow/migrate-service.md || \
		{ echo "error: workflow/migrate-service.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "  ok"
	@echo "lint-mysql-to-postgres-sql: scan fixture + pressure harness"
	@bash mysql-to-postgres-sql/tests/run_pressure_tests.sh
	@cache="$(CURDIR)/.pycache-lint-mysql"; \
	export PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$$cache"; \
	trap 'rm -rf "$$cache"' EXIT; \
	python3 -m py_compile mysql-to-postgres-sql/scripts/ast_check_mysql_dialect.py || exit 1; \
	if python3 -c "import pytest" >/dev/null 2>&1; then \
		python3 -m pytest -p no:cacheprovider mysql-to-postgres-sql/tests/test_pressure_policy.py -q || exit 1; \
		if python3 -c "import sqlglot" >/dev/null 2>&1; then \
			python3 -m pytest -p no:cacheprovider mysql-to-postgres-sql/tests/test_ast_check_mysql_dialect.py -q || exit 1; \
		else \
			echo "sqlglot not installed — install with 'python3 -m pip install sqlglot' to run the AST secondary-checker tests" >&2; \
			exit 1; \
		fi; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run mysql policy tests" >&2; \
		exit 1; \
	fi; \
	echo "  ok (pressure + pytest + AST checker)"
	@echo "lint-mysql-to-postgres-sql: dangling markdown links"
	$(call check_dangling_links,mysql-to-postgres-sql/*.md mysql-to-postgres-sql/reference/*.md mysql-to-postgres-sql/reference/domain-packs/*.md mysql-to-postgres-sql/workflow/*.md)
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

lint-loop-task-implementer:
	@echo "lint-loop-task-implementer: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,loop-task-implementer,180,)
	@echo "lint-loop-task-implementer: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	$(call check_workflow_frontmatter,loop-task-implementer)
	@echo "lint-loop-task-implementer: dangling markdown links"
	$(call check_dangling_links,loop-task-implementer/*.md loop-task-implementer/reference/*.md loop-task-implementer/workflow/*.md)
	@echo "lint-loop-task-implementer: required files"
	@for f in SETUP.md README.md examples.md report-template.md; do \
		test -f loop-task-implementer/$$f || \
			{ echo "error: missing loop-task-implementer/$$f" >&2; exit 1; }; \
	done
	$(call require_ref_files,loop-task-implementer/reference,phase-index lazy-load-index mcp-capabilities smoke-test pressure-tests platform-adapters)
	@test -f loop-task-implementer/reference/state-schema.yaml || \
		{ echo "error: missing loop-task-implementer/reference/state-schema.yaml" >&2; exit 1; }
	$(call require_setup_links_framework,loop-task-implementer)
	$(call require_cross_skill_escalation,loop-task-implementer)
	@echo "  ok"
	@echo "lint-loop-task-implementer: safe rendered-output boundary"
	$(call require_safe_output_link,loop-task-implementer)
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' loop-task-implementer/report-template.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' loop-task-implementer/report-template.md && \
	 grep -qiE 'escape|fence|backtick' loop-task-implementer/report-template.md && \
	 grep -qi 'redact' loop-task-implementer/report-template.md || \
		{ echo "error: report-template.md must sanitize and redact untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "  ok"

lint-backlog-runner:
	@echo "lint-backlog-runner: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,backlog-runner,180,keep orchestrator thin; detail in workflow/)
	@echo "lint-backlog-runner: disable-model-invocation set (automation entry point, must not compete with loop-task-implementer's ambient invocation)"
	$(call require_disable_model_invocation,backlog-runner)
	@echo "  ok"
	@echo "lint-backlog-runner: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	$(call check_workflow_frontmatter,backlog-runner)
	@echo "lint-backlog-runner: dangling markdown links"
	$(call check_dangling_links,backlog-runner/*.md backlog-runner/reference/*.md backlog-runner/workflow/*.md)
	@echo "lint-backlog-runner: required reference files"
	$(call require_ref_files,backlog-runner/reference,phase-index lazy-load-index queue-policy morning-summary-format smoke-test pressure-tests)
	@grep -q 'pressure-tests' backlog-runner/reference/smoke-test.md || \
		{ echo "error: smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	$(call require_safe_output_link,backlog-runner)
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' backlog-runner/reference/morning-summary-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' backlog-runner/reference/morning-summary-format.md && \
	 grep -qiE 'escape|fence' backlog-runner/reference/morning-summary-format.md && \
	 grep -qi 'redact' backlog-runner/reference/morning-summary-format.md || \
		{ echo "error: morning-summary-format.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	$(call require_setup_links_framework,backlog-runner)
	@echo "  ok (framework refs)"

lint-weekly-squad-digest:
	@echo "lint-weekly-squad-digest: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,weekly-squad-digest,180,keep orchestrator thin; detail in workflow/)
	@echo "lint-weekly-squad-digest: disable-model-invocation set (automation entry point, must not compete with migration-program-manager's/cost-optimization-sprint-planner's ambient invocation)"
	$(call require_disable_model_invocation,weekly-squad-digest)
	@echo "  ok"
	@echo "lint-weekly-squad-digest: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	$(call check_workflow_frontmatter,weekly-squad-digest)
	@echo "lint-weekly-squad-digest: dangling markdown links"
	$(call check_dangling_links,weekly-squad-digest/*.md weekly-squad-digest/reference/*.md weekly-squad-digest/workflow/*.md)
	@echo "lint-weekly-squad-digest: required reference files"
	$(call require_ref_files,weekly-squad-digest/reference,phase-index lazy-load-index report-format smoke-test pressure-tests)
	@grep -q 'pressure-tests' weekly-squad-digest/reference/smoke-test.md || \
		{ echo "error: smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	$(call require_setup_links_framework,weekly-squad-digest)
	$(call require_safe_output_link,weekly-squad-digest)
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' weekly-squad-digest/reference/report-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' weekly-squad-digest/reference/report-format.md && \
	 grep -qiE 'escape|fence|backtick' weekly-squad-digest/reference/report-format.md || \
		{ echo "error: report-format.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@test -f weekly-squad-digest/scripts/digest_grouping.py || \
		{ echo "error: missing weekly-squad-digest/scripts/digest_grouping.py" >&2; exit 1; }
	@echo "lint-weekly-squad-digest: digest_grouping pytest"
	@if python3 -c "import pytest" >/dev/null 2>&1; then \
		python3 -m pytest -p no:cacheprovider weekly-squad-digest/tests/ -q || exit 1; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run weekly-squad-digest tests" >&2; \
	fi
	@echo "  ok (framework refs + digest_grouping tests)"

define LINT_TEST_CREATOR_TARGET
lint-$(1):
	@echo "lint-$(1): SKILL.md line count (<= 180)"
	@test -f $(1)/SKILL.md || \
		{ echo "error: missing $(1)/SKILL.md" >&2; exit 1; }
	@lines=$$$$(wc -l < $(1)/SKILL.md | tr -d ' '); \
	if [ -z "$$$$lines" ] || [ "$$$$lines" -eq 0 ]; then \
		echo "error: $(1)/SKILL.md is empty" >&2; exit 1; \
	elif [ "$$$$lines" -gt 180 ]; then \
		echo "error: $(1) SKILL.md $$$$lines lines (> 180)" >&2; \
		exit 1; \
	fi; \
	echo "  ok ($$$$lines lines)"
	@echo "lint-$(1): workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	@fail=0; \
	for f in $(1)/workflow/*.md; do \
		fm=$$$$(awk '/^---$$$$/{c++; next} c==1' "$$$$f"); \
		for key in workflow_version phase produces consumes; do \
			if ! printf '%s\n' "$$$$fm" | grep -q "^$$$$key:"; then \
				echo "  missing $$$$key frontmatter: $$$$f" >&2; fail=1; \
			fi; \
		done; \
	done; \
	if [ "$$$$fail" -ne 0 ]; then echo "error: $(1) workflow/*.md must declare workflow_version, phase, produces, consumes" >&2; exit 1; fi; \
	echo "  ok"
	@echo "lint-$(1): required reference files"
	@for f in skill-contract phase-index lazy-load-index gate-policy test-quality-deltas framework-detection report-format smoke-test pressure-tests; do \
		test -f $(1)/reference/$$$$f.md || \
			{ echo "error: missing $(1)/reference/$$$$f.md" >&2; exit 1; }; \
	done
	@for f in $(2); do \
		test -f $(1)/scripts/$$$$f || \
			{ echo "error: missing $(1)/scripts/$$$$f" >&2; exit 1; }; \
	done
	@test -f $(1)/examples.md || \
		{ echo "error: missing $(1)/examples.md" >&2; exit 1; }
	@grep -q '## Invocation' $(1)/examples.md || \
		{ echo "error: $(1)/examples.md must have Invocation section" >&2; exit 1; }
	@grep -q 'skill-framework' $(1)/SETUP.md || \
		{ echo "error: $(1)/SETUP.md must link to docs/skill-framework" >&2; exit 1; }
	@grep -q 'docs/skill-framework/shared/skill-routing.md' $(1)/SKILL.md || \
		{ echo "error: $(1)/SKILL.md must link to shared skill-routing" >&2; exit 1; }
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' $(1)/SKILL.md || \
		{ echo "error: $(1)/SKILL.md must link to shared prompt-injection" >&2; exit 1; }
	@grep -q 'docs/skill-framework/shared/test-creation-principles.md' $(1)/reference/skill-contract.md || \
		{ echo "error: $(1)/reference/skill-contract.md must link to shared test-creation-principles" >&2; exit 1; }
	@echo "  ok (framework refs)"
	@echo "lint-$(1): dangling markdown links"
	@bash scripts/lint-dangling-md-links.sh $(1)/*.md $(1)/reference/*.md $(1)/workflow/*.md && echo "  ok" || \
		{ echo "error: dangling reference link(s) found" >&2; exit 1; }
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
		python3 -m pytest -p no:cacheprovider $(1)/tests/$(3) -q || exit 1; \
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

# All five test-creator skills (api, contract, e2e, integration, unit) now have a safe-output boundary
# (their own *_TEST_REPORT.md render surface) — these are EXTRA prerequisites on top of the shared
# LINT_TEST_CREATOR_TARGET macro above, not a change to the macro itself.
lint-api-test-creator: lint-api-test-creator-safe-output

lint-api-test-creator-safe-output:
	@echo "lint-api-test-creator: safe rendered-output boundary"
	@grep -q 'docs/skill-framework/shared/safe-output.md' api-test-creator/SKILL.md || \
		{ echo "error: api-test-creator/SKILL.md must link to shared safe-output" >&2; exit 1; }
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' api-test-creator/reference/report-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' api-test-creator/reference/report-format.md && \
	 grep -qiE 'escape|backtick|code span' api-test-creator/reference/report-format.md || \
		{ echo "error: reference/report-format.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "  ok"

lint-contract-test-creator: lint-contract-test-creator-safe-output

lint-contract-test-creator-safe-output:
	@echo "lint-contract-test-creator: safe rendered-output boundary"
	@grep -q 'docs/skill-framework/shared/safe-output.md' contract-test-creator/SKILL.md || \
		{ echo "error: contract-test-creator/SKILL.md must link to shared safe-output" >&2; exit 1; }
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' contract-test-creator/reference/report-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' contract-test-creator/reference/report-format.md && \
	 grep -qiE 'escape|backtick|code span' contract-test-creator/reference/report-format.md || \
		{ echo "error: reference/report-format.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "  ok"

lint-e2e-test-creator: lint-e2e-test-creator-safe-output

lint-e2e-test-creator-safe-output:
	@echo "lint-e2e-test-creator: safe rendered-output boundary"
	@grep -q 'docs/skill-framework/shared/safe-output.md' e2e-test-creator/SKILL.md || \
		{ echo "error: e2e-test-creator/SKILL.md must link to shared safe-output" >&2; exit 1; }
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' e2e-test-creator/reference/report-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' e2e-test-creator/reference/report-format.md && \
	 grep -qiE 'escape|backtick|code span' e2e-test-creator/reference/report-format.md || \
		{ echo "error: reference/report-format.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "  ok"

lint-integration-test-creator: lint-integration-test-creator-safe-output

lint-integration-test-creator-safe-output:
	@echo "lint-integration-test-creator: safe rendered-output boundary"
	@grep -q 'docs/skill-framework/shared/safe-output.md' integration-test-creator/SKILL.md || \
		{ echo "error: integration-test-creator/SKILL.md must link to shared safe-output" >&2; exit 1; }
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' integration-test-creator/reference/report-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' integration-test-creator/reference/report-format.md && \
	 grep -qiE 'escape|backtick|code span' integration-test-creator/reference/report-format.md || \
		{ echo "error: reference/report-format.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "  ok"

lint-unit-test-creator: lint-unit-test-creator-safe-output

lint-unit-test-creator-safe-output:
	@echo "lint-unit-test-creator: safe rendered-output boundary"
	@grep -q 'docs/skill-framework/shared/safe-output.md' unit-test-creator/SKILL.md || \
		{ echo "error: unit-test-creator/SKILL.md must link to shared safe-output" >&2; exit 1; }
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' unit-test-creator/reference/report-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' unit-test-creator/reference/report-format.md && \
	 grep -qiE 'escape|backtick|code span' unit-test-creator/reference/report-format.md || \
		{ echo "error: reference/report-format.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "  ok"

lint-test-writer:
	@echo "lint-test-writer: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,test-writer,180,)
	@echo "lint-test-writer: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	$(call check_workflow_frontmatter,test-writer)
	@echo "lint-test-writer: no detection/generation scripts (router only)"
	@if [ -d test-writer/scripts ] || [ -d test-writer/tests ]; then \
		echo "error: test-writer must not have scripts/ or tests/ — it is a router with no detection/generation logic of its own" >&2; exit 1; \
	fi
	@echo "  ok"
	@echo "lint-test-writer: required reference files"
	$(call require_ref_files,test-writer/reference,skill-contract phase-index lazy-load-index level-classification smoke-test pressure-tests)
	@test -f test-writer/examples.md || \
		{ echo "error: missing test-writer/examples.md" >&2; exit 1; }
	@grep -q '## Invocation' test-writer/examples.md || \
		{ echo "error: test-writer/examples.md must have Invocation section" >&2; exit 1; }
	$(call require_setup_links_framework,test-writer)
	@grep -q 'docs/skill-framework/shared/skill-routing.md' test-writer/SKILL.md || \
		{ echo "error: test-writer/SKILL.md must link to shared skill-routing" >&2; exit 1; }
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' test-writer/SKILL.md || \
		{ echo "error: test-writer/SKILL.md must link to shared prompt-injection" >&2; exit 1; }
	@echo "  ok (framework refs)"
	@echo "lint-test-writer: dangling markdown links"
	$(call check_dangling_links,test-writer/*.md test-writer/reference/*.md test-writer/workflow/*.md unit-test-creator/SKILL.md integration-test-creator/SKILL.md contract-test-creator/SKILL.md e2e-test-creator/SKILL.md api-test-creator/SKILL.md unit-test-creator/workflow/*.md integration-test-creator/workflow/*.md contract-test-creator/workflow/*.md e2e-test-creator/workflow/*.md api-test-creator/workflow/*.md)

lint-prd-architect:
	@echo "lint-prd-architect: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,prd-architect,180,)
	@echo "lint-prd-architect: route-aware workflow contract (workflow_version, phase, produces, consumes checked here too)"
	@python3 -m scripts.validate_workflow_contracts prd-architect
	@echo "lint-prd-architect: required reference files"
	$(call require_ref_files,prd-architect/reference,skill-contract rationalization-guards phase-index lazy-load-index global-rules depth response-modes section-triggers requirements-format correctness-rules adversarial-review output-contract smoke-test pressure-tests)
	@test -f prd-architect/report-template.md || \
		{ echo "error: missing prd-architect/report-template.md" >&2; exit 1; }
	@test -f prd-architect/prd-architect.eval.md || \
		{ echo "error: missing prd-architect/prd-architect.eval.md" >&2; exit 1; }
	@test -f prd-architect/scripts/prd_safe_output.py || \
		{ echo "error: missing prd-architect safe-output renderer" >&2; exit 1; }
	@test -f prd-architect/examples.md || \
		{ echo "error: missing prd-architect/examples.md" >&2; exit 1; }
	@grep -q '## Invocation' prd-architect/examples.md || \
		{ echo "error: prd-architect/examples.md must have Invocation section" >&2; exit 1; }
	$(call require_cross_skill_escalation,prd-architect)
	@grep -q 'smoke-test' prd-architect/SKILL.md || \
		{ echo "error: prd-architect/SKILL.md must link to reference/smoke-test.md" >&2; exit 1; }
	$(call require_setup_links_framework,prd-architect)
	@grep -q 'docs/skill-framework/shared/skill-routing.md' prd-architect/SKILL.md || \
		{ echo "error: prd-architect/SKILL.md must link to shared skill-routing" >&2; exit 1; }
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' prd-architect/SKILL.md || \
		{ echo "error: prd-architect/SKILL.md must link to shared prompt-injection" >&2; exit 1; }
	$(call require_safe_output_link,prd-architect)
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' prd-architect/workflow/gate.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' prd-architect/workflow/gate.md && \
	 grep -qi 'source_material' prd-architect/workflow/gate.md && \
	 grep -qiE 'escape|fence' prd-architect/workflow/gate.md && \
	 grep -qi 'redact' prd-architect/workflow/gate.md || \
		{ echo "error: prd-architect Gate must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "  ok (framework refs)"
	@echo "lint-prd-architect: dangling markdown links"
	$(call check_dangling_links,prd-architect/*.md prd-architect/reference/*.md prd-architect/workflow/*.md)

lint-architecture-review:
	@echo "lint-architecture-review: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,architecture-review,180,keep orchestrator thin; detail in workflow/)
	@echo "lint-architecture-review: disable-model-invocation NOT set (ambiently invocable)"
	$(call forbid_disable_model_invocation,architecture-review)
	@echo "  ok"
	@echo "lint-architecture-review: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	$(call check_workflow_frontmatter,architecture-review)
	@echo "lint-architecture-review: dangling markdown links"
	$(call check_dangling_links,architecture-review/*.md architecture-review/reference/*.md architecture-review/workflow/*.md)
	@echo "lint-architecture-review: required reference files"
	$(call require_ref_files,architecture-review/reference,phase-index lazy-load-index report-format smoke-test pressure-tests)
	@grep -q 'pressure-tests' architecture-review/reference/smoke-test.md || \
		{ echo "error: architecture-review/reference/smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	@grep -q '## Invocation' architecture-review/examples.md || \
		{ echo "error: architecture-review/examples.md must have Invocation section" >&2; exit 1; }
	$(call require_setup_links_framework,architecture-review)
	$(call require_cross_skill_escalation,architecture-review)
	$(call require_safe_output_link,architecture-review)
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' architecture-review/reference/report-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' architecture-review/reference/report-format.md && \
	 grep -qiE 'escape|fence|backtick' architecture-review/reference/report-format.md && \
	 grep -qi 'redact' architecture-review/reference/report-format.md || \
		{ echo "error: architecture-review/reference/report-format.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "  ok (framework refs)"

lint-system-design:
	@echo "lint-system-design: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,system-design,180,keep orchestrator thin; detail in workflow/)
	@echo "lint-system-design: disable-model-invocation NOT set (ambiently invocable)"
	$(call forbid_disable_model_invocation,system-design)
	@echo "  ok"
	@echo "lint-system-design: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	$(call check_workflow_frontmatter,system-design)
	@echo "lint-system-design: dangling markdown links"
	$(call check_dangling_links,system-design/*.md system-design/reference/*.md system-design/workflow/*.md)
	@echo "lint-system-design: required reference files"
	$(call require_ref_files,system-design/reference,phase-index lazy-load-index report-format smoke-test pressure-tests)
	@grep -q 'pressure-tests' system-design/reference/smoke-test.md || \
		{ echo "error: system-design/reference/smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	@grep -q '## Invocation' system-design/examples.md || \
		{ echo "error: system-design/examples.md must have Invocation section" >&2; exit 1; }
	$(call require_setup_links_framework,system-design)
	$(call require_cross_skill_escalation,system-design)
	$(call require_safe_output_link,system-design)
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' system-design/reference/report-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' system-design/reference/report-format.md && \
	 grep -qiE 'escape|fence|backtick' system-design/reference/report-format.md && \
	 grep -qi 'redact' system-design/reference/report-format.md || \
		{ echo "error: system-design/reference/report-format.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "  ok (framework refs)"

lint-api-design-review:
	@echo "lint-api-design-review: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,api-design-review,180,keep orchestrator thin; detail in workflow/)
	@echo "lint-api-design-review: disable-model-invocation NOT set (ambiently invocable)"
	$(call forbid_disable_model_invocation,api-design-review)
	@echo "  ok"
	@echo "lint-api-design-review: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	$(call check_workflow_frontmatter,api-design-review)
	@echo "lint-api-design-review: dangling markdown links"
	$(call check_dangling_links,api-design-review/*.md api-design-review/reference/*.md api-design-review/workflow/*.md)
	@echo "lint-api-design-review: required reference files"
	$(call require_ref_files,api-design-review/reference,phase-index lazy-load-index report-format smoke-test pressure-tests)
	@grep -q 'pressure-tests' api-design-review/reference/smoke-test.md || \
		{ echo "error: api-design-review/reference/smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	@grep -q '## Invocation' api-design-review/examples.md || \
		{ echo "error: api-design-review/examples.md must have Invocation section" >&2; exit 1; }
	$(call require_setup_links_framework,api-design-review)
	$(call require_cross_skill_escalation,api-design-review)
	$(call require_safe_output_link,api-design-review)
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' api-design-review/reference/report-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' api-design-review/reference/report-format.md && \
	 grep -qiE 'escape|fence|backtick' api-design-review/reference/report-format.md && \
	 grep -qi 'redact' api-design-review/reference/report-format.md || \
		{ echo "error: api-design-review/reference/report-format.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "  ok (framework refs)"

lint-database-review:
	@echo "lint-database-review: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,database-review,180,keep orchestrator thin; detail in workflow/)
	@echo "lint-database-review: disable-model-invocation NOT set (ambiently invocable)"
	$(call forbid_disable_model_invocation,database-review)
	@echo "  ok"
	@echo "lint-database-review: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	$(call check_workflow_frontmatter,database-review)
	@echo "lint-database-review: dangling markdown links"
	$(call check_dangling_links,database-review/*.md database-review/reference/*.md database-review/workflow/*.md)
	@echo "lint-database-review: required reference files"
	$(call require_ref_files,database-review/reference,phase-index lazy-load-index report-format smoke-test pressure-tests)
	@grep -q 'pressure-tests' database-review/reference/smoke-test.md || \
		{ echo "error: database-review/reference/smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	@grep -q '## Invocation' database-review/examples.md || \
		{ echo "error: database-review/examples.md must have Invocation section" >&2; exit 1; }
	$(call require_setup_links_framework,database-review)
	$(call require_cross_skill_escalation,database-review)
	$(call require_safe_output_link,database-review)
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' database-review/reference/report-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' database-review/reference/report-format.md && \
	 grep -qiE 'escape|fence|backtick' database-review/reference/report-format.md && \
	 grep -qi 'redact' database-review/reference/report-format.md || \
		{ echo "error: database-review/reference/report-format.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "  ok (framework refs)"

lint-security-review:
	@echo "lint-security-review: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,security-review,180,keep orchestrator thin; detail in workflow/)
	@echo "lint-security-review: disable-model-invocation NOT set (ambiently invocable)"
	$(call forbid_disable_model_invocation,security-review)
	@echo "  ok"
	@echo "lint-security-review: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	$(call check_workflow_frontmatter,security-review)
	@echo "lint-security-review: dangling markdown links"
	$(call check_dangling_links,security-review/*.md security-review/reference/*.md security-review/workflow/*.md)
	@echo "lint-security-review: required reference files"
	$(call require_ref_files,security-review/reference,phase-index lazy-load-index report-format smoke-test pressure-tests)
	@grep -q 'pressure-tests' security-review/reference/smoke-test.md || \
		{ echo "error: security-review/reference/smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	@grep -q '## Invocation' security-review/examples.md || \
		{ echo "error: security-review/examples.md must have Invocation section" >&2; exit 1; }
	$(call require_setup_links_framework,security-review)
	$(call require_cross_skill_escalation,security-review)
	$(call require_safe_output_link,security-review)
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' security-review/reference/report-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' security-review/reference/report-format.md && \
	 grep -qiE 'escape|fence|backtick' security-review/reference/report-format.md && \
	 grep -qi 'redact' security-review/reference/report-format.md || \
		{ echo "error: security-review/reference/report-format.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "  ok (framework refs)"

lint-performance-review:
	@echo "lint-performance-review: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,performance-review,180,keep orchestrator thin; detail in workflow/)
	@echo "lint-performance-review: disable-model-invocation NOT set (ambiently invocable)"
	$(call forbid_disable_model_invocation,performance-review)
	@echo "  ok"
	@echo "lint-performance-review: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	$(call check_workflow_frontmatter,performance-review)
	@echo "lint-performance-review: dangling markdown links"
	$(call check_dangling_links,performance-review/*.md performance-review/reference/*.md performance-review/workflow/*.md)
	@echo "lint-performance-review: required reference files"
	$(call require_ref_files,performance-review/reference,phase-index lazy-load-index report-format smoke-test pressure-tests)
	@grep -q 'pressure-tests' performance-review/reference/smoke-test.md || \
		{ echo "error: performance-review/reference/smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	@grep -q '## Invocation' performance-review/examples.md || \
		{ echo "error: performance-review/examples.md must have Invocation section" >&2; exit 1; }
	$(call require_setup_links_framework,performance-review)
	$(call require_cross_skill_escalation,performance-review)
	$(call require_safe_output_link,performance-review)
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' performance-review/reference/report-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' performance-review/reference/report-format.md && \
	 grep -qiE 'escape|fence|backtick' performance-review/reference/report-format.md && \
	 grep -qi 'redact' performance-review/reference/report-format.md || \
		{ echo "error: performance-review/reference/report-format.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "  ok (framework refs)"

lint-capacity-planner:
	@echo "lint-capacity-planner: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,capacity-planner,180,keep orchestrator thin; detail in workflow/)
	@echo "lint-capacity-planner: disable-model-invocation NOT set (ambiently invocable)"
	$(call forbid_disable_model_invocation,capacity-planner)
	@echo "  ok"
	@echo "lint-capacity-planner: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	$(call check_workflow_frontmatter,capacity-planner)
	@echo "lint-capacity-planner: dangling markdown links"
	$(call check_dangling_links,capacity-planner/*.md capacity-planner/reference/*.md capacity-planner/workflow/*.md)
	@echo "lint-capacity-planner: required reference files"
	$(call require_ref_files,capacity-planner/reference,phase-index lazy-load-index report-format smoke-test pressure-tests)
	@grep -q 'pressure-tests' capacity-planner/reference/smoke-test.md || \
		{ echo "error: capacity-planner/reference/smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	@grep -q '## Invocation' capacity-planner/examples.md || \
		{ echo "error: capacity-planner/examples.md must have Invocation section" >&2; exit 1; }
	$(call require_setup_links_framework,capacity-planner)
	$(call require_cross_skill_escalation,capacity-planner)
	$(call require_safe_output_link,capacity-planner)
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' capacity-planner/reference/report-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' capacity-planner/reference/report-format.md && \
	 grep -qiE 'escape|fence|backtick' capacity-planner/reference/report-format.md && \
	 grep -qi 'redact' capacity-planner/reference/report-format.md || \
		{ echo "error: capacity-planner/reference/report-format.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "  ok (framework refs)"

lint-observability-review:
	@echo "lint-observability-review: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,observability-review,180,keep orchestrator thin; detail in workflow/)
	@echo "lint-observability-review: disable-model-invocation NOT set (ambiently invocable)"
	$(call forbid_disable_model_invocation,observability-review)
	@echo "  ok"
	@echo "lint-observability-review: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	$(call check_workflow_frontmatter,observability-review)
	@echo "lint-observability-review: dangling markdown links"
	$(call check_dangling_links,observability-review/*.md observability-review/reference/*.md observability-review/workflow/*.md)
	@echo "lint-observability-review: required reference files"
	$(call require_ref_files,observability-review/reference,phase-index lazy-load-index report-format smoke-test pressure-tests)
	@grep -q 'pressure-tests' observability-review/reference/smoke-test.md || \
		{ echo "error: observability-review/reference/smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	@grep -q '## Invocation' observability-review/examples.md || \
		{ echo "error: observability-review/examples.md must have Invocation section" >&2; exit 1; }
	$(call require_setup_links_framework,observability-review)
	$(call require_cross_skill_escalation,observability-review)
	$(call require_safe_output_link,observability-review)
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' observability-review/reference/report-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' observability-review/reference/report-format.md && \
	 grep -qiE 'escape|fence|backtick' observability-review/reference/report-format.md && \
	 grep -qi 'redact' observability-review/reference/report-format.md || \
		{ echo "error: observability-review/reference/report-format.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "  ok (framework refs)"

lint-deployment-risk-review:
	@echo "lint-deployment-risk-review: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,deployment-risk-review,180,keep orchestrator thin; detail in workflow/)
	@echo "lint-deployment-risk-review: disable-model-invocation NOT set (ambiently invocable)"
	$(call forbid_disable_model_invocation,deployment-risk-review)
	@echo "  ok"
	@echo "lint-deployment-risk-review: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	$(call check_workflow_frontmatter,deployment-risk-review)
	@echo "lint-deployment-risk-review: dangling markdown links"
	$(call check_dangling_links,deployment-risk-review/*.md deployment-risk-review/reference/*.md deployment-risk-review/workflow/*.md)
	@echo "lint-deployment-risk-review: required reference files"
	$(call require_ref_files,deployment-risk-review/reference,phase-index lazy-load-index report-format smoke-test pressure-tests)
	@grep -q 'pressure-tests' deployment-risk-review/reference/smoke-test.md || \
		{ echo "error: deployment-risk-review/reference/smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	@grep -q '## Invocation' deployment-risk-review/examples.md || \
		{ echo "error: deployment-risk-review/examples.md must have Invocation section" >&2; exit 1; }
	$(call require_setup_links_framework,deployment-risk-review)
	$(call require_cross_skill_escalation,deployment-risk-review)
	$(call require_safe_output_link,deployment-risk-review)
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' deployment-risk-review/reference/report-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' deployment-risk-review/reference/report-format.md && \
	 grep -qiE 'escape|fence|backtick' deployment-risk-review/reference/report-format.md && \
	 grep -qi 'redact' deployment-risk-review/reference/report-format.md || \
		{ echo "error: deployment-risk-review/reference/report-format.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "  ok (framework refs)"

lint-dependency-upgrade-review:
	@echo "lint-dependency-upgrade-review: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,dependency-upgrade-review,180,keep orchestrator thin; detail in workflow/)
	@echo "lint-dependency-upgrade-review: disable-model-invocation NOT set (ambiently invocable)"
	$(call forbid_disable_model_invocation,dependency-upgrade-review)
	@echo "  ok"
	@echo "lint-dependency-upgrade-review: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	$(call check_workflow_frontmatter,dependency-upgrade-review)
	@echo "lint-dependency-upgrade-review: dangling markdown links"
	$(call check_dangling_links,dependency-upgrade-review/*.md dependency-upgrade-review/reference/*.md dependency-upgrade-review/workflow/*.md)
	@echo "lint-dependency-upgrade-review: required reference files"
	$(call require_ref_files,dependency-upgrade-review/reference,phase-index lazy-load-index report-format smoke-test pressure-tests)
	@grep -q 'pressure-tests' dependency-upgrade-review/reference/smoke-test.md || \
		{ echo "error: dependency-upgrade-review/reference/smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	@grep -q '## Invocation' dependency-upgrade-review/examples.md || \
		{ echo "error: dependency-upgrade-review/examples.md must have Invocation section" >&2; exit 1; }
	$(call require_setup_links_framework,dependency-upgrade-review)
	$(call require_cross_skill_escalation,dependency-upgrade-review)
	$(call require_safe_output_link,dependency-upgrade-review)
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' dependency-upgrade-review/reference/report-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' dependency-upgrade-review/reference/report-format.md && \
	 grep -qiE 'escape|fence|backtick' dependency-upgrade-review/reference/report-format.md && \
	 grep -qi 'redact' dependency-upgrade-review/reference/report-format.md || \
		{ echo "error: dependency-upgrade-review/reference/report-format.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "  ok (framework refs)"

lint-tech-debt-assessor:
	@echo "lint-tech-debt-assessor: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,tech-debt-assessor,180,keep orchestrator thin; detail in workflow/)
	@echo "lint-tech-debt-assessor: disable-model-invocation NOT set (ambiently invocable)"
	$(call forbid_disable_model_invocation,tech-debt-assessor)
	@echo "  ok"
	@echo "lint-tech-debt-assessor: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	$(call check_workflow_frontmatter,tech-debt-assessor)
	@echo "lint-tech-debt-assessor: dangling markdown links"
	$(call check_dangling_links,tech-debt-assessor/*.md tech-debt-assessor/reference/*.md tech-debt-assessor/workflow/*.md)
	@echo "lint-tech-debt-assessor: required reference files"
	$(call require_ref_files,tech-debt-assessor/reference,phase-index lazy-load-index report-format smoke-test pressure-tests)
	@grep -q 'pressure-tests' tech-debt-assessor/reference/smoke-test.md || \
		{ echo "error: tech-debt-assessor/reference/smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	@grep -q '## Invocation' tech-debt-assessor/examples.md || \
		{ echo "error: tech-debt-assessor/examples.md must have Invocation section" >&2; exit 1; }
	$(call require_setup_links_framework,tech-debt-assessor)
	$(call require_cross_skill_escalation,tech-debt-assessor)
	$(call require_safe_output_link,tech-debt-assessor)
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' tech-debt-assessor/reference/report-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' tech-debt-assessor/reference/report-format.md && \
	 grep -qiE 'escape|fence|backtick' tech-debt-assessor/reference/report-format.md && \
	 grep -qi 'redact' tech-debt-assessor/reference/report-format.md || \
		{ echo "error: tech-debt-assessor/reference/report-format.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "  ok (framework refs)"

lint-change-impact-analyzer:
	@echo "lint-change-impact-analyzer: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,change-impact-analyzer,180,keep the leaf bounded; detail in workflow/)
	$(call forbid_disable_model_invocation,change-impact-analyzer)
	$(call check_workflow_frontmatter,change-impact-analyzer)
	$(call check_dangling_links,change-impact-analyzer/*.md change-impact-analyzer/reference/*.md change-impact-analyzer/workflow/*.md)
	$(call require_ref_files,change-impact-analyzer/reference,phase-index lazy-load-index report-format smoke-test pressure-tests)
	@grep -q 'pressure-tests' change-impact-analyzer/reference/smoke-test.md
	@grep -q '## Invocation' change-impact-analyzer/examples.md
	$(call require_setup_links_framework,change-impact-analyzer)
	$(call require_cross_skill_escalation,change-impact-analyzer)
	$(call require_safe_output_link,change-impact-analyzer)
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' change-impact-analyzer/reference/report-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' change-impact-analyzer/reference/report-format.md && \
	 grep -qiE 'escape|fence|backtick' change-impact-analyzer/reference/report-format.md && \
	 grep -qi 'redact' change-impact-analyzer/reference/report-format.md
	@python3 -m py_compile scripts/change_impact.py
	@python3 -m pytest -p no:cacheprovider scripts/tests/test_change_impact_analyzer.py -q
	@echo "  ok"

lint: lint-change-impact-analyzer
lint: lint-resilience-review

lint: lint-implementation-planner

lint-implementation-planner:
	@echo "lint-implementation-planner: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,implementation-planner,180,keep the leaf bounded; detail in workflow/)
	$(call forbid_disable_model_invocation,implementation-planner)
	$(call check_workflow_frontmatter,implementation-planner)
	$(call check_dangling_links,implementation-planner/*.md implementation-planner/reference/*.md implementation-planner/workflow/*.md)
	$(call require_ref_files,implementation-planner/reference,phase-index lazy-load-index report-format smoke-test pressure-tests)
	@grep -q 'pressure-tests' implementation-planner/reference/smoke-test.md
	@grep -q '## Invocation' implementation-planner/examples.md
	$(call require_setup_links_framework,implementation-planner)
	$(call require_cross_skill_escalation,implementation-planner)
	$(call require_safe_output_link,implementation-planner)
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' implementation-planner/reference/report-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' implementation-planner/reference/report-format.md && \
	 grep -qiE 'escape|fence|backtick' implementation-planner/reference/report-format.md && \
	 grep -qi 'redact' implementation-planner/reference/report-format.md
	@python3 -m py_compile scripts/implementation_plan.py
	@python3 -m pytest -p no:cacheprovider scripts/tests/test_implementation_plan.py -q
	@echo "  ok"

lint-resilience-review:
	@echo "lint-resilience-review: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,resilience-review,180,keep the leaf bounded; detail in workflow/)
	$(call forbid_disable_model_invocation,resilience-review)
	$(call check_workflow_frontmatter,resilience-review)
	$(call check_dangling_links,resilience-review/*.md resilience-review/reference/*.md resilience-review/workflow/*.md)
	$(call require_ref_files,resilience-review/reference,phase-index lazy-load-index report-format smoke-test pressure-tests)
	@grep -q 'pressure-tests' resilience-review/reference/smoke-test.md
	@grep -q '## Invocation' resilience-review/examples.md
	$(call require_setup_links_framework,resilience-review)
	$(call require_cross_skill_escalation,resilience-review)
	$(call require_safe_output_link,resilience-review)
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' resilience-review/reference/report-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' resilience-review/reference/report-format.md && \
	 grep -qiE 'escape|fence|backtick' resilience-review/reference/report-format.md && \
	 grep -qi 'redact' resilience-review/reference/report-format.md
	@python3 -m py_compile scripts/resilience_review.py
	@python3 -m pytest -p no:cacheprovider scripts/tests/test_resilience_review.py -q
	@echo "  ok"

lint: lint-production-readiness-review

lint-production-readiness-review:
	@echo "lint-production-readiness-review: SKILL.md line count (<= 180)"
	$(call check_skill_md_length,production-readiness-review,180,keep the orchestrator bounded; detail in workflow/)
	$(call forbid_disable_model_invocation,production-readiness-review)
	$(call check_workflow_frontmatter,production-readiness-review)
	$(call check_dangling_links,production-readiness-review/*.md production-readiness-review/reference/*.md production-readiness-review/workflow/*.md)
	$(call require_ref_files,production-readiness-review/reference,phase-index lazy-load-index report-format smoke-test pressure-tests)
	@grep -q 'pressure-tests' production-readiness-review/reference/smoke-test.md
	@grep -q '## Invocation' production-readiness-review/examples.md
	$(call require_setup_links_framework,production-readiness-review)
	$(call require_cross_skill_escalation,production-readiness-review)
	$(call require_safe_output_link,production-readiness-review)
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' production-readiness-review/reference/report-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' production-readiness-review/reference/report-format.md && \
	 grep -qiE 'escape|fence|backtick' production-readiness-review/reference/report-format.md && \
	 grep -qi 'redact' production-readiness-review/reference/report-format.md
	@python3 -m py_compile scripts/production_readiness.py
	@python3 -m pytest -p no:cacheprovider scripts/tests/test_production_readiness_contract.py -q
	@echo "  ok"

lint-framework:
	@echo "lint-framework: shared docs present"
	@test -f docs/skill-framework/README.md
	@for f in confidence-bands cross-skill-escalation post-action-templates \
		smoke-test-conventions examples-conventions phase-glossary review-metadata-schema \
		skill-routing prompt-injection claude-code-setup org-rollup-schema test-creation-principles \
		setup-freshness; do \
		test -f docs/skill-framework/shared/$$f.md || exit 1; \
		test -s docs/skill-framework/shared/$$f.md || \
			{ echo "error: docs/skill-framework/shared/$$f.md is empty" >&2; exit 1; }; \
	done
	@grep -q 'confidence-bands' docs/skill-framework/README.md
	@echo "lint-framework: required sections"
	@grep -q '^## 1\. Purpose' docs/skill-framework/shared/confidence-bands.md
	@grep -q '^## 7\. Anti-patterns' docs/skill-framework/shared/confidence-bands.md
	@grep -q '^## 1\. Symmetric matrix' docs/skill-framework/shared/cross-skill-escalation.md
	@grep -q 'User prompt template' docs/skill-framework/shared/cross-skill-escalation.md
	@grep -q '^## 7\. Confirmation gates' docs/skill-framework/shared/post-action-templates.md
	@grep -q 'Jira ticket update fields' docs/skill-framework/shared/post-action-templates.md
	@grep -q '^## 5\. Failure diagnosis' docs/skill-framework/shared/smoke-test-conventions.md
	@grep -q 'Invocation string' docs/skill-framework/shared/smoke-test-conventions.md
	@grep -q 'Invocation table template' docs/skill-framework/shared/examples-conventions.md
	@grep -q '^## 1\. Required sections' docs/skill-framework/shared/examples-conventions.md
	@grep -q '^## 2\. Scenario format' docs/skill-framework/shared/examples-conventions.md
	@grep -q '^## 5\. Anti-patterns' docs/skill-framework/shared/examples-conventions.md
	@for skill in pr-review pr-gatekeeper incident-rca incident-triage-agent k8s-overprovisioning-datadog domain-comprehension squad-map who-owns-x-bot new-hire-guide release-readiness-checker migration-program-manager mysql-to-postgres-sql loop-task-implementer backlog-runner cost-optimization-sprint-planner weekly-squad-digest prd-architect test-writer unit-test-creator integration-test-creator contract-test-creator e2e-test-creator api-test-creator architecture-review system-design api-design-review database-review security-review performance-review capacity-planner observability-review deployment-risk-review dependency-upgrade-review tech-debt-assessor change-impact-analyzer resilience-review implementation-planner production-readiness-review; do \
		test -f $$skill/examples.md || \
			{ echo "error: missing $$skill/examples.md (examples-conventions)" >&2; exit 1; }; \
		grep -q '## Invocation' $$skill/examples.md || \
			{ echo "error: $$skill/examples.md must have Invocation section" >&2; exit 1; }; \
	done
	@grep -q '^## 5\. Cross-skill analogies' docs/skill-framework/shared/phase-glossary.md
	@grep -q 'MCP profile' docs/skill-framework/shared/phase-glossary.md
	@grep -q 'Minimum evidence gate' docs/skill-framework/shared/phase-glossary.md
	@grep -q '^## 3\. `history` block' docs/skill-framework/shared/review-metadata-schema.md
	@grep -q '^## 8\. `assessment_metadata`' docs/skill-framework/shared/review-metadata-schema.md
	@grep -q 'investigation_quality' docs/skill-framework/shared/review-metadata-schema.md
	@grep -q 'repository_health' docs/skill-framework/shared/review-metadata-schema.md
	@grep -q '^## Rule' docs/skill-framework/shared/prompt-injection.md
	@grep -q 'incident-rca.*Phase 2' docs/skill-framework/shared/review-metadata-schema.md
	@grep -q 'domain-comprehension' docs/skill-framework/shared/confidence-bands.md
	@grep -q 'mysql-to-postgres-sql' docs/skill-framework/shared/confidence-bands.md
	@grep -q 'risk tier' docs/skill-framework/shared/confidence-bands.md
	@grep -q '### 8.3 domain-comprehension' docs/skill-framework/shared/review-metadata-schema.md
	@grep -q '### 8.4 squad-map' docs/skill-framework/shared/review-metadata-schema.md
	@grep -q '### 8.5 mysql-to-postgres-sql' docs/skill-framework/shared/review-metadata-schema.md
	@grep -q 'mysql-to-postgres-sql mapping' docs/skill-framework/shared/phase-glossary.md
	@grep -q 'squad map complete' docs/skill-framework/shared/post-action-templates.md
	@grep -q 'kubesense-alerts' docs/skill-framework/shared/cross-skill-escalation.md || \
		{ echo "error: cross-skill-escalation must include kubesense-alerts handoff" >&2; exit 1; }
	@grep -q 'MYSQL_TO_PG_SQL_REWRITES' docs/skill-framework/shared/cross-skill-escalation.md || \
		{ echo "error: cross-skill-escalation must include mysql artifact handoff block" >&2; exit 1; }
	@grep -q 'Approach B' docs/skill-framework/README.md || \
		{ echo "error: skill-framework README must document deferred Approach B" >&2; exit 1; }
	@test -f domain-comprehension/reference/assessment-metadata.md
	@test -f squad-map/reference/assessment-metadata.md
	@test -f mysql-to-postgres-sql/reference/assessment-metadata.md
	@grep -q 'review-metadata-schema' docs/skill-framework/README.md
	@echo "lint-framework: SETUP.md freshness tables"
	@python3 scripts/validate_setup_freshness.py
	@echo "  ok"
	@echo "lint-framework: dangling markdown links"
	@bash scripts/lint-dangling-md-links.sh docs/skill-framework/README.md docs/skill-framework/shared/*.md && echo "  ok" || \
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
	@grep -q '| Complete |' docs/skill-framework/README.md
	@for skill in pr-review pr-gatekeeper incident-rca incident-triage-agent k8s-overprovisioning-datadog domain-comprehension squad-map who-owns-x-bot new-hire-guide release-readiness-checker migration-program-manager mysql-to-postgres-sql loop-task-implementer backlog-runner cost-optimization-sprint-planner weekly-squad-digest prd-architect test-writer unit-test-creator integration-test-creator contract-test-creator e2e-test-creator api-test-creator architecture-review system-design api-design-review database-review security-review performance-review capacity-planner observability-review deployment-risk-review dependency-upgrade-review tech-debt-assessor change-impact-analyzer resilience-review implementation-planner production-readiness-review; do \
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
	for skill in pr-review pr-gatekeeper incident-rca incident-triage-agent k8s-overprovisioning-datadog domain-comprehension squad-map who-owns-x-bot new-hire-guide release-readiness-checker migration-program-manager mysql-to-postgres-sql loop-task-implementer backlog-runner cost-optimization-sprint-planner weekly-squad-digest prd-architect test-writer unit-test-creator integration-test-creator contract-test-creator e2e-test-creator api-test-creator architecture-review system-design api-design-review database-review security-review performance-review capacity-planner observability-review deployment-risk-review dependency-upgrade-review tech-debt-assessor change-impact-analyzer resilience-review implementation-planner production-readiness-review; do \
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
	@cache="$(CURDIR)/.pycache-lint"; \
	export PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$$cache"; \
	trap 'rm -rf "$$cache"' EXIT; \
	python3 -m py_compile scripts/validate_metadata_footer.py || exit 1; \
	python3 scripts/validate_metadata_footer.py \
		docs/skill-framework/shared/examples/review-metadata.example.yaml \
		docs/skill-framework/shared/examples/assessment-metadata-rca.example.yaml \
		docs/skill-framework/shared/examples/assessment-metadata-k8s.example.yaml \
		pr-review/tests/fixtures/phase5-review-metadata.yaml || exit 1
	@echo "lint-framework: source-tree reference validation (anchors + local links, cross-cutting docs)"
	@python3 scripts/validate_references.py --source-tree . --exclude docs/superpowers --exclude docs/skill-framework --exclude .claude/worktrees || exit 1
	@echo "lint-framework: ok"

# Split out from lint-framework: this is the repo's dominant test cost (the shared
# scripts/tests/ suite, ~1700 tests covering registry/eval/operational-upkeep/metadata
# logic) so CI can schedule it as its own parallel job instead of serializing it after
# lint-framework's cheap doc/structure checks.
lint-framework-tests:
	@echo "lint-framework-tests: scripts/tests/ suite"
	@if python3 -c "import pytest" >/dev/null 2>&1; then \
		python3 -m pytest -p no:cacheprovider $(PYTEST_XDIST_FLAG) scripts/tests/ -q || exit 1; \
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
