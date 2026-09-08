---
workflow_version: 1.0
phase: analyze
produces:
  - metrics_findings
  - log_findings
  - tracing_findings
  - dashboard_findings
  - alert_findings
  - slo_findings
  - correlation_id_findings
consumes:
  - service_name
  - observability_material
  - critical_path
  - correlation_id_field
---

# Analyze — evaluate coverage across seven observability categories

Run all seven checks below against `observability_material`. For any category with no material supplied
at all (per Inputs' per-category presence flag), record every check in that category as `Unknown` and move
on — do not infer, guess, or assume a clean pass from silence.

## 1. Metrics coverage — golden signals

For each component on `critical_path` (or each component named anywhere in `observability_material` when
`critical_path` wasn't supplied), check whether the four golden signals are covered: **latency**,
**traffic**, **errors**, **saturation**. A component missing all four is a `Missing` row; missing one or
two of four is `Partial`; all four present is `Present`. A component named in `critical_path` with zero
metrics material anywhere is `Unknown` for every signal, not `Missing` — the gap is in what was supplied,
not necessarily in what exists.

## 2. Log quality

- **Structured** — are log lines parseable key-value/JSON, or unstructured free text? Grep-only free text
  makes every downstream check (correlation, alerting on log content) harder.
- **Correlatable** — does the log schema/sample carry a correlation or trace ID field (see § 7)?
- **Meaningful levels** — are log levels used to distinguish signal from noise (not everything `INFO` or
  everything `ERROR`)?

## 3. Tracing coverage

For each hop on `critical_path` (service-to-service, service-to-queue, service-to-datastore), check
whether spans are instrumented on **both sides** of the hop and whether trace context is actually
propagated across it (a span on each side that doesn't share a trace ID is not coverage — it's two
disconnected traces). Record the sampling rate if documented; an undocumented sampling rate is a gap in
its own right (can't reason about trace completeness without it). A hop with zero tracing material is
`Unknown`, not `No spans` — only mark `No spans` when the supplied material shows the hop is instrumented
on one side but not the other, or not at all despite tracing material existing for neighboring hops.

## 4. Dashboards

- Does a top-level dashboard answer "is `<service_name>` healthy right now" without drilling in?
- Are the golden signals from § 1 represented on it?
- Is there a drill-down path from a symptom (elevated latency/errors) to the specific component/hop
  responsible?

## 5. Alerts

- **Symptom-mapped, not just cause-mapped** — does at least one alert fire on a golden-signal/SLO breach
  (a symptom a user would feel), not only on internal-cause signals (e.g. CPU% alone) that may or may not
  correlate with user impact?
- **Actionable thresholds** — is there a stated rationale for each threshold (tied to an SLO, a known
  capacity limit, historical baseline), or is it an arbitrary round number with no stated basis (a common
  source of alert fatigue)?
- **Runbook/owner routing** — does the alert rule reference a runbook or an owning team/rotation?

## 6. SLOs

For each SLO defined in `observability_material`: is a target and measurement window explicitly stated
(not just an aspirational sentence)? Is it measured by a real SLI (an actual metric/query), not a proxy
with no defined relationship to the SLO? Is there at least one alert (burn-rate or threshold) tied to it —
an SLO nothing alerts on cannot protect anything in practice, however well-defined its target is.

## 7. Correlation IDs

- **Generated at ingress** — is a correlation/trace ID assigned at the system's entry point (edge/gateway),
  not invented ad hoc partway through?
- **Propagated end-to-end** — does it survive every critical-path hop (including async boundaries: queues,
  background jobs), or does it get dropped at a hop?
- **Consistently present** — does the same ID show up in logs, traces, *and* alert/incident payloads, so a
  responder can pivot between them, or do different subsystems use different, unlinked identifiers?

## Evidence gaps

Any individual check that cannot be completed — because its category has no supplied material, or because
the supplied material is ambiguous/contradictory — is recorded as `Unknown` for that specific check, with
a one-line reason, not silently skipped and not folded into a `Yes`/`No`/`Present`/`Missing` call. This
feeds Report's Unknown handling directly: a check Analyze marks `Unknown` renders as `Unknown` in
`OBSERVABILITY_REVIEW_REPORT.md`, never silently upgraded or downgraded.
