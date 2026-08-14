"""Cross-check Makefile install-<skill> targets against the registry.

The Makefile hand-authors 23 install-<skill> targets (some with shortened
target names) but every one of them invokes ``bash scripts/install.sh
<skill-id>`` with the real registry id as its argument. Validating that
argument catches drift without needing to know each target's alias.
"""
from __future__ import annotations

import re
from pathlib import Path

from scripts.registry.models import Registry

_INSTALL_ARG_RE = re.compile(r"bash scripts/install\.sh ([a-z0-9]+(?:-[a-z0-9]+)*)\s*$", re.MULTILINE)

MAKEFILE_RELATIVE = Path("Makefile")


def validate_install_targets(root: Path, registry: Registry) -> list[str]:
    path = root / MAKEFILE_RELATIVE
    if not path.is_file():
        return []

    text = path.read_text(encoding="utf-8")
    invoked = set(_INSTALL_ARG_RE.findall(text))
    registered = set(registry.skills)

    errors: list[str] = []
    dangling = sorted(invoked - registered)
    if dangling:
        errors.append(
            "error: Makefile installs unregistered skills: " + ", ".join(dangling),
        )
    missing = sorted(registered - invoked)
    if missing:
        errors.append(
            "error: Makefile has no install-<skill> target for: " + ", ".join(missing),
        )
    return errors
