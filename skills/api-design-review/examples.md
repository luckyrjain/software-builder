# Examples — invocation patterns

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation table

| # | Caller sends | Behavior |
|---|--------------|----------|
| 1 | `api_spec` (OpenAPI, 6 endpoints) + `previous_spec` (prior version), everything clean | Inputs → Analyze → Report → `API_DESIGN_REVIEW_REPORT.md`, **Verdict: Approved** |
| 2 | `api_spec` with a removed required field vs `previous_spec`, no versioning strategy anywhere | **Verdict: Rejected** — breaking change, no migration path |
| 3 | Same breaking change, but `api_spec` declares a `/v2/` versioning strategy | **Verdict: Changes required** — breaking change absorbed by a real migration path, not a hard block |
| 4 | `api_spec` has a `POST /payments` with no documented idempotency key, everything else clean | **Verdict: Changes required** |
| 5 | `api_spec` supplied alone, no `previous_spec` | Compatibility recorded `Unknown — no previous_spec supplied`; **Verdict: Approved with conditions** — evidence gap, not a bare Approved |
| 6 | `api_spec` absent | Inputs **HARD STOP** — ask, no Analyze |
| 7 | `api_spec` has an admin-only mutation with no declared authorization scope at all | **Verdict: Rejected**; cross-skill escalation to **security-review** offered |
| 8 | "Review MR !482, it touches the `/orders` endpoint" | **Wrong skill** → **pr-review** directly |
| 9 | `api_spec` clean except a public `POST /signups` with no declared rate limit | **Verdict: Changes required** |
| 10 | "Review our `orders` table schema and indexes" | **Wrong skill** → **database-review** directly |
| 11 | "Design the components and data model for this new API" | **Wrong skill** → **system-design** directly |

---

### Scenario: Clean API design — happy path

**Caller:** `api_spec: <OpenAPI spec, 6 endpoints>`, `previous_spec: <prior version of the same spec>`

**Agent:**

1. Inputs — both `api_spec` and `previous_spec` parsed; `system_design_context` not supplied
2. Analyze — Compatibility: no breaking changes found; Pagination: cursor-based, consistent, capped at
   100; Idempotency: the one unsafe method (`POST /orders`) requires an `Idempotency-Key` header,
   documented; Error semantics: consistent `{code, message, details}` envelope across all endpoints;
   Versioning: `/v1/` URI strategy, consistently applied; Authorization: every endpoint declares a scope,
   consistent with its sensitivity; Rate limiting: declared with `X-RateLimit-*` headers on all endpoints
3. Report — no proven issues, no evidence gaps → **Verdict: Approved**

**Expected fragment:**

```markdown
# API design review — orders-api

**Verdict: Approved**

## Compatibility

| Check | Finding | Evidence |
|-------|---------|----------|
| Backward compatibility vs `previous_spec` | compatible | No removed/renamed fields or endpoints |

## Idempotency

| Check | Finding |
|-------|---------|
| Unsafe methods (POST/create-like RPCs) | idempotency key required and documented — `Idempotency-Key` header on `POST /orders` |
```

---

### Scenario: Breaking change with no migration path — worst verdict

**Caller:** `api_spec: <OpenAPI spec, POST /orders no longer accepts `legacy_sku`>`, `previous_spec: <prior version requiring legacy_sku>`. No versioning strategy declared anywhere in `api_spec`.

**Agent:**

1. Inputs — both specs parsed
2. Analyze — Compatibility: `legacy_sku` field removed from `POST /orders` request body vs
   `previous_spec` — breaking change for any existing caller still sending it; Versioning: no strategy
   declared at all — the breaking change has no migration path; other five checks clean
3. Report — a breaking change with no versioning strategy to absorb it → **Verdict: Rejected**, per
   [reference/report-format.md](reference/report-format.md) precedence

**Expected fragment:**

```markdown
# API design review — orders-api

**Verdict: Rejected**

## Compatibility

| Check | Finding | Evidence |
|-------|---------|----------|
| Backward compatibility vs `previous_spec` | breaking change | `POST /orders` — `legacy_sku` field removed from request body |

## Versioning

| Check | Finding |
|-------|---------|
| Versioning strategy | absent — breaking changes have no migration path |
```

