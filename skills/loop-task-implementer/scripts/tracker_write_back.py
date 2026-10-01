#!/usr/bin/env python3
"""Post-merge / PR-opened tracker write-back (gap-backlog B8).

Implements, as directly as possible, the converged (revision 3) design's Data model / State
machines / Failure strategy sections --
``docs/superpowers/specs/2026-10-01-b8-post-merge-write-back-design.md``.

**The single most important property in this module** (closes the confused-deputy risk this
design's own revision history records being found, and incorrectly "fixed," twice before a round-3
targeted rename finally closed it): :func:`derive_source_issue_ref` has **no parameter through
which repository or ticket content could flow in**. It takes only ``caller_task_ref`` -- a clean,
caller-supplied, structured identifier (``orchestrator.md``'s own new ``consumes: caller_task_ref``
entry, never the untrusted, pasted-ticket-text ``task_source`` channel, and never any ticket
body/description text) -- and ``verified_repo`` -- the Orchestrator's own already-verified
repository context (``orchestrator.md`` Sec 1), never parsed out of ``caller_task_ref`` itself. This
module never reads a repository, a ticket body, or any file at all.

Core pieces, matching the design's own naming exactly:

- :func:`derive_source_issue_ref` -- parses ``caller_task_ref`` into
  ``{repo, issue_number} | None``. ``repo`` in the output is always ``verified_repo``.
- :func:`render_merged_body` / :func:`render_pr_opened_body` -- the two literal, variant-tagged
  comment templates. Every placeholder is an already-verified fact passed in as a parameter; neither
  function reads task description, finding text, or PR/issue comment text, and neither fetches
  anything.
- :func:`get_write_back_actor_identity` -- discovers the write-back mechanism's own known identity
  via ``gh api user`` (its ``login`` field; ``gh auth status`` only prints human-readable text and
  does not reliably expose a parseable login across ``gh`` versions). Used ONLY for the
  author-scoped marker check below. **This should be a dedicated service identity in production,
  never shared with anything that renders untrusted content into GitHub-authenticated actions** --
  a design-level recommendation this module supports (by taking the identity as an opaque string
  everywhere it is used) but cannot itself enforce: the actual identity is whatever ``gh`` is
  authenticated as in the running environment.
- :func:`check_existing_marker` -- a pure read (``gh api repos/{repo}/issues/{issue_number}/comments``,
  which is the endpoint that returns both ``body`` and ``user.login`` per comment --
  ``gh issue view --comments`` alone does not reliably expose the author login in a parseable
  form). Filters to comments authored by ``actor_identity`` only (ignoring any marker from any other
  commenter -- closes the marker-spoofing finding), then searches the filtered set for the exact,
  variant-tagged marker. Returns ``False`` on any read failure (fails toward attempting the post,
  per the design's own disclosed Failure strategy).
- :func:`post_write_back` -- ``gh issue comment {issue_number} --repo {repo} --body {body}``, returns
  a structured ``{"success": bool, "error_category": str}`` result -- never the raw exception/error
  text verbatim, matching ``convention_capture.py``'s ``ConventionCaptureFetchError`` bare-category
  discipline (gap-backlog B6).
- :func:`attempt_write_back` -- the orchestrating function. Re-runs the idempotency precheck
  immediately before every individual post attempt -- the first attempt and the one bounded retry --
  never caching or reusing a prior precheck result. This is the exact mechanism that closes this
  design's own round-2 finding that a retry without re-checking reopens duplicate-post risk.

Returns one of four outcomes: ``"not_attempted"``, ``"skipped_already_posted"``, ``"posted"``, or
``"failed:<bare_error_category>"`` (the bare category is appended after a terminal retry failure,
never the raw exception/subprocess-stderr text -- same discipline as ``post_write_back``'s own
``error_category``).
"""

from __future__ import annotations

import json
import subprocess
import time
from typing import Any, Callable

