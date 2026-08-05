# Unified Skill Framework — Design Spec

**Date:** 2025-06-30  
**Status:** Approved (Approach A+C)  
**Scope:** `pr-review/`, `incident-rca/`, `k8s-overprovisioning-datadog/` in `/Users/luckyjain/Projects/ai-skills`  
**Reference implementation:** `pr-review/` (repo root)

---

## 1. Summary & goals

### Problem

The three production skills in this repo evolved independently. They share concepts — phased workflows, MCP capability detection, confidence bands, cross-skill handoffs, smoke tests, pressure scenarios — but express them with different vocabulary, file layouts, and completeness. Agents that switch between skills must re-learn conventions; maintainers cannot apply a single quality bar.

### Goal

Establish a **unified skill framework** so all three skills:

1. **Look alike** — predictable directory anatomy, frontmatter, and lazy-load patterns.
2. **Behave alike** — same confidence vocabulary, escalation matrix, degraded-mode rules, and post-action templates.
3. **Lint alike** — extendable `make lint-*` gates for structural compliance, not just skill-specific invariants.
4. **Hand off cleanly** — symmetric cross-skill escalation with copy-paste handoff blocks.

### Non-goal (this spec)

This document defines the framework and compliance path. It does **not** patch skills. Skill changes follow Phases 2–4 in §8.

### Skills in scope

| Skill | Repo path | Installed path (Cursor) |
|-------|-----------|-------------------------|
| pr-review | `pr-review/` | `~/.cursor/skills/pr-review/` (symlink via `make install-pr-review`) |
| incident-rca | `incident-rca/` | `~/.cursor/skills/incident-rca/` |
| k8s-overprovisioning-datadog | `k8s-overprovisioning-datadog/` | `~/.cursor/skills/k8s-overprovisioning-datadog/` |

All three live in the monorepo; `scripts/install.sh` symlinks each into `~/.cursor/skills/`.

---

## 2. Approach — A+C hybrid rationale

### Approach A — Framework spec first, then patch each skill

**Rationale:** Writing the shared contract before editing skills prevents three divergent “fixes.” The spec (this document) and shared library (`docs/skill-framework/shared/`) are the single source of truth. Each skill patch is a **compliance diff** against a checklist (§4), not ad hoc improvement.

**Risk without A:** Patching one skill first bakes in that skill’s idioms as “the standard,” forcing the others to conform to accidental choices (e.g. k8s numeric confidence vs pr-review categorical).

### Approach C — Shared reference library

**Rationale:** Duplicating confidence-band rules, escalation tables, and smoke-test conventions across three `SKILL.md` files guarantees drift. Shared docs are **referenced by link**, not copied inline. Skills keep only skill-specific deltas (e.g. pr-review per-finding `PRR-` IDs; k8s `OBS_`/`DEC_` graph IDs).

**Placement:** `docs/skill-framework/` lives at **repo root** (not inside any skill directory) so:

- One edit updates all skills’ references in the same commit.
- `make lint-framework` (new, §9) can validate links without installing skills.
- Installed symlinks do not need to ship framework docs — agents read them from the workspace clone or maintainers paste stable anchors.

### Why A+C together

| Approach alone | Gap | A+C combined |
|----------------|-----|--------------|
| A only | Spec without shared primitives → each skill re-implements prose | Shared library materializes the spec |
| C only | Shared docs without per-skill compliance plan → optional adoption | Spec + checklist force adoption per skill |

**Execution order:** Shared library stubs → framework lint rules → incident-rca (largest structural gap) → k8s → pr-review polish (closest to bar already).

---

## 3. Framework anatomy

Every compliant skill is a self-contained directory installable via `scripts/install.sh`. Required and optional artifacts:

### 3.1 Required files (root)

| File | Purpose | Line budget | Reference |
|------|---------|-------------|-----------|
| `SKILL.md` | Thin orchestrator: description frontmatter, when-NOT-to-use, workflow index, guardrails, cross-skill escalation (links to shared matrix) | pr-review ≤180; k8s ≤150; rca ≤180 | `pr-review/SKILL.md` |
| `SETUP.md` | Install, MCP config, env requirements, directory map | No hard limit | `pr-review/SETUP.md` |
| `README.md` | Human-facing one-pager (optional but recommended) | — | `pr-review/README.md` |
| `examples.md` | Invocation table + ≥3 end-to-end scenario walkthroughs | ≥150 lines or ≥8 scenarios | `pr-review/examples.md` |
| `report-template.md` | Canonical output skeleton (chat-first); anchors for handoff blocks | — | `incident-rca/report-template.md`, `k8s-overprovisioning-datadog/report-template.md` |