---

### Scenario: Multiple must-fix findings, no hard blocker

**Caller:** `api_spec: <OpenAPI spec>` — `POST /payments` has no idempotency key, error responses are
inconsistent (`GET /accounts/{id}` returns a bare string, everything else returns `{code, message}`), and
`POST /signups` (public) declares no rate limit. No breaking changes (no `previous_spec` issue here — one
was supplied and is clean), no authorization gaps.

**Agent:**

1. Inputs — `api_spec` + `previous_spec` parsed
2. Analyze — Compatibility clean; Pagination clean; Idempotency: `POST /payments` missing a key;
   Error semantics: `GET /accounts/{id}` shape inconsistent with the rest; Versioning clean; Authorization
   clean; Rate limiting: `POST /signups` has none declared
3. Report — three proven must-fix issues, no `Rejected`-tier condition → **Verdict: Changes required**,
   all three findings listed, not just one

**Expected fragment:**

```markdown
**Verdict: Changes required**

## Idempotency

| Check | Finding |
|-------|---------|
| Unsafe methods (POST/create-like RPCs) | missing — `POST /payments` has no documented idempotency key, retries can double-charge |

## Error semantics

| Check | Finding |
|-------|---------|
| Status code / error shape consistency | inconsistent shapes across endpoints — `GET /accounts/{id}` returns a bare string, all others return `{code, message}` |

## Rate limiting

| Check | Finding |
|-------|---------|
| Rate limit declared for public/write endpoints | absent — `POST /signups` has no declared limit |
```

---

### Scenario: Degraded path — no previous_spec, evidence gap recorded

**Caller:** `api_spec: <OpenAPI spec, 4 endpoints>` only — no `previous_spec` supplied.

**Agent:**

1. Inputs — `api_spec` parsed; `previous_spec` absent, per [workflow/inputs.md](workflow/inputs.md) this
   is not a HARD STOP (only `api_spec` is required) — noted as a scoped-down Compatibility check
2. Analyze — Compatibility: only internal consistency checked (no contradictory resource definitions
   found); the version-diff sub-check recorded as an evidence gap, not "compatible"; all other six checks
   clean
3. Report — no proven issue, but one unresolved evidence gap → **Verdict: Approved with conditions**, per
   [reference/report-format.md](reference/report-format.md) — an unresolved check never silently yields a
   bare `Approved`

**Expected fragment:**

```markdown
**Verdict: Approved with conditions**

## Compatibility

| Check | Finding | Evidence |
|-------|---------|----------|
| Backward compatibility vs `previous_spec` | Unknown — no previous_spec supplied | Internal consistency checked only, no contradictions found |

## Notes

No `previous_spec` was supplied — the Compatibility check above covers only internal consistency, not a
real backward/forward-compatibility diff against a prior version.
```

---

### Scenario: Cross-skill handoff — exploitable authorization gap

**Caller:** `api_spec: <OpenAPI spec>` — `DELETE /admin/users/{id}` declares no authorization scope at
all, while every other admin endpoint requires an `admin:write` scope.

**Agent:**

1. Inputs — `api_spec` parsed
2. Analyze — Authorization: `DELETE /admin/users/{id}` has no declared scope, inconsistent with every
   other admin endpoint — flagged as directly exploitable (any authenticated caller could delete any
   user), not merely a documentation gap
3. Report — an exploitable authorization gap → **Verdict: Rejected**, per
   [reference/report-format.md](reference/report-format.md); cross-skill escalation offered per
   [SKILL.md § Cross-skill escalation](SKILL.md#cross-skill-escalation)

**Expected fragment:**

```markdown
**Verdict: Rejected**

## Authorization

| Check | Finding |
|-------|---------|
| Per-endpoint/field authorization model | gap found — `DELETE /admin/users/{id}` has no declared scope, inconsistent with every other admin endpoint (all require `admin:write`); this looks directly exploitable, not just an omission |
```

**Handoff offered:** "This authorization gap looks directly exploitable — recommend a dedicated
**security-review** of the admin API surface before this ships. Run it now?"
