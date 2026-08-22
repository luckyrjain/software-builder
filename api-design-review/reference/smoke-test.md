# Smoke test — expected minimal output

Run after install or any edit to this skill. Use a real OpenAPI/GraphQL SDL/proto/event-schema excerpt of
a handful of endpoints — enough to exercise all seven checks (at least one unsafe/write method, one paginated
list endpoint, one error response) — and, when available, a prior version of the same spec to exercise the
Compatibility diff rather than only the internal-consistency path.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md).

## Invocation

> `api_spec: <OpenAPI/GraphQL SDL/proto/event-schema text>` (optional `previous_spec`, `system_design_context`)

## A correct minimal output contains

1. **Inputs echoed** — which of `api_spec` / `previous_spec` / `system_design_context` were supplied,
   before Analyze starts.
2. **Scope announcement** — which endpoints/operations were in scope for the review.
3. **All seven checks in a findings table** — Compatibility, Pagination, Idempotency, Error semantics,
   Versioning, Authorization, Rate limiting — each with an explicit finding, or "none found"/"N/A", never
   an omitted row.
4. **`API_DESIGN_REVIEW_REPORT.md`** — full report per [report-format.md](report-format.md), verdict line
   first.
5. **Confirmation / next step** — a cross-skill escalation offer when a finding matches
   [SKILL.md § Cross-skill escalation](../SKILL.md#cross-skill-escalation), or a plain "review complete"
   otherwise.

## Degraded paths

| Condition | Expected behavior |
|-----------|--------------------|
| `api_spec` absent or empty | Inputs HARD STOP — ask, no Analyze |
| `previous_spec` not supplied | Compatibility check scoped to internal consistency only — recorded as `Unknown — no previous_spec supplied` for the version-diff sub-check, not silently marked `compatible` |
| `api_spec` omits a section a check depends on (e.g. no auth model documented at all) | That check's row records an explicit `Unknown` finding, not a silent "consistent" |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
