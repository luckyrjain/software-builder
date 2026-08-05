---
workflow_version: 1.12
phase: session-0b
produces:
  - mcp_profile
  - squad_map
consumes:
  - domain_config_yaml
  - domain_map_skeleton
  - repo_census
---

# Session 0b — Squad enrichment (optional)

**Goal:** Map each in-scope repo to a **squad** using GitLab group prefixes and Datadog service team tags.
Runs after Session 0 census; may parallelize with keyword sweep (step 6 in Session 0).

**Delegates to squad-map skill** — do not duplicate mapping procedure here.

## When to run

| Condition | Action |
|-----------|--------|
| GitLab ✅ or Datadog ✅ expected | Run Session 0b via squad-map |
| Both ❌ | Invoke squad-map anyway — CODEOWNERS fallback (confidence LOW) |
| `SQUAD_MAP.md` exists and census unchanged | Skip unless user requests refresh |

## Steps

1. **Preconditions:** Session 0 census complete; in-scope repo list available.

2. **Invoke squad-map skill** — read [squad-map/SKILL.md](../../squad-map/SKILL.md) and follow its workflow:
   - Pass `repos` = in-scope census from Session 0
   - Pass `ownership_config` from `domain-config.yaml` `ownership:` block
   - Set `workspace_root` from Session 0 inputs
   - Do not re-discover repos independently

   Normative mapping rules: [squad-map/reference/squad-mapping.md](../../squad-map/reference/squad-mapping.md)
   MCP tools: [squad-map/reference/mcp-capabilities.md](../../squad-map/reference/mcp-capabilities.md)
   Deliverable template: [squad-map/templates/SQUAD_MAP.md](../../squad-map/templates/SQUAD_MAP.md)

3. **Verify output:** `SQUAD_MAP.md` exists at workspace root with MCP profile header and per-repo rows.

4. **Domain-comprehension follow-up** — pre-fill `UNKNOWNS.md` **Likely owner** when confidence ≥ MEDIUM
   (use Datadog team, else GitLab squad). This step stays in domain-comprehension only.

5. **If squad-map skipped** (user declined or both MCP ❌ with no CODEOWNERS) — note in
   `KNOWN_OMISSIONS.md`; P0 inventory uses UNKNOWN for squad columns.

## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| MCP profile | `SQUAD_MAP.md` header | GitLab status, Datadog status | Phase incomplete |
| Squad map | `SQUAD_MAP.md` | Repo, GitLab squad, Datadog team, Confidence, Evidence (§ Conflicts is a separate table) | Phase skipped — note in KNOWN_OMISSIONS.md |

## Checkpoint

[phase-completion-gate.md](../reference/phase-completion-gate.md) · [phase-outputs.md § Session 0b](../reference/phase-outputs.md#session-0b-squad-enrichment)
