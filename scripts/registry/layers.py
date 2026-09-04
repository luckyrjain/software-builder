"""Which optional contract/generation layers are active for one repository root.

This is the registry's config-resolution seam. It lives apart from `cli.py` so the
generator and validator modules can ask "is this layer active here?" without
importing the command-line entrypoint; `cli.py` re-exports the names it used to own
so existing callers keep their import path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scripts.registry.canonical_manifest import contract_document_path, contract_section_source
from scripts.registry.host_adapter import host_contracts_path


def capability_catalog_path(root: Path) -> Path:
    return root / "scripts" / "registry" / "capability_catalog.yaml"


def capability_families_path(root: Path) -> Path:
    return root / "scripts" / "registry" / "capability_families.yaml"


def release_contract_path(root: Path) -> Path:
    return root / "scripts" / "release_contract.yaml"


def p1_layer_paths(root: Path) -> list[Path]:
    return [
        host_contracts_path(root),
        root / "scripts" / "registry" / "eval_contracts.yaml",
        root / "docs" / "skill-framework" / "shared" / "runtime-contract.md",
        root / "docs" / "skill-framework" / "shared" / "host-adapter-contract.md",
        root / "docs" / "skill-framework" / "shared" / "eval-contract.md",
    ]


@dataclass(frozen=True)
class OptionalLayers:
    """Which optional contract/generation layers are active for one repository root.

    `scripts/registry/cli.py`'s generate and validate flows both need the same answer
    to "is capability_catalog / composition_runtime / release_contract / the P1 layer
    active here" -- before this existed, each of the generate collector,
    `_validate_for_generate`, and `_validate_all` answered it separately via ad hoc
    `Path.is_file()` checks and inline path literals, duplicated up to three times per
    layer. That drift already produced one dead helper (a prior `_platform_contracts_path`
    was defined and never called by anything -- removed). This dataclass is the one
    place that answers the question, composed from the individual path-construction
    helpers above (kept standalone: they're pure path arithmetic, independently useful
    and independently tested); every consumer reads a field here instead of
    re-deriving it.

    A `None` field means that layer is inactive for this root (an optional file it
    depends on doesn't exist); a `Path` means it's active, at that path.

    Not memoized like schema.py's `load_registry_raw` cache -- `detect_optional_layers`
    recomputes on every call (a handful of cheap `Path.is_file()` checks). It's named
    "detect", not "resolve", specifically to avoid implying it shares that cache's
    "computed once, invalidated via clear_registry_cache()" contract; it doesn't, and
    doesn't need to for its own fields. Its one indirect dependency on the cache is
    `canonical_manifest.contract_section_source`, which reads skills.yaml's shape via the
    cached `load_registry_raw` rather than a raw read of its own.
    """

    host_contracts: Path | None
    capability_catalog: Path | None
    capability_families: Path | None
    composition_runtime: Path | None
    release_contract: Path | None
    # Where the `composition` contract section is read from -- skills.yaml under the
    # canonical shape, otherwise the standalone projection. Named for the section, not for
    # skills.yaml's mere existence, which is what the field used to detect.
    composition_contracts: Path | None
    p1_layer_active: bool


# The layer -> label pairs `cmd_validate` reports on, in the order it names them. Paired with
# `OptionalLayers`' own fields, so a layer cannot be added without deciding how a run that
# skipped it is reported.
LAYER_LABELS: tuple[tuple[str, str], ...] = (
    ("host_contracts", "host adapter contract"),
    ("capability_catalog", "capability catalogue"),
    ("capability_families", "capability families"),
    ("composition_runtime", "composition runtime"),
    ("composition_contracts", "composition contracts"),
    ("release_contract", "release contract"),
)


def detect_optional_layers(root: Path) -> OptionalLayers:
    def active(path: Path) -> Path | None:
        return path if path.is_file() else None

    return OptionalLayers(
        host_contracts=active(host_contracts_path(root)),
        capability_catalog=active(capability_catalog_path(root)),
        capability_families=active(capability_families_path(root)),
        composition_runtime=contract_section_source(root, "composition_runtime"),
        release_contract=active(release_contract_path(root)),
        composition_contracts=active(contract_document_path(root, "composition")),
        p1_layer_active=any(path.is_file() for path in p1_layer_paths(root)),
    )


def optional_layer_paths(root: Path) -> list[Path]:
    """Every file an optional validation layer keys off of, for this root.

    `detect_optional_layers` gates each layer behind `Path.is_file()`, which is what lets
    the deliberately minimal registry fixtures skip layers they do not carry. That same
    leniency means a deleted file silently disables its layer in the real repository, so
    `scripts/check_platform_files.py` hard-asserts these paths exist there. Deriving that
    inventory from this list -- rather than restating it -- is what keeps the two in step.
    """
    return [
        capability_catalog_path(root),
        capability_families_path(root),
        release_contract_path(root),
        *p1_layer_paths(root),
    ]
