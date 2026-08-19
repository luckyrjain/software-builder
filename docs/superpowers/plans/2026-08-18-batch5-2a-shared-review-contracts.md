# Batch 5.2A Shared Review Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one canonical, machine-verifiable change-identity and review-evidence contract that both `pr-review` and `loop-task-implementer` can consume without duplicating fingerprint/freshness semantics.

**Architecture:** Add small shared schema/reference modules under the existing shared skill framework, plus a validator that fails closed on malformed identities, stale evidence, and illegal completeness claims. Keep this PR contract-only: no `pr-review` or `loop-task-implementer` workflow behavior changes beyond wiring tests that prove both consumers can reference the shared contract.

**Tech Stack:** Markdown/YAML contracts, Python 3 validators/tests, pytest, existing repository `make lint`/registry validation.

**Spec:** `docs/superpowers/specs/2026-08-18-batch5-2-review-orchestration-design.md`

## Global Constraints

- Implement only Batch 5.2A shared contracts; do not implement backlog items 40+.
- Machine contracts are additive; existing human-readable reports remain supported.
- Generated-file changes participate in fingerprint freshness.
- `complete` review inspection is invalid when any mandatory review surface is unavailable.
- Finding categories are exactly defect, suggestion, or question; questions are non-blocking unless promoted by evidence.
- Existing authorization/merge/deploy semantics are unchanged.
- Every implementation task follows RED → GREEN and ends with an independently reviewable commit.
- Final PR gate: full CI plus two consecutive zero-finding reviews on the exact same head SHA.

---

## File map

- Create `docs/skill-framework/shared/change-identity.yaml` — canonical field contract and normalization rules.
- Create `docs/skill-framework/shared/review-evidence.yaml` — canonical portable review-evidence envelope.
- Create `scripts/validate_review_contracts.py` — fail-closed structural and semantic validator for both shared contracts and fixture payloads.
- Create `scripts/tests/test_review_contracts.py` — direct validator and fingerprint/freshness contract tests.
- Modify `docs/skill-framework/README.md` — register the two new shared contracts and consumer guidance.
- Modify `scripts/registry/operational_upkeep.yaml` only if current file-role policy requires explicit classification for the new shared YAML files; otherwise leave unchanged and prove existing pattern covers them.
- Modify `make/core.mk` — add `validate-review-contracts` and wire it into `lint` if no existing generic shared-contract validator can absorb the checks.

### Task 1: Define canonical change identity

**Files:**
- Create: `docs/skill-framework/shared/change-identity.yaml`
- Test: `scripts/tests/test_review_contracts.py`

**Interfaces:**
- Consumes: Git commit identities plus canonical diff metadata supplied by a host/skill.
- Produces: `change_identity` with `schema_version`, `base_sha`, `head_sha`, `merge_base_sha`, `normalized_diff_fingerprint`, `changed_paths`, `generated_paths`, `dependency_changes`, and `config_changes`.

- [ ] **Step 1: Write failing schema-shape tests**

```python
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]


def _yaml(path: str):
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def test_change_identity_contract_has_required_fields():
    contract = _yaml("docs/skill-framework/shared/change-identity.yaml")
    assert contract["schema_version"] == 1
    required = contract["change_identity"]["required_fields"]
    assert required == [
        "base_sha",
        "head_sha",
        "merge_base_sha",
        "normalized_diff_fingerprint",
        "changed_paths",
        "generated_paths",
        "dependency_changes",
        "config_changes",
    ]
    assert contract["normalization"]["include_generated_paths"] is True
    assert "commit_message" in contract["normalization"]["excluded_transport_metadata"]
    assert contract["freshness"]["content_change_invalidates_review"] is True
```

- [ ] **Step 2: Run the test and prove RED**

Run: `pytest -q scripts/tests/test_review_contracts.py::test_change_identity_contract_has_required_fields`

Expected: FAIL because `change-identity.yaml` does not exist.

- [ ] **Step 3: Add the minimal contract**

Create `docs/skill-framework/shared/change-identity.yaml` with this exact semantic shape:

