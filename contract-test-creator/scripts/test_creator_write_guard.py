#!/usr/bin/env python3
"""Source-tree adapter for the canonical packaged test-creator write guard."""

from pathlib import Path
import runpy


CANONICAL = Path(__file__).resolve().parents[2] / "scripts" / "test_creator_write_guard.py"


def main() -> None:
    if not CANONICAL.is_file():
        raise SystemExit(f"canonical write guard not found: {CANONICAL}")
    runpy.run_path(str(CANONICAL), run_name="__main__")


if __name__ == "__main__":
    main()
