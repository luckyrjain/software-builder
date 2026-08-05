# Review Checklist

Run each changed file against the dimensions below. Not every dimension applies to every diff — skip
what's irrelevant, but don't skip a dimension just because it's tedious (security and tests are the
two most often skipped and most often regretted). For each finding, score **Likelihood**, **Impact**,
and **Overall** per `severity-rubric.md` (risk matrix + hard floors).

## 1. Correctness & logic
- Does it do what the ticket says? Cross-check against the Jira **acceptance criteria**.
- Boundary conditions: empty, null/None, zero, negative, max, single-element, duplicates.
- Off-by-one, inverted boolean, wrong operator, wrong default.
- Dead/unreachable code; conditions that can never be true.

## 2. Security
- Input from users/network treated as untrusted: injection (SQL/NoSQL/command/template), path
  traversal, SSRF, unsafe deserialization, XXE.
- AuthN/AuthZ: is every new endpoint/action permission-checked? IDOR (object owned by another user)?
- Secrets in code/config/diff; tokens logged; PII logged.
- Crypto: no homemade crypto, no weak/legacy algorithms, no hardcoded IVs/keys.
- Output encoding / XSS for anything rendered.
- Open redirect: user-controlled `redirect` / `next` / `return_to` URLs validated against an
  allowlist; no protocol-relative or off-site redirects.
- CSRF: state-changing endpoints (POST/PUT/DELETE/PATCH) have CSRF protection or use a
  safe auth mechanism (token-in-header, SameSite cookie).
- CORS: new endpoints don't open wildcard origins (`*`) for credentialed requests.
- Rate limiting: new auth, login, OTP, or public-facing endpoints have rate limiting or
  account lockout to prevent brute-force.
- Dependency CVEs: newly added packages have no known critical CVEs (check advisories /
  lockfile audit).
- Mass assignment: new model/serializer fields aren't inadvertently writable from user input.
- Timing: auth or secret comparisons use constant-time equality, not plain `==` on tokens.

## 3. Error handling & resilience
- External calls (DB, HTTP, queue, cache) have timeouts and handle failure.
- Errors are caught at the right level — not swallowed, not over-broad `except`/`catch`.
- Failures are observable (logged with context) and don't leak internals to the caller.
- Retries are bounded and idempotent; no infinite retry loops.
- Circuit breakers / bulkheads on external dependencies; cascading failure contained when upstream is
  down.

## 4. Performance & scalability

Apply when the diff touches queries, ORM/repository code, HTTP handlers on hot paths, workers/queues,
caches, or loops over collections. Skip for pure docs/config with no runtime path. Score with L/I per
`severity-rubric.md` — perf on a hot path is often **Likelihood High**.

### Database
- **N+1** — query or ORM access inside a loop over a collection; missing eager load / `JOIN` /
  `prefetch_related` / `include` / batch loader; GraphQL resolvers fetching per row without DataLoader.
- **Indexes** — new `WHERE`/`ORDER BY`/`JOIN` columns without an index on large tables; filter on
  unindexed JSON fields; migration adds column used in hot queries but no index plan.
- **Pagination** — unbounded `SELECT *`; loading full result sets into memory; missing `LIMIT`/`OFFSET`
  or cursor pagination on list endpoints; `OFFSET` on very large tables without keyset pagination.
- **Query shape** — `SELECT *` when few columns needed; functions on indexed columns preventing index
  use; missing query timeouts; connection pool exhaustion (long transactions holding connections).

### Caching
- Repeated identical fetches/computations that should be memoized or cached (per-request, Redis, CDN).
- Missing **TTL** or unbounded cache growth; no eviction policy on in-memory caches.
- **Cache stampede** — no lock/single-flight on cold cache; thundering herd on expiry.
- Stale reads after writes — missing cache invalidation or too-long TTL on mutable data.
- Cache key collisions or keys that omit tenant/user scope (cross-tenant leakage + wrong perf).

### Memory
- **Allocations** — building large strings/buffers/slices in hot loops; repeated serialization of big
  payloads; copying large collections when references suffice.
- Unbounded in-memory aggregation (`append`/`push` in a loop without cap); loading entire tables/files
  into a list/map; parsing huge JSON/XML bodies without size limits.
- Retaining references preventing GC (closures holding request-scoped data on singletons).

