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
#
# The install-<skill> / install-claude-<skill> rules below carry the same
# guarantee: their prerequisite edges ARE each skill's `install.requires`,
# read from the registry, so the Make graph cannot disagree with skills.yaml
# about what a skill depends on. Adding a skill needs no make/core.mk edit.

ALL_SKILLS := pr-review pr-gatekeeper incident-rca incident-triage-agent k8s-overprovisioning-datadog domain-comprehension squad-map who-owns-x-bot new-hire-guide release-readiness-checker migration-program-manager mysql-to-postgres-sql loop-task-implementer backlog-runner cost-optimization-sprint-planner weekly-squad-digest prd-architect test-writer unit-test-creator integration-test-creator contract-test-creator e2e-test-creator api-test-creator architecture-review system-design api-design-review database-review security-review performance-review capacity-planner observability-review deployment-risk-review dependency-upgrade-review tech-debt-assessor change-impact-analyzer resilience-review implementation-planner production-readiness-review

.PHONY: install-pr-review install-claude-pr-review install-pr-gatekeeper install-claude-pr-gatekeeper install-incident-rca install-claude-incident-rca install-incident-triage-agent install-claude-incident-triage-agent install-k8s-overprovisioning install-claude-k8s-overprovisioning install-domain-comprehension install-claude-domain-comprehension install-squad-map install-claude-squad-map install-who-owns-x-bot install-claude-who-owns-x-bot install-new-hire-guide install-claude-new-hire-guide install-release-readiness-checker install-claude-release-readiness-checker install-migration-program-manager install-claude-migration-program-manager install-mysql-to-postgres-sql install-claude-mysql-to-postgres-sql install-loop-task-implementer install-claude-loop-task-implementer install-backlog-runner install-claude-backlog-runner install-cost-optimization-sprint-planner install-claude-cost-optimization-sprint-planner install-weekly-squad-digest install-claude-weekly-squad-digest install-prd-architect install-claude-prd-architect install-test-writer install-claude-test-writer install-unit-test-creator install-claude-unit-test-creator install-integration-test-creator install-claude-integration-test-creator install-contract-test-creator install-claude-contract-test-creator install-e2e-test-creator install-claude-e2e-test-creator install-api-test-creator install-claude-api-test-creator install-architecture-review install-claude-architecture-review install-system-design install-claude-system-design install-api-design-review install-claude-api-design-review install-database-review install-claude-database-review install-security-review install-claude-security-review install-performance-review install-claude-performance-review install-capacity-planner install-claude-capacity-planner install-observability-review install-claude-observability-review install-deployment-risk-review install-claude-deployment-risk-review install-dependency-upgrade-review install-claude-dependency-upgrade-review install-tech-debt-assessor install-claude-tech-debt-assessor install-change-impact-analyzer install-claude-change-impact-analyzer install-resilience-review install-claude-resilience-review install-implementation-planner install-claude-implementation-planner install-production-readiness-review install-claude-production-readiness-review

install-pr-review:
	bash scripts/install.sh pr-review

install-claude-pr-review:
	bash scripts/install.sh --agent claude-user pr-review

install-pr-gatekeeper: install-pr-review
	bash scripts/install.sh pr-gatekeeper

install-claude-pr-gatekeeper: install-claude-pr-review
	bash scripts/install.sh --agent claude-user pr-gatekeeper

install-incident-rca: install-incident-rca-deps
	bash scripts/install.sh incident-rca

install-claude-incident-rca: install-incident-rca-deps
	bash scripts/install.sh --agent claude-user incident-rca

install-incident-triage-agent: install-incident-rca install-squad-map
	bash scripts/install.sh incident-triage-agent

install-claude-incident-triage-agent: install-claude-incident-rca install-claude-squad-map
	bash scripts/install.sh --agent claude-user incident-triage-agent

install-k8s-overprovisioning:
	bash scripts/install.sh k8s-overprovisioning-datadog

install-claude-k8s-overprovisioning:
	bash scripts/install.sh --agent claude-user k8s-overprovisioning-datadog

install-domain-comprehension: install-squad-map
	bash scripts/install.sh domain-comprehension

install-claude-domain-comprehension: install-claude-squad-map
	bash scripts/install.sh --agent claude-user domain-comprehension

install-squad-map:
	bash scripts/install.sh squad-map

install-claude-squad-map:
	bash scripts/install.sh --agent claude-user squad-map

install-who-owns-x-bot: install-squad-map
	bash scripts/install.sh who-owns-x-bot

install-claude-who-owns-x-bot: install-claude-squad-map
	bash scripts/install.sh --agent claude-user who-owns-x-bot

install-new-hire-guide: install-domain-comprehension install-squad-map
	bash scripts/install.sh new-hire-guide

install-claude-new-hire-guide: install-claude-domain-comprehension install-claude-squad-map
	bash scripts/install.sh --agent claude-user new-hire-guide

install-release-readiness-checker: install-pr-review install-k8s-overprovisioning install-incident-rca
	bash scripts/install.sh release-readiness-checker

install-claude-release-readiness-checker: install-claude-pr-review install-claude-k8s-overprovisioning install-claude-incident-rca
	bash scripts/install.sh --agent claude-user release-readiness-checker

install-migration-program-manager: install-mysql-to-postgres-sql install-squad-map
	bash scripts/install.sh migration-program-manager

install-claude-migration-program-manager: install-claude-mysql-to-postgres-sql install-claude-squad-map
	bash scripts/install.sh --agent claude-user migration-program-manager

install-mysql-to-postgres-sql:
	bash scripts/install.sh mysql-to-postgres-sql

