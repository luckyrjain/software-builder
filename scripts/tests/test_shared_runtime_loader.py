"""One containment policy for loading executable modules out of the vendored shared tree.

docs/skill-framework/shared/shared_runtime_loader.py replaces the two per-skill resolvers that had
already diverged: loop-task-implementer refused to walk out of an installed package,
pr-review did not. These tests pin the policy and the packaging rule that makes it reachable.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from scripts.package_skill import package_skill


ROOT = Path(__file__).resolve().parents[2]
LOADER = ROOT / "docs/skill-framework/shared/shared_runtime_loader.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def loader():
    return _load(LOADER, "shared_runtime_loader_under_test")


def test_a_vendored_copy_always_wins(loader, tmp_path: Path) -> None:
    skill = tmp_path / "skill"
    vendored = skill / "docs/skill-framework/shared/thing.py"
    vendored.parent.mkdir(parents=True)
    vendored.write_text("VALUE = 1\n", encoding="utf-8")

    assert loader.shared_runtime_path(skill, "thing") == vendored
    assert loader.load_shared_runtime(skill, "thing").VALUE == 1


def test_an_installed_package_never_looks_outside_itself(loader, tmp_path: Path) -> None:
    skill = tmp_path / "skill"
    skill.mkdir()
    (skill / ".software-builder-manifest.json").write_text('{"skill": "skill"}', encoding="utf-8")
    # A parent that looks exactly like a source checkout must still not be consulted.
    (tmp_path / "skills.yaml").write_text("schema_version: 1\n", encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/package_skill.py").write_text("# marker\n", encoding="utf-8")
    hostile = tmp_path / "docs/skill-framework/shared/thing.py"
    hostile.parent.mkdir(parents=True)
    hostile.write_text("raise RuntimeError('must not load parent runtime')\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="unable to load packaged"):
        loader.shared_runtime_path(skill, "thing")


def test_a_source_checkout_must_prove_itself_with_repository_markers(loader, tmp_path: Path) -> None:
    skill = tmp_path / "skill"
    skill.mkdir()
    source = tmp_path / "docs/skill-framework/shared/thing.py"
    source.parent.mkdir(parents=True)
    source.write_text("VALUE = 2\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="verified source-checkout runtime"):
        loader.shared_runtime_path(skill, "thing")

    (tmp_path / "skills.yaml").write_text("schema_version: 1\n", encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/package_skill.py").write_text("# marker\n", encoding="utf-8")
    assert loader.shared_runtime_path(skill, "thing") == source


def test_module_names_are_names_not_paths(loader, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="invalid shared runtime module name"):
        loader.shared_runtime_path(tmp_path, "../../etc/passwd")


def test_packaged_pr_review_validator_refuses_to_walk_out_of_its_package(tmp_path: Path):
    """pr-review's loader used to try SKILL_ROOT.parent unconditionally: for an installed package
    at ~/.claude/skills/pr-review that is the shared skills root, a directory any other installed
    skill or the user's own tooling can write to. Both skills now share one containment policy."""
    dest = tmp_path / "pr-review"
    package_skill(skill="pr-review", repo_root=ROOT, dest=dest, host="test")

    runtime = dest / "docs/skill-framework/shared/review_contract_runtime.py"
    loader = dest / "scripts/shared_runtime_loader.py"
    assert runtime.is_file()
    assert loader.is_file(), "the loader must be vendored beside the skill's own scripts"

    validator = _load(dest / "scripts/validate_review_coverage.py", "installed_review_coverage")
    assert Path(validator._load_shared_validator().__file__).resolve() == runtime.resolve()

    runtime.unlink()

    # A parent that looks like a source checkout must still not become executable policy for a
    # package whose manifest proves it should be self-contained.
    (tmp_path / "skills.yaml").write_text("schema_version: 1\n", encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/package_skill.py").write_text("# marker\n", encoding="utf-8")
    hostile = tmp_path / "docs/skill-framework/shared/review_contract_runtime.py"
    hostile.parent.mkdir(parents=True)
    hostile.write_text("raise RuntimeError('must not load parent runtime')\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="packaged shared review runtime"):
        validator._load_shared_validator()


def test_vendoring_follows_the_scripts_not_the_markdown_links(tmp_path: Path):
    """Vendoring used to be inferred from markdown links alone, so trimming a SKILL.md link could
    silently stop shipping a runtime the skill's scripts still execute."""
    from scripts.package_skill import skill_loads_shared_runtime

    skill = tmp_path / "some-skill"
    (skill / "scripts").mkdir(parents=True)
    (skill / "SKILL.md").write_text("# no framework links\n", encoding="utf-8")
    assert not skill_loads_shared_runtime(skill)

    (skill / "scripts" / "check.py").write_text(
        "loader.load_shared_runtime(SKILL_ROOT, 'review_contract_runtime')\n", encoding="utf-8"
    )
    assert skill_loads_shared_runtime(skill)


def test_packaged_pr_review_ships_the_framework_tree_its_scripts_execute(tmp_path: Path):
    from scripts.package_skill import skill_loads_shared_runtime

    dest = tmp_path / "pr-review"
    package_skill(skill="pr-review", repo_root=ROOT, dest=dest, host="test")

    assert skill_loads_shared_runtime(dest)
    assert (dest / "docs/skill-framework/shared/review_contract_runtime.py").is_file()
    assert (dest / "scripts/shared_runtime_loader.py").is_file()
