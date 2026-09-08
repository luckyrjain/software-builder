---
workflow_version: 1.0
phase: analyze
produces:
  - authn_findings
  - authz_findings
  - secrets_findings
  - injection_findings
  - ssrf_findings
  - data_leakage_findings
  - cryptography_findings
  - dependency_exposure_findings
  - unknowns
consumes:
  - review_target
  - scope_hint
---

# Analyze — run the eight-category security sweep over `review_target`

Evaluate `review_target` against each of the following categories. Every category is checked on
every run regardless of `scope_hint` (see [workflow/inputs.md](inputs.md) § Normalization) — a
finding, an explicit "None found," or an explicit gap in `## Unknowns` for each one, never a
silently skipped category.

- **AuthN (authentication)** — how identity is established: credential verification, session/token
  issuance and validation, MFA where applicable, failure/lockout handling. Flag missing or
  bypassable checks, weak or absent rate-limiting on auth endpoints, and trust placed in
  client-supplied identity claims without server-side verification.
- **AuthZ, including tenant isolation** — how access is granted per identity: role/permission
  checks at every access point (not just the entry route), and specifically whether one tenant's
  identity can reach another tenant's data (missing tenant-scoping in a query, an ID passed
  straight from a request into a lookup with no ownership check, a shared cache/queue key without a
  tenant namespace).
- **Secrets handling** — how credentials, keys, and tokens are stored, logged, and transmitted.
  Flag hardcoded secrets, secrets written to logs or error messages, secrets sent over an
  unencrypted channel, and secrets held in a broader-than-necessary scope (env var readable by
  unrelated code, secret embedded in a URL).
- **Injection** — SQL, command, template, and similar injection: string-concatenated queries/
  commands/template strings built from untrusted input instead of parameterized calls or vetted
  escaping, and unsafe deserialization of untrusted input.
- **SSRF** — server-side requests whose target (host, URL, or resolved redirect) is influenced by
  untrusted input without an allowlist, causing the service to fetch attacker-chosen internal or
  external resources.
- **Data leakage** — responses, logs, or error messages that return more than the caller should see
  (over-broad API responses exposing internal fields, verbose stack traces or internal identifiers
  in user-facing errors, debug endpoints left reachable).
- **Cryptography** — algorithm choice (weak/deprecated ciphers or hashes, e.g. unsalted fast
  hashing for passwords), key management (hardcoded or long-lived keys, no rotation path, keys
  generated with insufficient entropy), and use of cryptographic primitives outside their intended
  mode (e.g. a nonce reused across encryptions).
- **Dependency exposure** — known-vulnerable libraries actually reachable from `review_target`'s
  scope (a manifest/lockfile entry pinned to a version with a known CVE that the reviewed code path
  exercises). This is a narrower check than a full CVE sweep — see
  [SKILL.md § Cross-skill escalation](../SKILL.md#cross-skill-escalation) for handing a broader
  upgrade decision to `dependency-upgrade-review`.

For each finding, record: category, one-line description, severity (Critical/High/Medium/Low),
evidence (a short excerpt — file/symbol location plus the relevant line(s), see
[reference/report-format.md § Safe rendered-output boundary](../reference/report-format.md#safe-rendered-output-boundary)
for how it is escaped and redacted before rendering), and a one-line recommendation.

**Evidence gaps are recorded, not silently skipped.** If `review_target` references code/config a
category needs but doesn't include it (an imported auth middleware not supplied, a config value
referenced by name but not shown), record that category's gap explicitly — what was needed, what
was tried, why it stopped — instead of marking the category clean or omitting it. This feeds
Report's `## Unknowns` section and its `Blocked — insufficient access` verdict state.
