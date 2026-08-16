# Prompt module and artifact-schema deprecation

Deprecation is a compatibility change, not an editorial cleanup. A prompt module, machine-readable contract, artifact schema, route alias, or report field may be removed only after an explicit compatibility window and a validated migration path.

## Required metadata

Any YAML contract marked `status: deprecated` or `deprecated: true` must include a `deprecation` mapping with all of these fields:

- `deprecated_since` — ISO date when the deprecation became active.
- `replacement` — stable ID or path of the supported replacement; use `none` only when removal is intentional and consumers have no successor.
- `remove_after` — earliest ISO date on which removal is permitted.
- `migration_note` — concise consumer action required before removal.
- `aliases` — compatibility aliases retained during the window, even when the list is empty.

The default compatibility window is 90 days and is defined in `scripts/operational_upkeep.yaml`. CI validates deprecated registry YAML against the required metadata contract.

## Compatibility rules

1. Deprecation must not silently change an existing stable route, stop-condition, or report-field ID.
2. Existing aliases stay valid through `remove_after`.
3. A replacement schema must be available before the old schema is marked deprecated.
4. Generated reports and eval fixtures must identify the new schema/version before the old one is removed.
5. Removal is a schema or routing-risk change and therefore requires changed test/eval evidence under the prompt-diff risk policy.

## Removal checklist

Before removing a deprecated item, confirm that the compatibility window has elapsed, all repository references have migrated, no generated adapter or package still emits the deprecated identifier, relevant evals cover the replacement, and release notes identify the removal and migration path.
