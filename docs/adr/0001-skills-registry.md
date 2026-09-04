# ADR 0001: Canonical `skills.yaml` registry

**Status:** Accepted  
**Date:** 2026-08-08

## Context

Twenty-three portable skills lived in sibling directories with install edges scattered across the
`Makefile`, generated adapters duplicated routing prose, and no single place to answer “what skills
exist, how are they invoked, and what do they require?”

## Decision

- Add root `skills.yaml` as the **versioned canonical manifest** for skill entries and machine-checkable
  platform, artifact, and composition contracts. The manifest is identified by
  `manifest_kind: canonical` and `schema_version`.
- Keep agent-facing policy and workflow prose in each skill’s `SKILL.md`; its frontmatter owns
  discovery-facing identity and lifecycle markers, while the canonical manifest owns versions and
  platform metadata. `skill_version` and `platform_contract` are legacy frontmatter fields and are
  rejected for the canonical repository.
- Generate thin `.cursor/rules/*.mdc` and `.kiro/steering/*` adapters from the registry (`make generate`).
- Generate `scripts/registry/composition_contracts.yaml` and `composition_runtime.yaml` as
  projections; they are not independent authoring surfaces. (A third projection,
  `platform_contracts.yaml`, was generated alongside them until nothing outside `skills.yaml`
  was left reading it; the `contracts.platform` section is now read from `skills.yaml` only.)
- Gate merges with `make validate-registry` and `make generate --check`.

## Consequences

- **Positive:** One source of truth for versions, install allowlists, artifact schemas, composition
  validation, and generated discovery wrappers.
- **Positive:** Registry-driven installer can default to “install all registered skills” safely.
- **Negative:** Skill authors must update `skills.yaml` when install edges or invocation mode change; drift fails CI.
- **Follow-ups:** Keep generated projections synchronized and evolve the manifest with an explicit
  schema-version migration when the contract shape changes.

## Amended 2026-09-04

Three statements above have been overtaken by later changes. The decision itself stands — `skills.yaml`
is still the canonical manifest every validator, generator, and test reads — but its *authoring* model
changed and one gate command was never spelled correctly.

- **`skills.yaml`'s `skills:` mapping is now generated, not hand-authored.** Each skill's entry is
  authored one-per-file at `scripts/registry/skills.d/<skill-id>.yaml`, and
  `scripts/registry/manifest_merge.py` merges every fragment back into the `skills:` mapping during
  `make generate` (wired at `scripts/registry/cli.py`'s `_collect_outputs`). Hand-editing that mapping
  is a drift error, not an authoring step: the "Skill authors must update `skills.yaml`" consequence
  recorded above now means "authors must add or edit their fragment, then run `make generate`". A checkout with
  no `scripts/registry/skills.d/` directory keeps the original hand-edited mapping untouched, so
  fixtures and forks predating the split still validate.
- **The rest of `skills.yaml` is still hand-authored** — `schema_version`, `manifest_kind`,
  `contracts:`, and `profiles:`. Only the `skills:` mapping is a generated projection, so the list of
  projections above (`composition_contracts.yaml`, `composition_runtime.yaml`) is incomplete
  rather than wrong.
- **The merge gate is `make generate-check`**, not `make generate --check`. No such flag exists; the
  literal command in the Decision section fails. `make generate-check` is part of `lint-static` and
  fails when any generated output — including the merged `skills:` mapping — drifts from what its
  sources would produce.

The fragment authoring model, profile inheritance (`profiles:` / `extends:`), and the optional-layer
detection that decides which contract layers a checkout has are recorded in
[ADR 0005](0005-registry-authoring-model.md). The separate host/evidence registry (`agent-hosts.yaml`)
and its deliberate divergence from `scripts/registry/host_contracts.yaml` are recorded in
[ADR 0006](0006-host-registry-and-evidence-model.md).

`skills.yaml` still carries no "generated — do not edit" banner, so the file does not tell a reader its
own authoring rule; adding one to the merged output is tracked as follow-up work against
`manifest_merge.py`.
