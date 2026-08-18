# Batch 5.2C Loop Task Implementer Lifecycle Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `loop-task-implementer` persist an explicit task plan, trace requirements to implementation/tests/reviews, consume canonical review freshness, distinguish authoritative CI from local evidence, route to one relevant test creator, and resume safely after interruptions.

**Architecture:** Consume the shared 5.2A change/review contracts and the richer 5.2B review evidence. Extend the existing Orchestrator-owned state schema rather than creating a parallel state store; preserve Builder/Reviewer/Orchestrator boundaries and existing two-lens model.

**Tech Stack:** YAML state/contracts, Markdown role workflows, Python validators/tests/fixtures, pytest, existing loop-task-implementer lint/eval harness, repository CI.

**Spec:** `docs/superpowers/specs/2026-08-18-batch5-2-review-orchestration-design.md`

## Global Constraints

- Branch only after 5.2B is merged.
- Reuse shared `change_identity`/`review_evidence`; no second fingerprint schema.
- Builder prose alone never satisfies a requirement.
- Ownership evidence is advisory context, never authorization.
- Only `authoritative_ci` may satisfy a required remote CI gate.
- Generated-file changes invalidate affected review evidence.
- This batch selects one primary existing test creator only; do not implement Batch 5 item 42 multi-level test orchestration.
- Existing merge/deploy authorization and role boundaries remain unchanged.
- RED → GREEN per task; full CI + two consecutive zero-finding reviews before merge.

---

## File map

- Create `loop-task-implementer/templates/TASK-PLAN.yaml` — canonical task-plan artifact.
- Create `loop-task-implementer/reference/task-plan-contract.yaml` — required fields/traceability semantics.
- Modify `loop-task-implementer/reference/state-schema.yaml` — checkpoint, canonical identity/evidence, CI source/retry state, traceability, ownership, test handoff.
- Modify `loop-task-implementer/workflow/orchestrator.md` — initialization, merge-base freshness, resume validation, CI evidence acceptance.
- Modify `loop-task-implementer/workflow/builder.md` — consume task plan and emit implementation/test evidence without self-completing requirements.
- Modify `loop-task-implementer/workflow/reviewer.md` — attach lens evidence to shared identity and refuse stale evidence reuse.
- Modify or create focused references for fingerprint/freshness, test-creator routing, and checkpoint semantics if current files would otherwise become oversized.
- Modify `loop-task-implementer/report-template.md` — show task-plan/traceability/checkpoint/CI evidence state.
- Modify `loop-task-implementer/SKILL.md` — concise pointers only.
- Add/modify `loop-task-implementer/tests/` fixtures/tests for the required behavioral scenarios.
- Update changelog/workflow versions per repository convention.

### Task 1: Introduce TASK-PLAN artifact and requirement traceability

**Files:**
- Create: `loop-task-implementer/templates/TASK-PLAN.yaml`
- Create: `loop-task-implementer/reference/task-plan-contract.yaml`
- Modify: `loop-task-implementer/workflow/orchestrator.md`
- Modify: `loop-task-implementer/workflow/builder.md`
- Test: `loop-task-implementer/tests/test_batch5_2_loop_contracts.py`

**Interfaces:**
- Produces `task_plan` before Builder dispatch with stable requirement/AC IDs and expected test/change surfaces.

- [ ] **Step 1: Add failing contract tests**

```python
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _yaml(path: str):
    return yaml.safe_load(_text(path))


def test_task_plan_contract_requires_traceable_fields():
    contract = _yaml("loop-task-implementer/reference/task-plan-contract.yaml")
    assert contract["schema_version"] == 1
    required = contract["required_fields"]
    for field in (
        "task",
        "requirements",
        "acceptance_criteria",
        "expected_files",
        "expected_tests",
        "risk_surfaces",
        "test_handoff",
        "authorization",
    ):
        assert field in required
    assert contract["traceability"]["completion_requires"] == [
        "implementation_evidence",
        "test_evidence",
        "review_evidence",
    ]


def test_orchestrator_requires_task_plan_before_builder_dispatch():
    text = _text("loop-task-implementer/workflow/orchestrator.md")
    assert "TASK-PLAN.yaml" in text
    assert "before" in text.lower() and "builder" in text.lower()
```

- [ ] **Step 2: Run and prove RED**

Run: `pytest -q loop-task-implementer/tests/test_batch5_2_loop_contracts.py -k 'task_plan'`

