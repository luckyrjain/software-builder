# Unified Skill Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring pr-review, incident-rca, and k8s-overprovisioning-datadog into unified framework compliance per [2025-06-30-unified-skill-framework-design.md](../specs/2025-06-30-unified-skill-framework-design.md) — shared library, `make lint-framework`, and per-skill checklist §4.

**Architecture:** Four sequential phases: (1) expand shared docs + framework lint gate, (2) incident-rca largest compliance lift + Round 3 gaps, (3) k8s compliance + Round 3 gaps, (4) pr-review polish + Round 3 gaps. Each phase ends with `make lint` green for touched targets and updated pressure-test rows. Round 3 skill-specific gap tasks are defined in sibling plans and referenced here — do not duplicate; execute them as sub-plans within Phases 2–4.

**Tech Stack:** Markdown skill documents, root `Makefile`, optional `pytest` (pr-review scripts only). No runtime code changes in framework phases.

**Related sub-plans (execute within Phases 2–4):**
- [2026-06-30-rca-round3-gaps.md](./2026-06-30-rca-round3-gaps.md)
- [2026-06-30-k8s-round3-gaps.md](./2026-06-30-k8s-round3-gaps.md)
- [2026-06-30-pr-review-round3-gaps.md](./2026-06-30-pr-review-round3-gaps.md)

---

## File map (created or modified by this plan)

| Path | Phase | Responsibility |
|------|-------|----------------|
| `docs/skill-framework/shared/*.md` | 1 | Normative shared conventions (expand stubs) |
| `docs/skill-framework/README.md` | 1 | Index; flip Status table to Complete |
| `Makefile` | 1, 2 | `lint-framework`; optional SETUP link check in `lint-incident-rca` |
| `incident-rca/SKILL.md`, `SETUP.md`, `examples.md`, `reference/mcp-capabilities.md` | 2 | Framework links, examples depth, MCP matrix |
| `incident-rca/workflow/*.md`, `reference/pressure-tests.md` | 2 | Round 3 gaps (rca sub-plan) |
| `k8s-overprovisioning-datadog/reference/phase-index.md` | 3 | **Create** — ordered phase list |
| `k8s-overprovisioning-datadog/reference/lazy-load-index.md` | 3 | **Create** — mirror pr-review pattern |
| `k8s-overprovisioning-datadog/reference/smoke-test.md` | 3 | **Create** — extract from `workflow/render.md` |
| `k8s-overprovisioning-datadog/SKILL.md`, `SETUP.md`, `examples.md`, `reference/confidence-formula.md` | 3 | Framework links, cross-skill examples |
| `k8s-overprovisioning-datadog/workflow/*.md`, `reference/pressure-tests.md` | 3 | Round 3 gaps (k8s sub-plan) |
| `pr-review/SKILL.md`, `SETUP.md`, `reference/executive-summary.md` | 4 | Framework links, escalation dedup |
| `pr-review/workflow/*.md`, `reference/pressure-tests.md` | 4 | Round 3 gaps (pr-review sub-plan) |

---

## Phase 1 — Shared framework docs + `make lint-framework`

**Exit criteria:** All six `shared/*.md` files are normative (no "Stub outline" status); `make lint-framework` passes; README Status table shows Complete.

---

### Task 1: Expand `confidence-bands.md` to normative prose

**Files:**
- Modify: `docs/skill-framework/shared/confidence-bands.md`
- Modify: `docs/skill-framework/README.md` (Status row)

- [ ] **Step 1: Remove stub banner and add normative sections**

  Replace the file header and ensure §1–§7 from the design spec are present. After edits, the file MUST contain these sections (add missing prose):

  ```markdown
  # Confidence bands (shared)

  **Normative.** All three skills MUST use these four categorical bands only: HIGH, MEDIUM, LOW, UNKNOWN.

  ## 1. Purpose
  …

  ## 7. Anti-patterns

  | Anti-pattern | Correct behavior |
  |--------------|------------------|
  | Label HIGH after one Datadog query | Cap at MEDIUM; list gaps |
  | Emit numeric 0.9 without factor list | Include `arithmetic` / Reason bullets |
  | Use "Confident", "Likely", "Probably" | Map to MEDIUM or LOW with Reason |
  | pr-review High overall on truncated MR | Per-finding High allowed; overall may be Medium |
  ```

  Keep existing §2–§6 tables; expand §6 Display rules with one fenced example per skill.

