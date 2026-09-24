#!/usr/bin/env python3
"""Enforce the F1 review-evidence gate for one PR (Track B).

Two subcommands:

`check` (the default -- `--pr <n>` alone means `check --pr <n>`, matching the design doc's
`scripts/check_review_evidence.py --pr <n>` CLI contract): `review-evidence-check`'s own logic
(the CI job of that name, in `.github/workflows/review-evidence.yml`). Fetches the PR's current
head SHA and full diff text via `gh` (never a repository checkout -- see
docs/superpowers/specs/2026-09-24-f1-review-evidence-gate-design.md, APIs table), classifies
the PR as sensitive-or-not via `scripts.sensitive_path_match`, and, if sensitive, requires the
GitHub Reviews API to show the *most recent* review per `user.login`, at the current head SHA,
as `APPROVED` from a login other than the PR author.

Exit codes for `check` (design doc, `check_review_evidence.py` row):
    0 -- clean (not sensitive, or sensitive with a qualifying approval)
    1 -- sensitive, evidence missing
    2 -- cannot determine (API error, malformed/empty sensitive-path list) -- fail closed, never
         treated as "nothing is sensitive"

`analyze`: classifies the same way, and for a sensitive PR writes a verdict artifact. Invoked
directly by the `review-evidence-post` job in `.github/workflows/review-evidence-post.yml` --
**not** by a separate `pull_request`-triggered job. An earlier revision had a standalone
`review-evidence-analyze` CI job run this and hand its artifact to `review-evidence-post` across
a `workflow_run` boundary; that was a trust-boundary bypass (PR #298 remediation, LENS-A-1): a
`pull_request`-triggered job's own step definitions are resolved from the PR's own branch, so a
same-repo PR could forge the "classify" step itself. `review-evidence-post` now calls this
subcommand itself, from a checkout it can prove is base-branch-pinned (see that workflow file's
header comment for the full reasoning) -- so nothing this subcommand's *caller* computed on a
PR branch is ever trusted, only what this subcommand computes against the base-pinned code that
is running it. Phase 0 ships no real review pass -- see `build_verdict`'s `TODO(condition-1)`.

The PR diff text both subcommands read is untrusted, third-party content (any PR author can
write it) -- it is parsed here purely as data (glob/regex matching over its text), never
executed or treated as instructions, per docs/skill-framework/shared/prompt-injection.md.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import sensitive_path_match  # noqa: E402

DEFAULT_REPO = os.environ.get("GITHUB_REPOSITORY", "luckyrjain/software-builder")


class GhApiError(RuntimeError):
    """Raised when a `gh` invocation fails or returns unparseable output."""


def run_gh(args: list[str]) -> str:
    """Run `gh <args>`, returning stdout. Raises GhApiError on any failure."""
    try:
        result = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    except OSError as exc:
        raise GhApiError(f"could not execute gh {' '.join(args)}: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise GhApiError(f"gh {' '.join(args)} failed: {detail}")
    return result.stdout


def parse_paginated_json(text: str) -> list[Any]:
    """Decode zero or more concatenated top-level JSON values from `--paginate` output.

    `gh api ... --paginate` prints each page's JSON body one after another with no separator
    (e.g. `[...][...]` for an array-returning endpoint) -- not valid JSON as a whole. Decoding
    with a raw_decode loop, rather than assuming any particular `--jq`-imposed line framing,
    works regardless of how many pages were fetched (including zero, or exactly one).
    """
    decoder = json.JSONDecoder()
    values: list[Any] = []
    index = 0
    length = len(text)
    while index < length:
        while index < length and text[index].isspace():
            index += 1
        if index >= length:
            break
        try:
            value, end = decoder.raw_decode(text, index)
        except json.JSONDecodeError as exc:
            raise GhApiError(f"could not parse paginated gh api output: {exc}") from exc
        values.append(value)
        index = end
    return values


def fetch_pr_metadata(repo: str, pr_number: int) -> tuple[str, str]:
    """Return (head_sha, author_login) for `pr_number`."""
    stdout = run_gh(["pr", "view", str(pr_number), "--repo", repo, "--json", "headRefOid,author"])
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise GhApiError(f"could not parse `gh pr view` output: {exc}") from exc
    head_sha = data.get("headRefOid")
    author_login = (data.get("author") or {}).get("login")
    if not head_sha or not author_login:
        raise GhApiError("`gh pr view` returned incomplete PR metadata (missing headRefOid/author.login)")
    return head_sha, author_login


def fetch_pr_diff(repo: str, pr_number: int) -> str:
    """Return the PR's full unified-diff patch text (`gh pr diff`'s output, not `--name-only`)."""
    return run_gh(["pr", "diff", str(pr_number), "--repo", repo])


def fetch_pr_reviews(repo: str, pr_number: int) -> list[dict[str, Any]]:
    """Return every review ever left on `pr_number`, GitHub's own chronological order."""
    stdout = run_gh(["api", f"repos/{repo}/pulls/{pr_number}/reviews", "--paginate"])
    reviews: list[dict[str, Any]] = []
    for page in parse_paginated_json(stdout):
        if not isinstance(page, list):
            raise GhApiError("`gh api .../reviews` did not return a JSON array")
        reviews.extend(page)
    return reviews