MERGED_VARIANT = "merged"
PR_OPENED_VARIANT = "pr-opened"
_VARIANTS = (MERGED_VARIANT, PR_OPENED_VARIANT)

_GH_TIMEOUT_SECONDS = 30

_MERGED_TEMPLATE = (
    "Completed via loop-task-implementer.\n\n"
    "PR: {pr_url}\n"
    "Merged commit: {merge_commit_sha}\n"
    "Verified on {target_branch} at {integration_timestamp_utc}\n\n"
    "<!-- loop-task-implementer:write-back:{task_id}:merged -->"
)

_PR_OPENED_TEMPLATE = (
    "Ready for review via loop-task-implementer.\n\n"
    "PR: {pr_url}\n"
    "Opened against {target_branch} at {pr_opened_timestamp_utc}\n"
    "Awaiting human merge decision.\n\n"
    "<!-- loop-task-implementer:write-back:{task_id}:pr-opened -->"
)


class TrackerWriteBackError(RuntimeError):
    """Raised only by :func:`get_write_back_actor_identity` when identity discovery itself fails.

    Mirrors ``convention_capture.py``'s ``ConventionCaptureFetchError`` bare-category discipline
    (gap-backlog B6): this exception's message never carries raw subprocess output, only a short,
    bare failure category (e.g. ``"gh_unavailable"``, ``"malformed_response"``).
    """


# =================================================================================================
# derive_source_issue_ref -- the single highest-priority function in this module.
# =================================================================================================


def _parse_issue_number(candidate: str) -> int | None:
    """Recognized ``caller_task_ref`` shapes (Open Question 3 of the design -- pinned here as a
    concrete, documented choice, since the design leaves the exact grammar open for implementation):

    - a bare integer-shaped string: ``"123"``
    - ``"#123"``
    - ``"owner/repo#123"`` (the ``owner/repo`` portion is parsed only to confirm the shape and is
      then discarded -- ``repo`` in the output is ALWAYS ``verified_repo``, never this substring)
    - a full GitHub issue URL: ``"https://github.com/owner/repo/issues/123"`` (same discard rule)

    Anything else -- a Jira-style key (``"PROJ-123"``), free text, an empty string -- is not
    recognized and yields ``None``.
    """
    text = candidate.strip()
    if not text:
        return None

    number_text: str | None = None
    if text.startswith("#"):
        number_text = text[1:]
    elif text.isdigit():
        number_text = text
    elif "#" in text and "/" in text.split("#", 1)[0]:
        owner_repo, _, after_hash = text.partition("#")
        if owner_repo.count("/") == 1 and all(owner_repo.split("/")) and after_hash.isdigit():
            number_text = after_hash
    elif text.startswith(("http://", "https://")) and "/issues/" in text:
        tail = text.split("/issues/", 1)[1]
        # Stop at the first non-digit (a trailing slash, query string, or fragment).
        digits = ""
        for char in tail:
            if char.isdigit():
                digits += char
            else:
                break
        number_text = digits or None

    if number_text is None or not number_text.isdigit():
        return None
    number = int(number_text)
    return number if number > 0 else None


def derive_source_issue_ref(caller_task_ref: Any, verified_repo: str) -> dict[str, Any] | None:
    """Parse ``caller_task_ref`` ONLY (never ``task_source``, never any ticket body/description
    text -- this function has no parameter through which either could flow in) into
    ``{"repo": verified_repo, "issue_number": int} | None``.

    ``repo`` in the output is ALWAYS ``verified_repo`` -- the Orchestrator's own already-verified
    repository context -- NEVER derived from parsing ``caller_task_ref`` itself, even when
    ``caller_task_ref`` is itself an ``owner/repo#123``-shaped or full-URL-shaped reference that
    names a *different* repo. This closes the design's "unpinned ``--repo``" finding: the write
    target is always the repo the Orchestrator itself verified, never a string an upstream caller
    (or, transitively, a compromised tracker) could use to redirect the write.

    Returns ``None`` when ``caller_task_ref`` is absent, not a string/int, or does not parse into
    one of the recognized GitHub-Issue-shaped forms documented on :func:`_parse_issue_number`.
    """
    if caller_task_ref is None or isinstance(caller_task_ref, bool):
        return None
    if isinstance(caller_task_ref, int):
        return {"repo": verified_repo, "issue_number": caller_task_ref} if caller_task_ref > 0 else None
    if not isinstance(caller_task_ref, str):
        return None

    issue_number = _parse_issue_number(caller_task_ref)
    if issue_number is None:
        return None
    return {"repo": verified_repo, "issue_number": issue_number}


