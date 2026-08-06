# Lazy-load index

Load **one reference file at a time** when the active workflow phase points to it.

| When | Read |
|------|------|
| Any phase — non-negotiable rules | [skill-contract.md](skill-contract.md) |
| Any phase — shared test-creation rules (test-first evidence, refactor limits, escalation) | [test-creation-principles.md](../../docs/skill-framework/shared/test-creation-principles.md) |
| Select targets §4 — prioritizing backfill targets + response-shape corroboration when domain-comprehension's `API_CATALOG.md` exists (optional) | [domain-comprehension-integration.md](../../docs/skill-framework/shared/domain-comprehension-integration.md) |
| Detect conventions — marker files, confidence levels, the canonical-collection ambiguity rule, resolution order | [framework-detection.md](framework-detection.md) |
| Any phase — HARD STOPs and live gates | [gate-policy.md](gate-policy.md) |
| Generate tests — what makes an API test acceptable (deltas only) | [test-quality-deltas.md](test-quality-deltas.md) |
| Report — `API_TEST_REPORT.md` structure | [report-format.md](report-format.md) |
| Post-install check | [smoke-test.md](smoke-test.md) |
| Editing this skill — regression scenarios | [pressure-tests.md](pressure-tests.md) |

Framework: [skill-routing.md](../../docs/skill-framework/shared/skill-routing.md) ·
[cross-skill-escalation.md](../../docs/skill-framework/shared/cross-skill-escalation.md) ·
[prompt-injection.md](../../docs/skill-framework/shared/prompt-injection.md)
