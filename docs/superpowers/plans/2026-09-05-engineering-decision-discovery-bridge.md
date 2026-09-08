# Engineering Decision Discovery Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the explicit human-owned grilling and decision-frontier capability required to complete Matt-style candidate selection without allowing a host to synthesize approval or automatically refactor code.

**Architecture:** Add `engineering-decision-discovery` as a read-only ambient specialist with a typed `engineering_decision_record` v1 artifact. It receives a bounded candidate handoff from `codebase-architecture-review`, computes the current frontier of a decision tree, asks only prerequisite-safe questions, and returns `BLOCKED` when unattended execution lacks a human decision. It does not write ADRs or source code.

**Tech Stack:** Markdown skill package, YAML registry fragments, canonical `skills.yaml` generation, Python registry/artifact/eval validators, Tier-1/Tier-2/Tier-3 eval fixtures, six host projections.

**Spec:** `docs/superpowers/specs/2026-09-05-matt-architecture-parity-bridge.md` (R6–R9)

**Prerequisite:** Execute Child Plan A Task 1 before this plan. That task adds
the shared `event_order` and `event_data_equals` transcript assertions used by
the decision-frontier cases below.

## Global Constraints

- Facts belong to the skill; material decisions belong to the user unless authority is explicitly delegated.
- The skill is ambient, interactive, read-only, and report-only.
- No source, test, configuration, registry, ADR, commit, push, PR, or external post may be created by this skill.
- `ENGINEERING_DECISION_RECORD.md` is a report emitted for the session; no ADR is written automatically.
- Unresolved material decisions in an unattended composition return `BLOCKED` with the decision frontier.
- `codebase-architecture-review` retains `recommended_next_skill: null`; its handoff is a user-visible offer requiring a separate invocation.
- The decision tree separates prerequisite-dependent decisions from independent decisions.
- Every recommendation includes rationale and remains a recommendation until the user decides.
- Existing routing, artifact, host, prompt-injection, safe-output, and composition contracts remain authoritative.

---

### Task 1: Establish the RED decision-discovery baseline

**Files:**
- Create: `scripts/tests/test_engineering_decision_discovery.py`
- Create: `evals/transcripts/engineering-decision-discovery/decision-frontier.yaml`
- Create: `evals/golden/engineering-decision-discovery/decision-record.yaml`
- Create: `docs/superpowers/specs/2026-09-05-engineering-decision-discovery-red-baseline.md`

**Interfaces:**
- Consumes: current routing, the existing user-visible decision interaction contract, and the approved R6 requirements. It does not depend on another skill being installed.
- Produces: failing tests for dependent-question ordering, repository fact retrieval, recommendation/approval separation, unattended blocking, and bounded completion.

- [ ] **Step 1: Add failing registry/routing assertions.**

  Add tests that assert the following prompts select
  `engineering-decision-discovery`:

  ```python
  @pytest.mark.parametrize("prompt", [
      "Grill me on this architecture decision.",
      "Challenge my plan and question my assumptions.",
      "Stress-test this engineering decision.",
      "What decisions are missing before we implement this design?",
      "Help me decide between these module designs.",
  ])
  def test_decision_discovery_has_a_dedicated_owner(prompt: str) -> None:
      result = _dispatch(prompt)
      assert result.status == "selected", result
      assert result.owner == "engineering-decision-discovery"
  ```

  Define `_dispatch` in this test module with the same repository-root and
  `load_registry(ROOT)` setup used by
  `scripts/tests/test_codebase_architecture_foundation.py`; do not mock the
  routing resolver.

- [ ] **Step 2: Add failing transcript assertions.**

  Require this exact event ordering:

  ```yaml
  events:
    - type: tool
      name: repository_read
    - type: decision_frontier
      decisions: [D1]
    - type: recommendation
      decision: D1
      approved: false
    - type: human_decision
      decision: D1
    - type: decision_frontier
      decisions: [D2, D3]
    - type: recommendation
      decision: D2
    - type: recommendation
      decision: D3
    - type: outcome
      status: complete
  assertions:
    - type: event_order
      events: [repository_read, decision_frontier, recommendation, human_decision, decision_frontier]
    - type: tool_not_called
      name: repository_write
    - type: tool_not_called
      name: write_adr
    - type: event_data_equals
      event: recommendation
      path: approved
      value: false
  ```

  Add an unattended scenario requiring `BLOCKED` with an explicit unresolved
  frontier and no synthesized human decision.

