#!/usr/bin/env python3
"""Classification gate for the dependency-upgrade-review -> loop-task-implementer handoff (Epic C, C2).

Implements the design's final (revision 4) specification for one of the two pieces of real code this
ticket adds -- see
``docs/superpowers/specs/2026-10-01-c2-dependency-upgrade-executor-handoff-design.md``. Full context
for this function's own population rule and the envelope it feeds is documented at
``docs/skill-framework/shared/dependency-upgrade-handoff.md``; this module's docstrings state only
this function's own contract, not a re-derivation of that reference doc's broader content.

Why this function exists: ``dependency-upgrade-review``'s own report format
(``skills/dependency-upgrade-review/reference/report-format.md``) already reduces an upgrade
assessment to a clean, closed, four-state verdict enum -- ``"Safe to upgrade"``,
``"Upgrade with mitigations"``, ``"Do not upgrade yet"``, ``"Blocked — insufficient info"``. Unlike
C1's own ``classify_security_finding`` (which has to classify free-text ``Recommendation`` prose),
this handoff's input is already a closed vocabulary, so no NLP-style heuristic is needed here -- a
simple, exact-string-match function is genuinely sufficient (the design's own explicit reasoning,
confirmed by both architecture-review and three adversarial design-review rounds). What the design's
own round-2 review found missing is the *extraction* step: the report never hands a caller a bare
state string -- the real rendered line is ``**Verdict: <state>**`` (literal bold markers and
prefix), and one of the four canonical states contains a Unicode em-dash (``"Blocked — insufficient
info"``, U+2014), not a hyphen. A naive implementation that skipped stating the extraction contract
explicitly, or that silently substituted a plain hyphen for the em-dash, could route a qualifying
report to ``NOT_QUALIFYING`` forever (or vice versa) without ever raising an error -- the same
"a function's exact-match contract is only as good as its never-before-specified extraction step"
bug class C1's own round-3 ``validate_repro_command`` fix closed in its own domain. This function
closes that gap by stating and applying the extraction regex explicitly, rather than assuming every
caller extracts the state identically.

**This function's own classification is exact-string-match only -- no NLP, no heuristic, no partial
or fuzzy matching.** That is a deliberate, documented choice, not an oversight: the input vocabulary
is already closed and enforced upstream by ``report-format.md`` itself, so the kind of
paraphrase-evasion risk C1's own keyword/proximity heuristic has to disclose as a known limitation
does not apply here.

The single most important safety property of this function: it fails closed toward
``NOT_QUALIFYING`` on any ambiguous, malformed, ``None``, empty, or unrecognized input -- including a
future fifth verdict state this report format might one day add. It never fails open toward
``QUALIFYING``. A false positive here (a genuinely non-qualifying report routed to
``NOT_QUALIFYING`` when it need not have been) cannot happen by construction, since
``NOT_QUALIFYING`` is this function's own fail-closed default. A false negative (a qualifying report
silently routed to ``NOT_QUALIFYING``) costs one unnecessary human read of the report; the reverse --
a non-qualifying report silently routed to ``QUALIFYING`` -- is the real failure this function exists
to prevent, and the exact-match discipline below never does that.
"""

from __future__ import annotations

import re
from typing import Literal

Classification = Literal["QUALIFYING", "NOT_QUALIFYING"]

# dependency-upgrade-review's own real, fixed, four-state verdict vocabulary
# (skills/dependency-upgrade-review/reference/report-format.md). Exact string match, including the
# literal U+2014 em-dash in "Blocked — insufficient info" (not a hyphen).
_QUALIFYING_STATES = frozenset({"Safe to upgrade", "Upgrade with mitigations"})
_NON_QUALIFYING_STATES = frozenset({"Do not upgrade yet", "Blocked — insufficient info"})

# The real rendered verdict line from the report (report-format.md's "Structure" section):
# "**Verdict: <state>**" -- literal bold markers and a "Verdict:" prefix, the state captured in
# group 1. Applied against the FULL line as it appears in a rendered report.
_VERDICT_LINE_RE = re.compile(r"^\*\*Verdict:\s*(.+?)\*\*$")


def _extract_state(verdict: str) -> str:
    """Return the bare state string for ``verdict``.

    Accepts either the full rendered ``**Verdict: <state>**`` line (as it appears in a rendered
    ``DEPENDENCY_UPGRADE_REPORT.md``) or a state string a caller has already extracted by its own
    means -- callers may extract differently (e.g. a caller that already parsed the report into a
    structured object may hand this function the bare state directly). When ``verdict`` matches the
    full-line pattern, the captured group is returned; otherwise ``verdict`` itself is returned
    unchanged, so a pre-extracted bare state passes through untouched.
    """
    match = _VERDICT_LINE_RE.match(verdict)
    if match is not None:
        return match.group(1)
    return verdict


def classify_dependency_upgrade(verdict: str) -> Classification:
    """Classify a dependency-upgrade-review verdict for the dependency-upgrade-review ->
    loop-task-implementer handoff.

    Args:
        verdict: Either the full rendered verdict line from a ``DEPENDENCY_UPGRADE_REPORT.md``
            (``"**Verdict: <state>**"``, literal bold markers and prefix), or a bare,
            already-extracted state string (e.g. ``"Safe to upgrade"``). Both forms are accepted --
            see :func:`_extract_state`. May be ``None``, empty, whitespace-only, or any other
            malformed value.

    Returns:
        ``"QUALIFYING"`` when the extracted/given state is exactly (case-sensitive, exact string
        match, no trimming beyond what the extraction regex itself performs) one of
        ``"Safe to upgrade"`` or ``"Upgrade with mitigations"``.

        ``"NOT_QUALIFYING"`` otherwise -- this includes the two real non-qualifying states
        (``"Do not upgrade yet"``, ``"Blocked — insufficient info"``, the second with a literal
        U+2014 em-dash, not a hyphen substitute), ``None``, empty or whitespace-only input, any
        string that doesn't match the full-line extraction pattern and also isn't one of the four
        canonical states verbatim, and any unrecognized/future verdict state. This is the fail-closed
        default: ambiguous or malformed input never routes to ``QUALIFYING``.
    """
    if not isinstance(verdict, str) or not verdict.strip():
        return "NOT_QUALIFYING"

    state = _extract_state(verdict)

    if state in _QUALIFYING_STATES:
        return "QUALIFYING"

    if state in _NON_QUALIFYING_STATES:
        return "NOT_QUALIFYING"

    # Unrecognized/malformed/future verdict state -- fail closed, never QUALIFYING.
    return "NOT_QUALIFYING"
