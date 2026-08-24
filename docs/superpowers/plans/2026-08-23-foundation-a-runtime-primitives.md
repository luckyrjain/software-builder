# Foundation A — Lifecycle & Composition Runtime Primitives v10

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the PRD→System Design→Architecture Review lifecycle and add reusable state, identity, trust, and embedded-context runtime primitives without migrating durable artifacts to v2.

**Architecture:** Keep Foundation A platform-only: correct canonical composition/routing first, then add bounded state semantics, canonical target/digest/trust helpers, and the external assessment_context carrier. All later PRs consume these primitives instead of reimplementing identity or trust logic.

**Tech Stack:** Python 3, YAML registry contracts, pytest, Make, Markdown skill contracts.

**Spec:** External reviewed execution-package artifact `2026-08-23-engineering-decision-delivery-after-pr159-design-v10.md` (SHA-256: `78f8810b1b7d45508c413eb46cff654824205cca8976d6319931dbe8456bf57b`).

## Global Constraints

- Execute only with the sibling v10 design artifact whose SHA-256 is `78f8810b1b7d45508c413eb46cff654824205cca8976d6319931dbe8456bf57b`; if the file is missing or the digest differs, stop and re-review before implementation.
- Start every PR from fresh reviewed `main`; PR #159 is merged and must not be treated as a stacked prerequisite.
- Execute in a dedicated isolated clean worktree/branch. Before Task 0 and after every task commit, `git status --porcelain` must be empty; if unrelated changes appear, stop and isolate them before any `git add -A`.
- Preserve canonical registry ownership: edit `skills.yaml` and source registries, then regenerate projections with `make generate`; do not hand-edit generated projections.
- Machine gates fail closed on missing, stale, conflicting, untrusted, or target-mismatched evidence; `UNKNOWN`/`NOT_APPLICABLE` are never silently promoted to PASS.
- Preserve evidence authority through handoffs; producer trust never upgrades caller/model/repository evidence authority.
- Keep explicit PR/MR code-review ownership with `pr-review`; do not create competing numbered-PR owners.
- Use TDD for behavioral changes and run the repository-wide final gate before claiming the PR ready.
- Do not merge or perform destructive remote actions from this plan without explicit authorization.

---

**Date:** 2026-08-23
**Repository:** `luckyrjain/software-builder`
**Repository destination:** `docs/superpowers/plans/2026-08-23-foundation-a-runtime-primitives.md`
**Depends on:** fresh `main` containing PR #159 merge commit `319eb2200264f5b2a4cdf327686d98e5383387ef`
**Design source:** External reviewed execution-package artifact `2026-08-23-engineering-decision-delivery-after-pr159-design-v10.md` (SHA-256: `78f8810b1b7d45508c413eb46cff654824205cca8976d6319931dbe8456bf57b`).

## Baseline preflight

Before RED:

```bash
git fetch origin main
git merge-base --is-ancestor 319eb2200264f5b2a4cdf327686d98e5383387ef origin/main
git rev-parse origin/main
```

Record the resulting `origin/main` SHA in the PR description and create the work branch from that exact SHA. If `main` moved after the reviewed merge commit, inspect the intervening contract-path diff before continuing.

## Scope

This PR owns:

- PRD -> system-design -> architecture-review routing;
- optional `allowed_state_semantics` runtime support;
- assessment-target canonicalization/digest helpers;
- artifact-trust classification helper;
- typed external `assessment_context` for artifact-backed embedded skill invocations;
- registry-derived count cleanup;
- security-scanner-safe adversarial-fixture policy;
- tests/docs/generated projections for only those changes.

This PR does **not**:

- upgrade any durable artifact from schema v1 to v2;
- add a new skill;
- change release readiness;
- add production readiness;
- add implementation-plan execution behavior.

## Review-size guard

Before implementation, count expected changed non-generated files. Keep the behavioral diff below the repository default hard stop: **40 files / 1500 changed lines**. If generated publication pushes the final PR over the file threshold, move only generated/docs publication to a no-behavior follow-up.

---

## Task 0 — Revalidate merged-main baseline

**Interfaces:**
- Consumes: merged `main`, current registry/runtime/tests.
- Produces: recorded base SHA and verified clean baseline.


**Read:**
- `skills.yaml` from fresh `origin/main`
- `docs/skill-framework/shared/runtime-contract.md`
- `scripts/registry/artifact_contracts.py`
- `scripts/registry/composition_runtime.py`
- affected routing/eval tests