# =================================================================================================
# Literal content templates -- citation-by-reference only, never raw task/finding/comment text.
# =================================================================================================


def render_merged_body(
    *, task_id: str, pr_url: str, merge_commit_sha: str, target_branch: str, integration_timestamp_utc: str
) -> str:
    """Every placeholder here is an already-verified fact the Orchestrator's own Sec 18 recorded
    (``pr_url``/``merge_commit_sha`` from the re-fetched, verified PR state; ``target_branch`` from
    Sec 1's policy discovery; ``integration_timestamp_utc`` from Sec 18's own recording step). This
    function performs no I/O and reads nothing beyond its own parameters -- it cannot itself embed
    task description, finding text, or PR/issue comment text."""
    return _MERGED_TEMPLATE.format(
        task_id=task_id,
        pr_url=pr_url,
        merge_commit_sha=merge_commit_sha,
        target_branch=target_branch,
        integration_timestamp_utc=integration_timestamp_utc,
    )


def render_pr_opened_body(*, task_id: str, pr_url: str, target_branch: str, pr_opened_timestamp_utc: str) -> str:
    """``pr_opened_timestamp_utc`` must be read back from the run log's own already-recorded
    ``pr_opened`` event ``ts`` field by the caller (``orchestrator.md``'s own integration point) --
    this function never invents or freshly asserts it, and never fetches anything itself."""
    return _PR_OPENED_TEMPLATE.format(
        task_id=task_id,
        pr_url=pr_url,
        target_branch=target_branch,
        pr_opened_timestamp_utc=pr_opened_timestamp_utc,
    )


# =================================================================================================
# Actor identity, idempotency precheck, and the post itself.
# =================================================================================================


