#!/usr/bin/env python3
"""Print each registered skill's directory path, one per line.

Used to build a repo-wide reference-validator --exclude list that skips
skill directories (already covered by the per-skill scripts/lint-dangling-md-links.sh
Makefile targets) without hand-maintaining a second, driftable copy of the
skill list — see validate_references.py's --exclude flag and CHANGELOG.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.registry.load import load_registry


def main() -> int:
    registry = load_registry(ROOT)
    for path in sorted(entry.path for entry in registry.skills.values()):
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