### Concurrency & throughput
- **Locks** — coarse mutex/`synchronized` on hot paths; row/table locks held across network I/O; lock
  ordering that risks deadlocks (cross-ref §7); `FOR UPDATE` on wide scans.
- **Retry storms** — unbounded or aggressive retries on failure (client, worker, HTTP middleware);
  retry without backoff/jitter; retrying non-idempotent operations; cascading retries across services.
- **Queue amplification** — one event fans out to N queue messages without batching; worker publishes
  back to same queue on failure (infinite loop); missing rate limits or concurrency caps on consumers;
  poison messages requeued forever without DLQ.

### API / GraphQL (when present)
- Depth/complexity limits; unbounded list fields; N+1 resolvers; introspection exposed in prod.
- Large response payloads without compression or field selection; missing rate limits on expensive endpoints.

## 5. Data & migrations
- Backward-compatible: can old and new code run against the schema during a rolling deploy?
- Nullable vs non-nullable with defaults; safe column drops/renames; data backfills.
- Migration is reversible (or the irreversibility is intentional and called out).
- Large-table migrations won't lock/timeout in production.

## 6. API & contracts
- Breaking changes to request/response shape, status codes, or error format are versioned or
  backward-compatible.
- New fields documented; removed fields deprecated, not deleted.
- Pagination, rate-limit, and idempotency semantics preserved.
- **GraphQL schema:** breaking field/type removals, nullable → non-null without migration path,
  deprecated fields removed before sunset, auth on new queries/mutations/subscriptions.

## 7. Concurrency & state
- Shared mutable state guarded; no data races.
- Lock ordering: multi-row or multi-resource updates acquire locks in a consistent order; document
  ordering when several resources are updated in one flow (deadlock risk).
- Idempotency for retried/duplicated requests (webhooks, payments).
- Transaction boundaries correct; no partial writes on failure.
- No new global/singleton state that breaks under parallelism.

## 8. Tests & test quality

Apply when **production logic** changes — new behavior, bug fixes, refactors with behavior change,
API/handlers, concurrency, or integrations. Skip docs-only, config-only, or pure rename/format with no
behavior change. Do not stop at "tests present" — evaluate **what** is tested and **what is missing**.

### Coverage
- Critical new branches and error paths have tests; not only the happy path.
- Changed files have corresponding test updates in the diff or a credible note (integration suite, follow-up ticket).
- If logic files changed but **no test file** in the diff → **Low** by default; **Medium/High** on
  payments/auth/critical paths per `domain-overrides.md`.
- Coverage tools in CI are unchanged or improved; no large untested surface without justification.

### Edge cases
- Boundaries exercised: empty, null, zero, max, single element, duplicates, unicode, timezone edges.
- Off-by-one and collection edge cases for loops and pagination logic.

### Negative cases
- Invalid input, auth failure, permission denied, not-found, conflict, timeout, upstream 4xx/5xx.
- Tests assert the **correct error** (status code, error type, message class) — not just "throws".

### Concurrency
- Race-prone code (shared state, double-submit, idempotency) has concurrent or serialized tests where feasible.
- Tests don't depend on execution order unless order is the behavior under test.

### Failure injection
- Retries, circuit breakers, partial failures, and rollback paths tested or explicitly deferred with ticket.
- Mocks/stubs simulate failure modes — not only success responses from dependencies.

### Regression
- Bug-fix MRs include a test that **fails without the fix** (or references the failing test case ID).
- No removal of tests that still protect behavior unless behavior intentionally changed and documented.

### Property tests
- Where invariants matter (parsers, serializers, money math, state machines), property/fuzz/table-driven
  tests or generative cases — or note why omitted.

### Integration
- Cross-module or cross-service flows covered when the change spans boundaries (DB + API, queue + worker).
- Testcontainers, embedded DB, or contract-backed integration tests preferred over untested wiring.

### Contract
- Consumer/provider contract tests updated for API or schema changes (Pact, OpenAPI diff, GraphQL schema test).
- Breaking contract change without updated contract test → **High** with §6.

### Load / performance tests
- Hot-path or scalability-sensitive changes: benchmark, load test, or perf regression test in diff or CI job.
- If absent on a hot path → **Low/Medium** observation; **High** when §4 perf risk is High.