def get_write_back_actor_identity() -> str:
    """Discover the write-back mechanism's own known identity via ``gh api user``, reading its
    stable ``login`` field. Used ONLY for the author-scoped marker check in
    :func:`check_existing_marker` below -- never for anything that renders untrusted content into a
    GitHub-authenticated action. In production this identity should be a dedicated service account,
    never shared with any component that renders untrusted (task/ticket/comment) text into a
    GitHub-authenticated call; this module cannot enforce that itself -- it takes and returns
    whatever ``gh`` is actually authenticated as.

    Raises :class:`TrackerWriteBackError` (bare category only) if identity discovery fails for any
    reason -- a malformed response, an unauthenticated ``gh``, or the CLI being unavailable.
    """
    try:
        result = subprocess.run(
            ["gh", "api", "user"],
            capture_output=True,
            text=True,
            timeout=_GH_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise TrackerWriteBackError("timeout") from None
    except OSError:
        raise TrackerWriteBackError("gh_unavailable") from None

    if result.returncode != 0:
        raise TrackerWriteBackError("gh_unauthenticated")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise TrackerWriteBackError("malformed_response") from None
    login = payload.get("login") if isinstance(payload, dict) else None
    if not isinstance(login, str) or not login:
        raise TrackerWriteBackError("malformed_response")
    return login


def _marker(task_id: str, variant: str) -> str:
    return f"<!-- loop-task-implementer:write-back:{task_id}:{variant} -->"


def check_existing_marker(repo: str, issue_number: int, task_id: str, variant: str, actor_identity: str) -> bool:
    """Read the target issue's existing comments (``gh api repos/{repo}/issues/{issue_number}/comments``
    -- the endpoint that returns both ``body`` and ``user.login`` per comment; ``gh issue view
    --comments`` alone does not reliably expose the author login in parseable form), keep only
    those authored by ``actor_identity`` (ignoring any marker posted by any other commenter --
    closes the marker-spoofing finding), then search the kept set for this exact,
    variant-tagged marker. A prior marker for a *different* variant never counts as a match here --
    a ``pr-opened`` marker never blocks a subsequent ``merged`` check for the same ``task_id``, and
    vice versa.

    On ANY read failure (network error, malformed response, ``gh`` unavailable), returns ``False`` --
    fails toward attempting the post, per the design's own disclosed Failure strategy, rather than
    silently skipping write-back on a flaky read. This is a pure read; it must be called fresh
    immediately before every individual post attempt, never cached or reused across attempts.
    """
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{repo}/issues/{issue_number}/comments"],
            capture_output=True,
            text=True,
            timeout=_GH_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if result.returncode != 0:
        return False
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, list):
        return False

    marker = _marker(task_id, variant)
    for item in payload:
        if not isinstance(item, dict):
            continue
        author = item.get("user")
        login = author.get("login") if isinstance(author, dict) else None
        if login != actor_identity:
            continue  # not our own identity -- ignore regardless of body content (anti-spoofing)
        body = item.get("body")
        if isinstance(body, str) and marker in body:
            return True
    return False


def post_write_back(repo: str, issue_number: int, body: str) -> dict[str, Any]:
    """``gh issue comment {issue_number} --repo {repo} --body {body}``. Returns a structured
    ``{"success": True}`` or ``{"success": False, "error_category": <bare category>}`` -- never the
    raw exception or subprocess stderr text verbatim, matching ``convention_capture.py``'s
    ``ConventionCaptureFetchError`` bare-category discipline (gap-backlog B6): a stderr line could
    itself carry unexpected content (e.g. an echoed, attacker-shaped request body on certain API
    error responses), so only a short, closed-vocabulary category is ever surfaced.
    """
    try:
        result = subprocess.run(
            ["gh", "issue", "comment", str(issue_number), "--repo", repo, "--body", body],
            capture_output=True,
            text=True,
            timeout=_GH_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"success": False, "error_category": "timeout"}
    except OSError:
        return {"success": False, "error_category": "gh_unavailable"}

    if result.returncode == 0:
        return {"success": True}

    stderr = (result.stderr or "").lower()
    if "403" in stderr or "429" in stderr or "rate limit" in stderr:
        category = "rate_limited"
    elif "404" in stderr or "not found" in stderr:
        category = "not_found"
    elif "permission" in stderr or "forbidden" in stderr:
        category = "permission_denied"
    else:
        category = "http_error"
    return {"success": False, "error_category": category}


