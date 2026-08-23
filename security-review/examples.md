# Examples — invocation patterns

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation table

| # | Caller sends | Behavior |
|---|--------------|----------|
| 1 | `review_target: <auth middleware + session code>` | Inputs → Analyze → Report → all 8 categories checked, no findings → `SECURITY_REVIEW_REPORT.md` verdict **Pass** |
| 2 | `review_target: <API handler with a Low-severity verbose error message>` | Findings: 1 Low under Data leakage, rest clean → verdict **Pass with findings** |
| 3 | `review_target: <query builder concatenating a raw SQL string from request input>` | Injection finding rated **High** → verdict **Fail — Critical/High findings present** |
| 4 | `review_target: <handler that fetches a resource by ID with no ownership check>` | AuthZ/tenant-isolation finding rated **Critical** (cross-tenant data access) → verdict **Fail — Critical/High findings present** |
| 5 | `review_target: <handler importing `session_guard` which is not included in the pasted content>` | AuthN category recorded as a gap in `## Unknowns`, no Critical/High elsewhere → verdict **Blocked — insufficient access** |
| 6 | `review_target` absent | Inputs HARD STOP — ask for content, no Analyze |
| 7 | `review_target: <library manifest showing a pinned dependency with a known CVE reachable from the reviewed code path>` | Dependency exposure finding recorded → escalation offered to **dependency-upgrade-review** for the version-bump decision |
| 8 | `review_target: <full merge-request diff>` with "just review this MR generally" | **Wrong skill** → routed to **pr-review**; security-review is for a dedicated security pass, not a general code-quality review |
| 9 | `review_target: <package.json diff bumping one library's version>` with "any CVEs in this bump?" | **Wrong skill** → routed to **dependency-upgrade-review**; no broader review scope requested |
| 10 | `review_target: <design doc>`, `scope_hint: focus on the auth flow` | All 8 categories still checked; Analyze weights depth toward AuthN/AuthZ per the hint, other categories still get a row |

---

### Scenario: Clean review — happy path

**Caller:** `review_target: <src/auth/session.py, showing token issuance, validation, and a
parameterized session lookup>`

**Agent:**

1. Inputs — `review_target` parsed, no `scope_hint` given, full 8-category sweep runs
2. Analyze — AuthN: token validation checked server-side, no bypass found; AuthZ: session-scoped
   queries all include a tenant filter; Secrets: token stored in an httpOnly cookie, never logged;
   Injection: parameterized query, no concatenation; SSRF/Data leakage/Cryptography/Dependency
   exposure: no findings
3. Report — zero findings, zero gaps → verdict `Pass`

**Expected fragment:**

```
# Security review — src/auth/session.py

**Verdict: Pass**

## AuthN

| Finding | Severity | Evidence | Recommendation |
|---------|----------|----------|-----------------|
| None found | — | — | — |

## AuthZ (incl. tenant isolation)

| Finding | Severity | Evidence | Recommendation |
|---------|----------|----------|-----------------|
| None found | — | — | — |
```

---

### Scenario: Critical cross-tenant data access — worst state

**Caller:** `review_target: <GET /invoices/:id handler that loads the invoice by ID alone, with no
check that it belongs to the requesting tenant>`

**Agent:**

1. Inputs — `review_target` parsed
2. Analyze — AuthZ: the handler resolves `:id` straight into a lookup with no tenant-scoping
   clause; any authenticated caller can read another tenant's invoice by guessing/incrementing the
   ID — rated **Critical** (direct cross-tenant data exposure, no privilege required beyond a valid
   session). Other categories: no findings.
3. Report — one Critical finding → verdict `Fail — Critical/High findings present`

**Expected fragment:**

```
# Security review — GET /invoices/:id handler

**Verdict: Fail — Critical/High findings present**

## AuthZ (incl. tenant isolation)

| Finding | Severity | Evidence | Recommendation |
|---------|----------|----------|-----------------|
| Invoice lookup has no tenant-ownership check — any authenticated caller can read another tenant's invoice by ID | Critical | `handlers/invoices.py`: "`invoice = db.get(Invoice, id)`" | Add `tenant_id == current_tenant.id` to the lookup filter; return 404 (not 403) on mismatch to avoid confirming the ID exists |
```

---

### Scenario: Low-severity data leakage — multi-finding, Pass with findings

**Caller:** `review_target: <API error handler that returns the raw exception message and stack
trace to the client on a 500>`

**Agent:**

1. Inputs — `review_target` parsed
2. Analyze — Data leakage: raw stack trace and internal exception text returned to the client,
   rated **Low** (information disclosure, not directly exploitable on its own, but aids
   reconnaissance). AuthN/AuthZ/Secrets/Injection/SSRF/Cryptography/Dependency exposure: no
   findings.
3. Report — one Low finding, no gaps → verdict `Pass with findings`

**Expected fragment:**

```
# Security review — API error handler

**Verdict: Pass with findings**

## Data leakage

| Finding | Severity | Evidence | Recommendation |
|---------|----------|----------|-----------------|
| Raw exception message and stack trace returned to the client on 500 | Low | `handlers/middleware.py`: "`return {"error": str(e), "trace": traceback.format_exc()}, 500`" | Return a generic error message to the client; log the full trace server-side only |
```

---

### Scenario: Evidence gap — degraded path

**Caller:** `review_target: <a request handler that calls `require_auth()`, but the `require_auth`
implementation itself is not included in the pasted content>`

**Agent:**

1. Inputs — `review_target` parsed, no `scope_hint`
2. Analyze — AuthN: the handler calls `require_auth()`, but its implementation is not in scope —
   cannot verify whether it actually enforces authentication or how it fails. Recorded as a gap in
   `## Unknowns`, not assumed clean. Other categories checked normally, no findings.
3. Report — no Critical/High finding, but one unresolved gap → verdict `Blocked — insufficient
   access`

**Expected fragment:**

```
# Security review — request handler

**Verdict: Blocked — insufficient access**

## AuthN

| Finding | Severity | Evidence | Recommendation |
|---------|----------|----------|-----------------|
| Cannot verify authentication enforcement — `require_auth()` is called but its implementation is not included in `review_target` | — | `handlers/orders.py`: "`@require_auth`" | Supply `require_auth`'s implementation for a complete AuthN check |

## Unknowns

- AuthN: `require_auth()` implementation not in `review_target` scope — could not verify enforcement or failure behavior.
```

---

### Scenario: Cross-skill handoff — vulnerable dependency

**Caller:** `review_target: <requirements.txt pinning `some-lib==2.1.0`, plus code that calls the
vulnerable function directly>`

**Agent:** Analyze's dependency-exposure check finds `some-lib==2.1.0` has a known CVE in the exact
function the reviewed code calls, rated **High**. Report sets verdict `Fail — Critical/High
findings present` and, per
[SKILL.md § Cross-skill escalation](SKILL.md#cross-skill-escalation), offers a handoff: *"This
finding's root cause is a vulnerable dependency version — hand off to **dependency-upgrade-review**
for the breaking-change/CVE/rollout analysis of upgrading `some-lib` past 2.1.0?"*

**Expected fragment:**

```
## Dependency exposure

| Finding | Severity | Evidence | Recommendation |
|---------|----------|----------|-----------------|
| `some-lib==2.1.0` has a known CVE in a function this code calls directly | High | `requirements.txt`: "`some-lib==2.1.0`" | Upgrade past the patched version — see dependency-upgrade-review for breaking-change/rollout analysis |
```