**SKILL.md frontmatter (required):**

```yaml
---
name: <skill-name>
description: >-
  Use when … Keywords: …
# optional — omit to allow natural-language auto-invocation (pr-review, incident-rca, k8s):
# disable-model-invocation: true
---
```

### 3.2 Required `workflow/` directory

One markdown file per phase or orchestrator step. **Every** `workflow/*.md` file MUST begin with YAML frontmatter:

```yaml
---
workflow_version: <semver>
phase: <id or name>          # e.g. 1, collect, orchestrator
produces:
  - <artifact_id>
consumes:
  - <artifact_id>
---
```

**Required workflow files by skill:**

| Skill | Minimum workflow set |
|-------|---------------------|
| pr-review | `inputs.md`, `phase-0.md` … `phase-5.md`, `posting.md`, `phase-2-3-gate.md` |
| incident-rca | `inputs.md`, `phase-0.md`, `phase-0b.md` (conditional), `phase-1.md` … `phase-5.md` |
| k8s | `orchestrator.md`, `collect-metrics.md`, `reason.md`, `build-graph.md`, `validate-invariants.md`, `report.md`, `render.md` + analysis modules |

Skills MAY add workflow files; they MUST NOT collapse phases into `SKILL.md`.

### 3.3 Required `reference/` directory

| File | Required | Purpose |
|------|----------|---------|
| `phase-index.md` | Yes | Ordered phase list → workflow file links |
| `lazy-load-index.md` | Yes | Which reference files load per phase |
| `mcp-capabilities.md` | Yes | Tool matrix: required / optional / degraded path per MCP server |
| `smoke-test.md` | Yes (or anchored section in workflow) | Post-install + post-edit verification checklist |
| `pressure-tests.md` | Yes | Maintainer table: scenario → expected behavior |
| Skill-specific schemas | As needed | e.g. `evidence-schema.md`, `decision-graph-schema.md`, `severity-rubric.md` |

### 3.4 Optional but standardized directories

| Path | When | Example |
|------|------|---------|
| `templates/` | Multi-section reports | `k8s-overprovisioning-datadog/templates/` (≥14 files) |
| `render/` | Multiple output formats | `k8s-overprovisioning-datadog/render/markdown.md`, `json.md` |
| `scripts/` + `tests/` | Deterministic helpers | `pr-review/scripts/diff-to-positions.py` + pytest |
| `examples/` | Non-markdown fixtures | `pr-review/examples/review-rules.yaml` |
| `thresholds.md` | Numeric cutoffs | k8s only |

### 3.5 Shared framework references (required links)

Each skill MUST link to the shared library from `SKILL.md` or `SETUP.md`:

```markdown
Framework conventions: [docs/skill-framework/README.md](../../../docs/skill-framework/README.md)
```

(Relative path from skill root to repo `docs/skill-framework/`.)

Required shared links per skill:

| Shared doc | pr-review | incident-rca | k8s |
|------------|-----------|--------------|-----|
| `confidence-bands.md` | Per-finding + overall | Hypothesis bands | Assessment + REC bands |
| `cross-skill-escalation.md` | § in SKILL.md → shared | § in SKILL.md → shared | § in SKILL.md → shared |
| `smoke-test-conventions.md` | Extends local smoke-test | Extends local smoke-test | Extends render smoke |
| `examples-conventions.md` | Local examples.md | Local examples.md | Local examples.md |
| `phase-glossary.md` | Phase 0–5 names | Phase 0–5 names | COLLECT→RENDER names |
| `post-action-templates.md` | Jira write-back | Jira + Slack | Canvas hints |

### 3.6 Naming conventions

| Concept | Convention |
|---------|------------|
| Phase files | `phase-N.md` (0-based or 1-based per skill; document in phase-index) |
| Workflow version | Semver in frontmatter; bump when `produces`/`consumes` change |
| Finding IDs | pr-review: `PRR-###`; k8s: `OBS_`, `EVID_`, `DEC_`, `REC_`; rca: hypothesis types in evidence schema |
| Stop reasons | k8s: `STOP_REASON: <snake_case>`; rca: blocked report gates; pr-review: phase-2-3 gate |
| Telemetry | Datadog calls include `telemetry.intent` string (all three skills) |

---

## 4. Quality bar checklist

A skill passes framework compliance when **all** items below are true. Use as PR review checklist for skill patches.

