# Batch 5.2B PR Review Intelligence Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `pr-review` so it produces machine-visible impact/inspection evidence, explicitly separates defects/suggestions/questions, and evaluates compatibility, migrations, rollout, tests, dependencies, config, and deployment risks while preserving its signal-over-noise model.

**Architecture:** Consume the shared 5.2A `change_identity` and `review_evidence` contracts. Extend the existing Phase 1/2 finding pipeline with one impact-graph artifact and one mandatory-dimensions checklist; keep existing provider adapters, posting authority, ≤10 normal cap, and exhaustive-mode escape hatch.

**Tech Stack:** Markdown/YAML workflow contracts, Python tests/fixtures already used by `pr-review`, pytest, existing PR-review lint/eval harness, repository CI.

**Spec:** `docs/superpowers/specs/2026-08-18-batch5-2-review-orchestration-design.md`

## Global Constraints

- Branch only after 5.2A is merged; consume its shared contracts rather than copy them.
- Preserve `pr-review` read + optional-comment authority; never approve, request changes, merge, close, reopen, or unapprove.
- Preserve normal-mode hard cap ≤10 after root-cause grouping.
- Exhaustive mode has no arbitrary top-level cap but still filters style-only noise.
- Every non-mechanical review evaluates every mandatory dimension even when that dimension yields no finding.
- Questions are non-blocking unless evidence promotes them to defects.
- Unavailable mandatory surfaces must be explicit; no silent completeness claims.
- RED → GREEN per task; full CI + two consecutive zero-finding reviews before merge.

---

## File map

- Create `pr-review/reference/impact-graph-contract.yaml` — machine-visible cross-file impact graph shape.
- Create `pr-review/reference/review-dimensions.yaml` — canonical mandatory review dimensions and triggers.
- Modify `pr-review/reference/finding-pipeline.md` — taxonomy, impact graph, dimension evaluation, exhaustive semantics.
- Modify `pr-review/workflow/phase-1.md` — gather consumer/config/deployment/test surfaces and unable-to-inspect annotations.
- Modify `pr-review/workflow/phase-2.md` — execute mandatory dimensions and emit shared review evidence.
- Modify `pr-review/workflow/phase-2-3-gate.md` — block completeness/posting path on invalid shared evidence where appropriate, without treating partial inspection as an automatic defect.
- Modify `pr-review/report-template.md` — render coverage and taxonomy clearly.
- Modify `pr-review/SKILL.md` — concise orchestrator references only; keep line budget.
- Add/modify `pr-review/tests/` fixtures/tests for the 12 required behavioral cases.
- Modify `pr-review/reference/smoke-test.md` and changelog/version records required by repository convention.

### Task 1: Add impact graph contract and Phase 1 collection

**Files:**
- Create: `pr-review/reference/impact-graph-contract.yaml`
- Modify: `pr-review/workflow/phase-1.md`
- Test: `pr-review/tests/test_batch5_2_pr_review.py`

**Interfaces:**
- Produces `impact_graph` nodes/edges consumed by Phase 2.
- Edge status: `observed | inferred | unable_to_inspect` with evidence.

- [ ] **Step 1: Write failing contract tests**

```python
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _yaml(path: str):
    return yaml.safe_load(_text(path))


def test_impact_graph_contract_covers_consumers_and_operational_surfaces():
    contract = _yaml("pr-review/reference/impact-graph-contract.yaml")
    assert contract["schema_version"] == 1
    assert contract["edge_status_values"] == ["observed", "inferred", "unable_to_inspect"]
    required = contract["edge_required_fields"]
    for field in ("from", "to", "relationship", "status", "evidence"):
        assert field in required
    assert "consumer" in contract["relationship_values"]
    assert "deployment" in contract["relationship_values"]
    assert "test" in contract["relationship_values"]


def test_phase1_collects_impact_and_unavailable_surfaces():
    text = _text("pr-review/workflow/phase-1.md")
    for token in (
        "impact_graph",
        "direct consumers",
        "generated clients",
        "configuration",
        "feature flags",
        "deployment",
        "unable_to_inspect",
    ):
        assert token.lower() in text.lower()
```

- [ ] **Step 2: Run and prove RED**

Run: `pytest -q pr-review/tests/test_batch5_2_pr_review.py -k 'impact_graph or phase1'`

Expected: FAIL because contract/Phase 1 behavior is absent.

- [ ] **Step 3: Add the contract and Phase 1 instructions**

Contract shape:

```yaml
schema_version: 1
edge_status_values: [observed, inferred, unable_to_inspect]
edge_required_fields: [from, to, relationship, status, evidence]
relationship_values:
  - symbol
  - contract
  - schema
  - consumer
  - generated_client
  - configuration
  - feature_flag
  - migration
  - deployment
  - test
```

Phase 1 must build evidence only from inspectable repository/provider surfaces. An unavailable consumer/config/deployment surface becomes `unable_to_inspect`; never synthesize an `observed` edge from naming guesses.