- [ ] `git fetch origin main`.
- [ ] `git merge-base --is-ancestor 319eb2200264f5b2a4cdf327686d98e5383387ef origin/main` succeeds.
- [ ] Record `git rev-parse origin/main` in the PR description.
- [ ] If `origin/main` is newer than the reviewed merge commit, inspect the intervening diff for every contract path this PR touches.
- [ ] Run the existing registry/artifact tests before RED.

PR #159 is already merged; do not stack on its old feature branch and do not carry the earlier Secret Scan failure forward as current state. The final PR head passed Lint, Secret Scan, Dependency Review, and CodeQL.

**Verification:**
```bash
git status --short
git rev-parse HEAD
make validate-registry
python3 -m pytest -p no:cacheprovider scripts/tests/test_artifact_contracts.py -q
```

Commit: none.

---

## Executable test helper contract

Use the repository's real dispatcher/registry loaders. Production APIs introduced/modified by this PR are exactly: `canonical_payload_digest`, `canonical_text_digest`, `normalize_repo_identity`, `normalize_environment_identity`, `same_environment`, `classify_artifact_trust`, `classify_assessment_context_trust`, `resolve_embedded_inputs`, `validate_embedded_result_target`, `validate_artifact_contracts`, `validate_artifact_result`, and `validate_composition_runtime`.

Module ownership is explicit: digest/identity helpers live in `scripts/registry/assessment_target.py`; producer/context trust classification lives in `scripts/registry/artifact_trust.py`; `resolve_embedded_inputs` and `validate_embedded_result_target` live in new `scripts/registry/embedded_context.py`; artifact validators remain in `scripts/registry/artifact_contracts.py`; runtime graph validation remains in `scripts/registry/composition_runtime.py`. The internal `_issue_runtime_handoff_metadata` factory is runtime-owned test/integration plumbing, not a caller-authenticated payload field; dictionary metadata claiming `runtime_handoff` must remain untrusted.

Test-local builders defined before first use are exactly: `assessment_context`, `assessment_target`, `registry_fixture`, `registry_fixture_with_raw_only_invoke_edge`, `registry_fixture_with_assessment_context_invoke_edge`, `load_manifest_with_assessment_context`, `valid_security_result`, and `valid_mr_review_result`. `no_mandatory_handoff` is a one-line local assertion helper over `load_registry(ROOT).skills[source].composition.invokes`. Routing tests call `dispatch_prompt` directly; there is no generic `route()` production API.
### Execution checklist

- [ ] **Step 1: Verify the preflight exactly as written in this task.**
- [ ] **Step 2: Confirm the working tree is clean and record the resolved base/version evidence.** If any baseline assertion fails, stop this PR and revise the plan against fresh `main`; do not patch around drift.
- [ ] **Step 3: Do not make production changes in this preflight task.** Its deliverable is the verified baseline consumed by Task 1.

## Task 1 — Correct the design lifecycle

**Interfaces:**
- Consumes: current dispatcher, `prd_report` v1, `system_design_spec` v1.
- Produces: corrected PRD→System Design→Architecture Review routing plus exact v1 `consume_fields`.


**Modify:**
- `docs/skill-framework/shared/skill-routing.md`
- `docs/skill-framework/shared/cross-skill-escalation.md`
- `prd-architect/SKILL.md`
- `prd-architect/CHANGELOG.md`
- `system-design/SKILL.md`
- `system-design/CHANGELOG.md`
- `architecture-review/SKILL.md`
- `architecture-review/CHANGELOG.md`
- `skills.yaml`
- routing/eval tests that encode the old path

### RED

Add routing assertions:

```python
from scripts.evals.dispatcher import dispatch_prompt
from scripts.registry.load import load_registry

def _owner(prompt: str) -> str | None:
    result = dispatch_prompt(ROOT, load_registry(ROOT), prompt)
    assert result.status == "selected", result
    return result.owner

def test_ready_prd_routes_to_system_design_before_architecture_review() -> None:
    assert _owner("Turn this ready PRD into the implementation design") == "system-design"

def test_pre_pr_d_numbered_pr_readiness_remains_unowned() -> None:
    # Production-readiness-review does not exist yet; do not misroute readiness to code review.
    result = dispatch_prompt(ROOT, load_registry(ROOT), "Is PR #123 production ready?")
    assert result.status == "no_match"
    assert result.owner is None

def test_architecture_rework_is_recommendation_not_runtime_cycle() -> None:
    assert no_mandatory_handoff("architecture-review", "system-design")

def test_foundation_a_lifecycle_consume_fields_are_exact() -> None:
    registry = load_registry(ROOT)
    sd = registry.skills["system-design"].composition
    ar = registry.skills["architecture-review"].composition
    assert sd.consume_fields["prd_report"] == ["title", "build_readiness", "depth", "response_mode"]
    assert sd.consume_fields["architecture_review_report"] == ["title", "decision"]
    assert ar.consume_fields["system_design_spec"] == ["title", "readiness"]
    assert ar.consume_fields["prd_report"] == ["title", "build_readiness", "depth", "response_mode"]

```