- [ ] **Step 2: Verify no stub language remains**

  ```bash
  grep -i 'stub' docs/skill-framework/shared/confidence-bands.md && exit 1 || echo "ok"
  ```

- [ ] **Step 3: Commit**

  ```bash
  git add docs/skill-framework/shared/confidence-bands.md
  git commit -m "docs(framework): normative confidence-bands shared reference"
  ```

---

### Task 2: Expand `cross-skill-escalation.md`

**Files:**
- Modify: `docs/skill-framework/shared/cross-skill-escalation.md`

- [ ] **Step 1: Add full 3×3 forward matrix and reverse table**

  Ensure §1 matrix has all six forward paths from spec §5.2:
  - pr-review → incident-rca, pr-review → k8s
  - incident-rca → k8s, incident-rca → pr-review
  - k8s → incident-rca, k8s → pr-review

  Add a **User prompt template** column with one-line copy-paste prompts, e.g.:

  ```markdown
  | Trigger | From → To | Handoff artifact | User prompt template |
  |---------|-----------|------------------|----------------------|
  | Deploy regression confirmed | incident-rca → pr-review | Causative MR URL/IID + window | "Review MR !{iid} for deploy regression tied to {service} outage {window}" |
  ```

  §2 reverse escalations must include all three rows from spec (k8s 7d re-run, rca → pr-review, pr-review → k8s).

- [ ] **Step 2: Add §5 Canvas hint with skill-specific triggers**

  Copy canvas table from spec §5.2 item 6; link to canvas skill path `~/.cursor/skills-cursor/canvas/SKILL.md`.

- [ ] **Step 3: Remove stub banner; verify**

  ```bash
  grep -c 'From → To' docs/skill-framework/shared/cross-skill-escalation.md
  ```
  Expected: ≥6 data rows in forward matrix.

- [ ] **Step 4: Commit**

  ```bash
  git add docs/skill-framework/shared/cross-skill-escalation.md
  git commit -m "docs(framework): complete cross-skill escalation matrix"
  ```

---

### Task 3: Expand `post-action-templates.md`

**Files:**
- Modify: `docs/skill-framework/shared/post-action-templates.md`

- [ ] **Step 1: Add Jira ticket field table and confirmation gates**

  After §3, insert:

  ```markdown
  ### Jira ticket update fields

  | Field | incident-rca | pr-review | k8s |
  |-------|--------------|-----------|-----|
  | Labels | `rca-complete` | `mr-reviewed` | `rightsizing-ready` |
  | Priority | unchanged unless P1 outage | per blocking count | per REC severity |
  | Comment | §1 template | §2 template | §3 template |
  ```

  §7 Confirmation gates must state explicitly: pr-review Phase 3 gate; rca/k8s read-only (offer paste, never auto-post).

- [ ] **Step 2: Remove stub banner; commit**

  ```bash
  git add docs/skill-framework/shared/post-action-templates.md
  git commit -m "docs(framework): complete post-action templates"
  ```

---

### Task 4: Expand `smoke-test-conventions.md`

**Files:**
- Modify: `docs/skill-framework/shared/smoke-test-conventions.md`

- [ ] **Step 1: Add failure diagnosis table (§5 from spec)**

  Append after §4:

  ```markdown
  ## 5. Failure diagnosis

  | Symptom | Likely cause | Fix |
  |---------|--------------|-----|
  | Phase 0 shows all MCP ❌ | MCP server disconnected / auth | Re-auth; check Cursor MCP settings |
  | Smoke passes but pressure test fails | Edge case regression | Check `pressure-tests.md` row |
  | pytest fails in pr-review | Script change broke diff parser | `make lint-pr-review-scripts` |
  | k8s INV failure in smoke | Schema or template drift | `make lint-k8s-skill` |
  ```

- [ ] **Step 2: Remove stub banner; commit**

  ```bash
  git add docs/skill-framework/shared/smoke-test-conventions.md
  git commit -m "docs(framework): complete smoke-test conventions"
  ```

---

### Task 5: Expand `examples-conventions.md`

**Files:**
- Modify: `docs/skill-framework/shared/examples-conventions.md`

