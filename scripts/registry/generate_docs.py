from __future__ import annotations

import re

from scripts.registry.cross_skill_routing import parse_forward_escalation_matrix
from scripts.registry.models import Registry

README_COUNT_START = "<!-- skills-count:start -->"
README_COUNT_END = "<!-- skills-count:end -->"
REPOSITORY_TABLE_START = "<!-- registry-skills-table:start -->"
REPOSITORY_TABLE_END = "<!-- registry-skills-table:end -->"
README_LINKS_START = "<!-- skill-doc-links:start -->"
README_LINKS_END = "<!-- skill-doc-links:end -->"
README_ROUTING_START = "<!-- cross-skill-routing:start -->"
README_ROUTING_END = "<!-- cross-skill-routing:end -->"


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


def render_skills_table(registry: Registry) -> str:
    lines = [
        "| Skill | Category | Invocation | Install requires | Lint target |",
        "|-------|----------|------------|------------------|-------------|",
    ]
    for skill_id, entry in sorted(registry.skills.items()):
        requires = ", ".join(entry.install.requires) if entry.install.requires else "—"
        lines.append(
            f"| `{skill_id}` | {entry.category} | {entry.invocation} | {requires} | "
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


def update_repository_table(repository_md: str, registry: Registry) -> str:
    table = "\n" + render_skills_table(registry).rstrip() + "\n"
    return update_marker_block(
        repository_md,
        REPOSITORY_TABLE_START,
        REPOSITORY_TABLE_END,
        table,
    )


def render_doc_links_table(registry: Registry) -> str:
    lines = [
        "| Skill | Human overview | Agent entry | Setup |",
        "|-------|----------------|-------------|-------|",
    ]
    for skill_id in sorted(registry.skills):
        lines.append(
            f"| **{skill_id}** | [{skill_id}/README.md](../{skill_id}/README.md) | "
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


def update_readme_doc_links(readme: str, registry: Registry) -> str:
    table = "\n" + render_doc_links_table(registry).rstrip() + "\n"
    return update_marker_block(readme, README_LINKS_START, README_LINKS_END, table)


def update_readme_routing_table(readme: str, escalation_matrix_md: str) -> str:
    edges = parse_forward_escalation_matrix(escalation_matrix_md)
    table = "\n" + render_routing_table(edges).rstrip() + "\n"
    return update_marker_block(readme, README_ROUTING_START, README_ROUTING_END, table)
