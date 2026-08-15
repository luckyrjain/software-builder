from __future__ import annotations

import subprocess
import tarfile
from pathlib import Path, PurePosixPath

import pytest

from scripts.registry import cli as registry_cli
from scripts.registry.generic_package import _is_safe_file, _validate_output_path, build_generic_package
from scripts.registry.host_adapter import HOSTS, capability_support, validate_host_adapter_interface
from scripts.registry.host_portability import validate_host_portability
from scripts.registry.schema import parse_registry

ROOT = Path(__file__).resolve().parents[2]


def test_host_adapter_interface_covers_canonical_hosts() -> None:
    assert HOSTS == {"cursor", "claude", "codex", "chatgpt", "kiro", "generic"}
    assert validate_host_adapter_interface(ROOT) == []
    assert capability_support(ROOT, "codex", "scm") == "full"
    assert capability_support(ROOT, "chatgpt", "terminal") == "unsupported"
    with pytest.raises(ValueError):
        capability_support(ROOT, "unknown-host", "scm")
    with pytest.raises(ValueError):
        capability_support(ROOT, "codex", "unknown-capability")


def test_host_packaging_semantics_validate() -> None:
    assert validate_host_portability(ROOT) == []


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


def test_generic_package_refuses_ci_sensitive_and_self_including_paths(tmp_path: Path) -> None:
    github_file = tmp_path / ".github" / "workflow.yml"
    github_file.parent.mkdir()
    github_file.write_text("name: test\n", encoding="utf-8")
    assert _is_safe_file(tmp_path, github_file) is False

    secret = tmp_path / ".env.local"
    secret.write_text("TOKEN=example\n", encoding="utf-8")
    with pytest.raises(ValueError, match="potentially sensitive"):
        _is_safe_file(tmp_path, secret)

    with pytest.raises(ValueError, match="output inside repository"):
        _validate_output_path(tmp_path, tmp_path / "skill" / "bundle.tar.gz")
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
    assert "software-builder/skills.yaml" in names
    assert "software-builder/docs/skill-framework/shared/skill-routing.md" in names
    assert "software-builder/docs/skill-framework/shared/runtime-contract.md" in names
    assert not any("/.git/" in f"/{name}/" or "/.github/" in f"/{name}/" for name in names)
    assert not any("/dist/" in f"/{name}/" for name in names)
    assert not any("__pycache__" in name or name.endswith(".pyc") for name in names)

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
