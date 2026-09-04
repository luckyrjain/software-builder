"""Cross-check cross-skill-escalation.md's matrix against the registry's escalation edges.

`composition.escalation_targets` in each skill's fragment and the "Symmetric matrix (forward
escalations)" table in docs/skill-framework/shared/cross-skill-escalation.md are two statements
of the same fact: which skill hands off to which. Nothing compared them, and they had drifted
apart in both directions -- 17 registry edges the doc never mentioned, and doc endpoints naming
skills that were never registered under that name.

This validator is the comparison, and it is deliberately asymmetric. The registry is the
machine-readable contract, so every edge it declares must be documented. The doc may say more:
it also carries one-off routes that no skill declares as a standing escalation target, and its
endpoints may name a group of skills or an external system -- but each such endpoint must be
allowlisted here by name, never silently tolerated, which is the same rule routing_sync.py
applies to skill-routing.md.
"""

from __future__ import annotations

import re
from pathlib import Path

from scripts.registry.cross_skill_routing import parse_forward_escalation_matrix
from scripts.registry.id_diff import report_id_coverage
from scripts.registry.models import Registry

ESCALATION_DOC_RELATIVE = Path("docs") / "skill-framework" / "shared" / "cross-skill-escalation.md"

# One From → To cell can name several destinations ("k8s + incident-rca"), so an endpoint is
# split before it is resolved.
_ENDPOINT_SEPARATORS = re.compile(r"\s+\+\s+|\s+/\s+")

# Shorthand the matrix has always used for a registered skill. Resolved rather than rewritten:
# the short name is what a reader of the table recognises, and "k8s" appears in the reverse
# escalation section and in several skills' own rows too.
ENDPOINT_ALIASES: dict[str, str] = {"k8s": "k8s-overprovisioning-datadog"}

# Endpoints that deliberately name something other than one registered skill. Each entry is a
# decision, not a backlog item: two external KubeSense surfaces, and the five test creators
# addressed as one group (the row applies to whichever of them produced the finding, so it is
# a group name rather than a slash-separated list of the five).
EXTERNAL_ENDPOINTS: frozenset[str] = frozenset(
    {
        "kubesense-alerts",
        "kubesense-dashboards",
        "unit/integration/contract/e2e/api-test-creator",
    }
)


def escalation_doc_path(root: Path) -> Path:
    return root / ESCALATION_DOC_RELATIVE


def _endpoint_ids(endpoint: str) -> list[str]:
    """The skill ids one From/To cell side names, in document order."""
    parts = _ENDPOINT_SEPARATORS.split(endpoint)
    resolved = []
    for part in parts:
        name = part.strip().strip("*").strip()
        if not name:
            continue
        resolved.append(ENDPOINT_ALIASES.get(name, name))
    return resolved


def documented_escalation_edges(markdown: str) -> set[tuple[str, str]]:
    """Every (from, to) pair the forward matrix documents, with multi-target rows expanded."""
    edges: set[tuple[str, str]] = set()
    for _trigger, source, target in parse_forward_escalation_matrix(markdown):
        for source_id in _endpoint_ids(source):
            for target_id in _endpoint_ids(target):
                edges.add((source_id, target_id))
    return edges


def registry_escalation_edges(registry: Registry) -> set[tuple[str, str]]:
    return {
        (skill_id, target)
        for skill_id, entry in registry.skills.items()
        for target in entry.composition.escalation_targets
    }


def validate_escalation_matrix(root: Path, registry: Registry) -> list[str]:
    path = escalation_doc_path(root)
    if not path.is_file():
        return []

    markdown = path.read_text(encoding="utf-8")
    documented = documented_escalation_edges(markdown)
    registered_ids = set(registry.skills)

    errors = report_id_coverage(
        {endpoint for edge in documented for endpoint in edge},
        registered_ids,
        dangling_label=(
            "error: cross-skill-escalation.md routes to unregistered skills (register them, add "
            "to escalation_sync.EXTERNAL_ENDPOINTS if intentionally external, or fix the name)"
        ),
        missing_label="error: cross-skill-escalation.md has no escalation row mentioning",
        exempt=EXTERNAL_ENDPOINTS,
    )

    undocumented = sorted(registry_escalation_edges(registry) - documented)
    if undocumented:
        errors.append(
            "error: cross-skill-escalation.md is missing registry escalation edges: "
            + ", ".join(f"{source} → {target}" for source, target in undocumented),
        )
    return errors