- [ ] **Step 1: Add invocation table template and wrong-skill row example**

  Insert after §1:

  ```markdown
  ### Invocation table template

  | # | User says | Resolves to | Notes |
  |---|-----------|-------------|-------|
  | 1 | "Review MR !123 in group/project" | pr-review Phase 0→5 | Happy path |
  | 8 | "Size my K8s deployment" | k8s skill (not pr-review) | Wrong-skill row |
  ```

- [ ] **Step 2: Remove stub banner; commit**

  ```bash
  git add docs/skill-framework/shared/examples-conventions.md
  git commit -m "docs(framework): complete examples conventions"
  ```

---

### Task 6: Expand `phase-glossary.md`

**Files:**
- Modify: `docs/skill-framework/shared/phase-glossary.md`

- [ ] **Step 1: Add cross-skill analogy table from spec §5.6**

  Verify §5 table includes row "MCP profile" and "Minimum evidence gate" (already in stub — expand with one-line descriptions per cell).

- [ ] **Step 2: Remove stub banner; commit**

  ```bash
  git add docs/skill-framework/shared/phase-glossary.md
  git commit -m "docs(framework): complete phase glossary"
  ```

---

### Task 7: Add `make lint-framework` to Makefile

**Files:**
- Modify: `Makefile` (`.PHONY` line and new target; add to `lint` aggregate)

- [ ] **Step 1: Update `.PHONY` and `lint` target**

  Change line 1 from:
  ```makefile
  .PHONY: install install-pr-review install-k8s-overprovisioning install-incident-rca lint lint-pr-review lint-k8s-skill lint-incident-rca setup-hooks
  ```
  to:
  ```makefile
  .PHONY: install install-pr-review install-k8s-overprovisioning install-incident-rca lint lint-framework lint-pr-review lint-k8s-skill lint-incident-rca setup-hooks
  ```

  Change line 15 from:
  ```makefile
  lint: lint-pr-review lint-k8s-skill lint-incident-rca
  ```
  to:
  ```makefile
  lint: lint-framework lint-pr-review lint-k8s-skill lint-incident-rca
  ```

- [ ] **Step 2: Append `lint-framework` target before `setup-hooks`**

  ```makefile
  lint-framework:
  	@echo "lint-framework: shared docs present"
  	@test -f docs/skill-framework/README.md
  	@for f in confidence-bands cross-skill-escalation post-action-templates \
  		smoke-test-conventions examples-conventions phase-glossary; do \
  		test -f docs/skill-framework/shared/$$f.md || exit 1; \
  	done
  	@grep -q 'confidence-bands' docs/skill-framework/README.md
  	@echo "lint-framework: ok"
  ```

- [ ] **Step 3: Run lint-framework**

  ```bash
  make lint-framework
  ```
  Expected: `lint-framework: ok`

- [ ] **Step 4: Commit**

  ```bash
  git add Makefile
  git commit -m "chore: add make lint-framework gate for shared skill docs"
  ```

---

### Task 8: Update framework README status table

**Files:**
- Modify: `docs/skill-framework/README.md`

- [ ] **Step 1: Flip Status table to Complete**

  Replace the Status section:

  ```markdown
  ## Status

  | File | Status |
  |------|--------|
  | confidence-bands.md | Complete |
  | cross-skill-escalation.md | Complete |
  | post-action-templates.md | Complete |
  | smoke-test-conventions.md | Complete |
  | examples-conventions.md | Complete |
  | phase-glossary.md | Complete |
  ```

- [ ] **Step 2: Verify and commit**

  ```bash
  make lint-framework
  git add docs/skill-framework/README.md
  git commit -m "docs(framework): mark shared library complete"
  ```

---

## Phase 2 — incident-rca compliance

**Order:** F1/F2 → execute [rca-round3-gaps](./2026-06-30-rca-round3-gaps.md) (P2-2 → P1-3 → P2-3 → P3-1) → F3/F4 → checklist sign-off

**Exit criteria:** `make lint-incident-rca` passes; `make lint-framework` passes; §4 checklist true for incident-rca; 4/4 Round 3 gaps closed.

---

### Task 9: F1 — Framework links in incident-rca SKILL.md and SETUP.md

**Files:**
- Modify: `incident-rca/SKILL.md`
- Modify: `incident-rca/SETUP.md`

