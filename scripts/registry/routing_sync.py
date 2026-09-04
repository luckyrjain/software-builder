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


def _routing_table_rows(text: str) -> list[list[str]]:
    """The routing table's data rows, each as its list of trimmed cells."""
    rows: list[list[str]] = []
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
        if len(cells) >= 3 and cells[2] != "NOT these":
            rows.append(cells)
    return rows


def _excluded_ids(not_these: str) -> set[str]:
    """The skill ids one "NOT these" cell names.

    The column is bare comma/slash-separated text like "incident-rca, squad-map (that's what
    it delegates to internally...)", so each fragment's leading token is the id and the rest is
    prose explaining the distinction.
    """
    if set(not_these) <= {"-"}:
        return set()
    ids: set[str] = set()
    for fragment in _split_top_level(not_these):
        token = re.split(r"[\s(]", fragment.strip(), maxsplit=1)[0].strip("*")
        if _TABLE_TOKEN_RE.match(token):
            ids.add(token)
    return ids


def _not_these_mentions(text: str) -> set[str]:
    """Every skill-id mention in the routing table's bare "NOT these" column.

    Route-to mentions are always bold (caught by _SKILL_MENTION_RE); covering "NOT these"
    needs table structure, not just a bold-span scan, since it's most of the document's actual
    skill references.
    """
    return {skill_id for cells in _routing_table_rows(text) for skill_id in _excluded_ids(cells[2])}


def routing_exclusions_by_skill(text: str) -> dict[str, set[str]]:
    """For each skill the routing table routes to, the union of its rows' "NOT these" ids.

    A skill can own several rows (prd-architect has one per mode), and the exclusions of all of
    them together are what that skill's own documentation may draw from.
    """
    exclusions: dict[str, set[str]] = {}
    for cells in _routing_table_rows(text):
        excluded = _excluded_ids(cells[2])
        for skill_id in _SKILL_MENTION_RE.findall(cells[1]):
            exclusions.setdefault(skill_id, set()).update(excluded)
    return exclusions


def skill_md_exclusions(skill_md: str) -> set[str] | None:
    """The skill ids a SKILL.md's own "NOT to use" table routes away to, or None if it has none.

    Two heading shapes are in use -- `## When NOT to use` with a Request/Use-instead table, and
    `## When to use / NOT to use` with a Use/Not table -- but in both the last column is the
    one naming other skills, and it names them in bold.
    """
    lines = skill_md.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.startswith("## ") and "NOT to use" in line),
        None,
    )
    if start is None:
        return None
    ids: set[str] = set()
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if stripped.startswith("## "):
            break
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) >= 2:
            ids.update(_SKILL_MENTION_RE.findall(cells[-1]))
    return ids


def validate_skill_not_these_subsets(root: Path, registry: Registry) -> list[str]:
    """Enforce skill-routing.md's own rule: a skill's "NOT to use" table is a subset of its row.

    The document states this ("Each skill's 'When NOT to use' table MUST be a subset of this
    routing table -- do not maintain independent routing logic per skill") and nothing checked
    it, so 15 skills had grown per-skill routing decisions the shared table never learned about.
    """
    path = routing_doc_path(root)
    if not path.is_file():
        return []

    exclusions = routing_exclusions_by_skill(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    for skill_id, entry in sorted(registry.skills.items()):
        skill_md = root / entry.path / "SKILL.md"
        if not skill_md.is_file():
            continue
        named = skill_md_exclusions(skill_md.read_text(encoding="utf-8"))
        if named is None:
            continue
        extra = sorted(named - exclusions.get(skill_id, set()))
        if extra:
            errors.append(
                f"error: {skill_id}: SKILL.md routes away to {', '.join(extra)}, which "
                f"skill-routing.md's own row for {skill_id} does not list under 'NOT these' "
                "(add them there — the shared table is the superset, not the per-skill one)",
            )
    return errors


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
