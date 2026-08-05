.PHONY: install install-pr-review install-k8s-overprovisioning install-incident-rca install-incident-rca-deps install-domain-comprehension install-squad-map install-mysql-to-postgres-sql install-claude install-claude-pr-review install-claude-k8s-overprovisioning install-claude-incident-rca install-claude-domain-comprehension install-claude-squad-map install-claude-mysql-to-postgres-sql lint lint-framework lint-pr-review lint-k8s-skill lint-k8s lint-incident-rca lint-domain-comprehension lint-squad-map lint-mysql-to-postgres-sql setup-hooks setup kubesense-errors

install:
	bash scripts/install.sh

install-pr-review:
	bash scripts/install.sh pr-review

install-k8s-overprovisioning:
	bash scripts/install.sh k8s-overprovisioning-datadog

install-incident-rca-deps:
	bash scripts/install-incident-rca-deps.sh

install-incident-rca: install-incident-rca-deps
	bash scripts/install.sh incident-rca

install-domain-comprehension: install-squad-map
	bash scripts/install.sh domain-comprehension

install-squad-map:
	bash scripts/install.sh squad-map

install-mysql-to-postgres-sql:
	bash scripts/install.sh mysql-to-postgres-sql

install-claude:
	bash scripts/install.sh --agent claude-user

install-claude-pr-review:
	bash scripts/install.sh --agent claude-user pr-review

install-claude-k8s-overprovisioning:
	bash scripts/install.sh --agent claude-user k8s-overprovisioning-datadog

install-claude-incident-rca: install-incident-rca-deps
	bash scripts/install.sh --agent claude-user incident-rca

install-claude-domain-comprehension: install-claude-squad-map
	bash scripts/install.sh --agent claude-user domain-comprehension

install-claude-squad-map:
	bash scripts/install.sh --agent claude-user squad-map

install-claude-mysql-to-postgres-sql:
	bash scripts/install.sh --agent claude-user mysql-to-postgres-sql

setup:
	@echo "setup: installing Python dev dependencies (requirements.txt)"
	@python3 -m pip install -r requirements.txt 2>/dev/null || \
		python3 -m pip install --user --break-system-packages -r requirements.txt
	@$(MAKE) setup-hooks

