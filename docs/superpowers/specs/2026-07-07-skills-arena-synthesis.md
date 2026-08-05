# Skills Arena — Synthesis Note

**Date:** 2026-07-07  
**Artifact:** [2026-07-07-skills-arena-improvements.md](2026-07-07-skills-arena-improvements.md)

## Base

**Candidate 3** (composer-2.5-fast) — only complete candidate.

| Rubric | Score | Notes |
|--------|-------|-------|
| R1 Grounded in current repo | ✅ | File citations verified for top 5 items |
| R2 Safety-first ordering | ✅ | P1 INV-12, rca temporal, domain lint ranked correctly |
| R3 Actionable | ✅ | Each gap names files/phases |
| R4 Cross-skill coherence | ✅ | Confidence/metadata drift matrix |
| R5 Lazy senior bar | ✅ | Rejected framework extraction, Grafana MCP, HARD STOP pagination |
| R6 No stale duplicates | ✅ | Closed table for June/Round 3 items |

**Score:** 5.5/6 — minor deduction for vendored kubesense LOW confidence (appendix only).

## Dropouts

None — all three candidates completed (C1/C2 arrived after initial synthesis).

| Candidate | Model | Output |
|-----------|-------|--------|
| C1 | claude-opus-4-8-thinking-high | `IMPROVEMENTS.md` + `RATIONALE.md` |
| C2 | gpt-5.3-codex-high-fast | `IMPROVEMENTS.md` + `RATIONALE.md` |
| C3 | composer-2.5-fast | `IMPROVEMENTS.md` + `RATIONALE.md` (base) |

Cross-judge skipped — parent triaged convergence below.

## Cross-candidate convergence (3/3)

**Unanimous:** June P0–P2 gaps in pr-review / incident-rca / k8s are **closed**; remaining work is framework drift, lint asymmetry on newer skills, and capability extensions — not re-litigating old backlog.

**Strong agreement (2–3/3):**
- Framework `confidence-bands` + `assessment_metadata` incomplete for domain/mysql/squad
- domain-comprehension needs deeper machine validation (`--check-content`, content heuristics)
- pr-review CVE/dependency coverage weak when CI scans absent
- incident-rca OSS path degraded vs Datadog; correlator CLI optional → variance
- mysql scan blind spots + weak P0 shadow-verify bar

**Rank divergence (all valid, complementary):**

| Rank | C1 | C2 | C3 |
|------|----|----|-----|
| #1 | Framework link-lint (CF-1/2) | Confidence literal drift lint | domain `--check-content` lint |
| #2 | GPU + ephemeral-storage (k8s) | pr-review CVE fallback | k8s INV-12 enforcement |
| #3 | 6-skill glossary/confidence docs | OSS MCP adapters (rca) | Framework metadata convergence |

**C2-only grafts:** k8s deploy-freeze silent-skip vs `mcp-error-handling` policy; squad-map `squad_path_segment` guided preflight; correlator CLI as default install path.

## Late C1 addendum (grafts not in base report)

C1 converges with C3 on June gaps closed + framework drift. **Unique C1 findings worth a future pass:**

| ID | Item | Tier |
|----|------|------|
| CF-1/CF-2 | Framework dangling-link lint gap + fence-skipping false positives in `lint-dangling-md-links.sh` | P0 tooling |
| K8S-N1/N2 | GPU + ephemeral-storage sizing absent in k8s | P1 |
| RCA-N1 | Multi-region / multi-cluster correlation absent in rca | P1 |
| PR-N1 | IaC/Terraform review profile absent in pr-review | P2 |
| SQL-N1 | P0 compliance flows need stricter than sample-only shadow compare | P1 |
| Meta | Mark `2026-06-29-skills-gap-analysis.md` **CLOSED** in docs | housekeeping |

C1 ranks **framework link-lint** #1; C3 ranks **domain `--check-content` lint** #1. Both are small, high-leverage — not mutually exclusive.

## Grafts (parent → base)

| From | Graft | Why |
|------|-------|-----|
| Parent | `make lint` green verification row in Phase F | Prove-it-works baseline |
| Parent | Explicit `phase-glossary.md` mysql omission confirmation | FW-NEW-1 spot-check |
| Parent | Makefile line refs for `--check-content` gap | DC-P1-1 precision |

## Rejections (from C3 rationale, accepted)

| Proposal | Rejected because |
|----------|------------------|
| Re-open June P0 gaps | Shipped — grep + pressure tests confirm |
| Grafana MCP native support | Large integration; oss-obs exists |
| squad-map HARD STOP on pagination | Blocks large orgs; downgrade preferred |
| Semantic shadow-compare in mysql lint | Needs live DB fixtures; process not lint |
| Approach B shared validator framework | Roadmap deferred until 3rd consumer |

## Verification

- `make lint`: **PASS** (2026-07-07)
- Top-5 spot-checks: **4/5 confirmed** in repo files; item 5 (mysql domain pack) is design-only (not yet implemented — expected)

## Next action

Implement rank #1 (domain lint `--check-content` in Makefile) as smallest ROI MR unless user prioritizes k8s INV-12 ops safety first.