install-claude-mysql-to-postgres-sql:
	bash scripts/install.sh --agent claude-user mysql-to-postgres-sql

install-loop-task-implementer:
	bash scripts/install.sh loop-task-implementer

install-claude-loop-task-implementer:
	bash scripts/install.sh --agent claude-user loop-task-implementer

install-backlog-runner: install-loop-task-implementer
	bash scripts/install.sh backlog-runner

install-claude-backlog-runner: install-claude-loop-task-implementer
	bash scripts/install.sh --agent claude-user backlog-runner

install-cost-optimization-sprint-planner: install-k8s-overprovisioning install-squad-map
	bash scripts/install.sh cost-optimization-sprint-planner

install-claude-cost-optimization-sprint-planner: install-claude-k8s-overprovisioning install-claude-squad-map
	bash scripts/install.sh --agent claude-user cost-optimization-sprint-planner

install-weekly-squad-digest: install-migration-program-manager install-cost-optimization-sprint-planner
	bash scripts/install.sh weekly-squad-digest

install-claude-weekly-squad-digest: install-claude-migration-program-manager install-claude-cost-optimization-sprint-planner
	bash scripts/install.sh --agent claude-user weekly-squad-digest

install-prd-architect:
	bash scripts/install.sh prd-architect

install-claude-prd-architect:
	bash scripts/install.sh --agent claude-user prd-architect

install-test-writer: install-unit-test-creator install-integration-test-creator install-contract-test-creator install-e2e-test-creator install-api-test-creator
	bash scripts/install.sh test-writer

install-claude-test-writer: install-claude-unit-test-creator install-claude-integration-test-creator install-claude-contract-test-creator install-claude-e2e-test-creator install-claude-api-test-creator
	bash scripts/install.sh --agent claude-user test-writer

install-unit-test-creator:
	bash scripts/install.sh unit-test-creator

install-claude-unit-test-creator:
	bash scripts/install.sh --agent claude-user unit-test-creator

install-integration-test-creator:
	bash scripts/install.sh integration-test-creator

install-claude-integration-test-creator:
	bash scripts/install.sh --agent claude-user integration-test-creator

install-contract-test-creator:
	bash scripts/install.sh contract-test-creator

install-claude-contract-test-creator:
	bash scripts/install.sh --agent claude-user contract-test-creator

install-e2e-test-creator:
	bash scripts/install.sh e2e-test-creator

install-claude-e2e-test-creator:
	bash scripts/install.sh --agent claude-user e2e-test-creator

install-api-test-creator:
	bash scripts/install.sh api-test-creator

install-claude-api-test-creator:
	bash scripts/install.sh --agent claude-user api-test-creator

install-architecture-review:
	bash scripts/install.sh architecture-review

install-claude-architecture-review:
	bash scripts/install.sh --agent claude-user architecture-review

install-system-design:
	bash scripts/install.sh system-design

install-claude-system-design:
	bash scripts/install.sh --agent claude-user system-design

install-api-design-review:
	bash scripts/install.sh api-design-review

install-claude-api-design-review:
	bash scripts/install.sh --agent claude-user api-design-review

install-database-review:
	bash scripts/install.sh database-review

install-claude-database-review:
	bash scripts/install.sh --agent claude-user database-review

install-security-review:
	bash scripts/install.sh security-review

install-claude-security-review:
	bash scripts/install.sh --agent claude-user security-review

install-performance-review:
	bash scripts/install.sh performance-review

install-claude-performance-review:
	bash scripts/install.sh --agent claude-user performance-review

install-capacity-planner:
	bash scripts/install.sh capacity-planner

install-claude-capacity-planner:
	bash scripts/install.sh --agent claude-user capacity-planner

install-observability-review:
	bash scripts/install.sh observability-review

install-claude-observability-review:
	bash scripts/install.sh --agent claude-user observability-review

install-deployment-risk-review:
	bash scripts/install.sh deployment-risk-review

install-claude-deployment-risk-review:
	bash scripts/install.sh --agent claude-user deployment-risk-review

install-dependency-upgrade-review:
	bash scripts/install.sh dependency-upgrade-review

install-claude-dependency-upgrade-review:
	bash scripts/install.sh --agent claude-user dependency-upgrade-review

install-tech-debt-assessor:
	bash scripts/install.sh tech-debt-assessor

install-claude-tech-debt-assessor:
	bash scripts/install.sh --agent claude-user tech-debt-assessor

install-change-impact-analyzer:
	bash scripts/install.sh change-impact-analyzer

install-claude-change-impact-analyzer:
	bash scripts/install.sh --agent claude-user change-impact-analyzer

install-resilience-review:
	bash scripts/install.sh resilience-review

install-claude-resilience-review:
	bash scripts/install.sh --agent claude-user resilience-review

install-implementation-planner:
	bash scripts/install.sh implementation-planner

install-claude-implementation-planner:
	bash scripts/install.sh --agent claude-user implementation-planner

install-production-readiness-review: install-pr-review install-change-impact-analyzer install-deployment-risk-review install-security-review install-observability-review install-resilience-review install-api-design-review install-database-review install-performance-review install-capacity-planner install-dependency-upgrade-review
	bash scripts/install.sh production-readiness-review

install-claude-production-readiness-review: install-claude-pr-review install-claude-change-impact-analyzer install-claude-deployment-risk-review install-claude-security-review install-claude-observability-review install-claude-resilience-review install-claude-api-design-review install-claude-database-review install-claude-performance-review install-claude-capacity-planner install-claude-dependency-upgrade-review
	bash scripts/install.sh --agent claude-user production-readiness-review
