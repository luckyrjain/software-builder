#!/usr/bin/env python3
"""Flag root CHANGELOG.md entries that look like they duplicate a skill's own CHANGELOG.md.

CONTRIBUTING.md's "Record user-visible changes" rule says a change belongs in the skill's own
`<skill>/CHANGELOG.md`, and the root `CHANGELOG.md` is reserved "for cross-cutting changes" --
i.e. changes that touch more than one skill or the shared framework. That's advisory prose, not
lint-enforced, and a spot check of the real file (see `scripts/tests/test_check_changelog_placement.py`
and the PR that added this script) confirmed the predictable failure mode: a single-skill change
gets recorded in *both* places instead of just the skill's own file. Concretely, of the 38 root
`## <skill>` dated entries that have a same-dated entry in that skill's own CHANGELOG.md, 26 are a
near-total rewrite of each other (>=0.25 token-Jaccard overlap on distinctive words) -- e.g. the
2026-08-10 "safe rendered-output boundary" rollout landed nearly-identical entries in both
CHANGELOG.md and six-plus skills' own CHANGELOG.md files on the same day.

Detection is deliberately simple and explainable, not fuzzy/ML matching:
  1. Parse root CHANGELOG.md into (skill, date, body) triples: each `## <skill-name>` section
     that matches a real skill directory, and each `### ... (YYYY-MM-DD)` entry nested under it.
  2. Parse that skill's own `<skill>/CHANGELOG.md` (if it exists) the same way, extracting a date
     from any heading line (its own version-heading conventions vary skill to skill, but every
     dated entry has a YYYY-MM-DD somewhere in its heading).
  3. For each root entry, compare its body against every same-dated entry in the skill's own file
     using Jaccard similarity over the set of distinctive words (length >= 4, case-folded) in
     each body. Flag the best match if it clears a threshold.

This is a WARNING, not a hard error (always exits 0). Retroactively flagging all of history would
be noisy on day one -- the spot check above found 26 pre-existing likely-duplicates already in the
repository, none of which anyone is going to rewrite retroactively -- and the metric is a heuristic
(word-overlap, not semantic understanding), so it can both miss real duplicates phrased completely
differently and, in principle, flag two genuinely-unrelated entries that happen to share enough
domain vocabulary. Treat every hit as a prompt to double check placement on review, not as a gate.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
HEADING_RE = re.compile(r"^(#{2,6})\s+(.*\S)\s*$")

# Same date + this much token overlap is the "near-identical or substantially overlapping"
# bar from the task: high enough that the 26 confirmed real duplicates above all clear it, low
# enough it doesn't fire on the many same-day-but-unrelated entries the repo also has (those
# top out well below this in the spot check).
SIMILARITY_THRESHOLD = 0.25
# A floor on shared distinctive words, so two very short entries can't hit the ratio by chance
# on two or three incidentally shared words.
MIN_SHARED_WORDS = 5


def _parse_headings(text: str) -> list[tuple[int, int, str]]:
    """Return (line_index, heading_level, heading_text) for every heading line.

    Fenced code blocks are skipped, matching scripts/registry/generate_docs.py's
    parse_changelog_sections -- a `## `/`### `-prefixed line inside an example
    snippet must never be mistaken for a real section/entry heading.
    """
    headings = []
    in_code_fence = False
    for line_index, line in enumerate(text.splitlines()):
        if line.strip().startswith("```"):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue
        match = HEADING_RE.match(line)
        if match:
            headings.append((line_index, len(match.group(1)), match.group(2)))
    return headings


def _entry_body(lines: list[str], headings: list[tuple[int, int, str]], entry_index: int) -> str:
    """Text between one heading and the next heading at the same-or-shallower level."""
    line_index, level, _ = headings[entry_index]
    end_line = len(lines)
    for later_line_index, later_level, _ in headings[entry_index + 1 :]:
        if later_level <= level:
            end_line = later_line_index
            break
    return "\n".join(lines[line_index + 1 : end_line])


def parse_skill_changelog_entries(changelog_md: str) -> list[tuple[str, str, str]]:
    """Return (date, heading_title, body) for every dated heading in a per-skill CHANGELOG.md."""
    lines = changelog_md.splitlines()
    headings = _parse_headings(changelog_md)
    entries = []
    for index, (_, _, title) in enumerate(headings):
        date_match = DATE_RE.search(title)
        if not date_match:
            continue
        body = _entry_body(lines, headings, index)
        entries.append((date_match.group(0), title, body))
    return entries


def parse_root_changelog_entries(
    changelog_md: str, skill_dirs: set[str]
) -> list[tuple[str, str, str, str]]:
    """Return (skill, date, heading_title, body) for dated entries under a real skill's section.

    Root sections are `## <name>` at level 2; a section counts only when `<name>` matches a real
    skill directory (so cross-cutting sections like "Platform", "Repository", or "Unreleased"
    are excluded -- those are exactly the sections CONTRIBUTING.md's "root one for cross-cutting
    changes" carve-out is for, and duplication there isn't the failure mode this check targets).
    Dated entries are `### ... (YYYY-MM-DD)`-style headings nested directly under such a section.
    """
    lines = changelog_md.splitlines()
    headings = _parse_headings(changelog_md)
    entries = []
    current_skill: str | None = None
    for index, (_, level, title) in enumerate(headings):
        if level == 2:
            stripped = title.strip()
            current_skill = stripped if stripped in skill_dirs else None
            continue
        if level == 3 and current_skill is not None:
            date_match = DATE_RE.search(title)
            if date_match:
                body = _entry_body(lines, headings, index)
                entries.append((current_skill, date_match.group(0), title, body))
    return entries


def _distinctive_words(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {word for word in words if len(word) >= 4}


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def find_likely_misplacements(root: Path) -> list[str]:
    changelog_path = root / "CHANGELOG.md"
    if not changelog_path.is_file():
        return []

    skill_dirs = {
        path.name for path in root.iterdir() if path.is_dir() and (path / "CHANGELOG.md").is_file()
    }
    root_entries = parse_root_changelog_entries(
        changelog_path.read_text(encoding="utf-8"), skill_dirs
    )

    warnings: list[str] = []
    skill_entries_cache: dict[str, list[tuple[str, str, str]]] = {}
    for skill, date, root_title, root_body in root_entries:
        if skill not in skill_entries_cache:
            skill_changelog = root / skill / "CHANGELOG.md"
            skill_entries_cache[skill] = parse_skill_changelog_entries(
                skill_changelog.read_text(encoding="utf-8")
            )

        root_words = _distinctive_words(root_body)
        best_ratio = 0.0
        best_title = ""
        best_shared = 0
        for entry_date, skill_title, skill_body in skill_entries_cache[skill]:
            if entry_date != date:
                continue
            skill_words = _distinctive_words(skill_body)
            shared = len(root_words & skill_words)
            ratio = _jaccard(root_words, skill_words)
            if ratio > best_ratio:
                best_ratio, best_title, best_shared = ratio, skill_title, shared

        if best_ratio >= SIMILARITY_THRESHOLD and best_shared >= MIN_SHARED_WORDS:
            warnings.append(
                f"warning: CHANGELOG.md '## {skill}' entry {date} ({root_title!r}) shares "
                f"{best_ratio:.0%} word-overlap with {skill}/CHANGELOG.md's {date} entry "
                f"({best_title!r}) -- possible duplicate recording (heuristic word-overlap match, "
                "not a semantic check: this can also fire on a genuinely cross-cutting root entry "
                "that happens to share vocabulary with a same-day per-skill entry). If this "
                "entry only describes a single-skill change, CONTRIBUTING.md says it belongs in "
                f"{skill}/CHANGELOG.md instead; if it's genuinely cross-cutting, no action needed."
            )
    return warnings


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    warnings = find_likely_misplacements(root)
    for warning in warnings:
        print(warning)
    if warnings:
        print(
            f"warning: {len(warnings)} possible CHANGELOG.md/skill-changelog duplicate(s) found "
            "(non-fatal; see scripts/check_changelog_placement.py docstring)",
        )
    else:
        print("ok: no likely CHANGELOG.md/skill-changelog duplicates found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