### Hygiene (always)
- Tests assert **behavior**, not implementation details that break on refactor.
- No flaky patterns: `sleep()` timing, real network without hermetic setup, unseeded randomness, wall clock.
- Test data has no real secrets or PII.

When logic changes materially, render a **test quality table** in Phase 2 (like §17 rollback):

| Dimension | Status | Evidence |
|-----------|--------|----------|
| Coverage | ✅ / ❌ / ⚠️ | … |
| Edge cases | ✅ / ❌ / ⚠️ | … |
| Negative cases | ✅ / ❌ / ⚠️ | … |
| Concurrency | ✅ / N/A / ⚠️ | … |
| Failure injection | ✅ / ❌ / ⚠️ | … |
| Regression | ✅ / ❌ / ⚠️ | … |
| Property tests | ✅ / N/A / ⚠️ | … |
| Integration | ✅ / ❌ / ⚠️ | … |
| Contract | ✅ / N/A / ⚠️ | … |
| Load | ✅ / N/A / ⚠️ | … |

Flag **❌** on critical dimensions as findings (`test ·` prefix). **⚠️** → Low/Medium unless regulated path.

## 9. Observability

Apply to **production runtime changes** — new handlers, workers, business logic, integrations, feature
flags, or error paths. Skip docs-only, test-only, or mechanical refactors with no behavior change. For
each new or materially changed path, ask whether operators can **see, trace, and alert** on it in prod.

### Metrics
- Does new code emit **counters/histograms/gauges** for success, failure, and latency?
- Are metrics named/labeled consistently with repo conventions (service, endpoint, operation)?
- High-cardinality labels avoided (no raw user IDs, unbounded paths in label values)?
- SLO-critical paths have request/error/duration metrics suitable for dashboards?

### Logs
- Important paths log at appropriate **level** (not `error` for expected cases; not `debug` for prod-only failures).
- Logs include **correlation IDs** / trace IDs / request IDs for cross-service debugging.
- No PII, secrets, or full payloads in logs (redact or hash).
- Failure logs carry enough context to diagnose (operation, entity ID, error class) without stack-dump spam.

### Tracing
- New external calls (HTTP, DB, queue, cache) participate in **distributed tracing** (spans propagated)?
- Span names and attributes identify the operation; parent/child relationships preserved across async boundaries?

### Error attribution
- Errors are distinguishable by **type/code** — not a generic "something went wrong" for all failures.
- Client vs server vs upstream attribution clear in logs/metrics (HTTP status, error wrapper, `cause` chain).
- Partial failures in batch/queue processing report **which item** failed and whether the batch continued.

### Feature flag metrics
- New or changed **feature flags** emit exposure/evaluation metrics (or use the team's flag analytics).
- Flag-gated paths log/metric when the flag is on vs off so rollout and rollback are observable.
- Flag defaults and kill-switch behavior visible in monitoring (not silent fallback).

### Dashboards
- New production surfaces have or extend a **dashboard** (or the MR notes which existing dashboard covers them).
- Key golden signals present: traffic, errors, latency, saturation for the new component.
- If no dashboard change in diff, **Low** observation when the path is user-facing or revenue-impacting:
  *"No dashboard update in diff — confirm existing dashboards cover `<service>`."*

### Alerts
- New **failure modes** are alertable — error-rate, latency SLO breach, queue depth, or health-check failure.
- Alerts are actionable (runbook link, owner team, not noisy threshold).
- Missing alerts on critical new paths → use **contextual severity** (`reference/contextual-severity.md`):
  **High** on production-critical paths (payments/auth), **Medium** on standard API paths, **Low** on internal/admin.
- Alert rules not duplicated or missing for flag rollouts that change prod behavior.

**Severity for §9 gaps:** classify path context first — missing logging/metrics is **not** always Medium.
See `reference/contextual-severity.md` (checkout payment → High; admin dashboard → Low).

Cross-ref **§3** (errors observable) and **§4** (queue/retry metrics) — observability is how ops detects those failure modes in prod.

## 10. Readability & maintainability

**Trigger:** Always run core items (naming, comments, conventions, dead code). Apply frontend/accessibility sub-bullets (keyboard navigation, ARIA labels, colour contrast, focus management) **only** when the diff touches UI components, templates, HTML, JSX/TSX, or CSS/SCSS files.

- Names reveal intent; functions do one thing; nesting isn't excessive.
- No copy-paste duplication that should be shared.
- Comments explain *why*, not *what*; no stale comments left behind.
- Follows the repo's existing conventions (check `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, rules, and
  nearby code).
