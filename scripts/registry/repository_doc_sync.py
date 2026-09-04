"""Cross-check docs/REPOSITORY.md's hand-written Layout tree against the registry.

docs/REPOSITORY.md carries two statements of "what skills exist": a hand-typed ASCII
directory tree under "## Layout" (one line per skill, with a short prose description)
and, a few lines below it, the `<!-- registry-skills-table:start -->` block that
scripts/registry/generate_docs.py regenerates from the registry on every `make
generate`. Only the second one is generated. The commit that added
codebase-architecture-review/ and module-design/ (9d6b726) updated that generated
table but not the hand-typed tree above it, leaving the file contradicting itself --
an agent orienting from the tree alone would conclude those two skills don't exist.

This is a one-directional check: every registered skill id must appear as a `name/`
entry somewhere in the tree. The reverse isn't checked, since the tree also lists
non-skill entries (README.md, docs/, scripts/, generated/catalogue/, ...) that have
nothing to do with the registry.
"""

from __future__ import annotations

import re
from pathlib import Path

from scripts.registry.models import Registry

LAYOUT_TREE_RE = re.compile(r"## Layout\n+```\n(.*?)\n```", re.DOTALL)
# A tree line's directory entry: the branch glyphs, then a bare `name/` (a skill
# directory), never `name/sub/path` -- only top-level entries are being enumerated.
TREE_DIR_RE = re.compile(r"^[│├└─\s]*([a-z0-9][a-z0-9-]*)/(?:\s|$)", re.MULTILINE)


def repository_doc_path(root: Path) -> Path:
    return root / "docs" / "REPOSITORY.md"


def _tree_directory_names(markdown: str) -> set[str] | None:
    """The skill-directory names in the `## Layout` fenced tree, or None if that section is
    absent -- distinct from an empty *set*, which would (wrongly) read as "every registered
    skill is missing from the tree" for a doc that never had one to begin with (e.g. a minimal
    test fixture)."""
    match = LAYOUT_TREE_RE.search(markdown)
    if not match:
        return None
    return set(TREE_DIR_RE.findall(match.group(1)))


def validate_repository_doc_layout_tree(root: Path, registry: Registry) -> list[str]:
    path = repository_doc_path(root)
    if not path.is_file():
        return []

    tree_dirs = _tree_directory_names(path.read_text(encoding="utf-8"))
    if tree_dirs is None:
        return []
    missing = sorted(set(registry.skills) - tree_dirs)
    if not missing:
        return []
    return [
        "error: docs/REPOSITORY.md's Layout tree (## Layout) is missing registered "
        "skill(s) — the generated registry-skills-table below it already lists them, "
        "so the file now contradicts itself: " + ", ".join(missing),
    ]