Run:

```bash
python3 -m pytest -p no:cacheprovider \
  scripts/tests/test_batch3_scenario_harness.py \
  scripts/tests/test_platform_eval_contract.py -q
```

Expected: at least the corrected routing/consume-field assertion fails.

### GREEN

Normative path:

```text
prd-architect -> system-design -> architecture-review
```

Alternate path when caller already has a sufficiently concrete ADR/design:

```text
architecture-review -> system-design
```

`architecture-review -> system-design` after `Needs rework` is a **recommendation for a new invocation**, not a mandatory composition edge.

Version changes in this PR:

```text
prd-architect         1.2.0 -> 1.3.0
system-design         1.0.0 -> 1.1.0
architecture-review   1.0.0 -> 1.1.0
```

These bumps belong to Foundation A because the externally observable lifecycle/input/handoff behavior changes here. Foundation B may bump `system-design` and `architecture-review` once more for their separate artifact-v2 producer change.

Update canonical consume fields and runtime input semantics. At the Foundation-A/v1 stage the registry contract is exact:

```yaml
system-design:
  consumes: [prd_report, architecture_review_report]
  consume_fields:
    prd_report: [title, build_readiness, depth, response_mode]
    architecture_review_report: [title, decision]
architecture-review:
  consumes: [system_design_spec, prd_report]
  consume_fields:
    system_design_spec: [title, readiness]
    prd_report: [title, build_readiness, depth, response_mode]
```

- `system-design` consumes v1 `prd_report` as the machine readiness gate; document identity is carried separately in invocation/handoff context until B1 **and** it requires the full Final PRD content or a retrievable immutable PRD reference; `architecture_review_report` remains only the reviewed-ADR alternate entry, not the default PRD path;
- `architecture-review` consumes v1 `system_design_spec` as the machine readiness gate; design identity is carried separately in invocation/handoff context until B1 **and** it requires the full System Design Spec content or a retrievable immutable design reference, plus `prd_report`/proposal context as required by its existing contract;
- neither skill may reconstruct the missing document body from `title`, `readiness`, `build_readiness`, or other summary fields;
- `resolve_embedded_inputs` is the shared Foundation-A helper that distinguishes machine gate metadata from required semantic document content/ref and returns a typed BLOCKED result when the body/ref is absent.

At Foundation A time, the document/ref may be carried in current invocation/handoff context. Foundation B1 later binds the ref/digest into v2 `assessment_target`; do not wait for B1 to enforce the no-summary-as-content rule.

Do not broaden PR/MR routing in Foundation A. Before PR D exists, an explicit PR/MR production-readiness prompt remains `no_match` in the deterministic oracle rather than being misrouted to code review or release-wide readiness. Intent-specific routing is updated by PR A/B/D as those capabilities land; generic PR/MR code review remains owned by `pr-review`.

Run the RED command again; expected PASS.

Commit:

```bash
git add docs/skill-framework/shared/skill-routing.md \
  docs/skill-framework/shared/cross-skill-escalation.md \
  prd-architect system-design architecture-review skills.yaml scripts/tests
git commit -m "fix: correct product to design review lifecycle"
```
### Execution checklist

- [ ] **Step 1: Add the RED assertions shown in this task before changing production behavior.** Use the exact test/fixture/API names defined in this task's interface and helper contracts.
- [ ] **Step 2: Run the focused test command.**

```bash
python3 -m pytest -p no:cacheprovider scripts/tests/test_artifact_contracts.py scripts/tests/test_composition_runtime.py scripts/tests/test_composition_contracts.py -q
```

Expected: FAIL because this task's new contract/behavior is not implemented yet; a missing unrelated dependency or pre-existing failure is not an acceptable RED signal.

