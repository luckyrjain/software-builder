# Smoke test — expected minimal output

Run after install and after any edit to `SKILL.md`, `workflow/`, or `reference/`.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

## Invocation

> `request: "write tests for the payments module"`, `repo_root: <path>`

## A correct minimal output contains

1. **No detection or generation output of its own** — test-writer never prints framework detection,
   target lists, or written test files; that is the dispatched skill's own Phase 0/1 output.
2. **A classification decision announced first** — either the resolved `level` (unambiguous match or
   `level_hint`), or a live question listing the real candidate levels when ambiguous.
3. **Exactly one dispatch** — one of unit-test-creator / integration-test-creator /
   contract-test-creator / e2e-test-creator / api-test-creator invoked, never more than one per request.
4. **The dispatched skill's own report relayed verbatim** — `UNIT_TEST_REPORT.md` /
   `INTEGRATION_TEST_REPORT.md` / `CONTRACT_TEST_REPORT.md` / `E2E_TEST_REPORT.md`, unmodified.
5. **No re-summarization** — test-writer's own chat output does not restate or paraphrase the dispatched
   report's findings differently than the report itself states them.

## Failure diagnosis

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Two skills both invoked for one request | Classify's "ask once" gate skipped instead of asking on an ambiguous match | Re-check [workflow/classify.md](../workflow/classify.md) §3 |
| A framework/tooling detection line appears in test-writer's own output | Detection logic leaked back into this router | This router must have zero detection logic — check nothing in `workflow/delegate.md` re-implements a dispatched skill's own Phase 0 |
| Report looks reformatted from the dispatched skill's own | Regression in relay behavior | Re-check [workflow/delegate.md](../workflow/delegate.md) §2 |
| `unit` chosen for a request that clearly needed a real dependency | Level-classification keyword table not consulted, or an unlisted "unambiguous default" invented | Re-check [reference/level-classification.md](level-classification.md) — only its two listed default cases skip asking |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
