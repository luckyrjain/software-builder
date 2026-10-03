#!/usr/bin/env python3
"""Classification gate for the incident-rca -> loop-task-implementer handoff (Epic C, C3).

Implements the design's final (revision 5) specification for one of the two pieces of real code this
ticket adds -- see
``docs/superpowers/specs/2026-10-02-c3-incident-rca-executor-handoff-design.md``. Full context for
this function's own population rules and the envelope it feeds is documented at
``docs/skill-framework/shared/incident-rca-handoff.md``; this module's docstrings state only this
function's own contract, not a re-derivation of that reference doc's broader content.

Why this function exists: the one thing this ticket exists to get right is separating a freestanding,
code-level ``Preventive actions`` row (no existing task or branch) from the existing
"incident-rca confirms a regression tied to a task branch" escalation row, and from corrective,
infrastructure-shaped or already-handled actions. Revision 1 of the design left that distinction to
prose. Round 1 review found it had no code behind it (the identical "claimed structural, actually
convention" defect C1 and C2 each hit), so every distinction below is an explicit, fail-closed
parameter at the function boundary instead.

Why each of the six axes exists (all six must hold; any other value is ``NOT_QUALIFYING``):

1. ``action_source == "preventive"`` -- the table the row came from. Population is structural (which
   real H2 heading the row sits under), never a judgment about the row's "nature" (round 2).
2. ``priority`` in ``{"P1", "P2"}`` -- an exact-match *allowlist*, trimmed of surrounding whitespace
   only. ``P0`` is ``report-template.md``'s documented Corrective signature, so this is the
   cross-check that catches a Corrective item misfiled under the Preventive heading, which axis 1
   alone cannot. Revision 3 used a ``!= "P0"`` denylist, which was fail-open (``p0``, ``P0/P1``,
   ``Sev0``, ``""`` and ``None`` all passed); revision 4 replaced it (round 4).
3. ``confidence`` -- receives the **raw Incident-scope ``Confidence`` cell**, not a pre-extracted
   token. The real gold shape is ``HIGH — deploy + error spike + diff on failing path``, so the whole
   cell never equals a bare enum value. This function takes the cell's first whitespace-delimited
   token, which must be exactly ``"HIGH"`` or ``"MEDIUM"`` (case-sensitive). The appendix metadata's
   lowercase ``confidence: high`` form is deliberately not accepted (round 4).
4. ``incident_class`` in ``{"Software defect", "Deploy"}`` -- exact match against ``incident-rca``'s
   real ``Incident class`` vocabulary (``skills/incident-rca/report-template.md``).
5. ``has_existing_task_branch is False`` -- an identity check; only the literal boolean ``False``
   passes. ``True``, ``None``, ``0`` and everything else fail closed. This is the explicit parameter
   that makes the "no existing task/branch" distinction a function-boundary property (round 2).
   Population is a caller-applied lookup convention (Orchestrator-side; ``None`` on any lookup
   failure), not code-enforced: a caller can still pass ``False`` without running a lookup. The
   parameter makes the distinction explicit and fail-closed here; it does not make the lookup
   enforced (round 5).
6. ``action_text`` passes a whole-cell keyword presence/absence check (no proximity window: the
   Preventive ``Action`` cell is a short phrase, not multi-sentence prose, so a word-distance window is
   nearly vacuous -- round 2). Preconditions, fail-closed: a ``str``; ``isascii()`` (Turkish dotted
   ``İ`` and a Cyrillic ``а`` otherwise evade the exclusion side after lowercasing -- round 5); at
   most 200 characters; no character with code point below 32 or equal to 127. Then, on the
   lowercased text: tokens come from ``[a-z0-9]+`` so hyphen, underscore and apostrophe *split* tokens
   (``waf-rule`` -> ``waf``, ``rule``) while digits stay inside a token (``k8s``, ``s3``, ``ec2``).
   The qualifying side is strict whole-token equality against an inflected verb set; at least one
   must be present. The exclusion side is stem-*prefix* matching and deliberately over-matches
   (``tokenizer``, ``retry policy``, ``scalar``, ``helmet`` are all excluded) because over-matching
   only yields a false ``NOT_QUALIFYING``, the safe direction. Four multi-word phrases (network policy,
   security group, load balancer, roll back) are matched as substrings of the lowercased text with
   every non-alphanumeric run removed, so camelCase and concatenated spellings (``LoadBalancer``,
   ``SecurityGroup``, ``NetworkPolicy``, ``loadbalancer``) are caught as well as spaced, hyphenated and
   underscored ones. Substring matching already over-matched mid-word before squashing (``scroll back``
   contains ``roll back``); squashing additionally ignores any separator, so ``load.balancer`` and
   ``network/policy`` match too. Over-matching is the safe direction.

**Disclosed evasion residual (stated honestly, not claimed solved).** The converse of the exclusion
list still qualifies: a qualifying verb plus an infrastructure noun that appears in none of the lists
(for example "Fix the data-store replication config") classifies ``QUALIFYING``. These keyword lists
are a best-effort first gate on a short string of untrusted text, **not** the control for
infrastructure changes. The real control is the deterministic diff-path check in
``skills/loop-task-implementer/workflow/reviewer.md`` Blocking-standard condition 9, which acts on
what the PR actually changed rather than on six words of untrusted summary text. Condition 7 remains
the backstop for the narrower credential/identity/secrets case.

The single most important safety property of this function: it fails closed toward
``NOT_QUALIFYING`` on any malformed, ``None``, empty, wrong-typed or unrecognized input on any
argument. It never fails open toward ``QUALIFYING``. It is pure: no I/O, no network, no state.
"""

