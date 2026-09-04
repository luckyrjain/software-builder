# ADR 0005: Registry authoring model — fragments, profiles, and optional layers

**Status:** Accepted
**Date:** 2026-09-04

## Context

[ADR 0001](0001-skills-registry.md) made root `skills.yaml` the canonical manifest and left it
hand-authored. At 38 skills that file reached ~4,400 lines with every skill's ~50-line entry under one
`skills:` mapping, so every skill-adding change touched the same mapping and conflicted with every
other one. Two further pressures accumulated with no record of their own:

- Most review skills carry an identical block of platform metadata (`authority`, `entrypoint`, host
  discovery, invocation mode, risk class, supported hosts), repeated per skill.
- Not every checkout that the registry tooling runs against has every contract layer. Test fixtures and
  reduced roots may have no `host_contracts.yaml`, no capability catalog, no composition runtime, and no
  P1 layer, so both the generate flow and the validate flow needed the same answer to "which layers
  exist here" — and each answered it separately with inline `Path.is_file()` checks.

These three mechanisms shipped without an ADR, so `CONTRIBUTING.md` was the only place any of them was
described, and `extends:` was documented in no markdown file at all.

## Decision

**1. Skill entries are authored one per file under `scripts/registry/skills.d/`.**

A skill's registry entry lives at `scripts/registry/skills.d/<skill-id>.yaml`, containing only that
skill's own entry keyed by its skill id. `scripts/registry/manifest_merge.py` merges every fragment into
`skills.yaml`'s `skills:` mapping, and `scripts/registry/cli.py`'s `_collect_outputs` emits the merged
file as a generated output of `make generate` — the same pattern `generate_cursor.py` and
`generate_kiro.py` already used for per-host adapters. `make generate-check` fails when the mapping
drifts from what the fragments produce, which is also what catches a hand-edit of the mapping.

Everything else in `skills.yaml` stays hand-authored in that file: `schema_version`, `manifest_kind`,
`contracts:`, and `profiles:`. A root with no `scripts/registry/skills.d/` directory is untouched — its
`skills:` mapping remains the hand-edited source of truth — so fixtures and older checkouts keep working.

**2. Shared platform metadata is factored into named profiles inherited with `extends:`.**

`skills.yaml`'s top-level `profiles:` mapping holds named blocks of registry fields. A skill entry
naming one with `extends: <profile-name>` inherits that block. `resolve_registry_profiles`
(`scripts/registry/schema.py`) resolves inheritance at load time:

- The profile is the base and the skill's own keys are the override, deep-merged by `_deep_merge` —
  nested mappings merge key by key, and any non-mapping value (including a list) replaces the base
  value outright rather than concatenating with it.
- `extends` itself is stripped from the merged entry, and the whole `profiles:` key is stripped from
  the resolved document.
- An `extends:` naming a profile that does not exist is a hard `ValueError`, not a silent skip.

The contract is that **no consumer ever sees `extends` or `profiles`**. Every reader of the registry —
whether it goes through `parse_registry` or reads the raw mapping — sees the same fully-inlined shape
the registry had before profiles existed. The one deliberate exception is
`scripts/registry/backfill_capabilities.py`, which is a *writer*: its round-trip must preserve the
unresolved `extends:` form on disk. Today one profile (`read-only-leaf-review`) is inherited by 15
skills.

**3. `OptionalLayers` is the single answer to "which contract layers are active in this root".**

`scripts/registry/cli.py` defines a frozen `OptionalLayers` dataclass and a `detect_optional_layers(root)`
function. Each field is `None` when that layer is inactive for the root and a `Path` when it is active
at that path (`p1_layer_active` is a plain bool). The generate flow, the per-generate validation flow,
and the full validation flow all read fields off one `OptionalLayers` value instead of re-deriving the
answer from inline path literals — the duplication that previously left a dead
`_platform_contracts_path` helper behind.

`detect_optional_layers` is deliberately named "detect", not "resolve", and is deliberately not
memoized: it recomputes a handful of `Path.is_file()` checks per call and does not share
`load_registry_raw`'s "computed once, invalidated via `clear_registry_cache()`" contract.

## Consequences

- **Positive:** Adding a skill touches one new file instead of a shared 4,400-line mapping; two
  skill-adding branches no longer conflict in the registry.
- **Positive:** Shared platform metadata is stated once. The `read-only-leaf-review` profile collapsed
  seven byte-identical fields repeated across 15 skills into one block.
- **Positive:** "Is this layer active here?" has one implementation, so a new layer is added in one place.
- **Negative:** `skills.yaml` is now partly generated and partly hand-authored, and the file itself does
  not say which parts are which. Until the merged output carries a banner, a reader must consult
  `CONTRIBUTING.md` or this ADR to know that the `skills:` mapping is not an authoring surface.
- **Negative:** A fragment no longer shows a skill's complete effective registry entry when it uses
  `extends:`; the effective entry is the profile deep-merged with the fragment. Read the profile too, or
  read the merged `skills.yaml`.
- **Follow-ups:** Emit a `GENERATED — do not edit the skills: mapping` banner from
  `manifest_merge.py` so `skills.yaml` states its own authoring rule, keeping it inside the generated
  region so `make generate-check` stays idempotent.
