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
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml import YAMLError as RuamelYAMLError
from ruamel.yaml.scalarstring import LiteralScalarString

from scripts.evals.golden import load_golden_fixtures, run_golden_case


def _make_yaml() -> YAML:
    # Round-trip loader/dumper (matches scripts/registry/backfill_capabilities.py's
    # convention) so a fixture's `# CAVEAT: ...` comments survive a refresh instead of
    # being silently dropped, which plain yaml.safe_load/safe_dump would do.
    rt_yaml = YAML(typ="rt")
    rt_yaml.preserve_quotes = True
    rt_yaml.width = 100000
    # golden fixtures indent sequence dashes two spaces under their key (`assertions:\n  - type: ...`),
    # unlike skills.yaml's flush-left convention that scripts/registry/backfill_capabilities.py matches.
    rt_yaml.indent(mapping=2, sequence=4, offset=2)
    return rt_yaml


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: recorded output must be a JSON object")
    return data


def _as_scalar(value: str) -> Any:
    # A block literal (`|`) is YAML-spec line-break-normalizing, so a string carrying
    # literal \r\n would silently come back as \n on the next load — only use the
    # readable block style when that's lossless; a \r-bearing string still round-trips
    # exactly via ruamel's normal quoted-scalar escaping.
    if "\n" in value and "\r" not in value:
        return LiteralScalarString(value)
    return value


def _merge_recorded_output(existing: Any, new: Any) -> Any:
    """Update a loaded ruamel node with freshly captured `recorded_output` data,
    editing matching mapping keys / sequence indices in place rather than replacing
    the whole node — ruamel attaches a `# CAVEAT: ...` comment on a recorded_output
    field to that specific node, so wholesale replacement (the previous approach)
    silently drops any comment attached inside recorded_output, as opposed to one
    attached to an assertions: list item (a sibling, never-replaced node), which
    survives either way.
    """
    if isinstance(new, dict):
        if not isinstance(existing, dict):
            return {key: _merge_recorded_output(None, val) for key, val in new.items()}
        for key in list(existing.keys()):
            if key not in new:
                del existing[key]
        for key, val in new.items():
            existing[key] = _merge_recorded_output(existing.get(key), val)
        return existing
    if isinstance(new, list):
        if not (isinstance(existing, list) and len(existing) == len(new)):
            return [_merge_recorded_output(None, val) for val in new]
        for index, val in enumerate(new):
            existing[index] = _merge_recorded_output(existing[index], val)
        return existing
    if isinstance(new, str):
        return _as_scalar(new)
    return new


def _golden_dir_for_fixture(fixture_path: Path) -> Path:
    for candidate in fixture_path.parents:
        if candidate.name == "golden":
            return candidate
    raise ValueError(f"{fixture_path}: not under an evals/golden/ directory")


def refresh_fixture(
    fixture_path: Path,
    recorded_output: dict[str, Any],
    *,
    dry_run: bool,
    note: str,
) -> None:
    rt_yaml = _make_yaml()
    raw = rt_yaml.load(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{fixture_path}: root must be a mapping")

    raw["recorded_output"] = _merge_recorded_output(raw.get("recorded_output"), recorded_output)
    refresh_meta = raw.setdefault("refresh_meta", {})
    if not isinstance(refresh_meta, dict):
        raise ValueError(f"{fixture_path}: refresh_meta must be a mapping")
    refresh_meta["last_refreshed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    refresh_meta["refresh_note"] = note

    buf = io.StringIO()
    rt_yaml.dump(raw, buf)
    dumped = buf.getvalue()

    if dry_run:
        print(dumped)
        return

    fixture_path.write_text(dumped, encoding="utf-8")


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
    except (ValueError, json.JSONDecodeError, OSError, RuamelYAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        return 0

    print(f"updated {fixture_path}")

    if args.verify:
        cases = load_golden_fixtures(_golden_dir_for_fixture(fixture_path))
        match = [c for c in cases if c.path.resolve() == fixture_path]
        if not match:
            print("error: could not reload fixture for verification", file=sys.stderr)
            return 1
        result = run_golden_case(match[0])
        if not result.passed:
            for err in result.messages:
                print(err, file=sys.stderr)
            return 1
        print("verify: assertions passed")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