### 4.1 Structure & lint

- [ ] `make lint-<skill>` passes (existing targets in root `Makefile`)
- [ ] `make lint-framework` passes (new target — link checks to `docs/skill-framework/shared/*.md`)
- [ ] `SKILL.md` within line budget
- [ ] Every `workflow/*.md` has `workflow_version`, `produces`, `consumes` in frontmatter
- [ ] No dangling `](*.md#anchor)` references within skill tree
- [ ] `reference/phase-index.md` matches actual workflow files
- [ ] `SETUP.md` directory tree matches disk

### 4.2 Smoke test

- [ ] `reference/smoke-test.md` (or k8s `workflow/render.md#smoke-test`) lists **numbered** expected output elements
- [ ] Smoke test instructs re-run after **any** skill edit (not only install)
- [ ] Smoke test references ≥2 pressure-test rows for edge cases
- [ ] Follows [smoke-test-conventions.md](../../skill-framework/shared/smoke-test-conventions.md)

### 4.3 Examples depth

- [ ] `examples.md` has invocation table (≥8 rows)
- [ ] ≥3 multi-step scenarios with expected output fragments (not just one-liners)
- [ ] ≥1 degraded-path example (MCP missing, sparse data, chat-only)
- [ ] ≥1 cross-skill handoff example
- [ ] Follows [examples-conventions.md](../../skill-framework/shared/examples-conventions.md)

### 4.4 MCP matrix

- [ ] `reference/mcp-capabilities.md` tables: tool name, required/optional, fallback when absent
- [ ] Phase 0 announces MCP profile (✅/❌ per integration)
- [ ] Degraded path documented for each **required** MCP (what skill does instead of stopping silently)
- [ ] `telemetry.intent` mandated for observability MCP calls

### 4.5 Degraded paths

- [ ] Explicit **when NOT to use** table in `SKILL.md`
- [ ] Read-only guardrail stated (investigation skills)
- [ ] Partial/blocked report path when minimum evidence gate fails (rca, k8s stop reasons)
- [ ] Rate-limit / API error handling documented in workflow or query-playbook

### 4.6 Confidence & evidence

- [ ] Uses shared vocabulary HIGH / MEDIUM / LOW / UNKNOWN per [confidence-bands.md](../../skill-framework/shared/confidence-bands.md)
- [ ] Never asserts HIGH on single source (rca guardrail; k8s INV rules; pr-review dont-guess-gate)
- [ ] Every confidence label has a **Reason** or factor list in output

### 4.7 Cross-skill escalation

- [ ] `SKILL.md` escalation table links to [cross-skill-escalation.md](../../skill-framework/shared/cross-skill-escalation.md)
- [ ] Handoff blocks in `report-template.md` use stable anchors
- [ ] Reverse escalations documented (symmetric matrix)

### 4.8 Pressure tests

- [ ] `reference/pressure-tests.md` table: scenario | expected behavior
- [ ] ≥1 row per P1 gap closed (see §6)
- [ ] ≥2 rows testing **wrong** agent behavior (must not …)

### 4.9 Post-actions

- [ ] Jira write-back or explicit skip documented (pr-review phase-5; rca optional)
- [ ] Slack/canvas hints per [post-action-templates.md](../../skill-framework/shared/post-action-templates.md) where applicable

### 4.10 pr-review parity targets (reference bar)

Skills SHOULD match pr-review where concept applies:

| pr-review feature | incident-rca target | k8s target |
|-------------------|---------------------|------------|
| `lazy-load-index.md` | Present | Add if missing |
| `incremental-rerun` / re-review | N/A | N/A |
| `fast-path.md` | Partial-report fast path | Namespace-ranking fast path |
| `session-context-cache.md` | Window cache across phases | Service context cache |
| Executive summary + metadata footer | Phase 5 report + evidence JSON | Human Report + decision graph |
| `review_metadata` YAML | `evidence.example.json` parity | `decision-graph.example.yaml` |

---

## 5. Shared library layout

**Index:** [docs/skill-framework/README.md](../../skill-framework/README.md)

**Directory:**

```
docs/skill-framework/
├── README.md                          # Index + how skills reference shared docs
└── shared/
    ├── confidence-bands.md            # §5.1
    ├── cross-skill-escalation.md      # §5.2
    ├── post-action-templates.md       # §5.3
    ├── smoke-test-conventions.md      # §5.4
    ├── examples-conventions.md        # §5.5
    └── phase-glossary.md              # §5.6
```

