"""The shared per-skill lint checks: one failing case each, plus the live roster."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from scripts.lint_skills import lint_skill, main
from scripts.registry.schema import load_registry_raw

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL = "architecture-review"

REGISTRY: dict[str, Any] = {
    "skills": {SKILL: {"path": SKILL, "lint": {"skill_md_max_lines": 180}}},
}

SKILL_MD = """\
# Architecture review

Routing: docs/skill-framework/shared/skill-routing.md
Untrusted input: docs/skill-framework/shared/prompt-injection.md
Rendered output: docs/skill-framework/shared/safe-output.md
Escalation: docs/skill-framework/shared/cross-skill-escalation.md
"""

WORKFLOW_MD = """\
---
workflow_version: 1
phase: analyze
produces: architecture_review_report
consumes: prd_report
---

# Analyze
"""

# Deliberately carries exactly one of the escape-pattern alternatives
# (escape|fence|backtick) so the parametrized case below can remove it.
REPORT_FORMAT_MD = """\
# Report format

Sanitize per docs/skill-framework/shared/prompt-injection.md and
docs/skill-framework/shared/safe-output.md: escape untrusted values, redact secrets.
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def skill_root(tmp_path: Path) -> Path:
    """A synthetic checkout holding one skill that passes every shared check."""
    skill_dir = tmp_path / SKILL
    _write(skill_dir / "SKILL.md", SKILL_MD)
    _write(skill_dir / "SETUP.md", "See docs/skill-framework for the shared contract.\n")
    _write(skill_dir / "examples.md", "# Examples\n\n## Invocation\n\nRun it.\n")
    _write(skill_dir / "workflow" / "analyze.md", WORKFLOW_MD)
    for name in ("phase-index", "lazy-load-index"):
        _write(skill_dir / "reference" / f"{name}.md", f"# {name}\n")
    _write(skill_dir / "reference" / "smoke-test.md", "# Smoke test\n\nSee pressure-tests.\n")
    _write(skill_dir / "reference" / "pressure-tests.md", "# Pressure tests\n")
    _write(skill_dir / "reference" / "report-format.md", REPORT_FORMAT_MD)
    return tmp_path


def test_synthetic_skill_passes_every_shared_check(skill_root: Path) -> None:
    assert lint_skill(skill_root, SKILL, REGISTRY) == []


def test_skill_md_over_the_registry_line_cap(skill_root: Path) -> None:
    _write(skill_root / SKILL / "SKILL.md", SKILL_MD + "filler\n" * 200)
    errors = lint_skill(skill_root, SKILL, REGISTRY)
    assert any("SKILL.md" in e and "(> 180)" in e for e in errors), errors
    assert all(e.startswith(f"error: {SKILL}: ") for e in errors)


def test_skill_md_line_cap_comes_from_the_registry(skill_root: Path) -> None:
    registry = {"skills": {SKILL: {"path": SKILL, "lint": {"skill_md_max_lines": 2}}}}
    errors = lint_skill(skill_root, SKILL, registry)
    assert [e for e in errors if "(> 2)" in e], errors


def test_empty_skill_md(skill_root: Path) -> None:
    _write(skill_root / SKILL / "SKILL.md", "")
    assert [e for e in lint_skill(skill_root, SKILL, REGISTRY) if "is empty" in e]


def test_missing_skill_md(skill_root: Path) -> None:
    (skill_root / SKILL / "SKILL.md").unlink()
    errors = lint_skill(skill_root, SKILL, REGISTRY)
    assert errors == [f"error: {SKILL}: missing {(skill_root / SKILL / 'SKILL.md').as_posix()}"]


@pytest.mark.parametrize("key", ["workflow_version", "phase", "produces", "consumes"])
def test_workflow_frontmatter_key_missing(skill_root: Path, key: str) -> None:
    stripped = "\n".join(
        line for line in WORKFLOW_MD.splitlines() if not line.startswith(f"{key}:")
    )
    _write(skill_root / SKILL / "workflow" / "analyze.md", stripped + "\n")
    errors = lint_skill(skill_root, SKILL, REGISTRY)
    assert [e for e in errors if f"missing {key} frontmatter" in e], errors


def test_workflow_frontmatter_skipped_when_a_workflow_contract_exists(
    skill_root: Path,
) -> None:
    """The five contract-bearing skills get these keys checked route-by-route by
    scripts/validate_workflow_contracts.py instead, so this pass stands down."""
    _write(skill_root / SKILL / "workflow" / "analyze.md", "# Analyze\n")
    assert [e for e in lint_skill(skill_root, SKILL, REGISTRY) if "frontmatter" in e]
    _write(skill_root / SKILL / "workflow-contract.yaml", "schema_version: 1\n")
    assert not [e for e in lint_skill(skill_root, SKILL, REGISTRY) if "frontmatter" in e]


