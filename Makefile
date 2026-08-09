.PHONY: install install-pr-review install-pr-gatekeeper install-k8s-overprovisioning install-incident-rca install-incident-rca-deps install-incident-triage-agent install-domain-comprehension install-squad-map install-who-owns-x-bot install-new-hire-guide install-release-readiness-checker install-migration-program-manager install-cost-optimization-sprint-planner install-mysql-to-postgres-sql install-loop-task-implementer install-backlog-runner install-weekly-squad-digest install-unit-test-creator install-integration-test-creator install-contract-test-creator install-e2e-test-creator install-api-test-creator install-test-writer install-prd-architect install-claude install-claude-pr-review install-claude-pr-gatekeeper install-claude-k8s-overprovisioning install-claude-incident-rca install-claude-incident-triage-agent install-claude-domain-comprehension install-claude-squad-map install-claude-who-owns-x-bot install-claude-new-hire-guide install-claude-release-readiness-checker install-claude-migration-program-manager install-claude-cost-optimization-sprint-planner install-claude-mysql-to-postgres-sql install-claude-loop-task-implementer install-claude-backlog-runner install-claude-weekly-squad-digest install-claude-unit-test-creator install-claude-integration-test-creator install-claude-contract-test-creator install-claude-e2e-test-creator install-claude-api-test-creator install-claude-prd-architect install-claude-test-writer lint lint-framework lint-pr-review lint-pr-gatekeeper lint-k8s-skill lint-k8s lint-incident-rca lint-incident-triage-agent lint-domain-comprehension lint-squad-map lint-who-owns-x-bot lint-new-hire-guide lint-release-readiness-checker lint-migration-program-manager lint-cost-optimization-sprint-planner lint-mysql-to-postgres-sql lint-loop-task-implementer lint-backlog-runner lint-weekly-squad-digest lint-unit-test-creator lint-integration-test-creator lint-contract-test-creator lint-e2e-test-creator lint-api-test-creator lint-test-writer setup-hooks setup validate-registry generate generate-check verify-github-ruleset kubesense-errors

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

setup:
	@echo "setup: installing Python dev dependencies (requirements.lock)"
	@python3 -m pip install --require-hashes -r requirements.lock 2>/dev/null || \
		python3 -m pip install --user --break-system-packages --require-hashes -r requirements.lock
	@$(MAKE) setup-hooks

lint-requirements-lock:
	@python3 scripts/check_requirements_lock.py

verify-install:
	@bash scripts/tests/test_install_integration.sh

verify-install-all:
	@bash scripts/tests/test_install_all_skills.sh

verify-github-ruleset:
	@python3 scripts/check_github_ruleset.py

validate-registry:
	@python3 -m scripts.registry validate

backfill-capabilities-check:
	@python3 -m scripts.registry backfill-capabilities --check

validate-evals:
	@python3 -m scripts.evals

doctor:
	@python3 scripts/doctor.py

package-release:
	@python3 scripts/package_release.py --output-dir dist

verify-release-tag:
	@test -n "$(TAG)" || (echo "error: set TAG=vX.Y.Z" >&2; exit 1)
	@python3 scripts/verify_release_tag.py "$(TAG)"

generate:
	@python3 -m scripts.registry generate

generate-check:
	@python3 -m scripts.registry generate --check

lint: validate-registry backfill-capabilities-check generate-check validate-evals lint-framework lint-pr-review lint-pr-gatekeeper lint-k8s-skill lint-incident-rca lint-incident-triage-agent lint-domain-comprehension lint-squad-map lint-who-owns-x-bot lint-new-hire-guide lint-release-readiness-checker lint-migration-program-manager lint-cost-optimization-sprint-planner lint-mysql-to-postgres-sql lint-loop-task-implementer lint-backlog-runner lint-weekly-squad-digest lint-unit-test-creator lint-integration-test-creator lint-contract-test-creator lint-e2e-test-creator lint-api-test-creator lint-test-writer lint-prd-architect lint-requirements-lock verify-install verify-install-all
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

lint-pr-review: lint-pr-review-skill lint-pr-review-scripts

lint-pr-review-scripts:
	@echo "py_compile pr-review/scripts/diff-to-positions.py pr-review/scripts/pr_review_policy_guards.py"
	@echo "pytest pr-review/tests/"
	@cache="$(CURDIR)/.pycache-lint"; \
	export PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$$cache"; \
	trap 'rm -rf "$$cache"' EXIT; \
	python3 -m py_compile pr-review/scripts/diff-to-positions.py || exit 1; \
	python3 -m py_compile pr-review/scripts/pr_review_policy_guards.py || exit 1; \
	if python3 -c "import pytest" >/dev/null 2>&1; then \
		python3 -m pytest -p no:cacheprovider pr-review/tests/ -q || exit 1; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run script tests" >&2; \
		exit 1; \
	fi

