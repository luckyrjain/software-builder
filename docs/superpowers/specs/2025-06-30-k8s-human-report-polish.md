# k8s human-report polish (7 items)

**Skill:** `k8s-overprovisioning-datadog`  
**Date:** 2025-06-30  
**Scope:** Human Report presentation only — graph schema, INV-01–INV-12, and appendix ID tables unchanged unless slug additions require report-schema updates.

---

## Item 1 — Lead with **Recommendation**, not **Verdict**

**Files:** `templates/human-report.md`, `report-template.md`, `render/markdown.md`, `workflow/report.md:md`, `reference/report-schema.md`, `templates/index.md`, `examples.md`, `README.md`

**Change:** Section heading `## Recommendation`; block opens with `{emoji} Recommendation` (not `Decision` / `Verdict`). Map `assessment.final_decision` to action verbs. Severity, assessment confidence, and review cadence follow the action line.

---

## Item 2 — Replace **Blocked** on **keep** recommendations

**Files:** `templates/human-report.md`, `render/markdown.md`, `thresholds.md`, `report-template.md`, `workflow/report.md`, `reference/recommendation-ids.md`

**Change:** Split human State mapping by rec intent:

| Graph `status` | Rec pattern | Human State |
|----------------|-------------|-------------|
| `BLOCKED` | `REC_*_KEEP`, `REC_*_OBSERVE` | **Decision: Keep** or **Recommended** |
| `BLOCKED` | change rec blocked by STOP_REASON | **Blocked** |
| `READY` / `COMPLETED` | actionable change | **Ready** |
| `DEFERRED` | | **Defer** |
| `REJECTED` | | → Item 3 section |

Graph `BLOCKED` on `REC_CPU_KEEP` unchanged.

---

## Item 3 — Section: **Changes evaluated but not recommended**

**Files:** `templates/human-report.md`, `report-template.md`, `render/markdown.md`, `reference/report-schema.md`, `templates/index.md`, `thresholds.md`, `reference/decision-graph.example.yaml`, `examples.md`

**Change:** New Human Report slug after Recommendations, before Risks. Render `recommendations[]` where `status == REJECTED` only here — not inline as Blocked.

**Golden graph:** Add `REC_CPU_REDUCE` with `status: REJECTED` to `decision-graph.example.yaml`.

---

## Item 4 — Evidence table ordering

**Files:** `templates/human-report.md`, `render/markdown.md`, `report-template.md`, `reference/smoke-test.md`, `reference/pressure-tests.md`

**Normative order:**

1. Fleet CPU p95  
2. Kafka consumer lag  
3. Memory peak (worst pod)  
4. HPA (min / max / current)  
5. CPU average (7d)  
6. HTTP metrics (latency, error rate, RPS)  
7. Pod restarts (7d)  
8. Manifest drift  

CPU throttle rate: Notes column under p95, not a separate sort tier.

---

## Item 5 — Risks: one-sentence overall framing first

**Files:** `templates/human-report.md`, `report-template.md`, `workflow/report.md`, `render/markdown.md`

**Change:** Risks section opens with `Overall: {one sentence}` before impact-ordered bullets.

---

## Item 6 — Hide confidence math; show band + basis bullets

**Files:** `workflow/report.md`, `templates/human-report.md`, `report-template.md`, `render/markdown.md`, `reference/confidence-formula.md`, `templates/metadata.md`

**Human Report:**

```text
Assessment confidence: Very High (0.9)

Basis:
• Evidence completeness — …
• Evidence quality — …
• Telemetry coverage — …
• Contradiction resolution — …
```

**Never in Human Report:** `0.35×…`, `arithmetic` string, weighted-sum lines. Graph `assessment.assessment_confidence.arithmetic` unchanged for INV-07.

Per-rec: `Decision confidence: Very High (0.9)` — no per-rec formula in human body.

---

## Item 7 — End with **Conclusion**; ban agent mode instructions

**Files:** `templates/human-report.md`, `report-template.md`, `reference/report-schema.md`, `render/markdown.md`, `workflow/report.md`, `reference/smoke-test.md`, `SKILL.md`, `templates/index.md`

**Change:** New slug `Conclusion` — last Human Report section before `---`. 2–4 sentences restating recommendation, key constraint, review cadence.

**Prohibition:** Human Report MUST NOT include agent mode instructions (e.g. "Type ACT"), posting confirmations, or MCP setup steps. Post-render chat instructions live in `SKILL.md` and `post-action-templates.md`.

---

## Implementation order

1. Item 4 — evidence sort  
2. Item 6 — confidence display  
3. Item 1 — Recommendation lead  
4. Items 2 + 3 — state vocabulary + rejected section  
5. Item 5 — risks framing  
6. Item 7 — Conclusion + ACT prohibition  
7. Update smoke-test, pressure-tests, examples golden outputs  

---

## Consolidated file touch list

| File | Items |
|------|-------|
| `templates/human-report.md` | 1–7 |
| `report-template.md` | 1–7 |
| `render/markdown.md` | 1–7 |
| `workflow/report.md` | 1, 2, 5, 6, 7 |
| `reference/report-schema.md` | 1, 3, 7 |
| `templates/index.md` | 1, 3, 7 |
| `thresholds.md` | 2, 3 |
| `examples.md` | 1–7 |
| `reference/smoke-test.md` | 4, 6, 7 |
| `reference/pressure-tests.md` | 1–7 |
| `reference/confidence-formula.md` | 6 |
| `templates/metadata.md` | 6 |
| `reference/decision-graph.example.yaml` | 3 |
| `reference/recommendation-ids.md` | 2 |
| `README.md` | 1 |
| `SKILL.md` | 7 |

**No edits:** `scripts/validate_decision_graph.py`, `reference/invariants.md`, `workflow/validate-invariants.md`.
