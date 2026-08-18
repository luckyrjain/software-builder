# Batch 5.2 — Review Intelligence and Implementation Loop Hardening

**Status:** Design approved for Approach B; implementation not started
**Base:** `main` at `249b91378106fda7f6f7d9f9e0360fe3b82431d4`
**Backlog scope:** items 38 (`pr-review`) and 39 (`loop-task-implementer`)

## Goal

Make review evidence portable, machine-verifiable, and freshness-bound so `pr-review` can produce richer review intelligence and `loop-task-implementer` can safely consume review evidence during implementation loops without accepting stale or incomplete review state.

## Non-goals

- Do not implement Batch 5 items 40+.
- Do not redesign the shared runtime contract or authority model repo-wide.
- Do not expand `test-writer` into multi-level orchestration yet; only route to one relevant existing test creator.
- Do not change `pr-review` posting authority: it remains read + optional comment only, never approve/merge.
- Do not change `loop-task-implementer` authorization semantics for merge/deploy.

## Delivery strategy

Use three small PRs sharing one contract rather than one large cross-skill PR.

1. **5.2A — Shared change/review contracts**
2. **5.2B — `pr-review` intelligence hardening**
3. **5.2C — `loop-task-implementer` lifecycle hardening**

Each PR requires RED→GREEN behavioral tests, full CI, and two consecutive zero-finding reviews on the same SHA before merge.

## 5.2A — Shared contracts

### Change identity

Define one canonical change identity consumed by both skills:

```yaml
change_identity:
  schema_version: 1
  base_sha: string
  head_sha: string
  merge_base_sha: string
  normalized_diff_fingerprint: string
  changed_paths: [string]
  generated_paths: [string]
  dependency_changes: [object]
  config_changes: [object]
```

### Normalized diff fingerprint

The fingerprint must be deterministic for semantically identical patch content and must include generated-file changes. It should exclude transport-only metadata such as commit-message text and provider formatting.

A content-neutral base update may preserve review evidence only when the normalized patch fingerprint is unchanged and no conflict resolution occurred. Any effective patch change invalidates prior review evidence.

### Review evidence envelope

```yaml
review_evidence:
  schema_version: 1
  change_identity: object
  requirements_ref: object | null
  review_mode: normal | exhaustive
  inspection_status: complete | partial | unable
  inspected_surfaces: [string]
  unable_to_inspect: [object]
  findings:
    defect: [object]
    suggestion: [object]
    question: [object]
  generated_at: string
```

Rules:
- `complete` is illegal if any mandatory review surface is recorded as unable to inspect.
- `unable_to_inspect` must name the missing surface and why it could not be inspected.
- finding categories are disjoint; questions do not become blockers without evidence promoting them to defects.
- stale `change_identity` makes the entire envelope stale.

### 5.2A tests

RED tests must cover deterministic fingerprinting, fingerprint changes on generated files, malformed SHA/fingerprint values, stale merge-base/head combinations, invalid finding categories, and illegal `complete` inspection status with missing mandatory surfaces.

## 5.2B — `pr-review`

Preserve the current signal-over-noise model, ≤10 normal-mode cap, provider safety, diff-line evidence, and optional exhaustive mode.

### Cross-file impact graph

During review, build a machine-visible impact graph:

```text
changed file
  -> symbols/contracts/schemas
  -> callers/consumers
  -> config/deployment/migrations
  -> tests
```

Each edge is classified `observed`, `inferred`, or `unable_to_inspect` and carries evidence.

### Mandatory review dimensions

Every non-mechanical review evaluates:

- cross-file callers/callees/shared contracts;
- generated/schema migration behavior;
- compatibility and hidden consumers;
- rollout and rollback safety;
- test-change quality;
- dependency/version risk;
- config and feature-flag behavior;
- IaC/deployment impact;
- inspection coverage and unable-to-inspect surfaces.

Dimensions may evaluate to no finding; evaluation itself is mandatory.

### Finding taxonomy

Top-level findings are one of:

- `DEFECT` — evidence-backed correctness/safety/compatibility/operability issue;
- `SUGGESTION` — non-blocking improvement with concrete value;
- `QUESTION` — unresolved information request that is not a defect until evidence supports promotion.

Severity is meaningful for defects; suggestions/questions must not masquerade as blockers.

### Normal vs exhaustive

- `normal`: hard cap ≤10 top-level findings after root-cause grouping.
- `exhaustive`: no arbitrary top-level cap, but still root-cause grouped and style-noise filtered.

### `pr-review` behavioral tests

At minimum:

1. API change finds an untouched direct consumer.
2. schema migration without rollback becomes a defect.
3. affected generated client that cannot be inspected produces `unable_to_inspect`.
4. dependency bump with compatibility risk is analyzed.
5. feature-flag default change is analyzed.
6. Terraform/Kubernetes deployment impact is analyzed.
7. changed tests that weaken assertions are flagged.
8. question does not become defect without evidence.
9. normal mode caps at 10.
10. exhaustive mode can exceed 10.
11. changed fingerprint invalidates prior review evidence.
12. generated-file change invalidates prior review evidence.

