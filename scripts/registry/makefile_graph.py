"""Read the repository's Make target graph as one text blob.

Validators that need to reason about what `make` would see -- which targets are
declared `.PHONY`, which prerequisites a rule carries -- need the root Makefile
plus the files it includes, not just the root file. This resolves literal
``include``/``-include`` directives so the root Makefile can stay a small public
entry point while large target groups live in checked-in include files.

Variable-expanded or wildcard includes are intentionally ignored rather than
guessed: implementing GNU Make's expansion here would be a second, divergent
Make implementation, and a validator that guesses wrong is worse than one that
declines to look.
"""

from __future__ import annotations

import re
from pathlib import Path

_INCLUDE_RE = re.compile(r"^\s*-?include\s+([^#]+?)\s*(?:#.*)?$", re.MULTILINE)

MAKEFILE_RELATIVE = Path("Makefile")


def read_makefile_graph(root: Path, relative: Path = MAKEFILE_RELATIVE) -> str:
    """Return Makefile text plus safe literal includes, once each.

    Includes must resolve inside ``root`` and must be literal repository paths.
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
            # GNU Make allows multiple space-separated files on one include line.
            for token in match.group(1).split():
                if "$" in token or "*" in token or "?" in token or "[" in token:
                    continue
                visit(root_resolved / token)

    visit(root_resolved / relative)
    return "\n".join(chunks)