- [ ] **Step 1: Add Framework section to SETUP.md after install instructions**

  ```markdown
  ## Framework conventions

  - Index: [docs/skill-framework/README.md](../docs/skill-framework/README.md)
  - Confidence: [confidence-bands](../docs/skill-framework/shared/confidence-bands.md)
  - Escalation: [cross-skill-escalation](../docs/skill-framework/shared/cross-skill-escalation.md)
  - Smoke tests: [smoke-test-conventions](../docs/skill-framework/shared/smoke-test-conventions.md)
  - Examples: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md)
  - Phases: [phase-glossary](../docs/skill-framework/shared/phase-glossary.md)
  - Post-actions: [post-action-templates](../docs/skill-framework/shared/post-action-templates.md)
  ```

- [ ] **Step 2: Replace inline Cross-skill escalation table in SKILL.md with link + ≤10 skill-specific rows**

  Find `## Cross-skill escalation` in `incident-rca/SKILL.md`. Replace the full inline matrix with:

  ```markdown
  ## Cross-skill escalation

  Full symmetric matrix: [cross-skill-escalation.md](../docs/skill-framework/shared/cross-skill-escalation.md)

  | Finding (this skill) | Next skill |
  |----------------------|------------|
  | deploy_regression ranked HIGH | pr-review on causative MR |
  | infra_capacity / OOM | k8s-overprovisioning-datadog |
  | kafka_consumer_lag | k8s-overprovisioning-datadog |
  ```

  Keep only incident-rca-originating rows; remove duplicated pr-review/k8s-origin rows.

- [ ] **Step 3: Verify SKILL.md line count ≤180**

  ```bash
  wc -l incident-rca/SKILL.md
  make lint-incident-rca
  ```

- [ ] **Step 4: Commit**

  ```bash
  git add incident-rca/SKILL.md incident-rca/SETUP.md
  git commit -m "docs(rca): link incident-rca to unified skill framework"
  ```

---

### Task 10: F2 — Expand incident-rca `examples.md` to framework bar

**Files:**
- Modify: `incident-rca/examples.md`

- [ ] **Step 1: Add invocation table (8 rows) at top of file**

  ```markdown
  ## Invocation table

  | # | User says | Behavior |
  |---|-----------|----------|
  | 1 | "RCA for `service` 14:00–16:00 UTC" | Phase 0→5; window from user |
  | 2 | "RCA for INC-4521" | Phase 0b anchor → 1→5 |
  | 3 | "Root cause last Tuesday 2–4pm Kafka lag" | Org-wide Phase 1 discovery |
  | 4 | "RCA neo-disbursement — logs unavailable" | slo_breach fallback path |
  | 5 | "Post-incident review payout-worker" | Standard pipeline |
  | 6 | "What caused the 5xx spike?" | Symptom-only; service discovery |
  | 7 | "RCA with correlator CLI missing" | manual-scoring degraded path |
  | 8 | "Review MR !482 for security" | **Wrong skill** → pr-review |
  ```

- [ ] **Step 2: Add degraded-path scenario (PagerDuty absent)**

  ```markdown
  ### Scenario: PagerDuty absent — slo_breach only

  **User:** "RCA payment-api 2026-06-28 — no logs in Datadog"

  **Agent:**
  1. Detect (Phase 0) — Datadog ✅, logs empty in window
  2. Gather (Phase 1) — slo_breach path: burn rate, traces, war-room signals

  **Expected fragments:**
  ```
  **Primary:** slo_breach (**MEDIUM**) — error budget burn 340% in window; logs unavailable.
  **Gaps:** Log samples missing — ranking from SLO + traces only.
  ```
  ```

- [ ] **Step 3: Add cross-skill handoff scenario**

  ```markdown
  ### Scenario: Handoff to k8s after infra_capacity

  **User:** "RCA checkout-api — OOMKilled pods"

  **Expected fragments:**
  ```
  **Handoff → k8s-overprovisioning-datadog**
  - Service: `checkout-api`
  - Env: `prod`
  - Window: `2026-06-28T10:00Z` – `2026-06-28T12:00Z`
  - Trigger: infra_capacity — OOMKilled × 12
  - Ask: "Assess rightsizing for checkout-api in prod"
  ```
  ```

- [ ] **Step 4: Verify line count ≥150**

  ```bash
  wc -l incident-rca/examples.md
  ```
  Expected: ≥150 lines

- [ ] **Step 5: Commit**

  ```bash
  git add incident-rca/examples.md
  git commit -m "docs(rca): expand examples to framework depth bar"
  ```

---

### Task 11: Execute incident-rca Round 3 gap sub-plan