Expected: FAIL.

- [ ] **Step 3: Add template/contract and workflow rules**

Use stable IDs in the template:

```yaml
schema_version: 1
task:
  id: ""
  source: ""
requirements: []
acceptance_criteria: []
expected_files: []
expected_tests: []
risk_surfaces: []
test_handoff:
  primary_creator: null
authorization:
  allowed_actions: []
  forbidden_actions: []
```

Each requirement row must carry `id`, `statement`, and later `implementation_evidence`, `test_evidence`, `review_evidence`. Missing any evidence leaves that requirement incomplete.

- [ ] **Step 4: Add negative traceability test**

Assert a requirement with implementation evidence but missing test or review evidence cannot reach completion/PR_READY.

- [ ] **Step 5: Run focused tests and prove GREEN**

Run: `pytest -q loop-task-implementer/tests/test_batch5_2_loop_contracts.py -k 'task_plan or traceability'`

- [ ] **Step 6: Commit**

```bash
git add loop-task-implementer/templates/TASK-PLAN.yaml loop-task-implementer/reference/task-plan-contract.yaml loop-task-implementer/workflow/orchestrator.md loop-task-implementer/workflow/builder.md loop-task-implementer/tests/test_batch5_2_loop_contracts.py
git commit -m "feat(loop): add task plan and requirement traceability"
```

### Task 2: Extend official state with canonical identity, checkpoints, and stale-review rules

**Files:**
- Modify: `loop-task-implementer/reference/state-schema.yaml`
- Modify: `loop-task-implementer/workflow/orchestrator.md`
- Modify: `loop-task-implementer/workflow/reviewer.md`
- Modify: `loop-task-implementer/tests/test_batch5_2_loop_contracts.py`

**Interfaces:**
- State consumes shared `change_identity` and `review_evidence`.
- Checkpoints exactly: `TASK_PLANNED`, `BUILDER_COMPLETE`, `LENS_A_COMPLETE`, `REMEDIATION_COMPLETE`, `LENS_B_COMPLETE`, `CI_PENDING`, `CI_COMPLETE`, `PR_READY`, `BLOCKED`.

- [ ] **Step 1: Add failing state tests**

```python
def test_state_schema_persists_batch5_2_checkpoints_and_shared_identity():
    state = _yaml("loop-task-implementer/reference/state-schema.yaml")
    values = state["checkpoint"]["allowed"]
    assert values == [
        "TASK_PLANNED", "BUILDER_COMPLETE", "LENS_A_COMPLETE",
        "REMEDIATION_COMPLETE", "LENS_B_COMPLETE", "CI_PENDING",
        "CI_COMPLETE", "PR_READY", "BLOCKED",
    ]
    assert state["change_identity"]["contract"] == "../docs/skill-framework/shared/change-identity.yaml"
    assert state["review_evidence"]["contract"] == "../docs/skill-framework/shared/review-evidence.yaml"
```

Adjust relative paths to the actual convention used by neighboring state-schema references; do not invent a path format inconsistent with current file.

- [ ] **Step 2: Run and prove RED**

Run: `pytest -q loop-task-implementer/tests/test_batch5_2_loop_contracts.py -k 'state_schema'`

- [ ] **Step 3: Extend state and freshness rules**

Persist current branch/head/merge-base/fingerprint and each lens approval's fingerprint. On resume or before PR_READY, mismatch invalidates dependent evidence. Conflict resolution always invalidates both lenses. Generated-file-only effective patch changes count as mismatch.

- [ ] **Step 4: Add resume/fingerprint scenarios**

Add fixtures/tests for:
- identical effective patch after content-neutral base update preserves review;
- conflict resolution invalidates review;
- generated-file-only change invalidates review;
- stale review evidence blocks PR_READY.

- [ ] **Step 5: Run focused tests**

