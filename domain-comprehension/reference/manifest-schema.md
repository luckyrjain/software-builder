# Manifest schema (`manifest.yaml`)

**Normative.** Machine-readable engagement state at workspace root. Domain-specific artifacts live under
`engagement.artifact_root`, defaulting to `docs/domain-comprehension/<domain-slug>/`. Humans and CI
validate manifest/path/content state with `scripts/validate_manifest_yaml.py`; P5 additionally validates
`PRD.md` with `scripts/validate_prd.py`.

## Purpose

- deterministic artifact checklist and phase state
- scriptable completion gate
- resume locator without parsing prose
- persisted discovery-budget state for deterministic bounded discovery
- explicit machine-readable stale/current state for `PRD.md`
- evidence/completeness metrics
- a hard path boundary preventing manifest-controlled artifact lookup outside the workspace artifact root

`manifest.yaml` is the source of truth for phase/artifact/budget status; `PROGRESS.md` remains human-readable
inside the artifact root.

## Schema version

Current schema: `2`.

## Top-level fields

| Field | Required |
|-------|----------|
| `schema_version` | yes |
| `engagement` | yes |
| `discovery_budget` | no for legacy schema-v2 manifests; written by all new runs and backfilled before RESUME discovery |
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
| `artifact_root` | safe relative path; default `docs/domain-comprehension/<domain-slug>` |
| `map_file` | safe relative path such as `DISBURSEMENT_MAP.md` |
| `status` | `IN_PROGRESS | FIRST_PASS_COMPLETE` |
| `last_updated` | ISO-8601 UTC |
| `last_phase_completed` | phase key |
| `next_action` | one-line string |
| `model_used` | string or null |

`manifest.yaml` itself stays at workspace root. The validator resolves domain artifacts under
`<workspace_root>/<artifact_root>/`. `artifact_root` and `map_file` must be relative and may not contain
`..`; validation treats both `/` and `\\` as separators so Windows-style traversal cannot bypass Linux
CI. See [run-scoped-artifacts.md](run-scoped-artifacts.md).

## `discovery_budget`

New engagements persist the bounded-discovery profile and counters in machine state:

```yaml
discovery_budget:
  profile: QUICK
  limits: { repositories: 12, search_queries: 80, deep_file_reads: 60 }
  consumed: { repositories: 0, search_queries: 0, deep_file_reads: 0 }
```

`profile` is `QUICK | FULL | DELTA | ADD_REPO | CUSTOM`. Every configured limit is a positive integer; every
consumed counter is a non-negative integer and may not exceed its configured limit. The delivery-mode defaults
come from [domain-model-contract.yaml](domain-model-contract.yaml); Session 0 must replace the reusable
QUICK template values when another profile is selected.

The field remains optional to preserve RESUME compatibility with pre-Batch-5 schema-v2 manifests. Before a
legacy engagement performs new source discovery, RESUME must create the block from the active delivery profile
and any already-recorded counters that can be recovered without guessing. If prior consumption cannot be
recovered, record that limitation and choose a conservative remaining budget rather than silently resetting an
exhausted run. Mirror counters into `PROGRESS.md` for humans, but the manifest block is the machine source of
truth once present.

## `phases`

Keys: `session_0`, `session_0b`, `p0`, `p0_25`, `p0_5`, `p1`, `p2`, `p2b`, `p3`, `p3b`, `p4`, `p5`.
Each has `status`, `completed_at`, and `skip_reason`; skipped phases require a reason and completed phases
require a completion timestamp.

## `artifacts[]`

Each row has `id`, `path`, `phase`, `required`, and `status`
(`ok | stub | missing | stale | waived | n_a`). Paths are relative to `artifact_root`, except the root
manifest itself which is not an artifact row. Artifact and diagram paths must also be safe relative paths with
no `..`; absolute paths are invalid.

`stale` is valid **only** for artifact id `prd`. It means the file still exists but DELTA/ADD_REPO evidence
proved that it no longer represents current state. The validator therefore still checks that a stale PRD file
exists on disk, while strict `FIRST_PASS_COMPLETE` rejects the stale status because required artifacts must be
`ok`/`waived`. Other artifacts may not use `stale`.

Required P5 artifacts for a completed FULL engagement are:

