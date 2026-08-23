# Examples — invocation patterns

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation table

| # | Caller sends | Behavior |
|---|--------------|----------|
| 1 | `service_name: checkout-service` + material for all seven categories, every check clean | Inputs → Analyze → Report → **Coverage: Adequate** |
| 2 | Same, but the top-level dashboard is missing the saturation signal, otherwise clean | Coverage: **Partial gaps** |
| 3 | Tracing material shows the `checkout-service` → `payments-service` hop has no span on the receiving side | Coverage: **Critical gaps** (proven — hop instrumented on one side only) |
| 4 | An SLO is defined with a target and window, but no alert rule anywhere references it | Coverage: **Critical gaps** (SLO not tied to an alert) |
| 5 | `observability_material` supplied only for Metrics and Dashboards — nothing for Logs, Tracing, Alerts, SLOs, Correlation IDs | Coverage: **Unknown — insufficient input** — five sections `Unknown`, never upgraded to `Adequate` |
| 6 | `service_name` missing | Inputs **HARD STOP** — ask, no Analyze |
| 7 | `observability_material` absent entirely | Inputs **HARD STOP** — ask, no Analyze |
| 8 | Alert rules supplied, thresholds reasonable, but none has a runbook/owner field | Alerts § Runbook = No, other Alerts checks clean → Coverage: **Partial gaps** (not Critical — no proven severe gap) |
| 9 | `critical_path` names a hop with zero tracing material anywhere in `observability_material` | Tracing row for that hop: **Unknown**, not "No spans" — never assessed ≠ proven absent |
| 10 | "RCA for checkout-service, error rate spiking right now" | **Wrong skill** → **incident-rca** directly |
| 11 | "Is this release ready to ship?" | **Wrong skill** → **deployment-risk-review** directly |

---

### Scenario: Full coverage, happy path

**Caller:** `service_name: checkout-service`, `observability_material` covering all seven categories —
golden-signal metrics for every critical-path component, structured logs carrying `trace_id`, spans on
both sides of every critical-path hop with a documented 10% sampling rate, a top-level health dashboard
showing all four golden signals with drill-down, symptom-mapped alerts with runbook links, one SLO
(99.9% availability, 30-day window) wired to a burn-rate alert, and a correlation ID propagated across
every critical-path hop.

**Agent:**

1. Inputs — `service_name` and all seven categories of `observability_material` parsed; `critical_path`
   inferred from the tracing config (`checkout-service` → `payments-service` → `ledger-service`).
2. Analyze — all seven checks pass clean across every component/hop.
3. Report — no `Critical gaps`, `Partial gaps`, or `Unknown` findings → **Adequate**.

**Expected fragment:**

```
# Observability review — checkout-service

**Coverage: Adequate**

## Metrics

| Component | Golden signal | Status | Evidence |
|-----------|----------------|--------|----------|
| `checkout-service` | Latency | Present | `checkout_request_duration_seconds` histogram |
| `checkout-service` | Errors | Present | `checkout_requests_total{status=~"5.."}` |

## Tracing

| Critical-path hop | Status | Evidence |
|--------------------|--------|----------|
| `checkout-service to payments-service` | Spans present | Both sides instrumented, shared `trace_id`, 10% sampling documented |

## SLOs

| SLO | Target/window defined | Measured by a real SLI | Tied to an alert | Evidence |
|-----|------------------------|--------------------------|-------------------|----------|
| `checkout-availability` | Yes | Yes | Yes | 99.9% over 30d, burn-rate alert `checkout-slo-burn-fast` |
```

---

### Scenario: Proven critical gap — SLO with no alert

**Caller:** Same service, but the SLO section of `observability_material` defines `checkout-availability`
(99.9%, 30-day window, measured by a real SLI) with no alert rule anywhere in the supplied material
referencing it.

**Agent:**

1. Inputs — all six categories parsed.
2. Analyze § 6 — SLO target/window defined ✓, measured by a real SLI ✓, tied to an alert — searched every
   supplied alert rule, none references `checkout-availability` → **No**.
