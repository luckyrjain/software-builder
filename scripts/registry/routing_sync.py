"""Cross-check skill-id mentions in shared framework docs against the registry.

Prevents dangling routing references: a skill name that skill-routing.md
routes to but that was renamed or removed from skills.yaml, or a registered
skill nobody documented a route for.
"""
from __future__ import annotations

import re
from pathlib import Path

from scripts.registry.models import Registry

# Skill ids are exclusively lowercase alphanumerics and hyphens (see
# crosscheck.py's _SKILL_ID_RE), so a bold span matching that shape is always
# a skill-id reference -- prose emphasis always contains spaces, capitals, or
# punctuation and never matches this pattern.
_SKILL_MENTION_RE = re.compile(r"\*\*([a-z0-9]+(?:-[a-z0-9]+)*)\*\*")

ROUTING_DOC_RELATIVE = Path("docs") / "skill-framework" / "shared" / "skill-routing.md"

# Bold, skill-id-shaped mentions that are deliberately not registered skills.
# Keep this list explicit and small: item 4 requires every routing reference
# to be either registered, or explicitly marked external here -- never silent.
_EXTERNAL_MENTIONS: frozenset[str] = frozenset()


def routing_doc_path(root: Path) -> Path:
    return root / ROUTING_DOC_RELATIVE


def validate_skill_routing_references(root: Path, registry: Registry) -> list[str]:
    path = routing_doc_path(root)
    if not path.is_file():
        return []

    text = path.read_text(encoding="utf-8")
    mentioned = set(_SKILL_MENTION_RE.findall(text))
    registered = set(registry.skills)

    errors: list[str] = []
    dangling = sorted(mentioned - registered - _EXTERNAL_MENTIONS)
    if dangling:
        errors.append(
            "error: skill-routing.md references unregistered skills: "
            + ", ".join(dangling)
            + " (register them, add to routing_sync._EXTERNAL_MENTIONS if intentionally "
            "external, or remove the reference)",
        )
    unrouted = sorted(registered - mentioned)
    if unrouted:
        errors.append(
            "error: skill-routing.md has no routing entry for: " + ", ".join(unrouted),
        )
    return errors
