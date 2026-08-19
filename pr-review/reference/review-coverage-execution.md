# Review coverage execution

This reference operationalizes `review-coverage-contract.yaml` without duplicating the detailed detectors in
`review-checklist.md`. It is mandatory in Phase 1 and Phase 2 for every non-listing review.

## Phase 1 — build identity and inspection plan

After the review boundary, provider SHAs, changed-file reads, capability profile, CI context, and Jira ACs are
available:

1. Build `change_identity` using the shared `../../docs/skill-framework/shared/change-identity.yaml` contract.
   - `base_sha`, `head_sha`, and `merge_base_sha` come from the normalized provider state.
   - `changed_paths` is the canonical sorted changed-path list from the review boundary.
   - `generated_paths` contains only generated files that are also in `changed_paths`.
   - `dependency_changes` captures manifest/lockfile dependency deltas in canonical object order.
   - `config_changes` captures runtime config and IaC/config surface deltas in canonical object order.
   - `normalized_diff_fingerprint` is computed from the canonical effective patch, including generated-file
     content and excluding transport-only metadata.
   Validate the identity before Phase 2; invalid identity is a blocker, never a warning.

2. Build `inspection_plan` from `review-coverage-contract.yaml`. For each surface, record
   `{triggered, reason, mandatory, evidence_sources, status}` where status starts `pending` when triggered and
   `not_applicable` otherwise.

3. Trigger the six surfaces deterministically:
   - **cross-file impact** — production code, shared module, public export, API/event/schema, or configuration
     behavior changes. Include changed-file interactions and direct callers/callees already discoverable under
     the review boundary/one-hop policy.
   - **hidden consumers** — shared libraries, public APIs, routes, event/schema contracts, config keys, feature
     flags, or serialized data change. Search the permitted repository context/import graph/CODEOWNERS/contract
     registry for consumers. If repository search or consumer registry is unavailable, record
     `unable_to_inspect`; do not infer that there are no consumers.
   - **schema/migration compatibility** — DB migration/schema, API/event/schema, serialization, config schema,
     or persisted-data contract changes. Inspect rolling-deploy compatibility, old/new code coexistence,
     backfill/data state, and forward/backward compatibility.
   - **rollout/rollback** — production behavior, deployment, migration, feature flag, dependency, or IaC change.
     Inspect rollout ordering, success/abort signals, rollback mechanism, and data/schema compatibility after
     rollback.
   - **test quality** — production logic, contract, migration, dependency behavior, or IaC behavior change.
     Inspect negative/error cases, regression proof, failure injection, integration/contract tests, and relevant
     performance/concurrency coverage rather than merely checking that tests exist.
   - **dependency/config/IaC** — manifest/lockfile, runtime config, CI/CD, Terraform, Helm, Kubernetes,
     Dockerfile, policy, or deployment surface change. Inspect compatibility, safe defaults, security/permissions,
     destructive changes, and deployment impact.

4. Every failed or unavailable evidence source becomes a machine `unable_to_inspect` candidate with
   `{surface, reason, mandatory}`. A mandatory surface is one whose trigger is material to a correctness,
   security, compatibility, or production-readiness claim for this change.

Phase 1 produces: `change_identity`, `inspection_plan`, and initial `unable_to_inspect` candidates.

## Phase 2 — complete surfaces and emit portable evidence

Before applying stop-search, complete every triggered **mandatory** inspection surface. Stop-search may suppress
new detector exploration, but it must not turn a pending mandatory surface into a clean result.

For each triggered surface:

- `complete` — evidence was inspected; record evidence paths/sources and candidate/finding IDs produced.
- `unable` — evidence could not be inspected; append `{surface, reason, mandatory}` to
  `review_evidence.unable_to_inspect`.
- Never use `not_applicable` for a triggered surface.

Run the existing finding pipeline for defect judgment/severity. Then map outputs into the shared evidence
taxonomy:

- `defect` — emitted PRR finding that proves a correctness, security, compatibility, operational, AC, or other
  actionable defect. Preserve the existing `PRR-{CAT}-{NNN}` ID/category as the defect's stable ID/subclass.
- `suggestion` — engineering improvement with no proven defect. Suggestions do not enter the severity gate.
- `question` — unresolved information request or unverifiable uncertainty. Questions remain non-blocking until
  new evidence promotes them to a defect.

Build `review_evidence` per `../../docs/skill-framework/shared/review-evidence.yaml`:

- `change_identity`: exact validated Phase 1 identity.
- `requirements_ref`: normalized Jira/MR requirements reference, or `null` when none exists.
- `review_mode`: `normal` or `exhaustive` as required by the shared envelope; retrospective/incremental lifecycle
  remains review metadata outside this v1 field.
- `inspection_status`:
  - `complete` only when all triggered surfaces are complete/not-applicable as appropriate and no mandatory
    `unable_to_inspect` exists;
  - `partial` when some triggered surface is unavailable but useful review evidence exists;
  - `unable` when the primary review boundary or another mandatory primary surface cannot be inspected enough
    to perform a meaningful review.
- `inspected_surfaces`: stable names of completed triggered surfaces.
- `unable_to_inspect`: all unavailable surface records; never silently drop one at rendering/posting time.
- `findings`: exactly `defect`, `suggestion`, and `question` buckets.
- `generated_at`: generation timestamp.

Validate the envelope against the current change identity and requirements surface before the Phase 2→3 gate.
A stale/invalid envelope blocks posting and caps the review as partial/unable rather than allowing an Approve-like
recommendation.

## Cross-file and hidden-consumer evidence rules

One-hop contextual reads remain bounded by `workflow/phase-1.md`; this contract does not authorize arbitrary
transitive browsing. However, when hidden-consumer inspection is triggered and the provider exposes repository
search/import graph/contract registry as an approved read capability, use that capability specifically to identify
consumer paths. Record the searched source in `inspection_plan.evidence_sources` and the discovered consumer paths
in the surface evidence. If the capability is unavailable, record `unable_to_inspect` instead of guessing.

A consumer outside the changed-line review boundary may support impact/compatibility reasoning but is not itself a
valid inline finding anchor. Findings still require a primary changed-line anchor under the existing finding
pipeline.
