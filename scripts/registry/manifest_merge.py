"""Merge per-skill authoring fragments into the generated root skills.yaml.

At 38 skills, skills.yaml is one ~4400-line hand-edited file: shared
contracts/schema at the top, then every skill's own ~50-line entry under a
single `skills:` mapping. Every skill-adding PR touches that same mapping,
which guarantees merge conflicts as the registry grows.

This module lets skills be authored one-per-file under
scripts/registry/skills.d/<skill-id>.yaml instead, and produces the merged
skills.yaml content -- mirroring the pattern generate_cursor.py/
generate_kiro.py already use for per-host adapters generated FROM the
canonical source. skills.yaml itself stays the single file every existing
consumer (validators, generators, tests, docs) reads unchanged; only its
`skills:` mapping and the per-skill sub-mappings of its `contracts:` section
become generated content, wired into cli.py's _collect_outputs/cmd_generate
the same way those adapters are.

Those contract sub-mappings -- `contracts.platform.skill_types`,
`contracts.platform.skill_permissions`,
`contracts.composition_runtime.skill_types` and `contracts.composition.skills`
-- used to restate, once per section, facts each skill already declares in its
own fragment. Four cross-section drift validators existed only to police that
restatement. Deriving them here removes both the restatement and the need to
police it: a fragment is the single place a skill's type, permissions, write
authority and produced/consumed artifacts are declared.

Repos/fixtures with no scripts/registry/skills.d/ directory are untouched:
callers should only invoke merge_registry_yaml() when that directory exists,
in which case skills.yaml's own `skills:` mapping is legacy/hand-edited and
authoritative as-is (see cli.py's _collect_outputs).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from scripts.yaml_safety import load_unique_yaml_file, require_mapping

FRAGMENTS_DIRNAME = "skills.d"


# Announces each generated block, the same way the generated Cursor/Kiro adapters and the
# standalone contract projections are marked. A banner is written immediately above its own
# section and stripped from that spot before the next render (see `replace_top_level_sections`),
# so regeneration is idempotent rather than stacking one banner per run.
def mapping_banner(key: str) -> str:
    return (
        f"# GENERATED from scripts/registry/{FRAGMENTS_DIRNAME}/*.yaml — do not edit the {key}: "
        "mapping; run make generate"
    )


SKILLS_BANNER = mapping_banner("skills")
CONTRACTS_BANNER = "\n".join(
    (
        "# GENERATED in part from scripts/registry/skills.d/*.yaml — run make generate.",
        "# Derived per skill, do not edit: platform.skill_types, platform.skill_permissions,",
        "# composition_runtime.skill_types, composition.skills. The rest of this section is",
        "# authored here, but the whole block is re-rendered, so it cannot carry comments.",
    )
)


def skills_fragments_dir(root: Path) -> Path:
    return root / "scripts" / "registry" / FRAGMENTS_DIRNAME


def load_fragment_skills(root: Path) -> dict[str, Any]:
    """Load and merge every scripts/registry/skills.d/*.yaml fragment.

    Each fragment must be a mapping with exactly one key: the skill id, whose
    value is that skill's own entry (the same shape it had inline under
    skills.yaml's `skills:` mapping, `extends:` profile references included --
    profile resolution happens later, against the merged document). The
    fragment's filename (minus `.yaml`) must match its skill id, so a
    misnamed or accidentally duplicated fragment fails loudly instead of
    silently mismatching or shadowing another skill.
    """
    fragments_dir = skills_fragments_dir(root)
    fragment_paths = sorted(fragments_dir.glob("*.yaml"))
    if not fragment_paths:
        raise ValueError(
            f"{fragments_dir}: exists but contains no *.yaml fragments -- refusing to "
            "merge an empty skill set (a bad rebase, partial checkout, or misconfigured "
            ".gitignore could produce this; if the fragments directory itself is meant "
            "to go away, remove it rather than leaving it present and empty)",
        )
    skills: dict[str, Any] = {}
    for fragment_path in fragment_paths:
        raw = require_mapping(load_unique_yaml_file(fragment_path), str(fragment_path))
        if len(raw) != 1:
            raise ValueError(
                f"{fragment_path}: fragment must contain exactly one skill entry, got {len(raw)}",
            )
        ((skill_id, entry),) = raw.items()
        if not isinstance(skill_id, str):
            raise ValueError(f"{fragment_path}: skill id must be a string")
        if skill_id != fragment_path.stem:
            raise ValueError(
                f"{fragment_path}: fragment key {skill_id!r} must match filename {fragment_path.stem!r}.yaml",
            )
        if skill_id in skills:
            raise ValueError(f"duplicate skill id across fragments: {skill_id!r}")
        skills[skill_id] = entry
    return skills


def _top_level_key_lines(text: str, label: str = "skills.yaml") -> list[tuple[str, int]]:
    """Every top-level key of a YAML document with the 0-indexed source line it begins on, in
    document order, found via yaml.compose (a parse pass with no object construction) rather
    than a text/regex search.

    A regex anchored on `^skills:` looks safe -- indented block scalars can't produce
    a false match -- but a *quoted* scalar's continuation lines are valid YAML at
    *any* indentation, including column 0: `description: "...text\\nskills:\\n  more
    text..."` folds into one string, yet still contains a line that is textually
    `skills:` at the start of a line. A regex can't tell that apart from the real
    key; the parser already does, via each node's own source position.
    """
    document = yaml.compose(text)
    if not isinstance(document, yaml.MappingNode):
        raise ValueError(f"{label}: root must be a mapping")
    return [(str(key_node.value), key_node.start_mark.line) for key_node, _ in document.value]


def _strip_trailing_banner(chunk: str, banner: str | None) -> str:
    """Drop the banner a previous run emitted at the end of a preserved chunk.

    A banner is written immediately above the section it announces, so it lands at the tail of
    the *preceding* top-level section's source lines. Only the exact text this run is about to
    re-emit there is removed, so a maintainer's own prose comment above a generated section --
    `degraded_behavior.yaml`'s policy note, for instance -- survives untouched.
    """
    if banner is None:
        return chunk
    suffix = banner + "\n"
    while chunk.endswith(suffix):
        chunk = chunk[: -len(suffix)]
    return chunk


def _skill_composition_contract(entry: dict[str, Any]) -> dict[str, Any]:
    """One skill's `contracts.composition.skills.<id>` entry, from that skill's own fragment.

    `produces`/`produce_fields` come from the skill's `output_contract`, `write_authority`
    from its `authority`, and the consumed half from its `composition` block -- the only
    facts here with no other home in the fragment. Empty field maps are omitted rather than
    written as `{}`, matching how the section was authored by hand. Missing blocks project as
    empty rather than raising: requiring them is `validate_canonical_manifest`'s job, and the
    minimal fixtures several tests build carry neither.
    """
    output_contract = require_mapping(entry.get("output_contract") or {}, "output_contract")
    composition = require_mapping(entry.get("composition") or {}, "composition")
    contract: dict[str, Any] = {
        "produces": list(output_contract.get("produces", [])),
        "consumes": list(composition.get("consumes", [])),
    }
    produce_fields = output_contract.get("produce_fields") or {}
    if produce_fields:
        contract["produce_fields"] = produce_fields
    consume_fields = composition.get("consume_fields") or {}
    if consume_fields:
        contract["consume_fields"] = consume_fields
    contract["write_authority"] = entry.get("authority")
    return contract


def derive_contract_sections(
    contracts: dict[str, Any],
    skills: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Return `contracts` with every per-skill sub-mapping re-derived from `skills`.

    `skills` must be profile-resolved, so a skill inheriting its `authority` or `type` from a
    `profiles:` entry projects the value it actually runs with.

    A section this registry does not carry is left alone rather than conjured: the minimal
    skills.yaml fixtures several tests build declare only part of `contracts:`, and whether a
    required section is missing is `validate_canonical_manifest`'s question, not this one's.
    """
    derived = copy.deepcopy(contracts)
    skill_types = {skill_id: entry.get("type") for skill_id, entry in skills.items()}
    sub_mappings: dict[str, dict[str, Any]] = {
        "platform": {
            "skill_types": skill_types,
            "skill_permissions": {
                skill_id: entry.get("permissions") for skill_id, entry in skills.items()
            },
        },
        "composition_runtime": {"skill_types": dict(skill_types)},
        "composition": {
            "skills": {
                skill_id: _skill_composition_contract(entry) for skill_id, entry in skills.items()
            },
        },
    }
    for section, fields in sub_mappings.items():
        if section not in derived:
            continue
        target = require_mapping(derived[section], f"contracts.{section}")
        for field, value in fields.items():
            target[field] = value
    return derived


def merge_registry_yaml(root: Path) -> str:
    """Render skills.yaml's full merged content.

    Rebuilds the file one top-level section at a time: `skills:` is the union of
    scripts/registry/skills.d/ fragments, `contracts:` is skills.yaml's own contract data with
    its per-skill sub-mappings re-derived from those fragments, and every other section
    (schema_version, manifest_kind, profiles, ...) is copied through byte-for-byte, comments
    included. Those sections stay hand-edited directly in skills.yaml; a full-document
    round-trip would silently drop any comment a maintainer adds there, since PyYAML's dumper
    has no comment-preservation. `contracts:` is the one hand-authored section that pays that
    price, because half of it is generated -- which its banner says out loud.

    Only call this when scripts/registry/skills.d/ exists; see module
    docstring for why an absent fragments directory is a distinct, legacy
    code path handled by the caller instead of here.
    """
    # Deferred: schema.py imports this module at import time, so the dependency can only run
    # the other way at call time. `resolve_registry_profiles` is the one seam that knows how an
    # `extends:` profile merges into a skill entry, and re-deriving the contract sub-mappings
    # needs the same resolved view every other consumer sees.
    from scripts.registry.schema import resolve_registry_profiles

    manifest_path = root / "skills.yaml"
    original = manifest_path.read_text(encoding="utf-8")
    if not any(key == "skills" for key, _ in _top_level_key_lines(original)):
        raise ValueError("skills.yaml: expected a top-level 'skills:' key to splice fragments into")

    document = require_mapping(load_unique_yaml_file(manifest_path), str(manifest_path))
    skills = load_fragment_skills(root)
    resolved = require_mapping(
        resolve_registry_profiles({"profiles": document.get("profiles"), "skills": skills}),
        "resolved skills",
    )["skills"]

    generated: dict[str, tuple[str, Any]] = {"skills": (SKILLS_BANNER, skills)}
    if "contracts" in document:
        generated["contracts"] = (
            CONTRACTS_BANNER,
            derive_contract_sections(document["contracts"], resolved),
        )
    return replace_top_level_sections(original, generated)


def replace_top_level_sections(
    original: str,
    generated: dict[str, tuple[str, Any]],
    *,
    label: str = "skills.yaml",
) -> str:
    """Re-render the named top-level sections of a YAML document, copying the rest verbatim.

    `generated` maps a top-level key to the banner announcing it and the value to render under
    it. Every other section -- and everything before the first key -- is copied through
    byte-for-byte, comments included, which is the whole point: PyYAML's dumper has no
    comment-preservation, so a full-document round-trip would silently drop a maintainer's
    comment from a section nothing generates.
    """
    lines = original.splitlines(keepends=True)
    key_lines = _top_level_key_lines(original, label)
    keys = [key for key, _ in key_lines]
    bounds = [line for _, line in key_lines] + [len(lines)]

    def banner_above(index: int) -> str | None:
        """The banner section `index` is preceded by, if that section is generated."""
        if index >= len(keys) or keys[index] not in generated:
            return None
        return generated[keys[index]][0]

    rendered = [_strip_trailing_banner("".join(lines[: bounds[0]]), banner_above(0))]
    for index, (key, start) in enumerate(key_lines):
        if key in generated:
            banner, value = generated[key]
            rendered.append(
                banner
                + "\n"
                + yaml.safe_dump(
                    {key: value},
                    sort_keys=False,
                    default_flow_style=False,
                    allow_unicode=True,
                )
            )
        else:
            rendered.append(
                _strip_trailing_banner(
                    "".join(lines[start : bounds[index + 1]]),
                    banner_above(index + 1),
                )
            )
    return "".join(rendered)


@dataclass(frozen=True)
class SideFileProjection:
    """One aggregate side-file whose per-skill rows are authored in the fragments.

    `degraded_behavior.yaml`, `setup_freshness.yaml` and `routing_rules.yaml` each carried one
    hand-maintained row per skill, keyed by skill id, in a file no skill author would think to
    open -- three more places a new skill had to be registered, each with its own "every skill
    must appear exactly once" validator to catch the omission. The row now lives in that
    skill's own fragment under `fragment_key`, and the file becomes a projection: same path,
    same shape, so every existing reader (scripts/evals/scenario_harness.py,
    scripts/validate_setup_freshness.py, scripts/evals/dispatcher.py) is untouched.

    Only the `container_key` mapping is generated; the file's own header -- schema_version,
    `defaults:`, and the prose comments explaining the policy -- stays hand-edited there,
    because it is policy for the whole set rather than a per-skill fact.
    """

    filename: str
    fragment_key: str
    container_key: str


SIDE_FILE_PROJECTIONS: tuple[SideFileProjection, ...] = (
    SideFileProjection("degraded_behavior.yaml", "degraded_behavior", "skills"),
    SideFileProjection("setup_freshness.yaml", "setup_freshness", "skills"),
    SideFileProjection("routing_rules.yaml", "routing", "routes"),
)


def side_file_path(root: Path, projection: SideFileProjection) -> Path:
    return root / "scripts" / "registry" / projection.filename


def render_side_file(root: Path, projection: SideFileProjection) -> str:
    """Render one side-file with its per-skill mapping regenerated from the fragments."""
    path = side_file_path(root, projection)
    rows = {
        skill_id: entry[projection.fragment_key]
        for skill_id, entry in load_fragment_skills(root).items()
        if isinstance(entry, dict) and projection.fragment_key in entry
    }
    return replace_top_level_sections(
        path.read_text(encoding="utf-8"),
        {projection.container_key: (mapping_banner(projection.container_key), rows)},
        label=projection.filename,
    )
