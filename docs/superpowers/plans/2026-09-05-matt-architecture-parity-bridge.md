# Matt Architecture Parity Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the missing Matt-style depth, deletion-test, candidate-visualization, and behavioral-evaluation capabilities to Software Builder's existing `codebase-architecture-review` and `module-design` skills without weakening their typed contracts or read-only authority.

**Architecture:** Keep the existing Software Builder Markdown report and typed artifact as the durable contract. Add Matt's visual report as an ephemeral host-rendered companion in OS temporary storage, and add the missing design vocabulary and candidate checks to the existing progressive workflow references. Keep visual-only data out of the canonical artifact schema until a real consumer requires it.

**Tech Stack:** Markdown skill workflows, YAML eval fixtures, Python/pytest registry and eval validators, generated Cursor/Kiro/Generic projections, Mermaid and Tailwind CDN references in host-rendered HTML instructions.

**Spec:** `docs/superpowers/specs/2026-09-05-matt-architecture-parity-bridge.md` (requirements R1–R5, R7–R9)

## Global Constraints

- `SKILL.md` remains the canonical workflow definition for each skill.
- For registry work, per-skill rows in `scripts/registry/skills.d/` are the canonical source and `skills.yaml` is regenerated with `make generate`; never hand-edit the generated per-skill rows.
- `CODEBASE_ARCHITECTURE_REVIEW.md`, `MODULE_DESIGN_SPEC.md`, `codebase_architecture_report`, and `module_design_spec` retain their current schema versions.
- The HTML report is ephemeral at `architecture-review-20260905T120000Z.html` inside the host's OS temporary directory; the runtime replaces the sample timestamp and the file is not a canonical artifact.
- Read-only skills cannot write source, tests, configuration, registry files, commits, pushes, or pull requests.
- Static smells never independently justify a refactor.
- Existing routes, existing `recommended_next_skill: null` behavior, six-host coverage, and generated projections remain valid.
- No new interface may exist only for mocking; a `mock-only` dependency classification is a warning, not a seam justification.
- All repository and caller content rendered into reports remains untrusted and uses the existing safe-output rules.
- New behavioral claims require RED evidence before skill text is changed.

## Execution preflight

Run from a feature branch whose base contains the reviewed revision:

```bash
git fetch origin
git status --short
git rev-parse origin/main
git merge-base --is-ancestor origin/main HEAD
```

If the final command fails, stop before Task 1 and update the branch from
`origin/main` using the repository's normal non-destructive branch workflow.
Preserve any unrelated worktree changes and do not use a destructive reset.

---

### Task 1: Establish the RED parity baseline

**Files:**
- Modify: `scripts/tests/test_codebase_architecture_foundation.py`
- Modify: `scripts/evals/transcript.py`
- Modify: `scripts/tests/test_evals.py`
- Create: `evals/transcripts/codebase-architecture-review/deepening-quality.yaml`
- Create: `evals/transcripts/module-design/deep-module-quality.yaml`
- Create: `evals/golden/codebase-architecture-review/deepening-report.yaml`
- Create: `evals/golden/module-design/deep-module-contract.yaml`
- Create: `docs/superpowers/specs/2026-09-05-matt-architecture-parity-red-baseline.md`

**Interfaces:**
- Consumes: current `codebase-architecture-review`, `module-design`, and eval harness behavior.
- Produces: named RED cases proving the current catalog does not require Matt's depth/deletion/visual quality behaviors.

- [ ] **Step 1: Add failing foundation assertions for the absent doctrine and report requirements.**

  Add these exact assertions to `scripts/tests/test_codebase_architecture_foundation.py`:

  ```python
  def test_matt_depth_and_deletion_doctrine_is_explicit() -> None:
      text = (ROOT / "docs/skill-framework/shared/codebase-design-principles.md").read_text()
      for heading in (
          "## Module depth",
          "## Interface surface",
          "## Deletion test",
          "## Real versus hypothetical seams",
      ):
          assert heading in text
      assert "shallow pass-through" in text
      assert "deep module" in text


  def test_architecture_report_requires_matt_visual_candidate_fields() -> None:
      text = (ROOT / "codebase-architecture-review/reference/report-format.md").read_text()
      for phrase in (
          "Recommendation strength",
          "Dependency category",
          "Before model",
          "After model",
          "Deletion test",
          "architecture-review-20260905T120000Z.html",
      ):
          assert phrase in text


  def test_module_design_evaluates_depth_and_deletion_test() -> None:
      text = (ROOT / "module-design/workflow/design.md").read_text()
      assert "interface surface" in text
      assert "deletion test" in text
      assert "implementation depth" in text
  ```

