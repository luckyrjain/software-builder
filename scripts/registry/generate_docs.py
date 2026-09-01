from __future__ import annotations

import re
from typing import Any

from scripts.registry.cross_skill_routing import (
    filter_deprecated_edges,
    parse_forward_escalation_matrix,
)
from scripts.registry.models import Registry

README_COUNT_START = "<!-- skills-count:start -->"
README_COUNT_END = "<!-- skills-count:end -->"
REPOSITORY_TABLE_START = "<!-- registry-skills-table:start -->"
REPOSITORY_TABLE_END = "<!-- registry-skills-table:end -->"
README_LINKS_START = "<!-- skill-doc-links:start -->"
README_LINKS_END = "<!-- skill-doc-links:end -->"
README_ROUTING_START = "<!-- cross-skill-routing:start -->"
README_ROUTING_END = "<!-- cross-skill-routing:end -->"
CHANGELOG_TOC_START = "<!-- changelog-toc:start -->"
CHANGELOG_TOC_END = "<!-- changelog-toc:end -->"


def escape_table_cell(value: object) -> str:
    """Escape a dynamic value for safe interpolation into a generated Markdown table cell, so
    untrusted/dynamic content (a skill description, a free-text evidence reference, ...) cannot
    change the table's shape or escape into Markdown link/image syntax. Shared by every
    generate_*.py module that renders a table -- see generate_compatibility.py and
    generate_agent_compatibility.py -- rather than each keeping its own copy.
    """
    escaped: list[str] = []
    for char in str(value):
        codepoint = ord(char)
        if char == "\\":
            escaped.append("\\\\")
        elif char in {"|", "`", "[", "]", "(", ")", "<", ">"}:
            escaped.append("\\" + char)
        elif codepoint < 0x20 or codepoint == 0x7F:
            escaped.append(f"\\x{codepoint:02x}")
        else:
            escaped.append(char)
    return "".join(escaped)


def update_marker_block(text: str, start: str, end: str, content: str) -> str:
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    replacement = f"{start}{content}{end}"
    if not pattern.search(text):
        raise ValueError(f"missing marker block: {start} ... {end}")
    # A callable repl, not a string, so re.sub never interprets backslash-escapes (\g<0>, \1, ...)
    # in `replacement` as backreferences -- content can come from free-text prose in a repo
    # markdown file (e.g. a Trigger cell in cross-skill-escalation.md), not just tightly
    # controlled registry strings, so treating it as a literal string here is load-bearing.
    return pattern.sub(lambda _match: replacement, text, count=1)


def update_readme_badge(readme: str, count: int) -> str:
    # The generated value must never sit *inside* the badge's image destination. CommonMark's
    # grammar for a bare (non-`<...>`-bracketed) link/image destination forbids literal whitespace;
    # `<!-- skills-count:start -->23<!-- skills-count:end -->` fused into the URL contains spaces
    # inside the comment tags themselves, which broke the destination outright and made the whole
    # `![alt](url)` fall back to literal text plus a stray auto-link on the real rendered GitHub
    # page — independent of comment-stripping timing (confirmed: the identical tags *without*
    # spaces parse into a working, if oddly percent-encoded, image; the spaces are what break it).
    # Keeping the whole image on its own line, bracketed by the markers on their own lines too,
    # keeps the comments unambiguously block-level and the image intact.
    badge_block = f"\n![Skills](https://img.shields.io/badge/skills-{count}-blue)\n"
    return update_marker_block(readme, README_COUNT_START, README_COUNT_END, badge_block)


def _deprecated_skill_label(skill_id: str, deprecation: dict[str, Any]) -> str:
    """Render a deprecated skill's table cell without silently dropping its row.

    deprecation-policy.md rule 1 requires deprecation to "not silently change" a
    stable identity, and requires a `migration_note`/`replacement` be documented for
    every deprecated item -- so a deprecated skill stays visible in generated docs,
    flagged clearly, through its whole compatibility window, rather than disappearing
    the moment `deprecated: true` is set.
    """
    replacement = deprecation.get("replacement")
    if isinstance(replacement, str) and replacement and replacement != "none":
        return f"`{skill_id}` (deprecated → `{replacement}`)"
    return f"`{skill_id}` (deprecated)"


def render_skills_table(
    registry: Registry,
    deprecated: dict[str, dict[str, Any]] | None = None,
) -> str:
    deprecated = deprecated or {}
    lines = [
        "| Skill | Category | Invocation | Install requires | Lint target |",
        "|-------|----------|------------|------------------|-------------|",
    ]
    for skill_id, entry in sorted(registry.skills.items()):
        requires = ", ".join(entry.install.requires) if entry.install.requires else "—"
        skill_cell = (
            _deprecated_skill_label(skill_id, deprecated[skill_id])
            if skill_id in deprecated
            else f"`{skill_id}`"
        )
        lines.append(
            f"| {skill_cell} | {entry.category} | {entry.invocation} | {requires} | "
            f"`make lint-{entry.lint.target}` |",
        )
    return "\n".join(lines) + "\n"