```yaml
schema_version: 1
change_identity:
  required_fields:
    - base_sha
    - head_sha
    - merge_base_sha
    - normalized_diff_fingerprint
    - changed_paths
    - generated_paths
    - dependency_changes
    - config_changes
  sha_format: git_sha_40_or_64_hex
  fingerprint_format: sha256_hex_64
  path_format: repository_relative_posix
normalization:
  source: canonical_effective_patch
  include_generated_paths: true
  excluded_transport_metadata:
    - commit_message
    - provider_diff_headers
    - review_comment_text
  ordering:
    changed_paths: lexicographic
    generated_paths: lexicographic
    dependency_changes: canonical_key_order
    config_changes: canonical_key_order
freshness:
  unchanged_effective_patch_may_preserve_review: true
  conflict_resolution_invalidates_review: true
  content_change_invalidates_review: true
  generated_file_change_invalidates_review: true
```

- [ ] **Step 4: Run the focused test and prove GREEN**

Run: `pytest -q scripts/tests/test_review_contracts.py::test_change_identity_contract_has_required_fields`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/skill-framework/shared/change-identity.yaml scripts/tests/test_review_contracts.py
git commit -m "feat(review): define canonical change identity contract"
```

### Task 2: Define canonical review evidence envelope

**Files:**
- Create: `docs/skill-framework/shared/review-evidence.yaml`
- Modify: `scripts/tests/test_review_contracts.py`

**Interfaces:**
- Consumes: canonical `change_identity` from Task 1.
- Produces: `review_evidence` with explicit inspection status, finding taxonomy, and unavailable-surface annotations.

- [ ] **Step 1: Add the failing contract test**

```python
def test_review_evidence_contract_is_portable_and_fail_closed():
    contract = _yaml("docs/skill-framework/shared/review-evidence.yaml")
    assert contract["schema_version"] == 1
    evidence = contract["review_evidence"]
    assert evidence["review_modes"] == ["normal", "exhaustive"]
    assert evidence["inspection_status_values"] == ["complete", "partial", "unable"]
    assert evidence["finding_categories"] == ["defect", "suggestion", "question"]
    assert evidence["rules"]["questions_are_non_blocking_until_promoted"] is True
    assert evidence["rules"]["complete_forbidden_with_mandatory_unable_surface"] is True
    assert evidence["rules"]["stale_change_identity_invalidates_envelope"] is True
```

- [ ] **Step 2: Run and prove RED**

Run: `pytest -q scripts/tests/test_review_contracts.py::test_review_evidence_contract_is_portable_and_fail_closed`

Expected: FAIL because `review-evidence.yaml` does not exist.

- [ ] **Step 3: Add the minimal contract**

```yaml
schema_version: 1
review_evidence:
  required_fields:
    - change_identity
    - requirements_ref
    - review_mode
    - inspection_status
    - inspected_surfaces
    - unable_to_inspect
    - findings
    - generated_at
  review_modes: [normal, exhaustive]
  inspection_status_values: [complete, partial, unable]
  finding_categories: [defect, suggestion, question]
  unable_to_inspect_required_fields: [surface, reason]
  finding_required_fields: [id, category, summary, evidence]
  rules:
    questions_are_non_blocking_until_promoted: true
    complete_forbidden_with_mandatory_unable_surface: true
    stale_change_identity_invalidates_envelope: true
    categories_are_disjoint: true
```

- [ ] **Step 4: Run and prove GREEN**

Run: `pytest -q scripts/tests/test_review_contracts.py::test_review_evidence_contract_is_portable_and_fail_closed`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/skill-framework/shared/review-evidence.yaml scripts/tests/test_review_contracts.py
git commit -m "feat(review): define shared review evidence envelope"
```

### Task 3: Implement fail-closed validator

**Files:**
- Create: `scripts/validate_review_contracts.py`
- Modify: `scripts/tests/test_review_contracts.py`

**Interfaces:**
- Produces: `validate_change_identity(payload: object) -> list[str]`, `validate_review_evidence(payload: object, current_identity: object | None = None) -> list[str]`, CLI exit `0` on clean payload/contract and non-zero with deterministic errors otherwise.

