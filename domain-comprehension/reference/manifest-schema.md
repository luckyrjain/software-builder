# Manifest schema (`manifest.yaml`)

**Normative.** Machine-readable engagement state at workspace root. Domain-specific artifacts live under
`engagement.artifact_root`, defaulting to `docs/domain-comprehension/<domain-slug>/`. Humans and CI
validate with `scripts/validate_manifest_yaml.py`.

## Purpose

- deterministic artifact checklist and phase state
- scriptable completion gate
- resume locator without parsing prose
- evidence/completeness metrics

`manifest.yaml` is the source of truth for phase/artifact status; `PROGRESS.md` remains human-readable
inside the artifact root.

## Schema version

Current schema: `2`.

## Top-level fields

| Field | Required |
|-------|----------|
| `schema_version` | yes |
| `engagement` | yes |
| `phases` | yes |
| `artifacts` | yes |
| `diagrams` | yes |
| `five_questions` | yes |
| `overall_confidence` | yes |
| `repos` | yes |
| `runtime_validation` | yes |
| `evidence_summary` | yes |
| `section_confidences` | no |

## `engagement`

| Field | Contract |
|-------|----------|
| `domain_name` | domain slug |
| `workspace_root` | absolute workspace path |
| `artifact_root` | relative path, no `..`; default `docs/domain-comprehension/<domain_name>` |
| `map_file` | filename such as `DISBURSEMENT_MAP.md` |
| `status` | `IN_PROGRESS | FIRST_PASS_COMPLETE` |
| `last_updated` | ISO-8601 UTC |
| `last_phase_completed` | phase key |
| `next_action` | one-line string |
| `model_used` | string or null |

`manifest.yaml` itself stays at workspace root. The validator resolves domain artifacts under
`<workspace_root>/<artifact_root>/`. See [run-scoped-artifacts.md](run-scoped-artifacts.md).

## `phases`

Keys: `session_0`, `session_0b`, `p0`, `p0_25`, `p0_5`, `p1`, `p2`, `p2b`, `p3`, `p3b`, `p4`, `p5`.
Each has `status`, `completed_at`, and `skip_reason`; skipped phases require a reason and completed phases
require a completion timestamp.

## `artifacts[]`

Each row has `id`, `path`, `phase`, `required`, and `status` (`ok | stub | missing | waived | n_a`). Paths
are relative to `artifact_root`, except the root manifest itself which is not an artifact row.

Required P5 artifact `prd` (`PRD.md`) is the evidence-backed as-built/current-state requirements
synthesis. P5 marks it `ok` only after stable `FR-*`, `BR-*`, and `NFR-*` requirements and traceability
are populated. Unrecoverable product intent stays `Unknown`.

Optional outputs include `E2E_FLOW.md`, Memory Bank export, Postman export, and runtime dependency graph.

## `diagrams[]`

Diagram rows use the same relative-path resolution. Common ids include `logical_context`, `service_call`,
`deployment`, `runtime`, `business_flow`, `sequence_happy`, `sequence_failure`, and `state_machine`.

## `five_questions` / confidence

```yaml
five_questions:
  q1: { status: DRAFT, confidence: UNKNOWN }
overall_confidence: UNKNOWN
```

Question status: `DRAFT | PARTIAL | COMPLETE | UNKNOWN`. Confidence:
`HIGH | MEDIUM | LOW | UNKNOWN`.

## `repos[]`

Rows contain repo `name`, branch/SHA, tier, [classification](repo-classification.md), inventory status,
understand status, and deep-dive status.

## Agent update rules

1. Session 0 creates the docs artifact root, copies domain templates there, writes root `manifest.yaml`, and
   sets `engagement.artifact_root`.
2. End each phase by updating phases/artifacts/diagrams/evidence/confidence and running validation.
3. Skipped phases require a reason; optional artifacts become `n_a` or `waived` as appropriate.
4. `FIRST_PASS_COMPLETE` requires `--strict`; required P5 `prd` must be `ok`.
5. `ADD_REPO` keeps affected phases in progress while merge conflicts remain open.

## Validation

```bash
python3 domain-comprehension/scripts/validate_manifest_yaml.py manifest.yaml \
  --workspace-root /path/to/workspace --strict
```

An absolute `artifact_root` or one containing `..` is invalid.
