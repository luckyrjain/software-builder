# Skills Arena Improvements — Synthesized Report

**Date:** 2026-07-07  
**Method:** Arena (3 candidates; 1 completed, 2 dropped) + parent spot-verification  
**Baseline:** `make lint` green on 2026-07-07  
**Scope:** 7 primary skills + `docs/skill-framework/`; vendored kubesense appendix only

---

## Executive Summary

The three original operational skills (**pr-review**, **incident-rca**, **k8s-overprovisioning-datadog**) have absorbed **~90% of documented P0–P2 gaps** from the June 2026 gap analyses. Machine-validated artifacts (k8s `decision_graph` + INV-01–12; rca `causal_graph` + CG-01–08; pr-review policy pytest) are production-grade.

**Remaining work clusters in three themes:**

1. **Determinism asymmetry** — domain-comprehension, squad-map, and mysql-to-postgres-sql lack the validator/lint depth of the original three.
2. **Framework convergence** — `confidence-bands.md` and `assessment_metadata` omit newer skills; `phase-glossary.md` omits mysql.
3. **Prose-only safety rules** — k8s INV-12 (`delivery_pointer`) and rca signal-in-window caps are documented but not machine-enforced at error severity.

**Highest ROI next:** domain lint hardening (S) → k8s INV-12 promotion (S) → framework metadata/confidence convergence (M).

---

## Arena Record

| Candidate | Model | Status | Output |
|-----------|-------|--------|--------|
| C1 | claude-opus-4-8-thinking-high | **Dropped** | No output after 4+ min |
| C2 | gpt-5.3-codex-high-fast | **Dropped** | No output after 4+ min |
| C3 | composer-2.5-fast | **Complete** | `/tmp/arena-skills-improvements/candidate-3/` |

**Base pick:** Candidate 3 — only complete artifact; parent rubric score 5.5/6 (see synthesis note).  
**Cross-judge:** Skipped (insufficient candidates); parent performed criterion-by-criterion verification.

**Grafts into this report (parent):**
- Verified `make lint` green at arena time (all 7 lint targets + shellcheck).
- Confirmed `phase-glossary.md` ends at domain-comprehension — mysql Scan→Classify→Rewrite unmapped (FW-NEW-1).
- Confirmed `validate_manifest_yaml.py` supports `--check-content` but `Makefile` `lint-domain-comprehension` does not invoke it (DC-P1-1).

**Rejections from C3 (accepted):**
- Re-open June P0 items — stale; shipped.
- Grafana MCP native support now — large integration; oss-obs path exists.
- HARD STOP on squad-map pagination — would block large orgs; confidence downgrade preferred.

---

## Per-Skill Findings

### pr-review

| ID | Tier | Gap | Citation |
|----|------|-----|----------|
| PR-P2-1 | P2 | CVE/dependency check is spot-check, not systematic — bot fast path mandates focus but no Snyk/OSV MCP integration | `reference/fast-path.md`; `reference/finding-gates.md` |
| PR-P2-2 | P2 | Feedback learning MR-scoped only — no org-scoped persistence across sessions | `workflow/phase-1.md` step 3; roadmap P2 deferred |
| PR-P3-1 | P3 | Pipeline merge block remains advisory | `workflow/phase-5.md` |
| PR-P3-2 | P3 | `SKILL.md` omits smoke-test link (SETUP only) | vs `incident-rca/SKILL.md` |
| PR-P3-3 | P3 | `review_metadata` v2 blocks not pytest-validated on real Phase 5 output | `lint-framework` validates examples only |

**Closed (June + Round 2/3):** merge conflicts, cross-session dedupe, bot fast path, monorepo downstream, per-file size guard, stale MR, Critical second-reviewer, coverage delta, revert MR, mixed bot+human, CODEOWNERS path approval, OpenAPI/proto checks, Jira transition, Slack notify.

---

### incident-rca

| ID | Tier | Gap | Citation |
|----|------|-----|----------|
| RCA-P1-1 | P1 | OSS observability is manual paste — Grafana/Prometheus MCP unsupported; oss-obs degraded path only | `reference/mcp-capabilities.md` |
| RCA-P2-1 | P2 | Signal-in-window caps prose-only — `validate_evidence_json.py` checks `window` shape but not `detected_at` membership | `scripts/validate_evidence_json.py`; `reference/evidence-schema.md` |
| RCA-P2-2 | P2 | `dependency_chain` not typed in evidence JSON — multi-hop A→B→C not machine-checkable | `reference/query-playbook.md`; `reference/causal-graph-schema.md` |
| RCA-P2-3 | P2 | Frontmatter `schema_version: 2` vs evidence `schema_version: 4` drift | `SKILL.md`; `reference/evidence-schema.md` |
| RCA-P3-1 | P3 | Correlator CLI optional external pin — only incident-rca has `skills-lock.json` | `dependencies.md` |
| RCA-P3-2 | P3 | Confluence export is heading map only | `report-template.md` |