- [ ] **Step 3: Implement the minimum production/registry/skill changes specified in this task.** Do not broaden scope beyond the exact interfaces and files named here.
- [ ] **Step 4: Run the same focused command again.** Expected: PASS. Then run any additional task-specific command already listed above.
- [ ] **Step 5: Review the task diff and commit only after the focused tests pass.**

```bash
git status --short
git diff --check
git add -A
git commit -m "feat: correct the design lifecycle"
```

---

## Task 2 — Add `allowed_state_semantics`

**Interfaces:**
- Consumes: current `state_semantics` and artifact validator.
- Produces: `allowed_state_semantics` validation with backward-compatible defaults.


**Modify:**
- `skills.yaml`
- `scripts/registry/artifact_contracts.py`
- `docs/skill-framework/shared/runtime-contract.md`
- `scripts/tests/test_artifact_contracts.py`

### RED

Use `security_review_report` as the representative final-config artifact:

```python
def test_allowed_state_semantics_accepts_declared_alternate_state(tmp_path: Path) -> None:
    root = registry_fixture(
        tmp_path,
        artifact="security_review_report",
        default="current_state",
        allowed=["current_state", "proposed_state"],
    )
    result = valid_security_result(state_semantic="proposed_state")
    assert validate_artifact_result(
        root, "security_review_report", result, producer_skill="security-review"
    ) == []

def test_default_must_be_in_allowed_state_set(tmp_path: Path) -> None:
    root = registry_fixture(
        tmp_path,
        artifact="security_review_report",
        default="current_state",
        allowed=["proposed_state"],
    )
    assert any("default state semantic" in e for e in validate_artifact_contracts(root))

def test_artifact_without_allowed_set_remains_exact() -> None:
    result = valid_mr_review_result(state_semantic="proposed_state")
    errors = validate_artifact_result(
        ROOT, "mr_review_report", result, producer_skill="pr-review"
    )
    assert any("state semantic" in e for e in errors)
```

Run:

```bash
python3 -m pytest -p no:cacheprovider scripts/tests/test_artifact_contracts.py -q
```

Expected: new alternate-state test fails.

### GREEN

Add optional:

```yaml
contracts:
  platform:
    artifact_runtime:
      allowed_state_semantics: {}
```

Validation rules:

1. optional mapping;
2. keys must be durable artifact IDs;
3. values are non-empty unique lists from current vocabulary;
4. default `state_semantics[artifact]` is included;
5. result emits exactly one `state_semantic`;
6. if no allowed set exists, preserve exact old behavior.

Update runtime-contract wording from “durable artifacts declare one state semantic” to:

> A durable artifact has one default semantic and may declare a finite allowed set; each individual result still emits exactly one semantic.

Do **not** configure the delivery artifacts' final allowed sets until Foundation B.

Run same tests; expected PASS.

Commit:

```bash
git add skills.yaml scripts/registry/artifact_contracts.py \
  docs/skill-framework/shared/runtime-contract.md scripts/tests/test_artifact_contracts.py
git commit -m "feat: support bounded artifact state semantics"
```
### Execution checklist

- [ ] **Step 1: Add the RED assertions shown in this task before changing production behavior.** Use the exact test/fixture/API names defined in this task's interface and helper contracts.
- [ ] **Step 2: Run the focused test command.**

```bash
python3 -m pytest -p no:cacheprovider scripts/tests/test_artifact_contracts.py scripts/tests/test_composition_runtime.py scripts/tests/test_composition_contracts.py -q
```

Expected: FAIL because this task's new contract/behavior is not implemented yet; a missing unrelated dependency or pre-existing failure is not an acceptable RED signal.

- [ ] **Step 3: Implement the minimum production/registry/skill changes specified in this task.** Do not broaden scope beyond the exact interfaces and files named here.
- [ ] **Step 4: Run the same focused command again.** Expected: PASS. Then run any additional task-specific command already listed above.
- [ ] **Step 5: Review the task diff and commit only after the focused tests pass.**

```bash
git status --short
git diff --check
git add -A
git commit -m "feat: add allowed state semantics"
```

---

## Task 3 — Add canonical target/digest and trust helpers

**Interfaces:**
- Consumes: Foundation-A artifact validator hooks.
- Produces: `canonical_payload_digest`, `canonical_text_digest`, target normalization, artifact/context trust classifiers.


