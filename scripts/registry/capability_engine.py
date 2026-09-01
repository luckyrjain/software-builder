"""The single required/optional/any_of capability-resolution engine skills.yaml's capability
contracts are evaluated against.

Extracted from scripts/doctor.py (where it originated as a private helper) so
scripts/registry/compatibility_resolver.py (Candidate 4) can reuse it too without doctor.py and
compatibility_resolver.py importing each other -- doctor.py now imports compatibility_resolver.py
directly (Candidate 10, for host-aware --agent support), so the reverse import would be circular.
This is exactly the "reuse the existing capability engine, do not build a second one" instruction
in the spec's Section 11 -- there is now exactly one implementation, owned by neither of its two
callers.
"""

from __future__ import annotations

from scripts.registry.models import CapabilityPath


def capability_status(
    entry_required: list[str],
    entry_optional: list[str],
    entry_any_of: list[CapabilityPath],
    available: set[str] | None,
) -> tuple[list[str], list[str], str, CapabilityPath | None]:
    if available is None:
        return [], [], "UNSPECIFIED", None
    missing_required = [cap for cap in entry_required if cap not in available]
    if missing_required:
        return missing_required, [], "BLOCKED", None

    active_path: CapabilityPath | None = None
    if entry_any_of:
        complete_paths = [
            path for path in entry_any_of if all(cap in available for cap in path.required)
        ]
        if not complete_paths:
            closest_path = min(
                entry_any_of,
                key=lambda path: sum(cap not in available for cap in path.required),
            )
            missing_required = [cap for cap in closest_path.required if cap not in available]
            return missing_required, [], "BLOCKED", None
        active_path = min(
            complete_paths,
            key=lambda path: sum(item.name not in available for item in path.optional),
        )

    active_optional = list(entry_optional)
    if active_path is not None:
        active_optional.extend(item.name for item in active_path.optional)
    missing_optional = [cap for cap in active_optional if cap not in available]
    if missing_optional:
        return missing_required, missing_optional, "DEGRADED", active_path
    return missing_required, missing_optional, "READY", active_path
