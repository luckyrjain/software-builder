"""Tests for scripts/install_engine.py's platform-support install gate (gap-backlog F2).

Reuses test_install_engine_install.py's own `_minimal_repo` fixture builder (a real git checkout
package_skill() can actually package) rather than duplicating it, and only adds what this gate
needs on top: a `platforms:` override and/or a `scripts/` tree for the auto-detector to read.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from scripts.install_engine import _current_platform_label, install_skill
from scripts.tests.test_install_engine_install import _minimal_repo


def _add_platforms_override(repo: Path, *, skill_id: str, platforms: str) -> None:
    skills_yaml = repo / "skills.yaml"
    original = skills_yaml.read_text(encoding="utf-8")
    marker = "risk_class: [read-only]"
    assert marker in original
    updated = original.replace(marker, f"{marker}\n    platforms: {platforms}", 1)
    skills_yaml.write_text(updated, encoding="utf-8")


def test_current_platform_label_matches_sys_platform_translation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    assert _current_platform_label() == "windows"
    monkeypatch.setattr(sys, "platform", "linux")
    assert _current_platform_label() == "posix"
    monkeypatch.setattr(sys, "platform", "darwin")
    assert _current_platform_label() == "posix"


def test_install_refused_when_declared_platforms_exclude_this_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _minimal_repo(tmp_path)
    _add_platforms_override(repo, skill_id="demo-skill", platforms="[windows]")
    monkeypatch.setattr(sys, "platform", "linux")  # this process's "posix"
    dest_root = tmp_path / "dest"

    outcome = install_skill("demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor")

    assert outcome.status == "failed"
    assert "does not include this platform" in outcome.message
    assert not (dest_root / "demo-skill").exists()


def test_install_proceeds_when_declared_platforms_include_this_one(tmp_path: Path) -> None:
    """Deliberately does not simulate `sys.platform` -- this test proceeds through the full
    install (staging, locking, packaging), which install_engine.py's own OS-specific branches
    (msvcrt on real Windows, fcntl elsewhere -- bound once at module import time, from the real
    `sys.platform`) require actually matching the real, current OS to exercise safely. The
    platform-gate hook itself is exercised against the real current platform's own label."""
    repo = _minimal_repo(tmp_path)
    _add_platforms_override(repo, skill_id="demo-skill", platforms=f"[{_current_platform_label()}]")
    dest_root = tmp_path / "dest"

    outcome = install_skill("demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor")

    assert outcome.status == "installed"


def test_allow_unsupported_platform_proceeds_with_a_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Declares the *other* platform (never the real current one) so the gate's refusal-then-
    override path is genuinely exercised, while the install itself still proceeds on the real,
    current OS -- see test_install_proceeds_when_declared_platforms_include_this_one for why this
    suite never simulates `sys.platform` around a full install."""
    other_platform = "windows" if _current_platform_label() == "posix" else "posix"
    repo = _minimal_repo(tmp_path)
    _add_platforms_override(repo, skill_id="demo-skill", platforms=f"[{other_platform}]")
    dest_root = tmp_path / "dest"

    outcome = install_skill(
        "demo-skill",
        repo_root=repo,
        dest_root=dest_root,
        host_label="cursor",
        allow_unsupported_platform=True,
    )

    assert outcome.status == "installed"
    captured = capsys.readouterr()
    assert "does not include this platform" in captured.err
    assert "--allow-unsupported-platform" in captured.err


def test_dry_run_still_refuses_on_platform_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The hook point is before the dry-run short-circuit, so a dry-run preview accurately
    reflects a refusal rather than reporting "would install" for a skill that would actually be
    refused."""
    repo = _minimal_repo(tmp_path)
    _add_platforms_override(repo, skill_id="demo-skill", platforms="[windows]")
    monkeypatch.setattr(sys, "platform", "linux")
    dest_root = tmp_path / "dest"

    outcome = install_skill(
        "demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor", dry_run=True
    )

    assert outcome.status == "failed"
    assert "does not include this platform" in outcome.message
    assert not (dest_root / "demo-skill").exists()


def test_dry_run_still_reports_would_install_when_platform_supported(tmp_path: Path) -> None:
    repo = _minimal_repo(tmp_path)
    _add_platforms_override(repo, skill_id="demo-skill", platforms="[posix, windows]")
    dest_root = tmp_path / "dest"

    outcome = install_skill(
        "demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor", dry_run=True
    )

    assert outcome.status == "dry_run"


def test_no_explicit_platforms_falls_back_to_derivation(tmp_path: Path) -> None:
    """No `platforms:` override at all: the gate reads the same auto-derived value schema.py's
    parse would compute -- a skill with no scripts/ tree derives the permissive default, so it
    installs regardless of this platform. Runs on the real, current platform (not a simulated
    one) since this exercises the full install, including the OS-specific locking code the
    other tests here deliberately short-circuit past by refusing before reaching it."""
    repo = _minimal_repo(tmp_path)
    dest_root = tmp_path / "dest"

    outcome = install_skill("demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor")

    assert outcome.status == "installed"


def test_no_explicit_platforms_with_posix_only_scripts_refuses_on_windows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _minimal_repo(tmp_path)
    scripts_dir = repo / "demo-skill" / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "lock.py").write_text("import fcntl\n", encoding="utf-8")
    monkeypatch.setattr(sys, "platform", "win32")
    dest_root = tmp_path / "dest"

    outcome = install_skill("demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor")

    assert outcome.status == "failed"
    assert "does not include this platform" in outcome.message


def test_every_read_install_generate_validate_agree_on_platforms(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every-read consistency: install_skill()'s own platform read, and a direct parse_registry()
    call (the same function make generate/make validate go through), must resolve the identical
    platforms value for the same on-disk content."""
    from scripts.registry.schema import clear_registry_cache, parse_registry

    repo = _minimal_repo(tmp_path)
    scripts_dir = repo / "demo-skill" / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "lock.py").write_text("import fcntl\n", encoding="utf-8")
    monkeypatch.setattr(sys, "platform", "win32")
    dest_root = tmp_path / "dest"

    clear_registry_cache()
    via_registry = parse_registry(repo / "skills.yaml").skills["demo-skill"].platforms
    outcome = install_skill("demo-skill", repo_root=repo, dest_root=dest_root, host_label="cursor")

    assert via_registry == ["posix"]
    assert outcome.status == "failed"
    assert "does not include this platform" in outcome.message