Run: `pytest -q loop-task-implementer/tests/test_batch5_2_loop_contracts.py -k 'checkpoint or resume or fingerprint or stale'`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add loop-task-implementer/reference/state-schema.yaml loop-task-implementer/workflow/orchestrator.md loop-task-implementer/workflow/reviewer.md loop-task-implementer/tests/test_batch5_2_loop_contracts.py loop-task-implementer/tests/fixtures
git commit -m "feat(loop): persist freshness-bound review checkpoints"
```

### Task 3: Add merge-base freshness and change-ownership detection

**Files:**
- Modify: `loop-task-implementer/workflow/orchestrator.md`
- Create or modify: `loop-task-implementer/reference/change-ownership.md`
- Modify: `loop-task-implementer/tests/test_batch5_2_loop_contracts.py`

**Interfaces:**
- Produces `ownership_evidence` and merge-base gate outcomes; neither grants authorization.

- [ ] **Step 1: Add failing tests**

Assert Orchestrator checks merge base before reviewer dispatch, authoritative CI acceptance, and PR_READY. Assert ownership sources include CODEOWNERS/module/generated/migration/shared-contract evidence and explicitly say advisory/not authorization.

- [ ] **Step 2: Run RED**

Run: `pytest -q loop-task-implementer/tests/test_batch5_2_loop_contracts.py -k 'merge_base or ownership'`

- [ ] **Step 3: Implement minimal workflow/reference**

Merge-base outcomes:

```text
UNCHANGED_EFFECTIVE_PATCH -> may preserve review
CHANGED_EFFECTIVE_PATCH   -> invalidate affected review evidence
CONFLICT_RESOLUTION       -> invalidate both lenses
UNKNOWN                   -> block reuse until resolved
```

Ownership evidence must never alter `authorization.allowed_actions`.

- [ ] **Step 4: Add negative authorization test**

Fixture where CODEOWNERS names the current actor; assert merge/deploy remains forbidden unless independently authorized by the existing authorization contract.

- [ ] **Step 5: Run focused tests and commit**

```bash
pytest -q loop-task-implementer/tests/test_batch5_2_loop_contracts.py -k 'merge_base or ownership'
git add loop-task-implementer/workflow/orchestrator.md loop-task-implementer/reference/change-ownership.md loop-task-implementer/tests
git commit -m "feat(loop): gate on merge base and record change ownership"
```

If `change-ownership.md` already exists on merged main, modify it rather than creating a duplicate.

### Task 4: Add one-primary-test-creator routing

**Files:**
- Create or modify: `loop-task-implementer/reference/test-creator-routing.yaml`
- Modify: `loop-task-implementer/workflow/orchestrator.md`
- Modify: `loop-task-implementer/reference/task-plan-contract.yaml`
- Modify: `loop-task-implementer/tests/test_batch5_2_loop_contracts.py`

**Interfaces:**
- Produces one `test_handoff.primary_creator` from existing creators: unit, integration, contract, e2e, API.

- [ ] **Step 1: Add failing representative routing tests**

Create table-driven cases for pure function logic → unit, DB/service boundary → integration, published API/event/schema → contract, user workflow → e2e, HTTP endpoint behavior → API. Assert exactly one primary creator is selected.

- [ ] **Step 2: Run RED**

Run: `pytest -q loop-task-implementer/tests/test_batch5_2_loop_contracts.py -k 'test_creator'`

- [ ] **Step 3: Implement routing contract**

Routing order must be deterministic for overlapping signals. Document that additional levels are out of scope until Batch 5 item 42.

- [ ] **Step 4: Run GREEN and commit**

```bash
pytest -q loop-task-implementer/tests/test_batch5_2_loop_contracts.py -k 'test_creator'
git add loop-task-implementer/reference/test-creator-routing.yaml loop-task-implementer/reference/task-plan-contract.yaml loop-task-implementer/workflow/orchestrator.md loop-task-implementer/tests
git commit -m "feat(loop): route tasks to a primary test creator"
```

### Task 5: Distinguish authoritative CI and bound retry behavior

**Files:**
- Modify: `loop-task-implementer/reference/state-schema.yaml`
- Modify: `loop-task-implementer/workflow/orchestrator.md`
- Modify: `loop-task-implementer/report-template.md`
- Modify: `loop-task-implementer/tests/test_batch5_2_loop_contracts.py`

**Interfaces:**
- CI evidence source exactly one of `builder_local`, `reviewer_local`, `orchestrator_local`, `authoritative_ci`.
- Retry state: `max_attempts: 2`, `consumed`, `last_failure_class`.

- [ ] **Step 1: Add failing CI-source/retry tests**

Assert local sources cannot satisfy a remote required CI gate. Assert two flaky retry attempts exhaust the budget. Assert a run after a code change resets/starts a new execution rather than consuming the previous flaky rerun budget as if the commit were unchanged.

- [ ] **Step 2: Run RED**

Run: `pytest -q loop-task-implementer/tests/test_batch5_2_loop_contracts.py -k 'authoritative_ci or retry'`

- [ ] **Step 3: Implement state/workflow semantics**

Use:

```yaml
ci_evidence:
  source: authoritative_ci
  commit_sha: ""
  status: pending
