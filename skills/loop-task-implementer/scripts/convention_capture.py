#!/usr/bin/env python3
"""Cross-run repo-convention capture (gap-backlog B6).

Implements the design's Data model section, verbatim, as two genuinely distinct functions (the
design's own revision history records this split being found necessary three separate times before
landing correctly — see
``docs/superpowers/specs/2026-09-30-b6-convention-capture-design.md``, revision 5):

- :func:`score_text_pair` — pure, local, deterministic, no network, no I/O of any kind. Word-level
  trigram Jaccard overlap, used both by the conflict-check below (candidate principle sentence vs.
  every existing ``learned-conventions.md`` entry's own principle sentence) and, indirectly, by
  :func:`fetch_and_score`.
- :func:`fetch_and_score` — the **only** function in this module with network/fetch capability.
  Fetches a cited PR's own review-comment text (never title/body/diff) and scores it against a
  supplied candidate text. Never returns, logs, or raises with the fetched text itself — see its own
  docstring for the exact security requirement this closes.

This module does **not** attempt to semantically cluster free-text PR review comments into
candidate-convention categories: per the design (Components: "Occurrence/diversity aggregator...
category... a short, LLM-synthesized label"), that judgment call belongs to the Orchestrator (an
LLM), not to a deterministic script. :func:`aggregate_occurrences` therefore takes already-labeled
:class:`Occurrence` records — (category, principle sentence, PR number, scope), each already
identified and synthesized upstream — and performs only the mechanical, testable part: grouping,
distinct-PR counting, and the occurrence/diversity threshold. :func:`scan_pr_history` supplies the
bounded, real PR-number universe those occurrences are checked against, so a candidate cannot be
credited with evidence from outside the design's stated scan window.

:func:`main` (via :func:`generate_convention_scan_report`) runs the full pipeline: aggregate ->
threshold-check -> conflict-check-against-existing-entries -> textual-contradiction-check ->
write-report. It writes exactly one report file to disk and nothing else — see that function's own
docstring for why this is explicitly **not** a "write to the repository" in this skill's
write-authority-doctrine sense, and why it must never invoke ``git add``/``commit``/``push``.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

# --- repo-root import bootstrap (mirrors the sys.path convention already used by sibling skill
# scripts -- e.g. k8s-overprovisioning-datadog/scripts/validate_decision_graph.py,
# migration-program-manager/scripts/aggregate_migration_status.py -- for locating a repository-root
# module from inside skills/<name>/scripts/). Not the yaml-safety GENERATED bootstrap (that one is
# specific to scripts/yaml_safety.py and machine-managed by `make generate`); this is a small,
# hand-written equivalent for `scripts.task_lease`, which the design requires be imported, never
# reimplemented (Data model: "Scan-lease").
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[2]
if (_REPO_ROOT / "skills.yaml").is_file() and str(_REPO_ROOT) not in sys.path:
    sys.path.append(str(_REPO_ROOT))

try:
    from scripts.task_lease import derive_lease_id, resolve_lease_dir, try_acquire
except ImportError:  # pragma: no cover - only reachable outside a source checkout of this repo
    derive_lease_id = None  # type: ignore[assignment]
    resolve_lease_dir = None  # type: ignore[assignment]
    try_acquire = None  # type: ignore[assignment]


DEFAULT_REPO = "luckyrjain/software-builder"
DEFAULT_LEARNED_CONVENTIONS_PATH = _REPO_ROOT / "docs" / "skill-framework" / "learned-conventions.md"
DEFAULT_SPECS_DIR = _REPO_ROOT / "docs" / "superpowers" / "specs"
DEFAULT_CONTRIBUTING_PATH = _REPO_ROOT / "CONTRIBUTING.md"

# Data model: "at least 3 occurrences across at least 3 distinct PRs".
MIN_OCCURRENCES = 3
MIN_DISTINCT_PRS = 3

# Data model: "Threshold: 0.4 for both functions, still an explicitly unvalidated starting point".
SIMILARITY_THRESHOLD = 0.4

# Data model: "min(50 most recent closed/merged PRs, PRs within the last 90 days)".
SCAN_MAX_PRS = 50
SCAN_WINDOW_DAYS = 90


# =================================================================================================
# score_text_pair -- pure, local, deterministic. No network. No I/O of any kind.
# =================================================================================================

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_CHECKBOX_RE = re.compile(r"^[ \t]*[-*][ \t]*\[[ xX]\][ \t]*", re.MULTILINE)
_HEADING_RE = re.compile(r"^[ \t]{0,3}#{1,6}[ \t].*$", re.MULTILINE)
_WORD_RE = re.compile(r"[a-z0-9']+")


def _strip_markdown_boilerplate(text: str) -> str:
    """Remove common markdown boilerplate that carries no author-chosen content: HTML comments
    (``<!-- ... -->``, e.g. hidden PR-template instructions), checkbox syntax (``- [ ]``/``- [x]``,
    e.g. a PR-template checklist item), and heading lines (e.g. a PR/issue template's own
    ``## Description`` / ``## Checklist`` section headers). Stripped *before* tokenizing so two
    comments differing only in this structural noise score as near-identical rather than being
    penalized for boilerplate neither author actually chose to write."""
    text = _HTML_COMMENT_RE.sub(" ", text)
    text = _CHECKBOX_RE.sub(" ", text)
    text = _HEADING_RE.sub(" ", text)
    return text


def _tokenize(text: str) -> list[str]:
    """Lowercase-fold and split into word tokens, after boilerplate stripping."""
    return _WORD_RE.findall(_strip_markdown_boilerplate(text).lower())


def _trigrams(tokens: Sequence[str]) -> set[tuple[str, str, str]]:
    if len(tokens) < 3:
        return set()
    return {tuple(tokens[i : i + 3]) for i in range(len(tokens) - 2)}


def score_text_pair(text_a: str, text_b: str) -> float:
    """Word-level trigram Jaccard overlap of ``text_a`` and ``text_b``, lowercase-folded, with
    common markdown boilerplate stripped before tokenizing (see :func:`_strip_markdown_boilerplate`).
    ``|A intersect B| / |A union B|`` over each text's set of word trigrams.

    PURE, LOCAL, NO NETWORK, NO I/O OF ANY KIND (Data model / Hard constraints) — this function
    reads only its two string arguments and returns a float; it never touches the filesystem or the
    network. Reading ``learned-conventions.md``'s existing entries is the caller's job
    (:func:`check_against_existing_entries`), never this function's own.

    Degenerate-case convention (documented explicitly, as the design requires): a text shorter than
    three words produces no trigrams at all, so its trigram set is empty. If *both* texts' trigram
    sets are empty, ``|A union B|`` is also empty and the ratio is mathematically 0/0 — this
    function returns ``0.0`` for that case by convention (chosen over raising, or over treating two
    contentless inputs as a confident match — an "empty == identical" convention would silently flag
    every blank/near-blank candidate as a duplicate of every other one). The same ``0.0`` is
    returned, for the same reason, whenever the union is empty for any other reason it might
    (in practice only the both-empty case, since a non-empty text always contributes to the union
    once it has >= 3 tokens).
    """
    trigrams_a = _trigrams(_tokenize(text_a))
    trigrams_b = _trigrams(_tokenize(text_b))
    union = trigrams_a | trigrams_b
    if not union:
        return 0.0
    return len(trigrams_a & trigrams_b) / len(union)


# =================================================================================================
# fetch_and_score -- the ONLY function with network/fetch capability.
# =================================================================================================


class ConventionCaptureFetchError(RuntimeError):
    """Raised by :func:`fetch_and_score` when fetching a cited PR's review-comment text fails after
    retries are exhausted (rate limit, malformed response, or another fetch failure).

    CRITICAL SECURITY REQUIREMENT (verified across 2 review rounds of the design this implements):
    this exception's own message NEVER includes the fetched PR text — only bare, structural facts
    (the PR number and a short failure category, e.g. ``"rate_limited"``, ``"malformed_response"``,
    ``"timeout"``, ``"http_error"``). Callers (the Reviewer, per ``workflow/reviewer.md``) catch this
    and treat it as ``NEEDS_EVIDENCE`` — never fall back to reading the raw PR content by any other
    path.
    """


_RATE_LIMIT_MARKERS = ("403", "429", "rate limit", "API rate limit")


def _looks_rate_limited(returncode: int, stderr: str) -> bool:
    if returncode == 0:
        return False
    lowered = stderr.lower()
    return any(marker.lower() in lowered for marker in _RATE_LIMIT_MARKERS)


def _fetch_review_comment_text(
    pr_number: int,
    *,
    repo: str = DEFAULT_REPO,
    max_retries: int = 3,
    backoff_seconds: float = 1.0,
    sleep: Any = time.sleep,
) -> str:
    """Fetch PR ``#pr_number``'s own review-comment bodies only (never title/body/diff) via the PR
    *review*-comments endpoint (``gh api repos/{owner}/{repo}/pulls/{pr_number}/comments``) --
    distinct from ``.../issues/{pr}/comments``, which returns top-level conversation comments, not
    comments anchored to the diff. Retries with exponential backoff on a rate-limit-shaped failure
    (HTTP 403/429); raises :class:`ConventionCaptureFetchError` (with no fetched text in its message
    or in any output this function produces on any path) once retries are exhausted.

    This is the one function boundary tests mock (see ``tests/test_convention_capture.py``) rather
    than shelling out to a real ``gh`` process.
    """
    failure_category = "unknown_error"
    attempts = 0
    for attempt in range(max_retries + 1):
        attempts = attempt + 1
        try:
            result = subprocess.run(
                ["gh", "api", f"repos/{repo}/pulls/{pr_number}/comments"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except subprocess.TimeoutExpired:
            failure_category = "timeout"
        except OSError:
            # e.g. `gh` not installed. Never retryable -- no amount of backoff installs the CLI.
            failure_category = "gh_unavailable"
            break
        else:
            if result.returncode == 0:
                try:
                    payload = json.loads(result.stdout)
                except json.JSONDecodeError:
                    failure_category = "malformed_response"
                else:
                    if not isinstance(payload, list):
                        failure_category = "malformed_response"
                    else:
                        bodies = [
                            item.get("body", "")
                            for item in payload
                            if isinstance(item, dict) and isinstance(item.get("body"), str)
                        ]
                        return "\n".join(bodies)
            elif _looks_rate_limited(result.returncode, result.stderr or ""):
                failure_category = "rate_limited"
            else:
                failure_category = "http_error"
        if attempt < max_retries and failure_category in ("rate_limited", "timeout"):
            sleep(backoff_seconds * (2**attempt))
            continue
        break
    raise ConventionCaptureFetchError(
        f"fetch failed for PR #{pr_number}: {failure_category} (after {attempts} attempt(s))"
    )


def fetch_and_score(text: str, pr_numbers: list[int]) -> dict[int, float]:
    """For each PR number in ``pr_numbers``, fetch that PR's own review-comment text only (never
    title/body/diff) and score it against ``text`` via :func:`score_text_pair`. Returns a bare
    ``{pr_number: score}`` map.

    THE ONLY FUNCTION IN THIS MODULE WITH NETWORK/FETCH CAPABILITY. The raw fetched text is never
    included in this function's return value, and never appears in any exception message, log line,
    or stderr output on any failure path (network error, malformed API response, rate limit) — only
    bare, structural facts (see :class:`ConventionCaptureFetchError`). A failure on any cited PR
    aborts the whole call (raises :class:`ConventionCaptureFetchError`) rather than silently
    returning a partial map — this matches the design's "on failure, the finding becomes
    NEEDS_EVIDENCE, full stop" behavior (``workflow/reviewer.md``), not a mix of scored and unscored
    PRs a caller could mistake for a complete result.
    """
    scores: dict[int, float] = {}
    for pr_number in pr_numbers:
        fetched_text = _fetch_review_comment_text(pr_number)
        scores[pr_number] = score_text_pair(text, fetched_text)
    return scores


# =================================================================================================
# Conflict-check against existing learned-conventions.md entries -- pure, local, no network.
# =================================================================================================

_ENTRY_HEADING_RE = re.compile(r"^### (.+)$", re.MULTILINE)


def _load_existing_principles(path: Path) -> list[str]:
    """Extract each existing entry's own principle sentence (the ``###``-level heading, per the
    design's template) from ``learned-conventions.md``. Returns an empty list if the file does not
    exist yet (the file starts genuinely empty)."""
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    return [heading.strip() for heading in _ENTRY_HEADING_RE.findall(text)]


def check_against_existing_entries(
    candidate_principle: str,
    *,
    learned_conventions_path: Path = DEFAULT_LEARNED_CONVENTIONS_PATH,
    threshold: float = SIMILARITY_THRESHOLD,
) -> tuple[bool, float, str | None]:
    """Check a new candidate's FULL synthesized principle sentence — never the short category label
    (the design's round-5 fix; regressing to the category label reintroduces the "duplicates
    forever" / false-positive bug class round 4 found) — against every existing entry already
    present in ``learned-conventions.md``'s single running list, via :func:`score_text_pair` (pure,
    local, no fetch — never :func:`fetch_and_score`, which this function must never call: no network
    is needed to compare two already-in-hand strings).

    Returns ``(already_captured, best_score, best_matching_principle)``. ``already_captured`` is
    ``True`` when ``best_score`` exceeds ``threshold`` against any existing entry.
    """
    best_score = 0.0
    best_match: str | None = None
    for principle in _load_existing_principles(learned_conventions_path):
        score = score_text_pair(candidate_principle, principle)
        if score > best_score:
            best_score = score
            best_match = principle
    return (best_score > threshold, best_score, best_match)


# =================================================================================================
# Textual-contradiction check -- CONTRIBUTING.md + implicated SKILL.md files, explicit contradiction
# only. This is NOT a hard deterministic algorithm (per the design); see the docstring below for
# exactly what "explicit contradiction" means as implemented here.
# =================================================================================================

_NEGATION_CUES = (
    "never",
    "must not",
    "do not",
    "don't",
    "avoid",
    "no longer",
    "not allowed",
)
_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "for",
    "is",
    "are",
    "be",
    "this",
    "that",
    "it",
    "as",
    "by",
    "with",
    "never",
    "not",
    "always",
    "must",
}


def _significant_keywords(text: str) -> set[str]:
    return {word for word in _tokenize(text) if word not in _STOPWORDS and len(word) > 2}


def check_textual_contradiction(
    candidate_principle: str,
    *,
    contributing_path: Path = DEFAULT_CONTRIBUTING_PATH,
    skill_md_paths: Sequence[Path] = (),
) -> list[str]:
    """A coarse, keyword-scoped heuristic for "does this candidate convention explicitly contradict
    an already-stated repository instruction" — checked against ``CONTRIBUTING.md`` and any
    implicated ``SKILL.md`` files (``skill_md_paths``), explicit contradiction only, per the design.

    What "explicit contradiction" means here, concretely: this is NOT semantic negation detection
    and does NOT itself decide whether a real contradiction exists — it is a locator, not a verdict.
    For each candidate keyword (a significant word from the candidate's own principle sentence, see
    :func:`_significant_keywords`), it scans each target file's lines for one of a small set of
    negation cue phrases (``never``, ``must not``, ``do not``, ...) appearing on the same line as
    that keyword — a line shaped like "never do X" in a target file, where "X" shares vocabulary
    with a candidate that proposes doing X, is the kind of line worth a human's (or an
    Orchestrator's) closer look. It returns every such line as a bare ``"path:line: <text>"`` hit;
    an empty return is NOT proof of no conflict, only that this coarse heuristic found nothing to
    flag — the same disclosed residual as the design's own "doctrine blind spot" (unwritten
    institutional conventions no fixed file set can capture). A real, final judgment about whether a
    flagged line is an actual contradiction remains a human/Orchestrator call, exactly as the design
    states.
    """
    keywords = _significant_keywords(candidate_principle)
    if not keywords:
        return []
    hits: list[str] = []
    targets = [contributing_path, *skill_md_paths]
    for path in targets:
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, start=1):
            lowered = line.lower()
            if not any(cue in lowered for cue in _NEGATION_CUES):
                continue
            line_words = set(_tokenize(line))
            if keywords & line_words:
                hits.append(f"{path}:{lineno}: {line.strip()}")
    return hits


# =================================================================================================
# PR-history scanner -- the bounded, real PR-number universe (Data model: scan window).
# =================================================================================================


def scan_pr_history(
    *,
    repo: str = DEFAULT_REPO,
    max_prs: int = SCAN_MAX_PRS,
    window_days: int = SCAN_WINDOW_DAYS,
    now: datetime | None = None,
) -> set[int]:
    """Query up to ``max_prs`` most-recently-merged/closed PRs for ``repo``, intersected with a
    ``window_days``-day recency window (Data model: ``min(50 most recent closed/merged PRs, PRs
    within the last 90 days)``). Read-only; never writes. Returns the set of eligible PR numbers —
    the bounded universe :func:`aggregate_occurrences` checks candidate evidence against, so an
    occurrence citing a PR outside this window never counts toward the occurrence/diversity
    threshold.

    Does not fetch review-comment text (that is :func:`fetch_and_score`'s own, separate, narrower
    capability) — only lightweight PR metadata (number, closed date).

    On a missing ``gh`` CLI, an unauthenticated call, or a malformed response, returns an empty set
    and prints a bare, non-leaking warning to stderr (Failure strategy: "PR-history-read capability
    absent -> skip the scan entirely, report the gap").
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)
    try:
        result = subprocess.run(
            [
                "gh",
                "pr",
                "list",
                "--repo",
                repo,
                "--state",
                "merged",
                "--limit",
                str(max_prs),
                "--json",
                "number,closedAt,mergedAt",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        print(
            "convention_capture: PR-history scan unavailable (gh CLI missing or timed out) -- "
            "skipping the scan",
            file=sys.stderr,
        )
        return set()
    if result.returncode != 0:
        print(
            "convention_capture: PR-history scan failed (gh api error) -- skipping the scan",
            file=sys.stderr,
        )
        return set()
    try:
        prs = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(
            "convention_capture: PR-history scan returned malformed JSON -- skipping the scan",
            file=sys.stderr,
        )
        return set()
    if not isinstance(prs, list):
        return set()
    eligible: set[int] = set()
    for pr in prs:
        if not isinstance(pr, dict):
            continue
        number = pr.get("number")
        closed_raw = pr.get("closedAt") or pr.get("mergedAt")
        if not isinstance(number, int) or not isinstance(closed_raw, str):
            continue
        try:
            closed_at = datetime.fromisoformat(closed_raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        if closed_at >= cutoff:
            eligible.add(number)
    return eligible


def _default_base_branch(repo: str = DEFAULT_REPO) -> str:
    """A small, one-shot default-branch query for the scan-lease's ``base_branch`` argument (Data
    model / APIs). Falls back to ``"main"`` on any failure -- this is a lease-identity input, not a
    correctness-critical value, so a fallback keeps the scan runnable rather than fail-closed here."""
    try:
        result = subprocess.run(
            ["gh", "repo", "view", repo, "--json", "defaultBranchRef"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            name = (data.get("defaultBranchRef") or {}).get("name")
            if isinstance(name, str) and name:
                return name
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return "main"


# =================================================================================================
# Occurrence/diversity aggregator -- mechanical grouping + threshold check only. Category/principle
# labeling itself is an upstream (Orchestrator/LLM) judgment call, not this module's job -- see the
# module docstring.
# =================================================================================================


@dataclass(frozen=True)
class Occurrence:
    """One already-identified, already-labeled instance of a candidate recurring pattern: a
    category label and a synthesized principle sentence for it (both the Orchestrator's own
    judgment, formed by reading the actual historical PR content -- never this module's job), plus
    the PR number it was observed in and the skill/area scope it was observed in."""

    category: str
    principle: str
    pr_number: int
    scope: str = ""


@dataclass(frozen=True)
class CandidateConvention:
    """A category that met the occurrence/diversity threshold, ready for the conflict-check and
    contradiction-check."""

    category: str
    principle: str
    evidence_prs: tuple[int, ...]
    scope: str


def aggregate_occurrences(
    occurrences: Sequence[Occurrence],
    *,
    eligible_prs: set[int] | None = None,
    min_occurrences: int = MIN_OCCURRENCES,
    min_distinct_prs: int = MIN_DISTINCT_PRS,
) -> list[CandidateConvention]:
    """Group ``occurrences`` by category, keep only categories meeting the occurrence/diversity
    threshold: at least ``min_occurrences`` occurrences across at least ``min_distinct_prs`` distinct
    PRs (Data model: "at least 3 occurrences across at least 3 distinct PRs" — never a single
    incident, however clear).

    When ``eligible_prs`` is given (see :func:`scan_pr_history`), an occurrence whose ``pr_number``
    is not in that set is discarded before grouping — evidence from outside the bounded scan window
    never counts toward the threshold.
    """
    if eligible_prs is not None:
        occurrences = [occ for occ in occurrences if occ.pr_number in eligible_prs]
    by_category: dict[str, list[Occurrence]] = {}
    for occ in occurrences:
        by_category.setdefault(occ.category, []).append(occ)
    candidates: list[CandidateConvention] = []
    for category, occs in by_category.items():
        distinct_prs = sorted({occ.pr_number for occ in occs})
        if len(occs) < min_occurrences or len(distinct_prs) < min_distinct_prs:
            continue
        candidates.append(
            CandidateConvention(
                category=category,
                principle=occs[0].principle,
                evidence_prs=tuple(distinct_prs),
                scope=occs[0].scope,
            )
        )
    return candidates


# =================================================================================================
# Report generation -- scan -> aggregate -> threshold-check -> conflict-check ->
# contradiction-check -> write-report. Writes exactly one file; never a repository write in the
# write-authority-doctrine sense.
# =================================================================================================


def _load_occurrences(path: Path) -> list[Occurrence]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a JSON array of occurrence objects")
    occurrences = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError(f"{path}: each occurrence must be a JSON object")
        occurrences.append(
            Occurrence(
                category=str(item["category"]),
                principle=str(item["principle"]),
                pr_number=int(item["pr_number"]),
                scope=str(item.get("scope", "")),
            )
        )
    return occurrences


def _render_candidate(candidate: CandidateConvention) -> str:
    evidence = ", ".join(f"PR #{n}" for n in candidate.evidence_prs)
    return (
        f"### {candidate.principle}\n\n"
        f"**Category:** {candidate.category} — for human browsing only; not used for "
        f"duplicate-recognition\n"
        f"**Evidence:** {evidence} ({len(candidate.evidence_prs)} distinct PRs)\n"
        f"**Scope:** {candidate.scope}\n"
    )


def _write_report(
    surviving: list[CandidateConvention],
    *,
    output_dir: Path,
    scan_window_end_date: str,
    counts: dict[str, int],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{scan_window_end_date}-b6-convention-scan-report.md"
    generated_at = datetime.now(timezone.utc).isoformat()
    lines = [
        "# Convention-scan report",
        "",
        f"Generated by `convention_capture.py` on {generated_at}. Scan window: "
        f"`min({SCAN_MAX_PRS} most recent closed/merged PRs, PRs within the last "
        f"{SCAN_WINDOW_DAYS} days)`, ending {scan_window_end_date}.",
        "",
        "Report-only: this file is never auto-committed and this script never invokes `git "
        "add`/`git commit`/`git push`. A human decides whether/when to act on any candidate below "
        "(gap-backlog B6 design, Rollout Phase 3).",
        "",
        f"Discarded below occurrence/diversity threshold: {counts.get('below_threshold', 0)} "
        "(bare count only).",
        f"Discarded as already-captured (matches an existing `learned-conventions.md` entry): "
        f"{counts.get('already_captured', 0)} (bare count only).",
        f"Discarded on textual-contradiction check: {counts.get('contradicted', 0)} (bare count "
        "only).",
        "",
    ]
    if surviving:
        lines.append("## Candidates")
        lines.append("")
        for candidate in surviving:
            lines.append(_render_candidate(candidate))
    else:
        lines.append("No candidates cleared every check this pass.")
        lines.append("")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def generate_convention_scan_report(
    occurrences_path: Path | None,
    *,
    repo: str = DEFAULT_REPO,
    output_dir: Path = DEFAULT_SPECS_DIR,
    learned_conventions_path: Path = DEFAULT_LEARNED_CONVENTIONS_PATH,
    contributing_path: Path = DEFAULT_CONTRIBUTING_PATH,
    skill_md_paths: Sequence[Path] = (),
    scan_window_end_date: str | None = None,
    use_scan_lease: bool = True,
) -> Path:
    """The report-generation entrypoint: scan -> aggregate -> threshold-check ->
    conflict-check-against-existing-entries -> textual-contradiction-check -> write-report.

    NOT A "WRITE TO THE REPOSITORY" in this skill's write-authority-doctrine sense, the same way a
    Builder's PR/commit is: this function writes exactly one report file
    (``docs/superpowers/specs/<date>-b6-convention-scan-report.md``) to disk and nothing else. It
    never invokes ``git add``/``git commit``/``git push``, opens no PR, and touches no other
    repository file. A human decides, out of band, whether and when to commit the resulting report
    alongside acting on any candidate in it (design, Rollout Phase 3) -- this function's own effect
    ends at the filesystem write.

    Reuses the scan-lease (``derive_lease_id(repo, base_branch, f"convention-capture-scan:{date}")``
    from ``scripts/task_lease.py``, gap-backlog B1's own established mixing pattern) to prevent two
    concurrent scan passes; set ``use_scan_lease=False`` only for tests that don't want to touch the
    real, process-wide lease directory.
    """
    scan_window_end_date = scan_window_end_date or datetime.now(timezone.utc).date().isoformat()

    handle = None
    if use_scan_lease:
        if derive_lease_id is None or try_acquire is None or resolve_lease_dir is None:
            raise RuntimeError(
                "convention_capture: scripts.task_lease is not importable from this checkout -- "
                "cannot safely run a convention-capture scan without the scan-lease"
            )
        base_branch = _default_base_branch(repo)
        lease_id = derive_lease_id(repo, base_branch, f"convention-capture-scan:{scan_window_end_date}")
        handle = try_acquire(resolve_lease_dir(None), lease_id)
        if handle is None:
            raise RuntimeError(
                f"convention_capture: a scan is already in progress for window ending "
                f"{scan_window_end_date} -- not starting a second one"
            )

    try:
        occurrences = _load_occurrences(occurrences_path) if occurrences_path else []
        eligible_prs = scan_pr_history(repo=repo)
        all_candidates = aggregate_occurrences(occurrences, eligible_prs=eligible_prs or None)

        surviving: list[CandidateConvention] = []
        counts = {"already_captured": 0, "contradicted": 0}
        for candidate in all_candidates:
            already_captured, _score, _match = check_against_existing_entries(
                candidate.principle, learned_conventions_path=learned_conventions_path
            )
            if already_captured:
                counts["already_captured"] += 1
                continue
            contradictions = check_textual_contradiction(
                candidate.principle,
                contributing_path=contributing_path,
                skill_md_paths=skill_md_paths,
            )
            if contradictions:
                counts["contradicted"] += 1
                continue
            surviving.append(candidate)

        # Below-threshold candidates never reach aggregate_occurrences' own output at all, so the
        # bare count for the report is computed from the category universe, not from `all_candidates`.
        categories_seen = {occ.category for occ in occurrences}
        counts["below_threshold"] = len(categories_seen) - len(all_candidates)

        return _write_report(
            surviving,
            output_dir=output_dir,
            scan_window_end_date=scan_window_end_date,
            counts=counts,
        )
    finally:
        if handle is not None:
            handle.release()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--occurrences",
        type=Path,
        default=None,
        help="path to a JSON array of already-labeled occurrence objects "
        "({category, principle, pr_number, scope})",
    )
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_SPECS_DIR)
    parser.add_argument("--learned-conventions", type=Path, default=DEFAULT_LEARNED_CONVENTIONS_PATH)
    parser.add_argument("--scan-window-end-date", default=None)
    parser.add_argument("--no-lease", action="store_true", help="skip the scan-lease (tests only)")
    args = parser.parse_args(argv)

    report_path = generate_convention_scan_report(
        args.occurrences,
        repo=args.repo,
        output_dir=args.output_dir,
        learned_conventions_path=args.learned_conventions,
        scan_window_end_date=args.scan_window_end_date,
        use_scan_lease=not args.no_lease,
    )
    print(f"wrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
