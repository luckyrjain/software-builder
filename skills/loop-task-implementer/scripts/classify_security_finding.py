#!/usr/bin/env python3
"""Classification gate for the security-review -> loop-task-implementer handoff (Epic C, C1).

Implements the design's final (revision 3) specification for the one piece of real code this
ticket adds — see
``docs/superpowers/specs/2026-10-01-c1-security-review-executor-handoff-design.md``. Full context
for this function's own population rule and the envelope it feeds is documented at
``docs/skill-framework/shared/security-review-handoff.md``; this module's docstrings state only
this function's own contract, not a re-derivation of that reference doc's broader content.

Why this function exists (the central defect this design's own review history found and fixed):
revision 1 of the design claimed the rotation/fix split was "structurally impossible" to conflate
while describing it only as a documented, prose-level convention a human applies by eye. That claim
was false -- nothing in the repository's own untyped ``implementation_task`` envelope stopped a
human or Orchestrator from hand-authoring a rotation-shaped task anyway. :func:`classify_security_finding`
closes that gap by making the classification a real, tested, deterministic function call instead of
a convention -- mirroring ``skills/bug-diagnosis``'s own ``validate_repro_command`` precedent for
exactly this class of problem (a safety-critical classification that must not be left to prose
judgment re-derived by eye on every call).

**This function is a strong, fail-closed FIRST gate -- it is not, by itself, the structural
backstop against autonomous credential rotation.** The real structural backstop is that the
Builder has no code path to any live external credential-management system (a cloud provider's
IAM, a secrets vault, a CI/CD secret store) anywhere in this framework, today, independent of
this ticket -- a true capability absence, not a configurable gate this function could be a
substitute for. This function's own keyword/severity heuristic is deliberately simple and known
to be evadable by ordinary paraphrase (e.g. "Request a new value from the identity provider and
update the config" describes rotation with zero keyword overlap, and this function classifies it
``QUALIFYING`` -- a disclosed, documented limitation, not a silently-accepted gap). Blocking-standard
condition 7 in ``skills/loop-task-implementer/workflow/reviewer.md`` is the independent, downstream
backstop for exactly this case: it fires on the resulting task's own ``scope``/``acceptance_criteria``
content at review time, regardless of whether this function was ever called, called correctly, or
evaded by paraphrase.

The single most important safety property of this function: it fails closed toward
``ROTATION_REQUIRED`` on any ambiguous, malformed, ``None``, or empty input. It never fails open
toward ``QUALIFYING``. A false positive here (an ordinary code fix incorrectly routed to
human-action-required) costs one unnecessary human review. A false negative (a rotation-requiring
finding incorrectly routed to an autonomous task) is the real failure this function exists to
prevent.
"""

from __future__ import annotations

import re
from typing import Literal

Classification = Literal["QUALIFYING", "ROTATION_REQUIRED", "NOT_QUALIFYING"]

# security-review's own real verdict vocabulary (skills/security-review/reference/report-format.md):
# "Critical | High | Medium | Low | -". Case-sensitive match -- this handoff's severity floor.
_QUALIFYING_SEVERITIES = frozenset({"Critical", "High", "Medium"})

# Rotation-action keywords (case-insensitive). Any of these appearing near a credential-noun below
# routes to ROTATION_REQUIRED.
_ROTATION_ACTION_WORDS = (
    "rotate",
    "revoke",
    "reissue",
    "re-issue",
    "regenerate",
)

# Credential-noun keywords (case-insensitive).
_CREDENTIAL_NOUN_WORDS = (
    "credential",
    "secret",
    "key",
    "token",
    "password",
)

# Proximity window: an action keyword and a noun keyword are "near" each other when no more than
# this many words separate them (in either direction), a concrete, documented window size per the
# design's own API contract ("within a short word-distance window -- pick a concrete, documented
# window size, e.g. within 10 words").
_PROXIMITY_WINDOW_WORDS = 10

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")


def _tokenize(text: str) -> list[str]:
    """Lowercase word tokens, in order, for proximity scanning."""
    return [match.group(0).lower() for match in _WORD_RE.finditer(text)]


def _rotation_keywords_in_proximity(recommendation_text: str) -> bool:
    """Return True iff a rotation-action keyword and a credential-noun keyword appear within
    ``_PROXIMITY_WINDOW_WORDS`` words of each other, anywhere in ``recommendation_text``.

    Matching is on whole word tokens (not substrings), case-insensitive, order-independent (the
    noun may precede or follow the action word). This is a deliberately simple, conservative
    heuristic -- see the module docstring for its known paraphrase-evasion limitation and the
    disclosed downstream backstop for it.
    """
    tokens = _tokenize(recommendation_text)
    action_positions = [i for i, tok in enumerate(tokens) if tok in _ROTATION_ACTION_WORDS]
    if not action_positions:
        return False
    noun_positions = [i for i, tok in enumerate(tokens) if tok in _CREDENTIAL_NOUN_WORDS]
    if not noun_positions:
        return False
    for a in action_positions:
        for n in noun_positions:
            if abs(a - n) <= _PROXIMITY_WINDOW_WORDS:
                return True
    return False


def classify_security_finding(recommendation_text: str, severity: str) -> Classification:
    """Classify a security-review finding for the security-review -> loop-task-implementer handoff.

    Args:
        recommendation_text: The finding's own ``Recommendation`` cell text (already Rule-5
            redacted by the caller per the envelope-population mapping -- this function does not
            redact; it only classifies). May be ``None`` or empty.
        severity: The finding's own ``Severity`` cell text, expected to be one of
            ``security-review``'s real verdict vocabulary (``"Critical"``, ``"High"``,
            ``"Medium"``, ``"Low"``, ``"-"``), case-sensitive. May be ``None`` or any other value.

    Returns:
        ``"NOT_QUALIFYING"`` when ``severity`` is not exactly one of ``{"Critical", "High",
        "Medium"}`` (case-sensitive) -- this includes ``None``, ``"Low"``, ``"-"``, empty string,
        or any unrecognized value. This check runs first and takes precedence: a Low-severity
        finding with rotation-shaped language is still ``NOT_QUALIFYING``, not
        ``ROTATION_REQUIRED`` -- it never reaches the rotation-classification handoff regardless of
        its wording, since it never qualifies for this handoff in the first place.

        Otherwise (severity qualifies), ``"ROTATION_REQUIRED"`` when ``recommendation_text`` is
        ``None``, empty/whitespace-only, or contains a rotation-action keyword
        (``rotate``/``revoke``/``reissue``/``regenerate``/``re-issue``) within
        :data:`_PROXIMITY_WINDOW_WORDS` words of a credential-noun keyword
        (``credential``/``secret``/``key``/``token``/``password``), all case-insensitive. Ambiguous
        or malformed ``recommendation_text`` (anything that is not a non-empty string) also fails
        closed to ``"ROTATION_REQUIRED"`` here -- never ``"QUALIFYING"``.

        Otherwise, ``"QUALIFYING"``.
    """
    if severity not in _QUALIFYING_SEVERITIES:
        return "NOT_QUALIFYING"

    if not isinstance(recommendation_text, str) or not recommendation_text.strip():
        # Ambiguous/malformed/None/empty input, with a qualifying severity: fail closed.
        return "ROTATION_REQUIRED"

    if _rotation_keywords_in_proximity(recommendation_text):
        return "ROTATION_REQUIRED"

    return "QUALIFYING"