**Files:** Per [2026-06-30-rca-round3-gaps.md](./2026-06-30-rca-round3-gaps.md)

- [ ] **Step 1: Execute Task 1 (P2-2)** — Phase 0b backstroke in `workflow/phase-0b.md`

- [ ] **Step 2: Execute Task 2 (P1-3)** — slo_breach fallback in `workflow/phase-1.md`

- [ ] **Step 3: Execute Task 3 (P2-3)** — runbook dedup across `phase-1.md` / `phase-4.md`

- [ ] **Step 4: Execute Task 4 (P3-1)** — PagerDuty/OpsGenie in `phase-0.md` + `query-playbook.md`

  Follow each task's steps and commits exactly as written in the sub-plan. Do not skip pressure-test rows.

- [ ] **Step 5: Verify**

  ```bash
  make lint-incident-rca
  ```

---

### Task 12: F3 — MCP matrix completeness (Grafana/Prometheus)

**Files:**
- Modify: `incident-rca/reference/mcp-capabilities.md`
- Modify: `incident-rca/reference/pressure-tests.md` (1 row if missing)

- [ ] **Step 1: Add explicit degraded rows for Grafana and Prometheus**

  In the MCP table, add rows:

  ```markdown
  | Grafana | optional | ❌ Not supported in v1 — use Datadog dashboards/metrics only; do not call Grafana MCP |
  | Prometheus | optional | ❌ Not supported in v1 — use Datadog metrics; document gap in report |
  ```

- [ ] **Step 2: Add pressure test for Grafana request**

  ```markdown
  | User asks to query Grafana directly | Agent states Grafana not supported; uses Datadog path; no silent failure |
  ```

- [ ] **Step 3: Commit**

  ```bash
  git add incident-rca/reference/mcp-capabilities.md incident-rca/reference/pressure-tests.md
  git commit -m "docs(rca): explicit Grafana/Prometheus degraded MCP rows"
  ```

---

### Task 13: F4 — Framework link lint in `lint-incident-rca`

**Files:**
- Modify: `Makefile` (`lint-incident-rca` target)

- [ ] **Step 1: Append SETUP.md link check to lint-incident-rca**

  After the dangling-anchor check block in `lint-incident-rca`, add:

  ```makefile
  	@echo "lint-incident-rca: framework link in SETUP.md"
  	@grep -q 'skill-framework' incident-rca/SETUP.md || \
  		{ echo "error: incident-rca/SETUP.md must link to docs/skill-framework" >&2; exit 1; }
  	@echo "  ok"
  ```

- [ ] **Step 2: Run and commit**

  ```bash
  make lint-incident-rca
  git add Makefile
  git commit -m "chore: lint-incident-rca requires skill-framework link"
  ```

---

### Task 14: incident-rca framework checklist sign-off

- [ ] **Step 1: Walk design spec §4 checklist for incident-rca**

  Manually verify each §4.1–§4.9 item. Fix any gap in the same commit batch.

- [ ] **Step 2: Final lint**

  ```bash
  make lint-framework lint-incident-rca
  ```

- [ ] **Step 3: Commit any fixes**

  ```bash
  git commit -m "docs(rca): framework compliance checklist complete"
  ```

---

## Phase 3 — k8s-overprovisioning-datadog compliance

**Order:** F1/F2 (reference files) → execute [k8s-round3-gaps](./2026-06-30-k8s-round3-gaps.md) (P1-1 → P1-2 → P2-1 → P3-2) → F3/F4 → checklist sign-off

**Exit criteria:** `make lint-k8s-skill` passes; `reference/phase-index.md`, `lazy-load-index.md`, `smoke-test.md` exist; §4 checklist true for k8s.

---

### Task 15: Create k8s `reference/phase-index.md`

**Files:**
- Create: `k8s-overprovisioning-datadog/reference/phase-index.md`

- [ ] **Step 1: Create phase-index aligned with phase-glossary**

  ```markdown
  # Phase index

  Canonical names: [phase-glossary](../../docs/skill-framework/shared/phase-glossary.md#4-k8s-mapping)

  | Order | Phase | Workflow file |
  |-------|-------|---------------|
  | 0 | Detect / route | [orchestrator.md](../workflow/orchestrator.md) |
  | 1 | COLLECT | [collect-metrics.md](../workflow/collect-metrics.md) |
  | 2 | REASON | [reason.md](../workflow/reason.md) |
  | 3 | BUILD_GRAPH | [build-graph.md](../workflow/build-graph.md) |
  | 4 | VALIDATE_INVARIANTS | [validate-invariants.md](../workflow/validate-invariants.md) |
  | 5 | RENDER | [render.md](../workflow/render.md), [report.md](../workflow/report.md) |
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add k8s-overprovisioning-datadog/reference/phase-index.md
  git commit -m "docs(k8s): add reference phase-index"
  ```

