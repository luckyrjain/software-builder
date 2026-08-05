# Org profiles (domain guardrails)

Load during **Phase 1** when OpenSearch/Elasticsearch, search/DB saturation, or **KubeSense-primary**
(`logs_primary: kubesense`, e.g. **acme**) applies. Universal STOP rules stay in [SKILL.md](../SKILL.md).

**This file holds real, org-specific guardrails, not illustrative examples.** The "acme /
KubeSense-primary" section below applies only to that org's actual observability topology (Datadog logs
genuinely aren't populated there). A different org with a different setup should add its own section
following the same pattern — do not assume acme's guardrails apply to your org's Datadog/KubeSense
mix without checking.

## OpenSearch / Elasticsearch

- **Search/DB saturation** with trigger Unknown and no query investigation — run
  [query-investigation.md](query-investigation.md); **Phase 1 `aggregate_spans`**
  (`service:elasticsearch`, group by `resource_name` + `@base_service`) before trigger Unknown
- **`query_governance` vs `infra_capacity`** — when expensive-query branch fires, do not report CPU-only
  root cause; consider multi-cause co-reporting
- **ES saturation + `traffic_anomaly` change story** — correlation ≠ causation; require caller request
  rate ≥2× baseline before ranking `traffic_spike`; run expensive-query onset signature
  ([query-investigation.md](query-investigation.md) §Phase 1) first
- **CPU ↑ while ES `elasticsearch_requests` flat or declining** — mandatory expensive-query onset
  signature; do **not** rank `traffic_spike` or pure `infra_capacity` as primary without query investigation
- **Full-window ES APM only** — onset may be drowned by retry noise; require onset slice
  (`from_time` −2m → +5m) before Phase 2
- **ES saturation without MCP body attempt** when log text needed → `mcp_process_failure`; SPL CLI
  only after MCP `body` fails — cap trigger attribution at **MEDIUM** if both fail

## acme / KubeSense-primary

- Datadog application log queries are **N/A** — read **`kubesense-mcp`** + **`kubesense-logs`** skills;
  use KubeSense `analyze-logs` + `search-logs` with `body`
- Do **not** record Datadog empty log results as `log_coverage_gap`
- Field discovery: prefer `workload` filter when discovery shows `workload` and no `service`/`message`
- Split `analyze-logs` into ≤1h windows on timeout; SPL CLI only after MCP `body` fails
- **AWS-managed data stores (OpenSearch/RDS/etc.) — metrics ≠ logs:** the Datadog AWS integration on
  this org supplies **CloudWatch metrics only** (`aws.es.*`, confirmed available and reliable for
  CPU/queue/rejection signals). It does **not** forward CloudWatch **Logs** groups (e.g. OpenSearch
  index/search slow-logs) — this org has **zero logs of any source** ingested into Datadog, full stop.
  Do not spend a turn probing `search_datadog_logs` for AWS-managed-service log sources on this org;
  treat it as a known gap and go straight to: (1) confirm with ops whether the AWS-side slow-log
  publish option is enabled on the domain, (2) if enabled, route that CloudWatch Logs group to
  **KubeSense** (this org's actual log pipe), not Datadog. Record as a standing P0 gap, not a
  per-incident one, until closed.

Detail: [query-playbook.md](query-playbook.md) §Org profile — acme · [kubesense-spl.md](kubesense-spl.md)
