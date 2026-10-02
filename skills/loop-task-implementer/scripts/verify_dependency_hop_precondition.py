#!/usr/bin/env python3
"""Hop-precondition gate for the dependency-upgrade-review -> loop-task-implementer handoff (Epic
C, C2).

Implements the design's final (revision 4) specification for the second piece of real code this
ticket adds -- see
``docs/superpowers/specs/2026-10-01-c2-dependency-upgrade-executor-handoff-design.md``. This
module's own docstrings state only this function's own narrow contract. The full extraction
contract this function's inputs depend on -- which lockfile to read per ecosystem, the exact
resolved-version field to extract, and the round-4 non-lockfile exact-pin fallback rule -- is
documented at ``docs/skill-framework/shared/dependency-upgrade-handoff.md``, not re-derived here,
mirroring ``classify_security_finding.py``'s own narrow-pure-function-plus-reference-doc split.

Why this function exists: a single dependency-upgrade request can require multiple, sequentially
dependent hops when the version distance is large enough that a direct jump is unsafe (one major
version per hop, per the design's Data model section). Revision 1 of the design asserted that
authoring hop N+1 before hop N's own PR had actually merged "would visibly mismatch... via the
Builder's own git state" -- an unconfirmed property stated as fact, never backed by real code. Round
1 adversarial review (Security Architect and SRE, independently) found this the central defect: a
premature or mis-ordered hop doesn't surface as an obviously mis-scoped task, it can silently execute
a larger, unintended version jump that still passes tests and review as an ordinary bump --
compounded by ``dependency-upgrade-review``'s own report format stating its inputs are "not validated
beyond presence," so a stale ``current_version`` is inherited silently rather than caught.
:func:`verify_dependency_hop_precondition` closes that gap by converting the disclosed convention
into a real, code-enforced precondition check, mirroring B3's own ``validate_repro_command``
precedent for exactly this class of problem (a safety-critical check that must not be left to
convention re-derived by eye on every call).

**This function does no file I/O of its own.** Reading the ecosystem's lockfile (or, per the
round-4 fallback, a manifest's own exact pin when no lockfile exists) to produce
``manifest_pinned_version`` is the caller's (the Builder's) own documented responsibility, per the
extraction contract in ``dependency-upgrade-handoff.md`` -- this function is a pure comparison only,
by design, the same narrow scope ``classify_security_finding.py``'s own module docstring describes
for its relationship to the security-review-handoff.md reference doc. Keeping this function pure
(no I/O, no network, no file access) makes it trivially, deterministically testable, and keeps the
per-ecosystem lockfile-discovery logic -- which does need to change as new ecosystems are added --
decoupled from this function's own, permanently narrow contract.

The single most important safety property of this function: it fails closed toward ``False`` on any
mismatch, including when either input is ``None``, empty, or otherwise not a clean string. It never
guesses or fails open toward ``True``. A false negative here (a hop that actually is at the correct
starting state, incorrectly reported as a mismatch) costs one unnecessary ``BLOCKED`` report and a
human re-check. A false positive (a hop that is NOT at the correct starting state, incorrectly
reported as matching) is the real failure this function exists to prevent, and exact string equality
with no normalization, trimming, or fuzzy comparison never produces that outcome.
"""

from __future__ import annotations


def verify_dependency_hop_precondition(
    manifest_pinned_version: str, expected_current_version: str
) -> bool:
    """Verify that a dependency's actual resolved version matches the version a stepwise upgrade
    hop expects to start from.

    Args:
        manifest_pinned_version: The dependency's actual, resolved, pinned version string, as
            already extracted by the caller (the Builder) from the ecosystem's real lockfile
            (``package-lock.json``/``yarn.lock``/``pnpm-lock.yaml``, ``poetry.lock``/
            ``Pipfile.lock``, ``Gemfile.lock``, ``go.sum``, ``Cargo.lock``) -- or, per the design's
            round-4 fallback, from a manifest's own exact pin when no ecosystem lockfile exists at
            all (e.g. a bare ``requirements.txt`` line with ``==``, no range operator). This
            function performs **no file I/O itself** and does not know or care which of those
            sources produced the value -- see ``dependency-upgrade-handoff.md`` for the full,
            per-ecosystem extraction contract, including the fail-closed default for any repo shape
            that fits neither case (no lockfile and no exact-pin manifest, the dependency absent
            from wherever was checked, or an undisambiguated monorepo/workspace). May be ``None`` or
            empty when the caller's own extraction found nothing.
        expected_current_version: This hop's own declared starting version -- the task's
            ``specialist_inputs.expected_current_version`` field (see the envelope-population
            mapping in ``dependency-upgrade-handoff.md``). May be ``None`` or empty in a malformed
            task.

    Returns:
        ``True`` only when both arguments are non-empty strings that are exactly equal
        (case-sensitive, no normalization, no version-semantics-aware comparison -- a plain string
        equality check). ``False`` on any mismatch, including when either argument is ``None``,
        empty, or not a string -- fail-closed. A ``False`` result means the Builder must stop
        immediately and report ``BLOCKED`` with the mismatch as evidence, never proceeding to Plan
        or Implement for this hop.
    """
    if not isinstance(manifest_pinned_version, str) or not manifest_pinned_version:
        return False
    if not isinstance(expected_current_version, str) or not expected_current_version:
        return False

    return manifest_pinned_version == expected_current_version
