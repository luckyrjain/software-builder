#!/usr/bin/env python3
"""Verify the live GitHub main-branch ruleset matches docs/github-ruleset-main.json."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = "luckyrjain/software-builder"
RULESET_ID = 20535141
EXPECTED_PATH = Path(__file__).resolve().parents[1] / "docs" / "github-ruleset-main.json"


def load_expected() -> dict[str, Any]:
    data = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    data.pop("_documentation", None)
    return data


def fetch_live_ruleset() -> dict[str, Any]:
    result = subprocess.run(
        ["gh", "api", f"repos/{REPO}/rulesets/{RULESET_ID}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
        raise RuntimeError(
            "could not read ruleset via gh api — authenticate with `gh auth login` "
            "and ensure the token can read repository rulesets",
        )
    return json.loads(result.stdout)


def rule_by_type(rules: list[dict[str, Any]], rule_type: str) -> dict[str, Any] | None:
    for rule in rules:
        if rule.get("type") == rule_type:
            return rule
    return None


def check_status_checks(live: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    live_rule = rule_by_type(live.get("rules", []), "required_status_checks")
    expected_rule = rule_by_type(expected.get("rules", []), "required_status_checks")
    if expected_rule is None:
        return errors

    if live_rule is None:
        errors.append("missing required_status_checks rule")
        return errors

    live_params = live_rule.get("parameters", {})
    expected_params = expected_rule.get("parameters", {})
    live_contexts = {
        item.get("context")
        for item in live_params.get("required_status_checks", [])
        if isinstance(item, dict)
    }
    expected_contexts = {
        item.get("context")
        for item in expected_params.get("required_status_checks", [])
        if isinstance(item, dict)
    }
    if live_contexts != expected_contexts:
        errors.append(
            f"required status check contexts mismatch: live={sorted(live_contexts)} "
            f"expected={sorted(expected_contexts)}",
        )

    for key in ("strict_required_status_checks_policy", "do_not_enforce_on_create"):
        if live_params.get(key) != expected_params.get(key):
            errors.append(
                f"required_status_checks.{key}: live={live_params.get(key)!r} "
                f"expected={expected_params.get(key)!r}",
            )
    return errors


def check_pull_request(live: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    live_rule = rule_by_type(live.get("rules", []), "pull_request")
    expected_rule = rule_by_type(expected.get("rules", []), "pull_request")
    if expected_rule is None:
        return errors
    if live_rule is None:
        errors.append("missing pull_request rule")
        return errors

    live_params = live_rule.get("parameters", {})
    expected_params = expected_rule.get("parameters", {})
    for key in (
        "required_approving_review_count",
        "require_code_owner_review",
        "required_review_thread_resolution",
    ):
        if live_params.get(key) != expected_params.get(key):
            errors.append(
                f"pull_request.{key}: live={live_params.get(key)!r} "
                f"expected={expected_params.get(key)!r}",
            )

    live_methods = set(live_params.get("allowed_merge_methods", []))
    expected_methods = set(expected_params.get("allowed_merge_methods", []))
    if live_methods != expected_methods:
        errors.append(
            f"pull_request.allowed_merge_methods: live={sorted(live_methods)} "
            f"expected={sorted(expected_methods)}",
        )
    return errors


def main() -> int:
    expected = load_expected()
    try:
        live = fetch_live_ruleset()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    errors: list[str] = []
    if live.get("enforcement") != expected.get("enforcement"):
        errors.append(
            f"enforcement: live={live.get('enforcement')!r} expected={expected.get('enforcement')!r}",
        )

    live_types = {rule.get("type") for rule in live.get("rules", [])}
    expected_types = {rule.get("type") for rule in expected.get("rules", [])}
    for rule_type in sorted(expected_types - live_types):
        errors.append(f"missing rule type: {rule_type}")

    errors.extend(check_status_checks(live, expected))
    errors.extend(check_pull_request(live, expected))

    if errors:
        print("error: GitHub ruleset does not match docs/github-ruleset-main.json:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        print(
            "\nhint: Settings → Rules → Rulesets → main, or apply docs/github-ruleset-main.json "
            "via repo-admin `gh api PUT repos/luckyrjain/software-builder/rulesets/20535141`",
            file=sys.stderr,
        )
        return 1

    print("ok: GitHub ruleset matches docs/github-ruleset-main.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