lint-pr-review-skill:
	@echo "lint-pr-review-skill: SKILL.md line count (<= 180)"
	@lines=$$(wc -l < pr-review/SKILL.md | tr -d ' '); \
	if [ "$$lines" -gt 180 ]; then \
		echo "error: pr-review SKILL.md $$lines lines (> 180) — keep orchestrator thin; detail in workflow/" >&2; \
		exit 1; \
	fi; \
	echo "  ok ($$lines lines)"
	@echo "lint-pr-review-skill: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	@fail=0; \
	for f in pr-review/workflow/*.md; do \
		fm=$$(awk '/^---$$/{c++; next} c==1' "$$f"); \
		for key in workflow_version phase produces consumes; do \
			if ! printf '%s\n' "$$fm" | grep -q "^$$key:"; then \
				echo "  missing $$key frontmatter: $$f" >&2; fail=1; \
			fi; \
		done; \
	done; \
	if [ "$$fail" -ne 0 ]; then echo "error: pr-review workflow/*.md must declare workflow_version, phase, produces, consumes" >&2; exit 1; fi; \
	echo "  ok"
	@echo "lint-pr-review-skill: route-aware workflow contract"
	@python3 -m scripts.validate_workflow_contracts pr-review
	@echo "lint-pr-review-skill: dangling markdown links"
	@bash scripts/lint-dangling-md-links.sh pr-review/*.md pr-review/reference/*.md pr-review/workflow/*.md && echo "  ok" || \
		{ echo "error: dangling reference link(s) found" >&2; exit 1; }
	@grep -q 'cross-skill-escalation' pr-review/SKILL.md || \
		{ echo "error: pr-review SKILL.md must link to shared cross-skill-escalation" >&2; exit 1; }
	@grep -q 'smoke-test' pr-review/SKILL.md || \
		{ echo "error: pr-review SKILL.md must link to reference/smoke-test.md" >&2; exit 1; }
	@grep -q 'docs/skill-framework/shared/safe-output.md' pr-review/SKILL.md || \
		{ echo "error: pr-review SKILL.md must link to shared safe-output" >&2; exit 1; }
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
	@test -f pr-gatekeeper/SKILL.md || \
		{ echo "error: missing pr-gatekeeper/SKILL.md" >&2; exit 1; }
	@lines=$$(wc -l < pr-gatekeeper/SKILL.md | tr -d ' '); \
	if [ -z "$$lines" ] || [ "$$lines" -eq 0 ]; then \
		echo "error: pr-gatekeeper/SKILL.md is empty" >&2; exit 1; \
	elif [ "$$lines" -gt 180 ]; then \
		echo "error: pr-gatekeeper SKILL.md $$lines lines (> 180) — keep orchestrator thin; detail in workflow/" >&2; \
		exit 1; \
	fi; \
	echo "  ok ($$lines lines)"
	@echo "lint-pr-gatekeeper: disable-model-invocation set (automation entry point, must not compete with pr-review's ambient invocation)"
	@grep -q '^disable-model-invocation: true' pr-gatekeeper/SKILL.md || \
		{ echo "error: pr-gatekeeper/SKILL.md must set disable-model-invocation: true" >&2; exit 1; }
	@echo "  ok"
	@echo "lint-pr-gatekeeper: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	@fail=0; \
	for f in pr-gatekeeper/workflow/*.md; do \
		fm=$$(awk '/^---$$/{c++; next} c==1' "$$f"); \
		for key in workflow_version phase produces consumes; do \
			if ! printf '%s\n' "$$fm" | grep -q "^$$key:"; then \
				echo "  missing $$key frontmatter: $$f" >&2; fail=1; \
			fi; \
		done; \
	done; \
	if [ "$$fail" -ne 0 ]; then echo "error: pr-gatekeeper workflow/*.md must declare workflow_version, phase, produces, consumes" >&2; exit 1; fi; \
	echo "  ok"
	@echo "lint-pr-gatekeeper: dangling markdown links"
	@bash scripts/lint-dangling-md-links.sh pr-gatekeeper/*.md pr-gatekeeper/reference/*.md pr-gatekeeper/workflow/*.md && echo "  ok" || \
		{ echo "error: dangling reference link(s) found" >&2; exit 1; }
	@echo "lint-pr-gatekeeper: required reference files"
	@for f in phase-index lazy-load-index auto-post-policy smoke-test pressure-tests; do \
		test -f pr-gatekeeper/reference/$$f.md || \
			{ echo "error: missing pr-gatekeeper/reference/$$f.md" >&2; exit 1; }; \
	done
	@grep -q 'pressure-tests' pr-gatekeeper/reference/smoke-test.md || \
		{ echo "error: smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	@grep -q 'skill-framework' pr-gatekeeper/SETUP.md || \
		{ echo "error: pr-gatekeeper/SETUP.md must link to docs/skill-framework" >&2; exit 1; }
	@grep -q 'docs/skill-framework/shared/safe-output.md' pr-gatekeeper/SKILL.md || \
		{ echo "error: pr-gatekeeper/SKILL.md must link to shared safe-output" >&2; exit 1; }
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' pr-gatekeeper/reference/auto-post-policy.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' pr-gatekeeper/reference/auto-post-policy.md && \
	 grep -qiE 'escape|fence|backtick' pr-gatekeeper/reference/auto-post-policy.md || \
		{ echo "error: auto-post-policy.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "lint-pr-gatekeeper: idempotency store pytest"
	@if python3 -c "import pytest" >/dev/null 2>&1; then \
		python3 -m pytest -p no:cacheprovider pr-gatekeeper/tests/test_idempotency_store.py -q || exit 1; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run pr-gatekeeper tests" >&2; \
	fi
	@echo "  ok (framework refs + idempotency tests)"
	@echo "lint-pr-gatekeeper: ask-point drift check (pr-review workflow vs auto-post-policy.md)"
	@python3 pr-gatekeeper/scripts/check-ask-point-drift.py || \
		{ echo "error: pr-review ask-point drift detected — see pr-gatekeeper/reference/auto-post-policy.md" >&2; exit 1; }

lint-k8s-skill:
	@echo "lint-k8s-skill: SKILL.md line count (<= 150)"
	@lines=$$(wc -l < k8s-overprovisioning-datadog/SKILL.md | tr -d ' '); \
	if [ "$$lines" -gt 150 ]; then \
		echo "error: k8s SKILL.md $$lines lines (> 150) — keep orchestrator thin; detail in workflow/" >&2; \
		exit 1; \
	fi; \
	echo "  ok ($$lines lines)"
	@echo "lint-k8s-skill: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	@fail=0; \
	for f in k8s-overprovisioning-datadog/workflow/*.md; do \
		fm=$$(awk '/^---$$/{c++; next} c==1' "$$f"); \
		for key in workflow_version phase produces consumes; do \
			if ! printf '%s\n' "$$fm" | grep -q "^$$key:"; then \
				echo "  missing $$key frontmatter: $$f" >&2; fail=1; \
			fi; \
		done; \
	done; \
	if [ "$$fail" -ne 0 ]; then echo "error: k8s workflow/*.md must declare workflow_version, phase, produces, consumes" >&2; exit 1; fi; \
	echo "  ok"
	@echo "lint-k8s-skill: dangling markdown links"
	@bash scripts/lint-dangling-md-links.sh k8s-overprovisioning-datadog/*.md k8s-overprovisioning-datadog/workflow/*.md k8s-overprovisioning-datadog/reference/*.md k8s-overprovisioning-datadog/render/*.md k8s-overprovisioning-datadog/templates/*.md && echo "  ok" || \
		{ echo "error: dangling reference link(s) found" >&2; exit 1; }
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
	@grep -q 'skill-framework' k8s-overprovisioning-datadog/SETUP.md || \
		{ echo "error: k8s-overprovisioning-datadog/SETUP.md must link to docs/skill-framework" >&2; exit 1; }
	@grep -q 'cross-skill-escalation' k8s-overprovisioning-datadog/SKILL.md || \
		{ echo "error: k8s SKILL.md must link to shared cross-skill-escalation" >&2; exit 1; }
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
		python3 -m pytest -p no:cacheprovider k8s-overprovisioning-datadog/tests/ -q || exit 1; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run k8s script tests" >&2; \
		exit 1; \
	fi; \
	echo "  ok"

lint-k8s: lint-k8s-skill

lint-incident-rca:
	@echo "lint-incident-rca: SKILL.md line count (<= 180)"
	@lines=$$(wc -l < incident-rca/SKILL.md | tr -d ' '); \
	if [ "$$lines" -gt 180 ]; then \
		echo "error: incident-rca SKILL.md $$lines lines (> 180) — push detail into workflow/ and reference/" >&2; \
		exit 1; \
	fi; \
	echo "  ok ($$lines lines)"
	@echo "lint-incident-rca: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	@fail=0; \
	for f in incident-rca/workflow/*.md; do \
		fm=$$(awk '/^---$$/{c++; next} c==1' "$$f"); \
		for key in workflow_version phase produces consumes; do \
			if ! printf '%s\n' "$$fm" | grep -q "^$$key:"; then \
				echo "  missing $$key frontmatter: $$f" >&2; fail=1; \
			fi; \
		done; \
	done; \
	if [ "$$fail" -ne 0 ]; then echo "error: incident-rca workflow/*.md must declare workflow_version, phase, produces, consumes" >&2; exit 1; fi; \
	echo "  ok"
	@echo "lint-incident-rca: evidence.example.json parses as JSON"
	@cache="$(CURDIR)/.pycache-lint-rca"; \
	export PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$$cache"; \
	trap 'rm -rf "$$cache"' EXIT; \
	python3 -c "import json,sys; json.load(open('incident-rca/reference/evidence.example.json'))" || \
		{ echo "error: incident-rca/reference/evidence.example.json is not valid JSON" >&2; exit 1; }; \
	echo "  ok"
	@echo "lint-incident-rca: dangling markdown links"
	@bash scripts/lint-dangling-md-links.sh incident-rca/*.md incident-rca/reference/*.md incident-rca/workflow/*.md && echo "  ok" || \
		{ echo "error: dangling reference link(s) found" >&2; exit 1; }
	@echo "lint-incident-rca: framework reference files"
	@for f in phase-index lazy-load-index smoke-test mcp-capabilities; do \
		test -f incident-rca/reference/$$f.md || \
			{ echo "error: missing incident-rca/reference/$$f.md" >&2; exit 1; }; \
	done
	@grep -q 'skill-framework' incident-rca/SETUP.md || \
		{ echo "error: incident-rca/SETUP.md must link to docs/skill-framework" >&2; exit 1; }
	@grep -q 'cross-skill-escalation' incident-rca/SKILL.md || \
		{ echo "error: incident-rca SKILL.md must link to shared cross-skill-escalation" >&2; exit 1; }
	@grep -q 'skill_version' incident-rca/SKILL.md || \
		{ echo "error: incident-rca SKILL.md must use skill_version (not schema_version)" >&2; exit 1; }
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
		python3 -m pytest -p no:cacheprovider incident-rca/tests/ -q || exit 1; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run schema tests" >&2; \
		exit 1; \
	fi; \
	echo "  ok"

lint-incident-triage-agent:
	@echo "lint-incident-triage-agent: SKILL.md line count (<= 180)"
	@test -f incident-triage-agent/SKILL.md || \
		{ echo "error: missing incident-triage-agent/SKILL.md" >&2; exit 1; }
	@lines=$$(wc -l < incident-triage-agent/SKILL.md | tr -d ' '); \
	if [ -z "$$lines" ] || [ "$$lines" -eq 0 ]; then \
		echo "error: incident-triage-agent/SKILL.md is empty" >&2; exit 1; \
	elif [ "$$lines" -gt 180 ]; then \
		echo "error: incident-triage-agent SKILL.md $$lines lines (> 180) — keep orchestrator thin; detail in workflow/" >&2; \
		exit 1; \
	fi; \
	echo "  ok ($$lines lines)"
	@echo "lint-incident-triage-agent: disable-model-invocation set (automation entry point, must not compete with incident-rca/squad-map's ambient invocation)"
	@grep -q '^disable-model-invocation: true' incident-triage-agent/SKILL.md || \
		{ echo "error: incident-triage-agent/SKILL.md must set disable-model-invocation: true" >&2; exit 1; }
	@echo "  ok"
	@echo "lint-incident-triage-agent: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	@fail=0; \
	for f in incident-triage-agent/workflow/*.md; do \
		fm=$$(awk '/^---$$/{c++; next} c==1' "$$f"); \
		for key in workflow_version phase produces consumes; do \
			if ! printf '%s\n' "$$fm" | grep -q "^$$key:"; then \
				echo "  missing $$key frontmatter: $$f" >&2; fail=1; \
			fi; \
		done; \
	done; \
	if [ "$$fail" -ne 0 ]; then echo "error: incident-triage-agent workflow/*.md must declare workflow_version, phase, produces, consumes" >&2; exit 1; fi; \
	echo "  ok"
	@echo "lint-incident-triage-agent: dangling markdown links"
	@bash scripts/lint-dangling-md-links.sh incident-triage-agent/*.md incident-triage-agent/reference/*.md incident-triage-agent/workflow/*.md && echo "  ok" || \
		{ echo "error: dangling reference link(s) found" >&2; exit 1; }
	@echo "lint-incident-triage-agent: required reference files"
	@for f in phase-index lazy-load-index unattended-gate-policy triage-doc-format postmortem-format smoke-test pressure-tests; do \
		test -f incident-triage-agent/reference/$$f.md || \
			{ echo "error: missing incident-triage-agent/reference/$$f.md" >&2; exit 1; }; \
	done
	@grep -q 'pressure-tests' incident-triage-agent/reference/smoke-test.md || \
		{ echo "error: smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	@grep -q 'skill-framework' incident-triage-agent/SETUP.md || \
		{ echo "error: incident-triage-agent/SETUP.md must link to docs/skill-framework" >&2; exit 1; }
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
		"$$PY" -m pytest -p no:cacheprovider domain-comprehension/tests/ -q || exit 1; \
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
	@test -f domain-comprehension/SKILL.md || \
		{ echo "error: missing domain-comprehension/SKILL.md" >&2; exit 1; }
	@lines=$$(wc -l < domain-comprehension/SKILL.md | tr -d ' '); \
	if [ -z "$$lines" ] || [ "$$lines" -eq 0 ]; then \
		echo "error: domain-comprehension/SKILL.md is empty" >&2; exit 1; \
	elif [ "$$lines" -gt 180 ]; then \
		echo "error: domain-comprehension SKILL.md $$lines lines (> 180) — keep orchestrator thin; detail in workflow/" >&2; \
		exit 1; \
	fi; \
	echo "  ok ($$lines lines)"
	@echo "lint-domain-comprehension: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	@fail=0; \
	for f in domain-comprehension/workflow/*.md; do \
		fm=$$(awk '/^---$$/{c++; next} c==1' "$$f"); \
		for key in workflow_version phase produces consumes; do \
			if ! printf '%s\n' "$$fm" | grep -q "^$$key:"; then \
				echo "  missing $$key frontmatter: $$f" >&2; fail=1; \
			fi; \
		done; \
	done; \
	if [ "$$fail" -ne 0 ]; then echo "error: domain-comprehension workflow/*.md must declare workflow_version, phase, produces, consumes" >&2; exit 1; fi; \
	echo "  ok"
	@echo "lint-domain-comprehension: dangling markdown links"
	@bash scripts/lint-dangling-md-links.sh domain-comprehension/*.md domain-comprehension/reference/*.md domain-comprehension/workflow/*.md domain-comprehension/reference/domain-packs/*.md && echo "  ok" || \
		{ echo "error: dangling reference link(s) found" >&2; exit 1; }
	@echo "lint-domain-comprehension: framework reference files"
	@for f in phase-index lazy-load-index smoke-test mcp-capabilities phase-outputs manifest-schema \
		repo-classification evidence-precedence evidence-summary business-flows large-scale-execution; do \
		test -f domain-comprehension/reference/$$f.md || \
			{ echo "error: missing domain-comprehension/reference/$$f.md" >&2; exit 1; }; \
	done
	@test -f domain-comprehension/templates/manifest.yaml || \
		{ echo "error: missing domain-comprehension/templates/manifest.yaml" >&2; exit 1; }
	@test -f domain-comprehension/templates/BUSINESS_FLOWS.md || exit 1
	@test -f domain-comprehension/templates/KNOWN_OMISSIONS.md || exit 1
	@grep -q 'skill-framework' domain-comprehension/SETUP.md || \
		{ echo "error: domain-comprehension/SETUP.md must link to docs/skill-framework" >&2; exit 1; }
	@grep -q 'cross-skill-escalation' domain-comprehension/SKILL.md || \
		{ echo "error: domain-comprehension SKILL.md must link to shared cross-skill-escalation" >&2; exit 1; }
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

lint-squad-map:
	@echo "lint-squad-map: SKILL.md line count (<= 180)"
	@test -f squad-map/SKILL.md || \
		{ echo "error: missing squad-map/SKILL.md" >&2; exit 1; }
	@lines=$$(wc -l < squad-map/SKILL.md | tr -d ' '); \
	if [ -z "$$lines" ] || [ "$$lines" -eq 0 ]; then \
		echo "error: squad-map/SKILL.md is empty" >&2; exit 1; \
	elif [ "$$lines" -gt 180 ]; then \
		echo "error: squad-map SKILL.md $$lines lines (> 180) — keep orchestrator thin; detail in workflow/" >&2; \
		exit 1; \
	fi; \
	echo "  ok ($$lines lines)"
	@echo "lint-squad-map: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	@fail=0; \
	for f in squad-map/workflow/*.md; do \
		fm=$$(awk '/^---$$/{c++; next} c==1' "$$f"); \
		for key in workflow_version phase produces consumes; do \
			if ! printf '%s\n' "$$fm" | grep -q "^$$key:"; then \
				echo "  missing $$key frontmatter: $$f" >&2; fail=1; \
			fi; \
		done; \
	done; \
	if [ "$$fail" -ne 0 ]; then echo "error: squad-map workflow/*.md must declare workflow_version, phase, produces, consumes" >&2; exit 1; fi; \
	echo "  ok"
	@echo "lint-squad-map: dangling markdown links"
	@bash scripts/lint-dangling-md-links.sh squad-map/*.md squad-map/reference/*.md squad-map/workflow/*.md && echo "  ok" || \
		{ echo "error: dangling reference link(s) found" >&2; exit 1; }
	@echo "lint-squad-map: required reference files"
	@for f in squad-mapping mcp-capabilities config-schema smoke-test lazy-load-index phase-index; do \
		test -f squad-map/reference/$$f.md || \
			{ echo "error: missing squad-map/reference/$$f.md" >&2; exit 1; }; \
	done
	@test -f squad-map/templates/SQUAD_MAP.md || \
		{ echo "error: missing squad-map/templates/SQUAD_MAP.md" >&2; exit 1; }
	@grep -q 'skill-framework' squad-map/SETUP.md || \
		{ echo "error: squad-map/SETUP.md must link to docs/skill-framework" >&2; exit 1; }
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
		python3 -m pytest -p no:cacheprovider squad-map/tests/ -q || exit 1; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run squad-map tests" >&2; \
		exit 1; \
	fi; \
	echo "  ok (framework refs + squad_mapping tests)"

lint-who-owns-x-bot:
	@echo "lint-who-owns-x-bot: SKILL.md line count (<= 180)"
	@test -f who-owns-x-bot/SKILL.md || \
		{ echo "error: missing who-owns-x-bot/SKILL.md" >&2; exit 1; }
	@lines=$$(wc -l < who-owns-x-bot/SKILL.md | tr -d ' '); \
	if [ -z "$$lines" ] || [ "$$lines" -eq 0 ]; then \
		echo "error: who-owns-x-bot/SKILL.md is empty" >&2; exit 1; \
	elif [ "$$lines" -gt 180 ]; then \
		echo "error: who-owns-x-bot SKILL.md $$lines lines (> 180) — keep orchestrator thin; detail in workflow/" >&2; \
		exit 1; \
	fi; \
	echo "  ok ($$lines lines)"
	@echo "lint-who-owns-x-bot: disable-model-invocation set (automation entry point, must not compete with squad-map's ambient invocation)"
	@grep -q '^disable-model-invocation: true' who-owns-x-bot/SKILL.md || \
		{ echo "error: who-owns-x-bot/SKILL.md must set disable-model-invocation: true" >&2; exit 1; }
	@echo "  ok"
	@echo "lint-who-owns-x-bot: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	@fail=0; \
	for f in who-owns-x-bot/workflow/*.md; do \
		fm=$$(awk '/^---$$/{c++; next} c==1' "$$f"); \
		for key in workflow_version phase produces consumes; do \
			if ! printf '%s\n' "$$fm" | grep -q "^$$key:"; then \
				echo "  missing $$key frontmatter: $$f" >&2; fail=1; \
			fi; \
		done; \
	done; \
	if [ "$$fail" -ne 0 ]; then echo "error: who-owns-x-bot workflow/*.md must declare workflow_version, phase, produces, consumes" >&2; exit 1; fi; \
	echo "  ok"
	@echo "lint-who-owns-x-bot: dangling markdown links"
	@bash scripts/lint-dangling-md-links.sh who-owns-x-bot/*.md who-owns-x-bot/reference/*.md who-owns-x-bot/workflow/*.md && echo "  ok" || \
		{ echo "error: dangling reference link(s) found" >&2; exit 1; }
	@echo "lint-who-owns-x-bot: required reference files"
	@for f in phase-index lazy-load-index slack-format smoke-test pressure-tests; do \
		test -f who-owns-x-bot/reference/$$f.md || \
			{ echo "error: missing who-owns-x-bot/reference/$$f.md" >&2; exit 1; }; \
	done
	@grep -q 'pressure-tests' who-owns-x-bot/reference/smoke-test.md || \
		{ echo "error: smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	@grep -q 'skill-framework' who-owns-x-bot/SETUP.md || \
		{ echo "error: who-owns-x-bot/SETUP.md must link to docs/skill-framework" >&2; exit 1; }
	@echo "  ok (framework refs)"

lint-new-hire-guide:
	@echo "lint-new-hire-guide: SKILL.md line count (<= 180)"
	@test -f new-hire-guide/SKILL.md || \
		{ echo "error: missing new-hire-guide/SKILL.md" >&2; exit 1; }
	@lines=$$(wc -l < new-hire-guide/SKILL.md | tr -d ' '); \
	if [ -z "$$lines" ] || [ "$$lines" -eq 0 ]; then \
		echo "error: new-hire-guide/SKILL.md is empty" >&2; exit 1; \
	elif [ "$$lines" -gt 180 ]; then \
		echo "error: new-hire-guide SKILL.md $$lines lines (> 180) — keep orchestrator thin; detail in workflow/" >&2; \
		exit 1; \
	fi; \
	echo "  ok ($$lines lines)"
	@echo "lint-new-hire-guide: disable-model-invocation NOT set (ambiently invocable, unlike the webhook/schedule wrappers)"
	@grep -q '^disable-model-invocation:' new-hire-guide/SKILL.md && \
		{ echo "error: new-hire-guide/SKILL.md must NOT set disable-model-invocation — a human is always present for this flow" >&2; exit 1; } || true
	@echo "  ok"
	@echo "lint-new-hire-guide: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	@fail=0; \
	for f in new-hire-guide/workflow/*.md; do \
		fm=$$(awk '/^---$$/{c++; next} c==1' "$$f"); \
		for key in workflow_version phase produces consumes; do \
			if ! printf '%s\n' "$$fm" | grep -q "^$$key:"; then \
				echo "  missing $$key frontmatter: $$f" >&2; fail=1; \
			fi; \
		done; \
	done; \
	if [ "$$fail" -ne 0 ]; then echo "error: new-hire-guide workflow/*.md must declare workflow_version, phase, produces, consumes" >&2; exit 1; fi; \
	echo "  ok"
	@echo "lint-new-hire-guide: dangling markdown links"
	@bash scripts/lint-dangling-md-links.sh new-hire-guide/*.md new-hire-guide/reference/*.md new-hire-guide/workflow/*.md && echo "  ok" || \
		{ echo "error: dangling reference link(s) found" >&2; exit 1; }
	@echo "lint-new-hire-guide: required reference files"
	@for f in phase-index lazy-load-index tour-format smoke-test pressure-tests; do \
		test -f new-hire-guide/reference/$$f.md || \
			{ echo "error: missing new-hire-guide/reference/$$f.md" >&2; exit 1; }; \
	done
	@grep -q 'pressure-tests' new-hire-guide/reference/smoke-test.md || \
		{ echo "error: smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	@grep -q 'skill-framework' new-hire-guide/SETUP.md || \
		{ echo "error: new-hire-guide/SETUP.md must link to docs/skill-framework" >&2; exit 1; }
	@grep -q 'docs/skill-framework/shared/safe-output.md' new-hire-guide/SKILL.md || \
		{ echo "error: new-hire-guide/SKILL.md must link to shared safe-output" >&2; exit 1; }
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' new-hire-guide/reference/tour-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' new-hire-guide/reference/tour-format.md && \
	 grep -qiE 'escape|fence|backtick' new-hire-guide/reference/tour-format.md && \
	 grep -qi 'redact' new-hire-guide/reference/tour-format.md || \
		{ echo "error: tour-format.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "  ok (framework refs)"

lint-release-readiness-checker:
	@echo "lint-release-readiness-checker: SKILL.md line count (<= 180)"
	@test -f release-readiness-checker/SKILL.md || \
		{ echo "error: missing release-readiness-checker/SKILL.md" >&2; exit 1; }
	@lines=$$(wc -l < release-readiness-checker/SKILL.md | tr -d ' '); \
	if [ -z "$$lines" ] || [ "$$lines" -eq 0 ]; then \
		echo "error: release-readiness-checker/SKILL.md is empty" >&2; exit 1; \
	elif [ "$$lines" -gt 180 ]; then \
		echo "error: release-readiness-checker SKILL.md $$lines lines (> 180) — keep orchestrator thin; detail in workflow/" >&2; \
		exit 1; \
	fi; \
	echo "  ok ($$lines lines)"
	@echo "lint-release-readiness-checker: disable-model-invocation NOT set (ambiently invocable, unlike the webhook/schedule wrappers)"
	@grep -q '^disable-model-invocation:' release-readiness-checker/SKILL.md && \
		{ echo "error: release-readiness-checker/SKILL.md must NOT set disable-model-invocation — a human is always present for this flow" >&2; exit 1; } || true
	@echo "  ok"
	@echo "lint-release-readiness-checker: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	@fail=0; \
	for f in release-readiness-checker/workflow/*.md; do \
		fm=$$(awk '/^---$$/{c++; next} c==1' "$$f"); \
		for key in workflow_version phase produces consumes; do \
			if ! printf '%s\n' "$$fm" | grep -q "^$$key:"; then \
				echo "  missing $$key frontmatter: $$f" >&2; fail=1; \
			fi; \
		done; \
	done; \
	if [ "$$fail" -ne 0 ]; then echo "error: release-readiness-checker workflow/*.md must declare workflow_version, phase, produces, consumes" >&2; exit 1; fi; \
	echo "  ok"
	@echo "lint-release-readiness-checker: dangling markdown links"
	@bash scripts/lint-dangling-md-links.sh release-readiness-checker/*.md release-readiness-checker/reference/*.md release-readiness-checker/workflow/*.md && echo "  ok" || \
		{ echo "error: dangling reference link(s) found" >&2; exit 1; }
	@echo "lint-release-readiness-checker: required reference files"
	@for f in phase-index lazy-load-index gate-policy report-format smoke-test pressure-tests; do \
		test -f release-readiness-checker/reference/$$f.md || \
			{ echo "error: missing release-readiness-checker/reference/$$f.md" >&2; exit 1; }; \
	done
	@grep -q 'pressure-tests' release-readiness-checker/reference/smoke-test.md || \
		{ echo "error: smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	@grep -q 'skill-framework' release-readiness-checker/SETUP.md || \
		{ echo "error: release-readiness-checker/SETUP.md must link to docs/skill-framework" >&2; exit 1; }
	@echo "  ok (framework refs)"

lint-migration-program-manager:
	@echo "lint-migration-program-manager: SKILL.md line count (<= 180)"
	@test -f migration-program-manager/SKILL.md || \
		{ echo "error: missing migration-program-manager/SKILL.md" >&2; exit 1; }
	@lines=$$(wc -l < migration-program-manager/SKILL.md | tr -d ' '); \
	if [ -z "$$lines" ] || [ "$$lines" -eq 0 ]; then \
		echo "error: migration-program-manager/SKILL.md is empty" >&2; exit 1; \
	elif [ "$$lines" -gt 180 ]; then \
		echo "error: migration-program-manager SKILL.md $$lines lines (> 180) — keep orchestrator thin; detail in workflow/" >&2; \
		exit 1; \
	fi; \
	echo "  ok ($$lines lines)"
	@echo "lint-migration-program-manager: disable-model-invocation NOT set (ambiently invocable, no live wrapped-skill invocation to gate)"
	@grep -q '^disable-model-invocation:' migration-program-manager/SKILL.md && \
		{ echo "error: migration-program-manager/SKILL.md must NOT set disable-model-invocation" >&2; exit 1; } || true
	@echo "  ok"
	@echo "lint-migration-program-manager: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	@fail=0; \
	for f in migration-program-manager/workflow/*.md; do \
		fm=$$(awk '/^---$$/{c++; next} c==1' "$$f"); \
		for key in workflow_version phase produces consumes; do \
			if ! printf '%s\n' "$$fm" | grep -q "^$$key:"; then \
				echo "  missing $$key frontmatter: $$f" >&2; fail=1; \
			fi; \
		done; \
	done; \
	if [ "$$fail" -ne 0 ]; then echo "error: migration-program-manager workflow/*.md must declare workflow_version, phase, produces, consumes" >&2; exit 1; fi; \
	echo "  ok"
	@echo "lint-migration-program-manager: dangling markdown links"
	@bash scripts/lint-dangling-md-links.sh migration-program-manager/*.md migration-program-manager/reference/*.md migration-program-manager/workflow/*.md && echo "  ok" || \
		{ echo "error: dangling reference link(s) found" >&2; exit 1; }
	@echo "lint-migration-program-manager: required reference files"
	@for f in phase-index lazy-load-index report-format smoke-test pressure-tests; do \
		test -f migration-program-manager/reference/$$f.md || \
			{ echo "error: missing migration-program-manager/reference/$$f.md" >&2; exit 1; }; \
	done
	@grep -q 'pressure-tests' migration-program-manager/reference/smoke-test.md || \
		{ echo "error: smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	@test -f migration-program-manager/scripts/aggregate_migration_status.py || \
		{ echo "error: missing migration-program-manager/scripts/aggregate_migration_status.py" >&2; exit 1; }
	@grep -q 'skill-framework' migration-program-manager/SETUP.md || \
		{ echo "error: migration-program-manager/SETUP.md must link to docs/skill-framework" >&2; exit 1; }
	@grep -q 'docs/skill-framework/shared/safe-output.md' migration-program-manager/SKILL.md || \
		{ echo "error: migration-program-manager/SKILL.md must link to shared safe-output" >&2; exit 1; }
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' migration-program-manager/reference/report-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' migration-program-manager/reference/report-format.md && \
	 grep -qiE 'escape|fence|backtick' migration-program-manager/reference/report-format.md && \
	 grep -qi 'redact' migration-program-manager/reference/report-format.md || \
		{ echo "error: report-format.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "lint-migration-program-manager: aggregator pytest"
	@if python3 -c "import pytest" >/dev/null 2>&1; then \
		python3 -m pytest -p no:cacheprovider migration-program-manager/tests/ -q || exit 1; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run migration-program-manager tests" >&2; \
	fi
	@echo "  ok (framework refs + aggregator tests)"

lint-cost-optimization-sprint-planner:
	@echo "lint-cost-optimization-sprint-planner: SKILL.md line count (<= 180)"
	@test -f cost-optimization-sprint-planner/SKILL.md || \
		{ echo "error: missing cost-optimization-sprint-planner/SKILL.md" >&2; exit 1; }
	@lines=$$(wc -l < cost-optimization-sprint-planner/SKILL.md | tr -d ' '); \
	if [ -z "$$lines" ] || [ "$$lines" -eq 0 ]; then \
		echo "error: cost-optimization-sprint-planner/SKILL.md is empty" >&2; exit 1; \
	elif [ "$$lines" -gt 180 ]; then \
		echo "error: cost-optimization-sprint-planner SKILL.md $$lines lines (> 180) — keep orchestrator thin; detail in workflow/" >&2; \
		exit 1; \
	fi; \
	echo "  ok ($$lines lines)"
	@echo "lint-cost-optimization-sprint-planner: disable-model-invocation NOT set (ambiently invocable, unlike the webhook/schedule wrappers)"
	@grep -q '^disable-model-invocation:' cost-optimization-sprint-planner/SKILL.md && \
		{ echo "error: cost-optimization-sprint-planner/SKILL.md must NOT set disable-model-invocation — a human is always present for this flow" >&2; exit 1; } || true
	@echo "  ok"
	@echo "lint-cost-optimization-sprint-planner: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	@fail=0; \
	for f in cost-optimization-sprint-planner/workflow/*.md; do \
		fm=$$(awk '/^---$$/{c++; next} c==1' "$$f"); \
		for key in workflow_version phase produces consumes; do \
			if ! printf '%s\n' "$$fm" | grep -q "^$$key:"; then \
				echo "  missing $$key frontmatter: $$f" >&2; fail=1; \
			fi; \
		done; \
	done; \
	if [ "$$fail" -ne 0 ]; then echo "error: cost-optimization-sprint-planner workflow/*.md must declare workflow_version, phase, produces, consumes" >&2; exit 1; fi; \
	echo "  ok"
	@echo "lint-cost-optimization-sprint-planner: dangling markdown links"
	@bash scripts/lint-dangling-md-links.sh cost-optimization-sprint-planner/*.md cost-optimization-sprint-planner/reference/*.md cost-optimization-sprint-planner/workflow/*.md && echo "  ok" || \
		{ echo "error: dangling reference link(s) found" >&2; exit 1; }
	@echo "lint-cost-optimization-sprint-planner: required reference files"
	@for f in phase-index lazy-load-index gate-policy sweep-policy report-format smoke-test pressure-tests; do \
		test -f cost-optimization-sprint-planner/reference/$$f.md || \
			{ echo "error: missing cost-optimization-sprint-planner/reference/$$f.md" >&2; exit 1; }; \
	done
	@grep -q 'pressure-tests' cost-optimization-sprint-planner/reference/smoke-test.md || \
		{ echo "error: smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	@grep -q 'skill-framework' cost-optimization-sprint-planner/SETUP.md || \
		{ echo "error: cost-optimization-sprint-planner/SETUP.md must link to docs/skill-framework" >&2; exit 1; }
	@grep -q 'docs/skill-framework/shared/safe-output.md' cost-optimization-sprint-planner/SKILL.md || \
		{ echo "error: cost-optimization-sprint-planner/SKILL.md must link to shared safe-output" >&2; exit 1; }
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' cost-optimization-sprint-planner/reference/report-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' cost-optimization-sprint-planner/reference/report-format.md && \
	 grep -qiE 'escape|fence|backtick' cost-optimization-sprint-planner/reference/report-format.md || \
		{ echo "error: report-format.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "  ok (framework refs)"

lint-mysql-to-postgres-sql:
	@echo "lint-mysql-to-postgres-sql: SKILL.md line count (<= 180)"
	@test -f mysql-to-postgres-sql/SKILL.md || \
		{ echo "error: missing mysql-to-postgres-sql/SKILL.md" >&2; exit 1; }
	@lines=$$(wc -l < mysql-to-postgres-sql/SKILL.md | tr -d ' '); \
	if [ -z "$$lines" ] || [ "$$lines" -eq 0 ]; then \
		echo "error: mysql-to-postgres-sql/SKILL.md is empty" >&2; exit 1; \
	elif [ "$$lines" -gt 180 ]; then \
		echo "error: mysql-to-postgres-sql SKILL.md $$lines lines (> 180)" >&2; \
		exit 1; \
	fi; \
	echo "  ok ($$lines lines)"
	@echo "lint-mysql-to-postgres-sql: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	@fail=0; \
	for f in mysql-to-postgres-sql/workflow/*.md; do \
		fm=$$(awk '/^---$$/{c++; next} c==1' "$$f"); \
		for key in workflow_version phase produces consumes; do \
			if ! printf '%s\n' "$$fm" | grep -q "^$$key:"; then \
				echo "  missing $$key frontmatter: $$f" >&2; fail=1; \
			fi; \
		done; \
	done; \
	if [ "$$fail" -ne 0 ]; then echo "error: mysql-to-postgres-sql workflow/*.md must declare workflow_version, phase, produces, consumes" >&2; exit 1; fi; \
	echo "  ok"
	@echo "lint-mysql-to-postgres-sql: required reference files"
	@for f in function-translations collection-domain-files smoke-test org-migration-gaps timestamp-handling data-type-mapping case-sensitivity nodejs-migration python-migration migration-prompts shadow-migration lazy-load-index collection-checklist-refresh migration-edge-cases calibration-snippets; do \
		test -f mysql-to-postgres-sql/reference/$$f.md || \
			{ echo "error: missing mysql-to-postgres-sql/reference/$$f.md" >&2; exit 1; }; \
	done
	@test -f mysql-to-postgres-sql/scripts/scan-mysql-dialect.sh || \
		{ echo "error: missing mysql-to-postgres-sql/scripts/scan-mysql-dialect.sh" >&2; exit 1; }
	@test -f mysql-to-postgres-sql/scripts/scan-report.sh || \
		{ echo "error: missing mysql-to-postgres-sql/scripts/scan-report.sh" >&2; exit 1; }
	@test -f mysql-to-postgres-sql/scripts/mysql-dialect-patterns.sh || \
		{ echo "error: missing mysql-to-postgres-sql/scripts/mysql-dialect-patterns.sh" >&2; exit 1; }
	@test -f mysql-to-postgres-sql/reference/spring-datasource-example.yaml || \
		{ echo "error: missing mysql-to-postgres-sql/reference/spring-datasource-example.yaml" >&2; exit 1; }
	@grep -q 'skill-framework' mysql-to-postgres-sql/SETUP.md || \
		{ echo "error: mysql-to-postgres-sql/SETUP.md must link to docs/skill-framework" >&2; exit 1; }
	@grep -q 'cross-skill-escalation' mysql-to-postgres-sql/SKILL.md || \
		{ echo "error: mysql-to-postgres-sql SKILL.md must link to shared cross-skill-escalation" >&2; exit 1; }
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
	@bash scripts/lint-dangling-md-links.sh mysql-to-postgres-sql/*.md mysql-to-postgres-sql/reference/*.md mysql-to-postgres-sql/reference/domain-packs/*.md mysql-to-postgres-sql/workflow/*.md && echo "  ok" || \
		{ echo "error: dangling reference link(s) found" >&2; exit 1; }
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
	@test -f loop-task-implementer/SKILL.md || \
		{ echo "error: missing loop-task-implementer/SKILL.md" >&2; exit 1; }
	@lines=$$(wc -l < loop-task-implementer/SKILL.md | tr -d ' '); \
	if [ -z "$$lines" ] || [ "$$lines" -eq 0 ]; then \
		echo "error: loop-task-implementer/SKILL.md is empty" >&2; exit 1; \
	elif [ "$$lines" -gt 180 ]; then \
		echo "error: loop-task-implementer SKILL.md $$lines lines (> 180)" >&2; \
		exit 1; \
	fi; \
	echo "  ok ($$lines lines)"
	@echo "lint-loop-task-implementer: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	@fail=0; \
	for f in loop-task-implementer/workflow/*.md; do \
		fm=$$(awk '/^---$$/{c++; next} c==1' "$$f"); \
		for key in workflow_version phase produces consumes; do \
			if ! printf '%s\n' "$$fm" | grep -q "^$$key:"; then \
				echo "  missing $$key frontmatter: $$f" >&2; fail=1; \
			fi; \
		done; \
	done; \
	if [ "$$fail" -ne 0 ]; then echo "error: loop-task-implementer workflow/*.md must declare workflow_version, phase, produces, consumes" >&2; exit 1; fi; \
	echo "  ok"
	@echo "lint-loop-task-implementer: dangling markdown links"
	@bash scripts/lint-dangling-md-links.sh loop-task-implementer/*.md loop-task-implementer/reference/*.md loop-task-implementer/workflow/*.md && echo "  ok" || \
		{ echo "error: dangling reference link(s) found" >&2; exit 1; }
	@echo "lint-loop-task-implementer: required files"
	@for f in SETUP.md README.md examples.md report-template.md; do \
		test -f loop-task-implementer/$$f || \
			{ echo "error: missing loop-task-implementer/$$f" >&2; exit 1; }; \
	done
	@for f in phase-index lazy-load-index mcp-capabilities smoke-test pressure-tests platform-adapters; do \
		test -f loop-task-implementer/reference/$$f.md || \
			{ echo "error: missing loop-task-implementer/reference/$$f.md" >&2; exit 1; }; \
	done
	@test -f loop-task-implementer/reference/state-schema.yaml || \
		{ echo "error: missing loop-task-implementer/reference/state-schema.yaml" >&2; exit 1; }
	@grep -q 'skill-framework' loop-task-implementer/SETUP.md || \
		{ echo "error: loop-task-implementer/SETUP.md must link to docs/skill-framework" >&2; exit 1; }
	@grep -q 'cross-skill-escalation' loop-task-implementer/SKILL.md || \
		{ echo "error: loop-task-implementer SKILL.md must link to shared cross-skill-escalation" >&2; exit 1; }
	@echo "  ok"

lint-backlog-runner:
	@echo "lint-backlog-runner: SKILL.md line count (<= 180)"
	@test -f backlog-runner/SKILL.md || \
		{ echo "error: missing backlog-runner/SKILL.md" >&2; exit 1; }
	@lines=$$(wc -l < backlog-runner/SKILL.md | tr -d ' '); \
	if [ -z "$$lines" ] || [ "$$lines" -eq 0 ]; then \
		echo "error: backlog-runner/SKILL.md is empty" >&2; exit 1; \
	elif [ "$$lines" -gt 180 ]; then \
		echo "error: backlog-runner SKILL.md $$lines lines (> 180) — keep orchestrator thin; detail in workflow/" >&2; \
		exit 1; \
	fi; \
	echo "  ok ($$lines lines)"
	@echo "lint-backlog-runner: disable-model-invocation set (automation entry point, must not compete with loop-task-implementer's ambient invocation)"
	@grep -q '^disable-model-invocation: true' backlog-runner/SKILL.md || \
		{ echo "error: backlog-runner/SKILL.md must set disable-model-invocation: true" >&2; exit 1; }
	@echo "  ok"
	@echo "lint-backlog-runner: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	@fail=0; \
	for f in backlog-runner/workflow/*.md; do \
		fm=$$(awk '/^---$$/{c++; next} c==1' "$$f"); \
		for key in workflow_version phase produces consumes; do \
			if ! printf '%s\n' "$$fm" | grep -q "^$$key:"; then \
				echo "  missing $$key frontmatter: $$f" >&2; fail=1; \
			fi; \
		done; \
	done; \
	if [ "$$fail" -ne 0 ]; then echo "error: backlog-runner workflow/*.md must declare workflow_version, phase, produces, consumes" >&2; exit 1; fi; \
	echo "  ok"
	@echo "lint-backlog-runner: dangling markdown links"
	@bash scripts/lint-dangling-md-links.sh backlog-runner/*.md backlog-runner/reference/*.md backlog-runner/workflow/*.md && echo "  ok" || \
		{ echo "error: dangling reference link(s) found" >&2; exit 1; }
	@echo "lint-backlog-runner: required reference files"
	@for f in phase-index lazy-load-index queue-policy morning-summary-format smoke-test pressure-tests; do \
		test -f backlog-runner/reference/$$f.md || \
			{ echo "error: missing backlog-runner/reference/$$f.md" >&2; exit 1; }; \
	done
	@grep -q 'pressure-tests' backlog-runner/reference/smoke-test.md || \
		{ echo "error: smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	@grep -q 'docs/skill-framework/shared/safe-output.md' backlog-runner/SKILL.md || \
		{ echo "error: backlog-runner/SKILL.md must link to shared safe-output" >&2; exit 1; }
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' backlog-runner/reference/morning-summary-format.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' backlog-runner/reference/morning-summary-format.md && \
	 grep -qiE 'escape|fence' backlog-runner/reference/morning-summary-format.md && \
	 grep -qi 'redact' backlog-runner/reference/morning-summary-format.md || \
		{ echo "error: morning-summary-format.md must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@grep -q 'skill-framework' backlog-runner/SETUP.md || \
		{ echo "error: backlog-runner/SETUP.md must link to docs/skill-framework" >&2; exit 1; }
	@echo "  ok (framework refs)"

lint-weekly-squad-digest:
	@echo "lint-weekly-squad-digest: SKILL.md line count (<= 180)"
	@test -f weekly-squad-digest/SKILL.md || \
		{ echo "error: missing weekly-squad-digest/SKILL.md" >&2; exit 1; }
	@lines=$$(wc -l < weekly-squad-digest/SKILL.md | tr -d ' '); \
	if [ -z "$$lines" ] || [ "$$lines" -eq 0 ]; then \
		echo "error: weekly-squad-digest/SKILL.md is empty" >&2; exit 1; \
	elif [ "$$lines" -gt 180 ]; then \
		echo "error: weekly-squad-digest SKILL.md $$lines lines (> 180) — keep orchestrator thin; detail in workflow/" >&2; \
		exit 1; \
	fi; \
	echo "  ok ($$lines lines)"
	@echo "lint-weekly-squad-digest: disable-model-invocation set (automation entry point, must not compete with migration-program-manager's/cost-optimization-sprint-planner's ambient invocation)"
	@grep -q '^disable-model-invocation: true' weekly-squad-digest/SKILL.md || \
		{ echo "error: weekly-squad-digest/SKILL.md must set disable-model-invocation: true" >&2; exit 1; }
	@echo "  ok"
	@echo "lint-weekly-squad-digest: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	@fail=0; \
	for f in weekly-squad-digest/workflow/*.md; do \
		fm=$$(awk '/^---$$/{c++; next} c==1' "$$f"); \
		for key in workflow_version phase produces consumes; do \
			if ! printf '%s\n' "$$fm" | grep -q "^$$key:"; then \
				echo "  missing $$key frontmatter: $$f" >&2; fail=1; \
			fi; \
		done; \
	done; \
	if [ "$$fail" -ne 0 ]; then echo "error: weekly-squad-digest workflow/*.md must declare workflow_version, phase, produces, consumes" >&2; exit 1; fi; \
	echo "  ok"
	@echo "lint-weekly-squad-digest: dangling markdown links"
	@bash scripts/lint-dangling-md-links.sh weekly-squad-digest/*.md weekly-squad-digest/reference/*.md weekly-squad-digest/workflow/*.md && echo "  ok" || \
		{ echo "error: dangling reference link(s) found" >&2; exit 1; }
	@echo "lint-weekly-squad-digest: required reference files"
	@for f in phase-index lazy-load-index report-format smoke-test pressure-tests; do \
		test -f weekly-squad-digest/reference/$$f.md || \
			{ echo "error: missing weekly-squad-digest/reference/$$f.md" >&2; exit 1; }; \
	done
	@grep -q 'pressure-tests' weekly-squad-digest/reference/smoke-test.md || \
		{ echo "error: smoke-test.md must link to pressure-tests.md" >&2; exit 1; }
	@grep -q 'skill-framework' weekly-squad-digest/SETUP.md || \
		{ echo "error: weekly-squad-digest/SETUP.md must link to docs/skill-framework" >&2; exit 1; }
	@grep -q 'docs/skill-framework/shared/safe-output.md' weekly-squad-digest/SKILL.md || \
		{ echo "error: weekly-squad-digest/SKILL.md must link to shared safe-output" >&2; exit 1; }
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

lint-test-writer:
	@echo "lint-test-writer: SKILL.md line count (<= 180)"
	@test -f test-writer/SKILL.md || \
		{ echo "error: missing test-writer/SKILL.md" >&2; exit 1; }
	@lines=$$(wc -l < test-writer/SKILL.md | tr -d ' '); \
	if [ -z "$$lines" ] || [ "$$lines" -eq 0 ]; then \
		echo "error: test-writer/SKILL.md is empty" >&2; exit 1; \
	elif [ "$$lines" -gt 180 ]; then \
		echo "error: test-writer SKILL.md $$lines lines (> 180)" >&2; \
		exit 1; \
	fi; \
	echo "  ok ($$lines lines)"
	@echo "lint-test-writer: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	@fail=0; \
	for f in test-writer/workflow/*.md; do \
		fm=$$(awk '/^---$$/{c++; next} c==1' "$$f"); \
		for key in workflow_version phase produces consumes; do \
			if ! printf '%s\n' "$$fm" | grep -q "^$$key:"; then \
				echo "  missing $$key frontmatter: $$f" >&2; fail=1; \
			fi; \
		done; \
	done; \
	if [ "$$fail" -ne 0 ]; then echo "error: test-writer workflow/*.md must declare workflow_version, phase, produces, consumes" >&2; exit 1; fi; \
	echo "  ok"
	@echo "lint-test-writer: no detection/generation scripts (router only)"
	@if [ -d test-writer/scripts ] || [ -d test-writer/tests ]; then \
		echo "error: test-writer must not have scripts/ or tests/ — it is a router with no detection/generation logic of its own" >&2; exit 1; \
	fi
	@echo "  ok"
	@echo "lint-test-writer: required reference files"
	@for f in skill-contract phase-index lazy-load-index level-classification smoke-test pressure-tests; do \
		test -f test-writer/reference/$$f.md || \
			{ echo "error: missing test-writer/reference/$$f.md" >&2; exit 1; }; \
	done
	@test -f test-writer/examples.md || \
		{ echo "error: missing test-writer/examples.md" >&2; exit 1; }
	@grep -q '## Invocation' test-writer/examples.md || \
		{ echo "error: test-writer/examples.md must have Invocation section" >&2; exit 1; }
	@grep -q 'skill-framework' test-writer/SETUP.md || \
		{ echo "error: test-writer/SETUP.md must link to docs/skill-framework" >&2; exit 1; }
	@grep -q 'docs/skill-framework/shared/skill-routing.md' test-writer/SKILL.md || \
		{ echo "error: test-writer/SKILL.md must link to shared skill-routing" >&2; exit 1; }
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' test-writer/SKILL.md || \
		{ echo "error: test-writer/SKILL.md must link to shared prompt-injection" >&2; exit 1; }
	@echo "  ok (framework refs)"
	@echo "lint-test-writer: dangling markdown links"
	@bash scripts/lint-dangling-md-links.sh test-writer/*.md test-writer/reference/*.md test-writer/workflow/*.md \
		unit-test-creator/SKILL.md integration-test-creator/SKILL.md contract-test-creator/SKILL.md e2e-test-creator/SKILL.md api-test-creator/SKILL.md \
		unit-test-creator/workflow/*.md integration-test-creator/workflow/*.md contract-test-creator/workflow/*.md e2e-test-creator/workflow/*.md api-test-creator/workflow/*.md \
		&& echo "  ok" || \
		{ echo "error: dangling reference link(s) found" >&2; exit 1; }

lint-prd-architect:
	@echo "lint-prd-architect: SKILL.md line count (<= 180)"
	@test -f prd-architect/SKILL.md || \
		{ echo "error: missing prd-architect/SKILL.md" >&2; exit 1; }
	@lines=$$(wc -l < prd-architect/SKILL.md | tr -d ' '); \
	if [ -z "$$lines" ] || [ "$$lines" -eq 0 ]; then \
		echo "error: prd-architect/SKILL.md is empty" >&2; exit 1; \
	elif [ "$$lines" -gt 180 ]; then \
		echo "error: prd-architect SKILL.md $$lines lines (> 180)" >&2; \
		exit 1; \
	fi; \
	echo "  ok ($$lines lines)"
	@echo "lint-prd-architect: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)"
	@fail=0; \
	for f in prd-architect/workflow/*.md; do \
		fm=$$(awk '/^---$$/{c++; next} c==1' "$$f"); \
		for key in workflow_version phase produces consumes; do \
			if ! printf '%s\n' "$$fm" | grep -q "^$$key:"; then \
				echo "  missing $$key frontmatter: $$f" >&2; fail=1; \
			fi; \
		done; \
	done; \
	if [ "$$fail" -ne 0 ]; then echo "error: prd-architect workflow/*.md must declare workflow_version, phase, produces, consumes" >&2; exit 1; fi; \
	echo "  ok"
	@echo "lint-prd-architect: route-aware workflow contract"
	@python3 -m scripts.validate_workflow_contracts prd-architect
	@echo "lint-prd-architect: required reference files"
	@for f in skill-contract rationalization-guards phase-index lazy-load-index global-rules depth response-modes section-triggers requirements-format correctness-rules adversarial-review output-contract smoke-test pressure-tests; do \
		test -f prd-architect/reference/$$f.md || \
			{ echo "error: missing prd-architect/reference/$$f.md" >&2; exit 1; }; \
	done
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
	@grep -q 'cross-skill-escalation' prd-architect/SKILL.md || \
		{ echo "error: prd-architect/SKILL.md must link to shared cross-skill-escalation" >&2; exit 1; }
	@grep -q 'smoke-test' prd-architect/SKILL.md || \
		{ echo "error: prd-architect/SKILL.md must link to reference/smoke-test.md" >&2; exit 1; }
	@grep -q 'skill-framework' prd-architect/SETUP.md || \
		{ echo "error: prd-architect/SETUP.md must link to docs/skill-framework" >&2; exit 1; }
	@grep -q 'docs/skill-framework/shared/skill-routing.md' prd-architect/SKILL.md || \
		{ echo "error: prd-architect/SKILL.md must link to shared skill-routing" >&2; exit 1; }
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' prd-architect/SKILL.md || \
		{ echo "error: prd-architect/SKILL.md must link to shared prompt-injection" >&2; exit 1; }
	@grep -q 'docs/skill-framework/shared/safe-output.md' prd-architect/SKILL.md || \
		{ echo "error: prd-architect/SKILL.md must link to shared safe-output" >&2; exit 1; }
	@grep -q 'docs/skill-framework/shared/prompt-injection.md' prd-architect/workflow/gate.md && \
	 grep -q 'docs/skill-framework/shared/safe-output.md' prd-architect/workflow/gate.md && \
	 grep -qi 'source_material' prd-architect/workflow/gate.md && \
	 grep -qiE 'escape|fence' prd-architect/workflow/gate.md && \
	 grep -qi 'redact' prd-architect/workflow/gate.md || \
		{ echo "error: prd-architect Gate must sanitize untrusted rendered fields per prompt-injection and safe-output" >&2; exit 1; }
	@echo "  ok (framework refs)"
	@echo "lint-prd-architect: dangling markdown links"
	@bash scripts/lint-dangling-md-links.sh prd-architect/*.md prd-architect/reference/*.md prd-architect/workflow/*.md \
		&& echo "  ok" || \
		{ echo "error: dangling reference link(s) found" >&2; exit 1; }

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
	@for skill in pr-review pr-gatekeeper incident-rca incident-triage-agent k8s-overprovisioning-datadog domain-comprehension squad-map who-owns-x-bot new-hire-guide release-readiness-checker migration-program-manager mysql-to-postgres-sql loop-task-implementer backlog-runner cost-optimization-sprint-planner weekly-squad-digest prd-architect test-writer unit-test-creator integration-test-creator contract-test-creator e2e-test-creator api-test-creator; do \
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
	@for skill in pr-review pr-gatekeeper incident-rca incident-triage-agent k8s-overprovisioning-datadog domain-comprehension squad-map who-owns-x-bot new-hire-guide release-readiness-checker migration-program-manager mysql-to-postgres-sql loop-task-implementer backlog-runner cost-optimization-sprint-planner weekly-squad-digest prd-architect test-writer unit-test-creator integration-test-creator contract-test-creator e2e-test-creator api-test-creator; do \
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
		"api-test-creator:workflow/inputs.md"; do \
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
	for skill in pr-review pr-gatekeeper incident-rca incident-triage-agent k8s-overprovisioning-datadog domain-comprehension squad-map who-owns-x-bot new-hire-guide release-readiness-checker migration-program-manager mysql-to-postgres-sql loop-task-implementer backlog-runner cost-optimization-sprint-planner weekly-squad-digest prd-architect test-writer unit-test-creator integration-test-creator contract-test-creator e2e-test-creator api-test-creator; do \
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
		pr-review/tests/fixtures/phase5-review-metadata.yaml || exit 1; \
	if python3 -c "import pytest" >/dev/null 2>&1; then \
		python3 -m pytest -p no:cacheprovider scripts/tests/ -q || exit 1; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run metadata footer tests" >&2; \
	fi
	@echo "lint-framework: ok"

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