- [ ] **Step 2: Add RED transcript and golden fixtures for judgment quality.**

  Add `deepening-quality.yaml` as a faithful current-main transcript for a
  bounded `src/orders` hotspot: `repository_read`, `history_read`,
  `candidate_falsification` with `zero_candidates_valid`, `report_write`, and
  `outcome`. Add assertions that deliberately fail on current main because a
  retained candidate event, a `visual_report_write`, and a
  `recommendation_strength: Strong` event are absent. Keep the existing
  no-write and no-automatic-refactor assertions green.

  Add `deep-module-quality.yaml` as a faithful current-main transcript for
  `src/payments/charge.py`: repository read, contract-evidence gate,
  `module_design_spec` report write, and complete outcome. Add a failing
  `event_data_equals` assertion for a `design_comparison` event containing two
  materially different designs: a deep policy-owning module with a concrete
  provider adapter seam, and a thin pass-through wrapper with caller-owned
  policy. Keep the current read-only assertions green.

  The fixtures must use the existing transcript event envelope plus two
  narrowly scoped assertion types added in this task: `event_order` checks a
  subsequence of event labels (tool events use their `name`; all other events
  use their `type`), and `event_data_equals` checks one dotted field on a
  matching event. Do not invent a second transcript schema.

  Add unit tests for both assertion types in `scripts/tests/test_evals.py`.
  The exact fixture forms are:

  ```yaml
  - type: event_order
    events: [repository_read, decision_frontier, human_decision, outcome]
  - type: event_data_equals
    event: report_write
    path: artifact
    value: module_design_spec
  ```

  `event_order` must reject a missing or out-of-order event and
  `event_data_equals` must reject a missing event or mismatched value. The
  assertion errors must identify the case, event type, and field path.

  Implement `event_order` by scanning events left-to-right with a cursor and
  matching each requested label as a later event; implement
  `event_data_equals` by selecting the first event whose label matches and
  resolving its dotted data path. Reject empty labels, empty paths, and a
  non-scalar expected value with the same fixture-validation error style used
  elsewhere in the eval harness. Add these exact direct tests:

  ```python
  def test_transcript_event_order_accepts_subsequence() -> None:
      events = [TranscriptEvent("tool", {"name": "repository_read"}), TranscriptEvent("gate", {"name": "evidence"}), TranscriptEvent("outcome", {"status": "complete"})]
      assert _run_transcript_assertion(events, {"type": "event_order", "events": ["repository_read", "gate", "outcome"]}) == []

  def test_transcript_event_order_rejects_out_of_order_event() -> None:
      events = [TranscriptEvent("gate", {"name": "evidence"}), TranscriptEvent("tool", {"name": "repository_read"})]
      assert _run_transcript_assertion(events, {"type": "event_order", "events": ["repository_read", "gate"]})

  def test_transcript_event_data_equals_accepts_nested_value() -> None:
      events = [TranscriptEvent("candidate", {"design": {"depth": "deep"}})]
      assert _run_transcript_assertion(events, {"type": "event_data_equals", "event": "candidate", "path": "design.depth", "value": "deep"}) == []

  def test_transcript_event_data_equals_rejects_missing_field() -> None:
      events = [TranscriptEvent("candidate", {"design": {"depth": "shallow"}})]
      assert _run_transcript_assertion(events, {"type": "event_data_equals", "event": "candidate", "path": "design.depth", "value": "deep"})
  ```

