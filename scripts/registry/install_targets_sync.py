"""Cross-check Makefile install-<skill> targets against the registry.

The Makefile hand-authors 46 install targets (23 skills x plain + `install-
claude-<skill>` forms, some with shortened target names) but every one of
them invokes ``bash scripts/install.sh [--agent <name>] <skill-id>`` with
the real registry id as its trailing argument. Validating that argument
catches drift without needing to know each target's alias.
"""
from __future__ import annotations

import re
from pathlib import Path

from scripts.registry.id_diff import report_id_coverage
from scripts.registry.models import Registry

# The skill id is always the final argument; `--agent claude-user` (or any
# other `--flag value` pair) may precede it, so skip flag/value pairs rather
# than assuming the id immediately follows `install.sh` -- otherwise every
# `install-claude-<skill>` target's `--agent claude-user <skill>` form is
# invisible to this check (verified: it's half of the 46 install.sh lines).
_INSTALL_ARG_RE = re.compile(
    r"bash scripts/install\.sh (?:--\S+ \S+ )*([a-z0-9]+(?:-[a-z0-9]+)*)\s*$",
    re.MULTILINE,
)

MAKEFILE_RELATIVE = Path("Makefile")


def validate_install_targets(root: Path, registry: Registry) -> list[str]:
    path = root / MAKEFILE_RELATIVE
    if not path.is_file():
        return []

    text = path.read_text(encoding="utf-8")
    invoked = set(_INSTALL_ARG_RE.findall(text))
    registered = set(registry.skills)

    return report_id_coverage(
        invoked,
        registered,
        dangling_label="error: Makefile installs unregistered skills",
        missing_label="error: Makefile has no install-<skill> target for",
    )