- [ ] **Step 1: Add failing validator tests**

```python
import importlib.util


def _load_validator():
    path = ROOT / "scripts/validate_review_contracts.py"
    spec = importlib.util.spec_from_file_location("validate_review_contracts", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _identity(**overrides):
    value = {
        "base_sha": "a" * 40,
        "head_sha": "b" * 40,
        "merge_base_sha": "a" * 40,
        "normalized_diff_fingerprint": "c" * 64,
        "changed_paths": ["src/a.py"],
        "generated_paths": [],
        "dependency_changes": [],
        "config_changes": [],
    }
    value.update(overrides)
    return value


def test_validator_rejects_malformed_identity_and_stale_evidence():
    validator = _load_validator()
    assert validator.validate_change_identity(_identity(head_sha=True))
    evidence = {
        "change_identity": _identity(),
        "requirements_ref": None,
        "review_mode": "normal",
        "inspection_status": "complete",
        "inspected_surfaces": ["diff"],
        "unable_to_inspect": [],
        "findings": {"defect": [], "suggestion": [], "question": []},
        "generated_at": "2026-08-18T00:00:00Z",
    }
    current = _identity(normalized_diff_fingerprint="d" * 64)
    errors = validator.validate_review_evidence(evidence, current_identity=current)
    assert any("stale change_identity" in error for error in errors)


def test_validator_rejects_complete_with_mandatory_unable_surface():
    validator = _load_validator()
    evidence = {
        "change_identity": _identity(),
        "requirements_ref": None,
        "review_mode": "normal",
        "inspection_status": "complete",
        "inspected_surfaces": ["diff"],
        "unable_to_inspect": [{"surface": "direct_consumers", "reason": "provider unavailable", "mandatory": True}],
        "findings": {"defect": [], "suggestion": [], "question": []},
        "generated_at": "2026-08-18T00:00:00Z",
    }
    errors = validator.validate_review_evidence(evidence)
    assert any("complete" in error and "mandatory" in error for error in errors)
```

- [ ] **Step 2: Run and prove RED**

Run: `pytest -q scripts/tests/test_review_contracts.py -k 'validator_'`

Expected: FAIL because validator module/functions do not exist.

- [ ] **Step 3: Implement minimal validation functions**

Implement explicit type checks before enum/set membership so malformed YAML/JSON lists/maps never raise `TypeError`. Validate 40/64-char Git SHAs, 64-char lowercase/uppercase hex SHA-256 fingerprints, repository-relative POSIX paths, finding buckets exactly `{defect,suggestion,question}`, and stale identity equality by `base_sha`, `head_sha`, `merge_base_sha`, and fingerprint.

Use signatures:

```python
def validate_change_identity(payload: object) -> list[str]: ...

def validate_review_evidence(
    payload: object,
    *,
    current_identity: object | None = None,
) -> list[str]: ...
```

The validator must return errors, not throw, for malformed user/machine payloads.

- [ ] **Step 4: Add generated-path and question-category negative tests**

```python
def test_generated_path_difference_makes_identity_stale():
    validator = _load_validator()
    stored = _identity(generated_paths=["generated/client.py"])
    current = _identity(generated_paths=["generated/client_v2.py"])
    evidence = {
        "change_identity": stored,
        "requirements_ref": None,
        "review_mode": "normal",
        "inspection_status": "complete",
        "inspected_surfaces": ["diff"],
        "unable_to_inspect": [],
        "findings": {"defect": [], "suggestion": [], "question": []},
        "generated_at": "2026-08-18T00:00:00Z",
    }
    assert any("stale change_identity" in e for e in validator.validate_review_evidence(evidence, current_identity=current))


def test_unknown_finding_bucket_is_rejected():
    validator = _load_validator()
    evidence = {
        "change_identity": _identity(),
        "requirements_ref": None,
        "review_mode": "normal",
        "inspection_status": "partial",
        "inspected_surfaces": [],
        "unable_to_inspect": [],
        "findings": {"defect": [], "suggestion": [], "question": [], "blocker": []},
        "generated_at": "2026-08-18T00:00:00Z",
    }
    assert any("finding buckets" in e for e in validator.validate_review_evidence(evidence))
```