def _pr_still_open(repo: str, pr_number: int) -> bool:
    """The PR-opened trigger's minimal freshness re-check: ``gh pr view {pr_number} --repo {repo}
    --json state,mergedAt``. Returns ``True`` only when the PR's state is genuinely ``OPEN`` and it
    carries no ``mergedAt``. Any read failure (network error, malformed response, ``gh``
    unavailable) returns ``False`` -- fails CLOSED here (toward ``not_attempted``), the opposite
    direction from :func:`check_existing_marker`'s own fail-open: an unreadable freshness check means
    this function cannot confirm the PR is still open, and posting a "ready for review" comment onto
    a PR that may have since merged or closed is the one mistake this specific check exists to
    prevent.
    """
    try:
        result = subprocess.run(
            ["gh", "pr", "view", str(pr_number), "--repo", repo, "--json", "state,mergedAt"],
            capture_output=True,
            text=True,
            timeout=_GH_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if result.returncode != 0:
        return False
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    return payload.get("state") == "OPEN" and not payload.get("mergedAt")


# =================================================================================================
# attempt_write_back -- the orchestrating function implementing the full contract.
# =================================================================================================


def attempt_write_back(
    *,
    tracker_write_back_authorized: bool,
    source_issue_ref: dict[str, Any] | None,
    variant: str,
    task_id: str,
    pr_url: str,
    target_branch: str,
    merge_commit_sha: str | None = None,
    integration_timestamp_utc: str | None = None,
    pr_opened_timestamp_utc: str | None = None,
    pr_number: int | None = None,
    max_retries: int = 1,
    sleep: Callable[[float], None] = time.sleep,
    backoff_seconds: float = 1.0,
) -> str:
    """The full write-back contract for one task, one trigger point/variant:

    1. If ``tracker_write_back_authorized`` is false, or ``source_issue_ref`` is ``None``, return
       ``"not_attempted"`` immediately -- no network calls of any kind.
    2. For the ``pr-opened`` variant ONLY, do the minimal freshness re-check (:func:`_pr_still_open`)
       and return ``"not_attempted"`` if the PR is no longer open.
    3. Discover the write-back actor's own identity once (:func:`get_write_back_actor_identity`).
    4. Run :func:`check_existing_marker` -- a FRESH call, never cached or reused. If it finds a
       match, return ``"skipped_already_posted"``.
    5. Call :func:`post_write_back`. If it succeeds, return ``"posted"``.
    6. If it fails and a retry remains, back off, then go back to step 4 -- a FRESH precheck, not a
       reuse of step 4's prior result -- before attempting the post again. This is what closes the
       design's own round-2 finding that a retry without re-checking reopens duplicate-post risk: if
       the first attempt actually succeeded server-side despite an apparent failure (e.g. a lost
       response), the retry's own fresh precheck finds the marker and returns
       ``"skipped_already_posted"`` rather than double-posting.
    7. After the one bounded retry is also exhausted, return ``"failed:<bare_error_category>"`` --
       never the raw exception/stderr text.

    ``variant`` must be ``"merged"`` or ``"pr-opened"`` (:data:`MERGED_VARIANT` /
    :data:`PR_OPENED_VARIANT`); any other value is a caller bug (``ValueError``), not one of the
    four outcomes above.
    """
    if variant not in _VARIANTS:
        raise ValueError(f"unknown write-back variant: {variant!r}; expected one of {_VARIANTS}")

    if not tracker_write_back_authorized or source_issue_ref is None:
        return "not_attempted"

    repo = source_issue_ref["repo"]
    issue_number = source_issue_ref["issue_number"]

    if variant == PR_OPENED_VARIANT:
        if pr_number is None or not _pr_still_open(repo, pr_number):
            return "not_attempted"
        body = render_pr_opened_body(
            task_id=task_id,
            pr_url=pr_url,
            target_branch=target_branch,
            pr_opened_timestamp_utc=pr_opened_timestamp_utc,  # type: ignore[arg-type]
        )
    else:
        body = render_merged_body(
            task_id=task_id,
            pr_url=pr_url,
            merge_commit_sha=merge_commit_sha,  # type: ignore[arg-type]
            target_branch=target_branch,
            integration_timestamp_utc=integration_timestamp_utc,  # type: ignore[arg-type]
        )

    try:
        actor_identity = get_write_back_actor_identity()
    except TrackerWriteBackError as exc:
        return f"failed:{exc}"

    last_category = "unknown_error"
    for attempt in range(max_retries + 1):
        if check_existing_marker(repo, issue_number, task_id, variant, actor_identity):
            return "skipped_already_posted"
        result = post_write_back(repo, issue_number, body)
        if result.get("success"):
            return "posted"
        last_category = result.get("error_category", last_category)
        if attempt < max_retries:
            sleep(backoff_seconds * (2**attempt))
            continue
    return f"failed:{last_category}"
