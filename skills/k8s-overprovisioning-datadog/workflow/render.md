---
workflow_version: 3.5
phase: render
produces: {dora_report: content, decision_graph_json: object}
consumes:
  required: {validated_graph: object}
  optional: {}
  conditional: {}
---

# Render

**RENDER phase** — after VALIDATE_INVARIANTS. **No reasoning here** — only transform `decision_graph`.

Default: **markdown** DORA with **Human Report + Technical Appendix**. Optional: **summary-only** markdown or **json** export.

| Renderer | Spec |
|----------|------|
| Markdown full (default) | [render/markdown.md](../render/markdown.md) → Human Report + Appendix |
| Markdown summary-only | Human Report only — [workflow/report.md](report.md#full-dora-vs-summary-only-mode) |
| JSON | [render/json.md](../render/json.md) |
| Slack / HTML / PDF | [render/README.md](../render/README.md) — not implemented in skill |

Presentation rules (human-first, ID hiding, confidence bands): [report.md](report.md).

**Also load now:** [gold-human-report-excerpt.md](../reference/gold-human-report-excerpt.md) — format
few-shot (match shape, not content).

## Pre-render attestation (required)

Print this checklist before authoring markdown. Every box must be checked or annotated N/A:

```markdown
### Pre-render attestation
- [ ] `invariant_violations[]` empty (critical) — or rendering blocked per validate-invariants
- [ ] All READY cut recs passed projection gate ([validate.md](../workflow/validate.md))
- [ ] No unresolved contradictions with cut `REC_*` in READY
- [ ] Human Report body will contain < 20 uppercase schema IDs
- [ ] READY actionable recs have `delivery_pointer.path` (INV-12 critical)
```

If any critical item fails → **do not render** Human Report; emit graph + violations or blocked state.

## Procedure

1. Load `validated_graph`
2. Select renderer:
   - User asks for JSON → `json`
   - User asks for summary / no appendix → `markdown` + `summary_only`
   - Else → `markdown` + `full`
3. Map graph paths to Human Report sections; translate IDs to labels ([render/markdown.md](../render/markdown.md#label-translation))
4. If full mode: append Technical Appendix (Decision Graph → Evidence Registry → metadata/validation) after `---`
5. Title: **Deployment Optimization Readiness Assessment**

## Smoke test

Run checklist in [reference/smoke-test.md](../reference/smoke-test.md). Re-run after any skill edit.

Replaces v2 `REPORT`-as-authoring. Graph is built in [build-graph.md](build-graph.md).