- [ ] **Step 5: Run focused tests and prove GREEN**

Run: `pytest -q scripts/tests/test_review_contracts.py`

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/validate_review_contracts.py scripts/tests/test_review_contracts.py
git commit -m "feat(review): validate shared review contracts"
```

### Task 4: Register and lint the contracts

**Files:**
- Modify: `docs/skill-framework/README.md`
- Modify: `make/core.mk`
- Modify: `scripts/tests/test_review_contracts.py`
- Conditional modify: `scripts/registry/operational_upkeep.yaml`

**Interfaces:**
- Produces: local/CI command `make validate-review-contracts` and discoverable shared-contract documentation.

- [ ] **Step 1: Add failing integration assertions**

```python
def test_shared_review_contracts_are_documented_and_linted():
    readme = (ROOT / "docs/skill-framework/README.md").read_text(encoding="utf-8")
    assert "change-identity.yaml" in readme
    assert "review-evidence.yaml" in readme
    makefile = (ROOT / "make/core.mk").read_text(encoding="utf-8")
    assert "validate-review-contracts:" in makefile
    assert "validate-review-contracts" in next(
        line for line in makefile.splitlines() if line.startswith("lint:")
    )
```

- [ ] **Step 2: Run and prove RED**

Run: `pytest -q scripts/tests/test_review_contracts.py::test_shared_review_contracts_are_documented_and_linted`

Expected: FAIL because registration/lint wiring is absent.

- [ ] **Step 3: Add docs and make target**

Add a concise shared-contract entry to `docs/skill-framework/README.md` describing both consumers. Add:

```make
.PHONY: validate-review-contracts
validate-review-contracts:
	$(PYTHON) scripts/validate_review_contracts.py --contracts-only
```

and include `validate-review-contracts` in the existing `lint:` prerequisite list without reordering unrelated targets.

If operational-upkeep health classifies `docs/skill-framework/shared/**` already, do not edit its policy. If it reports the new YAML files unclassified, add the narrowest shared-reference pattern needed and a corresponding operational-upkeep regression test.

- [ ] **Step 4: Run focused and registry checks**

Run:

```bash
pytest -q scripts/tests/test_review_contracts.py
make validate-review-contracts
make validate-registry
```

Expected: all PASS / exit 0.

- [ ] **Step 5: Commit**

```bash
git add docs/skill-framework/README.md make/core.mk scripts/tests/test_review_contracts.py scripts/registry/operational_upkeep.yaml
git commit -m "ci(review): enforce shared review contracts"
```

If `operational_upkeep.yaml` was not changed, omit it from `git add`.

### Task 5: Full verification and PR 5.2A gate

**Files:** No new implementation files unless verification reveals a defect.

- [ ] **Step 1: Run focused tests fresh**

Run: `pytest -q scripts/tests/test_review_contracts.py`

Expected: PASS, zero failures.

- [ ] **Step 2: Run full repository lint fresh**

Run: `make lint`

Expected: exit 0.

- [ ] **Step 3: Open draft PR 5.2A from a branch based on current `main`**

Title: `Batch 5.2A: add shared change and review evidence contracts`

Body must state that 5.2B/5.2C are intentionally not included.

- [ ] **Step 4: Wait for repository CI and require all required checks green on one exact head SHA**

Expected: Lint, CodeQL, Secret Scan, Dependency Review, and any current required checks all succeed.

- [ ] **Step 5: Run zero-finding review pass 1 on that exact SHA**

Review scope: validator correctness, malformed-input fail-closed behavior, schema consistency, generated-file freshness, CI wiring. Any finding triggers a fix and resets the counter.

- [ ] **Step 6: Run zero-finding review pass 2 independently on the unchanged exact SHA**

Review scope: consumer portability, backward compatibility, authority non-expansion, docs/lint drift. Require zero actionable findings.

- [ ] **Step 7: Merge only with explicit authorization after 2/2 clean reviews**

After merge, record the merge commit; 5.2B must branch from the resulting `main`.