3. Report — an SLO with no alert tied to it is a proven `Critical gaps` finding per
   [report-format.md § Rules](reference/report-format.md#rules) → **Critical gaps**, regardless of every
   other category being otherwise clean.

**Expected fragment:**

```
# Observability review — checkout-service

**Coverage: Critical gaps**

> `Critical gaps — checkout-availability SLO has no alert tied to it; see SLOs below.`

## SLOs

| SLO | Target/window defined | Measured by a real SLI | Tied to an alert | Evidence |
|-----|------------------------|--------------------------|-------------------|----------|
| `checkout-availability` | Yes | Yes | No | 99.9% over 30d defined in SLO config; no matching alert rule found in supplied alert material |
```

---

### Scenario: Insufficient input across most categories

**Caller:** `service_name: legacy-batch-worker`, `observability_material` containing only a metrics
definitions file and a dashboard JSON export — no logs, tracing, alerts, or SLO material supplied.

**Agent:**

1. Inputs — Metrics and Dashboards categories have material; Logs, Tracing, Alerts, SLOs, and Correlation
   IDs do not.
2. Analyze — Metrics and Dashboards checks run normally (both come back clean in this example); the five
   uncovered categories are recorded `Unknown` throughout, not guessed.
3. Report — no `Critical gaps` proven, but five categories are wholly unassessed → **Unknown — insufficient
   input** outranks `Partial gaps`/`Adequate` per the fixed precedence.

**Expected fragment:**

```
# Observability review — legacy-batch-worker

**Coverage: Unknown — insufficient input**

> `Unknown — insufficient input — no material supplied for Logs, Tracing, Alerts, SLOs, or Correlation IDs; see those sections.`

## Logs

| Check | Status | Evidence |
|-------|--------|----------|
| Structured (parseable key-value/JSON) | Unknown | No log material supplied |
| Correlatable (carries a correlation/trace ID field) | Unknown | No log material supplied |
| Log level usage is meaningful (not everything INFO/ERROR) | Unknown | No log material supplied |
```

---

### Scenario: Degraded path — tracing material covers only one of two hops

**Caller:** `critical_path: [checkout-service → payments-service, payments-service → ledger-service]`, but
`observability_material`'s tracing config only documents the first hop; nothing at all for the second.

**Agent:** Analyze § 3 cannot complete the tracing check for the `payments-service → ledger-service` hop —
no material to inspect. Per [workflow/analyze.md § Evidence gaps](workflow/analyze.md#evidence-gaps), this
is recorded `Unknown` for that hop specifically, not `No spans` (which would fabricate a finding no
material actually supports) and not silently dropped from the table.

**Expected fragment:**

```
## Tracing

| Critical-path hop | Status | Evidence |
|--------------------|--------|----------|
| `checkout-service to payments-service` | Spans present | Both sides instrumented, shared trace_id |
| `payments-service to ledger-service` | Unknown | No tracing material supplied for this hop |
```

Coverage verdict is at least `Partial gaps` from this hop alone: Tracing has some material (hop 1 assessed
clean), so it does not satisfy [workflow/report.md § Report](workflow/report.md)'s `Unknown — insufficient
input` tier, which requires every check in the category to be `Unknown`; a single gapped hop inside an
otherwise-assessed category falls to `Partial gaps` instead (no `Critical gaps` proven elsewhere in this
example).

---

### Scenario: Cross-skill — critical gap explains slow detection, ahead of a release

**Caller:** Same `checkout-service` review surfaces both a `Critical gaps` finding (no tracing across the
`checkout-service → payments-service` hop) and, in conversation, the caller mentions this review is
happening the week before a major `checkout-service` release.

**Agent:** Per [SKILL.md § Cross-skill escalation](SKILL.md#cross-skill-escalation), a tracing gap that
would plausibly slow incident detection gets an **incident-rca** pointer, and gaps found ahead of an
upcoming release get a **deployment-risk-review** pointer — both apply here, so Report's Notes section
offers both handoffs rather than picking one:

```
## Notes

Critical gap: no tracing spans across `checkout-service` to `payments-service` — this would slow
root-cause detection during a future incident on that path; consider running **incident-rca** if a
relevant incident occurs. This review was requested ahead of an upcoming release — consider running
**deployment-risk-review** for `checkout-service` before shipping, using this report as input.
```
