"""Tests for scripts/registry/schema.py's `platforms` field resolution (gap-backlog F2).

Covers the schema-validation precedent (`_parse_risk_class`'s exact pattern, extended for
`platforms`) and the non-recursive path-computation fix -- the concrete regression test for the
circular-recursion trap round 3 found: `_parse_skill_entry` must compute a skill's on-disk
directory independently, never by calling `package_skill._resolve_source_dir` (which calls
`parse_registry()` and would recurse straight back into this very per-skill loop).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.registry.schema import RegistryParseError, clear_registry_cache, parse_registry

_HOSTS_BLOCK = "cursor: {discovery: rule}\n      claude: {install: true}\n      kiro: {discovery: manual}"


def _write_minimal_registry(
    tmp_path: Path,
    *,
    platforms_line: str = "",
    scripts_source: str | None = None,
) -> None:
    skill_dir = tmp_path / "solo"
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: solo\nskill_version: 1.0\ndescription: 'Keywords: solo skill.'\n---\n",
        encoding="utf-8",
    )
    if scripts_source is not None:
        (scripts_dir / "run.py").write_text(scripts_source, encoding="utf-8")
    (tmp_path / "skills.yaml").write_text(
        f"""
schema_version: 1
skills:
  solo:
    path: solo
    category: testing
    invocation: ambient
    hosts:
      {_HOSTS_BLOCK}
    install: {{requires: []}}
    capabilities:
      required: [host.repository.read]
    lint: {{skill_md_max_lines: 180, target: solo}}
    risk_class: [read-only]
{platforms_line}
""",
        encoding="utf-8",
    )


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_registry_cache()
    yield
    clear_registry_cache()


def test_platforms_absent_derives_from_scripts_tree(tmp_path: Path) -> None:
    _write_minimal_registry(tmp_path, scripts_source="import fcntl\n")
    registry = parse_registry(tmp_path / "skills.yaml")
    assert registry.skills["solo"].platforms == ["posix"]


def test_platforms_absent_with_no_posix_evidence_defaults_permissive(tmp_path: Path) -> None:
    _write_minimal_registry(tmp_path, scripts_source="import os\n")
    registry = parse_registry(tmp_path / "skills.yaml")
    assert registry.skills["solo"].platforms == ["posix", "windows"]


def test_platforms_explicit_override_accepted(tmp_path: Path) -> None:
    _write_minimal_registry(tmp_path, platforms_line="    platforms: [posix]")
    registry = parse_registry(tmp_path / "skills.yaml")
    assert registry.skills["solo"].platforms == ["posix"]


def test_platforms_explicit_override_both_values(tmp_path: Path) -> None:
    _write_minimal_registry(tmp_path, platforms_line="    platforms: [posix, windows]")
    registry = parse_registry(tmp_path / "skills.yaml")
    assert registry.skills["solo"].platforms == ["posix", "windows"]


def test_platforms_explicit_override_rejects_unknown_value(tmp_path: Path) -> None:
    _write_minimal_registry(tmp_path, platforms_line="    platforms: [posix, plan9]")
    with pytest.raises(RegistryParseError, match="platforms invalid values: plan9"):
        parse_registry(tmp_path / "skills.yaml")


def test_platforms_explicit_override_rejects_empty_list(tmp_path: Path) -> None:
    _write_minimal_registry(tmp_path, platforms_line="    platforms: []")
    with pytest.raises(RegistryParseError, match="platforms must be a non-empty list"):
        parse_registry(tmp_path / "skills.yaml")


def test_platforms_resolution_never_raises_on_override_derivation_mismatch(tmp_path: Path) -> None:
    """An explicit override that disagrees with what the auto-detector would derive is data, not
    an exception -- `SkillEntry.platforms` resolution itself (schema.py) never raises on this;
    only `validate_platform_declarations` (crosscheck.py, a separate validation-layer step) does.
    This mismatch (override says windows-only-shaped value while the script imports fcntl) must
    parse cleanly here."""
    _write_minimal_registry(
        tmp_path, platforms_line="    platforms: [posix, windows]", scripts_source="import fcntl\n"
    )
    registry = parse_registry(tmp_path / "skills.yaml")
    assert registry.skills["solo"].platforms == ["posix", "windows"]


def test_parse_skill_entry_does_not_call_resolve_source_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The concrete regression test for round 3's circular-recursion-trap finding:
    `package_skill._resolve_source_dir` calls `parse_registry()`, so calling it from inside
    `_parse_skill_entry` (which runs *inside* `parse_registry()`'s own per-skill loop) would
    recurse straight back into this very call, either raising RecursionError or becoming
    pathologically expensive on every registry read. Patches it to raise if ever called, so a
    regression that "helpfully" simplifies the local path computation back into a call to that
    function fails this test loudly instead of silently reintroducing the trap."""
    import scripts.package_skill as package_skill_module

    def _must_not_be_called(*args: object, **kwargs: object) -> Path:
        raise AssertionError(
            "schema.py._parse_skill_entry must not call package_skill._resolve_source_dir "
            "(would recurse via parse_registry())"
        )

    monkeypatch.setattr(package_skill_module, "_resolve_source_dir", _must_not_be_called)

    _write_minimal_registry(tmp_path, scripts_source="import fcntl\n")
    registry = parse_registry(tmp_path / "skills.yaml")
    assert registry.skills["solo"].platforms == ["posix"]