- [ ] **Step 3: Run and record RED.**

  ```bash
  python3 -m pytest scripts/tests/test_engineering_decision_discovery.py -q
  python3 -m scripts.evals --skill engineering-decision-discovery
  ```

  Expected result: collection or assertions fail because the skill, route,
  artifact, and transcript support do not exist.

  Record exact command, date, current `HEAD`, failing test names, and messages
  in `docs/superpowers/specs/2026-09-05-engineering-decision-discovery-red-baseline.md`.

- [ ] **Step 4: Commit the RED baseline.**

  ```bash
  git add scripts/tests/test_engineering_decision_discovery.py evals/transcripts/engineering-decision-discovery/decision-frontier.yaml evals/golden/engineering-decision-discovery/decision-record.yaml docs/superpowers/specs/2026-09-05-engineering-decision-discovery-red-baseline.md
  git commit -m "test: add RED baseline for decision discovery"
  ```

### Task 2: Add the decision-discovery skill package

**Files:**
- Create: `engineering-decision-discovery/SKILL.md`
- Create: `engineering-decision-discovery/README.md`
- Create: `engineering-decision-discovery/SETUP.md`
- Create: `engineering-decision-discovery/CHANGELOG.md`
- Create: `engineering-decision-discovery/examples.md`
- Create: `engineering-decision-discovery/workflow/inputs.md`
- Create: `engineering-decision-discovery/workflow/tree.md`
- Create: `engineering-decision-discovery/workflow/frontier.md`
- Create: `engineering-decision-discovery/workflow/interaction.md`
- Create: `engineering-decision-discovery/workflow/report.md`
- Create: `engineering-decision-discovery/reference/phase-index.md`
- Create: `engineering-decision-discovery/reference/lazy-load-index.md`
- Create: `engineering-decision-discovery/reference/pressure-tests.md`
- Create: `engineering-decision-discovery/reference/report-format.md`
- Create: `engineering-decision-discovery/reference/smoke-test.md`
- Modify: `scripts/tests/test_engineering_decision_discovery.py`

**Interfaces:**
- Consumes: `decision_scope`, `repository_evidence`, optional selected candidate handoff, and user decisions.
- Produces: `ENGINEERING_DECISION_RECORD.md`, `engineering_decision_record` v1, a decision tree, current frontier, recommendations, resolved decisions, and explicit unresolved decisions.

- [ ] **Step 1: Write the compact skill contract.**

  The frontmatter and body must include this exact routing description:

  ```yaml
  ---
  name: engineering-decision-discovery
  description: >-
    Use when engineering decisions remain unresolved and need an interactive,
    evidence-backed challenge before design or implementation. Keywords: grill
    me, challenge my plan, stress-test this decision, question my assumptions,
    help me decide, what decisions are missing, interrogate this architecture.
    Not for reconstructing current domain behavior, reviewing a proposed
    architecture, or implementing an already-settled task.
  ---
  ```

  State that facts are retrieved by the skill, decisions belong to the user,
  and no unresolved decision may be silently approved.

- [ ] **Step 2: Define typed inputs and blocked behavior.**

  `workflow/inputs.md` must require a bounded decision scope and describe these
  inputs:

  ```yaml
  decision_scope:
    question: Should provider errors be translated at the charge module seam?
    context: src/payments/charge.py and its checkout callers, bounded to the current repository revision.
    selected_candidate:
      candidate_id: ARCH-001
      evidence_refs: [repo:src/payments/charge.py, repo:src/checkout/checkout.py]
  interaction_policy:
    human_available: true|false
    unattended: true|false
  ```

  Missing decision scope is `BLOCKED`. Missing optional repository evidence is
  an explicit gap, not a request for the user to fetch facts the host can read.

- [ ] **Step 3: Define the decision tree and frontier algorithm.**

  `workflow/tree.md` must define each decision node as:

  ```yaml
  id: D1
  question: Should provider errors be translated at the charge module seam?
  depends_on: []
  options:
    - id: A
      label: Translate at the charge seam
      rationale: Checkout callers currently branch on provider error codes; central translation reduces caller knowledge.
  status: unresolved|resolved|not_applicable
  selected_option: null|A
  evidence_refs: [repo:src/payments/charge.py, repo:src/checkout/checkout.py]
  ```

  A node is on the frontier only when every `depends_on` node is resolved.
  Independent nodes may share a frontier. A dependent node must never be
  asked in the same round as an unresolved prerequisite.