ci_retry:
  max_attempts: 2
  consumed: 0
  last_failure_class: null
```

`PR_READY` requires required authoritative CI success for the exact current head when repository policy requires remote CI.

- [ ] **Step 4: Run GREEN and commit**

```bash
pytest -q loop-task-implementer/tests/test_batch5_2_loop_contracts.py -k 'authoritative_ci or retry'
git add loop-task-implementer/reference/state-schema.yaml loop-task-implementer/workflow/orchestrator.md loop-task-implementer/report-template.md loop-task-implementer/tests
git commit -m "feat(loop): distinguish authoritative CI and bound retries"
```

### Task 6: Make interruption/resume fail closed

**Files:**
- Modify: `loop-task-implementer/workflow/orchestrator.md`
- Modify: `loop-task-implementer/report-template.md`
- Modify: `loop-task-implementer/tests/test_batch5_2_loop_contracts.py`

**Interfaces:**
- Resume validates branch/head/merge-base/fingerprint before trusting stored checkpoint/evidence.

- [ ] **Step 1: Add failing checkpoint-resume matrix**

For every checkpoint value, create/parameterize a test that resumes with matching identity and preserves only evidence allowed at that checkpoint. Add mismatched fingerprint case and assert dependent lens/CI evidence is invalidated and state cannot jump to PR_READY.

- [ ] **Step 2: Run RED**

Run: `pytest -q loop-task-implementer/tests/test_batch5_2_loop_contracts.py -k 'resume'`

- [ ] **Step 3: Implement resume algorithm in Orchestrator contract**

Required order:

```text
load state
-> validate state schema
-> resolve current branch/head/merge base
-> derive current shared change_identity
-> compare stored identity
-> invalidate dependent evidence on mismatch
-> restore last trustworthy checkpoint
-> continue
```

- [ ] **Step 4: Run GREEN and commit**

```bash
pytest -q loop-task-implementer/tests/test_batch5_2_loop_contracts.py -k 'resume'
git add loop-task-implementer/workflow/orchestrator.md loop-task-implementer/report-template.md loop-task-implementer/tests
git commit -m "feat(loop): persist safe interruption and resume checkpoints"
```

### Task 7: Update orchestrator/version/docs and run full loop tests

**Files:**
- Modify: `loop-task-implementer/SKILL.md`
- Modify: relevant changelog/workflow-version files
- Modify: `loop-task-implementer/tests/test_batch5_2_loop_contracts.py`

- [ ] **Step 1:** Add assertions that SKILL.md points to TASK-PLAN, shared identity/evidence, CI source model, test routing, and resume checkpoints without duplicating full contracts.
- [ ] **Step 2:** Run RED.
- [ ] **Step 3:** Apply minimal pointers and required version/changelog bumps.
- [ ] **Step 4:** Run `pytest -q loop-task-implementer/tests` plus the existing skill-specific lint/eval target and `make validate-registry`; require all green.
- [ ] **Step 5:** Commit with `docs(loop): record Batch 5.2 lifecycle hardening`.

### Task 8: Full verification and PR 5.2C gate

- [ ] **Step 1:** Run all loop-task-implementer tests fresh.
- [ ] **Step 2:** Run `make lint` fresh and require exit 0.
- [ ] **Step 3:** Open draft PR `Batch 5.2C: harden loop task implementation lifecycle`, based on merged 5.2B `main`.
- [ ] **Step 4:** Require all current repository CI checks green on one exact SHA.
- [ ] **Step 5:** Zero-finding review pass 1: task-plan/traceability, fingerprint freshness, generated files, merge-base gate, checkpoint correctness.
- [ ] **Step 6:** Zero-finding review pass 2 on unchanged SHA: role/authorization safety, authoritative CI semantics, retry boundaries, test routing, backward compatibility, docs/version drift.
- [ ] **Step 7:** Merge only with explicit authorization after 2/2 clean reviews.
- [ ] **Step 8:** Verify merged `main` satisfies the full Batch 5.2 completion checklist from the design spec before starting items 40–41.