**Create:**
- `scripts/registry/assessment_target.py`
- `scripts/registry/artifact_trust.py`
- `scripts/tests/test_assessment_target.py`
- `scripts/tests/test_artifact_trust.py`

**Modify:**
- `scripts/registry/artifact_contracts.py` only to expose/integrate helper validation hooks needed later; do not require v2 fields yet.

### RED — canonicalization/digest

```python
def test_payload_digest_is_key_order_independent() -> None:
    assert canonical_payload_digest({"b": 2, "a": 1}) == canonical_payload_digest({"a": 1, "b": 2})

def test_text_digest_normalizes_crlf_only() -> None:
    assert canonical_text_digest("a\r\nb\r\n") == canonical_text_digest("a\nb\n")

def test_environment_aliases_do_not_fuzzy_match() -> None:
    assert normalize_environment_identity(" PROD ") == "prod"
    assert normalize_environment_identity("production") == "production"
    assert same_environment("prod", "production") is False

def test_repo_normalization_does_not_alias_different_paths() -> None:
    assert normalize_repo_identity("https://GitHub.com/acme/a.git") == "https://github.com/acme/a"
    assert normalize_repo_identity("https://github.com/acme/a") != normalize_repo_identity("https://github.com/acme/b")
```

### RED — trust

```python
def test_caller_supplied_artifact_never_becomes_gate_trusted() -> None:
    trust = classify_artifact_trust(
        artifact_type="security_review_report",
        acquisition="caller_supplied",
        producer_skill="security-review",
        validator_passed=True,
    )
    assert trust.trusted_for_gate is False

def test_direct_child_requires_runtime_producer_identity_and_validation() -> None:
    trust = classify_artifact_trust(
        artifact_type="security_review_report",
        acquisition="direct_child",
        producer_skill="security-review",
        validator_passed=True,
    )
    assert trust.trusted_for_gate is True
```

Run:

```bash
python3 -m pytest -p no:cacheprovider \
  scripts/tests/test_assessment_target.py \
  scripts/tests/test_artifact_trust.py -q
```

Expected: import/test failure because helpers do not exist.

### GREEN

Implement exactly:

- SHA-256 canonical payload digest: UTF-8 JSON, recursive sorted keys, separators `,`/`:`, no insignificant whitespace;
- text digest: CRLF/CR -> LF, no trim;
- repo/service/environment lossless normalization from design v10;
- no fuzzy aliasing;
- artifact trust is execution metadata, not payload data;
- `caller_supplied`/`repository_file` never gate-trusted;
- `direct_child` only gate-trusted after trusted producer context + artifact validation;
- `runtime_validated` only when runtime retained the original trusted producer context;
- `assessment_context_trust` is runtime-owned; caller-supplied contexts collapse claimed authority to caller unless the child independently re-resolves the source; validated runtime handoffs preserve, never upgrade, authority.

Run tests; expected PASS.

Commit:

```bash
git add scripts/registry/assessment_target.py scripts/registry/artifact_trust.py \
  scripts/registry/artifact_contracts.py scripts/tests/test_assessment_target.py \
  scripts/tests/test_artifact_trust.py
git commit -m "feat: add assessment identity and artifact trust helpers"
```
### Execution checklist

- [ ] **Step 1: Add the RED assertions shown in this task before changing production behavior.** Use the exact test/fixture/API names defined in this task's interface and helper contracts.
- [ ] **Step 2: Run the focused test command.**

```bash
python3 -m pytest -p no:cacheprovider scripts/tests/test_artifact_contracts.py scripts/tests/test_composition_runtime.py scripts/tests/test_composition_contracts.py -q
```

Expected: FAIL because this task's new contract/behavior is not implemented yet; a missing unrelated dependency or pre-existing failure is not an acceptable RED signal.

- [ ] **Step 3: Implement the minimum production/registry/skill changes specified in this task.** Do not broaden scope beyond the exact interfaces and files named here.
- [ ] **Step 4: Run the same focused command again.** Expected: PASS. Then run any additional task-specific command already listed above.
- [ ] **Step 5: Review the task diff and commit only after the focused tests pass.**

```bash
git status --short
git diff --check
git add -A
git commit -m "feat: add canonical target digest and trust helpers"
```

---

## Task 4 — Add external `assessment_context` handoff carrier

**Interfaces:**
- Consumes: Task 3 trust/target helpers and composition runtime.
- Produces: external `assessment_context`, `resolve_embedded_inputs`, `validate_embedded_result_target`, validated runtime handoffs.


