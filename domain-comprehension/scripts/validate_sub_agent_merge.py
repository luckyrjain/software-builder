#!/usr/bin/env python3
"""Validate domain-comprehension sub-agent merge JSON payloads."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_manifest_yaml import CONFIDENCE, _invalid_enum  # noqa: E402

REQUIRED_TOP = ("repo", "phase", "findings", "open_questions", "conflicts", "files_read")


def validate_merge(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["root must be a JSON object"]

    for key in REQUIRED_TOP:
        if key not in data:
            errors.append(f"missing required field: {key}")

    # A key missing entirely is already reported by the REQUIRED_TOP loop above; the checks below
    # only need to fire for a *present* value (including an explicit `null`) that fails its type
    # check, so a single problem doesn't produce two error messages.
    repo = data.get("repo")
    if "repo" in data and (not isinstance(repo, str) or not repo.strip()):
        errors.append("repo must be a non-empty string")

    phase = data.get("phase")
    if "phase" in data and (not isinstance(phase, str) or not phase.strip()):
        errors.append("phase must be a non-empty string")

    findings = data.get("findings")
    if "findings" in data:
        if not isinstance(findings, list):
            errors.append("findings must be an array")
        else:
            for index, item in enumerate(findings):
                prefix = f"findings[{index}]"
                if not isinstance(item, dict):
                    errors.append(f"{prefix} must be an object")
                    continue
                for key in ("evidence", "conclusion", "confidence"):
                    if key not in item:
                        errors.append(f"{prefix} missing required field: {key}")
                for key in ("evidence", "conclusion"):
                    if key in item and not isinstance(item.get(key), str):
                        errors.append(f"{prefix}.{key} must be a string")
                conf = item.get("confidence")
                if "confidence" in item and _invalid_enum(conf, CONFIDENCE):
                    errors.append(f"{prefix}.confidence must be HIGH|MEDIUM|LOW|UNKNOWN")

    for list_field in ("open_questions", "conflicts", "files_read"):
        if list_field not in data:
            continue
        value = data.get(list_field)
        if not isinstance(value, list):
            errors.append(f"{list_field} must be an array")
        else:
            for index, item in enumerate(value):
                if not isinstance(item, str):
                    errors.append(f"{list_field}[{index}] must be a string")

    return errors


def main(argv: list[str] | None = None) -> int:
    paths = argv if argv is not None else sys.argv[1:]
    if not paths:
        print("usage: validate_sub_agent_merge.py <file.json>...", file=sys.stderr)
        return 2
    exit_code = 0
    for path_str in paths:
        path = Path(path_str)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"{path}: {exc}", file=sys.stderr)
            exit_code = 1
            continue
        errors = validate_merge(data)
        if errors:
            exit_code = 1
            print(f"{path}: validation failed", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
        else:
            print(f"{path}: ok")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
