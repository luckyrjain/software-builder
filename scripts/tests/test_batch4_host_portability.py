from __future__ import annotations

import shutil
import subprocess
import tarfile
from pathlib import Path, PurePosixPath

import pytest

from scripts.registry import cli as registry_cli
from scripts.registry.generic_package import (
    _is_safe_file,
    _markdown_targets,
    _packaged_bytes,
    _strip_non_runtime_links,
    _tracked_files,
    _validate_output_path,
    build_generic_package,
)
from scripts.registry.host_adapter import (
    HOSTS,
    capability_support,
    validate_host_adapter_identities,
    validate_host_adapter_interface,
)
from scripts.registry.host_portability import (
    HOST_BRANCH_RE,
    _claude_marketplace_errors,
    _plugin_errors,
    _runtime_host_branch_errors,
    validate_host_portability,
)
from scripts.registry.schema import parse_registry

ROOT = Path(__file__).resolve().parents[2]


def test_host_adapter_interface_covers_canonical_hosts() -> None:
    assert HOSTS == {"cursor", "claude", "codex", "chatgpt", "kiro", "generic"}
    assert validate_host_adapter_interface(ROOT) == []
    assert validate_host_adapter_identities(ROOT) == []
    assert capability_support(ROOT, "codex", "scm") == "full"
    assert capability_support(ROOT, "chatgpt", "terminal") == "unsupported"
    with pytest.raises(ValueError):
        capability_support(ROOT, "unknown-host", "scm")
    with pytest.raises(ValueError):
        capability_support(ROOT, "codex", "unknown-capability")


def test_host_adapter_interface_rejects_mixed_type_host_keys(tmp_path: Path) -> None:
    registry_dir = tmp_path / "scripts" / "registry"
    registry_dir.mkdir(parents=True)
    (registry_dir / "host_contracts.yaml").write_text(
        "schema_version: 1\ncapability_families: []\nallowed_support: []\nhosts:\n  1: {}\n  cursor: {}\n",
        encoding="utf-8",
    )

    errors = validate_host_adapter_interface(tmp_path)

    assert errors and errors[0].startswith("error: host adapter interface:")


def test_host_adapter_identity_rejects_extra_parity_keys(tmp_path: Path) -> None:
    registry_dir = tmp_path / "scripts" / "registry"
    registry_dir.mkdir(parents=True)
    shutil.copy2(ROOT / "scripts/registry/host_contracts.yaml", registry_dir / "host_contracts.yaml")
    parity_dir = tmp_path / "evals" / "host-parity"
    parity_dir.mkdir(parents=True)
    expected = ROOT / "evals/host-parity/expected.yaml"
    (parity_dir / "expected.yaml").write_text(
        expected.read_text(encoding="utf-8") + "  1: {adapter: evil}\n",
        encoding="utf-8",
    )

    errors = validate_host_adapter_identities(tmp_path)

    assert any("keys must be strings" in error for error in errors)


def test_host_branch_detector_rejects_directives_not_neutral_host_lists() -> None:
    assert HOST_BRANCH_RE.search("If running on Cursor, load .cursor/rules.")
    assert HOST_BRANCH_RE.search("On Claude Code: use the plugin adapter.")
    assert HOST_BRANCH_RE.search("For Kiro, load the steering file.")
    assert not HOST_BRANCH_RE.search(
        "Read platform-adapters.md for Cursor, ChatGPT/Codex, Claude Code, and Kiro setup.",
    )


def test_runtime_host_branch_detector_scans_workflow_and_reference_docs(tmp_path: Path) -> None:
    skill_root = tmp_path / "sample-skill"
    (skill_root / "workflow").mkdir(parents=True)
    (skill_root / "reference").mkdir()
    (skill_root / "SKILL.md").write_text("# Sample\nHost-neutral core.\n", encoding="utf-8")
    (skill_root / "workflow" / "phase.md").write_text(
        "# Phase\nOn Cursor: use the generated adapter.\n",
        encoding="utf-8",
    )
    (skill_root / "reference" / "notes.md").write_text(
        "# Notes\nSupports Cursor, Claude Code, and Kiro through adapters.\n",
        encoding="utf-8",
    )
    assert _runtime_host_branch_errors(skill_root, "sample-skill") == [
        "error: canonical skill sample-skill contains host-brand conditional logic in workflow/phase.md",
    ]


def test_host_packaging_semantics_validate() -> None:
    assert validate_host_portability(ROOT) == []


def test_host_manifests_fail_closed_on_non_object_json(tmp_path: Path) -> None:
    plugin = tmp_path / "plugin.json"
    plugin.write_text("[]\n", encoding="utf-8")
    assert _plugin_errors(plugin, "TestHost") == ["error: TestHost package manifest must be a JSON object"]

    marketplace_dir = tmp_path / ".claude-plugin"
    marketplace_dir.mkdir()
    (marketplace_dir / "marketplace.json").write_text("[]\n", encoding="utf-8")
    assert _claude_marketplace_errors(tmp_path) == ["error: Claude marketplace manifest must be a JSON object"]


def test_registry_validate_includes_host_portability(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry_cli, "_validate_for_generate", lambda root: [])
    monkeypatch.setattr(registry_cli, "validate_runtime_manifest", lambda root: [])
    monkeypatch.setattr(
        registry_cli,
        "validate_host_portability",
        lambda root: ["error: host-portability-marker"],
    )
    assert registry_cli._validate_all(ROOT) == ["error: host-portability-marker"]


def test_registry_package_generic_command(tmp_path: Path) -> None:
    output = tmp_path / "generic.tar.gz"
    assert registry_cli.main(["package-generic", "--output", str(output)]) == 0
    assert output.is_file()


