"""Discovery-precedence shadow detection for install.sh (Candidate 8 of
docs/superpowers/specs/2026-08-31-universal-agent-compatibility-design.md).

A host may discover the same skill from more than one root (spec Section 14); when it does, the
root with the *lowest* precedence number wins (agent-hosts.yaml's convention -- see e.g. cursor's
project binding at precedence 10 vs. its user binding at precedence 20). Writing a skill to a
lower-precedence root while a *different* copy already sits at a higher-precedence one means the
host will actually load that other copy, not the one just installed -- install.sh must not claim
success as if the new install is what will run (spec Section 35, this candidate's exit bar).

Scope: a written destination is checkable whenever some host in agent-hosts.yaml declares its
target as a discovery root -- scripts/registry/install_resolver.host_and_target_for_label() maps
the printed host label to that (host, target) pair rather than this module re-declaring the
mapping. The universal `agents` target is target-only (no host models it), so it has no discovery
precedence to be checked against and resolves to None there.

This warns rather than blocks: spec Section 35 does say a shadowed higher-precedence copy *may*
block, but a deliberate two-tier setup (an intentional project-level override on top of a
user-level default) is a normal, valid configuration, not a mistake to refuse. This candidate's
own exit bar is specifically about not *falsely claiming* activation -- so install.sh still writes
the file (that's a legitimate operation independent of what will end up executing) but replaces
its unconditional "Installed" success claim with an accurate one when a shadow is detected.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scripts.reference_utils import MANIFEST_NAME, ManifestError, read_manifest_file
from scripts.registry.compatibility_resolver import resolve_host
from scripts.registry.host_registry import HostRegistry, resolve_target_path

SHADOW_NONE = "NONE"
SHADOW_SHADOWED = "SHADOWED"
SHADOW_DUPLICATE_IDENTICAL = "DUPLICATE_IDENTICAL"
SHADOW_UNKNOWN_PRECEDENCE = "UNKNOWN_PRECEDENCE"


@dataclass(frozen=True)
class ShadowResult:
    status: str
    shadowing_path: Path | None = None


def detect_shadow(
    host_registry: HostRegistry,
    host_id: str,
    written_target_id: str,
    written_dest: Path,
    *,
    home: Path,
    target_dir: Path | None,
) -> ShadowResult:
    """Whether a higher-precedence discovery root for `host_id` also carries the skill just
    written to `written_dest`, and if so, whether its content matches (byte-for-byte, via each
    install's own recorded file hashes) what was just written.
    """
    host = resolve_host(host_registry, host_id)
    # Scoped to the one surface written_target_id actually belongs to, not flattened across every
    # surface the host has. host_registry.py only guarantees precedence numbers are unique *within
    # a surface* (each surface parses its own `seen_precedence` set); a host with more than one
    # surface kind (e.g. a future LOCAL + CLOUD split) could otherwise have two bindings on
    # different, non-comparable surfaces carry identical or interleaved precedence numbers with no
    # parse-time error, which this function would then wrongly treat as one global ordering.
    surface = next(
        (s for s in host.surfaces if any(b.target.id == written_target_id for b in s.discovery)),
        None,
    )
    if surface is None:
        return ShadowResult(SHADOW_NONE)
    bindings = surface.discovery
    written_precedence = next(
        (binding.precedence for binding in bindings if binding.target.id == written_target_id),
        None,
    )
    if written_precedence is None:
        return ShadowResult(SHADOW_NONE)

    try:
        written_manifest = read_manifest_file(written_dest / MANIFEST_NAME)
    except ManifestError:
        # written_dest is what install.sh itself just staged and moved into place -- a missing
        # or corrupt manifest here means something else is wrong, not a shadow question.
        return ShadowResult(SHADOW_NONE)

    higher = sorted(
        (binding for binding in bindings if binding.precedence < written_precedence),
        key=lambda binding: binding.precedence,
    )
    for binding in higher:
        shadow_root = resolve_target_path(binding.target, home=home, target_dir=target_dir)
        shadow_path = shadow_root / written_dest.name
        if shadow_path == written_dest or not shadow_path.is_dir():
            continue
        try:
            shadow_manifest = read_manifest_file(shadow_path / MANIFEST_NAME)
        except ManifestError:
            return ShadowResult(SHADOW_UNKNOWN_PRECEDENCE, shadow_path)
        if shadow_manifest.get("files") == written_manifest.get("files"):
            return ShadowResult(SHADOW_DUPLICATE_IDENTICAL, shadow_path)
        return ShadowResult(SHADOW_SHADOWED, shadow_path)
    return ShadowResult(SHADOW_NONE)