lint: lint-framework lint-pr-review lint-k8s-skill lint-incident-rca lint-domain-comprehension lint-squad-map lint-mysql-to-postgres-sql
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
	@echo "lint-pr-review-skill: workflow frontmatter (workflow_version in each workflow/*.md)"
	@fail=0; \
	for f in pr-review/workflow/*.md; do \
		if ! head -n 8 "$$f" | grep -q '^workflow_version:'; then \
			echo "  missing workflow_version frontmatter: $$f" >&2; fail=1; \
		fi; \
	done; \
	if [ "$$fail" -ne 0 ]; then echo "error: pr-review workflow/*.md must declare workflow_version, produces, consumes" >&2; exit 1; fi; \
	echo "  ok"
	@echo "lint-pr-review-skill: dangling markdown links"
	@bash scripts/lint-dangling-md-links.sh pr-review/*.md pr-review/reference/*.md pr-review/workflow/*.md && echo "  ok" || \
		{ echo "error: dangling reference link(s) found" >&2; exit 1; }
	@grep -q 'cross-skill-escalation' pr-review/SKILL.md || \
		{ echo "error: pr-review SKILL.md must link to shared cross-skill-escalation" >&2; exit 1; }
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

lint-k8s-skill:
	@echo "lint-k8s-skill: SKILL.md line count (<= 150)"
	@lines=$$(wc -l < k8s-overprovisioning-datadog/SKILL.md | tr -d ' '); \
	if [ "$$lines" -gt 150 ]; then \
		echo "error: k8s SKILL.md $$lines lines (> 150) — keep orchestrator thin; detail in workflow/" >&2; \
		exit 1; \
	fi; \
	echo "  ok ($$lines lines)"
	@echo "lint-k8s-skill: workflow frontmatter (workflow_version in each workflow/*.md)"
	@fail=0; \
	for f in k8s-overprovisioning-datadog/workflow/*.md; do \
		if ! head -n 8 "$$f" | grep -q '^workflow_version:'; then \
			echo "  missing workflow_version frontmatter: $$f" >&2; fail=1; \
		fi; \
	done; \
	if [ "$$fail" -ne 0 ]; then echo "error: k8s workflow/*.md must declare workflow_version, produces, consumes" >&2; exit 1; fi; \
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
		k8s-overprovisioning-datadog/reference/decision-graph.scale-up.example.yaml; do \
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
	@echo "lint-incident-rca: workflow frontmatter (workflow_version in each workflow/*.md)"
	@fail=0; \
	for f in incident-rca/workflow/*.md; do \
		if ! head -n 8 "$$f" | grep -q '^workflow_version:'; then \
			echo "  missing workflow_version frontmatter: $$f" >&2; fail=1; \
		fi; \
	done; \
	if [ "$$fail" -ne 0 ]; then echo "error: incident-rca workflow/*.md must declare workflow_version, produces, consumes" >&2; exit 1; fi; \
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
	if python3 -c "import pytest" >/dev/null 2>&1; then \
		python3 -m pytest -p no:cacheprovider incident-rca/tests/ -q || exit 1; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run schema tests" >&2; \
		exit 1; \
	fi; \
	echo "  ok"

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
	@echo "lint-domain-comprehension: workflow frontmatter (workflow_version in each workflow/*.md)"
	@fail=0; \
	for f in domain-comprehension/workflow/*.md; do \
		if ! head -n 8 "$$f" | grep -q '^workflow_version:'; then \
			echo "  missing workflow_version frontmatter: $$f" >&2; fail=1; \
		fi; \
	done; \
	if [ "$$fail" -ne 0 ]; then echo "error: domain-comprehension workflow/*.md must declare workflow_version, produces, consumes" >&2; exit 1; fi; \
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
	@echo "lint-squad-map: workflow frontmatter (workflow_version in each workflow/*.md)"
	@fail=0; \
	for f in squad-map/workflow/*.md; do \
		if ! head -n 8 "$$f" | grep -q '^workflow_version:'; then \
			echo "  missing workflow_version frontmatter: $$f" >&2; fail=1; \
		fi; \
	done; \
	if [ "$$fail" -ne 0 ]; then echo "error: squad-map workflow/*.md must declare workflow_version" >&2; exit 1; fi; \
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
	@echo "lint-mysql-to-postgres-sql: workflow frontmatter (workflow_version in each workflow/*.md)"
	@fail=0; \
	for f in mysql-to-postgres-sql/workflow/*.md; do \
		if ! head -n 8 "$$f" | grep -q '^workflow_version:'; then \
			echo "  missing workflow_version frontmatter: $$f" >&2; fail=1; \
		fi; \
	done; \
	if [ "$$fail" -ne 0 ]; then echo "error: mysql-to-postgres-sql workflow/*.md must declare workflow_version" >&2; exit 1; fi; \
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
	@test -f mysql-to-postgres-sql/reference/domain-packs/collection-mpokket.md || \
		{ echo "error: missing mysql-to-postgres-sql/reference/domain-packs/collection-mpokket.md" >&2; exit 1; }
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
	if python3 -c "import pytest" >/dev/null 2>&1; then \
		python3 -m pytest -p no:cacheprovider mysql-to-postgres-sql/tests/test_pressure_policy.py -q || exit 1; \
	else \
		echo "pytest not installed — install with 'python3 -m pip install pytest' to run mysql policy tests" >&2; \
		exit 1; \
	fi; \
	echo "  ok (pressure + pytest)"
	@echo "lint-mysql-to-postgres-sql: dangling markdown links"
	@bash scripts/lint-dangling-md-links.sh mysql-to-postgres-sql/*.md mysql-to-postgres-sql/reference/*.md mysql-to-postgres-sql/reference/domain-packs/*.md mysql-to-postgres-sql/workflow/*.md && echo "  ok" || \
		{ echo "error: dangling reference link(s) found" >&2; exit 1; }
	@echo "lint-mysql-to-postgres-sql: shellcheck scan + test scripts"
	@if command -v shellcheck >/dev/null 2>&1; then \
		shellcheck mysql-to-postgres-sql/scripts/scan-mysql-dialect.sh mysql-to-postgres-sql/scripts/scan-report.sh mysql-to-postgres-sql/tests/run_pressure_tests.sh; \
	elif command -v docker >/dev/null 2>&1; then \
		docker run --rm -v "$(CURDIR):/mnt" -w /mnt koalaman/shellcheck-alpine:stable \
			shellcheck mysql-to-postgres-sql/scripts/scan-mysql-dialect.sh mysql-to-postgres-sql/scripts/scan-report.sh mysql-to-postgres-sql/tests/run_pressure_tests.sh; \
	else \
		echo "error: install shellcheck or docker" >&2; exit 1; \
	fi
	@echo "  ok (framework refs + shellcheck)"

lint-framework:
	@echo "lint-framework: shared docs present"
	@test -f docs/skill-framework/README.md
	@for f in confidence-bands cross-skill-escalation post-action-templates \
		smoke-test-conventions examples-conventions phase-glossary review-metadata-schema \
		skill-routing prompt-injection claude-code-setup; do \
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
	@for skill in pr-review incident-rca k8s-overprovisioning-datadog domain-comprehension squad-map mysql-to-postgres-sql; do \
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
	@for skill in pr-review incident-rca k8s-overprovisioning-datadog domain-comprehension squad-map mysql-to-postgres-sql; do \
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
		"incident-rca:workflow/inputs.md" \
		"k8s-overprovisioning-datadog:workflow/collect-metrics.md" \
		"domain-comprehension:workflow/session-0.md" \
		"squad-map:workflow/inputs.md" \
		"mysql-to-postgres-sql:workflow/migrate-service.md"; do \
		skill=$${pair%%:*}; file=$${pair#*:}; \
		if ! grep -qiE 'untrusted|prompt-injection' $$skill/$$file; then \
			echo "error: $$skill/$$file must declare untrusted-content guard" >&2; fail=1; \
		fi; \
	done; \
	if [ "$$fail" -ne 0 ]; then exit 1; fi
	@echo "lint-framework: all SETUP.md links ok"
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
# Example: make kubesense-errors WORKLOAD=autodebit-service CLUSTER=mpokket-neo-prod-eks-cluster
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