- [ ] **Step 4: Define interaction and ownership rules.**

  `workflow/frontier.md` and `workflow/interaction.md` must require:

  1. compute the current frontier;
  2. ask only frontier questions;
  3. provide a recommended option and rationale for each;
  4. ask the user to decide, without treating the recommendation as approval;
  5. record the decision and recompute the tree; and
  6. return `BLOCKED` in unattended mode if a material frontier remains.

  The skill must stop after all material decisions are resolved or the user
  explicitly leaves the frontier unresolved. It must not conduct an infinite
  interview.

- [ ] **Step 5: Define the report-only output.**

  `workflow/report.md` and `reference/report-format.md` must require:

  - settled decisions only in `resolved_decisions`;
  - unresolved frontier in `unresolved_decisions`;
  - recommendation and rationale for every asked question;
  - evidence provenance and confidence;
  - explicit human decision ownership;
  - no ADR write; and
  - `ENGINEERING_DECISION_RECORD.md` emitted without source mutation.

- [ ] **Step 6: Run skill contract tests.**

  ```bash
  python3 -m pytest scripts/tests/test_engineering_decision_discovery.py -q
  ```

  Expected result: the package-level assertions pass once the registry wiring
  from Task 3 is complete; keep the test focused on skill text and workflow
  invariants here.

- [ ] **Step 7: Commit the skill package.**

  ```bash
  git add engineering-decision-discovery/ scripts/tests/test_engineering_decision_discovery.py
  git commit -m "feat: add engineering decision discovery skill"
  ```

### Task 3: Register artifact, skill, routing, and composition contracts

**Files:**
- Create: `scripts/registry/skills.d/engineering-decision-discovery.yaml`
- Generated: `scripts/registry/composition_contracts.yaml` via `make generate`
- Generated: `scripts/registry/composition_runtime.yaml` via `make generate`
- Generated: `scripts/registry/degraded_behavior.yaml` via `make generate`
- Generated: `scripts/registry/routing_rules.yaml` via `make generate`
- Modify: `skills.yaml`
- Generated by: `make generate` after the fragment is added; do not hand-edit its derived per-skill rows
- Modify: `scripts/tests/test_engineering_decision_discovery.py`
- Modify: `docs/skill-framework/shared/cross-skill-escalation.md`
- Modify: `docs/skill-framework/shared/skill-routing.md`

**Interfaces:**
- Consumes: existing `read-only-leaf-review` profile and current routing/composition schemas.
- Produces: a `leaf` ambient skill with no invokes, optional escalations, `engineering_decision_record` ownership, and deterministic grill-me routing.

- [ ] **Step 1: Add the registry fragment.**

  Use this exact contract shape:

  ```yaml
  engineering-decision-discovery:
    path: engineering-decision-discovery
    category: architecture
    extends: read-only-leaf-review
    install:
      requires: []
    composition:
      invokes: []
      escalation_targets:
      - module-design
      - architecture-review
    capabilities:
      required:
      - host.report.write
      - host.repository.read
      optional: []
    lint:
      skill_md_max_lines: 180
      target: engineering-decision-discovery
    version: 1.0.0
    type: leaf
    permissions:
      repository: read
      external_actions: none
      unattended: false
      merge: false
    output_contract:
      produces:
      - engineering_decision_record
      produce_fields:
        engineering_decision_record:
        - title
        - decision_scope
        - decision_tree
        - frontier
        - recommendations
        - resolved_decisions
        - unresolved_decisions
        - alternatives_rejected
        - limitations
    dependencies: []
    degraded_behavior:
      missing_capability: host.repository.read
      available_capabilities:
      - host.report.write
      behavior: BLOCKED
    setup_freshness:
      external_services: None — reads repository and caller-provided context only
    routing:
      patterns:
      - \b(grill me|challenge my plan|stress[- ]test this decision|question my assumptions|help me decide|what decisions are missing|interrogate this architecture)\b
      exclude_patterns:
      - \b(PR|MR|pull request|merge request)\s*[#!]?\d+\b
  ```

  Adjust only formatting required by the canonical registry schema; do not
  add a parallel taxonomy or unregistered capability.