### 5.1 `confidence-bands.md` — outline

1. **Purpose** — one vocabulary across skills; agents must not invent alternate labels.
2. **Categorical bands** — HIGH, MEDIUM, LOW, UNKNOWN definitions (evidence depth, source count).
3. **Numeric mapping (0.0–1.0)** — k8s `ASSESSMENT_CONFIDENCE` / `RECOMMENDATION_CONFIDENCE` bands:
   - 0.85–1.0 → HIGH (Very High)
   - 0.65–0.84 → MEDIUM (Moderate)
   - 0.40–0.64 → LOW
   - <0.40 or missing inputs → UNKNOWN / Insufficient
4. **pr-review per-finding** — High/Medium/Low in findings table; overall executive-summary Confidence; mapping table categorical ↔ numeric for cross-skill comparison.
5. **incident-rca hypothesis** — manual-scoring bands; cap rules (single source → max MEDIUM).
6. **Display rules** — always pair label with Reason; graph skills may hide arithmetic in Human Report.
7. **Anti-patterns** — hand-waved “High”; numeric 0.9 with only one signal.

### 5.2 `cross-skill-escalation.md` — outline

1. **Symmetric matrix** (3×3) — trigger | from → to | handoff artifact | user prompt template.
2. **Forward escalations** — pr-review → rca, pr-review → k8s, rca → k8s, rca → pr-review, k8s → rca, k8s → pr-review.
3. **Reverse escalations** — after k8s cut → re-run k8s in 7d; after rca deploy_regression → pr-review on MR; after pr-review infra MR → k8s validation.
4. **Handoff blocks** — required fields: service, env, time window, hypothesis, evidence links.
5. **When NOT to escalate** — wrong skill table (link to each SKILL.md).
6. **Canvas hint** — when escalation deliverable benefits from canvas (billing, timeline, multi-service).

### 5.3 `post-action-templates.md` — outline

1. **Jira comment** — RCA summary, PR review verdict, k8s recommendation block.
2. **Jira ticket update** — fields: priority, labels (`rca-complete`, `rightsizing-ready`).
3. **Slack** — incident channel brief; PR review 🔴 summary; cost-savings headline.
4. **Canvas** — when to open canvas vs chat markdown (per canvas skill).
5. **Confirmation gates** — pr-review Phase 3 before post; rca/k8s read-only (no auto-post).

### 5.4 `smoke-test-conventions.md` — outline

1. **When to run** — post-install, post-edit, pre-release.
2. **Structure** — numbered output checklist (minimum 5 elements).
3. **Fixtures** — small real target (MR <10 files; incident window with known service; deployment with metrics).
4. **Script self-test** — pytest/shellcheck/py_compile where scripts exist.
5. **Failure diagnosis** — MCP disconnected vs skill regression table.
6. **Link to pressure-tests** — maintainer deep scenarios.

### 5.5 `examples-conventions.md` — outline

1. **Required sections** — invocation table, happy path, degraded path, handoff example.
2. **Scenario format** — User says → agent actions → output fragments (fenced).
3. **Minimum counts** — 8 invocation rows, 3 scenarios, 1 wrong-skill example.
4. **Cross-linking** — examples reference workflow phases by name (phase-glossary).
5. **Anti-patterns** — examples that only show CLI commands without expected output.

### 5.6 `phase-glossary.md` — outline

1. **Shared phase names** — Detect (0), Gather/Collect (1), Analyze/Reason (2), Correlate (3), Rank/Validate (4), Report/Render (5).
2. **pr-review mapping** — Phase 0–5 + posting + gate.
3. **incident-rca mapping** — Phase 0, 0b, 1–5.
4. **k8s mapping** — COLLECT, NORMALIZE, REASON, VALIDATE, BUILD_GRAPH, VALIDATE_INVARIANTS, RENDER.
5. **Cross-skill analogies** — “pr-review Phase 1 ≈ k8s COLLECT ≈ rca Phase 1”.
6. **Artifact glossary** — `review_boundary`, `error_signals`, `decision_graph`, etc.

---

## 6. Per-skill gap closure plan

Priorities from [2026-06-30-skills-gap-analysis-round-3.md](./2026-06-30-skills-gap-analysis-round-3.md) plus **framework compliance** items (F-*). Implementation details in `docs/superpowers/plans/2026-06-30-*-round3-gaps.md`.

### 6.1 pr-review (reference — polish only)