- [ ] **Step 4: Run focused tests and prove GREEN**

Run: `pytest -q pr-review/tests/test_batch5_2_pr_review.py -k 'impact_graph or phase1'`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pr-review/reference/impact-graph-contract.yaml pr-review/workflow/phase-1.md pr-review/tests/test_batch5_2_pr_review.py
git commit -m "feat(pr-review): build cross-file impact graph"
```

### Task 2: Add mandatory review dimensions

**Files:**
- Create: `pr-review/reference/review-dimensions.yaml`
- Modify: `pr-review/reference/finding-pipeline.md`
- Modify: `pr-review/workflow/phase-2.md`
- Modify: `pr-review/tests/test_batch5_2_pr_review.py`

**Interfaces:**
- Consumes `impact_graph`.
- Produces per-dimension evaluation status/evidence and shared `review_evidence` inspection surfaces.

- [ ] **Step 1: Add failing dimension tests**

```python
def test_mandatory_dimensions_cover_batch5_review_scope():
    contract = _yaml("pr-review/reference/review-dimensions.yaml")
    names = [item["id"] for item in contract["dimensions"]]
    assert names == [
        "cross_file_impact",
        "schema_migration",
        "compatibility_hidden_consumers",
        "rollout_rollback",
        "test_change_quality",
        "dependency_version_risk",
        "config_feature_flags",
        "iac_deployment",
        "inspection_coverage",
    ]


def test_phase2_requires_dimension_evaluation_even_without_findings():
    text = _text("pr-review/workflow/phase-2.md")
    assert "every mandatory review dimension" in text.lower()
    assert "no finding" in text.lower()
```

- [ ] **Step 2: Run and prove RED**

Run: `pytest -q pr-review/tests/test_batch5_2_pr_review.py -k 'mandatory_dimensions or dimension_evaluation'`

Expected: FAIL.

- [ ] **Step 3: Add contract and pipeline wiring**

Each dimension entry must define `id`, `mandatory_for`, `inputs`, and `unable_behavior`. For non-mechanical reviews, all nine dimensions are evaluated. `unable_behavior` records incomplete inspection; it does not fabricate a defect.

- [ ] **Step 4: Add scenario fixtures/assertions for API consumer, schema rollback, dependency bump, feature flag, IaC, and weakened test**

Use existing `pr-review/tests/` fixture conventions. Each fixture must assert the expected dimension is evaluated and the finding category when a defect is evidence-backed.

- [ ] **Step 5: Run focused tests**

Run: `pytest -q pr-review/tests/test_batch5_2_pr_review.py`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pr-review/reference/review-dimensions.yaml pr-review/reference/finding-pipeline.md pr-review/workflow/phase-2.md pr-review/tests/test_batch5_2_pr_review.py pr-review/tests/fixtures
git commit -m "feat(pr-review): evaluate compatibility and operational dimensions"
```

### Task 3: Separate defects, suggestions, and questions

**Files:**
- Modify: `pr-review/reference/finding-pipeline.md`
- Modify: `pr-review/report-template.md`
- Modify: `pr-review/workflow/phase-2-3-gate.md`
- Modify: `pr-review/tests/test_batch5_2_pr_review.py`

**Interfaces:**
- Produces findings categorized exactly as `DEFECT`, `SUGGESTION`, `QUESTION` while serializing to shared lower-case evidence buckets.

- [ ] **Step 1: Add failing taxonomy test**

```python
def test_question_is_not_blocking_without_defect_evidence():
    pipeline = _text("pr-review/reference/finding-pipeline.md")
    gate = _text("pr-review/workflow/phase-2-3-gate.md")
    assert "DEFECT" in pipeline and "SUGGESTION" in pipeline and "QUESTION" in pipeline
    assert "question" in gate.lower()
    assert "non-blocking" in gate.lower()
```

Add one behavioral fixture where missing domain knowledge produces QUESTION and assert the gate does not classify it as a defect/blocker.

- [ ] **Step 2: Run and prove RED**

Run: `pytest -q pr-review/tests/test_batch5_2_pr_review.py -k 'question_is_not_blocking'`

Expected: FAIL.

- [ ] **Step 3: Implement taxonomy and rendering**

Rules:

```text
DEFECT      evidence proves incorrect/unsafe/incompatible behavior
SUGGESTION  concrete value, non-blocking
QUESTION    unresolved fact request; not blocker until promoted with evidence
```

Report must keep severity on defects; suggestions/questions render without pretending to be blocking severity findings.

- [ ] **Step 4: Run focused tests**