**Create:**
- `scripts/registry/embedded_context.py`

**Modify:**
- `skills.yaml`
- `scripts/registry/composition_runtime.py` only if the registered external-carrier validation requires a runtime-graph change
- `scripts/tests/test_composition_runtime.py`
- `scripts/tests/test_composition_contracts.py`
- `docs/skill-framework/shared/runtime-contract.md`

### RED

Add tests proving the existing runtime invariant and the new carrier:

```python
def test_system_design_blocks_on_machine_prd_summary_without_full_prd() -> None:
    result = resolve_embedded_inputs(
        target_skill="system-design",
        machine_artifact={"artifact_type": "prd_report", "payload": {"title": "Checkout", "build_readiness": "READY"}},
        document_content=None,
        document_ref=None,
    )
    assert result.status == "BLOCKED"
    assert result.missing == ["full_prd_content_or_ref"]

def test_architecture_review_blocks_on_machine_design_summary_without_design_body() -> None:
    result = resolve_embedded_inputs(
        target_skill="architecture-review",
        machine_artifact={"artifact_type": "system_design_spec", "payload": {"title": "Checkout", "readiness": "Ready to implement"}},
        document_content=None,
        document_ref=None,
    )
    assert result.status == "BLOCKED"
    assert result.missing == ["full_system_design_content_or_ref"]

def test_invoked_child_still_requires_registered_consumed_handoff_artifact() -> None:
    root = registry_fixture_with_raw_only_invoke_edge()
    errors = validate_composition_runtime(load_registry(root), root / "skills.yaml", root / "skills.yaml")
    assert any("handoff" in e and "consume" in e for e in errors)

def test_assessment_context_is_external_and_has_no_producer() -> None:
    manifest = load_manifest_with_assessment_context()
    assert "assessment_context" in manifest["contracts"]["platform"]["artifact_runtime"]["external_input_artifacts"]
    ownership = manifest["contracts"]["composition_runtime"]["artifact_ownership"]["assessment_context"]
    assert ownership == {"mode": "external", "owners": []}

def test_assessment_context_handoff_valid_when_target_consumes_it() -> None:
    root = registry_fixture_with_assessment_context_invoke_edge()
    assert validate_composition_runtime(load_registry(root), root / "skills.yaml", root / "skills.yaml") == []
def test_embedded_context_conflict_never_silently_prefers_top_level_input() -> None:
    result = resolve_embedded_inputs(
        execution_context={"parent_skill": "production-readiness-review"},
        assessment_context={"inputs": {"service_name": "payments"}},
        top_level={"service_name": "ledger"},
    )
    assert result.status in {"CONFLICTED", "BLOCKED"}

def test_child_result_target_must_match_handoff_target() -> None:
    expected = assessment_target(repo="github.com/acme/payments", head="a" * 40)
    actual = assessment_target(repo="github.com/acme/payments", head="b" * 40)
    assert validate_embedded_result_target(expected, actual) != []

def test_embedded_handoff_preserves_caller_input_authority() -> None:
    ctx = assessment_context(
        inputs={"rollback_plan": "always safe"},
        input_provenance={
            "rollback_plan": {"authority": "caller", "evidence_refs": ["caller:rollback"]}
        },
    )
    resolved = resolve_embedded_inputs(execution_context={"parent_skill": "production-readiness-review"}, assessment_context=ctx, top_level={})
    assert resolved.input_provenance["rollback_plan"]["authority"] == "caller"

def test_caller_context_cannot_self_claim_authoritative_host() -> None:
    ctx = assessment_context(
        inputs={"rollback_plan": "always safe"},
        input_provenance={
            "rollback_plan": {"authority": "authoritative_host", "evidence_refs": ["fake:host"]}
        },
    )
    trust = classify_assessment_context_trust(
        ctx,
        runtime_metadata={"acquisition": "caller_supplied", "parent_execution_validated": False},
    )
    assert trust.effective_authority("rollback_plan") == "caller"

def test_validated_runtime_handoff_preserves_but_does_not_upgrade_authority() -> None:
    ctx = assessment_context(
        inputs={"rollback_plan": "repo rollout config"},
        input_provenance={
            "rollback_plan": {"authority": "repository", "evidence_refs": ["repo:rollout"]}
        },
    )
    trust = classify_assessment_context_trust(
        ctx,
        runtime_metadata=_issue_runtime_handoff_metadata(
            parent_skill="production-readiness-review",
            trusted_authorities={"rollback_plan": "repository"},
        ),
    )
    assert trust.effective_authority("rollback_plan") == "repository"
```