def test_platforms_path_resolution_uses_the_declared_path_not_the_skill_id(tmp_path: Path) -> None:
    """The on-disk directory `platforms` is derived from must follow the same `root /
    entry.path` (falling back to `root / skill_id`) formula as `paths.skill_dir()` -- not just
    `root / skill_id` unconditionally."""
    (tmp_path / "actual-dir" / "scripts").mkdir(parents=True)
    (tmp_path / "actual-dir" / "scripts" / "run.py").write_text("import fcntl\n", encoding="utf-8")
    (tmp_path / "actual-dir" / "SKILL.md").write_text(
        "---\nname: aliased\nskill_version: 1.0\ndescription: 'Keywords: aliased skill.'\n---\n",
        encoding="utf-8",
    )
    (tmp_path / "skills.yaml").write_text(
        f"""
schema_version: 1
skills:
  aliased:
    path: actual-dir
    category: testing
    invocation: ambient
    hosts:
      {_HOSTS_BLOCK}
    install: {{requires: []}}
    capabilities:
      required: [host.repository.read]
    lint: {{skill_md_max_lines: 180, target: aliased}}
    risk_class: [read-only]
""",
        encoding="utf-8",
    )
    registry = parse_registry(tmp_path / "skills.yaml")
    assert registry.skills["aliased"].platforms == ["posix"]


def test_platforms_falls_back_to_skill_id_when_path_is_absent(tmp_path: Path) -> None:
    (tmp_path / "solo" / "scripts").mkdir(parents=True)
    (tmp_path / "solo" / "scripts" / "run.py").write_text("import fcntl\n", encoding="utf-8")
    (tmp_path / "solo" / "SKILL.md").write_text(
        "---\nname: solo\nskill_version: 1.0\ndescription: 'Keywords: solo skill.'\n---\n",
        encoding="utf-8",
    )
    (tmp_path / "skills.yaml").write_text(
        f"""
schema_version: 1
skills:
  solo:
    category: testing
    invocation: ambient
    hosts:
      {_HOSTS_BLOCK}
    install: {{requires: []}}
    capabilities:
      required: [host.repository.read]
    lint: {{skill_md_max_lines: 180, target: solo}}
    risk_class: [read-only]
""",
        encoding="utf-8",
    )
    registry = parse_registry(tmp_path / "skills.yaml")
    assert registry.skills["solo"].platforms == ["posix"]


def test_every_read_resolves_the_same_platforms_value(tmp_path: Path) -> None:
    """Every-read consistency: two independent parse_registry() calls against the same on-disk
    content (simulating separate make generate / make validate / install_skill() reads, each in
    its own process in real usage) resolve the same platforms value."""
    _write_minimal_registry(tmp_path, scripts_source="import fcntl\n")
    first = parse_registry(tmp_path / "skills.yaml").skills["solo"].platforms
    clear_registry_cache()
    second = parse_registry(tmp_path / "skills.yaml").skills["solo"].platforms
    assert first == second == ["posix"]
