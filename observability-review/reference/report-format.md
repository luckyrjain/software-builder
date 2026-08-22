# OBSERVABILITY_REVIEW_REPORT.md format

**Normative.** The exact structure [workflow/report.md](../workflow/report.md) must produce.

## Safe rendered-output boundary

`service_name`, `critical_path` entries, `correlation_id_field`, and every excerpt pulled from the
supplied `observability_material` (metrics definitions, log samples, tracing/span config, dashboard
definitions, alert rules, SLO definitions) are caller-/repository-supplied, untrusted content per
[prompt-injection.md](../../docs/skill-framework/shared/prompt-injection.md). All of it can render directly
into `OBSERVABILITY_REVIEW_REPORT.md` table cells and evidence quotes:

1. **Structurally escape or fence newlines, leading `#`/`>`/`-`, table `|` delimiters, and unbalanced
   triple-backtick fences in every one of them, always.**
2. Wrap short identifier-shaped values (paths, names, refs) in an inline code span, first **removing**
   any backtick already in it
   ([safe-output.md § Rule 4](../../docs/skill-framework/shared/safe-output.md#rule-4-markdown-chat-escaping)).

Log excerpts and pasted config are free-text evidence pulled straight from the reviewed material, the
same class of source [safe-output.md § Rule 5](../../docs/skill-framework/shared/safe-output.md#rule-5-pii-secret-redaction-in-rendered-output)
targets — **redact** plausible credentials/tokens/PII (bearer tokens, API keys, emails) before quoting a
raw log line or config excerpt, and note that redaction was applied. Every quoted excerpt is also
structurally escaped/fenced per rule 1 above, independent of whether it needed redaction.

## Structure (order fixed)

```markdown
# Observability review — <service_name>

**Coverage: <Adequate | Partial gaps | Critical gaps | Unknown — insufficient input>**

<When not Adequate, one line naming which category/categories set the verdict — never just the bare
state.>
> e.g. `Critical gaps — no tracing spans found across the checkout to payments hop; see Tracing below.`
> e.g. `Unknown — insufficient input — no alert rules or SLO definitions were supplied; see Alerts, SLOs.`

## Metrics

| Component | Golden signal | Status | Evidence |
|-----------|----------------|--------|----------|
| `<component>` | Latency \| Traffic \| Errors \| Saturation | Present \| Partial \| Missing \| Unknown | <metric name / definition excerpt, or "no metrics material supplied for this component"> |

## Logs

| Check | Status | Evidence |
|-------|--------|----------|
| Structured (parseable key-value/JSON) | Yes \| Partial \| No \| Unknown | <log schema/sample excerpt> |
| Correlatable (carries a correlation/trace ID field) | Yes \| Partial \| No \| Unknown | <field name found, or "none found"> |
| Log level usage is meaningful (not everything INFO/ERROR) | Yes \| Partial \| No \| Unknown | <observation> |

## Tracing

| Critical-path hop | Status | Evidence |
|--------------------|--------|----------|
| `<hop, e.g. checkout-service to payments-service>` | Spans present \| Partial \| No spans \| Unknown | <span/instrumentation excerpt, or "no tracing material supplied"> |

Sampling rate documented: <Yes/value \| No \| Unknown>. Context propagated across the hop (not just
instrumented locally): <Yes \| No \| Unknown>.

## Dashboards

| Check | Status | Evidence |
|-------|--------|----------|
| Top-level "is it healthy" view exists | Yes \| Partial \| No \| Unknown | <dashboard name/description excerpt> |
| Golden signals represented on it | Yes \| Partial \| No \| Unknown | <which signals present/absent> |
| Drill-down path from symptom to component exists | Yes \| Partial \| No \| Unknown | <observation> |

## Alerts

| Check | Status | Evidence |
|-------|--------|----------|
| Alerts map to symptoms (SLO/golden-signal breach), not just internal causes | Yes \| Partial \| No \| Unknown | <alert rule excerpt> |
| Thresholds are actionable (not arbitrary/static-noisy) | Yes \| Partial \| No \| Unknown | <threshold + rationale, or "no rationale supplied"> |
| Runbook/owner routing present | Yes \| Partial \| No \| Unknown | <link/owner field, or "none found"> |

## SLOs

| SLO | Target/window defined | Measured by a real SLI | Tied to an alert | Evidence |
|-----|------------------------|--------------------------|-------------------|----------|
| `<SLO name>` | Yes \| No \| Unknown | Yes \| No \| Unknown | Yes \| No \| Unknown | <SLO definition excerpt, or "no SLO material supplied"> |

## Correlation IDs

| Check | Status | Evidence |
|-------|--------|----------|
| Generated at ingress | Yes \| Partial \| No \| Unknown | <field/mechanism found> |
| Propagated across every critical-path hop | Yes \| Partial \| No \| Unknown | <hop-by-hop observation> |
| Present consistently in logs, traces, and alerts | Yes \| Partial \| No \| Unknown | <cross-reference observation> |

## Notes

<Any category with zero supplied material (recorded as Unknown throughout, not guessed); any redaction
applied to a quoted excerpt; any `critical_path` inferred rather than supplied.>
```

## Rules

- **Every check in every one of the seven sections appears in the report even when clean or when no
  material was supplied** — a clean check still gets a row, and an unassessed one gets `Unknown`, never a
  silently omitted row.
- **Coverage verdict derivation is fixed, four states, precedence `Critical gaps` > `Unknown — insufficient
  input` > `Partial gaps` > `Adequate`** (per [workflow/report.md](../workflow/report.md)):
  - `Critical gaps` — a **proven** severe finding from supplied material: a critical-path hop with no
    tracing spans at all, a core component missing every golden-signal metric, an SLO with no alert tied
    to it, or no correlation-ID propagation across a critical-path hop.
  - `Unknown — insufficient input` — one or more of the seven categories had **no supplied material to
    evaluate**, and no `Critical gaps`/`Partial gaps` finding was otherwise proven from what *was*
    supplied. An unassessed category is not the same as a clean one.
  - `Partial gaps` — every category had some material to assess, and at least one check is `Partial` or
    `No` short of the `Critical gaps` bar (e.g. alerts present but noisy/no runbook, a dashboard missing
    one golden signal).
  - `Adequate` — every category assessed, no `Critical gaps`, `Partial gaps`, or `Unknown` findings.
- **An evidence gap (no material supplied for a category) is its own state (`Unknown`) or an explicit
  per-row `Unknown` flag — never silently merged into a clean pass or folded into `Critical gaps`/`Partial
  gaps`.** Not having alert rules to review is a gap in the review, not proof the alerts are bad.
