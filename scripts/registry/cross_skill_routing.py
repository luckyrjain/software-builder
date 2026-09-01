from __future__ import annotations

import posixpath
import re

SECTION_HEADING = "## 1. Symmetric matrix (forward escalations)"
NEXT_HEADING_PREFIX = "## "
ARROW = "→"  # →

# cross-skill-escalation.md always lives here; its relative markdown links (e.g. "../../../
# who-owns-x-bot/reference/slack-format.md") are anchored to this directory. Carrying a Trigger
# cell's prose verbatim into docs/README.md — one directory shallower — would leave the link
# resolving from the wrong place (escaping the repo entirely), so every relative link gets
# re-anchored to the destination directory before it's rendered there.
_SOURCE_DIR = "docs/skill-framework/shared"
_DEST_DIR = "docs"
# Allows exactly one level of nested parens in the target (e.g. a Wikipedia-style URL ending in
# "_(bar)") so the match doesn't truncate at that inner ")" and leave a corrupted target plus a
# stray ")" in the rendered text -- a plain "[^)]+" target class does exactly that.
#
# Residual limitation: a target with TWO or more levels of nesting (e.g. "foo_(a_(b)_c)") doesn't
# match at all, rather than matching-and-truncating -- for a relative link this means it's left
# completely un-reanchored (silently resolving from the wrong directory once copied into
# docs/README.md), with no error. Python's `re` can't express general balanced-paren matching;
# going further would mean a real parser. No such link exists in cross-skill-escalation.md today
# (verified), so this is an accepted, documented gap rather than a case worth a parser for.
_MARKDOWN_LINK = re.compile(r"\[([^\]]*)\]\(((?:[^()\s]|\([^()]*\))*)\)")


def _reanchor_link_target(target: str) -> str:
    if target.startswith(("http://", "https://", "#", "mailto:", "/")):
        # An absolute path isn't anchored to _SOURCE_DIR in the first place, and rewriting it
        # relative to _DEST_DIR would resolve against the current process's cwd (via
        # posixpath.relpath), not repo-relative content -- pass it through unchanged rather than
        # produce a cwd-dependent result. No such link exists in cross-skill-escalation.md today;
        # this only guards against one being added later.
        return target
    path, _, fragment = target.partition("#")
    if not path:
        return target
    absolute = posixpath.normpath(posixpath.join(_SOURCE_DIR, path))
    reanchored = posixpath.relpath(absolute, _DEST_DIR)
    return f"{reanchored}#{fragment}" if fragment else reanchored


def reanchor_relative_links(text: str) -> str:
    """Rewrite relative markdown links in `text` from cross-skill-escalation.md's directory to
    docs/README.md's directory, so a Trigger cell copied verbatim still points inside the repo."""
    def replace(match: re.Match[str]) -> str:
        label, target = match.group(1), match.group(2)
        return f"[{label}]({_reanchor_link_target(target)})"

    return _MARKDOWN_LINK.sub(replace, text)


def parse_forward_escalation_matrix(markdown: str) -> list[tuple[str, str, str]]:
    """Parse the "Symmetric matrix (forward escalations)" table into (trigger, from, to) rows.

    Fails loudly (raises ValueError) on any shape this doesn't recognize, rather than silently
    dropping a row — a skill's escalation edge going missing from docs/README.md because a table
    row didn't parse is worse than a red `make generate-check` in CI.
    """
    lines = markdown.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == SECTION_HEADING)
    except StopIteration:
        raise ValueError(f"cross-skill-escalation.md: missing section heading {SECTION_HEADING!r}")

    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].strip().startswith(NEXT_HEADING_PREFIX):
            end = i
            break

    table_lines = [line for line in lines[start:end] if line.strip().startswith("|")]
    if len(table_lines) < 3:
        raise ValueError(
            f"cross-skill-escalation.md: expected a markdown table under {SECTION_HEADING!r}, "
            f"found {len(table_lines)} table-like lines",
        )

    header_cells = [c.strip() for c in table_lines[0].strip().strip("|").split("|")]
    expected_header = ["Trigger", f"From {ARROW} To", "Handoff artifact", "User prompt template"]
    if header_cells != expected_header:
        raise ValueError(
            f"cross-skill-escalation.md: unexpected table header {header_cells!r}, "
            f"expected {expected_header!r}",
        )

    edges: list[tuple[str, str, str]] = []
    for row in table_lines[2:]:
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) != len(expected_header):
            raise ValueError(f"cross-skill-escalation.md: malformed row (wrong cell count): {row!r}")
        trigger, from_to = cells[0], cells[1]
        if from_to.count(ARROW) != 1:
            raise ValueError(
                f"cross-skill-escalation.md: expected exactly one {ARROW!r} in From/To cell: {from_to!r}",
            )
        source, target = (part.strip() for part in from_to.split(ARROW))
        if not source or not target:
            raise ValueError(f"cross-skill-escalation.md: empty From/To side in row: {row!r}")
        edges.append((reanchor_relative_links(trigger), source, target))
    return edges


def filter_deprecated_edges(
    edges: list[tuple[str, str, str]],
    deprecated_skill_ids: set[str],
) -> list[tuple[str, str, str]]:
    """Drop any escalation edge that routes to or from a deprecated skill.

    A deprecated skill is mid-removal (see docs/skill-framework/shared/deprecation-policy.md):
    it is still registered and still directly invocable through its compatibility window, but
    an ambient-invocation router must never actively dispatch or escalate to it, and a
    still-active skill must never be advertised as an escalation target that immediately
    hands off to something already scheduled for removal. Without this filter, a deprecated
    skill stayed a full routing/escalation candidate for its entire 90-day removal window
    (and beyond, since nothing ever re-checked it).
    """
    if not deprecated_skill_ids:
        return edges
    return [
        (trigger, source, target)
        for trigger, source, target in edges
        if source not in deprecated_skill_ids and target not in deprecated_skill_ids
    ]