---

### Task 16: F2 — Create k8s `reference/lazy-load-index.md`

**Files:**
- Create: `k8s-overprovisioning-datadog/reference/lazy-load-index.md`

- [ ] **Step 1: Create lazy-load index mirroring pr-review pattern**

  ```markdown
  # Lazy-load index

  Read reference files **one at a time** when the active workflow phase says to.

  | When | Also load |
  |------|-----------|
  | Prerequisites | [mcp-capabilities.md](mcp-capabilities.md) if present; else orchestrator prerequisites |
  | COLLECT | [observation-ids.md](observation-ids.md), analysis modules as triggered |
  | REASON | [confidence-formula.md](confidence-formula.md), [invariants.md](invariants.md) |
  | BUILD_GRAPH | [decision-graph-schema.md](decision-graph-schema.md), [decision-ids.md](decision-ids.md) |
  | VALIDATE_INVARIANTS | [invariants.md](invariants.md) |
  | RENDER | [report-schema.md](report-schema.md), [templates/](../templates/) |
  | Smoke / install | [smoke-test.md](smoke-test.md) |
  | Maintainer edits | [pressure-tests.md](pressure-tests.md) |
  ```

  Create `reference/mcp-capabilities.md` stub if missing (table: Datadog required, git MCP optional, KubeSense optional).

- [ ] **Step 2: Commit**

  ```bash
  git add k8s-overprovisioning-datadog/reference/lazy-load-index.md
  git commit -m "docs(k8s): add lazy-load-index reference"
  ```

---

### Task 17: F1 — Extract `reference/smoke-test.md` from render workflow

**Files:**
- Create: `k8s-overprovisioning-datadog/reference/smoke-test.md`
- Modify: `k8s-overprovisioning-datadog/workflow/render.md`

- [ ] **Step 1: Create smoke-test.md with numbered checklist**

  ```markdown
  # Smoke test

  Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

  ## Fixture

  Deployment with ≥7d Datadog metrics; single namespace; <5 containers.

  ## Output checklist

  1. **MCP profile** — Datadog ✅; git MCP noted
  2. **Scope** — deployment, env, window announced
  3. **decision_graph** — passes INV-01–INV-12
  4. **Human Report** — all slugs from [report-schema.md](report-schema.md#human-report-fixed-order--primary-output)
  5. **Structured footer** — Assessment Metadata YAML present
  6. **Next step** — handoff offer or re-run hint

  Deep edge cases: [pressure-tests.md](pressure-tests.md)
  ```

- [ ] **Step 2: Replace inline smoke section in render.md with link**

  In `workflow/render.md`, replace `## Smoke test` section body with:

  ```markdown
  ## Smoke test

  Run checklist in [reference/smoke-test.md](../reference/smoke-test.md). Re-run after any skill edit.
  ```

- [ ] **Step 3: Commit**

  ```bash
  git add k8s-overprovisioning-datadog/reference/smoke-test.md k8s-overprovisioning-datadog/workflow/render.md
  git commit -m "docs(k8s): extract dedicated smoke-test reference"
  ```

---

### Task 18: F1 — Framework links in k8s SKILL.md and SETUP.md

**Files:**
- Modify: `k8s-overprovisioning-datadog/SKILL.md`
- Modify: `k8s-overprovisioning-datadog/SETUP.md`

- [ ] **Step 1: Add Framework section to SETUP.md** (same link block as Task 9, paths adjusted for `k8s-overprovisioning-datadog/`)

- [ ] **Step 2: Trim SKILL.md escalation to link + k8s-specific rows**

  ```markdown
  ## Cross-skill escalation

  Full matrix: [cross-skill-escalation.md](../docs/skill-framework/shared/cross-skill-escalation.md)

  | Finding (this skill) | Next skill |
  |----------------------|------------|
  | OOM / crashloop on assessed deployment | incident-rca |
  | Spike + recent deploy | pr-review |
  | Ready cut applied | k8s re-run in 7d |
  ```

