# Lazy-load index

Load **one reference file at a time** when the active workflow phase points to it.

| When | Read |
|------|------|
| Any phase — non-negotiable rules | [skill-contract.md](skill-contract.md), plus the shared [test-creation-principles.md](../../docs/skill-framework/shared/test-creation-principles.md) it links to |
| Detect conventions — marker files, confidence levels, ambiguity/no-tooling gates | [framework-detection.md](framework-detection.md) |
| Any phase — HARD STOPs and live gates | [gate-policy.md](gate-policy.md) |
| Generate tests — what makes a test acceptable (e2e-specific deltas) | [test-quality-deltas.md](test-quality-deltas.md) |
| Report — `E2E_TEST_REPORT.md` structure | [report-format.md](report-format.md) |
| Post-install check | [smoke-test.md](smoke-test.md) |
| Editing this skill — regression scenarios | [pressure-tests.md](pressure-tests.md) |

Framework: [skill-routing.md](../../docs/skill-framework/shared/skill-routing.md) ·
[cross-skill-escalation.md](../../docs/skill-framework/shared/cross-skill-escalation.md) ·
[prompt-injection.md](../../docs/skill-framework/shared/prompt-injection.md)