Run RED and confirm the fixtures fail until the new external artifact is registered.

### GREEN

Register:

```yaml
assessment_context:
  fields:
    - assessment_target
    - inputs
    - input_provenance
    - evidence_refs
    - unresolved
```

Add it to external input artifacts and external ownership. Do **not** weaken `validate_composition_runtime()` to allow raw-only invoke edges. Document the embedded invocation shape:

```yaml
handoff:
  inputs:
    assessment_context:
      assessment_target:
        repo: github.com/acme/payments
        service: payments
        environment: production
        source_type: release_candidate
        base_revision: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
        head_revision_or_digest: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
        source_artifact_ref: release:payments
        source_artifact_digest: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
      inputs:
        service_name: payments
        observability_material: observability/
      input_provenance:
        service_name:
          authority: trusted_runtime
          evidence_refs: [impact:service]
        observability_material:
          authority: repository
          evidence_refs: [repo:observability]
      evidence_refs: [impact:service, repo:observability]
      unresolved: []
```

No skill consumes it in Foundation A yet; B1/B2 and new skills add consumption with their behavior changes.

Run targeted registry/runtime tests GREEN.

```bash
git add skills.yaml scripts/tests/test_composition_runtime.py scripts/tests/test_composition_contracts.py docs/skill-framework/shared/runtime-contract.md
git commit -m "feat: add assessment handoff context"
```
### Execution checklist

- [ ] **Step 1: Add the RED assertions shown in this task before changing production behavior.** Use the exact test/fixture/API names defined in this task's interface and helper contracts.
- [ ] **Step 2: Run the focused test command.**

```bash
python3 -m pytest -p no:cacheprovider scripts/tests/test_artifact_contracts.py scripts/tests/test_composition_runtime.py scripts/tests/test_composition_contracts.py -q
```

Expected: FAIL because this task's new contract/behavior is not implemented yet; a missing unrelated dependency or pre-existing failure is not an acceptable RED signal.

- [ ] **Step 3: Implement the minimum production/registry/skill changes specified in this task.** Do not broaden scope beyond the exact interfaces and files named here.
- [ ] **Step 4: Run the same focused command again.** Expected: PASS. Then run any additional task-specific command already listed above.
- [ ] **Step 5: Review the task diff and commit only after the focused tests pass.**

```bash
git status --short
git diff --check
git add -A
git commit -m "feat: add external assessment context handoff carrier"
```

---

## Task 5 — Remove registry-derived hard-coded counts

**Interfaces:**
- Consumes: canonical registry/eval loaders.
- Produces: registry-derived skill/scenario/golden coverage counts with no hard-coded global totals.


**Modify:**
- `scripts/tests/test_install_all_skills.sh`
- `scripts/tests/test_install_support.py`
- `scripts/tests/test_p1_runtime_manifest.py`
- `scripts/tests/test_platform_eval_contract.py`
- `scripts/tests/test_risk_class.py`
- `scripts/tests/test_batch3_eval_contract.py`
- `scripts/tests/test_batch3_scenario_harness.py`
- `scripts/tests/test_evals_tier3.py` only where count is registry-derived

### RED

Add a temporary-registry fixture that inserts a synthetic valid skill and proves count-based tests derive from registry membership rather than literals such as `34` or `170`.

Run targeted files; expected old exact-count assertions to fail.

### GREEN

Rules:

- skill total = `len(registry.skills)`;
- five-dimension total = `len(registry.skills) * len(REQUIRED_DIMENSIONS)`;
- retain an exact fixture count only where exact fixture inventory itself is the contract; document why.

Search after change:

```bash
grep -RInE '== *34|EXPECTED_SKILL_COUNT *= *34|== *170' scripts/tests || true
```

Expected: no registry-derived literals remain.

Commit:

```bash
git add scripts/tests
git commit -m "test: derive skill and eval counts from registry"
```
### Execution checklist

- [ ] **Step 1: Add the RED assertions shown in this task before changing production behavior.** Use the exact test/fixture/API names defined in this task's interface and helper contracts.
- [ ] **Step 2: Run the focused test command.**

```bash
python3 -m pytest -p no:cacheprovider scripts/tests/test_artifact_contracts.py scripts/tests/test_composition_runtime.py scripts/tests/test_composition_contracts.py -q
```

