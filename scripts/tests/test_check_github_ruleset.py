"""Tests for GitHub ruleset expectation helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from check_github_ruleset import (  # noqa: E402
    check_pull_request,
    check_status_checks,
    load_expected,
    rule_by_type,
)


def test_expected_ruleset_requires_the_lint_jobs() -> None:
    expected = load_expected()
    rule = rule_by_type(expected["rules"], "required_status_checks")
    assert rule is not None
    contexts = [item["context"] for item in rule["parameters"]["required_status_checks"]]
    assert contexts == ["lint-static", "lint-suites"]


def test_every_required_status_check_is_a_real_workflow_job() -> None:
    """The doc once required a `lint` check after that job had been split into lint-static and
    lint-suites, so `make verify-github-ruleset` failed until someone noticed."""
    import yaml

    workflow = yaml.safe_load((Path(__file__).resolve().parents[2] / ".github" / "workflows" / "lint.yml").read_text(encoding="utf-8"))
    rule = rule_by_type(load_expected()["rules"], "required_status_checks")
    assert rule is not None
    for item in rule["parameters"]["required_status_checks"]:
        assert item["context"] in workflow["jobs"], f"{item['context']} is not a job in lint.yml"


def test_check_status_checks_detects_missing_rule() -> None:
    expected = load_expected()
    errors = check_status_checks({"rules": []}, expected)
    assert any("missing required_status_checks" in error for error in errors)


def test_check_pull_request_rejects_codeowner_for_solo_maintainer() -> None:
    expected = load_expected()
    live = json.loads(json.dumps(expected))
    pull_request = rule_by_type(live["rules"], "pull_request")
    assert pull_request is not None
    pull_request["parameters"]["require_code_owner_review"] = True
    errors = check_pull_request(live, expected)
    assert any("require_code_owner_review" in error for error in errors)
