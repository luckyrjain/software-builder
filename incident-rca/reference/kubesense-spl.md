# KubeSense SPL — MCP body fallback (incident-rca)

On **acme** (and any org with `logs_primary: kubesense`), **application logs are not stored in
Datadog**. KubeSense is the **only** source for log bodies, query strings, URIs, client channels, and
`sample_messages`. Datadog provides APM, metrics, and change stories only.

**Primary path:** install and read the official **`kubesense-mcp`** / **`kubesense-logs`** skills
([dependencies.md](../dependencies.md)). Use MCP `search-logs` with `body` in `fields` (15–30 min
windows, discovery-first).

**This document:** SPL REST CLI fallback when MCP `search-logs` with `body` fails after one retry
(`unable to fetch logs` or empty body rows when errors are confirmed by `analyze-logs`).

**Prerequisite:** `KUBESENSE_API_KEY` in the environment (same key as MCP Bearer token). Optional:
`KUBESENSE_BASE_URL` (default `https://kubesense.example.com`).

## When to run (Phase 1)

| Condition | Action |
|-----------|--------|
| **MCP `search-logs` with `body` succeeds** | Use MCP output — **do not** run SPL |
| **MCP body fetch fails after retry** | Run SPL CLI below |
| **acme / `logs_primary: kubesense`** | MCP first; SPL when MCP body unavailable |
| Expensive-query / wildcard ES incident | SPL on top caller `workload` — onset slice only if MCP body failed |
| Datadog already has `sample_messages` | SPL optional — **rare on acme** |

**Do not** record `kubesense_metadata_only` or a Gaps note about missing message body until **both**
MCP `body` attempt and SPL CLI (when `KUBESENSE_API_KEY` is set) have been tried.

## Workflow

1. **Read `kubesense-logs` skill** — discovery-first MCP workflow.
2. **Map service → workload** — acme uses `workload = '<service>'` (not `service` filter).
3. **MCP `search-logs`** — include `body` in `fields`; 15–30 min window; retry once if fetch fails.
4. **SPL fallback only if step 3 fails** — list clusters when `--cluster` unknown:

   ```bash
   python3 scripts/kubesense_logs.py <workload> --list-clusters
   ```

   From the ai-skills repo root, prefix `incident-rca/`.

5. **Fetch error logs with body** — use the **incident window** (`from_time` / `to_time` from inputs):

   ```bash
   python3 scripts/kubesense_logs.py <workload> \
     --cluster <cluster> \
     --namespace <namespace> \
     --from <from_time> \
     --to <to_time> \
     --limit 10
   ```

6. **Merge into evidence** — prefer `--evidence` for Phase 1 / Phase 4 JSON:

   ```bash
   python3 scripts/kubesense_logs.py <workload> \
     --cluster <cluster> \
     --namespace <namespace> \
     --from <from_time> \
     --to <to_time> \
     --limit 10 \
     --evidence
   ```

   Merge `error_signals[]` and `query_references[]` into the evidence bundle. Deduplicate
   `sample_messages` across Datadog and KubeSense (normalize whitespace, lowercase).

7. **Profile line** — after successful MCP body: `kubesense-mcp ✅ (queried)`. After SPL fallback:
   `kubesense-spl ✅`.

## Evidence mapping

| CLI output | Evidence field |
|------------|----------------|
| MCP `search-logs` + `body` | `source: "kubesense-mcp"`, `signal_type: "log_error"` |
| `--evidence` → `error_signals[0]` | `source: "kubesense-spl"`, `signal_type: "log_error"` |
| `sample_messages` | Top 5 unique messages (secrets redacted by CLI) |
| `detected_at` | Timestamp of newest log row |
| `query_references[]` | MCP tool invocation or full CLI command for audit |

Keep MCP `analyze-logs` counts in `evidence_links[]` or `magnitude` when both count and text are
needed.

## Query-string hunt (expensive-query / wildcard incidents)

When [query-investigation.md](query-investigation.md) §Phase 1 step 4 fires (wildcard auto-flag or
long `name=` in onset slice), hunt query text on the top caller `workload`:

1. **MCP first** — `filters: "body LIKE '%<keyword>%'"` with `body` in `fields` (onset slice).
2. **SPL fallback** if MCP body fails:

```bash
python3 incident-rca/scripts/kubesense_logs.py <caller-workload> \
  --cluster <cluster> --namespace <namespace> \
  --from <onset_from> --to <onset_to> \
  --limit 20 --evidence
```

Scan returned `body` for URI, query params, client channel, or `name=` patterns.

If SPL returns rows but no URI match, widen `--level` to `WARN` once — some services log slow queries at WARN.

## Failure modes

| Symptom | Action |
|---------|--------|
| MCP body works | Use MCP — skip SPL |
| MCP `unable to fetch logs` | Narrow window; retry once; then SPL |
| `KUBESENSE_API_KEY` unset | `kubesense-spl ❌` on profile; Gaps note |
| SPL returns 0 rows | `kubesense_metadata_only` in `evidence_links[]` only after MCP + SPL both tried |
| MCP counts + SPL text | **Do not** set `kubesense_schema_profile: "acme"` alone as blocker |

## Makefile shortcut

From repo root:

```bash
make kubesense-errors WORKLOAD=<workload> CLUSTER=<cluster> \
  NAMESPACE=<namespace> FROM=<from> TO=<to> LIMIT=10 EVIDENCE=1
```

See also [query-playbook.md](query-playbook.md) §KubeSense and
[KubeSense Logs API](https://docs.kubesense.ai/docs/18-api-access).