- **Frontend / UI changes:** keyboard navigation, focus management, ARIA labels/roles, colour contrast,
  form labels tied to inputs, meaningful alt text — flag WCAG gaps as Medium on user-facing paths.

## 11. Documentation
- README / API docs / changelog updated when behavior or interfaces change.
- Non-obvious decisions captured (inline or in an ADR) where warranted.
- MR description is adequate: states intent, test plan, and rollback notes. A blank or
  template-skipped description on a production-touching MR is a Low/Medium finding.

## 12. Scope & hygiene
- Changes map to the ticket; unrelated edits flagged as scope creep (Medium).
- No debug prints, commented-out code, `TODO`s without a tracking reference, or stray files.
- Dependency additions justified, pinned, and license-compatible; lockfile updated when the repo uses
  one (skip the lockfile check for manifest-only ecosystems).
- **Supply chain:** new packages are from known/trusted publishers; no suspicious transitive
  additions; when the repo commits a lock file, it is consistent with the manifest.
- Feature flags / config defaults are safe for production.

## 13. Domain hot-spots (optional)
If the repo is in a regulated or high-stakes domain, load repo `review-rules.yaml` first
(`reference/review-rules.md`). If absent, load `domain-overrides.md` (or repo-local
`.cursor/skills/pr-review/domain-overrides.md`) and raise severity one notch for findings in those areas.

## 14. Infrastructure / IaC (when present)
Apply when the diff touches Terraform, Helm charts, Kubernetes manifests, Dockerfiles, or CI/CD
pipeline definitions:
- RBAC / IAM changes follow least-privilege; no overly broad roles or wildcard permissions.
- Resource limits and requests set on new workloads; no unbounded CPU/memory.
- Network policies: new ports or ingress rules are justified.
- Image tags pinned (not `:latest`); prefer digest pinning (`image@sha256:…`) or immutable tags; base
  images from trusted registries.
- Secrets not embedded in manifests or plain env vars — use secret managers or sealed secrets.
- Terraform: intended `plan` output considered; no accidental destructive resource replacements.

## 15. AI / LLM (when present)
**Trigger — apply only when the diff matches AI/ML signals.** Scan the changed lines and their imports
(case-insensitive) for any of: `anthropic`, `openai`, `llm`, `embedding`, `prompt`, `langchain`,
`rag`, `vector_store`, `chat_completion`. If none match, skip this dimension; if any match, apply it.
This keeps §15 off unrelated diffs (noise) and on for genuine prompts, agent skills, RAG pipelines,
tool-calling, eval harnesses, or model-serving config:
- **Prompt injection:** user-controlled text reaching system prompts without sanitisation or boundaries.
- **Tool abuse:** agents granted write/network tools beyond least privilege; missing confirmation gates
  on destructive actions.
- **Hallucination risk:** LLM-generated code, SQL, or shell merged or executed without validation;
  RAG answers shown to users without source citation or retrieval grounding.
- **Secrets in prompts:** API keys, tokens, or PII embedded in prompt templates or few-shot examples.
- **PII to LLM:** user content (names, emails, financial/health data) sent to external model APIs
  without redaction, consent, or data-processing controls — raise **High** when production paths are
  affected.
- **Model pinning:** production paths pin model ID/version; no unversioned `latest` or floating
  aliases in config.
- **LLM fallback:** primary model failure must not silently downgrade to a less-capable model, leak
  prompts in errors, or skip safety checks.
- **Non-determinism:** missing temperature/max-token limits on production paths; no eval/regression set
  for prompt changes.
- **Cost / abuse:** unbounded context windows, missing rate limits, recursive agent loops without caps.
- **Output safety:** generated content rendered without encoding; model output executed blindly
  (`eval`, shell, SQL).