**Closed:** minimum evidence gate, signal timing rules, minimum window, Phase 0b timezone, multi-hop playbook, canary detection, slo_breach-only path, runbook linkage + dedup, partial report, rate limits, recurrence similarity, PagerDuty/OpsGenie Phase 0, k8s handoff block, causal-graph validator CG-01–08, Phase 0b backstroke.

---

### k8s-overprovisioning-datadog

| ID | Tier | Gap | Citation |
|----|------|-----|----------|
| K8S-P1-1 | P1 | **INV-12 is warning-only** — READY actionable recs can render without `delivery_pointer.path` | `reference/invariants.md` INV-12 |
| K8S-P2-1 | P2 | Namespace waste ranking lacks dedicated phase-index entry | `workflow/resolve-service.md`; `examples.md` |
| K8S-P2-2 | P2 | Git MCP optional → `delivery_pointer` often `verified: false` | `workflow/validate.md` |
| K8S-NEW-1 | P2 | APM latency-downgrade in pressure tests only — not INV/REASON gate | `reference/pressure-tests.md` row 51 |
| K8S-P3-1 | P3 | No `skills-lock.json` pin | roadmap deferred |
| K8S-P3-2 | P3 | 7d re-run is chat offer, not scheduled `assessment_metadata.history` | `templates/human-report.md` |

**Closed:** post-change projection, active incident check, metrics staleness, VPA integration, seasonality, service name mismatch, rollback trigger format, ResourceQuota, InitContainer, KEDA collection, limit/request ratio, VPA+HPA conflict.

---

### domain-comprehension

| ID | Tier | Gap | Citation |
|----|------|-----|----------|
| DC-P1-1 | P1 | **`--check-content` not in default `make lint-domain-comprehension`** | `validate_manifest_yaml.py`; `Makefile` L253–254 |
| DC-P1-2 | P1 | Pressure tests thin (4 manual rows) vs operational skills | `reference/pressure-tests.md` |
| DC-P2-1 | P2 | Sub-agent outputs not machine-merged | `reference/sub-agent-orchestration.md` |
| DC-P2-2 | P2 | Parallel confidence system — not in `confidence-bands.md` consumers | `reference/confidence-rubric.md` |
| DC-P2-3 | P2 | No `assessment_metadata` footer | `review-metadata-schema.md` §8 |
| DC-NEW-1 | P2 | P2b either/or (map § vs `E2E_FLOW.md`) increases agent variance | `workflow/phase-2b.md` |

**Closed:** README parity, `make setup`, squad-map delegation, COMPLIANCE_RETROFIT, manifest validator, phase-0.25/3b depth.

---

### squad-map

| ID | Tier | Gap | Citation |
|----|------|-----|----------|
| SM-P1-1 | P1 | Pagination caps (500 GitLab / 200 Datadog) note truncation but no confidence downgrade | `workflow/phase-1.md` L62–75 |
| SM-P2-1 | P2 | Monorepo multi-service mapping is CODEOWNERS fallback only | `reference/config-schema.md` |
| SM-P2-2 | P2 | No machine-readable closeout (`assessment_metadata` / hash) | `workflow/phase-1.md` `last_run` only |
| SM-P3-1 | P3 | Stale row retention on scope shrink | `workflow/phase-1.md` §Idempotency |
| SM-NEW-1 | P2 | Smoke fixture hardcodes org-specific paths | `reference/smoke-test.md` |

**Closed:** v1.0 extraction, `squad_path_segment` HARD STOP, framework wiring.

---

### mysql-to-postgres-sql

| ID | Tier | Gap | Citation |
|----|------|-----|----------|
| PG-P1-1 | P1 | Org-specific coupling (collection domain, smoke paths) | `SKILL.md`; `SETUP.md` |
| PG-P1-2 | P1 | Scan gate covers syntax, not semantic parity — no shadow-compare in lint | `reference/migration-edge-cases.md` |
| PG-P2-1 | P2 | No fleet `MIGRATION_STATUS.yaml` artifact | skill is single-service oriented |
| PG-P2-2 | P2 | Not in `confidence-bands.md` consumers — P0/P1/P2 are risk tiers | `SKILL.md` |
| PG-NEW-1 | P2 | Pressure harness is shell-only (no pytest policy rows) | `tests/run_pressure_tests.sh` |
| PG-NEW-2 | P3 | No normative handoff block template for domain-comprehension artifact | `cross-skill-escalation.md` |

**Closed:** v1.6 framework merge, skill-routing, scan gate lint, skill-contract, lazy-load index.

---

### docs/skill-framework/