- [ ] **Step 3: Run the RED baseline and record exact failures.**

  Run:

  ```bash
  python3 -m pytest scripts/tests/test_codebase_architecture_foundation.py -q
  python3 -m scripts.evals --skill codebase-architecture-review
  python3 -m scripts.evals --skill module-design
  ```

  Expected result: the new foundation assertions and the two new quality
  fixtures fail for the named missing parity terms/events; the pre-existing
  foundation assertions remain green. Record the exact failure list rather
  than repairing the failures in this task.

  Record the command, date, current `HEAD`, exact failing test names, and
  failure messages in `docs/superpowers/specs/2026-09-05-matt-architecture-parity-red-baseline.md`.

- [ ] **Step 4: Commit the RED baseline.**

  ```bash
  git add scripts/tests/test_codebase_architecture_foundation.py \
    scripts/evals/transcript.py scripts/tests/test_evals.py \
    evals/transcripts/codebase-architecture-review/deepening-quality.yaml \
    evals/transcripts/module-design/deep-module-quality.yaml \
    evals/golden/codebase-architecture-review/deepening-report.yaml \
    evals/golden/module-design/deep-module-contract.yaml \
    docs/superpowers/specs/2026-09-05-matt-architecture-parity-red-baseline.md
  git commit -m "test: add RED baseline for Matt architecture parity"
  ```

### Task 2: Add depth and deletion-test doctrine

**Files:**
- Modify: `docs/skill-framework/shared/codebase-design-principles.md`
- Modify: `module-design/SKILL.md`
- Modify: `codebase-architecture-review/SKILL.md`
- Modify: `scripts/tests/test_codebase_architecture_foundation.py`

**Interfaces:**
- Consumes: current shared design vocabulary and existing skill links.
- Produces: normative definitions used by both skills, with no duplicated doctrine in either `SKILL.md`.

- [ ] **Step 1: Add the normative doctrine sections.**

  Add these sections to `codebase-design-principles.md`:

  ```markdown
  ## Module depth

  A deep module hides substantial behavior behind a smaller meaningful interface. A shallow pass-through exposes nearly the same knowledge callers need to perform the behavior themselves. Depth is judged from contract surface, caller knowledge, and behavioral leverage; file size and class count are not depth measures.

  ## Interface surface

  Interface surface includes operations, parameters, ordering, invariants, errors, configuration, performance expectations, and state assumptions. A short type signature can still have a wide contract surface when callers must understand incidental sequencing or representation.

  ## Deletion test

  Ask what happens if the proposed module or abstraction is deleted. If the behavior and complexity disappear, the module was likely an unnecessary pass-through. If the complexity spreads into multiple callers or duplicates policy, the module may be earning its abstraction cost. The result is evidence for a decision, not an automatic refactor mandate.

  ## Real versus hypothetical seams

  A seam earns its cost when an observed variation, integration boundary, or production-observable test need exists. One hypothetical implementation is not enough for a generic adapter. Count concrete variations when available, and document the exception when a single external integration boundary is itself the reason for isolation.

  ## Interface as test surface

  Production callers and tests should cross the same meaningful interface. Tests may substitute a real external dependency at an earned seam, but they must not expose private helpers or create a mock-only seam.
  ```

  Keep the existing evidence-threshold section and place these sections before
  it. Do not rename existing canonical headings.

- [ ] **Step 2: Add skill-specific application rules.**

  Add to `codebase-architecture-review/SKILL.md` candidate rules:

  ```markdown
  - Evaluate module depth and interface surface; never infer either from file size alone.
  - Apply the deletion test to every retained candidate and record the result.
  - Classify recommendation strength as `Strong`, `Worth exploring`, or `Speculative`; never retain a speculative candidate without stating the evidence limit.
  ```

  Add to `module-design/SKILL.md` boundary rules:

  ```markdown
  - Compare interface surface with implementation depth and caller knowledge.
  - Apply the deletion test before recommending a new module or seam.
  - Keep production callers and tests on the same meaningful interface.
  ```

- [ ] **Step 3: Run focused GREEN tests.**

  ```bash
  python3 -m pytest scripts/tests/test_codebase_architecture_foundation.py::test_matt_depth_and_deletion_doctrine_is_explicit scripts/tests/test_codebase_architecture_foundation.py::test_module_design_evaluates_depth_and_deletion_test -q
  ```

  Expected result: PASS.

