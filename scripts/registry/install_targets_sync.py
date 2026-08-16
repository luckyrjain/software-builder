"""Cross-check Makefile install-<skill> targets against the registry.

The Makefile hand-authors plain and Claude install targets, but every one of
them invokes ``bash scripts/install.sh [--agent <name>] <skill-id>`` with
the real registry id as its trailing argument. Validating that argument
catches drift without needing to know each target's alias.

Static validation follows literal ``include``/``-include`` directives so the
root Makefile can remain a small public entry point while large target groups
live in checked-in include files. Variable-expanded or wildcard includes are
intentionally ignored rather than guessed.
"""
from __future__ import annotations

import re
from pathlib import Path

from scripts.registry.id_diff import report_id_coverage
from scripts.registry.models import Registry

_INSTALL_ARG_RE = re.compile(
    r"bash scripts/install\.sh (?:--\S+ \S+ )*([a-z0-9]+(?:-[a-z0-9]+)*)\s*$",
    re.MULTILINE,
)
_INCLUDE_RE = re.compile(r"^\s*-?include\s+([^#\s]+)\s*(?:#.*)?$", re.MULTILINE)

MAKEFILE_RELATIVE = Path("Makefile")


def _read_makefile_graph(root: Path, relative: Path = MAKEFILE_RELATIVE) -> str:
    """Return Makefile text plus safe literal includes, once each.

    Includes must resolve inside ``root`` and must be literal repository paths.
    This mirrors the static validator's needs without attempting to implement
    GNU Make variable expansion.
    """
    root_resolved = root.resolve()
    seen: set[Path] = set()
    chunks: list[str] = []

    def visit(path: Path) -> None:
        resolved = path.resolve()
        if resolved in seen or not resolved.is_file():
            return
        try:
            resolved.relative_to(root_resolved)
        except ValueError:
            return
        seen.add(resolved)
        text = resolved.read_text(encoding="utf-8")
        chunks.append(text)
        for match in _INCLUDE_RE.finditer(text):
            token = match.group(1)
            if "$" in token or "*" in token or "?" in token or "[" in token:
                continue
            visit(root_resolved / token)

    visit(root_resolved / relative)
    return "\n".join(chunks)


def validate_install_targets(root: Path, registry: Registry) -> list[str]:
    path = root / MAKEFILE_RELATIVE
    if not path.is_file():
        return []

    text = _read_makefile_graph(root)
    invoked = set(_INSTALL_ARG_RE.findall(text))
    registered = set(registry.skills)

    return report_id_coverage(
        invoked,
        registered,
        dangling_label="error: Makefile installs unregistered skills",
        missing_label="error: Makefile has no install-<skill> target for",
    )
