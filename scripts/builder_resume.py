"""Pure resume-decision logic for a redispatched Builder on a deterministic task branch (gap-backlog A5).

Builder is architecturally barred from the run log and from ``plan_execution_state`` (only the
Orchestrator mutates either, per ``orchestrator.md``'s own doctrine) -- so a Builder in-flight
checkpoint cannot use a new storage channel without widening Builder's persistence surface for no
benefit git does not already provide (the A5 architecture review's own "why not a third persistence
channel" analysis). Instead, ``builder.md``'s commit/push cadence moves from "once, at the very end"
to "after each milestone", each commit's message carrying a ``Checkpoint: <token>`` trailer (see
``skills/loop-task-implementer/workflow/builder.md`` §6). A crash after milestone N leaves real
git-native evidence the Orchestrator's *already-existing* branch/PR verification logic
(``orchestrator.md`` §5) can observe on the next pass -- this module is the pure decision function
that turns that observed commit list into a resume verdict.

This module does no I/O of its own: the Orchestrator gathers ``branch_commits`` itself (it already
does, per §5) and passes them in. Nothing here fetches, greps a diff, or shells out.

**Trust boundary, stated explicitly (Condition 4 of the architecture review).** A commit message is
Builder-authored, PR-author-adjacent content -- not adversarial the way an external PR author's diff
is, but still a claim, not verified fact. ``decide()``'s ``CONTINUE_FROM`` result is a hint about
*where* to resume from, never a certificate that the prior work up to that point was correct. The
Orchestrator always independently re-verifies the branch's actual current state (re-runs tests,
re-inspects the diff) before proceeding on a ``CONTINUE_FROM`` -- consistent with this skill's
existing "Builder prose is never sole source of merge-gate truth" doctrine (``orchestrator.md`` §13).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

# The two valid milestone tokens, in the order builder.md requires them to appear: a `tests-passing`
# checkpoint is only ever meaningful after an `implementation-complete` one landed first, since §4's
# full test run happens after §3's implementation is functionally complete. Kept as an explicit,
# ordered tuple (not scattered string comparisons) so a future third milestone has one place to add
# its ordering rule.
CHECKPOINT_MARKERS: tuple[str, ...] = ("implementation-complete", "tests-passing")

# A `Checkpoint: <token>` trailer, one token, trailing whitespace tolerated. Matches the last such
# line anywhere in the commit message (a trailer block conventionally sits at the end, but this does
# not require it to be the literal last line of the message -- only the last matching line wins, per
# ordinary git-trailer convention of "last occurrence of a repeated trailer key governs").
_CHECKPOINT_TRAILER_RE = re.compile(r"(?m)^Checkpoint:[ \t]*(\S+)[ \t]*$")


def parse_checkpoint_marker(message: str) -> str | None:
    """Return the last ``Checkpoint: <token>`` trailer found in ``message``, or ``None`` if absent.

    Does not validate ``token`` against :data:`CHECKPOINT_MARKERS` -- an unrecognized token is
    returned as-is; it is :func:`decide`'s job to treat it as not-a-recognized-marker.
    """
    matches = _CHECKPOINT_TRAILER_RE.findall(message)
    return matches[-1] if matches else None


@dataclass(frozen=True)
class CommitInfo:
    """One commit on the branch under consideration, in the shape the Orchestrator's existing §5
    branch verification already gathers (sha + message), plus the parsed checkpoint marker."""

    sha: str
    message: str
    checkpoint_marker: str | None = None

    @classmethod
    def from_commit(cls, sha: str, message: str) -> "CommitInfo":
        """Convenience constructor: parses ``checkpoint_marker`` out of ``message`` automatically."""
        return cls(sha=sha, message=message, checkpoint_marker=parse_checkpoint_marker(message))


@dataclass(frozen=True)
class ResumeDecision:
    action: Literal["FROM_SCRATCH", "CONTINUE_FROM", "ESCALATE"]
    last_marker: str | None
    resume_head: str | None
    reason: str


def decide(branch_commits: list[CommitInfo], base_revision: str) -> ResumeDecision:
    """Decide whether a redispatched Builder should start ``FROM_SCRATCH``, ``CONTINUE_FROM`` a known
    checkpoint, or the Orchestrator should ``ESCALATE`` because the branch's state is ambiguous.

    ``branch_commits`` must be supplied in chronological order, oldest first (the same order the
    Orchestrator's own git log gathering naturally produces) -- ordering validation below depends on
    it. ``base_revision`` is accepted for interface completeness / future use (e.g. distinguishing
    "no commits since base" from "no commits at all") but is not otherwise consulted here: an empty
    ``branch_commits`` list is by itself sufficient to mean "nothing to resume", regardless of what
    ``base_revision`` is.

    Decision rules, in order:

    - No commits at all -> ``FROM_SCRATCH``.
    - A ``tests-passing`` marker appears before any ``implementation-complete`` marker earlier in the
      list -> ``ESCALATE`` (out-of-order marker; an unrecognized/ambiguous state per the design's
      failure-strategy table, never guessed at).
    - Commits exist and the most recent commit's marker is a recognized token (and ordering above is
      valid) -> ``CONTINUE_FROM`` that marker and that commit's sha.
    - Otherwise (no commit anywhere carries a recognized marker, or the most recent commit does not
      even though an earlier one did) -> ``ESCALATE``, matching ``orchestrator.md`` §16's existing
      handling for an unrecognized/third-party branch change: this function never guesses at a resume
      point it cannot name with confidence.
    """
    if not branch_commits:
        return ResumeDecision(
            action="FROM_SCRATCH",
            last_marker=None,
            resume_head=None,
            reason=f"no commits found on the branch since base_revision {base_revision!r}; nothing to resume",
        )

    implementation_complete_seen = False
    any_recognized = False
    out_of_order = False
    for commit in branch_commits:
        marker = commit.checkpoint_marker
        if marker not in CHECKPOINT_MARKERS:
            continue
        any_recognized = True
        if marker == "implementation-complete":
            implementation_complete_seen = True
        elif marker == "tests-passing" and not implementation_complete_seen:
            out_of_order = True

    if out_of_order:
        return ResumeDecision(
            action="ESCALATE",
            last_marker=None,
            resume_head=None,
            reason=(
                "a 'tests-passing' Checkpoint trailer appears with no earlier 'implementation-complete' "
                "trailer in the same commit list; treating branch state as unrecognized rather than "
                "guessing at a resume point (orchestrator.md §16)"
            ),
        )

    last_commit = branch_commits[-1]
    if last_commit.checkpoint_marker in CHECKPOINT_MARKERS:
        return ResumeDecision(
            action="CONTINUE_FROM",
            last_marker=last_commit.checkpoint_marker,
            resume_head=last_commit.sha,
            reason=(
                f"most recent commit {last_commit.sha} carries a valid 'Checkpoint: "
                f"{last_commit.checkpoint_marker}' trailer; resume from there, but independently "
                "re-verify branch state (tests, diff) before proceeding -- this is a hint about where, "
                "never a certificate that prior work is correct"
            ),
        )

    if any_recognized:
        return ResumeDecision(
            action="ESCALATE",
            last_marker=None,
            resume_head=None,
            reason=(
                "an earlier commit carries a recognized Checkpoint trailer, but the most recent commit "
                "does not; branch state is ambiguous rather than cleanly resumable (orchestrator.md §16)"
            ),
        )

    return ResumeDecision(
        action="ESCALATE",
        last_marker=None,
        resume_head=None,
        reason=(
            "commits exist on the branch but none carry a recognized Checkpoint trailer; likely a "
            "third-party or unexpected push (orchestrator.md §16)"
        ),
    )
