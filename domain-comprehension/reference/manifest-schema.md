# Manifest schema (`manifest.yaml`)

**Normative.** Machine-readable engagement state at workspace root. Agents **must** update after every
phase. Humans and CI validate with `scripts/validate_manifest_yaml.py`.

## Purpose

- Same artifact checklist for every agent run ([phase-outputs.md](phase-outputs.md))
- Scriptable completion gate ([phase-completion-gate.md](phase-completion-gate.md))
- Resume without re-parsing `PROGRESS.md` prose
- Evidence metrics for completeness ([evidence-summary.md](evidence-summary.md))

`PROGRESS.md` remains human-readable; `manifest.yaml` is the **source of truth** for phase/artifact status.

## Schema version

| Version | Notes |
|---------|-------|
| `2` | Current — repo classification enum, evidence_summary, overall_confidence, four graph diagrams |
| `1` | Deprecated — bump `schema_version` to `2` and copy [templates/manifest.yaml](../templates/manifest.yaml) fields |

## Top-level fields

| Field | Type | Required |
|-------|------|----------|
| `schema_version` | `2` | yes |
| `engagement` | object | yes |
| `phases` | object | yes |
| `artifacts` | array | yes |
| `diagrams` | array | yes |
| `five_questions` | object | yes |
| `overall_confidence` | band | yes |
| `repos` | array | yes (may be empty) |
| `runtime_validation` | object | yes |
| `evidence_summary` | object | yes |
| `section_confidences` | array | no |

## `engagement`

| Field | Values |
|-------|--------|
| `domain_name` | slug |
| `workspace_root` | absolute path |
| `map_file` | e.g. `DISBURSEMENT_MAP.md` |
| `status` | `IN_PROGRESS` \| `FIRST_PASS_COMPLETE` |
| `last_updated` | ISO-8601 UTC |
| `last_phase_completed` | phase key e.g. `p2`, `session_0b` |
| `next_action` | one-line string |
| `model_used` | string \| null — optional; model name if the agent can introspect it, else `null` |
| `artifact_root` | relative path, no `..` segments — optional; set when this run's deliverables are namespaced under a subdirectory of `workspace_root` instead of living directly at `workspace_root`. See [run-scoped-artifacts.md](run-scoped-artifacts.md). `manifest.yaml` itself always stays at `workspace_root` regardless. |

## `phases` keys

`session_0`, `session_0b`, `p0`, `p0_25`, `p0_5`, `p1`, `p2`, `p2b`, `p3`, `p3b`, `p4`, `p5`

Each value:

```yaml
status: pending | in_progress | complete | skipped
completed_at: <ISO or null>
skip_reason: <string or null>   # required when status=skipped
```

## `artifacts[]`

| Field | Values |
|-------|--------|
| `id` | stable slug |
| `path` | relative to workspace_root |
| `phase` | phase that must mark `ok` |
| `required` | boolean |
| `status` | `ok` \| `stub` \| `missing` \| `waived` \| `n_a` |

Required P5 artifact: `prd` (`PRD.md`) — as-built/current-state requirements synthesis. It begins as a
Session 0 stub because all `templates/` are copied at bootstrap, but its owning phase is `p5`; P5 must
mark it `ok` only after stable `FR-*`, `BR-*`, and `NFR-*` requirements and their evidence traceability
are populated. Product intent that implementation evidence cannot establish remains `Unknown` rather
than being fabricated.

New v2 artifacts: `known_omissions`, `business_flows`.

Optional artifacts: `e2e_flow` (`E2E_FLOW.md`, P2 supplement when map § Runtime validation is stub+link).

Optional artifacts: `memory_bank_export` — per Tier 0/1 repo at `<repo>/memory-bank/` when
`memory_bank.export_mode` is not `never` ([memory-bank-integration.md](memory-bank-integration.md)).
Manifest `path` is `memory-bank/` (convention); status `ok` when all export-target repos are populated.

Optional artifacts: `api_tooling_export` — `postman/` deliverable set when `api_tooling.export_mode` is not
`never` ([api-tooling-integration.md](api-tooling-integration.md)). Manifest `path` is `postman/`
(convention); status `ok` when all required files (collection, env files, generator config/script, README,
OTP script if applicable) are present and `postman/postman_collection.json` is valid JSON.

Optional diagrams: `datadog_service_deps` (`.understand-anything/diagrams/datadog-service-deps.md`, P2b).

## `diagrams[]`

v2 diagram ids: `logical_context`, `service_call`, `deployment`, `runtime`, `business_flow`, …

## `five_questions` / `overall_confidence`

```yaml
five_questions:
  q1: { status: DRAFT, confidence: UNKNOWN }
overall_confidence: UNKNOWN
```

## `repos[]`

| Field | Notes |
|-------|-------|
| `name` | repo folder |
| `branch`, `sha` | git HEAD |
| `tier` | 0–3 |
| `classification` | [repo-classification.md](repo-classification.md) enum |
| `inventory` | `pending` \| `complete` |
| `understand` | `pending` \| `ok` \| `failed` \| `skipped` |
| `deep_dive` | `pending` \| `complete` \| `skipped` |

## `evidence_summary`

See [evidence-summary.md](evidence-summary.md). All integer fields ≥ 0.

## Agent update rules

1. **Session 0** — copy [templates/manifest.yaml](../templates/manifest.yaml); set `engagement.*`, all artifacts `stub`
2. **End of phase** — phases, artifacts, diagrams, `evidence_summary`, `overall_confidence`; run validator
3. **Skip phase** — `skipped` + `skip_reason`; optional artifacts `n_a` or `waived`
4. **FIRST_PASS_COMPLETE** — validator `--strict`; `prd` must be `ok` because it is a required P5 artifact
5. **`ADD_REPO`** — add new `repos[]` entry at start; on merge conflict leave the owning phase at
   `status: in_progress` (do not mark `complete` while `RISK_MAP.md` § Merge Conflicts has an `open`
   row); run validator with `--check-content` same as end-of-phase

## Validation

```bash
python3 domain-comprehension/scripts/validate_manifest_yaml.py manifest.yaml
python3 domain-comprehension/scripts/validate_manifest_yaml.py manifest.yaml --workspace-root /path/to/workspace --strict
```

When `engagement.artifact_root` is set, `--workspace-root` still points at the directory holding
`manifest.yaml` — the validator resolves every other deliverable (`EXEC_SUMMARY.md`, `PRD.md`, the map
file, `E2E_FLOW.md`, `RISK_MAP.md`, the Postman export) under `<workspace_root>/<artifact_root>/` instead
of directly under `<workspace_root>/`. An absolute `artifact_root` or one containing `..` segments is a
validation error.
