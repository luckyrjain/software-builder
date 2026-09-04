#!/usr/bin/env python3
"""The shared structural checks every registered skill must pass.

`make/core.mk` used to spell these out once per skill: ~34 hand-written
`lint-<skill>` recipes carrying the same six checks re-targeted at a different
directory, plus the same `## Invocation`, safe-output and pressure-tests
assertions inline. This module is the one interface behind all of them --
`lint_skill(root, skill_id, registry)` returns the errors for one skill -- so a
check is written, worded and fixed once, and a skill's `lint-<skill>` recipe
carries one line for the whole shared set instead of ~20. What stays in Make is
what is genuinely per-skill: content assertions on one skill's own prose
(`schema_version: 3`, `INV-12`) and that skill's pytest/py_compile steps.

Per-skill differences that are data live either in the registry's `lint:` block
(the SKILL.md line cap) or in the explicit tables below, each of which records
only the delta from the shared default.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.registry.schema import load_registry_raw  # noqa: E402
from scripts.validate_references import validate_files  # noqa: E402

WORKFLOW_FRONTMATTER_KEYS = ("workflow_version", "phase", "produces", "consumes")

SAFE_OUTPUT_LINK = "docs/skill-framework/shared/safe-output.md"
PROMPT_INJECTION_LINK = "docs/skill-framework/shared/prompt-injection.md"
SKILL_ROUTING_LINK = "docs/skill-framework/shared/skill-routing.md"

# Markdown globs handed to the reference checker, relative to the skill dir. The
# per-skill recipes all passed these three; the handful of skills that ship
# Markdown outside them declare the extra globs in _EXTRA_LINK_GLOBS.
BASE_LINK_GLOBS = ("*.md", "reference/*.md", "workflow/*.md")

_EXTRA_LINK_GLOBS: dict[str, tuple[str, ...]] = {
    "k8s-overprovisioning-datadog": ("render/*.md", "templates/*.md"),
    "domain-comprehension": ("reference/domain-packs/*.md",),
    "mysql-to-postgres-sql": ("reference/domain-packs/*.md",),
}

# test-writer is a router: its own links are checked together with the five
# test-creator skills it routes to, so a broken hand-off is caught from the
# router's side too. Paths here are repo-relative, not skill-relative.
_CROSS_SKILL_LINK_GLOBS: dict[str, tuple[str, ...]] = {
    "test-writer": tuple(
        f"{creator}/{leaf}"
        for creator in (
            "unit-test-creator",
            "integration-test-creator",
            "contract-test-creator",
            "e2e-test-creator",
            "api-test-creator",
        )
        for leaf in ("SKILL.md", "workflow/*.md")
    ),
}

# reference/ files every skill needs, plus the per-skill additions. Splitting
# them this way keeps the table a delta: a new skill inherits the base set and
# names only what is its own.
BASE_REFERENCE_FILES = ("phase-index", "lazy-load-index", "smoke-test", "pressure-tests")

# mysql-to-postgres-sql indexes its phases from lazy-load-index.md alone; it has
# no phase-index.md and never had one.
_BASE_REFERENCE_EXEMPT: dict[str, tuple[str, ...]] = {
    "mysql-to-postgres-sql": ("phase-index",),
}

_TEST_CREATOR_REFS = (
    "skill-contract",
    "gate-policy",
    "test-quality-deltas",
    "framework-detection",
    "report-format",
)

_EXTRA_REFERENCE_FILES: dict[str, tuple[str, ...]] = {
    "api-design-review": ("report-format",),
    "api-test-creator": _TEST_CREATOR_REFS,
    "architecture-review": ("report-format",),
    "backlog-runner": ("queue-policy", "morning-summary-format"),
    "capacity-planner": ("report-format",),
    "change-impact-analyzer": ("report-format",),
    "contract-test-creator": _TEST_CREATOR_REFS,
    "cost-optimization-sprint-planner": ("gate-policy", "sweep-policy", "report-format"),
    "database-review": ("report-format",),
    "dependency-upgrade-review": ("report-format",),
    "deployment-risk-review": ("report-format",),
    "domain-comprehension": (
        "mcp-capabilities",
        "phase-outputs",
        "manifest-schema",
        "repo-classification",
        "evidence-precedence",
        "evidence-summary",
        "business-flows",
        "large-scale-execution",
    ),
    "e2e-test-creator": _TEST_CREATOR_REFS,
    "implementation-planner": ("report-format",),
    "incident-rca": ("mcp-capabilities",),
    "incident-triage-agent": (
        "unattended-gate-policy",
        "triage-doc-format",
        "postmortem-format",
    ),
    "integration-test-creator": _TEST_CREATOR_REFS,
    "k8s-overprovisioning-datadog": ("mcp-capabilities",),
    "loop-task-implementer": ("mcp-capabilities", "platform-adapters"),
    "migration-program-manager": ("report-format",),
    "mysql-to-postgres-sql": (
        "function-translations",
        "collection-domain-files",
        "org-migration-gaps",
        "timestamp-handling",
        "data-type-mapping",
        "case-sensitivity",
        "nodejs-migration",
        "python-migration",
        "migration-prompts",
        "shadow-migration",
        "collection-checklist-refresh",
        "migration-edge-cases",
        "calibration-snippets",
    ),
    "new-hire-guide": ("tour-format",),
    "observability-review": ("report-format",),
    "performance-review": ("report-format",),
    "pr-gatekeeper": ("auto-post-policy",),
    "prd-architect": (
        "skill-contract",
        "rationalization-guards",
        "global-rules",
        "depth",
        "response-modes",
        "section-triggers",
        "requirements-format",
        "correctness-rules",
        "adversarial-review",
        "output-contract",
    ),
    "production-readiness-review": ("report-format",),
    "release-readiness-checker": ("gate-policy", "report-format"),
    "resilience-review": ("report-format",),
    "security-review": ("report-format",),
    "squad-map": ("squad-mapping", "mcp-capabilities", "config-schema"),
    "system-design": ("report-format",),
    "tech-debt-assessor": ("report-format",),
    "test-writer": ("skill-contract", "level-classification"),
    "unit-test-creator": _TEST_CREATOR_REFS,
    "weekly-squad-digest": ("report-format",),
    "who-owns-x-bot": ("slack-format",),
}

# Skills whose SKILL.md must set `disable-model-invocation: true`: the automation
# entry points (webhook/schedule/bot wrappers) that must not compete with the
# ambiently invocable skill they wrap. Every other skill must NOT set the key.
_DISABLE_MODEL_INVOCATION_REQUIRED = frozenset(
    {
        "backlog-runner",
        "incident-triage-agent",
        "pr-gatekeeper",
        "weekly-squad-digest",
        "who-owns-x-bot",
    },
)

# test-writer is a pure router: it renders nothing itself and escalates nowhere,
# so it carries neither the safe-output nor the cross-skill-escalation link.
_NO_SAFE_OUTPUT_LINK = frozenset({"test-writer"})
_NO_CROSS_SKILL_ESCALATION = frozenset({"test-writer"})

# domain-comprehension's pressure tests are driven by tests/run_pressure_tests.sh
# from its own lint target rather than linked from reference/smoke-test.md.
_NO_PRESSURE_TESTS_LINK = frozenset({"domain-comprehension"})

# Guidance appended to a SKILL.md-too-long failure, telling the author where the
# detail belongs. Skills absent from the table get the bare line count.
_LENGTH_GUIDANCE: dict[str, str] = {
    "architecture-review": "keep orchestrator thin; detail in workflow/",
    "api-design-review": "keep orchestrator thin; detail in workflow/",
    "backlog-runner": "keep orchestrator thin; detail in workflow/",
    "capacity-planner": "keep orchestrator thin; detail in workflow/",
    "change-impact-analyzer": "keep the leaf bounded; detail in workflow/",
    "cost-optimization-sprint-planner": "keep orchestrator thin; detail in workflow/",
    "database-review": "keep orchestrator thin; detail in workflow/",
    "dependency-upgrade-review": "keep orchestrator thin; detail in workflow/",
    "deployment-risk-review": "keep orchestrator thin; detail in workflow/",
    "domain-comprehension": "keep orchestrator thin; detail in workflow/",
    "implementation-planner": "keep the leaf bounded; detail in workflow/",
    "incident-rca": "push detail into workflow/ and reference/",
    "incident-triage-agent": "keep orchestrator thin; detail in workflow/",
    "k8s-overprovisioning-datadog": "keep orchestrator thin; detail in workflow/",
    "migration-program-manager": "keep orchestrator thin; detail in workflow/",
    "new-hire-guide": "keep orchestrator thin; detail in workflow/",
    "observability-review": "keep orchestrator thin; detail in workflow/",
    "performance-review": "keep orchestrator thin; detail in workflow/",
    "pr-gatekeeper": "keep orchestrator thin; detail in workflow/",
    "pr-review": "keep orchestrator thin; detail in workflow/",
    "production-readiness-review": "keep the orchestrator bounded; detail in workflow/",
    "release-readiness-checker": "keep orchestrator thin; detail in workflow/",
    "resilience-review": "keep the leaf bounded; detail in workflow/",
    "security-review": "keep orchestrator thin; detail in workflow/",
    "squad-map": "keep orchestrator thin; detail in workflow/",
    "system-design": "keep orchestrator thin; detail in workflow/",
    "tech-debt-assessor": "keep orchestrator thin; detail in workflow/",
    "weekly-squad-digest": "keep orchestrator thin; detail in workflow/",
    "who-owns-x-bot": "keep orchestrator thin; detail in workflow/",
}


@dataclass(frozen=True)
class RenderSurface:
    """A file that renders untrusted third-party content into a deliverable.

    Each must name the guidance it follows and show that it escapes -- and,
    where the surface carries secrets, redacts -- what it renders.
    """

    path: str
    escape_pattern: str = "escape|fence|backtick"
    require_redact: bool = True
    require_prompt_injection: bool = True
    extra_literals: tuple[str, ...] = field(default_factory=tuple)

    @property
    def contract(self) -> str:
        return (
            "prompt-injection and safe-output"
            if self.require_prompt_injection
            else "safe-output"
        )


_REPORT_FORMAT = RenderSurface("reference/report-format.md")
_TEST_CREATOR_SURFACE = RenderSurface(
    "reference/report-format.md",
    escape_pattern="escape|backtick|code span",
    require_redact=False,
)

_RENDER_SURFACES: dict[str, tuple[RenderSurface, ...]] = {
    "api-design-review": (_REPORT_FORMAT,),
    "api-test-creator": (_TEST_CREATOR_SURFACE,),
    "architecture-review": (_REPORT_FORMAT,),
    "backlog-runner": (
        RenderSurface("reference/morning-summary-format.md", escape_pattern="escape|fence"),
    ),
    "capacity-planner": (_REPORT_FORMAT,),
    "change-impact-analyzer": (_REPORT_FORMAT,),
    "contract-test-creator": (_TEST_CREATOR_SURFACE,),
    "cost-optimization-sprint-planner": (
        RenderSurface("reference/report-format.md", require_redact=False),
    ),
    "database-review": (_REPORT_FORMAT,),
    "dependency-upgrade-review": (_REPORT_FORMAT,),
    "deployment-risk-review": (_REPORT_FORMAT,),
    "domain-comprehension": (
        RenderSurface(
            "reference/deliverable-templates.md",
            escape_pattern="escape|backtick|code span",
            require_redact=False,
            require_prompt_injection=False,
        ),
    ),
    "e2e-test-creator": (_TEST_CREATOR_SURFACE,),
    "implementation-planner": (_REPORT_FORMAT,),
    "incident-rca": (
        RenderSurface(
            "report-template.md",
            escape_pattern="escape|backtick|code span",
            require_redact=False,
            require_prompt_injection=False,
        ),
    ),
    "incident-triage-agent": (
        RenderSurface("reference/triage-doc-format.md", require_redact=False),
        RenderSurface("reference/postmortem-format.md", require_redact=False),
    ),
    "integration-test-creator": (_TEST_CREATOR_SURFACE,),
    "k8s-overprovisioning-datadog": (
        RenderSurface(
            "render/markdown.md",
            escape_pattern="escape|backtick|code span",
            require_redact=False,
            require_prompt_injection=False,
        ),
    ),
    "loop-task-implementer": (RenderSurface("report-template.md"),),
    "migration-program-manager": (_REPORT_FORMAT,),
    "mysql-to-postgres-sql": (
        RenderSurface("workflow/migrate-service.md", require_redact=False),
    ),
    "new-hire-guide": (RenderSurface("reference/tour-format.md"),),
    "observability-review": (_REPORT_FORMAT,),
    "performance-review": (_REPORT_FORMAT,),
    "pr-gatekeeper": (
        RenderSurface("reference/auto-post-policy.md", require_redact=False),
    ),
    "pr-review": (
        RenderSurface("workflow/posting.md", escape_pattern="escape|fence"),
        RenderSurface("workflow/phase-5.md", escape_pattern="escape|fence"),
    ),
    "prd-architect": (
        RenderSurface(
            "workflow/gate.md",
            escape_pattern="escape|fence",
            extra_literals=("source_material",),
        ),
    ),
    "production-readiness-review": (_REPORT_FORMAT,),
    "release-readiness-checker": (
        RenderSurface("reference/report-format.md", require_redact=False),
    ),
    "resilience-review": (_REPORT_FORMAT,),
    "security-review": (_REPORT_FORMAT,),
    "squad-map": (RenderSurface("reference/squad-mapping.md", require_redact=False),),
    "system-design": (_REPORT_FORMAT,),
    "tech-debt-assessor": (_REPORT_FORMAT,),
    "unit-test-creator": (_TEST_CREATOR_SURFACE,),
    "weekly-squad-digest": (
        RenderSurface("reference/report-format.md", require_redact=False),
    ),
    "who-owns-x-bot": (
        RenderSurface(
            "reference/slack-format.md",
            escape_pattern="escape|strip",
            require_redact=False,
        ),
    ),
}


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _check_skill_md_length(skill_dir: Path, skill_id: str, max_lines: int) -> list[str]:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return [f"error: {skill_id}: missing {skill_md.as_posix()}"]
    text = _read(skill_md)
    if text is None:
        return [f"error: {skill_id}: cannot read {skill_md.as_posix()}"]
    # `wc -l` counts newlines, which is what the Make recipe compared.
    lines = text.count("\n")
    if lines == 0:
        return [f"error: {skill_id}: {skill_md.as_posix()} is empty"]
    if lines > max_lines:
        guidance = _LENGTH_GUIDANCE.get(skill_id)
        suffix = f" — {guidance}" if guidance else ""
        return [f"error: {skill_id}: SKILL.md {lines} lines (> {max_lines}){suffix}"]
    return []


def _frontmatter(text: str) -> str:
    """The block between the first and second `---` fence, as awk saw it."""
    body: list[str] = []
    seen = 0
    for line in text.splitlines():
        if line == "---":
            seen += 1
            continue
        if seen == 1:
            body.append(line)
        elif seen >= 2:
            break
    return "\n".join(body)


def _check_workflow_frontmatter(skill_dir: Path, skill_id: str) -> list[str]:
    # The five skills that ship a workflow-contract.yaml have these same four
    # keys checked route-by-route by scripts/validate_workflow_contracts.py,
    # which their lint target runs instead.
    if (skill_dir / "workflow-contract.yaml").is_file():
        return []
    workflow = skill_dir / "workflow"
    if not workflow.is_dir():
        return []
    errors: list[str] = []
    for md_file in sorted(workflow.glob("*.md")):
        text = _read(md_file)
        if text is None:
            errors.append(f"error: {skill_id}: cannot read {md_file.as_posix()}")
            continue
        frontmatter = _frontmatter(text)
        for key in WORKFLOW_FRONTMATTER_KEYS:
            if not re.search(rf"^{re.escape(key)}:", frontmatter, re.MULTILINE):
                errors.append(
                    f"error: {skill_id}: {md_file.as_posix()} is missing {key} frontmatter "
                    "(workflow/*.md must declare "
                    f"{', '.join(WORKFLOW_FRONTMATTER_KEYS)})",
                )
    return errors


def _check_dangling_links(root: Path, skill_dir: Path, skill_id: str) -> list[str]:
    files: list[Path] = []
    for pattern in BASE_LINK_GLOBS + _EXTRA_LINK_GLOBS.get(skill_id, ()):
        files.extend(sorted(skill_dir.glob(pattern)))
    for pattern in _CROSS_SKILL_LINK_GLOBS.get(skill_id, ()):
        files.extend(sorted(root.glob(pattern)))
    return [
        f"error: {skill_id}: dangling reference link: {detail}"
        for detail in validate_files(files)
    ]


def _check_reference_files(skill_dir: Path, skill_id: str) -> list[str]:
    exempt = set(_BASE_REFERENCE_EXEMPT.get(skill_id, ()))
    required = [name for name in BASE_REFERENCE_FILES if name not in exempt]
    required.extend(_EXTRA_REFERENCE_FILES.get(skill_id, ()))
    return [
        f"error: {skill_id}: missing {(skill_dir / 'reference' / f'{name}.md').as_posix()}"
        for name in required
        if not (skill_dir / "reference" / f"{name}.md").is_file()
    ]


def _check_shared_links(skill_dir: Path, skill_id: str) -> list[str]:
    errors: list[str] = []
    setup = _read(skill_dir / "SETUP.md")
    if setup is None:
        errors.append(f"error: {skill_id}: missing {(skill_dir / 'SETUP.md').as_posix()}")
    elif "skill-framework" not in setup:
        errors.append(f"error: {skill_id}: SETUP.md must link to docs/skill-framework")

    skill_md = _read(skill_dir / "SKILL.md")
    if skill_md is None:
        return errors
    if SKILL_ROUTING_LINK not in skill_md:
        errors.append(f"error: {skill_id}: SKILL.md must link to shared skill-routing")
    if PROMPT_INJECTION_LINK not in skill_md:
        errors.append(f"error: {skill_id}: SKILL.md must link to shared prompt-injection")
    if skill_id not in _NO_SAFE_OUTPUT_LINK and SAFE_OUTPUT_LINK not in skill_md:
        errors.append(f"error: {skill_id}: SKILL.md must link to shared safe-output")
    if skill_id not in _NO_CROSS_SKILL_ESCALATION and "cross-skill-escalation" not in skill_md:
        errors.append(
            f"error: {skill_id}: SKILL.md must link to shared cross-skill-escalation",
        )

    declares = any(
        line.startswith("disable-model-invocation:") for line in skill_md.splitlines()
    )
    if skill_id in _DISABLE_MODEL_INVOCATION_REQUIRED:
        if "\ndisable-model-invocation: true" not in f"\n{skill_md}":
            errors.append(
                f"error: {skill_id}: SKILL.md must set disable-model-invocation: true",
            )
    elif declares:
        errors.append(f"error: {skill_id}: SKILL.md must NOT set disable-model-invocation")
    return errors


def _check_examples(skill_dir: Path, skill_id: str) -> list[str]:
    examples = skill_dir / "examples.md"
    text = _read(examples)
    if text is None:
        return [f"error: {skill_id}: missing {examples.as_posix()}"]
    if "## Invocation" not in text:
        return [f"error: {skill_id}: examples.md must have Invocation section"]
    return []


def _check_pressure_tests_link(skill_dir: Path, skill_id: str) -> list[str]:
    if skill_id in _NO_PRESSURE_TESTS_LINK:
        return []
    smoke = skill_dir / "reference" / "smoke-test.md"
    text = _read(smoke)
    if text is None or "pressure-tests" in text:
        return []
    return [f"error: {skill_id}: reference/smoke-test.md must link to pressure-tests.md"]


def _check_render_surfaces(skill_dir: Path, skill_id: str) -> list[str]:
    errors: list[str] = []
    for surface in _RENDER_SURFACES.get(skill_id, ()):
        text = _read(skill_dir / surface.path)
        if text is None:
            ok = False
        else:
            required = [SAFE_OUTPUT_LINK, *surface.extra_literals]
            if surface.require_prompt_injection:
                required.append(PROMPT_INJECTION_LINK)
            lowered = text.lower()
            ok = (
                all(literal.lower() in lowered for literal in required)
                and re.search(surface.escape_pattern, text, re.IGNORECASE) is not None
                and (not surface.require_redact or "redact" in lowered)
            )
        if not ok:
            errors.append(
                f"error: {skill_id}: {surface.path} must sanitize untrusted rendered "
                f"fields per {surface.contract}",
            )
    return errors


def lint_skill(root: Path, skill_id: str, registry: Mapping[str, Any]) -> list[str]:
    """Every shared structural check for one registered skill.

    `registry` is the resolved registry mapping `load_registry_raw` returns --
    the same canonical projection of `skills.yaml` + `skills.d/` every other
    caller reads. Only two of its fields are consulted (the skill's `path` and
    its `lint.skill_md_max_lines` cap); validating the registry's own shape is
    `validate-registry`'s job, which runs once per lint rather than once per
    skill.

    Returns one `error: <skill>: ...` line per failure, empty when the skill
    passes. Every caller -- the CLI below, `make lint-<skill>`, the tests --
    goes through this one function, so a check cannot be enforced in one place
    and skipped in another.
    """
    entry = registry.get("skills", {}).get(skill_id)
    if not isinstance(entry, Mapping):
        return [f"error: {skill_id}: not a registered skill (absent from skills.yaml)"]
    skill_dir = root / str(entry.get("path", skill_id))
    if not skill_dir.is_dir():
        return [f"error: {skill_id}: missing skill directory {skill_dir.as_posix()}"]

    lint_spec = entry.get("lint")
    # Mirrors scripts/registry/schema.py's own default for an absent cap.
    max_lines = 180
    if isinstance(lint_spec, Mapping):
        max_lines = int(lint_spec.get("skill_md_max_lines", max_lines))

    errors = _check_skill_md_length(skill_dir, skill_id, max_lines)
    errors.extend(_check_workflow_frontmatter(skill_dir, skill_id))
    errors.extend(_check_dangling_links(root, skill_dir, skill_id))
    errors.extend(_check_reference_files(skill_dir, skill_id))
    errors.extend(_check_shared_links(skill_dir, skill_id))
    errors.extend(_check_examples(skill_dir, skill_id))
    errors.extend(_check_pressure_tests_link(skill_dir, skill_id))
    errors.extend(_check_render_surfaces(skill_dir, skill_id))
    return errors


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the shared structural lint checks over registered skills.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--skill", help="Lint one skill by registry id")
    mode.add_argument("--all", action="store_true", help="Lint every registered skill")
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Repository root (default: the checkout this script lives in)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    registry = load_registry_raw(root / "skills.yaml")
    skill_ids = sorted(registry.get("skills", {})) if args.all else [args.skill]

    errors: list[str] = []
    for skill_id in skill_ids:
        errors.extend(lint_skill(root, skill_id, registry))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"  ok (shared checks: {', '.join(skill_ids)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
