"""The execution-status half of the shared runtime result envelope.

Every assessment skill reports on two independent axes: a *verdict* in its own domain vocabulary
(READY/NOT_READY, PASS/FAIL, Approved with conditions, ...) and an *execution status* saying
whether the skill itself finished the analysis. Only the verdict vocabulary genuinely varies per
skill; the execution axis is one doctrine, stated once here:

* a required input the skill could not even read is a **blocker** -- the run is `BLOCKED`;
* a required dimension the skill read but could not resolve is an **unknown** -- the run is
  `PARTIAL`, regardless of how favourable or unfavourable the verdict happens to be;
* otherwise the run is `SUCCESS`.

Evidence status follows the same split: anything unresolved makes the evidence `UNKNOWN`, never
`OBSERVED`. A resolved bad-news verdict (NOT_READY, FAIL) is a `SUCCESS`ful analysis.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass


@dataclass(frozen=True)
class SkillResult:
    """The subset of the result envelope that carries execution status, shared by every skill.

    `blockers` carries the skill's own machine-readable reasons for a non-SUCCESS status.
    `state_semantic` records whether the analysed material is the current or a proposed state;
    skills that only ever assess a proposal keep the default.
    """

    status: str
    evidence_status: str = "UNKNOWN"
    blockers: tuple[str, ...] = ()
    state_semantic: str = "proposed_state"


def derive_execution_status(
    *,
    blockers: Collection[object] = (),
    unknowns: Collection[object] = (),
) -> tuple[str, str]:
    """Apply the axis split, returning `(status, evidence_status)`.

    `blockers` are unreadable required inputs; `unknowns` are required dimensions that were read
    but left unresolved. Both are taken by emptiness only, so a caller may pass whatever carrier
    it already has (a list of names, a set of dimensions, a list of gap records).
    """
    if blockers:
        return "BLOCKED", "UNKNOWN"
    if unknowns:
        return "PARTIAL", "UNKNOWN"
    return "SUCCESS", "OBSERVED"
