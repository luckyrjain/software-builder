# Deployment Optimization Readiness Assessment

**Graph-first (v3.3).** Do not author markdown directly.

## Workflow

1. Build `decision_graph` per [reference/decision-graph-schema.md](reference/decision-graph-schema.md)
2. Validate [reference/invariants.md](reference/invariants.md)
3. Load [reference/gold-human-report-excerpt.md](reference/gold-human-report-excerpt.md) — **format few-shot for RENDER**
4. Render via [render/markdown.md](render/markdown.md) (default) or [render/json.md](render/json.md)

Example graph: [reference/decision-graph.example.yaml](reference/decision-graph.example.yaml)

## Output layers

Every full DORA has two layers. Think **AWS Trusted Advisor**: human summary first, technical details in an appendix.

| Layer | Audience | Default? | Length |
|-------|----------|----------|--------|
| **Human Report** | Staff engineers, SREs, platform engineers, EMs, directors, service owners | Yes — primary deliverable | ~2–4 pages |
| **Technical Appendix** | Auditors, automation, debugging, repeat assessments | Full DORA: always appended; summary-only mode: omit | As needed |

Rendering rules: [workflow/report.md](workflow/report.md).

---

## Human Report (primary)

**Authoritative section spec:** [render/markdown.md § Human Report](render/markdown.md) ·
[templates/human-report.md](templates/human-report.md) ·
[reference/report-schema.md](reference/report-schema.md).

During live assessments, load **gold excerpt +** [workflow/report.md](workflow/report.md) — do not
bulk-load extended examples here.

---

## Technical Appendix (audit / debug)

**Authoritative section spec:** [render/markdown.md § Technical Appendix](render/markdown.md) ·
[templates/appendix.md](templates/appendix.md) ·
[reference/report-schema.md](reference/report-schema.md).

---

## Human-report rules

Normative presentation rules: [workflow/report.md](workflow/report.md#human-first-rules) ·
[recommendation-framework.md](recommendation-framework.md).
