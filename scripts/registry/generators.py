"""The declared interface every `make generate` output is produced through.

`cli.py`'s `_collect_outputs` used to hand-wire a dozen renderers, each with its own
argument list and each with its output path written as a literal at the call site. Three
of them (`generate_cursor_rules`, `generate_kiro_steering`, `generate_makefile_roster`)
already agreed on `(root, registry, ...) -> dict[Path, str]`; this module declares that
shape as `Generator` and gives every remaining `-> str` renderer a small adapter that
names its own output path next to the code that renders it.

The result is that "what does `make generate` write?" is answered by reading
`GENERATORS`, and adding a generated artifact appends to that list instead of editing
the package's most-churned function.

Each generator receives a `GenerateContext` and returns the paths it owns. A generator
that this repository root does not opt into returns an empty mapping rather than raising
-- the `Path.is_file()` and `OptionalLayers` gates that decide this are all resolved once,
into the context, before any generator runs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.registry.canonical_manifest import (
    LEGACY_PROJECTION_FILENAMES,
    has_canonical_manifest_shape,
    legacy_projection_path,
    render_legacy_projection,
)
from scripts.registry.composition import render_composition_mermaid
from scripts.registry.composition_runtime import render_dependency_graph
from scripts.registry.generate_agent_compatibility import (
    load_host_registry_and_registry,
    render_agent_compatibility_doc,
    update_readme_agent_compatibility_section,
)
from scripts.registry.generate_compatibility import render_compatibility_matrix
from scripts.registry.generate_cursor import generate_cursor_rules
from scripts.registry.generate_degraded_behavior_doc import (
    doc_path as degraded_behavior_doc_path,
)
from scripts.registry.generate_degraded_behavior_doc import render_degraded_behavior_doc
from scripts.registry.generate_docs import (
    render_install_mermaid,
    update_changelog_toc,
    update_readme_badge,
    update_readme_doc_links,
    update_readme_routing_table,
    update_repository_table,
)
from scripts.registry.generate_issue_templates import generate_issue_templates, issue_template_dir
from scripts.registry.generate_kiro import generate_kiro_steering
from scripts.registry.generate_makefile_roster import generate_makefile_roster
from scripts.registry.generate_shared_runtime_bootstrap import (
    generate_shared_runtime_bootstrap,
)
from scripts.registry.host_registry import HostRegistry
from scripts.registry.layers import OptionalLayers, detect_optional_layers
from scripts.registry.load import load_deprecated_skills, load_descriptions, load_registry
from scripts.registry.manifest_merge import (
    SIDE_FILE_PROJECTIONS,
    merge_registry_yaml,
    render_side_file,
    side_file_path,
    skills_fragments_dir,
)
from scripts.registry.models import Registry
from scripts.registry.schema import load_registry_raw


@dataclass(frozen=True)
class GenerateContext:
    """Everything the generators read, resolved once per `make generate`.

    Loading the registry, the per-skill descriptions and the deprecation map is the
    expensive part of a generate; resolving it here means a generator is a pure
    function of this value rather than of the filesystem, and adding a generator
    costs no additional load.

    `host_registry`/`agent_registry` are `None` when the root carries no
    `agent-hosts.yaml`, the same optional-layer convention `layers` uses.
    """

    root: Path
    registry: Registry
    descriptions: dict[str, str]
    deprecated: dict[str, dict[str, Any]]
    layers: OptionalLayers
    host_registry: HostRegistry | None
    agent_registry: Registry | None


Generator = Callable[[GenerateContext], dict[Path, str]]


def build_generate_context(root: Path) -> GenerateContext:
    registry = load_registry(root)
    host_registry: HostRegistry | None = None
    agent_registry: Registry | None = None
    if (root / "agent-hosts.yaml").is_file():
        host_registry, agent_registry = load_host_registry_and_registry(root)
    return GenerateContext(
        root=root,
        registry=registry,
        descriptions=load_descriptions(root, registry),
        deprecated=load_deprecated_skills(root, registry),
        layers=detect_optional_layers(root),
        host_registry=host_registry,
        agent_registry=agent_registry,
    )


def _generate_merged_registry(ctx: GenerateContext) -> dict[Path, str]:
    """skills.yaml and the three aggregate side-files, from the skills.d/ fragments.

    skills.yaml's `skills:` mapping is authored one-per-file under
    scripts/registry/skills.d/ (see manifest_merge.py); it is regenerated here the same
    way generate_cursor_rules/generate_kiro_steering regenerate their own per-host
    outputs from the canonical registry. Repos/fixtures without a skills.d/ directory
    keep skills.yaml's own `skills:` mapping as the legacy, hand-edited source of truth
    untouched.

    The same fragments own the per-skill rows of the three aggregate side-files
    (degraded behavior, SETUP.md freshness, routing rules); each is regenerated as a
    projection so its readers keep opening the same file with the same shape.
    """
    if not skills_fragments_dir(ctx.root).is_dir():
        return {}
    outputs: dict[Path, str] = {ctx.root / "skills.yaml": merge_registry_yaml(ctx.root)}
    for projection in SIDE_FILE_PROJECTIONS:
        path = side_file_path(ctx.root, projection)
        if path.is_file():
            outputs[path] = render_side_file(ctx.root, projection)
    return outputs


def _generate_cursor(ctx: GenerateContext) -> dict[Path, str]:
    return generate_cursor_rules(ctx.root, ctx.registry, ctx.descriptions, ctx.deprecated)


def _generate_kiro(ctx: GenerateContext) -> dict[Path, str]:
    return generate_kiro_steering(ctx.root, ctx.registry, ctx.deprecated)


def _generate_makefile_roster(ctx: GenerateContext) -> dict[Path, str]:
    return generate_makefile_roster(ctx.root, ctx.registry)


def _generate_shared_runtime_bootstrap(ctx: GenerateContext) -> dict[Path, str]:
    return generate_shared_runtime_bootstrap(ctx.root)


def _generate_issue_templates(ctx: GenerateContext) -> dict[Path, str]:
    if not issue_template_dir(ctx.root).is_dir():
        return {}
    return generate_issue_templates(ctx.root, ctx.registry)


def _generate_agent_compatibility_doc(ctx: GenerateContext) -> dict[Path, str]:
    if ctx.host_registry is None or ctx.agent_registry is None:
        return {}
    return {
        ctx.root / "docs" / "agent-compatibility.md": render_agent_compatibility_doc(
            ctx.host_registry, ctx.agent_registry
        )
    }


def _generate_readme(ctx: GenerateContext) -> dict[Path, str]:
    """README.md carries two generated blocks, so one generator owns the whole file.

    Splitting the badge and the agent-compatibility section into separate generators
    would have them race for the same output path, with the second silently discarding
    the first's edit.
    """
    readme = update_readme_badge(
        (ctx.root / "README.md").read_text(encoding="utf-8"),
        len(ctx.registry.skills),
    )
    if ctx.host_registry is not None:
        readme = update_readme_agent_compatibility_section(readme, ctx.host_registry)
    return {ctx.root / "README.md": readme}


def _generate_repository_doc(ctx: GenerateContext) -> dict[Path, str]:
    path = ctx.root / "docs" / "REPOSITORY.md"
    return {
        path: update_repository_table(
            path.read_text(encoding="utf-8"),
            ctx.registry,
            ctx.deprecated,
        )
    }


def _generate_changelog_toc(ctx: GenerateContext) -> dict[Path, str]:
    path = ctx.root / "CHANGELOG.md"
    if not path.is_file():
        return {}
    return {path: update_changelog_toc(path.read_text(encoding="utf-8"))}


def _generate_docs_readme(ctx: GenerateContext) -> dict[Path, str]:
    path = ctx.root / "docs" / "README.md"
    if not path.is_file():
        return {}
    docs_readme = update_readme_doc_links(
        path.read_text(encoding="utf-8"),
        ctx.registry,
        ctx.deprecated,
    )
    escalation_matrix_path = (
        ctx.root / "docs" / "skill-framework" / "shared" / "cross-skill-escalation.md"
    )
    if escalation_matrix_path.is_file():
        docs_readme = update_readme_routing_table(
            docs_readme,
            escalation_matrix_path.read_text(encoding="utf-8"),
            ctx.deprecated,
        )
    return {path: docs_readme}


def _generate_degraded_behavior_doc(ctx: GenerateContext) -> dict[Path, str]:
    """mcp-error-handling.md §4's normative table, projected from the same policy the
    eval scenario harness runs."""
    path = degraded_behavior_doc_path(ctx.root)
    if not path.is_file():
        return {}
    return {path: render_degraded_behavior_doc(ctx.root)}


def _generate_install_mermaid(ctx: GenerateContext) -> dict[Path, str]:
    path = ctx.root / "generated" / "catalogue" / "install-deps.mmd"
    return {path: render_install_mermaid(ctx.registry)}


def _generate_composition_mermaid(ctx: GenerateContext) -> dict[Path, str]:
    path = ctx.root / "generated" / "catalogue" / "composition-deps.mmd"
    return {path: render_composition_mermaid(ctx.registry)}


def _generate_compatibility_matrix(ctx: GenerateContext) -> dict[Path, str]:
    if ctx.layers.capability_catalog is None or ctx.layers.composition_contracts is None:
        return {}
    path = ctx.root / "generated" / "catalogue" / "compatibility-matrix.md"
    return {path: render_compatibility_matrix(ctx.root)}


def _generate_legacy_projections(ctx: GenerateContext) -> dict[Path, str]:
    """The standalone contract documents a canonical-shaped skills.yaml projects.

    Once a repository opts into the canonical shape it owns every contract section, so a
    malformed manifest must fail the generate rather than quietly leaving stale
    projections on disk. A repository that never opted in has no canonical source to
    project from, which is not an error.
    """
    if not has_canonical_manifest_shape(load_registry_raw(ctx.root / "skills.yaml")):
        return {}
    return {
        legacy_projection_path(ctx.root, section): render_legacy_projection(ctx.root, section)
        for section in LEGACY_PROJECTION_FILENAMES
    }


def _generate_composition_runtime_graph(ctx: GenerateContext) -> dict[Path, str]:
    if ctx.layers.composition_runtime is None or ctx.layers.composition_contracts is None:
        return {}
    path = ctx.root / "generated" / "catalogue" / "composition-runtime.mmd"
    return {
        path: render_dependency_graph(
            ctx.registry,
            runtime_path=ctx.layers.composition_runtime,
            contracts_path=ctx.layers.composition_contracts,
        )
    }


# Ordered because the outputs are written in this order and because two generators must
# not claim the same path. No generator reads another's output: every one of them reads
# the pre-generate working tree, and `cli.py` writes only after the whole list has run.
# The merged registry stays first regardless, so a reader meets skills.yaml -- the source
# every later generator projects from -- before its projections.
GENERATORS: tuple[Generator, ...] = (
    _generate_merged_registry,
    _generate_cursor,
    _generate_kiro,
    _generate_makefile_roster,
    _generate_shared_runtime_bootstrap,
    _generate_issue_templates,
    _generate_agent_compatibility_doc,
    _generate_readme,
    _generate_repository_doc,
    _generate_changelog_toc,
    _generate_docs_readme,
    _generate_degraded_behavior_doc,
    _generate_install_mermaid,
    _generate_composition_mermaid,
    _generate_compatibility_matrix,
    _generate_legacy_projections,
    _generate_composition_runtime_graph,
)


def collect_outputs(root: Path) -> dict[Path, str]:
    """Fold every registered generator into one path -> content mapping."""
    ctx = build_generate_context(root)
    outputs: dict[Path, str] = {}
    for generator in GENERATORS:
        outputs.update(generator(ctx))
    return outputs