def render_install_mermaid(registry: Registry) -> str:
    lines = ["graph TD"]
    for skill_id, entry in sorted(registry.skills.items()):
        for dep in entry.install.requires:
            lines.append(f"  {skill_id} --> {dep}")
    if len(lines) == 1:
        lines.append("  empty[No install dependencies]")
    return "\n".join(lines) + "\n"


def update_repository_table(
    repository_md: str,
    registry: Registry,
    deprecated: dict[str, dict[str, Any]] | None = None,
) -> str:
    table = "\n" + render_skills_table(registry, deprecated).rstrip() + "\n"
    return update_marker_block(
        repository_md,
        REPOSITORY_TABLE_START,
        REPOSITORY_TABLE_END,
        table,
    )


def render_doc_links_table(
    registry: Registry,
    deprecated: dict[str, dict[str, Any]] | None = None,
) -> str:
    deprecated = deprecated or {}
    lines = [
        "| Skill | Human overview | Agent entry | Setup |",
        "|-------|----------------|-------------|-------|",
    ]
    for skill_id in sorted(registry.skills):
        label = f"**{skill_id}** (deprecated)" if skill_id in deprecated else f"**{skill_id}**"
        lines.append(
            f"| {label} | [{skill_id}/README.md](../{skill_id}/README.md) | "
            f"[{skill_id}/SKILL.md](../{skill_id}/SKILL.md) | "
            f"[{skill_id}/SETUP.md](../{skill_id}/SETUP.md) |",
        )
    return "\n".join(lines) + "\n"


def render_routing_table(edges: list[tuple[str, str, str]]) -> str:
    lines = [
        "| From | Trigger | Next skill |",
        "|------|---------|------------|",
    ]
    for trigger, source, target in edges:
        lines.append(f"| {source} | {trigger} | {target} |")
    return "\n".join(lines) + "\n"


def update_readme_doc_links(
    readme: str,
    registry: Registry,
    deprecated: dict[str, dict[str, Any]] | None = None,
) -> str:
    table = "\n" + render_doc_links_table(registry, deprecated).rstrip() + "\n"
    return update_marker_block(readme, README_LINKS_START, README_LINKS_END, table)


def update_readme_routing_table(
    readme: str,
    escalation_matrix_md: str,
    deprecated: dict[str, dict[str, Any]] | None = None,
) -> str:
    edges = parse_forward_escalation_matrix(escalation_matrix_md)
    edges = filter_deprecated_edges(edges, set(deprecated or {}))
    table = "\n" + render_routing_table(edges).rstrip() + "\n"
    return update_marker_block(readme, README_ROUTING_START, README_ROUTING_END, table)


_CHANGELOG_SECTION_HEADING_RE = re.compile(r"^## (.+)$")


def parse_changelog_sections(changelog_md: str) -> list[str]:
    """Return the text of every top-level (`## `) heading, in document order.

    Fenced code blocks are skipped so a `## `-prefixed line inside an example snippet
    is never mistaken for a real section heading. `### `-level (or deeper) headings --
    the dated per-change entries nested under each skill section -- are intentionally
    excluded; the table of contents indexes skill sections, not individual entries.
    """
    headings: list[str] = []
    in_code_fence = False
    for line in changelog_md.splitlines():
        if line.strip().startswith("```"):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue
        match = _CHANGELOG_SECTION_HEADING_RE.match(line)
        if match:
            headings.append(match.group(1).strip())
    return headings


def _slugify_heading(heading: str) -> str:
    """Match the repository Markdown linter's simple GitHub-style heading slug rules."""
    slug = heading.lower()
    slug = re.sub(r"[^a-z0-9 -]", "", slug)
    slug = re.sub(r" +", " ", slug).strip().replace(" ", "-")
    return slug


def render_changelog_toc(headings: list[str]) -> str:
    # Section names repeat in this file (the same skill gets a new `## <skill>` section
    # each time change history returns to it, rather than every entry nesting under one
    # long-lived section) -- GitHub disambiguates repeated anchors by suffixing -1, -2, ...
    # in order of appearance, so the counters below must match that exactly for the links
    # to resolve to the right occurrence rather than always the first one.
    seen: dict[str, int] = {}
    lines = []
    for heading in headings:
        slug = _slugify_heading(heading)
        occurrence = seen.get(slug, 0)
        seen[slug] = occurrence + 1
        anchor = slug if occurrence == 0 else f"{slug}-{occurrence}"
        lines.append(f"- [{heading}](#{anchor})")
    return "\n".join(lines) + "\n"


def update_changelog_toc(changelog_md: str) -> str:
    headings = parse_changelog_sections(changelog_md)
    toc = "\n" + render_changelog_toc(headings).rstrip() + "\n"
    return update_marker_block(changelog_md, CHANGELOG_TOC_START, CHANGELOG_TOC_END, toc)
