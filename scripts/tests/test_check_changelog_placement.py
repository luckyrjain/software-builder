"""Tests for the root-CHANGELOG.md/skill-CHANGELOG.md duplicate-placement warning."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from check_changelog_placement import (  # noqa: E402
    find_likely_misplacements,
    parse_root_changelog_entries,
    parse_skill_changelog_entries,
)


def test_check_changelog_placement_exits_zero_on_repo() -> None:
    # Non-fatal by design (see the script's module docstring): it must never fail CI, even
    # though the real repository currently has confirmed likely-duplicates.
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_changelog_placement.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "warning:" in result.stdout


def test_parse_root_changelog_entries_only_matches_real_skill_sections() -> None:
    changelog = """# Changelog

## Platform

### Cross-cutting thing (2026-01-01)

- touches several skills

## squad-map

### Some change (2026-01-02)

- did a thing

## squad-map

### Another change (2026-01-03)

- did another thing
"""
    entries = parse_root_changelog_entries(changelog, skill_dirs={"squad-map"})

    assert entries == [
        ("squad-map", "2026-01-02", "Some change (2026-01-02)", "\n- did a thing\n"),
        ("squad-map", "2026-01-03", "Another change (2026-01-03)", "\n- did another thing"),
    ]


def test_parse_skill_changelog_entries_extracts_date_from_any_heading_style() -> None:
    changelog = """# Changelog — squad-map

## [1.2.5] — 2026-08-09

### Added

- did a thing
"""
    entries = parse_skill_changelog_entries(changelog)

    assert entries == [
        ("2026-08-09", "[1.2.5] — 2026-08-09", "\n### Added\n\n- did a thing"),
    ]


def test_find_likely_misplacements_flags_near_identical_same_day_entries(tmp_path: Path) -> None:
    (tmp_path / "CHANGELOG.md").write_text(
        """# Changelog

## squad-map

### Safe-output wiring (2026-08-09)

- New "Safe rendered-output boundary" section in reference/squad-mapping.md requires
  newline/heading/pipe/triple-backtick-fence/lone-backtick escaping on Repo/GitLab
  namespace/GitLab squad/Datadog service/Datadog team columns, deliberately not the
  inline-code-span wrap used everywhere else in this repo.
""",
        encoding="utf-8",
    )
    skill_dir = tmp_path / "squad-map"
    skill_dir.mkdir()
    (skill_dir / "CHANGELOG.md").write_text(
        """# Changelog — squad-map

## [1.2.5] — 2026-08-09

### Added

- reference/squad-mapping.md "Safe rendered-output boundary" section: Repo/GitLab
  namespace/GitLab squad/Datadog service/Datadog team all get structural
  newline/heading/pipe/fence/lone-backtick escaping, deliberately not code-span wrapping.
""",
        encoding="utf-8",
    )

    warnings = find_likely_misplacements(tmp_path)

    assert len(warnings) == 1
    assert "squad-map" in warnings[0]
    assert "2026-08-09" in warnings[0]


def test_find_likely_misplacements_ignores_skills_without_their_own_changelog(
    tmp_path: Path,
) -> None:
    (tmp_path / "CHANGELOG.md").write_text(
        """# Changelog

## domain-comprehension

### Some change (2026-01-01)

- some fairly detailed bullet describing the change in full
""",
        encoding="utf-8",
    )
    # No domain-comprehension/CHANGELOG.md on disk -- nothing to compare against, so this
    # skill contributes zero root entries, not a crash or a false warning.
    (tmp_path / "domain-comprehension").mkdir()

    assert find_likely_misplacements(tmp_path) == []


def test_find_likely_misplacements_does_not_flag_unrelated_same_day_entries(
    tmp_path: Path,
) -> None:
    (tmp_path / "CHANGELOG.md").write_text(
        """# Changelog

## squad-map

### Completely unrelated topic (2026-01-01)

- adjusted the timeout retry backoff curve for the outbound webhook client
""",
        encoding="utf-8",
    )
    skill_dir = tmp_path / "squad-map"
    skill_dir.mkdir()
    (skill_dir / "CHANGELOG.md").write_text(
        """# Changelog — squad-map

## [1.0.0] — 2026-01-01

### Added

- renamed the GitLab namespace column header in the output template
""",
        encoding="utf-8",
    )

    assert find_likely_misplacements(tmp_path) == []
