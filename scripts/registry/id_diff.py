"""Shared "found ids vs registered ids" two-way diff, used by the doc sync
validators (routing_sync.py) so the dangling vs. missing wording and set-diff
semantics can't drift between them.
"""
from __future__ import annotations


def report_id_coverage(
    found: set[str],
    registered: set[str],
    *,
    dangling_label: str,
    missing_label: str,
    exempt: frozenset[str] = frozenset(),
) -> list[str]:
    errors: list[str] = []
    dangling = sorted(found - registered - exempt)
    if dangling:
        errors.append(f"{dangling_label}: " + ", ".join(dangling))
    missing = sorted(registered - found)
    if missing:
        errors.append(f"{missing_label}: " + ", ".join(missing))
    return errors
