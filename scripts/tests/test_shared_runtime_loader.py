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


def test_a_source_checkout_is_found_by_walking_up_past_an_extra_nesting_level(
    loader, tmp_path: Path
) -> None:
    """Once skills move to skills/<name>/, `skill_root.parent` (here `skills/`) no longer IS repo
    root -- the walk-up must climb past it to find the ancestor that actually proves itself with
    SOURCE_CHECKOUT_MARKERS, simulating the post-migration `<repo>/skills/some-skill` layout."""
    repo_root = tmp_path
    skill = repo_root / "skills" / "some-skill"
    skill.mkdir(parents=True)
    source = repo_root / "docs/skill-framework/shared/thing.py"
    source.parent.mkdir(parents=True)
    source.write_text("VALUE = 3\n", encoding="utf-8")

    # The immediate parent (`skills/`) does not itself hold the markers -- proving this case
    # actually needs the walk-up, not just a layout where a single parent hop would still work.
    assert not (skill.parent / "skills.yaml").is_file()

    (repo_root / "skills.yaml").write_text("schema_version: 1\n", encoding="utf-8")
    (repo_root / "scripts").mkdir()
    (repo_root / "scripts/package_skill.py").write_text("# marker\n", encoding="utf-8")

    assert loader.shared_runtime_path(skill, "thing") == source
    assert loader.load_shared_runtime(skill, "thing").VALUE == 3


def test_a_source_checkout_is_still_refused_when_no_ancestor_proves_itself(
    loader, tmp_path: Path
) -> None:
    """Nesting a skill several levels deep with no ancestor ever proving itself via
    SOURCE_CHECKOUT_MARKERS must still fail with the same error the single-parent-hop code raised
    -- the walk-up only changes what can succeed, never weakens the refusal."""
    skill = tmp_path / "some-skill"
    skill.mkdir()
    # A source file exists at the immediate parent, but no ancestor ever gets the markers, so the
    # walk-up must exhaust its bound and still refuse -- proving unproven directories are never
    # trusted regardless of how many levels are searched.
    source = tmp_path / "docs/skill-framework/shared/thing.py"
    source.parent.mkdir(parents=True)
    source.write_text("VALUE = 4\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="verified source-checkout runtime"):
        loader.shared_runtime_path(skill, "thing")


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


def _exec_generated_bootstrap(script_path: Path):
    """Write scripts/registry/generate_shared_runtime_bootstrap.py's generated bootstrap block
    into `script_path` (with the minimal imports/`_RUNTIME_DESCRIPTION` every one of the 8 real
    target files supplies around it) and exec it, returning the resulting module. This exercises
    the exact text `make generate` projects into those 8 files -- not a reimplementation of it."""
    from scripts.registry.generate_shared_runtime_bootstrap import (
        render_shared_runtime_bootstrap_block,
    )

    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(
        "from __future__ import annotations\n"
        "import importlib.util\n"
        "from pathlib import Path\n"
        "from types import ModuleType\n"
        "\n"
        "_RUNTIME_DESCRIPTION = 'test runtime'\n"
        f"{render_shared_runtime_bootstrap_block()}",
        encoding="utf-8",
    )
    spec = importlib.util.spec_from_file_location("generated_bootstrap_under_test", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_bootstrap_finds_the_loader_at_todays_flat_layout(tmp_path: Path) -> None:
    """Before the skills/ migration, a skill's directory sits directly at repo root, so
    `SKILL_ROOT.parent` already IS the loader's ancestor -- the walk-up fallback must keep
    resolving to the identical location the old hardcoded `SKILL_ROOT.parent / ...` did, not just
    a plausible-looking one."""
    loader_dir = tmp_path / "docs/skill-framework/shared"
    loader_dir.mkdir(parents=True)
    (loader_dir / "shared_runtime_loader.py").write_text("MARKER = 'flat-layout'\n", encoding="utf-8")

    script_path = tmp_path / "some-skill/scripts/foo.py"
    module = _exec_generated_bootstrap(script_path)

    assert module.SKILL_ROOT.parent / "docs/skill-framework/shared/shared_runtime_loader.py" == (
        loader_dir / "shared_runtime_loader.py"
    )
    loaded = module._shared_runtime_loader()
    assert loaded.MARKER == "flat-layout"


def test_generated_bootstrap_walks_up_from_a_nested_skill_root(tmp_path: Path) -> None:
    """Once skills move to skills/<name>/, `SKILL_ROOT.parent` resolves to `skills/`, not repo
    root -- the walk-up must still find the loader by climbing past it, simulating the
    `<tmp>/skills/some-skill/scripts/foo.py` layout the migration produces."""
    loader_dir = tmp_path / "docs/skill-framework/shared"
    loader_dir.mkdir(parents=True)
    (loader_dir / "shared_runtime_loader.py").write_text("MARKER = 'nested-layout'\n", encoding="utf-8")

    script_path = tmp_path / "skills/some-skill/scripts/foo.py"
    module = _exec_generated_bootstrap(script_path)

    # SKILL_ROOT.parent alone (the old, non-walking computation) would land on `skills/`, which
    # does not hold the loader -- proving this case actually needs the walk-up, not just a layout
    # where the old code would have accidentally still worked.
    assert not (module.SKILL_ROOT.parent / "docs/skill-framework/shared/shared_runtime_loader.py").is_file()

    loaded = module._shared_runtime_loader()
    assert loaded.MARKER == "nested-layout"
