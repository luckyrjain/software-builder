# Smoke test — expected minimal output

Run after install or any edit to this skill. Use a small multi-repo workspace with GitLab MCP enabled.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

## Invocation

> Map squads for repos in `<workspace>` — org prefix `<org_prefix>`, squad segment `<n>`

Example: `Map squads for repos in ./services — org prefix acme-corp, squad segment 2`

## Expected first output

**Squad map MCP profile:** `GitLab ✅ (queried) | Datadog ✅/❌` — per
[mcp-capabilities.md](mcp-capabilities.md).

## A correct minimal output contains

1. **MCP profile line** — as above; written to `SQUAD_MAP.md` header.
2. **`SQUAD_MAP.md` created** at workspace root from [templates/SQUAD_MAP.md](../templates/SQUAD_MAP.md).
3. **At least one repo row** with GitLab namespace and squad (when GitLab ✅), or explicit UNKNOWN with
   evidence note.
4. **Confidence column** — HIGH, MEDIUM, LOW, or UNKNOWN per [reconciliation rules](squad-mapping.md#reconciliation).
5. **Conflicts table** — present (may be empty).
6. **Unmapped repos table** — present when repos could not be resolved.

## Degraded path (GitLab only)

When Datadog ❌:

- GitLab squad column filled; Datadog team UNKNOWN.
- Header notes Datadog ❌.

## Pass criteria

- No application source modified.
- `SQUAD_MAP.md` exists with MCP profile header and ≥1 data row.
- Read-only MCP — no writes, deploys, or mutations.

## Deep edge cases

See [pressure-tests.md](pressure-tests.md) — e.g. "One MCP ❌" (other lens only, capped confidence) and
"Both MCP ❌" (CODEOWNERS fallback, confidence LOW max).
