---
workflow_version: 1.0
phase: analyze
produces:
  - compatibility_findings
  - pagination_findings
  - idempotency_findings
  - error_semantics_findings
  - versioning_findings
  - authorization_findings
  - rate_limiting_findings
consumes:
  - api_spec
  - previous_spec
  - system_design_context
---

# Analyze — evaluate the API design against seven domain checks

Run all seven checks below over `api_spec` (and `previous_spec`/`system_design_context` where supplied).
Every check produces a finding, even when clean — never skip a check silently. When a check cannot be
completed for lack of evidence, record it as an explicit gap (feeds Report's Unknown handling) rather
than guessing or defaulting to "clean."

## 1. Compatibility

Compare `api_spec` against `previous_spec` when supplied: removed/renamed fields or endpoints, changed
field types, newly required fields on existing requests, changed enum values, removed error codes a
caller may already handle. Flag anything that breaks an existing caller as a breaking change. When
`previous_spec` is absent, check only internal consistency (no contradictory definitions of the same
resource) and record the version-diff sub-check as an evidence gap.

## 2. Pagination

For every list-returning endpoint/operation: is the pagination style (cursor, offset, page-number)
consistent across the spec; is there a page-size cap (default and max); is total-count exposure
consistent; does cursor-based pagination avoid leaking internal IDs where that matters. Flag
inconsistent styles across endpoints and unbounded/uncapped page sizes.

## 3. Idempotency

For every unsafe operation (POST or a non-idempotent RPC/mutation that creates or mutates state): is
there a documented idempotency key or equivalent safe-retry mechanism; is the key's scope and TTL
specified; do safe methods (GET, PUT with a full resource replace) already behave idempotently as
specified. Flag any create-like operation with no safe-retry story.

## 4. Error semantics

Check status-code usage (or GraphQL/gRPC error-code equivalent) and error-shape consistency across every
endpoint: same error envelope shape, consistent field names for code/message/details, consistent use of
4xx vs 5xx (or equivalent). Flag inconsistent shapes and misused codes (e.g. 200 with an error body).

## 5. Versioning

Is there an explicit versioning strategy (URI segment, header, field, or schema evolution rules for
GraphQL/proto)? Does every breaking change identified in Compatibility have a migration path under that
strategy? Flag a breaking change with no versioning strategy to absorb it, and flag an undocumented or
inconsistently-applied strategy (e.g. only some endpoints versioned).

## 6. Authorization

For every endpoint/field: is an authorization/scope requirement declared; is it consistent with
similar endpoints (no unexplained outlier with weaker requirements); does any endpoint appear to expose
data or actions with no declared requirement at all. A gap that looks directly exploitable (e.g. an
admin-only mutation with no declared scope) is flagged for escalation to **security-review** per
[SKILL.md § Cross-skill escalation](../SKILL.md#cross-skill-escalation), not adjudicated here as a full
security finding.

## 7. Rate limiting

Is a rate limit declared for public and/or write endpoints (limits, window, and response headers such as
`Retry-After` or equivalent)? Flag any public write endpoint with no declared limit.

## Evidence gaps

Any of the seven checks that cannot be completed — no `previous_spec` for a version diff, a spec section
too sparse to evaluate (e.g. no error responses documented at all) — is recorded as its own gap, carried
forward to [workflow/report.md](report.md) as an explicit "Unknown" in that check's row. Never silently
skipped and never silently treated as a clean pass.
