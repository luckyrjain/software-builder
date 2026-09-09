---
workflow_version: 1.1
phase: "0"
produces: {mcp_profile: string, cli_available: boolean}
consumes:
  required: {}
  optional: {from_time: string, to_time: string, service: string}
  conditional: {}
---

# Phase 0 — MCP capability check

**Read this file** at the start of Phase 0, after inputs are parsed.

**Exit:** [phase-exit-criteria.md](../reference/phase-exit-criteria.md) §Phase 0 before Phase 1.

**Read-only:** no remediation, restart, rollback, scaling, kubectl apply, or write APIs this session.
Query and analyze only — live changes are out of scope ([SKILL.md](../SKILL.md) §Guardrails).

Detect connected servers before querying and announce the profile using **exact status suffixes**:

| Status | Meaning |
|--------|---------|
| `✅ (queried)` | Tool available **and** at least one query attempted this session |
| `(attempted — no rows)` | Query ran; zero matching rows (still counts as queried) |
| `❌` | Tool unavailable or auth failed |

Example:

> **RCA MCP profile:** Datadog ✅ (queried) | KubeSense ✅ (attempted — no rows) | GitLab ✅ | Jenkins ✅ | Jira ✅ | CLI ❌ (manual scoring)

**Forbidden profile suffixes:** do not append rationalizations such as *(not queried — Datadog sufficient)*,
*(skipped — logs empty)*, or *(not needed)*. If KubeSense is connected but not yet queried, show
`KubeSense ✅` without a suffix until Phase 1 attempts run — then update to `(queried)` or
`(attempted — no rows)`.

Full tool matrix and degraded modes: **[reference/mcp-capabilities.md](../reference/mcp-capabilities.md)** — do not duplicate the table here.

**Datadog RUM:** use when symptoms may originate from client-side errors or faulty user behavior — see
query-playbook §RUM.

**Multiple instances:** more than one GitLab or Atlassian MCP server may be connected. Match the
target by **host** — pick the GitLab server whose `GITLAB_API_URL` matches the affected repo's remote;
for Jira, **probe each Atlassian server** with `getAccessibleAtlassianResources` and use the one whose
`cloudId`/site owns the incident project. Announce which instance you used.

Degrade gracefully: if Datadog is unavailable, rely on KubeSense; if both are missing, stop and ask the user to configure an observability MCP. **If KubeSense returns data but fewer than 3 distinct signal types**, supplement with Datadog rather than treating KubeSense alone as sufficient — note which sources provided signal in `query_references[]`.

Detect the optional correlator CLI: run `incident-rca --help` and record ✅/❌ in the profile line.

**KubeSense official skill:** when KubeSense MCP is `✅`, verify **`kubesense-mcp`** is installed
([dependencies.md](../dependencies.md)). Record `kubesense-mcp ✅` or `kubesense-mcp ❌` on the profile
line. Phase 1 reads **`kubesense-logs`** before querying.

**KubeSense SPL CLI (fallback):** when MCP `body` fetch fails, check `KUBESENSE_API_KEY` is set. Record
`kubesense-spl ✅` or `kubesense-spl ❌` on the profile line. Phase 1 uses
[reference/kubesense-spl.md](../reference/kubesense-spl.md) only after MCP body attempt fails.

**Quick check — existing incident record:** if `search_datadog_incidents` is available, run it before Phase 1 queries:

```text
search_datadog_incidents: service=<service>, from=<from_time>, to=<to_time>
```

An open or recently resolved incident may already have root-cause notes, a timeline, or a linked postmortem — this can short-circuit Phase 1–3 or seed the hypothesis list. Record any match in `jira_issues[]` with `source: "datadog_incident"`.

## Multi-site Datadog

Some organisations run **multiple Datadog instances** (US1 `datadoghq.com`, EU `datadoghq.eu`, US3 `us3.datadoghq.com`, US5 `us5.datadoghq.com`, AP1 `ap1.datadoghq.com`). Incidents that span sites require querying each site independently.

**Detection:** apply this section when any of the following is true:
- `ddconfig` or user reports multiple Datadog sites.
- Querying the configured site returns zero metrics/logs for a service the user confirms exists.
- Phase 1 returns an unexpectedly empty `error_signals` array despite the user reporting clear symptoms.

**Steps:**
1. Ask the user which Datadog site(s) the affected service reports to.
2. For each site: issue Datadog MCP queries with an **explicit per-call site scope** when the tool
   supports it. When the MCP only exposes one active site, ask the user to select/switch the Datadog MCP
   session for that site — **do not** run **ddconfig** to mutate shared configuration from this skill
   ([reference/datadog-site-policy.md](../reference/datadog-site-policy.md)).
3. Collect `error_signals` and `infra_signals` from each site independently.
4. Label evidence by site: `"source": "datadog_eu"`, `"source": "datadog_us1"`, etc.
5. Record which site each query ran against in `query_references[]`.
6. **Confidence cap:** evidence requiring correlation of signals from **two different sites** is capped at **MEDIUM** — cross-site clock drift can reach ~1 minute.

If only one Datadog site is configured, skip this section.

## PagerDuty / OpsGenie detection (optional)

After detecting Datadog and KubeSense, also check for alerting/on-call MCP tools:

**PagerDuty:** look for tools named `pd_get_incident`, `pd_list_incidents`, `pagerduty_list_incidents`,
or similar PD-prefixed tools in connected MCPs.

**OpsGenie:** look for tools named `opsgenie_list_alerts`, `og_list_incidents`, or similar.

Record in the MCP profile announcement (add columns when present):

> **RCA MCP profile:** Datadog ✅ | KubeSense ✅ | PagerDuty ✅ | OpsGenie ❌ | ...

**Phase 0 quick-check (when PD or OpsGenie available):**

Run immediately after the Datadog incidents quick-check:

*PagerDuty:*
```text
pd_list_incidents: service_ids=[<service>], since=<from_time>, until=<to_time>,
                   statuses=["triggered","acknowledged","resolved"]
```

*OpsGenie:*
```text
opsgenie_list_alerts: query="tag:<service> OR alias:<service>",
                      createdAt>=<from_time>, createdAt<=<to_time>
```

For each matched alert/incident, record in `pd_alerts[]`:

```json
{
  "source": "pagerduty",
  "alert_id": "<id>",
  "title": "<summary>",
  "severity": "P1",
  "triggered_at": "<iso_utc>",
  "acknowledged_at": "<iso_utc_or_null>",
  "resolved_at": "<iso_utc_or_null>",
  "link": "<web_url>"
}
```

**Window refinement:** if `pd_alerts[].triggered_at` is earlier than the current `from_time`,
use it to pull `from_time` backward — PD alert timestamps are set by the monitoring system and
are more accurate than ticket `created_at`. Then apply Phase 0b backstroke on top.

If no PD/OG tools are available, note `| PagerDuty ❌ | OpsGenie ❌ |` in the profile and
continue — these tools are optional.