def test_generic_package_uses_only_git_tracked_files(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    tracked = tmp_path / "tracked.md"
    tracked.write_text("# Tracked\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "tracked.md"], check=True)
    untracked = tmp_path / "id_rsa"
    untracked.write_text("PRIVATE MATERIAL\n", encoding="utf-8")

    tracked_files = _tracked_files(tmp_path.resolve())
    assert tracked.resolve() in tracked_files
    assert untracked.resolve() not in tracked_files


def test_generic_package_rejects_untracked_markdown_targets_and_bad_anchors(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    target = tmp_path / "target.md"
    source.write_text("[target](target.md)\n", encoding="utf-8")
    target.write_text("# Valid heading\n", encoding="utf-8")
    with pytest.raises(ValueError, match="untracked file"):
        _markdown_targets(tmp_path, source, {source})

    source.write_text("[target](target.md#missing)\n", encoding="utf-8")
    with pytest.raises(ValueError, match="dangling markdown anchor"):
        _markdown_targets(tmp_path, source, {source, target})

    source.write_text("[target](target.md#valid-heading)\n", encoding="utf-8")
    assert _markdown_targets(tmp_path, source, {source, target}) == {target}


def test_generic_package_strips_only_non_runtime_changelog_links() -> None:
    source = ROOT / "release-readiness-checker" / "reference" / "gate-policy.md"
    packaged = _packaged_bytes(ROOT, source).decode("utf-8")
    assert "[CHANGELOG.md](../CHANGELOG.md)" not in packaged
    assert "CHANGELOG.md" in packaged
    assert "[phase-0.md](../../pr-review/workflow/phase-0.md)" in packaged

    sample = "[history](CHANGELOG.md)\n![image](CHANGELOG.md)\n```md\n[example](CHANGELOG.md)\n```\n"
    rewritten = _strip_non_runtime_links(sample)
    assert rewritten.startswith("history\n")
    assert "![image](CHANGELOG.md)" in rewritten
    assert "[example](CHANGELOG.md)" in rewritten


def test_generic_package_refuses_ci_sensitive_and_self_including_paths(tmp_path: Path) -> None:
    github_file = tmp_path / ".github" / "workflow.yml"
    github_file.parent.mkdir()
    github_file.write_text("name: test\n", encoding="utf-8")
    assert _is_safe_file(tmp_path, github_file) is False

    tests_file = tmp_path / "skill" / "tests" / "fixture.yaml"
    tests_file.parent.mkdir(parents=True)
    tests_file.write_text("payload: adversarial\n", encoding="utf-8")
    assert _is_safe_file(tmp_path, tests_file) is False

    secret = tmp_path / ".env.local"
    secret.write_text("TOKEN=example\n", encoding="utf-8")
    with pytest.raises(ValueError, match="potentially sensitive"):
        _is_safe_file(tmp_path, secret)

    mixed_case_secret = tmp_path / "Credentials.JSON"
    mixed_case_secret.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="potentially sensitive"):
        _is_safe_file(tmp_path, mixed_case_secret)

    mixed_case_env = tmp_path / ".ENV.production"
    mixed_case_env.write_text("TOKEN=example\n", encoding="utf-8")
    with pytest.raises(ValueError, match="potentially sensitive"):
        _is_safe_file(tmp_path, mixed_case_env)

    mixed_case_changelog = tmp_path / "Changelog.MD"
    mixed_case_changelog.write_text("history\n", encoding="utf-8")
    assert _is_safe_file(tmp_path, mixed_case_changelog) is False

    with pytest.raises(ValueError, match="output inside repository"):
        _validate_output_path(tmp_path, tmp_path / "skill" / "bundle.tar.gz")
    with pytest.raises(ValueError, match="output inside repository"):
        _validate_output_path(tmp_path, tmp_path / ".git" / "bundle.tar.gz")
    _validate_output_path(tmp_path, tmp_path / "dist" / "bundle.tar.gz")
    _validate_output_path(tmp_path, tmp_path.parent / "outside.tar.gz")


def test_generic_package_is_deterministic_complete_and_link_safe(tmp_path: Path) -> None:
    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"
    build_generic_package(ROOT, first)
    build_generic_package(ROOT, second)
    assert first.read_bytes() == second.read_bytes()

    registry = parse_registry(ROOT / "skills.yaml")
    extract_root = tmp_path / "extract"
    with tarfile.open(first, "r:gz") as archive:
        members = archive.getmembers()
        names = {member.name for member in members}
        assert all(member.isfile() for member in members)
        assert all(not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts for name in names)
        archive.extractall(extract_root, filter="data")
    for skill_id, entry in registry.skills.items():
        assert f"software-builder/{entry.path}/SKILL.md" in names, skill_id
    assert "software-builder/README.md" in names
    assert "software-builder/skills.yaml" in names
    assert "software-builder/docs/skill-framework/shared/skill-routing.md" in names
    assert "software-builder/docs/skill-framework/shared/runtime-contract.md" in names
    assert not any("/.git/" in f"/{name}/" or "/.github/" in f"/{name}/" for name in names)
    assert not any("/dist/" in f"/{name}/" for name in names)
    assert not any("/tests/" in f"/{name}/" for name in names)
    assert not any("__pycache__" in name or name.endswith(".pyc") for name in names)
    assert not any(PurePosixPath(name).name.lower() == "changelog.md" for name in names)

    packaged_root = extract_root / "software-builder"
    markdown_files = sorted(str(path) for path in packaged_root.rglob("*.md"))
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/lint-dangling-md-links.sh"), *markdown_files],
        cwd=packaged_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