## 16. Architecture Lens (when triggered)
**Trigger — apply only when structural signals appear** (or the user requests architecture focus).
Scan changed lines and their imports for any of: cross-boundary import, new shared/global state,
new public API boundary (HTTP/RPC route, GraphQL root field, OpenAPI path, cross-package export — not
routine new classes/`public` members in an existing module), feature-flag usage, structural refactor
(>3 files moved/renamed in one package, new `internal/`/`shared/` path), or >50 non-mechanical files
changed.
Skip mechanical-only MRs (`*.lock`, `vendor/`, `dist/`, generated) unless the user overrides. Load
`reference/architecture-lens.md` (and repo-local `.cursor/skills/pr-review/architecture-lens.md` when
present). Anchor every finding to a changed line; cite unchanged paths as *Related* context only.
Prefix findings `arch · <concern>`:
- **Coupling:** new tight dependencies; bypassing facades/ports.
- **Boundaries:** cross-layer imports per docs, CODEOWNERS, or repo override forbidden edges.
- **Cycles:** new import edge completing a dependency cycle (read target imports when needed).
- **Shared state:** module-level mutable, singletons, request data on globals (design angle; §7 for runtime).
- **Domain leakage:** persistence/internal models at API or UI boundaries.
- **Flag debt:** new flags without sunset; permanent behavior behind flags; unsafe defaults.
- **Tech debt:** architectural shortcuts that compound (not §12 hygiene nits).
- **Testability:** hard dependencies, logic in untestable locations, critical untestable branches.
Tier severity per `architecture-lens.md` — hard violations → High; light signals → Medium/Low.
Phase 5 **Architectural summary** (`reference/architectural-summary.md`) synthesizes §16 and overall design.

## 17. Rollback safety (when risky)
**Trigger — apply when the MR is risky to deploy or hard to revert.** Scan for: DB migrations/schema,
public API or GraphQL contract changes, feature-flag additions/changes, IaC/deploy/Helm/K8s pipeline
changes, data backfills or dual-write patterns, irreversible config, or paths covered by
`domain-overrides.md` (payments, auth, migrations). Skip trivial bugfixes with no deploy/schema/API
surface. Senior reviewers always ask: *can we undo this safely?*

Render a **rollback checklist table** in Phase 2 output (like the Jira AC table):

| Question | Status | Evidence |
|----------|--------|----------|
| Can this be rolled back? | ✅ / ❌ / ⚠️ | Deploy revert sufficient, or needs forward migration/fix? |
| Backward compatible? | ✅ / ❌ / ⚠️ | Old code + new code coexist during rolling deploy? |
| Schema reversible? | ✅ / ❌ / ⚠️ / N/A | `down` migration, expand-contract, or one-way DDL called out? |
| Feature flagged? | ✅ / ❌ / ⚠️ / N/A | Risky behavior behind a flag with safe default? |
| Kill switch? | ✅ / ❌ / ⚠️ / N/A | Flag, config toggle, or circuit breaker to disable quickly? |
| Migration safe? | ✅ / ❌ / ⚠️ / N/A | Online migration, batch/backfill, lock risk, rollback plan in MR? |
| Dual write / backfill? | ✅ / ❌ / ⚠️ / N/A | Schema+data change has backfill and read path for old+new? |
| Canary possible? | ✅ / ❌ / ⚠️ | Gradual rollout (flag %, canary deploy, shadow traffic) documented? |

**What to look for (cross-ref §5 Data, §6 API, §12 flags, §14 IaC):**
- **Rollback path** — revert commit/deploy restores service; no orphaned data requiring manual repair.
- **Backward compatibility** — additive schema first; old clients work; nullable columns with defaults;
  no removing fields clients still send.
- **Schema reversibility** — destructive DDL (`DROP`, `NOT NULL` without default, type narrowing) without
  expand-contract; long locks on large tables; irreversible migrations noted in MR description.
- **Feature flag / kill switch** — risky logic default-off or kill-switch documented; not permanent
  `if (new_behavior)` with no off ramp; aligns with §16 flag debt.
- **Migration safety** — backfill job idempotent; dual-write/read-fallback during transition; deploy
  order documented (migrate-then-code or code-then-migrate).
- **Canary** — MR or ticket describes phased rollout; not big-bang only on critical paths.

Flag each **❌** or material **⚠️** as a finding (prefix `rollback ·` in Finding column). On regulated
paths, escalate one notch per `domain-overrides.md`. Blank MR rollback section when template requires it
→ Low/Medium per §11. Results feed **Rollback difficulty** in Phase 5 Production risk
(`reference/production-risk.md`).
