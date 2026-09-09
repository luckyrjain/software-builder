# Log redaction (all sources)

**Normative.** Every log line, stack trace, or request/response body copied into evidence JSON,
`sample_messages[]`, the RCA report, or chat must pass through the same secret-redaction rules before
persistence or display.

## Canonical implementation

Use `redact_secrets()` from [scripts/kubesense_logs.py](../scripts/kubesense_logs.py) — do not
re-implement ad hoc regex in workflow steps. The CLI and evidence exporters already call it; any new
log source must too. Covers `Authorization`/`Bearer`/`Basic` auth headers, `api_key`/`x-api-key`,
`password`/`passwd`/`pwd`, PEM private-key/certificate blocks (JSON-quoted and `key=value` forms), plus GitHub/OpenAI/AWS token prefixes, JWTs and `client_secret` values — the log profile of the shared table in `docs/skill-framework/shared/redaction.py`.

## Sources that must redact

| Source | Where redaction happens | Enforcement |
|--------|-------------------------|-------------|
| KubeSense / Splunk CLI | `kubesense_logs.py` (`message`, `body_redacted`) | Automated — the fetcher calls `redact_secrets()` itself, code-level |
| Datadog log aggregation | Apply `redact_secrets()` to each `sample_messages[]` entry before writing evidence | Agent-followed at ingestion + automated at Phase 5 (below) |
| Jira ticket bodies / comments | Redact before quoting in evidence or report (tokens in pasted curl, API keys in repro steps) | Agent-followed at ingestion + automated at Phase 5 |
| Slack / PagerDuty snippets | Redact before `sample_messages[]` or narrative quotes | Agent-followed at ingestion + automated at Phase 5 |
| Manual paste from engineer | Redact before evidence JSON — never trust "I'll redact it later" | Agent-followed at ingestion + automated at Phase 5 |

These four arrive as MCP tool results or human input directly into the agent's context — there is
no Python ingestion path to instrument the way `kubesense_logs.py` is. The Phase 5 check below
covers all five sources uniformly by scanning what actually got written to disk, regardless of
which source it came from.

## Verification checklist (Phase 5 pre-render)

Before rendering the final report:

1. Run `python3 scripts/verify_redaction.py evidence.json <report file>` — **automated**, not just
   a manual reminder. Exit 0 required. It reuses `redact_secrets()` directly (not a second copy of
   the pattern list) so it can never drift out of sync with what the automated KubeSense path
   actually catches.
2. Every `sample_messages[]` value in `evidence.json` was passed through `redact_secrets()` — item
   1 verifies this mechanically.
3. If a source could not be redacted (binary blob, truncated mid-token), note the gap in **Gaps**
   and omit the raw line — do not ship partial secrets.

## Partial RCA confidence

When emitting a partial/stopped report (Phase 4 skipped or incomplete), apply
`cap_partial_report_confidence()` from [scripts/incident_rca_policy_guards.py](../scripts/incident_rca_policy_guards.py)
to every hypothesis band — see [evidence-quality.md](evidence-quality.md) §Confidence caps.