| Priority | ID | Gap | Action |
|----------|-----|-----|--------|
| P1 | P1-4 | Revert MR detection absent | Add detection in `workflow/phase-1.md`, §19 in `phase-2.md`, pressure tests |
| P2 | P2-4 | Mixed bot+human MR | Human commit detection in phase-1; split profile in `fast-path.md` |
| P2 | P2-5 | CODEOWNERS approval not enforced | Cross-check in `workflow/phase-5.md` |
| P3 | P3-3 | OpenAPI/Proto spec changes | §20 in `phase-2.md` |
| F1 | — | Link to shared framework | Add SETUP.md + SKILL.md links to `docs/skill-framework/` |
| F2 | — | Escalation table dedup | Replace inline table with link + skill-specific rows only |
| F3 | — | Confidence bands link | Reference shared doc from `executive-summary.md` |

### 6.2 incident-rca (largest compliance lift)

| Priority | ID | Gap | Action |
|----------|-----|-----|--------|
| P1 | P1-3 | `slo_breach` path when logs missing | Fallback block in `workflow/phase-1.md` (traces, burn rate, war-room) |
| P2 | P2-2 | Phase 0b window backstroke | `analysis_from_time = from_time − 15m` in `phase-0b.md` |
| P2 | P2-3 | Runbook lookup duplication | Dedup tags `phase_1_preliminary` across phase-1 / phase-4 |
| P3 | P3-1 | PagerDuty/OpsGenie absent | Phase-0 detection + `query-playbook.md` recipes |
| F1 | — | Framework links | SETUP.md, SKILL.md → shared library |
| F2 | — | Examples depth | Expand `examples.md` to pr-review bar (≥8 invocations, 3 scenarios) |
| F3 | — | MCP matrix completeness | Grafana/Prometheus path or explicit “not supported” degraded row |
| F4 | — | `make lint-incident-rca` framework | Add optional link lint to shared docs |

### 6.3 k8s-overprovisioning-datadog

| Priority | ID | Gap | Action |
|----------|-----|-----|--------|
| P1 | P1-1 | KEDA metric collection undefined | `OBS_KEDA_*` IDs, `collect-metrics.md`, `replica-analysis.md` |
| P1 | P1-2 | Limit/request ratio not analyzed | Collect limits; cpu/memory analysis sections |
| P2 | P2-1 | VPA+HPA conflict | `reason.md` STOP_REASON + collect manifest check |
| P3 | P3-2 | APM confidence modifier | Optional APM collect; `confidence.md` −0.15 rule |
| F1 | — | Dedicated `reference/smoke-test.md` | Extract from `workflow/render.md#smoke-test` |
| F2 | — | `lazy-load-index.md` | Add if absent; mirror pr-review pattern |
| F3 | — | Framework links + confidence bands | Map numeric formula to shared categorical |
| F4 | — | Examples cross-skill | Handoff to/from incident-rca in `examples.md` |

---

## 7. Implementation phases

Ordered work packages. Each phase ends with `make lint` green and updated pressure-test rows for touched gaps.

### Phase 1 — Shared framework docs (this spec + library)

**Deliverables:**

- This design spec (complete)
- `docs/skill-framework/README.md`
- Full content for all six `shared/*.md` files (expand stubs to normative prose)
- `make lint-framework` in root `Makefile`:
  - All six shared files exist
  - README links resolve
  - Each skill’s `SETUP.md` contains `docs/skill-framework` link (after Phase 2–4)

**Exit criteria:** Shared docs are self-contained; an agent can comply without reading pr-review internals.

### Phase 2 — incident-rca compliance

**Order:** F1/F2 → P2-2 → P1-3 → P2-3 → P3-1 → F3/F4

**Deliverables:**

- Round 3 rca gaps closed per `docs/superpowers/plans/2026-06-30-rca-round3-gaps.md`
- Framework checklist §4 satisfied for incident-rca
- `make lint-incident-rca` passes

### Phase 3 — k8s compliance

**Order:** F1/F2 → P1-1 → P1-2 → P2-1 → P3-2 → F3/F4

**Deliverables:**

- Round 3 k8s gaps closed per `docs/superpowers/plans/2026-06-30-k8s-round3-gaps.md`
- Framework checklist §4 satisfied for k8s
- `make lint-k8s-skill` passes

### Phase 4 — pr-review polish

**Order:** P1-4 → P2-4 → P2-5 → P3-3 → F1–F3

**Deliverables:**

- Round 3 pr-review gaps closed per `docs/superpowers/plans/2026-06-30-pr-review-round3-gaps.md`
- Inline escalation table trimmed to skill-specific rows + shared link
- `make lint-pr-review` passes (skill + scripts + pytest)