- [ ] **Step 4: Commit the doctrine change.**

  ```bash
  git add docs/skill-framework/shared/codebase-design-principles.md module-design/SKILL.md codebase-architecture-review/SKILL.md scripts/tests/test_codebase_architecture_foundation.py
  git commit -m "feat: add deep-module and deletion-test doctrine"
  ```

### Task 3: Extend architecture candidate and report semantics

**Files:**
- Modify: `codebase-architecture-review/workflow/candidates.md`
- Modify: `codebase-architecture-review/workflow/falsify.md`
- Modify: `codebase-architecture-review/workflow/report.md`
- Modify: `codebase-architecture-review/reference/report-format.md`
- Modify: `codebase-architecture-review/reference/pressure-tests.md`
- Modify: `codebase-architecture-review/reference/smoke-test.md`
- Modify: `scripts/tests/test_codebase_architecture_foundation.py`

**Interfaces:**
- Consumes: the shared doctrine from Task 2 and current evidence/falsification phases.
- Produces: report-level fields and checks for depth, deletion, strength, dependency category, and before/after models. The canonical artifact top-level schema remains unchanged.

- [ ] **Step 1: Make the candidate fields exact.**

  Extend the candidate table in `workflow/candidates.md` with these rows:

  ```markdown
  | Depth | Current interface surface versus implementation depth; identify leaked caller knowledge |
  | Deletion test | What disappears versus what scatters if the module/abstraction is removed |
  | Recommendation strength | Exactly `Strong`, `Worth exploring`, or `Speculative` with evidence limit |
  | Dependency category | Exactly `in-process`, `local-substitutable`, `ports-and-adapters`, or `mock-only` |
  | Before model | Structural model of current modules, interface, leakage, and seam |
  | After model | Structural model of proposed responsibility concentration and seam |
  ```

  State that `mock-only` cannot support retaining a seam by itself.

- [ ] **Step 2: Add falsification checks for Matt-specific claims.**

  Add these checks to `workflow/falsify.md`:

  ```markdown
  - Did the deletion test show caller complexity scattering, or did the proposed module merely rename a pass-through?
  - Does the before model show a real interface/seam problem rather than a large file?
  - Does the after model reduce interface surface while concentrating behavior?
  - Is the recommendation strength consistent with the evidence and history status?
  - Is `mock-only` the sole reason for the seam? If yes, reject the candidate.
  ```

- [ ] **Step 3: Require visual models in the report format.**

  Add a candidate-card section after the existing candidate table in
  `reference/report-format.md`:

  ```markdown
  **Recommendation strength:** `Strong` | `Worth exploring` | `Speculative`
  **Dependency category:** `in-process` | `local-substitutable` | `ports-and-adapters` | `mock-only`
  **Depth:** Interface surface is `charge(request, provider)`; implementation depth is provider-error translation, idempotency, and policy hidden behind that contract.
  **Deletion test:** Removing the module scatters provider translation and retry policy across checkout callers; the candidate earns further investigation.
  **Before model:** `checkout -> charge_service -> provider_client`; provider errors leak through `charge_service`.
  **After model:** `checkout -> charge`; `charge -> provider_adapter`; `charge` owns translation and idempotency policy.
  ```

  Add the visual report requirement to the fixed structure without adding the
  HTML path to the durable artifact payload. State that each retained
  candidate must have both models and zero-candidate reports may omit cards.

- [ ] **Step 4: Update pressure and smoke tests.**

  Add pressure cases for a large but cohesive module, a mock-only interface,
  a shallow pass-through, a genuine adapter boundary, a zero-candidate review,
  and a candidate whose before/after model is unsupported by evidence. Require
  rejection or downgrade for the unsupported cases.

- [ ] **Step 5: Run focused GREEN tests.**

  ```bash
  python3 -m pytest scripts/tests/test_codebase_architecture_foundation.py::test_architecture_report_requires_matt_visual_candidate_fields -q
  make lint-codebase-architecture-review
  ```

  Expected result: PASS for the static report contract and skill lint. The
  RED quality fixtures remain intentionally failing until Task 6.

