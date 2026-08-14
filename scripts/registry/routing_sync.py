"""Cross-check skill-id mentions in shared framework docs against the registry.

Prevents dangling routing references: a skill name that skill-routing.md
routes to but that was renamed or removed from skills.yaml, or a registered
skill nobody documented a route for.
"""
from __future__ import annotations

import re
from pathlib import Path

from scripts.registry.id_diff import report_id_coverage
from scripts.registry.models import Registry

# Skill ids are exclusively lowercase alphanumerics and hyphens (see
# crosscheck.py's _SKILL_ID_RE), and every registered id is multi-word
# (verified: no single-word skill id exists), so a hyphenated, all-lowercase
# token is always a skill-id-shaped reference. The hyphen requirement (vs.
# zero-or-more) matters: without it, a plain bold word like "**required**"
# would false-positive as a dangling reference. A bold hyphenated *non*-skill
# phrase ("**read-only**") can still collide -- add it to _EXTERNAL_MENTIONS
# below if that ever happens.
_SKILL_ID_SHAPE = r"[a-z0-9]+-[a-z0-9]+(?:-[a-z0-9]+)*"
_SKILL_MENTION_RE = re.compile(rf"\*\*({_SKILL_ID_SHAPE})\*\*")

# Same shape, anchored for whole-token matching against the "NOT these"
# column, which is bare (unbolded) text.
_TABLE_TOKEN_RE = re.compile(f"^{_SKILL_ID_SHAPE}$")

ROUTING_DOC_RELATIVE = Path("docs") / "skill-framework" / "shared" / "skill-routing.md"

# Bold, skill-id-shaped mentions that are deliberately not registered skills.
# Keep this list explicit and small: item 4 requires every routing reference
# to be either registered, or explicitly marked external here -- never silent.
_EXTERNAL_MENTIONS: frozenset[str] = frozenset()


def routing_doc_path(root: Path) -> Path:
    return root / ROUTING_DOC_RELATIVE


def _split_top_level(value: str, separators: str = ",/") -> list[str]:
    """Split on separators outside parens, so "a (b, c), d" -> ["a (b, c)", "d"]."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for char in value:
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        if char in separators and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    parts.append("".join(current))
    return parts


def _not_these_mentions(text: str) -> set[str]:
    """Extract skill-id mentions from the routing table's bare "NOT these" column.

    Route-to mentions are always bold (caught by _SKILL_MENTION_RE); "NOT
    these" is bare comma/slash-separated text like "incident-rca, squad-map
    (that's what it delegates to internally...)" -- covering it needs table
    structure, not just a bold-span scan, since it's most of the document's
    actual skill references.
    """
    mentioned: set[str] = set()
    in_table = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## Routing table"):
            in_table = True
            continue
        if in_table and stripped.startswith("## "):
            break
        if not in_table or not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 3:
            continue
        not_these = cells[2]
        if not_these == "NOT these" or set(not_these) <= {"-"}:
            continue
        for fragment in _split_top_level(not_these):
            token = re.split(r"[\s(]", fragment.strip(), maxsplit=1)[0].strip("*")
            if _TABLE_TOKEN_RE.match(token):
                mentioned.add(token)
    return mentioned


def validate_skill_routing_references(root: Path, registry: Registry) -> list[str]:
    path = routing_doc_path(root)
    if not path.is_file():
        return []

    text = path.read_text(encoding="utf-8")
    mentioned = set(_SKILL_MENTION_RE.findall(text)) | _not_these_mentions(text)
    registered = set(registry.skills)

    return report_id_coverage(
        mentioned,
        registered,
        dangling_label=(
            "error: skill-routing.md references unregistered skills (register them, add to "
            "routing_sync._EXTERNAL_MENTIONS if intentionally external, or remove the reference)"
        ),
        missing_label="error: skill-routing.md has no routing entry for",
        exempt=_EXTERNAL_MENTIONS,
    )
