# Skills registry and canonical manifest — as-built record

**Original plan date:** 2026-08-08
**Implementation status:** Complete and superseded by the canonical-manifest design amended on
2026-08-22.
**Normative reference:** [skills-registry-design.md](../specs/2026-08-08-skills-registry-design.md)

The original plan described a split registry/frontmatter ownership model. That model is retained
here only as historical context; it is not an implementation instruction. The repository now uses
one versioned canonical manifest in `skills.yaml`.

## Delivered behavior

- `skills.yaml` declares `manifest_kind: canonical`, `schema_version: 1`, all 23 skill entries,
  platform contracts, composition runtime contracts, and composition artifact contracts.
- Skill versions and platform metadata are canonical-manifest fields.
- Canonical skill frontmatter is limited to discovery-facing identity and lifecycle metadata;
  legacy `skill_version` and `platform_contract` fields are rejected for the canonical repository.
- Generated platform/composition YAML projections and host discovery files are checked for drift.
- Durable artifact results have a single envelope with provenance, freshness, definition-of-done,
  authority, state semantics, explicit artifact schema versions, and payload validation.
- Registry CLI commands validate the manifest, render projections, check drift, discover skills,
  explain skill entries, and validate durable artifact results.

## Key implementation files

| File | Responsibility |
|---|---|
| `skills.yaml` | Versioned canonical manifest and authoring source |
| `scripts/registry/canonical_manifest.py` | Canonical shape, schema, version, and projection checks |
| `scripts/registry/manifest.py` | Normalized manifest builder |
| `scripts/registry/artifact_contracts.py` | Durable artifact catalog and result validation |
| `scripts/registry/composition_contracts.py` | Composition contract loading and validation |
| `scripts/registry/runtime_manifest.py` | Integrated runtime manifest validation |
| `scripts/registry/p1_validation.py` | Shared platform-contract and frontmatter gates |
| `scripts/registry/cli.py` | Validation, generation, discovery, and artifact commands |
| `scripts/registry/platform_contracts.yaml` | Generated platform projection |
| `scripts/registry/composition_contracts.yaml` | Generated composition projection |
| `scripts/registry/composition_runtime.yaml` | Generated runtime projection |
| `docs/skill-framework/shared/runtime-contract.md` | Normative runtime envelope and action rules |

## Required verification

Run from the repository root:

```bash
python3 -m scripts.registry validate
python3 -m scripts.registry generate --check
python3 -m compileall -q scripts
python3 -m pytest scripts/tests/test_canonical_manifest.py scripts/tests/test_platform_manifest.py scripts/tests/test_p1_contracts.py scripts/tests/test_artifact_contracts.py
```

`make lint` remains the repository-wide gate. The exact CI result for the commit under review is
authoritative over any local run.

## Change rule

Edit `skills.yaml` first. Regenerate projections with `make generate`; never hand-edit generated
contract YAML or host adapter files. When changing the manifest schema, update the canonical loader,
validators, projections, tests, and this documentation in the same change.
