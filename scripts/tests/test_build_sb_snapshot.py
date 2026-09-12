"""Tests for scripts/build_sb_snapshot.py -- the cli/ package's vendoring step."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scripts.build_sb_snapshot import build_snapshot
from scripts.install_engine import install_skill
from scripts.release_info import RELEASE_MANIFEST_NAME, SEMVER_RE, SHA_RE

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.mutates_repository_root
def test_build_snapshot_populates_both_output_directories() -> None:
    code_count, data_count = build_snapshot(ROOT)

    vendored = ROOT / "cli" / "sb" / "_vendored"
    snapshot = ROOT / "cli" / "sb" / "_registry_snapshot"
    assert (vendored / "scripts" / "doctor.py").is_file()
    assert (vendored / "scripts" / "registry" / "cli.py").is_file()
    assert not (vendored / "scripts" / "tests").exists()
    assert (snapshot / "skills.yaml").is_file()
    assert (snapshot / "agent-hosts.yaml").is_file()
    assert (snapshot / "VERSION").is_file()
    assert (snapshot / "skills" / "pr-review" / "SKILL.md").is_file()
    assert code_count > 0
    assert data_count > 0


@pytest.mark.mutates_repository_root
def test_build_snapshot_writes_release_manifest_for_provenance() -> None:
    """The snapshot is shipped inside the sb wheel with neither its own nor an enclosing .git,
    so package_skill.py's _release_provenance() falls back to reading a RELEASE-MANIFEST.json
    at its repo_root (the snapshot dir, once installed) instead of shelling out to git -- without
    this file, `sb install` fails on every real install with "release provenance requires a
    readable Git HEAD"."""
    build_snapshot(ROOT)

    snapshot = ROOT / "cli" / "sb" / "_registry_snapshot"
    manifest_path = snapshot / RELEASE_MANIFEST_NAME
    assert manifest_path.is_file()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert SEMVER_RE.fullmatch(manifest["distribution_version"])
    assert SHA_RE.fullmatch(manifest["source_sha"])


@pytest.mark.mutates_repository_root
def test_real_snapshot_has_the_shared_scripts_test_creator_and_yaml_safety_skills_need(
    tmp_path: Path,
) -> None:
    """Regression test for the bug _DATA_PATHSPECS's three scripts/*.py entries fix:
    package_skill() needs test_creator_write_guard.py + git_paths.py from repo_root/scripts/ for
    every TEST_CREATOR_SKILL_SET skill, and yaml_safety.py for every YAML_SAFETY_SKILL_SET skill
    -- and without those three files in the snapshot, installing any of those 9 skills from the
    shipped `sb` wheel fails outright. Installs one skill from each set via install_skill(), the
    same way test_install_engine_install.py's tests do, but against the REAL snapshot (ROOT),
    not a synthetic minimal fixture -- a synthetic fixture never needed these shared scripts and
    so never caught this bug across 4 prior tasks; only the real snapshot proves it's fixed."""
    build_snapshot(ROOT)
    snapshot = ROOT / "cli" / "sb" / "_registry_snapshot"

    test_creator_outcome = install_skill(
        "unit-test-creator",
        repo_root=snapshot,
        dest_root=tmp_path / "test-creator-dest",
        host_label="cursor",
    )
    assert test_creator_outcome.status == "installed", test_creator_outcome.message
    assert (
        tmp_path
        / "test-creator-dest"
        / "unit-test-creator"
        / "scripts"
        / "test_creator_write_guard.py"
    ).is_file()

    yaml_safety_outcome = install_skill(
        "domain-comprehension",
        repo_root=snapshot,
        dest_root=tmp_path / "yaml-safety-dest",
        host_label="cursor",
    )
    assert yaml_safety_outcome.status == "installed", yaml_safety_outcome.message
    assert (
        tmp_path / "yaml-safety-dest" / "domain-comprehension" / "scripts" / "yaml_safety.py"
    ).is_file()