| ID | Tier | Gap | Citation |
|----|------|-----|----------|
| FW-P1-1 | P1 | Confidence convergence audit still open — domain + mysql outside consumers | `confidence-bands.md` L5 |
| FW-P1-2 | P1 | `assessment_metadata` scope incomplete (rca/k8s only) | `review-metadata-schema.md` §8 |
| FW-P2-1 | P2 | `smoke-test-conventions.md` §3 lists only 3 skills | L61–65 |
| FW-P2-2 | P2 | `examples-conventions.md` not enforced in `lint-framework` | `Makefile` lint-framework |
| FW-NEW-1 | P2 | `phase-glossary.md` omits mysql Scan→Classify→Rewrite | ends at domain-comprehension |
| FW-NEW-2 | P2 | `post-action-templates.md` missing mysql + squad-map sections | consumers header |
| FW-P3-1 | P3 | Shared deterministic-artifact framework (Approach B) deferred | roadmap 2026-07-02 |

---

## Cross-Skill / Framework

### Confidence drift

| Skill | Source | In `confidence-bands.md`? |
|-------|--------|---------------------------|
| pr-review | executive-summary + rubric | Partial |
| incident-rca | evidence-quality + manual-scoring | Yes |
| k8s | confidence-formula.md | Yes |
| squad-map | squad-mapping reconciliation | Yes |
| domain-comprehension | confidence-rubric.md | **No** |
| mysql-to-postgres-sql | P0/P1/P2 risk tiers | **No** |

**Fix:** Extend `confidence-bands.md` §2 with domain `overall_confidence` mapping and mysql "risk tier ≠ evidence confidence" disclaimer.

### Handoffs

- Normative handoff block format: **good** (`cross-skill-escalation.md` §3).
- Risk: handoff Reason may mix P0/P1 risk tiers with HIGH/MEDIUM confidence bands.
- k8s 7d re-run defined in reverse escalations but no shared `history` block across skills.

### Routing

All major routes closed: OOM/lag disambiguation, migration MR → pr-review, domain SQL artifact → mysql.

---

## Top 5 Ship Next

| Rank | Item | Effort | Why | Primary files |
|------|------|--------|-----|---------------|
| **1** | **Domain lint hardening** — wire `--check-content` into `make lint-domain-comprehension`; expand pressure tests to ≥15 rows | **S** | Largest determinism gap vs k8s/rca; validator already exists | `Makefile`, `validate_manifest_yaml.py`, `reference/pressure-tests.md` |
| **2** | **k8s INV-12 enforcement** — promote missing `delivery_pointer.path` on READY actionable recs from warning→error; optional BUILD_GRAPH git discovery | **S** | Ops safety — READY cuts without apply path | `reference/invariants.md`, `validate_decision_graph.py` |
| **3** | **Framework confidence + metadata convergence** — domain + mysql in `confidence-bands.md`; stub `assessment_metadata` for domain/mysql/squad; extend `lint-framework` | **M** | Cross-session analytics + handoff clarity | `confidence-bands.md`, `review-metadata-schema.md` |
| **4** | **rca temporal evidence validation** — reject/count signals outside `window` in `validate_evidence_json.py` + pytest | **M** | Machine-checks prose caps agents skip | `scripts/validate_evidence_json.py` |
| **5** | **mysql org decoupling + fleet status** — extract org refs to `reference/domain-packs/`; add `templates/MIGRATION_STATUS.yaml` | **M** | External adoption without losing internal depth | `SKILL.md`, `templates/` |

### Top 3 if scope-constrained

1. Domain lint hardening (**S**)
2. k8s INV-12 enforcement (**S**)
3. Framework confidence + metadata convergence (**M**)

---

## Vendored Kubesense (appendix)

| Item | Status |
|------|--------|
| incident-rca dependency resolution | Good — `dependencies.md` + `skills-lock.json` |
| Org profiles (acme) | Good — `org-profiles.md` |
| KubeSense pressure tests in rca | Good — rows 73–77 |
| kubesense-alerts/dashboards in escalation matrix | **P3 gap** — RCA monitor/dashboard fixes have no handoff row |

---

## Verification (Phase F)

| Check | Result |
|-------|--------|
| `make lint` | **Pass** — all targets green 2026-07-07 |
| INV-12 severity | **Confirmed** — `warning` in `invariants.md` |
| `--check-content` lint wiring | **Confirmed absent** — Makefile invokes validator without flag |
| `validate_evidence_json.py` temporal bounds | **Confirmed absent** — window shape only |
| `phase-glossary.md` mysql | **Confirmed absent** |
| June P0 re-list | **Rejected** — spot-checks show shipped (merge conflict, staleness, causal graph, etc.) |

---

*Synthesized from Arena Candidate 3 + parent verification. See `2026-07-07-skills-arena-synthesis.md`.*