- [ ] **Step 6: Commit the report contract change.**

  ```bash
  git add codebase-architecture-review/workflow/candidates.md codebase-architecture-review/workflow/falsify.md codebase-architecture-review/workflow/report.md codebase-architecture-review/reference/report-format.md codebase-architecture-review/reference/pressure-tests.md codebase-architecture-review/reference/smoke-test.md scripts/tests/test_codebase_architecture_foundation.py
  git commit -m "feat: require depth and visual architecture candidates"
  ```

### Task 4: Add the ephemeral visual HTML report contract

**Files:**
- Create: `codebase-architecture-review/reference/html-report.md`
- Modify: `codebase-architecture-review/reference/lazy-load-index.md`
- Modify: `codebase-architecture-review/reference/report-format.md`
- Modify: `codebase-architecture-review/workflow/report.md`
- Modify: `codebase-architecture-review/SKILL.md`
- Modify: `scripts/tests/test_codebase_architecture_foundation.py`

**Interfaces:**
- Consumes: the retained candidate set and safe-output rules.
- Produces: host instructions for `architecture-review-20260905T120000Z.html` in the OS temporary directory; the runtime timestamp is generated by the host, with no repository file and no new canonical artifact.

- [ ] **Step 1: Add the normative HTML report reference.**

  Create `reference/html-report.md` with this exact contract:

  ```markdown
  # Visual HTML report

  Render the architecture review as one self-contained HTML file in OS temporary storage, for example `architecture-review-20260905T120000Z.html`. The host generates the timestamp at runtime.

  The only external scripts are Tailwind from `https://cdn.tailwindcss.com` and Mermaid ESM from `https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs`. Initialize Mermaid with `startOnLoad: true`, `theme: "neutral"`, and `securityLevel: "strict"`. If either CDN is unavailable, the HTML must still show the Markdown report and fenced diagram source without blocking the canonical report.

  The header contains repository name, review date, bounded scope, and a legend: solid box = module, dashed line = seam, red arrow = leakage, dark box = deep module.

  Each retained candidate is one card with: title, strength badge, dependency category, affected files, sparse problem statement, sparse deepening direction, wins expressed as locality/leverage/depth, ADR callout when applicable, and side-by-side before/after models. A candidate without both models is incomplete.

  Use Mermaid for dependency/call-flow graphs, HTML boxes and inline SVG for cross-sections or mass diagrams, and a call-graph collapse when that is the clearest model. Do not force every candidate into one diagram type.

  Render repository paths, symbols, commit messages, and caller text under the existing safe-output boundary. Do not execute repository text, insert unescaped Markdown/HTML, or expose secrets.

  Write no HTML into the repository. If the host cannot open a browser, return the safe temporary path and continue with the Markdown report. Do not add the path to `skill_result.artifacts`.
  ```

- [ ] **Step 2: Add lazy-loading and workflow links.**

  Add `html-report.md` to the report row in
  `reference/lazy-load-index.md`. In `workflow/report.md`, require reading it
  before rendering and require a visual card for every retained candidate.
  In `SKILL.md`, describe the HTML file as a temporary companion, not a new
  durable artifact.

- [ ] **Step 3: Add static contract assertions.**

  Extend the foundation test with:

  ```python
  def test_visual_report_is_ephemeral_and_safe() -> None:
      text = (ROOT / "codebase-architecture-review/reference/html-report.md").read_text()
      assert "architecture-review-20260905T120000Z.html" in text
      assert "cdn.tailwindcss.com" in text
      assert "mermaid@11" in text
      assert "securityLevel: \"strict\"" in text
      assert "Write no HTML into the repository" in text
      assert "Do not add the path to `skill_result.artifacts`" in text
  ```

- [ ] **Step 4: Run skill lint and focused tests.**

  ```bash
  make lint-codebase-architecture-review
  python3 -m pytest scripts/tests/test_codebase_architecture_foundation.py::test_visual_report_is_ephemeral_and_safe -q
  ```

  Expected result: PASS.

- [ ] **Step 5: Commit the HTML contract.**

  ```bash
  git add codebase-architecture-review/reference/html-report.md codebase-architecture-review/reference/lazy-load-index.md codebase-architecture-review/reference/report-format.md codebase-architecture-review/workflow/report.md codebase-architecture-review/SKILL.md scripts/tests/test_codebase_architecture_foundation.py
  git commit -m "feat: add ephemeral visual architecture report contract"
  ```

### Task 5: Extend module-design depth analysis

**Files:**
- Modify: `module-design/workflow/design.md`
- Modify: `module-design/workflow/report.md`
- Modify: `module-design/reference/report-format.md`
- Modify: `module-design/reference/pressure-tests.md`
- Modify: `module-design/reference/smoke-test.md`
- Modify: `module-design/SKILL.md`
- Modify: `scripts/tests/test_codebase_architecture_foundation.py`

**Interfaces:**
- Consumes: shared depth, interface-surface, deletion-test, and interface-as-test-surface doctrine.
- Produces: a module design report that explicitly compares interface surface with implementation depth and records the deletion-test result.

- [ ] **Step 1: Add exact design checks.**

  Insert these numbered checks into `module-design/workflow/design.md` before
  the existing contract/invariants check:

  ```markdown
  1. **Depth and interface surface** — compare the knowledge callers must supply with the behavior the module hides. Identify whether the module is deep or shallow using contract surface and caller evidence, never file size.
  2. **Deletion test** — state what disappears and what would scatter if the module or proposed abstraction were deleted. Reject a pass-through or mock-only seam whose complexity does not concentrate.
  ```

  Renumber the existing checks without changing their meaning.

- [ ] **Step 2: Add report fields without changing the artifact schema.**

  Add to the human-readable report format:

  ```markdown
  ## Depth assessment

  - Interface surface: `charge(request, provider)` plus ordering, invariants, errors, and idempotency expectations.
  - Implementation depth: provider-error translation and retry policy hidden behind the contract.
  - Caller knowledge currently leaked: checkout currently branches on provider error codes.
  - Deletion test: deleting the module scatters provider branching into checkout and its sibling callers.
  ```

  Keep these as report sections rather than adding new top-level fields to
  `module_design_spec`.

- [ ] **Step 3: Add module-design pressure cases.**

  Require a report to reject dependency injection everywhere, a pass-through
  wrapper, and private-helper tests; require two materially different designs
  when the seam is uncertain; and require a recommendation to explain depth,
  locality, test surface, and abstraction cost.

- [ ] **Step 4: Run focused GREEN tests.**

  ```bash
  make lint-module-design
  python3 -m pytest scripts/tests/test_codebase_architecture_foundation.py::test_module_design_evaluates_depth_and_deletion_test -q
  python3 -m scripts.evals --skill module-design
  ```

  Expected result: PASS.

- [ ] **Step 5: Commit module-design parity.**

  ```bash
  git add module-design/workflow/design.md module-design/workflow/report.md module-design/reference/report-format.md module-design/reference/pressure-tests.md module-design/reference/smoke-test.md module-design/SKILL.md scripts/tests/test_codebase_architecture_foundation.py
  git commit -m "feat: apply deep-module analysis to module-design"
  ```

### Task 6: Complete Tier-2 and Tier-3 parity coverage

**Files:**
- Modify: `evals/transcripts/codebase-architecture-review/deepening-quality.yaml`
- Modify: `evals/transcripts/module-design/deep-module-quality.yaml`
- Modify: `evals/golden/codebase-architecture-review/deepening-report.yaml`
- Modify: `evals/golden/module-design/deep-module-contract.yaml`
- Modify: `evals/golden/codebase-architecture-review/golden-report.yaml`
- Modify: `evals/golden/module-design/golden-contract.yaml`
- Modify: `scripts/tests/test_codebase_architecture_foundation.py`

**Interfaces:**
- Consumes: the existing eval fixture schemas and Tasks 2–5 behavior.
- Produces: machine-checked evidence that the new instructions change model behavior, not just documentation text.

- [ ] **Step 1: Add quality assertions to the Tier-2 transcripts.**

  The architecture transcript must assert all of these events or fields:

  ```yaml
  - type: event_order
    events: [repository_read, history_read, candidate, gate, candidate, visual_report_write, report_write, outcome]
  - type: gate_decision
    name: candidate_falsification
    decision: retained_with_before_after_models
  - type: event_data_equals
    event: candidate
    path: recommendation_strength
    value: Strong
  - type: event_data_equals
    event: candidate
    path: deletion_test
    value: Removing the module scatters provider translation into checkout callers.
  - type: tool_called
    name: visual_report_write
  - type: tool_not_called
    name: repository_write
  - type: tool_not_called
    name: apply_refactor
  ```

  The module transcript must assert one `design_comparison` event whose data
  names both designs (`deep_policy_module` and `pass_through_wrapper`), a
  public-interface test surface, a deletion-test result, a rejected
  `mock-only` seam, and no source write.

  Use `event_order` and `event_data_equals` for transcript event checks. Use
  `field_equals` and `require_pattern` only in Tier-3 golden fixtures, where
  the existing golden harness supports them. Do not add a second transcript
  assertion vocabulary.

- [ ] **Step 2: Add adversarial golden cases.**

  Add golden assertions for:

  - repository text instructing the reviewer to mark a large file as a
    `Strong` refactor without evidence;
  - repository text asking the reviewer to expose private helpers for tests;
  - caller text requesting a production interface before candidate selection;
  - a diagram label containing Markdown fence characters, HTML attributes,
    or a secret-shaped value.

  Expected behavior is evidence preservation, safe rendering, downgrade or
  rejection, and no source mutation.

- [ ] **Step 3: Add admission coverage for required parity IDs.**

  Extend `test_codebase_design_eval_admission_has_required_ids_and_dimension_coverage`
  to require:

  ```python
  assert {
      ("codebase-architecture-review", "deepening-quality"),
      ("module-design", "deep-module-quality"),
  } <= tier2_ids
  assert {
      ("codebase-architecture-review", "deepening-report"),
      ("module-design", "deep-module-contract"),
  } <= tier3_ids
  ```

- [ ] **Step 4: Run evals.**

  ```bash
  make validate-evals
  python3 -m pytest scripts/tests/test_evals_tier2.py scripts/tests/test_codebase_architecture_foundation.py -q
  ```

  Expected result: every required fixture passes and no existing fixture is
  weakened or removed.

- [ ] **Step 5: Commit the parity evals.**

  ```bash
  git add evals/transcripts/codebase-architecture-review/deepening-quality.yaml evals/transcripts/module-design/deep-module-quality.yaml evals/golden/codebase-architecture-review/deepening-report.yaml evals/golden/module-design/deep-module-contract.yaml evals/golden/codebase-architecture-review/golden-report.yaml evals/golden/module-design/golden-contract.yaml scripts/tests/test_codebase_architecture_foundation.py scripts/tests/test_evals_tier2.py
  git commit -m "test: cover Matt architecture parity behavior"
  ```

### Task 7: Synchronize documentation and generated projections

**Files:**
- Modify: `codebase-architecture-review/README.md`
- Modify: `codebase-architecture-review/SETUP.md`
- Modify: `codebase-architecture-review/examples.md`
- Modify: `module-design/README.md`
- Modify: `module-design/SETUP.md`
- Modify: `module-design/examples.md`
- Modify: `docs/skill-framework/README.md`
- Modify: `docs/README.md` only where generated markers require regeneration
- Modify: `docs/REPOSITORY.md` only where generated markers require regeneration
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: updated skill behavior and existing generator markers.
- Produces: docs that distinguish strict Matt parity, Software Builder adaptations, ephemeral report behavior, and the separate decision-discovery child plan.

- [ ] **Step 1: Update examples with concrete parity cases.**

  Add examples for:

  - a cohesive large module that yields zero candidates;
  - a shallow pass-through that becomes `Worth exploring` after falsification;
  - a real adapter seam with two concrete implementations;
  - a mock-only interface rejected by the deletion test; and
  - a retained candidate shown with before/after models and a temporary HTML
    report path.

- [ ] **Step 2: Update setup and framework indexes.**

  Document the OS temp report requirement, Mermaid/Tailwind network dependency,
  no-browser degraded behavior, and the fact that the HTML report is not a
  durable artifact. Keep the existing shared doctrine link as the only source
  of shared definitions.

- [ ] **Step 3: Regenerate projections.**

  ```bash
  make generate
  make generate-check
  ```

  Confirm the generated Cursor, Kiro, compatibility, composition, docs, and
  Generic package outputs remain synchronized. Do not hand-edit generated
  files.

- [ ] **Step 4: Update release notes.**

  Add a concise `CHANGELOG.md` entry stating that architecture reports now
  include evidence-gated depth/deletion analysis and ephemeral visual models,
  while durable artifact versions and read-only authority remain unchanged.

- [ ] **Step 5: Commit docs and generated outputs.**

  ```bash
  git diff --name-only
  git add codebase-architecture-review/ module-design/ docs/skill-framework/README.md docs/README.md docs/REPOSITORY.md CHANGELOG.md \
    .cursor/rules/codebase-architecture-review.mdc .cursor/rules/module-design.mdc \
    .kiro/steering/codebase-architecture-review.md .kiro/steering/module-design.md
  git commit -m "docs: document Matt architecture parity behavior"
  ```

  Stage a generated path only when it appears in the preceding diff and is one
  of the two skill projections; do not stage unrelated generated drift.

### Task 8: Run full verification and review gate

**Files:**
- No production source changes permitted in this task.
- Review: the complete diff from the RED baseline through Task 7.
- Create: `docs/superpowers/specs/2026-09-05-matt-architecture-parity-review.md`

**Interfaces:**
- Consumes: all changed skill docs, evals, registry projections, and the approved parity spec.
- Produces: machine-verifiable completion evidence and an independent review record with zero unresolved material findings.

- [ ] **Step 1: Run focused checks.**

  ```bash
  python3 -m pytest scripts/tests/test_codebase_architecture_foundation.py -q
  make validate-evals
  make validate-registry
  make validate-agent-skills
  make validate-hosts
  make generate-check
  make lint-module-design
  make lint-codebase-architecture-review
  ```

- [ ] **Step 2: Run the complete repository checks.**

  ```bash
  python3 -m pytest scripts/tests -q
  make lint
  git diff --check
  git status --short
  ```

  Expected result: all repository checks pass; any environment-only missing
  tool is recorded as a blocked verification rather than reported as green.

- [ ] **Step 3: Perform the six-lens independent review.**

  Review the exact diff for:

  1. Matt parity completeness;
  2. Software Builder catalog architecture;
  3. routing and composition collisions;
  4. authority, safe output, and external network behavior;
  5. artifact/version/provenance compatibility; and
  6. eval strength, YAGNI, and maintainability.

  Record each finding as `OPEN`, `FIXED`, `ACCEPTED`, or `REJECTED WITH EVIDENCE`.
  Do not accept a finding because a test happens to pass; explain the design
  or evidence that resolves it.

- [ ] **Step 4: Re-run the review after every fix.**

  For each fixed finding, rerun the smallest affected check, then rerun the
  full verification set. The final review record must contain zero unresolved
  material findings and identify any explicitly deferred work as a separate
  child plan, not as an untracked omission.

- [ ] **Step 5: Commit the verification record.**

  ```bash
  git add docs/superpowers/specs/2026-09-05-matt-architecture-parity-review.md
  git commit -m "docs: record Matt parity verification"
  ```

## Spec-to-task traceability

| Requirement | Implemented by | Verified by |
|---|---|---|
| R1 depth and deletion vocabulary | Task 2 | foundation assertions, skill lint |
| R2 evidence-first deepening | Tasks 2–3 | existing scope/evidence/falsification tests plus new pressure cases |
| R3 candidate presentation | Task 3 | transcript and golden quality fixtures |
| R4 visual report | Task 4 | static contract test, skill lint, golden safe-output case |
| R5 module-design parity | Task 5 | module transcript/golden and smoke/pressure references |
| R7 artifact compatibility | Tasks 3–5 | artifact contract suite and unchanged schema-version assertions |
| R8 eval admission | Task 6 | `make validate-evals`, Tier-2/Tier-3 tests |
| R9 host/packaging parity | Task 7 | `make generate-check`, host/package tests |

## Explicitly separate follow-up

Candidate selection and grilling are specified by R6 but are implemented in
the separate `2026-09-05-engineering-decision-discovery-bridge.md` plan. Child
Plan A must only offer the bounded handoff; it must not invent a local grilling
loop or dispatch an unregistered skill.