| ID | Path | Contract |
|---|---|---|
| `prd` | `PRD.md` | evidence-backed as-built/current-state requirements + traceability |
| `api_event_schema` | `API_EVENT_SCHEMA.yaml` | machine API/event contracts + source revision/evidence/confidence |
| `data_ownership_graph` | `DATA_OWNERSHIP_GRAPH.yaml` | machine authoritative data ownership/access graph |
| `dependency_graph_machine` | `DEPENDENCY_GRAPH.yaml` | machine sync/async, upstream/downstream, criticality graph |
| `capability_traceability` | `CAPABILITY_TRACEABILITY.yaml` | capability → repositories/code locations/owner/evidence |

P5 marks `prd` `ok` only after stable `FR-*`, `BR-*`, and `NFR-*` requirements and traceability are
populated and the stale-PRD comparison says the document is current. DELTA/ADD_REPO sets the PRD row to
`stale` as soon as a configured stale condition fires, before any handoff can claim the document is current;
regeneration returns the row to `ok`. P5 marks the four machine artifacts `ok` only after the reconciliation
procedure in [machine-domain-model.md](machine-domain-model.md). Unrecoverable product intent or machine
evidence stays `Unknown`; it is never guessed to satisfy completion.

QUICK engagements may create the machine files as stubs without completing P5. Strict validation only
requires all `required: true` artifact rows to be `ok`/`waived` when `engagement.status` is
`FIRST_PASS_COMPLETE`. COMPLIANCE_RETROFIT may use `waived` where re-analysis would be required; the waiver
must be disclosed in the human handoff/omissions rather than fabricating machine evidence.

Optional outputs include `E2E_FLOW.md`, Memory Bank export, Postman export, and runtime-only diagram
supplements.

## `diagrams[]`

Diagram rows use the same relative-path resolution and path-boundary rules. Common ids include
`logical_context`, `service_call`, `deployment`, `runtime`, `business_flow`, `sequence_happy`,
`sequence_failure`, and `state_machine`.

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

1. Session 0 creates the docs artifact root, copies domain templates there, writes root `manifest.yaml`,
   writes the same resolved path to `domain-config.yaml scope.artifact_root`, sets
   `engagement.artifact_root`, and initializes `discovery_budget` from the selected profile.
2. End each discovery-bearing phase by updating `discovery_budget.consumed` in the manifest and mirroring it
   to `PROGRESS.md`; never reset counters between phases or RESUME.
3. DELTA/ADD_REPO sets `artifacts[id=prd].status: stale` immediately when stale-PRD detection fires; do not
   leave the row `ok` while only disclosing staleness in prose. Regeneration restores `ok`.
4. End each phase by updating phases/artifacts/diagrams/evidence/confidence and running validation.
5. Skipped phases require a reason; optional artifacts become `n_a` or `waived` as appropriate.
6. `FIRST_PASS_COMPLETE` requires manifest `--strict --check-content` plus `validate_prd.py`; all required
   P5 artifacts must be `ok`/`waived`, and the PRD must satisfy its requirement/traceability contract.
7. `ADD_REPO` keeps affected phases in progress while merge conflicts remain open and must refresh affected
   machine artifacts before P5 freshness claims.
8. RESUME/DELTA/ADD_REPO on a manifest whose `artifacts[]` predates the current template (missing an id the
   template defines, e.g. a machine domain-model artifact) backfill the missing row(s) as `stub`/`n_a` before
   relying on `--strict`/`--check-content` — see [inputs.md](../workflow/inputs.md) § Legacy manifest artifact
   rows. A required id absent from `artifacts[]` is invisible to `--strict`'s per-row check, so skipping the
   backfill silently defeats the required-P5-artifacts contract above.

## Validation

```bash
python3 domain-comprehension/scripts/validate_manifest_yaml.py manifest.yaml \
  --workspace-root /path/to/workspace --strict --check-content

python3 domain-comprehension/scripts/validate_prd.py \
  /path/to/workspace/<artifact_root>/PRD.md
```

The manifest validator validates `discovery_budget` whenever it is present, rejects malformed/negative or
over-limit counters, restricts `stale` to the PRD artifact, verifies a stale PRD still exists, and rejects
stale required artifacts under strict completion. The PRD validator requires `Status` and `Confidence` on
`FR-*`, `BR-*`, and `NFR-*` definitions, exactly one traceability row for every requirement id, and evidence
for every `Observed` requirement.
