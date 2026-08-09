#!/usr/bin/env python3
"""Refresh Tier-3 golden eval fixtures from a captured model output JSON file.

CI replays recorded_output statically (no live LLM). Maintainers refresh goldens explicitly when
skill behavior intentionally changes.

Usage:
  # 1. Run the skill in a real session and save structured output to /tmp/out.json
  # 2. Refresh the fixture:
  python3 -m scripts.evals.golden_refresh \\
    --fixture evals/golden/pr-review/chat-only-not-posted.yaml \\
    --recorded-output /tmp/out.json \\
    --dry-run
  python3 -m scripts.evals.golden_refresh \\
    --fixture evals/golden/pr-review/chat-only-not-posted.yaml \\
    --recorded-output /tmp/out.json

Then run: python3 -m scripts.evals --tier 3
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from scripts.evals.golden import load_golden_fixtures, run_golden_case


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: recorded output must be a JSON object")
    return data


def refresh_fixture(
    fixture_path: Path,
    recorded_output: dict[str, Any],
    *,
    dry_run: bool,
    note: str,
) -> None:
    raw = yaml.safe_load(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{fixture_path}: root must be a mapping")

    raw["recorded_output"] = recorded_output
    refresh_meta = raw.setdefault("refresh_meta", {})
    if not isinstance(refresh_meta, dict):
        raise ValueError(f"{fixture_path}: refresh_meta must be a mapping")
    refresh_meta["last_refreshed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    refresh_meta["refresh_note"] = note

    if dry_run:
        print(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True))
        return

    fixture_path.write_text(
        yaml.safe_dump(raw, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", required=True, type=Path, help="Path to golden/*.yaml fixture")
    parser.add_argument(
        "--recorded-output",
        required=True,
        type=Path,
        help="JSON file with new recorded_output object",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print YAML without writing")
    parser.add_argument(
        "--note",
        default="manual refresh via golden_refresh.py",
        help="Stored in refresh_meta.refresh_note",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run golden assertions after write",
    )
    args = parser.parse_args(argv)

    fixture_path = args.fixture.resolve()
    if not fixture_path.is_file():
        print(f"error: fixture not found: {fixture_path}", file=sys.stderr)
        return 1

    try:
        recorded = _load_json(args.recorded_output.resolve())
        refresh_fixture(fixture_path, recorded, dry_run=args.dry_run, note=args.note)
    except (ValueError, json.JSONDecodeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        return 0

    print(f"updated {fixture_path}")

    if args.verify:
        cases = load_golden_fixtures(fixture_path.parent.parent)
        match = [c for c in cases if c.path.resolve() == fixture_path]
        if not match:
            print("error: could not reload fixture for verification", file=sys.stderr)
            return 1
        result = run_golden_case(match[0])
        if not result.passed:
            for err in result.errors:
                print(err, file=sys.stderr)
            return 1
        print("verify: assertions passed")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
