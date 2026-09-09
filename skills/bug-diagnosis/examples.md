# Examples — bug-diagnosis

Conventions: [examples-conventions](../../docs/skill-framework/shared/examples-conventions.md).

## Invocation

Invoke `bug-diagnosis` ambiently whenever a bug, test failure, or performance regression needs its
root cause found — outside a live production incident. It is read-only and report-only: confirm a
repro, form and actively falsify candidate root causes, and emit `BUG_DIAGNOSIS_REPORT.md` /
`bug_diagnosis_report`; never edit source, tests, or configuration to fix anything.

| # | Caller sends | Resolves to | Notes |
|---|-----------------|---------------|-------|
| 1 | "Diagnose this bug: the checkout button submits the order twice when clicked rapidly." | Inputs → Repro → Hypotheses → Report: confirmed repro + confirmed root cause | Happy path |
| 2 | "Why is test_payment_retry failing intermittently in CI?" | Inputs → Repro → Hypotheses → Report: repro reported unconfirmed, reason stated | Unconfirmed repro path |
| 3 | "What's the root cause of this test failure in test_order_totals — I think it's a timezone bug?" | Hypotheses phase actively falsifies the timezone candidate and rejects it, then finds and confirms the real cause | Falsified hypothesis |
| 4 | "Diagnose this bug for me, I'm not sure what's wrong yet." | HARD STOP — ask for the specific symptom (error text, failing assertion, or measured behavior) | Missing-symptom HARD STOP |
| 5 | "We have a live production incident — the checkout service is down for everyone right now." | Wrong scope — offer `incident-rca` instead | Wrong-skill row |
| 6 | "Can you reproduce this bug where file uploads over 10MB silently fail?" | Inputs → Repro → Hypotheses → Report: repro confirmed via a specific traced input/state combination | Repro-focused path |
| 7 | "What's the root cause of this bug that keeps showing up across every service touching the shared cache layer?" | Root cause confirmed as structural; Report offers `codebase-architecture-review` | Cross-skill handoff (structural) |
| 8 | "Diagnose this bug in resolve_discount() — customers are getting the wrong discount amount." | Root cause confirmed; Report offers `loop-task-implementer` to apply the fix, never applies it itself | Cross-skill handoff (implementer) |

## Example: confirmed repro and confirmed root cause

**Evidence:** the checkout button's click handler has no debounce; a failing test
`test_checkout_double_submit` reproduces two orders from one rapid double-click.

**Result:**

```
## Symptom and repro

| Field | Value |
|-------|-------|
| Symptom | Checkout button submits the order twice on rapid click |
| Repro status | confirmed |
| Repro evidence | `test_checkout_double_submit` fails: 2 orders created from 1 rapid double-click |

## Root cause

Confirmed (high confidence): `submitOrder()` in `checkout.js:88` has no debounce/disable-on-submit
guard, so a second click before the first request resolves fires a second order. Evidence:
`checkout.js:88`, `test_checkout_double_submit`.
```

A root cause is only stated as confirmed once cited evidence backs both the repro and the cause.

## Example: repro cannot be confirmed, stated explicitly

**Evidence:** `test_payment_retry` fails roughly 1 in 20 CI runs with no consistent input or timing
that reproduces it on demand.

**Result:**

```
## Symptom and repro

| Field | Value |
|-------|-------|
| Symptom | test_payment_retry fails intermittently: AssertionError: expected 3 retries, got 2 |
| Repro status | unconfirmed |
| Repro evidence | No consistent input/timing combination reproduces the failure on demand; CI shows ~1-in-20 flake rate |

## Root cause

Unresolved — no candidate has been falsified against a confirmed repro; a race condition in the
retry counter is suspected but not yet isolated.
```

An unconfirmed repro is reported as such, never inferred as confirmed from surrounding plausibility.

## Example: a hypothesis is actively falsified and rejected

**Evidence:** `test_order_totals` fails; the caller suspects a timezone bug. Tracing the failing
input shows the order and its totals are computed and asserted in the same UTC context — no
timezone conversion occurs on this path at all.

**Result:**

```
## Hypotheses tested

| Hypothesis | Falsification attempt | Result | Evidence |
|------------|--------------------------|--------|----------|
| Timezone conversion mismatch | Traced the failing input through `compute_totals()`; both the computed and asserted values use UTC, no conversion occurs on this path | rejected | `totals.py:41-58` |
| Rounding mode mismatch between `compute_totals()` and the test fixture | Traced both call sites; the test fixture uses `ROUND_HALF_UP`, `compute_totals()` uses `ROUND_HALF_EVEN` | survived | `totals.py:52`, `test_order_totals.py:19` |

## Root cause

Confirmed (high confidence): rounding-mode mismatch between `compute_totals()`
(`ROUND_HALF_EVEN`) and the test fixture's expected value (`ROUND_HALF_UP`).
```

The initially suspected candidate is listed and rejected with the evidence that ruled it out, not
silently dropped once a better candidate is found.

## Degraded path: caller supplies no concrete symptom

**Evidence:** the caller says "Diagnose this bug for me" with no error text, failing test, or
measured behavior named.

**Result:** **HARD STOP.** The skill asks for the specific observation — the exact error message,
failing assertion, or measured latency — before proceeding to the Repro phase. "Something is broken"
alone never satisfies the `symptom` input.

## Cross-skill handoff: root cause confirmed, fix handed to loop-task-implementer

**Evidence:** the root cause is confirmed as a missing null check in `resolve_discount()`; a
`None` customer-tier value reaches the discount calculation unguarded.

**Result:**

```
## Recommendation

Root cause confirmed: `resolve_discount()` in `pricing.py:114` does not guard against a `None`
customer tier before indexing the discount table. Handing off to `loop-task-implementer` to apply
the fix — this report makes no source, test, or configuration change.
```

`loop-task-implementer` is named only because a root cause was confirmed; the escalation is offered,
never invoked automatically.
