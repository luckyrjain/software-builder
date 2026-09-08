# Contextual (adaptive) severity

**Severity depends on path context** — not on issue type alone. The same defect class (e.g. missing
logging) is **High** on a checkout payment handler and **Low** on an admin dashboard widget.

Load with `reference/severity-rubric.md` in Phase 2. Apply **after** classifying the defect, **before**
the L×I matrix and hard floors.

## Scoring flow (every finding except nits/praise)

1. **Classify path context** for the finding's anchor `file:line`.
2. **Classify issue type** (observability gap, test gap, perf, error handling, …).
3. Look up **target Overall band** in the [context table](#context--issue-type-matrix) (or derive L/I).
4. Run the **risk matrix**; apply **hard floors** from `reference/severity-rubric.md` — floors win if higher.
5. **State context in the finding** — required on the Likelihood/Impact line:

   ```
   Likelihood: High · Impact: Medium · Overall: High · Context: checkout/payment (production-critical)
   ```

Do **not** assign a flat severity per issue label (e.g. never "missing logging → always Medium").

## Path context tiers

Assign **one** tier per anchor path (highest match wins):

| Tier | Meaning | Detection |
|------|---------|-----------|
| **production-critical** | Money, auth, checkout, webhooks, prod migrations, PII | `review-rules.yaml` domain **`critical`** match; or path/hunk signals: `checkout`, `payment`, `ledger`, `billing`, `webhook`, `auth`, `login`, `otp`, `settlement`, `refund`, `idempotency`, prod `migrate/` |
| **elevated** | Important but not money-path | `review-rules.yaml` domain **`high`** match; or `api/`, `worker`, `consumer`, `handler`, public routes |
| **standard** | Default production code | Anything not matched below |
| **internal** | Admin, tools, low-traffic backoffice | YAML `context.internal` patterns; or `admin`, `dashboard`, `backoffice`, `internal/`, `debug`, `tooling`, `scripts/` (non-deploy) |
| **generated** | Locks, vendor, dist | Do not report style/obs nits — security only |

Optional in `review-rules.yaml`:

```yaml
context:
  production_critical:
    - checkout
    - payment
  internal:
    - admin
    - dashboard
```

Repo **domain blocks** (`payments.critical: [ledger, …]`) also mark those paths **production-critical**
for adaptive severity.

## Context × issue-type matrix

Target **Overall** before hard floors (pick L/I that justify the band via the matrix):

| Issue type | production-critical | elevated / standard | internal |
|------------|---------------------|---------------------|----------|
| **Missing logging / metrics / tracing** on new/changed prod path | **High** | **Medium** | **Low** |
| **Missing tests** on new logic | **High** | **Medium** | **Low** |
| **Missing timeout / retry policy** on external I/O | **High** | **Medium** | **Low** |
| **N+1 / hot-path perf regression** | **High** | **Medium** | **Low** |
| **Weak error handling** (swallowed errors, generic catch) | **High** | **Medium** | **Low** |
| **Missing feature-flag observability** | **Medium** | **Low** | **Low** / omit |
| **Scope creep** (unrelated files) | **Medium** | **Medium** | **Low** |
| **Naming / style / doc gap** | **Low** | **Low** | **Nit** / omit |

### Canonical examples (observability)

| Location | Issue | Context | Overall |
|----------|-------|---------|---------|
| `checkout/payment/capture.go` | No structured logging on success/failure path | production-critical | **High** |
| `services/orders/handler.go` | No request duration metric on list endpoint | elevated | **Medium** |
| `admin/dashboard/stats.go` | No logging on rarely-used widget refresh | internal | **Low** |

Same issue class — different context — different severity. Cite **why** in the comment: *"Payment
capture is production-critical; missing logs block incident response on money failures."*

## Interaction with repo rules

| Source | Role |
|--------|------|
| `review-rules.yaml` domains | Set context tier + domain-specific hints (idempotency, terraform, …) |
| `domain-overrides.md` | When no YAML: treat payments/auth/migration paths as **production-critical** |
| Hard floors | Always ≥ matrix result (secrets, injection, AC gaps, …) |
| Review principle | **internal** + trivial obs gap → omit if value < effort |

When `review-rules.md` domain tier and contextual severity both apply, use **contextual severity** as
the primary Overall — do not stack an extra "+1 notch" on top unless a hard floor requires it.

## Findings table

Prefer showing context in the **Finding** column when helpful:

| Score | Overall | L | I | Conf | Location | Finding |
|-------|---------|---|---|------|----------|---------|
| 6 | 🟠 High | H | M | High | `checkout/pay.go:88` | **ctx: production-critical** — no structured logging on payment capture |

Optional compact form: prefix `obs ·` / `test ·` / `perf ·` plus context in prose.

## §9 Observability checklist

When §9 flags a gap, **do not default to Medium**. Run this file's matrix using the anchor path's
context tier first.