Expected: FAIL because this task's new contract/behavior is not implemented yet; a missing unrelated dependency or pre-existing failure is not an acceptable RED signal.

- [ ] **Step 3: Implement the minimum production/registry/skill changes specified in this task.** Do not broaden scope beyond the exact interfaces and files named here.
- [ ] **Step 4: Run the same focused command again.** Expected: PASS. Then run any additional task-specific command already listed above.
- [ ] **Step 5: Review the task diff and commit only after the focused tests pass.**

```bash
git status --short
git diff --check
git add -A
git commit -m "feat: remove registry derived hard coded counts"
```

---

## Task 6 — Document safe adversarial fixtures and finish Foundation A

**Interfaces:**
- Consumes: Tasks 1–5 complete.
- Produces: scanner-safe adversarial-fixture policy, updated shared docs, green repository gate.


**Modify:**
- `docs/skill-framework/README.md`
- `docs/README.md`
- `CHANGELOG.md`
- `scripts/registry/setup_freshness.yaml` if these docs are freshness-tracked
- generated projections only via generator

Document:

- committed golden fixtures must not contain randomized/realistic secret-shaped values;
- use well-known non-functional `...EXAMPLE` placeholders or clearly non-matching sentinels;
- do not add `.gitleaksignore` solely to silence a new fixture without policy approval;
- the actual secret-scanner negative fixture remains runtime-generated by `.github/workflows/secret-scan.yml`.

Generate:

```bash
make generate
make generate-check
```

Targeted verification:

```bash
python3 -m pytest -p no:cacheprovider \
  scripts/tests/test_artifact_contracts.py \
  scripts/tests/test_assessment_target.py \
  scripts/tests/test_artifact_trust.py \
  scripts/tests/test_batch3_scenario_harness.py \
  scripts/tests/test_batch3_eval_contract.py \
  scripts/tests/test_platform_eval_contract.py \
  scripts/tests/test_p1_runtime_manifest.py \
  scripts/tests/test_risk_class.py \
  scripts/tests/test_install_support.py \
  scripts/tests/test_evals_tier3.py -q
```

Full local gate:

```bash
make setup
make validate-registry
make validate-evals
make backfill-capabilities-drift-check
make validate-operational-upkeep
make generate-check
make verify-install-all
make doctor
make lint
```

After push, require GitHub workflows:

```text
Lint              success
Secret Scan       success
Dependency Review success
CodeQL             success
```

Do not merge Foundation A while Secret Scan is failing, even if the failure looks fixture-related.

Final review-size check:

```bash
base="$(git merge-base HEAD origin/main)"
git diff --stat "$base"...HEAD
git diff --name-only "$base"...HEAD | wc -l
```

If >40 changed files due only to generated/docs publication, split the no-behavior publication rather than weakening review-size policy.

Commit:

```bash
git add README.md docs CHANGELOG.md scripts/registry .cursor .kiro generated
git commit -m "docs: publish composition runtime foundation"
```

## Exit criteria

- zero P0/P1 findings in a fresh review;
- no durable artifact schema version has changed yet;
- `assessment_context` is registered as an external, producerless handoff artifact;
- raw-only invoke edges remain invalid;
- lifecycle is corrected;
- alternate state semantics feature is tested;
- target/digest/trust primitives exist;
- registry-derived count drift is removed;
- all required local and remote gates are green.
### Execution checklist

- [ ] **Step 1 (RED): Before generating or updating final docs/goldens, run `make generate-check`.** Expected: FAIL because earlier tasks changed canonical registry/contract sources while generated projections are intentionally still stale. If it passes unexpectedly, add the task-specific golden/docs assertion described above first and rerun the focused check; do not manufacture an unrelated failure.
- [ ] **Step 2: Add/update the documentation, eval, golden, and generated-contract assertions specified in this task, then run the task's targeted generation/eval checks.** Expected after the minimum task changes and `make generate`: PASS for the changed contract; unrelated baseline failures are not acceptable GREEN evidence.
- [ ] **Step 3: Apply only the docs/eval/generation changes specified above; run `make generate` only from canonical sources.**
- [ ] **Step 4: Run the task-specific checks above, then the full repository gate from this task.** Expected: PASS with no skipped required gate.
- [ ] **Step 5: Review `git status --short` and `git diff --check`; with only task-scoped files present, commit.**

```bash
git status --short
git diff --check
git add -A
git commit -m "docs: document safe adversarial fixtures and finish fo"
```