---

## 8. Success criteria

Measurable outcomes after Phases 1–4:

| Criterion | Measurement |
|-----------|-------------|
| Lint green | `make lint` exits 0 (all three skills + shellcheck + framework) |
| pr-review skill | `make lint-pr-review` — SKILL ≤180 lines, workflow frontmatter, anchors, pytest |
| k8s skill | `make lint-k8s-skill` — SKILL ≤150 lines, schema v3, ≥14 templates, memory p95 guard |
| incident-rca | `make lint-incident-rca` — SKILL ≤180 lines, valid `evidence.example.json`, anchors |
| Framework lint | `make lint-framework` — shared docs present; skills link to README |
| Checklist | All §4 items checked for each skill (tracked in PR description) |
| Gap closure | 12/12 Round 3 gaps addressed (4 per skill) |
| Cross-skill | `cross-skill-escalation.md` matrix matches all three `SKILL.md` tables |
| Confidence | Spot-check: same incident described in rca (MEDIUM) and k8s (0.7) maps to same band per shared doc |
| Smoke | Maintainer can run three smoke tests from shared conventions in <30 minutes |
| No drift | `SKILL.md` cross-skill sections ≤10 rows each; detail in shared doc |

### Proposed `make lint-framework` (Phase 1)

```makefile
lint-framework:
	@test -f docs/skill-framework/README.md
	@for f in confidence-bands cross-skill-escalation post-action-templates \
		smoke-test-conventions examples-conventions phase-glossary; do \
		test -f docs/skill-framework/shared/$$f.md || exit 1; \
	done
	@grep -q 'confidence-bands' docs/skill-framework/README.md
	@echo "lint-framework: ok"
```

Optional Phase 2+ enhancement: fail if `pr-review/SETUP.md`, `incident-rca/SETUP.md`, `k8s-overprovisioning-datadog/SETUP.md` lack `skill-framework` substring.

---

## 9. Out of scope

The unified framework explicitly does **not** cover:

| Topic | Reason |
|-------|--------|
| **New skills** beyond the trio | Framework is validated on three; fourth skill is a follow-on |
| **Cursor plugin skills** (`~/.cursor/plugins/cache/...`) | Out of repo; not installable via `scripts/install.sh` |
| **Runtime code / correlator CLI** | incident-rca Python correlator remains optional; framework is markdown-first |
| **MCP server implementation** | Skills consume MCPs; they do not ship servers |
| **Auto-invocation / skill routing** | Skills use `description` + optional `disable-model-invocation`; pr-review auto-invokes on clear MR-review phrases; no global router agent |
| **GitHub PR support** | pr-review is GitLab-only by design |
| **Live remediation** | rca and k8s remain read-only; no kubectl apply, no rollback execution |
| **i18n / localization** | English-only prose |
| **Versioned skill publishing** | No npm/pypi; symlinks from monorepo |
| **Round 1–2 gaps already closed** | Only Round 3 + framework compliance in scope unless regression found |
| **UI/automation beyond templates** | Jira/Slack/canvas are templates; no webhook automation |

---

## Appendix A — Self-review log

| Check | Result |
|-------|--------|
| No TBD/TODO placeholders | Confirmed |
| Paths match repo layout | `pr-review/`, `incident-rca/`, `k8s-overprovisioning-datadog/` at repo root |
| Approach A+C documented with rationale | §2 |
| All 9 required sections present | §1–§9 |
| Round 3 gaps mapped to per-skill plan | §6 (12 items) |
| `make lint-*` targets match Makefile | §8 (line budgets, pytest, schema v3) |
| Shared library outlines complete | §5.1–§5.6 |
| pr-review as reference bar | §3, §4.10, §6.1 |
| Contradictions pr-review date vs filename | Filename `2025-06-30` per request; gap analysis refs `2026-06-30` (repo convention) — both cited explicitly |

---

## Appendix B — Related documents

- [2026-06-30-skills-gap-analysis-round-3.md](./2026-06-30-skills-gap-analysis-round-3.md)
- [2026-06-30-pr-review-round3-gaps.md](../plans/2026-06-30-pr-review-round3-gaps.md)
- [2026-06-30-rca-round3-gaps.md](../plans/2026-06-30-rca-round3-gaps.md)
- [2026-06-30-k8s-round3-gaps.md](../plans/2026-06-30-k8s-round3-gaps.md)
- [docs/skill-framework/README.md](../../skill-framework/README.md)
