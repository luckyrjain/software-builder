# MCP capabilities — domain comprehension

**Re-verify each session** — tool availability changes across MCP upgrades.

Read-only boundary: no GitLab writes, no Datadog mutations, no deploys.

## Session 0b (squad mapping)

**Delegated to squad-map skill.** GitLab and Datadog MCP setup for ownership mapping:
[squad-map/reference/mcp-capabilities.md](../../squad-map/reference/mcp-capabilities.md).

Session 0b invokes squad-map — do not duplicate 0b tool tables here.

## Profile line (comprehension)

Announce at Session 0 start (and after 0b completes):

> **Comprehension MCP profile:** GitLab ✅ (queried) | Datadog ✅ (queried) | KubeSense ✅ (queried) | understand-anything ✅

| Status | Meaning |
|--------|---------|
| `✅ (queried)` | Tool available and at least one query attempted |
| `✅` | Connected, not yet queried this session |
| `❌` | Unavailable or auth failed |

Forbidden suffixes: *(not needed)*, *(skipped)* — use `❌` or `✅` only.

**Multiple GitLab instances:** match `GITLAB_API_URL` to repo `origin` host.

## Datadog (`plugin-datadog-datadog`) — P2b only

| Capability | Tool | Phase | Use |
|------------|------|-------|-----|
| Service dependencies | `search_datadog_service_dependencies` | P2b | Upstream/downstream architecture |
| Span aggregation | `aggregate_spans` | P2b | Top peers for disputed edges (bounded) |
| Raw spans | `search_datadog_spans` | P2b | Sample traces for disputed hops only |

**Required:** `telemetry.intent` on every Datadog call (English, no secrets).

P2b: `search_datadog_service_dependencies(service: "<name>", direction: downstream|upstream)`.

For service catalog / team tags (Session 0b), use **squad-map** skill.

**Setup:** If P2b tools missing → **ddsetup** / **ddconfig**; skip P2b runtime validation.

## KubeSense — P2b only

| Capability | Tool | Phase | Use |
|------------|------|-------|-----|
| Log search | `search-logs` | P2b | Error message patterns, last 24h default |
| Log analysis | `analyze-logs` | P2b | Workload/namespace-scoped error pattern summary |

Quote exact error message strings — do not paraphrase. Record: workload, namespace, log filter SQL.

**Setup:** If P2b tools missing → treat as ❌; skip KubeSense evidence, note in `KNOWN_OMISSIONS.md`.

## understand-anything

Not MCP — plugin skill for P0.5. Listed on profile line for visibility only.

## Degraded modes

| Profile | Behavior |
|---------|----------|
| GitLab ✅, Datadog ❌ | Session 0b: GitLab squad only (via squad-map); skip P2b Datadog table |
| GitLab ❌, Datadog ✅ | Session 0b: Datadog team only (via squad-map); P2b if enabled |
| GitLab ❌, Datadog ❌ | Session 0b: CODEOWNERS fallback via squad-map; skip P2b Datadog table |
| Datadog ✅, KubeSense ❌ | P2b runs on Datadog evidence only; note missing KubeSense in `KNOWN_OMISSIONS.md` |
| Datadog ❌, KubeSense ✅ | P2b runs on KubeSense log evidence only; note missing Datadog in `KNOWN_OMISSIONS.md` |
| Both Datadog and KubeSense ❌ | Skip P2b entirely; record skip reason |
| Partial pagination | Note truncated results; continue with mapped subset |