Run: `pytest -q pr-review/tests/test_batch5_2_pr_review.py -k 'question or taxonomy'`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pr-review/reference/finding-pipeline.md pr-review/report-template.md pr-review/workflow/phase-2-3-gate.md pr-review/tests/test_batch5_2_pr_review.py pr-review/tests/fixtures
git commit -m "feat(pr-review): separate defects suggestions and questions"
```

### Task 4: Make normal/exhaustive and inspection evidence machine-verifiable

**Files:**
- Modify: `pr-review/reference/finding-pipeline.md`
- Modify: `pr-review/workflow/phase-2.md`
- Modify: `pr-review/workflow/phase-5.md`
- Modify: `pr-review/report-template.md`
- Modify: `pr-review/tests/test_batch5_2_pr_review.py`

**Interfaces:**
- Produces shared `review_evidence` with `review_mode`, `inspection_status`, `inspected_surfaces`, `unable_to_inspect`, categorized findings, and current `change_identity`.

- [ ] **Step 1: Add failing mode/evidence tests**

```python
def test_normal_and_exhaustive_modes_are_explicitly_testable():
    pipeline = _text("pr-review/reference/finding-pipeline.md")
    assert "normal" in pipeline.lower()
    assert "exhaustive" in pipeline.lower()
    assert "≤10" in pipeline or "<=10" in pipeline
    assert "no arbitrary" in pipeline.lower()


def test_phase5_renders_inspection_coverage_and_shared_evidence():
    text = _text("pr-review/workflow/phase-5.md")
    assert "review_evidence" in text
    assert "inspection_status" in text
    assert "unable_to_inspect" in text
```

Add behavioral fixtures generating 11 valid distinct root causes: normal must cap at 10; exhaustive must retain all 11.

- [ ] **Step 2: Run and prove RED**

Run: `pytest -q pr-review/tests/test_batch5_2_pr_review.py -k 'normal_and_exhaustive or inspection_coverage'`

Expected: FAIL.

- [ ] **Step 3: Wire shared evidence semantics**

Normal mode: cap after root-cause grouping. Exhaustive: no arbitrary cap. Both serialize every mandatory inspected/unavailable surface. A mandatory unavailable surface makes `inspection_status: partial` or `unable`, never `complete`.

- [ ] **Step 4: Add stale change-identity regression**

Fixture review evidence against fingerprint A, then present effective patch fingerprint B; assert re-review invalidates prior evidence and cannot reuse the previous completion state. Include generated-file-only B case.

- [ ] **Step 5: Run focused PR-review tests**

Run: `pytest -q pr-review/tests/test_batch5_2_pr_review.py`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pr-review/reference/finding-pipeline.md pr-review/workflow/phase-2.md pr-review/workflow/phase-5.md pr-review/report-template.md pr-review/tests/test_batch5_2_pr_review.py pr-review/tests/fixtures
git commit -m "feat(pr-review): emit freshness-bound review evidence"
```

### Task 5: Update orchestrator/version/docs without bloating SKILL.md

**Files:**
- Modify: `pr-review/SKILL.md`
- Modify: `pr-review/reference/smoke-test.md`
- Modify: `CHANGELOG.md` and/or skill changelog file required by repository convention
- Modify: `pr-review/tests/test_batch5_2_pr_review.py`

- [ ] **Step 1: Add failing documentation/version assertions**

Assert `SKILL.md` references impact graph, mandatory dimensions, shared review evidence, and taxonomy while remaining within the current repository max-line rule. Assert smoke test covers partial inspection and exhaustive mode.

- [ ] **Step 2: Run RED**

Run: `pytest -q pr-review/tests/test_batch5_2_pr_review.py -k 'orchestrator or smoke'`

- [ ] **Step 3: Apply minimal orchestrator pointers and version/changelog updates**

Do not restate full contracts in `SKILL.md`; link reference files. Increment skill/workflow versions according to repository convention for every modified workflow contract.

- [ ] **Step 4: Run PR-review-specific checks**

Run the repository's existing PR-review lint target plus:

```bash
pytest -q pr-review/tests
make validate-registry
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add pr-review/SKILL.md pr-review/reference/smoke-test.md pr-review/tests CHANGELOG.md
git commit -m "docs(pr-review): record Batch 5.2 review intelligence contract"
```

Include any skill-local changelog/version file actually used by current `main`.

### Task 6: Full verification and PR 5.2B gate

- [ ] **Step 1:** Run all `pr-review` tests fresh.
- [ ] **Step 2:** Run `make lint` fresh; require exit 0.
- [ ] **Step 3:** Open draft PR `Batch 5.2B: harden PR review intelligence`, based on merged 5.2A `main`.
- [ ] **Step 4:** Require all repository CI checks green on one exact head SHA.
- [ ] **Step 5:** Zero-finding review pass 1: correctness, hidden consumers, migration/rollout semantics, taxonomy, partial inspection, normal/exhaustive behavior.
- [ ] **Step 6:** Zero-finding review pass 2 on unchanged SHA: authority safety, provider compatibility, stale evidence invalidation, generated files, test quality, docs/version drift.
- [ ] **Step 7:** Merge only after explicit authorization and 2/2 clean reviews. Record merge SHA; 5.2C branches from resulting `main`.
