# Phase exit criteria

Normative gates — **do not advance** to the next phase until exit criteria pass or the user explicitly
opts to stop (partial report per [phase-5.md](../workflow/phase-5.md)). Detail stays here; workflow files
link one-line reminders.

## Inputs

- [ ] `from_time` / `to_time` confirmed (or `jira_key` for Phase 0b path)
- [ ] Timezone confirmed when ambiguous
- [ ] ≥1 anchor parsed (service, INC-, symptom, namespace, deploy SHA, consumer group, etc.)
- [ ] Window validation warnings addressed or user confirmed

## Phase 0 — MCP capability check

- [ ] `mcp_profile` announced with correct suffixes (`✅ (queried)`, `(attempted — no rows)`, `❌`)
- [ ] `cli_available` set (`incident-rca --help` or manual fallback noted)
- [ ] ≥1 observability MCP available (Datadog or KubeSense) — else stop and offer setup

## Phase 0b — Jira-anchored window *(INC-xxxx path only)*

- [ ] Ticket fetched; window refined from ticket + comments
- [ ] Phase 0b backstroke applied to Phase 1 queries when applicable

## Phase 1 — Symptom detection

- [ ] Service scoped or org-wide top-3 confirmed
- [ ] `error_signals` and/or `infra_signals` collected **or** explicit none documented
- [ ] OpenSearch/ES APM pass completed when ES involved
- [ ] **Expensive-query onset signature** completed when ES saturated (CPU vs throughput, onset APM slice, caller baseline)
- [ ] Wildcard `POST /?/_search` (or equivalent) flagged → query-string hunt attempted
- [ ] Log-coverage fallback attempted when triggered (KubeSense mandatory)
- [ ] **KubeSense-primary profile** — when `logs_primary: kubesense` / mpokket: MCP `body` attempted for log text (SPL if MCP fails); no Datadog log gap recorded
- [ ] Phase 1 checkpoint announced (signal density: strong / sparse / none)
- [ ] User proceed confirmed when **sparse**; do not auto-advance on **none** without user OK

## Phase 2 — Change correlation

- [ ] `deploy_events` queried ±30 min before window
- [ ] Deploy/change timeline summarized in chat
- [ ] Phase 2 checkpoint announced

## Phase 3 — Tickets, timeline, query investigation

- [ ] Jira/recurrence JQL run (project keys confirmed or noted in Gaps)
- [ ] Unified timeline assembled with **Evidence quality** per row
- [ ] Detection metadata recorded (`detected_by`, MTTD)
- [ ] Query investigation complete when saturation branch triggered
- [ ] Missing telemetry domains noted for coverage dashboard

## Phase 4 — Correlate & rank

- [ ] Minimum evidence gate passed **or** blocked report path chosen
- [ ] Hypothesis deduplication applied — no split causal chain
- [ ] **Conflicting evidence** resolved or documented — do not rank until contradiction explained
- [ ] Evidence JSON written; CLI or manual scoring complete
- [ ] Causal-graph artifact written and `validate_causal_graph.py` passes (or Gaps note if validation skipped)
- [ ] Confidence caps applied; **no primary if all hypotheses ≤ MEDIUM after caps**
- [ ] [Evidence coverage](../reference/evidence-coverage.md) dashboard computed
- [ ] `incident_class` set from mapping

## Phase 5 — Render report

- [ ] All mandatory sections per [report-template.md](../report-template.md)
- [ ] Evidence coverage section + confidence ceiling when below HIGH
- [ ] Supporting and contradicting evidence blocks for each ranked hypothesis
- [ ] Causal graph acyclic; feedback loops described separately if present
- [ ] Post-RCA actions table in chat (not in report body CTAs)