def test_dangling_markdown_link(skill_root: Path) -> None:
    _write(
        skill_root / SKILL / "examples.md",
        "# Examples\n\n## Invocation\n\nSee [gone](reference/not-a-file.md).\n",
    )
    errors = lint_skill(skill_root, SKILL, REGISTRY)
    assert [e for e in errors if "dangling reference link" in e and "not-a-file.md" in e]


def test_missing_required_reference_file(skill_root: Path) -> None:
    (skill_root / SKILL / "reference" / "report-format.md").unlink()
    errors = lint_skill(skill_root, SKILL, REGISTRY)
    assert [e for e in errors if e.endswith("reference/report-format.md")], errors


def test_setup_md_must_link_the_framework(skill_root: Path) -> None:
    _write(skill_root / SKILL / "SETUP.md", "Nothing shared here.\n")
    errors = lint_skill(skill_root, SKILL, REGISTRY)
    assert errors == [f"error: {SKILL}: SETUP.md must link to docs/skill-framework"]


@pytest.mark.parametrize(
    ("link", "expected"),
    [
        ("docs/skill-framework/shared/skill-routing.md", "must link to shared skill-routing"),
        (
            "docs/skill-framework/shared/prompt-injection.md",
            "must link to shared prompt-injection",
        ),
        ("docs/skill-framework/shared/safe-output.md", "must link to shared safe-output"),
        (
            "docs/skill-framework/shared/cross-skill-escalation.md",
            "must link to shared cross-skill-escalation",
        ),
    ],
)
def test_shared_skill_md_links(skill_root: Path, link: str, expected: str) -> None:
    _write(skill_root / SKILL / "SKILL.md", SKILL_MD.replace(link, "docs/elsewhere.md"))
    errors = lint_skill(skill_root, SKILL, REGISTRY)
    assert [e for e in errors if expected in e], errors


def test_examples_needs_an_invocation_section(skill_root: Path) -> None:
    _write(skill_root / SKILL / "examples.md", "# Examples\n\n## Calls\n")
    errors = lint_skill(skill_root, SKILL, REGISTRY)
    assert errors == [f"error: {SKILL}: examples.md must have Invocation section"]


def test_smoke_test_must_link_pressure_tests(skill_root: Path) -> None:
    _write(skill_root / SKILL / "reference" / "smoke-test.md", "# Smoke test\n")
    errors = lint_skill(skill_root, SKILL, REGISTRY)
    assert errors == [
        f"error: {SKILL}: reference/smoke-test.md must link to pressure-tests.md",
    ]


@pytest.mark.parametrize("dropped", ["prompt-injection.md", "safe-output.md", "escape", "redact"])
def test_render_surface_must_show_its_sanitization(skill_root: Path, dropped: str) -> None:
    _write(
        skill_root / SKILL / "reference" / "report-format.md",
        REPORT_FORMAT_MD.replace(dropped, "elsewhere"),
    )
    errors = lint_skill(skill_root, SKILL, REGISTRY)
    assert errors == [
        f"error: {SKILL}: reference/report-format.md must sanitize untrusted rendered "
        "fields per prompt-injection and safe-output",
    ]


def test_disable_model_invocation_is_forbidden_outside_automation_entry_points(
    skill_root: Path,
) -> None:
    _write(skill_root / SKILL / "SKILL.md", "disable-model-invocation: true\n" + SKILL_MD)
    errors = lint_skill(skill_root, SKILL, REGISTRY)
    assert errors == [f"error: {SKILL}: SKILL.md must NOT set disable-model-invocation"]


def test_disable_model_invocation_is_required_for_automation_entry_points(
    tmp_path: Path,
) -> None:
    gatekeeper = tmp_path / "pr-gatekeeper"
    _write(gatekeeper / "SKILL.md", SKILL_MD)
    registry = {"skills": {"pr-gatekeeper": {"path": "pr-gatekeeper", "lint": {}}}}
    errors = lint_skill(tmp_path, "pr-gatekeeper", registry)
    assert [e for e in errors if "must set disable-model-invocation: true" in e], errors


def test_unregistered_skill_is_reported_not_skipped(skill_root: Path) -> None:
    assert lint_skill(skill_root, "not-a-skill", REGISTRY) == [
        "error: not-a-skill: not a registered skill (absent from skills.yaml)",
    ]


def test_every_registered_skill_passes_in_this_repository() -> None:
    registry = load_registry_raw(REPO_ROOT / "skills.yaml")
    errors: list[str] = []
    for skill_id in sorted(registry["skills"]):
        errors.extend(lint_skill(REPO_ROOT, skill_id, registry))
    assert errors == []


def test_cli_all_exits_zero_for_this_repository(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--all", "--root", str(REPO_ROOT)]) == 0
    assert "ok (shared checks:" in capsys.readouterr().out


def test_cli_reports_failures_on_stderr(skill_root: Path) -> None:
    (skill_root / SKILL / "examples.md").unlink()
    _write(skill_root / "skills.yaml", f"skills:\n  {SKILL}:\n    path: {SKILL}\n")
    assert main(["--skill", SKILL, "--root", str(skill_root)]) == 1