- [ ] **Step 3: Verify SKILL.md ≤150 lines; commit**

  ```bash
  wc -l k8s-overprovisioning-datadog/SKILL.md
  git add k8s-overprovisioning-datadog/SKILL.md k8s-overprovisioning-datadog/SETUP.md
  git commit -m "docs(k8s): link k8s skill to unified framework"
  ```

---

### Task 19: Execute k8s Round 3 gap sub-plan

**Files:** Per [2026-06-30-k8s-round3-gaps.md](./2026-06-30-k8s-round3-gaps.md)

- [ ] **Step 1: Execute Task 1 (P1-1)** — KEDA metrics

- [ ] **Step 2: Execute Task 2 (P1-2)** — limit/request ratio

- [ ] **Step 3: Execute Task 3 (P2-1)** — VPA+HPA conflict

- [ ] **Step 4: Execute Task 4 (P3-2)** — APM confidence modifier

- [ ] **Step 5: Verify**

  ```bash
  make lint-k8s-skill
  ```

---

### Task 20: F3 — Map numeric confidence to shared categorical bands

**Files:**
- Modify: `k8s-overprovisioning-datadog/reference/confidence-formula.md`

- [ ] **Step 1: Add shared reference link and mapping table at top**

  ```markdown
  Categorical bands (normative): [confidence-bands.md](../../docs/skill-framework/shared/confidence-bands.md)

  After computing `ASSESSMENT_CONFIDENCE` / `RECOMMENDATION_CONFIDENCE`, map to HIGH/MEDIUM/LOW/UNKNOWN
  using the 0.85 / 0.65 / 0.40 thresholds in the shared doc. Human Report displays band + factors only.
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add k8s-overprovisioning-datadog/reference/confidence-formula.md
  git commit -m "docs(k8s): map numeric confidence to shared categorical bands"
  ```

---

### Task 21: F4 — Cross-skill handoff examples in k8s `examples.md`

**Files:**
- Modify: `k8s-overprovisioning-datadog/examples.md`

- [ ] **Step 1: Add handoff scenario from incident-rca**

  ```markdown
  ### Scenario: Handoff from incident-rca (OOM)

  **User:** "Assess checkout-api prod — RCA found OOMKilled"

  **Expected fragments:**
  ```
  **Handoff accepted** — window 2026-06-28T10:00Z–12:00Z from RCA.
  **Assessment confidence:** MEDIUM (0.72) — CPU headroom low; memory limit 2× request.
  ```
  ```

- [ ] **Step 2: Add wrong-skill row to invocation table if not present**

  ```markdown
  | "RCA for checkout-api outage" | **Wrong skill** → incident-rca |
  ```

- [ ] **Step 3: Commit**

  ```bash
  git add k8s-overprovisioning-datadog/examples.md
  git commit -m "docs(k8s): add cross-skill handoff examples"
  ```

---

### Task 22: k8s framework checklist sign-off

- [ ] **Step 1: Walk design spec §4 for k8s; fix gaps**

- [ ] **Step 2: Final lint**

  ```bash
  make lint-framework lint-k8s-skill
  ```

- [ ] **Step 3: Commit fixes if any**

  ```bash
  git commit -m "docs(k8s): framework compliance checklist complete"
  ```

---

## Phase 4 — pr-review polish

**Order:** Execute [pr-review-round3-gaps](./2026-06-30-pr-review-round3-gaps.md) (P1-4 → P2-4 → P2-5 → P3-3) → F1–F3 → checklist sign-off

**Exit criteria:** `make lint-pr-review` passes (skill + scripts + pytest); escalation table deduped; §4 checklist true for pr-review.

---

### Task 23: Execute pr-review Round 3 gap sub-plan

**Files:** Per [2026-06-30-pr-review-round3-gaps.md](./2026-06-30-pr-review-round3-gaps.md)

- [ ] **Step 1: Execute Task 1 (P1-4)** — Revert MR detection

- [ ] **Step 2: Execute Task 2 (P2-4)** — Mixed bot+human MR

- [ ] **Step 3: Execute Task 3 (P2-5)** — CODEOWNERS approval

- [ ] **Step 4: Execute Task 4 (P3-3)** — OpenAPI/Proto spec changes

- [ ] **Step 5: Verify**

  ```bash
  make lint-pr-review
  ```

---

