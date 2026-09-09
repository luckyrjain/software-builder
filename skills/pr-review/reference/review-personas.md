# Review personas

One **primary persona** shapes emphasis per review — what to hunt first, what to deprioritize, and how
the executive summary is framed. Personas **narrow focus**; they do not disable hard floors, the
execution path gate, or a security skim on touched files.

Load at the **start of Phase 2** (`workflow/phase-2.md`).

## Personas

| Persona | Role | Primary emphasis |
|---------|------|------------------|
| **Principal Engineer** (default) | Balanced senior reviewer | AC, correctness, maintainability, proportionate scope — all checklist dimensions with review principle |
| **SRE** | Production operations | §9 Observability, §17 Rollback, deploy/IaC, alerts/dashboards, pipeline/merge train, production risk, failure modes |
| **Security** | AppSec / prod security | §2 Security, secrets, authN/Z, injection, dependencies/CVEs, CSRF/CORS, PII logging; §15 when AI handles user input |
| **Architect** | System design | §16 Architecture Lens, boundaries, coupling, API surface, feature-flag debt, layer violations |
| **Performance** | Latency & scale | §4 Performance, DB/ORM, N+1, caches, queues, locks, retry storms, hot-path allocations |
| **Payments SME** | Money movement | Money types, ledger/idempotency, webhooks, double-entry, audit trail, `review-rules` payments domain, §8 on payment paths |

## Selection (one primary persona)

Apply in order — **first match wins**:

1. **User override** — phrases like `as SRE`, `security persona`, `architect review`, `performance lens`,
   `payments SME`, `principal engineer` (explicit default).
2. **Repo `review-rules.yaml`** — optional top-level key:
   ```yaml
   persona: payments_sme   # principal_engineer | sre | security | architect | performance | payments_sme
   ```
3. **Auto-detect** (when user gave no persona) — strongest signal in the diff; if none, **Principal Engineer**:

| Persona | Auto-detect when |
|---------|------------------|
| **Payments SME** | Paths/hunks match payments domain in `review-rules.yaml`, or signals: `ledger`, `payment`, `checkout`, `webhook`, `refund`, `idempotency`, `settlement`, money types |
| **Security** | Auth/login/session, crypto, `password`, `token`, `secret`, `oauth`, security middleware, `go.mod`/`package.json` dependency bumps with advisories |
| **SRE** | `terraform`, `helm`, `k8s`, `Dockerfile`, deploy/CI config, prod migrations, feature-flag rollout, queue/worker infra |
| **Architect** | §16 triggers fire (cross-boundary import, new public API, >50 non-mechanical files, structural refactor) |
| **Performance** | ORM/query changes, cache layers, batch jobs, list endpoints, index migrations — without payments/security dominance |
| **Principal Engineer** | No strong specialist signal |

If **two specialists tie**, prefer **Payments SME** > **Security** > **SRE** > **Performance** > **Architect**.

## Phase 2 behavior by persona

Print once at Phase 2 start:

> **Review persona:** SRE *(auto-detected: terraform + migration in diff)*

or

> **Review persona:** Principal Engineer *(default)*

### Principal Engineer (default)

- Run all material checklist dimensions; no narrowing.
- Balance blocking vs noise; executive summary covers all score dimensions.

### SRE

- **Deep pass:** §9 (metrics, logs, traces, alerts), §17 rollback, production risk, pipeline status, merge train.
- **Findings prefix optional:** `sre ·` for ops-specific items (e.g. `sre · rollback · no feature flag`).
- **Deprioritize:** style nits, minor naming unless they affect runbooks or alert names.
- **Executive summary:** lead with Production readiness, Rollback difficulty, observability gaps.

### Security

- **Deep pass:** §2 full checklist, dependency/CVE changes, auth on changed routes, input validation, secrets scan.
- **Prefix:** `sec ·` for non-obvious security findings.
- **Never skip:** hard floors, execution path gate, secrets in diff.
- **Deprioritize:** architecture nits, perf micro-optimizations unless DoS-relevant.
- **Executive summary:** Security score and Major concerns dominated by security themes.

### Architect

- **Deep pass:** §16 Architecture Lens (load `reference/architecture-lens.md` when triggers fire; user override `architect review` forces §16).
- **Prefix:** `arch ·` (existing §16 convention).
- **Deprioritize:** nits, internal refactors with no boundary impact.
- **Executive summary:** Architecture and Maintainability scores prominent; note coupling/flag debt.

### Performance

- **Deep pass:** §4 Performance, query plans, caching, concurrency, backpressure, timeouts on I/O in hot paths.
- **Prefix:** `perf ·` for perf-specific findings.
- **Deprioritize:** docs, non-hot-path style.
- **Executive summary:** call out latency/scale risk in Major concerns when material.

### Payments SME

- **Deep pass:** money/`Decimal` types, idempotency, webhook signature/replay, ledger invariants, audit logging, §8 on payment paths; `review-rules` payments domain.
- **Prefix:** `payments ·` for domain-specific findings.
- **Context:** treat matched paths as **production-critical** (`reference/contextual-severity.md`).
- **Deprioritize:** unrelated modules outside payment boundary unless security.
- **Executive summary:** emphasize money-path risk; **Must fix** ordered by blast radius (payment correctness → infra → security → resilience).
- **Per finding (High/Critical):** require **blast radius** + **business impact** chain (`domain-overrides.md`).
- **Grouping:** merge Resilience, Jackson, date clusters; target ~8–10 top-level findings
- **Confidence:** calibrate — High for OEDR on diff line; Medium for Bucket4j+Redis, OUR auth gaps, Jackson erasure
- **High bar:** ~4–5 High max — demote inference-heavy findings to Medium (step 7a)

## Interaction with other mechanisms

| Mechanism | Interaction |
|-----------|-------------|
| Custom focus (`migrations only`) | **Overrides** persona narrowing — user focus wins |
| §16 Architecture Lens | Auto with Architect persona; trigger-gated otherwise |
| Stop searching | Unchanged unless `review-rules.yaml` sets `stop_search` |
| Feedback learning | Unchanged — personas do not disable category adaptation |
| Multi-persona request | If user asks `SRE and security`, use **Security** as primary and note *"Also applying SRE emphasis on §9/§17"* — do not run six full passes |

## Executive summary

Add to the metadata table or narrative opening:

| Field | Value |
|-------|-------|
| **Review persona** | SRE *(auto-detected)* |

Omit the row when persona is Principal Engineer and was not explicitly requested (keep default reviews clean).

## Repo example

```yaml
persona: payments_sme

payments:
  critical:
    - ledger
    - money
```