## 5.2C — `loop-task-implementer`

Consume the shared change identity/review evidence instead of introducing a second fingerprint or freshness model.

### Task-plan artifact

Every task loop creates `TASK-PLAN.yaml` before Builder execution:

```yaml
task:
requirements:
acceptance_criteria:
expected_files:
expected_tests:
risk_surfaces:
test_handoff:
authorization:
```

### Requirements traceability

Completion must establish:

```text
requirement -> implementation evidence -> test evidence -> review evidence
```

Builder prose alone cannot satisfy a requirement.

### Change ownership detection

Before Builder dispatch, collect available evidence from CODEOWNERS/module ownership/generated-file ownership/migration ownership/shared-contract ownership. Ownership is context and escalation evidence, not authorization.

### Merge-base freshness

Verify merge base before reviewer dispatch, before accepting authoritative CI, and before PR-ready completion.

- unchanged normalized patch + content-neutral base update: prior review may survive;
- conflict resolution or changed effective patch: invalidate both review lenses.

### Test-creator handoff

Select one primary existing creator based on changed behavior: unit, integration, contract, e2e, or API. This batch does not implement multi-level test orchestration.

### CI evidence model

Persist evidence source explicitly:

- `builder_local`
- `reviewer_local`
- `orchestrator_local`
- `authoritative_ci`

Only `authoritative_ci` satisfies a required remote CI gate.

Use a bounded retry state, initially:

```yaml
ci_retry:
  max_attempts: 2
  consumed: 0
  last_failure_class: null
```

A retry after code changes is a new execution, not a flaky rerun.

### Resume checkpoints

Persist at meaningful state transitions:

- `TASK_PLANNED`
- `BUILDER_COMPLETE`
- `LENS_A_COMPLETE`
- `REMEDIATION_COMPLETE`
- `LENS_B_COMPLETE`
- `CI_PENDING`
- `CI_COMPLETE`
- `PR_READY`
- `BLOCKED`

On resume, verify branch/head/merge-base/fingerprint before trusting checkpoint state. Any mismatch invalidates dependent evidence.

### Generated-file invalidation

Generated files participate in fingerprinting and stale-review invalidation. Regeneration that changes effective patch content invalidates affected review evidence even when source files are unchanged.

### `loop-task-implementer` behavioral tests

At minimum:

1. TASK-PLAN is required before Builder dispatch.
2. requirement without implementation/test/review evidence cannot complete.
3. changed merge base with identical effective patch preserves review.
4. conflict resolution invalidates review.
5. generated-file-only change invalidates review.
6. local checks cannot satisfy authoritative CI.
7. retry budget stops after configured attempts.
8. code-change rerun does not consume flaky retry budget incorrectly.
9. resume from each checkpoint verifies fingerprint before reuse.
10. ownership evidence is advisory, not authorization.
11. correct primary test creator is selected for representative change types.
12. stale review evidence prevents PR_READY.

## Error and degraded behavior

Both skills fail closed on malformed machine contracts. Missing inspection capability must produce an explicit partial/unable state rather than inferred completeness. Missing authoritative CI must preserve the strongest local evidence but cannot be reported as authoritative success.

## Compatibility

- Existing human-readable reports remain supported; machine contracts are additive.
- Existing `pr-review` posting rules remain unchanged.
- Existing `loop-task-implementer` Builder/Reviewer/Orchestrator role boundaries remain unchanged.
- Existing review-lens cleanliness survives only when the shared freshness rules prove the effective patch unchanged.

## Testing and review gates

For each PR:

1. add RED behavioral/contract tests first;
2. implement smallest change set to GREEN;
3. run focused tests;
4. run full `make lint` and repository CI;
5. run security/dependency/static checks already required by repository CI;
6. perform two consecutive zero-finding reviews on the exact same head SHA;
7. merge only after those gates are satisfied and explicit merge authorization exists.

## Batch completion criteria

Batch 5.2 is complete only when merged `main` demonstrates:

- one canonical change identity and review evidence model;
- machine-visible cross-file/consumer impact in `pr-review`;
- migration/compatibility/rollout/config/IaC/test-quality evaluation;
- explicit incomplete-inspection behavior;
- defect/suggestion/question separation;
- tested normal and exhaustive modes;
- task-plan artifact and requirement traceability in `loop-task-implementer`;
- deterministic fingerprint + merge-base freshness;
- generated-file review invalidation;
- one-primary-test-creator handoff;
- bounded CI retry semantics and authoritative/local evidence distinction;
- safe checkpoint resume;
- full CI and two consecutive zero-finding reviews per PR.

## Follow-on

After Batch 5.2, the next independent slice is Batch 5.3: backlog items 40–41 (`incident-rca` and `k8s-overprovisioning-datadog`).