### Task 24: F1 — Framework links in pr-review SETUP.md and SKILL.md

**Files:**
- Modify: `pr-review/SETUP.md`
- Modify: `pr-review/SKILL.md`

- [ ] **Step 1: Add Framework section to SETUP.md** (same seven-link block as Task 9)

- [ ] **Step 2: Dedup escalation in SKILL.md**

  Replace inline cross-skill table with:

  ```markdown
  ## Cross-skill escalation

  Full matrix: [cross-skill-escalation.md](../docs/skill-framework/shared/cross-skill-escalation.md)

  | Finding (this skill) | Next skill |
  |----------------------|------------|
  | Critical security / bad deploy in prod | incident-rca |
  | K8s/infra perf regression in MR | k8s-overprovisioning-datadog |
  | Resource-down MR merged | k8s + incident-rca if outage |
  ```

- [ ] **Step 3: Verify SKILL.md ≤180 lines; commit**

  ```bash
  make lint-pr-review
  git add pr-review/SETUP.md pr-review/SKILL.md
  git commit -m "docs(pr-review): link to unified framework; dedup escalation table"
  ```

---

### Task 25: F3 — Confidence bands link in executive-summary

**Files:**
- Modify: `pr-review/reference/executive-summary.md`

- [ ] **Step 1: Add normative link at Confidence section**

  ```markdown
  Per-finding and overall confidence bands: [confidence-bands.md](../../docs/skill-framework/shared/confidence-bands.md).
  Use High/Medium/Low in findings table; map to HIGH/MEDIUM/LOW/UNKNOWN when comparing across skills.
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add pr-review/reference/executive-summary.md
  git commit -m "docs(pr-review): reference shared confidence bands"
  ```

---

### Task 26: Extend `make lint-framework` for all SETUP.md links (optional enhancement)

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Add SETUP link checks to lint-framework**

  Append to `lint-framework` target:

  ```makefile
  	@for skill in pr-review incident-rca k8s-overprovisioning-datadog; do \
  		grep -q 'skill-framework' $$skill/SETUP.md || \
  			{ echo "error: $$skill/SETUP.md must link to docs/skill-framework" >&2; exit 1; }; \
  	done
  	@echo "lint-framework: all SETUP.md links ok"
  ```

  Run only after Phases 2–4 complete (all three SETUP.md files updated).

- [ ] **Step 2: Commit**

  ```bash
  make lint-framework
  git add Makefile
  git commit -m "chore: lint-framework checks skill-framework links in all SETUP.md"
  ```

---

### Task 27: Final integration — full lint + success criteria

- [ ] **Step 1: Run full lint suite**

  ```bash
  make lint
  ```
  Expected: exit 0 (framework + all three skills + shellcheck)

- [ ] **Step 2: Verify success criteria from design spec §8**

  | Criterion | Command |
  |-----------|---------|
  | Lint green | `make lint` |
  | 12/12 Round 3 gaps | grep pressure-tests for P1/P2/P3 rows per skill |
  | Cross-skill matrix | spot-check three SKILL.md escalation sections link shared doc |
  | Confidence mapping | rca MEDIUM + k8s 0.7 both map to MEDIUM per shared doc |

- [ ] **Step 3: Commit any final fixes**

  ```bash
  git commit -m "chore: unified skill framework Phases 1–4 complete"
  ```

---

## Self-review (plan author checklist)

| Spec section | Plan coverage |
|--------------|---------------|
| §3 Framework anatomy | Tasks 9–26 create missing k8s reference files; examples/smoke/MCP per skill |
| §4 Quality bar checklist | Task 14, 22, 27 sign-off steps |
| §5 Shared library | Tasks 1–8 |
| §6 Per-skill gaps | Tasks 11, 19, 23 delegate to round3 sub-plans |
| §7 Implementation phases | Four phases map 1:1 to plan sections |
| §8 Success criteria | Task 27 |
| §9 Out of scope | No new skills, no MCP server code, no auto-post |

**Placeholder scan:** No TBD/TODO/similar-to tasks. All file paths explicit.

---

## Execution handoff

**Plan complete and saved to `docs/superpowers/plans/2025-06-30-unified-skill-framework-plan.md`.**

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task (Tasks 1–27), review between tasks.

**2. Inline Execution** — use executing-plans skill; batch by phase with checkpoints after Tasks 8, 14, 22, 27.

**Do not start skill patches until execution mode is chosen.**
