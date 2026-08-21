from __future__ import annotations

from pathlib import Path

import yaml

from scripts.package_skill import package_skill


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = Path("reference/review-lifecycle-contract.yaml")


def _shared_contract_paths(skill_root: Path) -> list[Path]:
    data = yaml.safe_load((skill_root / CONTRACT).read_text(encoding="utf-8"))
    assert data["shared_contract_path_base"] == "package_or_repository_root"
    return [skill_root / rel for rel in data["shared_contracts"].values()]


def test_shared_contract_paths_resolve_from_source_repository_root():
    source_paths = _shared_contract_paths(ROOT / "loop-task-implementer")
    # Contract paths are logical root-relative paths; source execution resolves
    # them against the repository root, not the reference/ directory.
    data = yaml.safe_load((ROOT / "loop-task-implementer" / CONTRACT).read_text(encoding="utf-8"))
    for rel in data["shared_contracts"].values():
        assert (ROOT / rel).is_file()


def test_shared_contract_paths_resolve_inside_installed_package(tmp_path: Path):
    dest = tmp_path / "loop-task-implementer"
    package_skill(
        skill="loop-task-implementer",
        repo_root=ROOT,
        dest=dest,
        host="test",
    )

    data = yaml.safe_load((dest / CONTRACT).read_text(encoding="utf-8"))
    assert data["shared_contract_path_base"] == "package_or_repository_root"
    for rel in data["shared_contracts"].values():
        path = dest / rel
        assert path.is_file(), f"missing packaged shared contract: {path}"