def most_recent_review_per_login(reviews: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Reduce a PR's full reviews list to each reviewer's single most recent verdict.

    The Reviews API returns every historical review, not one per reviewer -- an "any entry
    matches" check would accept a stale APPROVED from a reviewer who later left
    CHANGES_REQUESTED at the *same* commit. This is a load-bearing correctness property (design
    doc, round-3 revision history, finding 8), not just documentation.
    """
    latest: dict[str, dict[str, Any]] = {}
    latest_submitted_at: dict[str, str] = {}
    for review in reviews:
        user = review.get("user") or {}
        login = user.get("login")
        submitted_at = review.get("submitted_at")
        state = review.get("state")
        if not login or not submitted_at or state == "PENDING":
            continue
        if login not in latest_submitted_at or submitted_at >= latest_submitted_at[login]:
            latest[login] = review
            latest_submitted_at[login] = submitted_at
    return latest


def has_valid_approval(reviews: list[dict[str, Any]], *, head_sha: str, author_login: str) -> bool:
    """True iff some reviewer other than the author's most recent review is APPROVED at head_sha.

    Login comparison is case-insensitive (GitHub usernames are case-insensitive) so a
    same-account approval can't slip through on a case variance.
    """
    author_lower = author_login.lower()
    for login, review in most_recent_review_per_login(reviews).items():
        if login.lower() == author_lower:
            continue
        if review.get("state") != "APPROVED":
            continue
        if review.get("commit_id") != head_sha:
            continue
        return True
    return False


def run_check(*, repo: str, pr_number: int, sensitive_path_list: Path) -> int:
    """review-evidence-check's own logic. See module docstring for exit codes."""
    try:
        spec = sensitive_path_match.load_sensitive_path_list(sensitive_path_list)
    except sensitive_path_match.SensitivePathListError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        head_sha, author_login = fetch_pr_metadata(repo, pr_number)
        diff_text = fetch_pr_diff(repo, pr_number)
    except GhApiError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    result = sensitive_path_match.classify(diff_text, spec)
    if not result.sensitive:
        print(f"ok: PR #{pr_number} does not touch any sensitive path or content pattern -- no review evidence required")
        return 0

    print(
        f"PR #{pr_number} touches sensitive path(s)/pattern(s): "
        f"globs={list(result.matched_globs)} content_patterns={list(result.matched_content_patterns)}",
    )

    try:
        reviews = fetch_pr_reviews(repo, pr_number)
    except GhApiError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if has_valid_approval(reviews, head_sha=head_sha, author_login=author_login):
        print(f"ok: found an APPROVED review at head {head_sha} from a login other than the author ({author_login})")
        return 0

    print(
        f"missing: no APPROVED review at current head {head_sha} from a login other than the "
        f"author ({author_login}) -- most-recent-per-reviewer reduction applied over "
        f"{len(reviews)} review(s) total",
        file=sys.stderr,
    )
    return 1


def build_verdict(
    spec: sensitive_path_match.SensitivePathList,
    diff_text: str,
    pr_number: int,
) -> dict[str, Any] | None:
    """The `analyze` subcommand's own decision: classify, then produce a verdict for a sensitive
    PR. Returns None for a non-sensitive PR (nothing to write -- analyze does nothing further,
    per the design doc's Components table).

    TODO(condition-1): the design's Open Questions leave "what the analyze subcommand's
    underlying review pass actually is" unresolved -- this repo's own pr-review/code-review
    skill, or a narrower purpose-built check (the design's own lean for v1, since it also
    sidesteps the prompt-injection risk architecture review Condition 1 names). Whichever is
    chosen MUST treat the diff text as data, never instructions, per
    docs/skill-framework/shared/prompt-injection.md, and Condition 1 requires an explicit
    adversarial-content test case before this becomes a live (required-check) activation. Phase
    0 ships no real review pass: every sensitive PR gets `block` here -- fail closed, never
    invent an auto-approve verdict, until that decision is made and implemented.
    """
    result = sensitive_path_match.classify(diff_text, spec)
    if not result.sensitive:
        return None
    return {
        "verdict": "block",
        "pr_number": pr_number,
        "matched_globs": list(result.matched_globs),
        "matched_content_patterns": list(result.matched_content_patterns),
        "reason": (
            "the analyze subcommand's underlying review pass is not yet implemented "
            "(architecture review Condition 1; design doc Open Questions). Phase 0 fails "
            "closed rather than inventing a verdict."
        ),
    }


def run_analyze(*, repo: str, pr_number: int, sensitive_path_list: Path, out_path: Path) -> int:
    """The `analyze` subcommand's own logic: never writes anything back to GitHub or the repo
    itself (design doc, Components table) -- only ever writes the local verdict artifact file
    the caller then hands to `actions/upload-artifact`.
    """
    try:
        spec = sensitive_path_match.load_sensitive_path_list(sensitive_path_list)
    except sensitive_path_match.SensitivePathListError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        diff_text = fetch_pr_diff(repo, pr_number)
    except GhApiError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    verdict = build_verdict(spec, diff_text, pr_number)
    if verdict is None:
        print(f"ok: PR #{pr_number} is not sensitive -- no verdict artifact written")
        return 0

    out_path.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
    print(f"wrote verdict artifact to {out_path}: {verdict}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command")

    check_parser = subparsers.add_parser("check", help="review-evidence-check: verify existing review evidence (default)")
    check_parser.add_argument("--pr", type=int, required=True, help="pull request number")
    check_parser.add_argument("--repo", default=DEFAULT_REPO, help="owner/repo (default: $GITHUB_REPOSITORY or luckyrjain/software-builder)")
    check_parser.add_argument(
        "--sensitive-path-list",
        type=Path,
        default=sensitive_path_match.DEFAULT_SENSITIVE_PATH_LIST,
        help="path to docs/sensitive-paths.yaml",
    )

    analyze_parser = subparsers.add_parser("analyze", help="classify sensitivity and write a verdict artifact (invoked by review-evidence-post)")
    analyze_parser.add_argument("--pr", type=int, required=True, help="pull request number")
    analyze_parser.add_argument("--repo", default=DEFAULT_REPO, help="owner/repo (default: $GITHUB_REPOSITORY or luckyrjain/software-builder)")
    analyze_parser.add_argument(
        "--sensitive-path-list",
        type=Path,
        default=sensitive_path_match.DEFAULT_SENSITIVE_PATH_LIST,
        help="path to docs/sensitive-paths.yaml",
    )
    analyze_parser.add_argument(
        "--out",
        type=Path,
        default=Path("review-evidence-verdict.json"),
        help="where to write the verdict artifact JSON (default: review-evidence-verdict.json)",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # `--pr <n>` alone (no subcommand) means `check --pr <n>` -- the design doc's literal CLI
    # contract is `scripts/check_review_evidence.py --pr <n>`, so a bare flag (or no args at
    # all) is routed to the `check` subcommand rather than requiring callers to spell it out.
    if not argv or argv[0].startswith("-"):
        argv = ["check", *argv]

    args = _build_parser().parse_args(argv)

    if args.command == "analyze":
        return run_analyze(
            repo=args.repo,
            pr_number=args.pr,
            sensitive_path_list=args.sensitive_path_list,
            out_path=args.out,
        )

    return run_check(repo=args.repo, pr_number=args.pr, sensitive_path_list=args.sensitive_path_list)


if __name__ == "__main__":
    sys.exit(main())
