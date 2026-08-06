---
workflow_version: 2.0
phase: classify
produces:
  - level
consumes:
  - request
  - level_hint
---

# Classify — resolve the request to exactly one level

Match `request` against [reference/level-classification.md](../reference/level-classification.md)'s
keyword table — the same trigger phrases [skill-routing.md](../../docs/skill-framework/shared/skill-routing.md)
uses to route callers directly to each `*-test-creator` skill.

## 1. `level_hint` resolves without asking

If `level_hint` is set to `unit`, `integration`, `contract`, or `e2e`, use it directly — the caller
already resolved the ambiguity. Skip §2.

## 2. Unambiguous match — proceed without asking

If `request`'s keywords match exactly one level in
[reference/level-classification.md](../reference/level-classification.md), set `level` to that match and
proceed to Delegate.

## 3. Ambiguous or no match — ask once, never guess

Two situations both land here, and both are a live gate — never default to `unit` as a "safe" fallback:

- **Multiple levels match** (e.g. "test the payments flow" could mean an integration test of the
  payment-processing seam or an e2e test of the checkout journey) — ask which, listing the real
  candidates that matched.
- **No level matches at all** (the request is too vague to classify, e.g. just "write tests") — ask the
  caller to describe the level directly: "unit (isolated, mocked), integration (a real dependency),
  contract (Pact-style consumer/provider), or e2e (browser journey)?"

Never proceed to Delegate with a guessed level. A wrong-level dispatch produces the wrong *kind* of test
entirely (e.g. a mocked unit test when the caller needed a real-dependency integration test) — this is
not a cosmetic error to fix downstream.

## 4. Level already named in the invocation

If the calling context already named a level explicitly (see
[workflow/inputs.md § Embedded invocation](inputs.md#embedded-invocation)), this phase should not have
been reached — that request should have gone directly to the matching skill. If it is reached anyway
(e.g. embedded in a larger free-text request), treat the named level exactly like a resolved `level_hint`
— no asking.
