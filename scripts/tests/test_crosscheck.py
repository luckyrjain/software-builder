"""Tests for scripts/registry/crosscheck.py's `validate_platform_declarations` (gap-backlog F2).

The end-to-end tests here (`test_cmd_generate_check_fails_on_platform_declaration_drift` and
`test_cmd_validate_fails_on_platform_declaration_drift`) are the concrete regression tests named
by the change-impact report's `review_triggers`: a Builder placing `validate_platform_declarations`
anywhere other than inside `validate_registry()` (e.g. directly inside `_validate_all`) would still
pass a narrow unit test of the function in isolation while silently never being reached by
`cmd_generate --check` -- only an end-to-end invocation of the real CLI entry points catches that.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.registry.crosscheck import validate_platform_declarations
from scripts.registry.models import (
    CompositionSpec,
    HostDiscoverySpec,
    InstallSpec,
    LintSpec,
    Registry,
    SkillEntry,
)
from scripts.tests.test_registry import (
    _write_minimal_composition_contracts,
    _write_minimal_registry_fixture,
)


def _skill_entry(*, path: str = "demo", platforms: list[str]) -> SkillEntry:
    return SkillEntry(
        path=path,
        category="testing",
        invocation="ambient",
        hosts={
            "cursor": HostDiscoverySpec(discovery="rule"),
            "claude": HostDiscoverySpec(install=True),
            "kiro": HostDiscoverySpec(discovery="manual"),
        },
        install=InstallSpec(requires=[]),
        lint=LintSpec(skill_md_max_lines=180, target="demo"),
        composition=CompositionSpec(),
        risk_class=["read-only"],
        platforms=platforms,
    )


def test_validate_platform_declarations_accepts_matching_derivation(tmp_path: Path) -> None:
    skill_dir = tmp_path / "demo" / "scripts"
    skill_dir.mkdir(parents=True)
    (skill_dir / "run.py").write_text("import fcntl\n", encoding="utf-8")

    registry = Registry(schema_version=1, skills={"demo": _skill_entry(platforms=["posix"])})
    assert validate_platform_declarations(tmp_path, registry) == []


def test_validate_platform_declarations_reports_mismatch(tmp_path: Path) -> None:
    skill_dir = tmp_path / "demo" / "scripts"
    skill_dir.mkdir(parents=True)
    (skill_dir / "run.py").write_text("import fcntl\n", encoding="utf-8")

    # Explicit override disagrees with what the auto-detector would derive (["posix"]).
    registry = Registry(
        schema_version=1, skills={"demo": _skill_entry(platforms=["posix", "windows"])}
    )
    errors = validate_platform_declarations(tmp_path, registry)
    assert len(errors) == 1
    assert "demo" in errors[0]
    assert "['posix']" in errors[0]
    assert "['posix', 'windows']" in errors[0]


def test_validate_platform_declarations_accepts_derived_default_with_no_evidence(
    tmp_path: Path,
) -> None:
    skill_dir = tmp_path / "demo" / "scripts"
    skill_dir.mkdir(parents=True)
    (skill_dir / "run.py").write_text("import os\n", encoding="utf-8")

    registry = Registry(
        schema_version=1, skills={"demo": _skill_entry(platforms=["posix", "windows"])}
    )
    assert validate_platform_declarations(tmp_path, registry) == []


def _write_mismatched_platform_fixture(tmp_path: Path) -> None:
    """A minimal registry (reusing test_registry.py's own real-CLI fixture helper) whose "solo"
    skill's scripts/ tree has unconditional `import fcntl` (auto-derives ["posix"]), but whose
    skills.yaml declares an explicit `platforms: [posix, windows]` override -- a deliberate
    override-vs-derivation mismatch."""
    _write_minimal_registry_fixture(tmp_path)
    scripts_dir = tmp_path / "solo" / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "run.py").write_text("import fcntl\n", encoding="utf-8")

    skills_yaml = tmp_path / "skills.yaml"
    original = skills_yaml.read_text(encoding="utf-8")
    assert "risk_class: [read-only]" in original
    updated = original.replace(
        "risk_class: [read-only]",
        "risk_class: [read-only]\n    platforms: [posix, windows]",
        1,
    )
    skills_yaml.write_text(updated, encoding="utf-8")


def test_cmd_generate_check_fails_on_platform_declaration_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_mismatched_platform_fixture(tmp_path)
    contracts_path = _write_minimal_composition_contracts(tmp_path)
    monkeypatch.setattr("scripts.registry.composition_contracts.CONTRACTS_PATH", contracts_path)
    monkeypatch.setattr("scripts.registry.cli.ROOT", tmp_path)

    from scripts.registry.cli import cmd_generate

    assert cmd_generate(tmp_path, check_only=True) == 1


def test_cmd_validate_fails_on_platform_declaration_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_mismatched_platform_fixture(tmp_path)
    contracts_path = _write_minimal_composition_contracts(tmp_path)
    monkeypatch.setattr("scripts.registry.composition_contracts.CONTRACTS_PATH", contracts_path)
    monkeypatch.setattr("scripts.registry.cli.ROOT", tmp_path)

    from scripts.registry.cli import cmd_validate

    assert cmd_validate(tmp_path) == 1
    captured = capsys.readouterr()
    assert "solo" in captured.err
    assert "platforms" in captured.err


def test_cmd_generate_check_clean_when_platforms_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sanity counterpart: an unmodified minimal fixture (no scripts/ dir, no explicit
    `platforms:` override) has nothing to drift and must generate --check clean, confirming this
    new validator doesn't introduce false positives on the common, no-override case."""
    _write_minimal_registry_fixture(tmp_path)
    contracts_path = _write_minimal_composition_contracts(tmp_path)
    monkeypatch.setattr("scripts.registry.composition_contracts.CONTRACTS_PATH", contracts_path)
    monkeypatch.setattr("scripts.registry.cli.ROOT", tmp_path)

    from scripts.registry.cli import cmd_generate

    assert cmd_generate(tmp_path, check_only=False) == 0
    assert cmd_generate(tmp_path, check_only=True) == 0
