# incident-rca

**Post-incident root cause analysis** skill for Cursor. Investigates a time window across observability,
change, and ticket sources and produces an **executive-ready RCA** with a fixed report schema.

Auto-invokes from natural language (no slash command) when you ask about RCA, outages, error spikes, or
deploy regressions.

## What it does

1. **Anchors the incident window** — from your prompt, a Jira ticket (`INC-xxxx`), or Phase 0b Jira lookup.
2. **Collects evidence read-only** from connected MCP servers:
   - **Datadog** — logs, metrics, traces, change stories, incidents
   - **KubeSense** — logs, traces, metrics (optional supplement)
   - **GitLab** — merged MRs and commits near the window
   - **Jenkins** — build SHA and change sets
   - **Jira** — incident tickets, recurrence search
3. **Builds an evidence JSON bundle** (`schema_version: 4`; see [reference/evidence-schema.md](reference/evidence-schema.md)) mapping signals to hypothesis types.
4. **Ranks hypotheses** — via optional external `incident-rca` CLI, or manual scoring fallback.
5. **Writes the report** — fixed section order: customer impact, detection, timeline, ranked hypotheses
   (0–100 scores), evidence matrix, recovery analysis, corrective actions with owners. Uses
   [report-template.md](report-template.md).

**Read-only boundary:** never invoke remediation, restart, rollback, scaling, deployment, or write APIs.

## When to use

| Use incident-rca | Use instead |
|------------------|-------------|
| "RCA for service X 2–4pm UTC" | K8s rightsizing → **k8s-overprovisioning-datadog** |
| "What caused the 5xx spike?" | MR code review → **pr-review** |
| "Root cause for INC-4521" | Live rollback / paging → out of scope |
| Symptom-only, org-wide discovery | Datadog MCP missing → **ddsetup** / **ddconfig** first |
| — | Paging webhook / on-call auto-triage (unattended) → **incident-triage-agent** |
| — | Release-wide go/no-go sweep across services → **release-readiness-checker** |
| — | PG cutover regression confirmed here → follow up with **mysql-to-postgres-sql** |

## Invocation examples

`neo-disbursement-service` below (and throughout examples.md/report-template.md) is a fictional service
name used consistently across this skill's documentation — not a real internal service.

```
RCA for neo-disbursement-service 2026-06-28 14:00–16:00 UTC — 5xx on transfer-money
Root cause analysis last Tuesday 2–4pm — Kafka consumer lag
RCA for INC-4521
What caused the production incident?
```

More patterns: [examples.md](examples.md)

## What you get

A fragment of a real report shape (fictional incident, matches actual output):

> **Between 2026-06-28 14:00–16:00 UTC, `neo-disbursement-service` experienced a 5xx spike on
> `transfer-money`.** Deploy regression (MR !482) is the leading hypothesis (**HIGH** confidence):
> production deploy at 14:20 UTC preceded the error spike at 14:45 UTC with diff touching
> `TransferMoneyHandler`. Immediate action: rollback or hotfix the handler path.

Full shape: [reference/gold-rca-excerpt.md](reference/gold-rca-excerpt.md).

- **Executive summary** — primary hypothesis, confidence (HIGH / MEDIUM / LOW / UNKNOWN)
- **Customer impact & detection analysis** — users, duration, SLO, MTTD, monitoring gaps
- **Unified timeline** — deploys, errors, tickets, remediation, recovery
- **Causal graph** — vertical chain from trigger to customer-visible symptom
- **Ranked hypotheses** — reproducible 0–100 scores + mandatory counter-evidence per hypothesis
- **Evidence coverage dashboard** — completeness %, confidence ceiling, blocking gaps
- **Incident class** — quarterly-review taxonomy (Deploy, Capacity, Security, …)
- **Phase exit criteria** — gates prevent skipping investigation steps
- **Initiating event** — separated from trigger and root cause
- **Evidence matrix** — signals mapped to hypotheses with quality labels (Observed/Correlated/Inferred/Assumed)
- **Trigger / root cause / contributing factors** — layered causality; **Unknown** conclusion when evidence insufficient
- **Recovery analysis** — what ended the incident + MTTR
- **Corrective & preventive actions** — owner, priority, ETA
- **Gaps / investigation follow-up** — explicit when data or MCP sources were missing
- **Recurrence escalation** — if ≥3 similar past incidents, severity → "Systemic / requires architectural fix"

## External skill dependency — `kubesense-mcp`

When KubeSense MCP is connected, install the official skill:

```bash
make install-incident-rca-deps
```

Details: [dependencies.md](dependencies.md).

## Optional correlator CLI

The Python **`incident-rca`** correlator is a **separate tool, not in this repo**. Detect with
`incident-rca --help`. Without it, the skill scores hypotheses manually per
[reference/manual-scoring.md](reference/manual-scoring.md) and labels the report accordingly.

## Workflow (agent)

| Phase | Purpose |
|-------|---------|
| 0 | Detect connected MCP servers |
| 0b | Jira-anchored window (when `INC-xxxx` given) |
| 1 | Service/symptom scoping, org-wide discovery if needed |
| 2 | Change correlation (Datadog change stories, GitLab MRs, Jenkins) |
| 3 | Observability deep dive + recurrence JQL |
| 4 | Evidence JSON + hypothesis ranking |
| 5 | Report assembly |

Agent entry point: [SKILL.md](SKILL.md). MCP setup: [SETUP.md](SETUP.md). Query recipes:
[reference/query-playbook.md](reference/query-playbook.md).

## Quality checks

From repo root: `make lint-incident-rca` (SKILL line count, JSON parse, anchor links).

Post-install validation: [reference/smoke-test.md](reference/smoke-test.md).
