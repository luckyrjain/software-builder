#!/usr/bin/env python3
"""Helpers for weekly-squad-digest cross-rollup grouping."""

from __future__ import annotations

import re
from typing import Any


def normalize_service_token(value: str) -> str:
    """Normalize service identifiers for cross-rollup matching.

    Case- and separator-insensitive (``api-payments`` == ``API_Payments``) without
    collapsing distinct names (``myapp`` != ``my-app``).
    """
    parts = [p for p in re.split(r"[^a-zA-Z0-9]+", value.strip().lower()) if p]
    return "-".join(parts)


def find_cross_rollup_service_pairs(
    migration_items: list[dict[str, Any]],
    cost_items: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Return migration/cost item pairs that refer to the same service under different squads.

    Matches on normalized ``service`` tokens. When multiple items share a token in one
    rollup, every distinct squad pairing is returned.
    """
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []

    def bucket(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            service = str(item.get("service", "")).strip()
            if not service:
                continue
            out.setdefault(normalize_service_token(service), []).append(item)
        return out

    mig_by_token = bucket(migration_items)
    cost_by_token = bucket(cost_items)
    for token in sorted(set(mig_by_token) & set(cost_by_token)):
        for mig in mig_by_token[token]:
            for cost in cost_by_token[token]:
                if mig.get("squad") != cost.get("squad"):
                    pairs.append((mig, cost))
    return pairs
