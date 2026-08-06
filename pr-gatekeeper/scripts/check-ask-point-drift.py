#!/usr/bin/env python3
"""check-ask-point-drift.py — heuristic drift check for pr-gatekeeper/reference/auto-post-policy.md.

WHY THIS EXISTS
----------------
auto-post-policy.md hand-enumerates every point pr-review stops and waits for a human reply, each
with pr-gatekeeper's deterministic scripted answer, so an unattended webhook run never hangs. That
enumeration is *copied prose* — nothing mechanically checks it against pr-review's own,
independently-versioned workflow files. If a future pr-review edit adds a new ask-point ("wait for
the user", a new `ask-question` call, a new "stop and warn ... unless the user confirms" gate, etc.)
that auto-post-policy.md doesn't cover, an unattended pr-gatekeeper-driven run would hang forever on
that new gate the first time it fires.

This script scans pr-review's *current* `workflow/*.md` files for ask-point-shaped text and checks
that each one has at least loose lexical overlap with auto-post-policy.md. It cannot understand
whether the automation's *answer* to a gate is still correct (that requires reading the prose) — it
only tries to catch the case where a gate exists in pr-review with **no trace of it at all** in
auto-post-policy.md, which is the specific failure mode that causes a silent hang.

RUN THIS after any edit to pr-review/workflow/*.md, and after any edit to
pr-gatekeeper/reference/auto-post-policy.md itself:

    python3 pr-gatekeeper/scripts/check-ask-point-drift.py

Exit code 0 = no new/uncovered ask-point-shaped text found (or only pre-approved exclusions).
Exit code 1 = at least one pr-review paragraph looks ask-point-shaped but shares too little
              vocabulary with auto-post-policy.md — treat as a probable drift and go read the
              flagged paragraph by hand; either update auto-post-policy.md (add the new ask-point
              and its deterministic answer) or, if it's a false positive, add a narrowly-scoped
              exception below with a comment explaining why.

KNOWN LIMITATIONS (read before trusting a clean run)
-----------------------------------------------------
1. This is a lexical-overlap heuristic, not a semantic check. It cannot verify that
   pr-gatekeeper's *documented answer* to a gate is still one of the options pr-review's prompt
   actually offers (e.g. if pr-review renames a button label, this script stays green). It only
   catches a gate that has gone entirely undocumented.
2. It scans `pr-review/workflow/*.md` only, not `pr-review/reference/*.md`. Ask-points that live
   only in a reference file, reached through a workflow file that never *quotes* them, will not be
   directly scanned — as of this writing there is no such case (every ask-point traced during audit
   has a describing sentence in a workflow file too), but that could change.
3. `inputs.md` is deliberately excluded — see EXCLUDED_FILES below. If pr-review's typed-invocation
   precedence changes so that a supplied `project`/`merge_request_iid` pair can still fall through
   to interactive MR resolution, this exclusion would hide that regression. Re-check by hand after
   any edit to `pr-review/workflow/inputs.md`'s typed-invocation section.
4. A careless (or adversarial) edit to auto-post-policy.md that pads it with the right *keywords*
   without actually documenting a deterministic answer would still pass this check — it verifies
   vocabulary overlap, not that a real answer was given. This script is a tripwire for gross drift
   (a brand-new ask-point with literally nothing said about it), not a substitute for the human
   review a prompt-engineering change should get.
5. The overlap threshold (OVERLAP_THRESHOLD below) was tuned against the repo state at the time
   this script was written (pr-review workflow_version 1.4 across all phase files). If pr-review's
   prose style changes significantly (much terser or much more verbose paragraphs), false positives
   or false negatives may drift — re-tune if this starts crying wolf on unchanged gates.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PR_REVIEW_WORKFLOW_DIR = REPO_ROOT / "pr-review" / "workflow"
AUTO_POST_POLICY = REPO_ROOT / "pr-gatekeeper" / "reference" / "auto-post-policy.md"

# See KNOWN LIMITATIONS #3 above.
EXCLUDED_FILES = {"inputs.md"}

# Ask-point-shaped signals, tuned against the actual phrasing pr-review uses today (see the audit
# that produced this script: grep -niE across pr-review/workflow/*.md for "ask", "wait for the
# user", "pause execution", "HARD STOP", "stop and/or warn", "offer", "confirm"). Kept broad on
# purpose — false positives here just mean one more paragraph a maintainer skims; false negatives
# mean a real gate slips through undetected, which is the failure mode this script exists to catch.
MARKER_PATTERNS = [
    re.compile(r"wait\s+for\s+(?:the\s+)?user", re.IGNORECASE),
    re.compile(r"pause\s+execution", re.IGNORECASE),
    re.compile(r"ask-question", re.IGNORECASE),
    re.compile(r"\bhard\s+stop\b", re.IGNORECASE),
    re.compile(r"stop(?:s|ped)?\s+(?:and|or)\s+(?:warn|report)", re.IGNORECASE),
    re.compile(r"unless\s+(?:the\s+)?user\s+(?:confirms?|explicitly\s+asks?|acknowledg\w*)", re.IGNORECASE),
    re.compile(r"offers?\s+(?:a\s+|the\s+)?full\s+re-review", re.IGNORECASE),
    re.compile(r"offer\s+to\s+post", re.IGNORECASE),
    re.compile(r"proceed\s+only\s+(?:if|on)\s+(?:the\s+)?user\s+confirm", re.IGNORECASE),
    re.compile(r"do\s+not\s+proceed\s+.{0,60}?until\s+the\s+user", re.IGNORECASE | re.DOTALL),
    re.compile(r"ask\s+(?:the\s+)?user\s+whether", re.IGNORECASE),
    re.compile(r"ask\s+before\s+paginating", re.IGNORECASE),
    re.compile(r"stop\s*:\s*[*\"]", re.IGNORECASE),
]

# Overlap ratio (shared significant words / paragraph's significant words) below which a flagged
# paragraph is treated as undocumented drift. See KNOWN LIMITATIONS #5.
OVERLAP_THRESHOLD = 0.30

# Common words long enough to pass the 5-char filter but too generic to count as "coverage" evidence.
STOPWORDS = {
    "before", "after", "always", "never", "under", "there", "their", "which", "where", "while",
    "would", "should", "could", "about", "again", "still", "these", "those", "other", "first",
    "phase", "review", "reviewer", "reviews", "workflow", "gitlab", "posting", "posted", "unless",
    "explicit", "explicitly", "prompt", "prompts", "render", "renders", "output", "outputs",
}

WORD_RE = re.compile(r"[a-z][a-z\-]{4,}")


def normalize_markdown(text: str) -> str:
    """Blank out markdown noise (** _ ` > # and [label](url) parens/url) while preserving every
    character's original offset and every newline — so match positions and line numbers computed
    against the *normalized* text stay valid against the *original* text. Only single characters or
    fixed noise runs are replaced with spaces of equal length; nothing is deleted."""
    text = re.sub(r"[*_`>#]", " ", text)
    # [label](url) -> "label " + spaces where "(url)" was, keeping length identical.
    def _delink(m: re.Match) -> str:
        label = m.group(1)
        rest = m.group(0)[len(m.group(1)) + 2 :]  # the "](url)" tail after "[label"
        return " " + label + " " * (len(rest) - 1)

    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", _delink, text)
    return text


def significant_words(text: str) -> set[str]:
    return {w for w in WORD_RE.findall(text.lower()) if w not in STOPWORDS}


# Characters of surrounding context pulled around each marker match to build its lexical
# "signature" — narrow enough to stay on-topic (pr-review's workflow files pack multiple
# unrelated concerns into single unbroken paragraphs, e.g. phase-1.md step 1), wide enough to
# capture the sentence(s) actually describing the gate.
CONTEXT_CHARS = 280


def marker_matches(normalized_text: str) -> list[tuple[int, int]]:
    """Return (start, end) spans for every MARKER_PATTERNS hit, de-duplicated by overlap."""
    spans: list[tuple[int, int]] = []
    for pattern in MARKER_PATTERNS:
        for m in pattern.finditer(normalized_text):
            spans.append((m.start(), m.end()))
    spans.sort()
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1] + 40:  # close enough: same gate, same context window
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def main() -> int:
    if not AUTO_POST_POLICY.is_file():
        print(f"error: {AUTO_POST_POLICY} not found", file=sys.stderr)
        return 1
    if not PR_REVIEW_WORKFLOW_DIR.is_dir():
        print(f"error: {PR_REVIEW_WORKFLOW_DIR} not found", file=sys.stderr)
        return 1

    doc_words = significant_words(AUTO_POST_POLICY.read_text(encoding="utf-8"))

    workflow_files = sorted(
        f for f in PR_REVIEW_WORKFLOW_DIR.glob("*.md") if f.name not in EXCLUDED_FILES
    )
    if not workflow_files:
        print("error: no pr-review/workflow/*.md files found to scan", file=sys.stderr)
        return 1

    flagged: list[tuple[str, int, str, float]] = []
    scanned_markers = 0

    for wf in workflow_files:
        original = wf.read_text(encoding="utf-8")
        normalized = normalize_markdown(original)
        for start, end in marker_matches(normalized):
            scanned_markers += 1
            line_no = normalized.count("\n", 0, start) + 1
            ctx_start = max(0, start - CONTEXT_CHARS)
            ctx_end = min(len(normalized), end + CONTEXT_CHARS)
            context = normalized[ctx_start:ctx_end]
            sig = significant_words(context)
            if not sig:
                continue
            overlap = len(sig & doc_words) / len(sig)
            if overlap < OVERLAP_THRESHOLD:
                snippet = original[ctx_start:ctx_end]
                flagged.append((str(wf.relative_to(REPO_ROOT)), line_no, snippet.strip(), overlap))

    print(f"check-ask-point-drift: scanned {len(workflow_files)} pr-review workflow file(s) "
          f"({', '.join(f.name for f in workflow_files)})")
    print(f"check-ask-point-drift: {scanned_markers} ask-point-shaped paragraph(s) found")

    if flagged:
        print(
            f"\nerror: {len(flagged)} ask-point-shaped paragraph(s) in pr-review/workflow/*.md "
            f"have < {OVERLAP_THRESHOLD:.0%} word overlap with "
            f"pr-gatekeeper/reference/auto-post-policy.md — possible undocumented ask-point drift.\n",
            file=sys.stderr,
        )
        for path, line_no, para, overlap in flagged:
            snippet = re.sub(r"\s+", " ", para)[:220]
            print(f"  {path}:~{line_no} (overlap {overlap:.0%})", file=sys.stderr)
            print(f"    {snippet}", file=sys.stderr)
        print(
            "\nIf this is a genuinely new ask-point: add it to auto-post-policy.md's numbered "
            "enumeration with pr-gatekeeper's deterministic answer, then re-run this script.\n"
            "If this is a false positive (paraphrase, unrelated 'stop'/'ask' text): either tighten "
            "MARKER_PATTERNS or add a narrowly-scoped exception with a comment explaining why — do "
            "not raise OVERLAP_THRESHOLD globally to silence one paragraph.",
            file=sys.stderr,
        )
        return 1

    print("check-ask-point-drift: ok — no undocumented ask-point-shaped text found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