from __future__ import annotations

import re
from typing import Literal

Classification = Literal["QUALIFYING", "NOT_QUALIFYING"]

_ALLOWED_PRIORITIES = frozenset({"P1", "P2"})
_ALLOWED_CONFIDENCE_TOKENS = frozenset({"HIGH", "MEDIUM"})
_ALLOWED_INCIDENT_CLASSES = frozenset({"Software defect", "Deploy"})

_MAX_ACTION_TEXT_CHARS = 200

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

# Qualifying side: strict whole-token equality. Inflections are listed explicitly, so "attestation"
# and "protest" never match "test".
_QUALIFYING_TOKENS = frozenset(
    {
        "fix", "fixes", "fixing",
        "patch", "patches", "patching",
        "validate", "validates", "validating", "validation",
        "handle", "handles", "handling",
        "correct", "corrects", "correcting",
        "test", "tests", "testing",
    }
)

# Exclusion side: any token that STARTS WITH one of these stems excludes. Deliberately over-matching.
_EXCLUSION_STEMS = (
    "alert", "dashboard", "runbook", "rollback", "scal", "autoscal", "capacit", "monitor",
    "architect", "refactor", "redesign", "decoupl", "migrat",
    "terraform", "cloudformation", "waf", "firewall", "iam", "kube", "k8s", "helm",
    "ingress", "gateway", "nginx", "envoy", "istio", "ansible", "pulumi", "cdk",
    "vpc", "subnet", "acl", "dns", "polic", "s3", "ec2",
    "credential", "secret", "password", "token",
)

# Multi-word exclusion phrases, stored without separators: they are matched against the lowercased text
# with every non-alphanumeric run removed, so "load balancer", "load-balancer", "LoadBalancer" and
# "loadbalancer" all hit.
_EXCLUSION_PHRASES = ("networkpolicy", "securitygroup", "loadbalancer", "rollback")


def _confidence_ok(confidence: object) -> bool:
    """True iff the first whitespace-delimited token of the raw cell is exactly HIGH or MEDIUM."""
    if not isinstance(confidence, str):
        return False
    parts = confidence.split()
    return bool(parts) and parts[0] in _ALLOWED_CONFIDENCE_TOKENS


def _action_text_ok(action_text: object) -> bool:
    """Axis 6: preconditions, then qualifying-token presence and exclusion-stem absence."""
    if not isinstance(action_text, str):
        return False
    if not action_text.isascii() or len(action_text) > _MAX_ACTION_TEXT_CHARS:
        return False
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in action_text):
        return False

    lowered = action_text.lower()
    tokens = _TOKEN_RE.findall(lowered)

    if not any(tok in _QUALIFYING_TOKENS for tok in tokens):
        return False
    if any(tok.startswith(_EXCLUSION_STEMS) for tok in tokens):
        return False

    squashed = _NON_ALNUM_RE.sub("", lowered)
    if any(phrase in squashed for phrase in _EXCLUSION_PHRASES):
        return False
    return True


def classify_incident_preventive_action(
    action_source: Literal["corrective", "preventive"],
    priority: str,
    confidence: str,
    incident_class: str,
    action_text: str,
    has_existing_task_branch: bool | None,
) -> Classification:
    """Classify one ``incident-rca`` Preventive-actions row for the incident-rca ->
    loop-task-implementer handoff.

    Args:
        action_source: ``"preventive"`` or ``"corrective"``, structurally derived from which H2
            heading the row appears under. Only the exact string ``"preventive"`` qualifies.
        priority: The row's own ``Priority`` cell, trimmed of surrounding whitespace only. Must be
            exactly ``"P1"`` or ``"P2"`` (case-sensitive allowlist).
        confidence: The RAW Incident-scope ``Confidence`` cell (for example
            ``"HIGH — deploy + error spike"``). Its first whitespace-delimited token must be exactly
            ``"HIGH"`` or ``"MEDIUM"`` (case-sensitive; lowercase ``"high"`` fails).
        incident_class: The report's ``Incident class``. Must be exactly ``"Software defect"`` or
            ``"Deploy"``.
        action_text: The row's own ``Action`` cell: untrusted data. Must be a short ASCII string
            with no control characters, containing a qualifying verb token and no infrastructure
            exclusion stem or phrase (see module docstring).
        has_existing_task_branch: Whether an existing ``loop-task-implementer`` task/branch already
            covers this action. Only the literal ``False`` qualifies; ``True``, ``None`` and every
            other value fail closed.

    Returns:
        ``"QUALIFYING"`` only when all six axes hold; ``"NOT_QUALIFYING"`` otherwise, including for
        any non-``str`` argument where a ``str`` is expected. Never raises on malformed input.
    """
    if not isinstance(action_source, str) or action_source != "preventive":
        return "NOT_QUALIFYING"
    if not isinstance(priority, str) or priority.strip() not in _ALLOWED_PRIORITIES:
        return "NOT_QUALIFYING"
    if not _confidence_ok(confidence):
        return "NOT_QUALIFYING"
    if not isinstance(incident_class, str) or incident_class not in _ALLOWED_INCIDENT_CLASSES:
        return "NOT_QUALIFYING"
    if has_existing_task_branch is not False:
        return "NOT_QUALIFYING"
    if not _action_text_ok(action_text):
        return "NOT_QUALIFYING"
    return "QUALIFYING"