- [ ] **Step 2: Add the artifact schema.**

  In the authored contract sections of `skills.yaml`, add
  `engineering_decision_record` to `durable_artifacts`, set
  `artifact_schema_versions.engineering_decision_record: 1`, set
  `state_semantics.engineering_decision_record: desired_state`, allow only
  `desired_state`, and add the following payload types:

  ```yaml
  engineering_decision_record:
    title: string
    decision_scope: mapping
    decision_tree: list
    frontier: list
    recommendations: list
    resolved_decisions: list
    unresolved_decisions: list
    alternatives_rejected: list
    limitations: list
  ```

  Add the matching `composition` contract entry with producer
  `engineering-decision-discovery`, no consumers, and the nine listed
  `produce_fields`. Add the matching `composition_runtime.artifact_ownership`
  entry with `mode: canonical`, `owners: [engineering-decision-discovery]`,
  and `delegates: []`. Keep nested decision-node semantic validation in the
  skill until a durable consumer requires a separately versioned validator.

- [ ] **Step 3: Add the handoff edge without automatic dispatch.**

  Add `codebase-architecture-review → engineering-decision-discovery` to the
  cross-skill matrix as a human-visible optional offer carrying:

  ```yaml
  selected_candidate:
    candidate_id: ARCH-001
    scope: [src/payments/charge.py, src/checkout/checkout.py]
    evidence_refs: [repo:src/payments/charge.py, repo:src/checkout/checkout.py]
    unresolved_questions: [Should provider errors be translated at the charge module seam?]
  ```

  Also document the two declared receiving escalations as optional rows:
  `engineering-decision-discovery → module-design` for a settled module seam
  and `engineering-decision-discovery → architecture-review` for a settled
  architecture-wide trade-off. These rows are required because every
  `composition.escalation_targets` edge must appear in the symmetric matrix.
  Do not set `recommended_next_skill` in the architecture artifact and do not
  add any of these edges to `composition.invokes`.

- [ ] **Step 4: Regenerate and validate.**

  ```bash
  make generate
  make generate-check
  make validate-registry
  make validate-agent-skills
  make validate-hosts
  ```

  Expected result: the new skill is present in all required registry and
  generated surfaces, has no composition cycle, and retains six-host parity.

- [ ] **Step 5: Commit registry wiring.**

  ```bash
  git diff --name-only
  git add scripts/registry/skills.d/engineering-decision-discovery.yaml \
    scripts/registry/composition_contracts.yaml scripts/registry/composition_runtime.yaml \
    scripts/registry/degraded_behavior.yaml scripts/registry/routing_rules.yaml skills.yaml \
    docs/skill-framework/shared/cross-skill-escalation.md docs/skill-framework/shared/skill-routing.md \
    README.md docs/README.md docs/REPOSITORY.md \
    docs/agent-compatibility.md docs/skill-framework/shared/mcp-error-handling.md \
    make/generated-roster.mk \
    generated/catalogue/compatibility-matrix.md generated/catalogue/composition-deps.mmd \
    generated/catalogue/install-deps.mmd generated/catalogue/composition-runtime.mmd \
    .cursor/rules/engineering-decision-discovery.mdc \
    .kiro/steering/engineering-decision-discovery.md
  git commit -m "feat: register engineering decision discovery contracts"
  ```

  Stage a listed generated path only when it appears in the preceding diff;
  unrelated generated drift is not part of this commit.

### Task 4: Add decision-discovery eval admission

**Files:**
- Create: `evals/fixtures/engineering-decision-discovery/contract.yaml`
- Modify: `evals/transcripts/engineering-decision-discovery/decision-frontier.yaml`
- Create: `evals/transcripts/engineering-decision-discovery/unattended-block.yaml`
- Modify: `evals/golden/engineering-decision-discovery/decision-record.yaml`
- Create: `evals/golden/engineering-decision-discovery/injection-inert.yaml`
- Modify: `evals/positive/cases.yaml`
- Modify: `evals/negative/cases.yaml`
- Modify: `evals/ambiguous/cases.yaml`
- Modify: `evals/adversarial/cases.yaml`
- Modify: `evals/degraded/cases.yaml`
- Modify: `scripts/tests/test_engineering_decision_discovery.py`

