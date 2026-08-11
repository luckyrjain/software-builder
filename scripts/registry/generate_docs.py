from __future__ import annotations

import re

from scripts.registry.models import Registry

README_COUNT_START = "<!-- skills-count:start -->"
README_COUNT_END = "<!-- skills-count:end -->"
REPOSITORY_TABLE_START = "<!-- registry-skills-table:start -->"
REPOSITORY_TABLE_END = "<!-- registry-skills-table:end -->"


def update_marker_block(text: str, start: str, end: str, content: str) -> str:
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    replacement = f"{start}{content}{end}"
    if not pattern.search(text):
        raise ValueError(f"missing marker block: {start} ... {end}")
    return pattern.sub(replacement, text, count=1)


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


def render_composition_mermaid(registry: Registry) -> str:
    from scripts.registry.composition import render_composition_mermaid as render

    return render(registry)


def update_repository_table(repository_md: str, registry: Registry) -> str:
    table = "\n" + render_skills_table(registry).rstrip() + "\n"
    return update_marker_block(
        repository_md,
        REPOSITORY_TABLE_START,
        REPOSITORY_TABLE_END,
        table,
    )
