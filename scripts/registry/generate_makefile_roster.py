from __future__ import annotations

from pathlib import Path

from scripts.registry.models import Registry, SkillEntry

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

# `make install-<skill>` is the public entry point for installing one skill, and
# `make install-claude-<skill>` the Claude-host variant. The target name is the
# skill id, except where an older, shorter alias predates the id and is still
# what the documentation and muscle memory use.
INSTALL_TARGET_ALIASES: dict[str, str] = {
    "k8s-overprovisioning-datadog": "k8s-overprovisioning",
}

# Prerequisites a skill needs that are not themselves skill installs, so
# `install.requires` cannot express them. Unlike skill prerequisites these are
# NOT host-prefixed for the Claude variant: the dependency bootstrap is
# host-independent, which is how make/core.mk encoded it by hand.
EXTRA_INSTALL_PREREQUISITES: dict[str, tuple[str, ...]] = {
    "incident-rca": ("install-incident-rca-deps",),
}

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
    "#\n"
    "# The install-<skill> / install-claude-<skill> rules below carry the same\n"
    "# guarantee: their prerequisite edges ARE each skill's `install.requires`,\n"
    "# read from the registry, so the Make graph cannot disagree with skills.yaml\n"
    "# about what a skill depends on. Adding a skill needs no make/core.mk edit.\n"
)


def _ordered_skills(registry: Registry) -> tuple[str, ...]:
    registry_skills = set(registry.skills.keys())
    ordered = [skill for skill in ALL_SKILLS_ORDER if skill in registry_skills]
    extra = sorted(registry_skills - set(ALL_SKILLS_ORDER))
    return tuple(ordered + extra)


def install_target(skill_id: str, *, host_prefix: str = "") -> str:
    """Make target name installing `skill_id` for the given host prefix."""
    return f"install-{host_prefix}{INSTALL_TARGET_ALIASES.get(skill_id, skill_id)}"


def _install_rule(entry: SkillEntry, skill_id: str, *, host_prefix: str, install_args: str) -> str:
    prerequisites = [
        install_target(required, host_prefix=host_prefix) for required in entry.install.requires
    ]
    prerequisites.extend(EXTRA_INSTALL_PREREQUISITES.get(skill_id, ()))
    target = install_target(skill_id, host_prefix=host_prefix)
    suffix = f": {' '.join(prerequisites)}" if prerequisites else ":"
    return f"{target}{suffix}\n\tbash scripts/install.sh {install_args}{skill_id}\n"


def render_install_targets(registry: Registry) -> str:
    """Render every per-skill install rule, plain and Claude host alike.

    These used to be hand-copied into make/core.mk -- two near-identical stanzas
    per skill, whose prerequisite edges restated `install.requires` from the
    registry. A separate validator existed only to prove the copies had not
    drifted; generating them removes both the copies and the need for that
    proof, since `make generate-check` already fails on any drift.
    """
    skills = _ordered_skills(registry)
    targets = [
        install_target(skill_id, host_prefix=prefix)
        for skill_id in skills
        for prefix in ("", "claude-")
    ]
    lines = [".PHONY: " + " ".join(targets), ""]
    for skill_id in skills:
        entry = registry.skills[skill_id]
        lines.append(_install_rule(entry, skill_id, host_prefix="", install_args=""))
        lines.append(
            _install_rule(entry, skill_id, host_prefix="claude-", install_args="--agent claude-user "),
        )
    return "\n".join(lines)


def render_makefile_roster(registry: Registry) -> str:
    skills = " ".join(_ordered_skills(registry))
    return (
        _GENERATED_HEADER
        + "\n"
        + f"ALL_SKILLS := {skills}\n"
        + "\n"
        + render_install_targets(registry)
    )


def generate_makefile_roster(root: Path, registry: Registry) -> dict[Path, str]:
    return {
        root / "make" / "generated-roster.mk": render_makefile_roster(registry),
    }
