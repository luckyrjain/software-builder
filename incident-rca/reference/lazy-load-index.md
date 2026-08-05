# Lazy-load index

Read reference files **one at a time** when the active workflow phase says to — never bulk-load.

| When | Also load |
|------|-----------|
| Phase 0 | [mcp-capabilities.md](mcp-capabilities.md); [dependencies.md](../dependencies.md) — verify `kubesense-mcp` skill installed |
| Phase 1 | **Read `kubesense-mcp` + `kubesense-logs` skills**; [query-playbook.md](query-playbook.md); [org-profiles.md](org-profiles.md) when OpenSearch/ES or KubeSense-primary; [kubesense-spl.md](kubesense-spl.md) only when MCP `body` fetch fails; [query-investigation.md](query-investigation.md) §Phase 1 APM pass **and** §Expensive-query onset signature when OpenSearch/ES; §Log coverage fallback when Datadog empty; §RUM when UI symptoms |
| Phase 2 | [query-playbook.md](query-playbook.md) (loaded in Phase 1 — already in context; use `#gitlab` / Jenkins sections) |
| Phase 3 | [query-playbook.md](query-playbook.md) (Jira §, §CloudWatch / JVM watchdog when JVM stall); [query-investigation.md](query-investigation.md) when search/DB saturation; §RUM when UI symptoms |
| Phase 4 | [evidence-schema.md](evidence-schema.md); [evidence-quality.md](evidence-quality.md); [evidence-coverage.md](evidence-coverage.md); [precedence.md](precedence.md); CLI absent → [manual-scoring.md](manual-scoring.md); [causal-graph-schema.md](causal-graph-schema.md) when writing the causal-graph artifact |
| Phase 5 | [gold-rca-excerpt.md](gold-rca-excerpt.md) (few-shot), [root-cause-depth.md](root-cause-depth.md), [evidence-quality.md](evidence-quality.md), [evidence-coverage.md](evidence-coverage.md), [causal-graph-schema.md](causal-graph-schema.md) (gate); extended template index in [report-template.md](../report-template.md) — do not bulk-load full template during live RCA |
| Any phase | [phase-exit-criteria.md](phase-exit-criteria.md) |
| Install / smoke test | [SETUP.md](../SETUP.md), [smoke-test.md](smoke-test.md) |
| Maintainer edits | [pressure-tests.md](pressure-tests.md) |

[examples.md](../examples.md) is for humans — never required during a live RCA.