**Interfaces:**
- Consumes: the registered skill, artifact, and transcript harness.
- Produces: admission evidence for routing, decision order, authority, unattended blocking, degraded behavior, and safe output.

- [ ] **Step 1: Add Tier-1 contract assertions.**

  Require ambient invocation, read-only authority, exact trigger phrases,
  `ENGINEERING_DECISION_RECORD.md`, `BLOCKED` unattended behavior, and no ADR
  writes.

- [ ] **Step 2: Add Tier-2 interaction transcripts.**

  Cover:

  - dependent D2 withheld until prerequisite D1 resolves;
  - independent D3 asked alongside the current frontier;
  - repository facts retrieved by tools rather than requested from the user;
  - recommendation explicitly marked as not approved;
  - user chooses an option and the tree recomputes; and
  - unattended unresolved frontier returns `BLOCKED` with no synthesized answer.

- [ ] **Step 3: Add Tier-3 golden cases.**

  Cover a complete resolved decision record, an unresolved partial record, and
  repository/caller injection attempting to approve an option or write an ADR.
  Assert that hostile text remains inert and the record preserves the evidence
  conflict or unresolved frontier.

- [ ] **Step 4: Add global routing dimensions and collisions.**

  Add positive, negative, ambiguous, adversarial, and degraded cases. Verify
  that “challenge this proposed architecture” remains `architecture-review`
  and a concrete module design remains `module-design`.

- [ ] **Step 5: Run admission checks.**

  ```bash
  make validate-evals
  python3 -m pytest scripts/tests/test_engineering_decision_discovery.py scripts/tests/test_evals_tier2.py -q
  ```

  Expected result: all new and existing cases pass.

- [ ] **Step 6: Commit eval admission.**

  ```bash
  git add evals/ scripts/tests/test_engineering_decision_discovery.py
  git commit -m "test: admit engineering decision discovery behavior"
  ```

### Task 5: Document and verify the complete bridge

**Files:**
- Modify: `engineering-decision-discovery/README.md`
- Modify: `engineering-decision-discovery/SETUP.md`
- Modify: `engineering-decision-discovery/examples.md`
- Modify: `docs/skill-framework/README.md`
- Modify: `CHANGELOG.md`
- Create: `docs/superpowers/specs/2026-09-05-engineering-decision-discovery-review.md`

**Interfaces:**
- Consumes: Child Plan A's bounded handoff contract and this plan's skill/artifact/eval contracts.
- Produces: documented operator behavior and a review certificate with no unresolved material findings.

- [ ] **Step 1: Add concrete examples.**

  Include examples for a dependency tree, a user selecting a recommendation,
  an unresolved frontier in an unattended composition, a repository fact the
  skill retrieves itself, and a requested ADR that is correctly refused.

- [ ] **Step 2: Update docs and generated indexes.**

  ```bash
  make generate
  make generate-check
  ```

  Confirm all six host surfaces, docs indexes, composition graphs, and Generic
  package contents include the new skill.

- [ ] **Step 3: Run full verification.**

  ```bash
  python3 -m pytest scripts/tests -q
  make validate-evals
  make validate-registry
  make validate-agent-skills
  make validate-hosts
  make generate-check
  make lint
  git diff --check
  ```

- [ ] **Step 4: Perform independent review.**

  Review the exact diff through product/capability, catalog architecture,
  routing/composition, authority/security, evidence/artifacts, eval TDD, and
  YAGNI lenses. Fix each material finding and rerun the affected test plus the
  full verification set. The review record must end with zero unresolved
  material findings.

- [ ] **Step 5: Commit the review record.**

  ```bash
  git add engineering-decision-discovery/README.md engineering-decision-discovery/SETUP.md engineering-decision-discovery/examples.md docs/skill-framework/README.md CHANGELOG.md docs/superpowers/specs/2026-09-05-engineering-decision-discovery-review.md
  git commit -m "docs: verify engineering decision discovery bridge"
  ```

## Spec-to-task traceability

| Requirement | Implemented by | Verified by |
|---|---|---|
| R6 human decision ownership | Tasks 2–4 | frontier, interaction, and unattended-block transcripts |
| R7 decision artifact compatibility | Task 3 | artifact contract and ownership validators |
| R8 eval admission | Task 4 | Tier-1/Tier-2/Tier-3 and routing dimensions |
| R9 host and packaging parity | Tasks 3 and 5 | generated projections, host validation, Generic package check |
