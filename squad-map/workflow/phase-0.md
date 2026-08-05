---
workflow_version: 1.0
phase: phase-0
produces:
  - mcp_profile
consumes:
  - workspace_root
---

# Phase 0 — MCP capability check

**Goal:** Determine which ownership sources are available before mapping.

Full MCP reference: [mcp-capabilities.md](../reference/mcp-capabilities.md).

## Steps

1. Probe GitLab MCP — attempt `search_repositories` or `get_project` on one known repo (or list tool
   availability).
   - **Multi-instance:** if repos have origins on different GitLab hosts, probe each host's MCP
     instance separately. Record per-host status (e.g., `gitlab.example.com ✅`, `gitlab2.internal ❌`).
     Match each instance's `GITLAB_API_URL` against repo `origin` URLs.
2. Probe Datadog MCP — attempt `search_datadog_services` with a bounded query (`telemetry.intent`
   required).
3. Announce profile line:

   > **Squad map MCP profile:** GitLab ✅ (queried) | Datadog ✅ (queried)

   For multi-instance GitLab, list each host:
   > **Squad map MCP profile:** GitLab ✅ gitlab.example.com (queried), ❌ gitlab2.internal | Datadog ✅ (queried)

   Use exact suffixes per [mcp-capabilities.md](../reference/mcp-capabilities.md).

4. Write MCP profile to `SQUAD_MAP.md` header (create from
   [templates/SQUAD_MAP.md](../templates/SQUAD_MAP.md) if missing).

## Read-only boundary

No GitLab writes, no Datadog mutations, no deploys, no application source changes.

## Degraded routing

| Profile | Phase 1 path |
|---------|--------------|
| GitLab ✅ or Datadog ✅ | Phase 1 Steps 1–6 (MCP mapping) |
| Both ❌ | Phase 1 Step 7 — CODEOWNERS fallback only |

## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| MCP profile | `SQUAD_MAP.md` header | GitLab status, Datadog status | Phase incomplete |

## Checkpoint

Proceed to [phase-1.md](phase-1.md) when profile is announced and header written.
