# Log redaction (all sources)

**Normative.** Every log line, stack trace, or request/response body copied into evidence JSON,
`sample_messages[]`, the RCA report, or chat must pass through the same secret-redaction rules before
persistence or display.

## Canonical implementation

Use `redact_secrets()` from [scripts/kubesense_logs.py](../scripts/kubesense_logs.py) — do not
re-implement ad hoc regex in workflow steps. The CLI and evidence exporters already call it; any new
log source must too.

## Sources that must redact

| Source | Where redaction happens |
|--------|-------------------------|
| KubeSense / Splunk CLI | `kubesense_logs.py` (`message`, `body_redacted`) |
| Datadog log aggregation | Apply `redact_secrets()` to each `sample_messages[]` entry before writing evidence |
| Jira ticket bodies / comments | Redact before quoting in evidence or report (tokens in pasted curl, API keys in repro steps) |
| Slack / PagerDuty snippets | Redact before `sample_messages[]` or narrative quotes |
| Manual paste from engineer | Redact before evidence JSON — never trust "I'll redact it later" |

## Verification checklist (Phase 5 pre-render)

Before rendering the final report:

1. Every `sample_messages[]` value in `evidence.json` was passed through `redact_secrets()`.
2. No raw `Authorization`, `Bearer`, `api_key`, `password=`, or PEM blocks appear outside
   `[REDACTED]` markers.
3. If a source could not be redacted (binary blob, truncated mid-token), note the gap in **Gaps**
   and omit the raw line — do not ship partial secrets.

## Partial RCA confidence

When emitting a partial/stopped report (Phase 4 skipped or incomplete), apply
`cap_partial_report_confidence()` from [scripts/incident_rca_policy_guards.py](../scripts/incident_rca_policy_guards.py)
to every hypothesis band — see [evidence-quality.md](evidence-quality.md) §Confidence caps.
