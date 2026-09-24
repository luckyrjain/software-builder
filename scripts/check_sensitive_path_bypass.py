#!/usr/bin/env python3
"""Scheduled sensitive-path-bypass scanner for the F1 review-evidence gate (Track B).

Lists PRs merged in the lookback window, classifies each with `scripts.sensitive_path_match`
(the same shared matcher `check_review_evidence.py`'s `check`/`analyze` subcommands use, so this
scanner's notion of "sensitive" never drifts from the gate's own), and cross-checks every
sensitive one against a passing `review-evidence-check` run on its **head SHA** (`headRefOid`) --
not its merge commit. This repo is squash-only (`docs/github-ruleset-main.json`'s
`allowed_merge_methods: ["squash"]`), so a merge commit is always a brand-new SHA distinct from
the head SHA `review-evidence-check`/`-post` actually ran against, and GitHub's Checks API never
copies check-runs onto it -- querying the merge commit alone (PR #298's originally shipped
behavior, LENS-B-1) returns no check-runs at all for essentially every merged PR, producing a
false bypass finding on every run. `fetch_check_runs_for_merged_pr` queries the head SHA first
and the merge commit SHA too, as defense-in-depth, when it differs from the head SHA. A sensitive
PR that merged without a passing check on either almost certainly went through the GitHub
ruleset's bypass-actor path -- this turns that from "check the audit log if you remember" into a
loud, automatic tracking issue (design doc:
docs/superpowers/specs/2026-09-24-f1-review-evidence-gate-design.md,
`check_sensitive_path_bypass.py` row and Failure-strategy table).

Also implements architecture review Condition 2 (a cheap credential-health signal): if the scan
window contains at least one sensitive PR and *none* of them show a successful
`review-evidence-post` check run, files a second tracking issue flagging the bot credential
(PAT/App install) as possibly expired or misconfigured. Known limitation, stated in the filed
issue itself: this can't distinguish "the bot never ran" from "a genuine second human approval
satisfied the gate and the bot was never needed" -- it's a cheap signal, not a precise one.

"Who alerts on the alerter": any unhandled failure in this script itself files a tracking issue
too (a distinct marker), not just relying on GitHub's easy-to-miss default workflow-failure
email -- the same "fail loud" doctrine, turned on itself.

Fail-closed on the scan target: a malformed/empty `docs/sensitive-paths.yaml` is a real error
(exit 2), not "nothing to scan".
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import check_review_evidence, sensitive_path_match  # noqa: E402

DEFAULT_REPO = check_review_evidence.DEFAULT_REPO

BYPASS_MARKER_TEMPLATE = "[sensitive-path-bypass] PR #{number}"
ALERTER_FAILURE_MARKER = "[sensitive-path-bypass][alerter-failure]"
BOT_HEALTH_MARKER = "[sensitive-path-bypass][bot-credential-health]"


def fetch_merged_prs(repo: str, since_days: int) -> list[dict[str, Any]]:
    """Return merged PRs (number, mergedAt, mergeCommit, headRefOid, files) merged in the last
    `since_days`.

    `headRefOid` (the PR's head SHA -- where `review-evidence-check`/`-post` actually ran) is
    fetched alongside `mergeCommit` (the PR's squash-merge commit on the base branch) because
    this repo is squash-only (`docs/github-ruleset-main.json`'s `allowed_merge_methods:
    ["squash"]`): a squash merge produces a brand-new commit SHA distinct from the head SHA, and
    GitHub's Checks API never copies check-runs from the head SHA onto that new commit (PR #298
    remediation, LENS-B-1).
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime("%Y-%m-%d")
    stdout = check_review_evidence.run_gh(
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "merged",
            "--search",
            f"merged:>={cutoff}",
            "--json",
            "number,mergedAt,mergeCommit,headRefOid,files",
            "--limit",
            "200",
        ],
    )
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise check_review_evidence.GhApiError(f"could not parse `gh pr list` output: {exc}") from exc
    if not isinstance(data, list):
        raise check_review_evidence.GhApiError("`gh pr list` did not return a JSON array")
    return data


def fetch_check_runs(repo: str, sha: str) -> list[dict[str, Any]]:
    """Return every check-run recorded against commit `sha` (paginated Checks API)."""
    stdout = check_review_evidence.run_gh(["api", f"repos/{repo}/commits/{sha}/check-runs", "--paginate"])
    check_runs: list[dict[str, Any]] = []
    for page in check_review_evidence.parse_paginated_json(stdout):
        if not isinstance(page, dict):
            raise check_review_evidence.GhApiError("`gh api .../check-runs` did not return a JSON object")
        runs = page.get("check_runs")
        if not isinstance(runs, list):
            raise check_review_evidence.GhApiError("`gh api .../check-runs` response missing a 'check_runs' array")
        check_runs.extend(runs)
    return check_runs


def check_run_succeeded(check_runs: list[dict[str, Any]], name: str) -> bool:
    """True iff some check run named `name` in `check_runs` concluded successfully."""
    return any(run.get("name") == name and run.get("conclusion") == "success" for run in check_runs)


def fetch_check_runs_for_merged_pr(repo: str, *, head_sha: str | None, merge_sha: str | None) -> list[dict[str, Any]]:
    """Return every check-run recorded against a merged PR, queried by its head SHA (primary --
    this repo is squash-only, and `review-evidence-check`/`-post` only ever ran against the PR's
    head SHA, never the squash-merge commit; see `fetch_merged_prs`'s docstring) and, as
    defense-in-depth for a repo that might allow other merge strategies, its merge commit SHA too
    when that differs from the head SHA (PR #298 remediation, LENS-B-1: the original
    implementation queried `mergeCommit.oid` only, which returns no check-runs at all for a
    squash-merged PR -- silently reporting a false bypass on every merged sensitive-path PR).
    """
    check_runs: list[dict[str, Any]] = []
    if head_sha:
        check_runs.extend(fetch_check_runs(repo, head_sha))
    if merge_sha and merge_sha != head_sha:
        check_runs.extend(fetch_check_runs(repo, merge_sha))
    return check_runs


def classify_merged_pr(
    pr: dict[str, Any],
    *,
    spec: sensitive_path_match.SensitivePathList,
    diff_text: str,
    check_runs: list[dict[str, Any]],
) -> tuple[sensitive_path_match.SensitivityResult, dict[str, Any] | None]:
    """Pure decision for one merged PR, given its already-fetched diff text and check runs.

    Returns (sensitivity result, bypass record or None). A bypass record is produced only when
    the PR is sensitive AND has no successful `review-evidence-check` run in `check_runs`
    (queried by the caller against the PR's head SHA and, as defense-in-depth, its merge commit
    SHA -- see `fetch_check_runs_for_merged_pr`).
    """
    files = [f.get("path") for f in pr.get("files", []) if isinstance(f, dict) and f.get("path")]
    result = sensitive_path_match.classify(diff_text, spec, changed_paths=files)
    if not result.sensitive:
        return result, None
    if check_run_succeeded(check_runs, "review-evidence-check"):
        return result, None
    record = {
        "number": pr.get("number"),
        "merged_at": pr.get("mergedAt"),
        "matched_globs": list(result.matched_globs),
        "matched_content_patterns": list(result.matched_content_patterns),
    }
    return result, record


def bot_credential_health(sensitive_pr_check_runs: list[list[dict[str, Any]]]) -> bool | None:
    """Architecture review Condition 2's cheap signal.

    Returns True if at least one sensitive PR in the window shows a successful
    `review-evidence-post` check run, False if the window had sensitive PRs but none show one
    (worth flagging), or None if the window had no sensitive PRs at all (nothing to judge).
    """
    if not sensitive_pr_check_runs:
        return None
    return any(check_run_succeeded(check_runs, "review-evidence-post") for check_runs in sensitive_pr_check_runs)


def tracking_issue_exists(repo: str, marker: str) -> bool:
    """True iff an open issue whose title contains `marker` already exists (dedupe)."""
    stdout = check_review_evidence.run_gh(
        ["issue", "list", "--repo", repo, "--state", "open", "--search", f'"{marker}" in:title', "--json", "number,title"],
    )
    try:
        issues = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise check_review_evidence.GhApiError(f"could not parse `gh issue list` output: {exc}") from exc
    if not isinstance(issues, list):
        raise check_review_evidence.GhApiError("`gh issue list` did not return a JSON array")
    return any(marker in (issue.get("title") or "") for issue in issues)


def open_tracking_issue(repo: str, title: str, body: str, *, dry_run: bool) -> None:
    if dry_run:
        print(f"[dry-run] would open tracking issue: {title}")
        return
    check_review_evidence.run_gh(["issue", "create", "--repo", repo, "--title", title, "--body", body])


def ensure_bypass_issue(repo: str, record: dict[str, Any], *, dry_run: bool) -> None:
    marker = BYPASS_MARKER_TEMPLATE.format(number=record["number"])
    if tracking_issue_exists(repo, marker):
        return
    title = f"{marker}: merged without a passing review-evidence-check run"
    body = (
        f"PR #{record['number']} (merged {record.get('merged_at')}) touched the sensitive-path "
        f"list (globs={record['matched_globs']}, content_patterns={record['matched_content_patterns']}) "
        "but merged without a passing `review-evidence-check` run on its merge commit -- "
        "likely the GitHub ruleset's bypass-actor path. Filed automatically by "
        "`scripts/check_sensitive_path_bypass.py` (design doc: "
        "docs/superpowers/specs/2026-09-24-f1-review-evidence-gate-design.md)."
    )
    open_tracking_issue(repo, title, body, dry_run=dry_run)


def ensure_bot_health_issue(repo: str, since_days: int, *, dry_run: bool) -> None:
    if tracking_issue_exists(repo, BOT_HEALTH_MARKER):
        return
    title = f"{BOT_HEALTH_MARKER}: no successful review-evidence-post run in the last {since_days} day(s)"
    body = (
        "At least one sensitive-path PR merged in the scan window, but no `review-evidence-post` "
        "check run succeeded on any of them -- the bot credential (PAT or GitHub App install) may "
        "be expired, revoked, or misconfigured (architecture review Condition 2).\n\n"
        "Known limitation: this signal cannot distinguish 'the bot never ran' from 'a genuine "
        "second human approval satisfied the gate and the bot was never needed' -- verify "
        "manually before rotating the credential. Filed automatically by "
        "`scripts/check_sensitive_path_bypass.py`."
    )
    open_tracking_issue(repo, title, body, dry_run=dry_run)


def report_own_failure(repo: str, exc: BaseException, *, dry_run: bool) -> None:
    """"Who alerts on the alerter": loudly surface this script's own failure with the same
    mechanism it uses for bypasses, instead of relying only on GitHub's easy-to-miss default
    workflow-failure email (design doc, Failure strategy).
    """
    title = f"{ALERTER_FAILURE_MARKER}: scripts/check_sensitive_path_bypass.py failed"
    body = (
        "`scripts/check_sensitive_path_bypass.py`'s scheduled scan raised an unhandled error and "
        f"did not complete:\n\n```\n{exc}\n```\n\n"
        "Sensitive-path bypass detection did not run this cycle -- investigate and fix, then "
        "re-run manually (`python3 scripts/check_sensitive_path_bypass.py`)."
    )
    try:
        if tracking_issue_exists(repo, ALERTER_FAILURE_MARKER):
            print(f"error: {exc}", file=sys.stderr)
            return
        open_tracking_issue(repo, title, body, dry_run=dry_run)
    except Exception as issue_exc:  # last-resort: the alerter's own alerting path must never
        # itself raise past this point uncaught -- stderr + a non-zero exit from main() is the
        # final fallback if even opening the failure-tracking issue doesn't work.
        print(f"error: could not open own-failure tracking issue: {issue_exc}", file=sys.stderr)
    print(f"error: {exc}", file=sys.stderr)


def _run(repo: str, since_days: int, sensitive_path_list: Path, *, dry_run: bool) -> int:
    spec = sensitive_path_match.load_sensitive_path_list(sensitive_path_list)
    prs = fetch_merged_prs(repo, since_days)

    bypassed: list[dict[str, Any]] = []
    sensitive_pr_check_runs: list[list[dict[str, Any]]] = []

    for pr in prs:
        number = pr.get("number")
        merge_sha = (pr.get("mergeCommit") or {}).get("oid")
        head_sha = pr.get("headRefOid")
        if number is None or (not merge_sha and not head_sha):
            continue

        diff_text = check_review_evidence.fetch_pr_diff(repo, number)
        check_runs = fetch_check_runs_for_merged_pr(repo, head_sha=head_sha, merge_sha=merge_sha)
        result, record = classify_merged_pr(pr, spec=spec, diff_text=diff_text, check_runs=check_runs)

        if result.sensitive:
            sensitive_pr_check_runs.append(check_runs)
        if record is not None:
            bypassed.append(record)

    for record in bypassed:
        ensure_bypass_issue(repo, record, dry_run=dry_run)

    healthy = bot_credential_health(sensitive_pr_check_runs)
    if healthy is False:
        ensure_bot_health_issue(repo, since_days, dry_run=dry_run)

    print(
        f"ok: scanned {len(prs)} merged PR(s) from the last {since_days} day(s) -- "
        f"{len(bypassed)} sensitive-path bypass(es) found, bot_credential_healthy={healthy}",
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default=DEFAULT_REPO, help="owner/repo (default: $GITHUB_REPOSITORY or luckyrjain/software-builder)")
    parser.add_argument(
        "--since-days",
        type=int,
        default=8,
        help="lookback window in days (default: 8 -- a weekly cron plus a 1-day overlap buffer)",
    )
    parser.add_argument(
        "--sensitive-path-list",
        type=Path,
        default=sensitive_path_match.DEFAULT_SENSITIVE_PATH_LIST,
        help="path to docs/sensitive-paths.yaml",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print planned issue creation instead of calling `gh issue create`",
    )
    args = parser.parse_args(argv)

    try:
        return _run(args.repo, args.since_days, args.sensitive_path_list, dry_run=args.dry_run)
    except Exception as exc:  # this IS the "who alerts on the alerter" path -- any failure here
        # must still loudly surface via a tracking issue, not just an Actions failure email a
        # solo maintainer could miss (see report_own_failure's docstring).
        report_own_failure(args.repo, exc, dry_run=args.dry_run)
        return 2


if __name__ == "__main__":
    sys.exit(main())
