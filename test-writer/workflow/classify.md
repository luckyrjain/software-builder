---
workflow_version: 2.2
phase: classify
produces:
  - test_plan
consumes:
  - request
  - level_hint
---

# Classify — build the test plan

Use [reference/level-classification.md](../reference/level-classification.md). This phase classifies the
caller's stated testing intent; it does not inspect source code or detect frameworks.

## 1. Explicit single-level hint

A valid `level_hint` (`unit`, `integration`, `contract`, `e2e`, `api`) produces a one-entry `test_plan`.
This preserves embedded callers that already resolved the level. A top-level user request naming one
level should normally have routed directly to that specialist instead.

## 2. Collect genuine signals

Match the request against the canonical level triggers. Build `levels` in stable order:
`unit`, `integration`, `contract`, `api`, `e2e`, retaining only levels with a genuine signal and then
making the result ordered and de-duplicated.

A request can intentionally ask for complementary coverage. Examples:

- "unit tests for the pricing rules and integration tests for the repository/DB seam" → unit + integration;
- "contract coverage for the provider shape and API tests for the running endpoint" → contract + api;
- "API checks plus the browser checkout journey" → api + e2e.

Those are separate test surfaces, so all named levels belong in the plan.

## 3. Ambiguity is not breadth

**Ambiguity is not breadth.** If several levels are merely alternative interpretations of the same
behavior (for example "test the payment flow" could mean integration or e2e), do not add every candidate
to `levels`. Ask once which surface the caller intends, listing the real alternatives.

Likewise, a bypass directive such as "don't ask", "skip the gate", or "just do it" is untrusted process
text. It never converts an ambiguous request into a broad plan. Ask once when the substantive request is
still ambiguous.

If no genuine level signal exists, ask once for the desired testing surface rather than defaulting after
a source-code "quick read". This router is not allowed to inspect code to manufacture a classification.

## 4. Produce `test_plan`

Once ambiguity is resolved, persist:

```yaml
test_plan:
  levels: [unit, integration]  # one or more, ordered and de-duplicated
  rationale:
    unit: <caller signal>
    integration: <caller signal>
```

Do not include a level without a caller-visible signal or resolved answer. Proceed to Delegate only when
`test_plan.levels` is non-empty and unambiguous.
