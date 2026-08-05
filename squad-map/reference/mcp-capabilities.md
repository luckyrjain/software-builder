# MCP capabilities — squad-map

**Re-verify each session** — tool availability changes across MCP upgrades.

Read-only boundary: no GitLab writes, no Datadog mutations, no deploys.

## Profile line

Announce at Phase 0 start:

> **Squad map MCP profile:** GitLab ✅ (queried) | Datadog ✅ (queried)

| Status | Meaning |
|--------|---------|
| `✅ (queried)` | Tool available and at least one query attempted |
| `✅` | Connected, not yet queried this session |
| `❌` | Unavailable or auth failed |

Forbidden suffixes: *(not needed)*, *(skipped)* — use `❌` or `✅` only.

**Multiple GitLab instances:** match `GITLAB_API_URL` to repo `origin` host.

## GitLab (`user-gitlab`)

| Capability | Tool | Use |
|------------|------|-----|
| Resolve project | `get_project` | `namespace.full_path`, `path_with_namespace` |
| Search by name | `search_repositories` | Match local folder → GitLab path |
| Bulk under group | `list_group_projects` | All projects under `group_prefixes` |
| List groups | `list_namespaces` | Discover `group_prefixes` candidates |

**Not used:** MR create, push, pipeline trigger, issue write.

## Datadog (`plugin-datadog-datadog`)

| Capability | Tool | Use |
|------------|------|-----|
| Service catalog + team | `search_datadog_services` | `team:` filter; per-service `team` |

**Required:** `telemetry.intent` on every Datadog call (English, no secrets).

Example queries:

- `name:disbursement-service*`
- `team:disbursement-platform`

**Setup:** If tools missing → **ddsetup** / **ddconfig**; continue with available source or CODEOWNERS fallback.

## Degraded modes

| Profile | Behavior |
|---------|----------|
| GitLab ✅, Datadog ❌ | GitLab squad only |
| GitLab ❌, Datadog ✅ | Datadog team only |
| Both ❌ | CODEOWNERS fallback (Phase 1 Step 7); confidence capped at LOW |
| Partial pagination | Note truncated results; continue with mapped subset |
