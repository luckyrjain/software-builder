# Skills registry and canonical manifest

**Originally approved:** 2026-08-08
**Amended:** 2026-08-22
**Status:** Implemented; this document is normative for the manifest boundary.

## Problem

The repository has 23 portable skills and several generated or compatibility-facing contract
files. Maintaining versions, platform rules, artifact schemas, composition contracts, and host
metadata in separate authoring surfaces creates drift risk.

## Decision

Root `skills.yaml` is the single versioned canonical manifest:

```yaml
schema_version: 1
manifest_kind: canonical
contracts:
  platform: ...
  composition_runtime: ...
  composition: ...
skills:
  <skill-id>: ...
```

The manifest owns:

- normalized skill versions, types, categories, invocation modes, authorities, permissions, hosts,
  entrypoints, dependencies, and output contracts;
- platform contracts such as evidence, completion, result-envelope, artifact-runtime, freshness,
  handoff, recursion, state, permissions, and action-gate rules;
- composition runtime types, handoff routes, artifact ownership, artifact schemas, and field
  contracts.

`SKILL.md` remains the source for agent-facing instructions and discovery-facing frontmatter. In
the canonical repository its frontmatter contains `name`, `description`, and optional lifecycle
markers. `skill_version` and `platform_contract` are legacy platform fields and must not be added
back to canonical skill frontmatter. Workflow-file frontmatter remains responsible for workflow
phase metadata such as `workflow_version`, `produces`, and `consumes`.

## Generated projections

These files are generated views and must not be edited as independent sources:

- `scripts/registry/platform_contracts.yaml`
- `scripts/registry/composition_contracts.yaml`
- `scripts/registry/composition_runtime.yaml`
- `.cursor/rules/*.mdc`
- `.kiro/steering/*.md`
- generated catalogue and registry inventory documentation

Update `skills.yaml`, then run:

```bash
python3 -m scripts.registry validate
python3 -m scripts.registry generate
python3 -m scripts.registry generate --check
```

## Durable artifact contract

Durable skill results use one manifest-backed envelope. The top-level sections are:

| Section | Purpose |
|---|---|
| `skill_result` | Producer identity, exact registered version, status, confidence, artifact ids, schema version, and state semantic |
| `provenance` | Source revision and source references |
| `freshness` | Observation time, revision, and environment |
| `definition_of_done` | Required artifacts/checks, completed checks, blockers, and bounded partial behavior |
| `authority` | Write authority and canonical artifact owner |
| `payload` | Artifact-specific fields declared by the composition contract |

Validate a result with:

```bash
python3 -m scripts.registry validate-artifact <artifact_type> <result.json> --producer-skill <skill-id>
```

The producer argument is caller context. A trusted host must source it from its execution context;
the validator checks agreement with `skill_result.skill` but does not authenticate a CLI argument or
provide a signing/attestation service.

Artifact schema compatibility is controlled by the explicit artifact schema version. Skill
minor/patch versions remain readable within the same major version, subject to the artifact
contract.

## Validation boundary

Validation is fail-closed for canonical repositories. It checks:

1. canonical manifest shape and schema version;
2. skill coverage and projection equality;
3. frontmatter identity and removal of legacy platform markers;
4. composition ownership, producer/consumer field compatibility, and runtime routes;
5. platform and artifact-runtime contract completeness;
6. generated-output drift through `generate --check`.

Legacy loaders remain only for isolated compatibility fixtures. They do not change the canonical
authoring rule.

## Migration rule

Any future contract-shape change must increment the manifest schema version or introduce an
explicitly versioned nested contract, update validators and projections together, and document the
compatibility window. Do not reintroduce a second source of truth for a field already owned by the
canonical manifest.