@pytest.mark.mutates_repository_root
def test_vendored_code_and_snapshot_data_work_together_end_to_end(tmp_path: Path) -> None:
    """The real proof: import the VENDORED copy (not this checkout's own scripts package) and
    run cmd_list/cmd_explain/cmd_doctor/compatibility_resolver.resolve against the snapshot --
    if the glob missed a needed file, this fails with an ImportError or a missing-file error,
    not a silent gap."""
    build_snapshot(ROOT)
    vendored = ROOT / "cli" / "sb" / "_vendored"
    snapshot = ROOT / "cli" / "sb" / "_registry_snapshot"

    # The top-level `from scripts.build_sb_snapshot import build_snapshot` above already cached
    # this checkout's real `scripts` package in sys.modules. Without clearing it here first,
    # `importlib.import_module("scripts.doctor")` below would resolve as a submodule of that
    # already-cached package (using its __path__, not re-searching sys.path) and silently import
    # THIS CHECKOUT's scripts.doctor instead of the vendored copy -- defeating the point of this
    # test. Clear it before inserting the vendored path onto sys.path, not just after.
    #
    # Snapshot the real entries first and restore them verbatim in `finally` -- merely deleting
    # and leaving them absent corrupts every OTHER test that shares this xdist worker process
    # afterward. A later `import scripts.yaml_safety` (e.g. test_yaml_safety.py's
    # test_rejects_excessive_nesting) would otherwise re-import a *second*, distinct module
    # object, while code imported earlier in the same worker (e.g. host_registry.py's
    # `from scripts.yaml_safety import load_unique_yaml_file`, bound at collection time) keeps
    # its reference to the *original* module object -- so a test's `monkeypatch.setattr` on the
    # newly-reimported module silently has no effect on the original one other code still calls.
    # Restoring the exact original objects keeps every name in sys.modules resolving to the one
    # canonical module the rest of the process already holds references to, same as before this
    # test ran. Reproduced directly: this is what made test_yaml_safety.py/
    # test_generic_package_security.py/test_verify_release_bundle_extract.py fail, but only
    # under pytest-xdist with exactly 2 workers (CI's PYTEST_XDIST_WORKERS=2) sharing a worker
    # with this test -- not under -n auto locally, where a different worker count hides it.
    saved_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "scripts" or name.startswith("scripts.")
    }
    for name in saved_modules:
        del sys.modules[name]

    sys.path.insert(0, str(vendored))
    try:
        import importlib

        doctor = importlib.import_module("scripts.doctor")
        registry_cli = importlib.import_module("scripts.registry.cli")
        compatibility_resolver = importlib.import_module("scripts.registry.compatibility_resolver")
        host_registry_module = importlib.import_module("scripts.registry.host_registry")
        load_module = importlib.import_module("scripts.registry.load")

        # Prove the loaded module really came from the vendored tree, not this checkout --
        # this assertion is what would have caught the sys.modules-caching bug above.
        assert Path(doctor.__file__).resolve().is_relative_to(vendored.resolve())

        assert registry_cli.cmd_list(snapshot) == 0
        assert registry_cli.cmd_explain(snapshot, "pr-review") == 0
        assert doctor.cmd_doctor(
            snapshot, skill_filter="pr-review", available=set(), install_roots=[]
        ) in (0, 1)

        host_registry = host_registry_module.parse_host_registry(snapshot / "agent-hosts.yaml")
        registry = load_module.load_registry(snapshot)
        result = compatibility_resolver.resolve(host_registry, registry, "claude", "pr-review")
        assert result.status in {"READY", "DEGRADED", "BLOCKED", "UNVERIFIED", "CONFLICTED"}
    finally:
        sys.path.remove(str(vendored))
        for name in list(sys.modules):
            if name == "scripts" or name.startswith("scripts."):
                del sys.modules[name]
        sys.modules.update(saved_modules)
