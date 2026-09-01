from __future__ import annotations

from pathlib import Path

from scripts.registry.models import Registry

# `make/core.mk` repeats the full skill roster verbatim in several `for skill in
# ...; do` loops inside its `lint-framework` recipe. That's the exact repeated-list
# drift risk this generator removes: instead of three (or more) hand-maintained
# copies that can silently fall out of sync when a skill is added or removed, there
# is one generated Make variable (`ALL_SKILLS`) that every call site references.
#
# The order below is frozen to match the order the roster has always appeared in
# `make/core.mk` (it predates this generator and isn't alphabetical or otherwise
# derivable from skills.yaml's own key order). Preserving it keeps `make -n`'s
# expanded recipe text byte-for-byte identical to what it was before this file
# existed. `_validate_roster` below is what actually prevents drift going
# forward: it fails generation loudly if skills.yaml's skill set and this order
# ever disagree, so a newly added/removed skill can't be silently missed.
ALL_SKILLS_ORDER: tuple[str, ...] = (
    "pr-review",
    "pr-gatekeeper",
    "incident-rca",
    "incident-triage-agent",
    "k8s-overprovisioning-datadog",
    "domain-comprehension",
    "squad-map",
    "who-owns-x-bot",
    "new-hire-guide",
    "release-readiness-checker",
    "migration-program-manager",
    "mysql-to-postgres-sql",
    "loop-task-implementer",
    "backlog-runner",
    "cost-optimization-sprint-planner",
    "weekly-squad-digest",
    "prd-architect",
    "test-writer",
    "unit-test-creator",
    "integration-test-creator",
    "contract-test-creator",
    "e2e-test-creator",
    "api-test-creator",
    "architecture-review",
    "system-design",
    "api-design-review",
    "database-review",
    "security-review",
    "performance-review",
    "capacity-planner",
    "observability-review",
    "deployment-risk-review",
    "dependency-upgrade-review",
    "tech-debt-assessor",
    "change-impact-analyzer",
    "resilience-review",
    "implementation-planner",
    "production-readiness-review",
)

_GENERATED_HEADER = (
    "# GENERATED from skills.yaml — do not edit; run `make generate`.\n"
    "#\n"
    "# ALL_SKILLS is the single source of truth for the full skill roster used by\n"
    "# make/core.mk's lint-framework recipe (previously hardcoded verbatim in three\n"
    "# separate `for skill in ...; do` loops). `make generate-check` fails if this\n"
    "# file drifts from skills.yaml -- that's the drift guard, not a separate\n"
    "# exception (see scripts/registry/generate_makefile_roster.py): a skill added\n"
    "# to skills.yaml but missing from ALL_SKILLS_ORDER is simply appended after it\n"
    "# (sorted), so the frozen order only pins the *existing* 38 skills' historical\n"
    "# positions -- it never has to be hand-updated, and never fails a registry\n"
    "# (e.g. a test fixture) that doesn't resemble the real repository at all.\n"
)


def _ordered_skills(registry: Registry) -> tuple[str, ...]:
    registry_skills = set(registry.skills.keys())
    ordered = [skill for skill in ALL_SKILLS_ORDER if skill in registry_skills]
    extra = sorted(registry_skills - set(ALL_SKILLS_ORDER))
    return tuple(ordered + extra)


def render_makefile_roster(registry: Registry) -> str:
    skills = " ".join(_ordered_skills(registry))
    return _GENERATED_HEADER + "\n" + f"ALL_SKILLS := {skills}\n"


def generate_makefile_roster(root: Path, registry: Registry) -> dict[Path, str]:
    return {
        root / "make" / "generated-roster.mk": render_makefile_roster(registry),
    }
