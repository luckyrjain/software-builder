"""Discovery-precedence shadow detection for install.sh (Candidate 8 of
docs/superpowers/specs/2026-08-31-universal-agent-compatibility-design.md).

A host may discover the same skill from more than one root (spec Section 14); when it does, the
root with the *lowest* precedence number wins (agent-hosts.yaml's convention -- see e.g. cursor's
project binding at precedence 10 vs. its user binding at precedence 20). Writing a skill to a
lower-precedence root while a *different* copy already sits at a higher-precedence one means the
host will actually load that other copy, not the one just installed -- install.sh must not claim
success as if the new install is what will run (spec Section 35, this candidate's exit bar).

Scope: only the four legacy single-target selectors (cursor, cursor-project, claude-user,
claude-project) are checked -- the universal `agents` target (Candidate 7) has no corresponding
host entry in agent-hosts.yaml (it's target-only, not host-modeled), so there is no discovery
precedence to check it against yet; `all` installs both cursor and claude destinations, each
individually checkable the same way as their single-selector counterparts, but is not wired in
this candidate to keep scope bounded to what install.sh's actual call site needs today.

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

# host_label (as install.sh's resolver already prints it) -> (host id, target id) -- only the
# four legacy single-target selectors have both a host entry and a fixed target id to check.
HOST_LABEL_TO_HOST_AND_TARGET: dict[str, tuple[str, str]] = {
    "cursor": ("cursor", "cursor-user"),
    "cursor-project": ("cursor", "cursor-project"),
    "claude-user": ("claude", "claude-user"),
    "claude-project": ("claude", "claude-project"),
}


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
    bindings = [binding for surface in host.surfaces for binding in surface.discovery]
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
