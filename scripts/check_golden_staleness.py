#!/usr/bin/env python3
"""Warn when a skill's SKILL.md changed after its golden fixtures were last refreshed.

Tier-3 golden fixtures (scripts/evals/golden.py) replay a *static* `recorded_output` in
CI -- there is no live LLM call to notice that a fixture no longer matches what the skill
actually does. scripts/evals/golden_refresh.py stamps `refresh_meta.last_refreshed_at`
whenever a maintainer deliberately refreshes a fixture, but docs/evals/GOLDEN-REFRESH.md
is explicit that "CI ignores refresh_meta -- it is provenance for maintainers only." That
leaves a gap: nothing ever compares that provenance against the thing it is provenance
*for* -- whether the skill's own SKILL.md has changed since.

This script closes that gap, advisory-only: for every golden fixture, it compares
`refresh_meta.last_refreshed_at` against the git commit date of its skill's SKILL.md
(`git log -1 --format=%cI -- <skill>/SKILL.md`). A SKILL.md commit landing after a
fixture's last refresh doesn't prove the fixture is wrong -- the change might be
unrelated to what the fixture asserts -- but it is exactly the situation a maintainer
would want a nudge to double-check. Per ADR-0003/0004 (this repo deliberately never
gates on live-model behavior), this is a WARNING only: it always exits 0 and never
fails `make lint-static` or CI.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evals.golden import load_golden_fixtures
from scripts.registry.load import load_registry
from scripts.yaml_safety import load_unique_yaml_file

REFRESH_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class StaleGoldenFixture(NamedTuple):
    skill: str
    case_id: str
    fixture_path: Path
    last_refreshed_at: str
    skill_md_last_commit_at: str


def _skill_md_last_commit_at(root: Path, skill_path: str) -> datetime | None:
    """The commit datetime of `<skill_path>/SKILL.md`'s most recent change, or None.

    None covers both "git isn't available / this isn't a git checkout" and "SKILL.md
    has no commits yet" (a brand-new, uncommitted skill) -- either way there is nothing
    to compare a fixture's refresh timestamp against, so the caller should skip it
    rather than report a false staleness warning.
    """
    relative_path = f"{skill_path}/SKILL.md"
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "log", "-1", "--format=%cI", "--", relative_path],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    commit_date = completed.stdout.strip()
    if not commit_date:
        return None
    try:
        return datetime.fromisoformat(commit_date)
    except ValueError:
        return None


def _parse_refresh_timestamp(value: object) -> datetime | None:
    """Parse a `refresh_meta.last_refreshed_at` value stamped by golden_refresh.py.

    Returns None for anything that isn't a validly-stamped UTC timestamp: missing
    refresh_meta, a fixture that has never been refreshed, or a hand-edited/malformed
    value. That is deliberately a distinct case from "predates the SKILL.md commit" --
    a fixture that was never refreshed through the documented workflow has no
    provenance to compare, so find_stale_golden_fixtures skips it rather than
    reporting a comparison it can't actually make.
    """
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.strptime(value, REFRESH_TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def find_stale_golden_fixtures(root: Path = ROOT) -> list[StaleGoldenFixture]:
    """Every golden fixture whose recorded last refresh predates its skill's SKILL.md.

    Only fixtures that carry a valid `refresh_meta.last_refreshed_at` are considered --
    a fixture with no refresh provenance at all is a separate gap (nothing has ever run
    golden_refresh.py against it) from the one this check targets (a *stamped* refresh
    that a later SKILL.md edit has since overtaken).
    """
    registry = load_registry(root)
    golden_cases = load_golden_fixtures(root / "evals" / "golden")

    skill_md_commit_cache: dict[str, datetime | None] = {}
    stale: list[StaleGoldenFixture] = []
    for case in golden_cases:
        raw = load_unique_yaml_file(case.path)
        refresh_meta = raw.get("refresh_meta") if isinstance(raw, dict) else None
        last_refreshed_raw = refresh_meta.get("last_refreshed_at") if isinstance(refresh_meta, dict) else None
        last_refreshed_at = _parse_refresh_timestamp(last_refreshed_raw)
        if last_refreshed_at is None:
            continue

        entry = registry.skills.get(case.skill)
        skill_path = entry.path if entry is not None else case.skill
        if skill_path not in skill_md_commit_cache:
            skill_md_commit_cache[skill_path] = _skill_md_last_commit_at(root, skill_path)
        skill_md_commit_at = skill_md_commit_cache[skill_path]
        if skill_md_commit_at is None:
            continue

        if last_refreshed_at < skill_md_commit_at:
            stale.append(
                StaleGoldenFixture(
                    skill=case.skill,
                    case_id=case.case_id,
                    fixture_path=case.path,
                    last_refreshed_at=last_refreshed_raw,
                    skill_md_last_commit_at=skill_md_commit_at.isoformat(),
                )
            )
    return stale


def main() -> int:
    try:
        stale = find_stale_golden_fixtures(ROOT)
    except Exception as exc:  # noqa: BLE001 -- advisory-only: never fail the caller (see module docstring)
        print(f"warning: golden-staleness check itself failed to run: {exc}", file=sys.stderr)
        print("This is advisory only (ADR-0003/0004): it never fails make lint-static or CI.")
        return 0
    if not stale:
        print("ok: no golden fixture is older than its skill's SKILL.md")
        return 0

    print(f"WARNING: {len(stale)} golden fixture(s) may be stale relative to their skill's SKILL.md:")
    for item in sorted(stale, key=lambda entry: (entry.skill, entry.case_id)):
        try:
            relative_path = item.fixture_path.relative_to(ROOT)
        except ValueError:
            relative_path = item.fixture_path
        print(
            f"  - {relative_path}: last_refreshed_at={item.last_refreshed_at}, but "
            f"{item.skill}/SKILL.md last changed at {item.skill_md_last_commit_at} -- "
            "consider re-verifying this fixture still matches SKILL.md's current behavior",
        )
    print("This is advisory only (ADR-0003/0004): it never fails make lint-static or CI.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
