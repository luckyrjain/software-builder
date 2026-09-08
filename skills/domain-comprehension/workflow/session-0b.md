---
workflow_version: 1.13
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

**Goal:** Map each in-scope repo to a squad using GitLab hierarchy and Datadog service team tags.
Delegates mapping to **squad-map**; do not duplicate its algorithm.

## When to run

| Condition | Action |
|-----------|--------|
| GitLab or Datadog expected | Run via squad-map |
| Both unavailable | Run CODEOWNERS fallback when possible |
| Domain snapshot exists and census unchanged | Skip unless refresh requested |

## Steps

1. Require the Session 0 census and resolved `artifact_root`.
2. Invoke [squad-map/SKILL.md](../../squad-map/SKILL.md) with the in-scope repo list and ownership config; do not re-discover repos independently.
3. squad-map may maintain its shared `workspace_root/SQUAD_MAP.md`. After it completes, **copy the resulting snapshot to `{artifact_root}/SQUAD_MAP.md`** so domain-comprehension's canonical artifact set remains under `docs/` and the manifest validator resolves it consistently.
4. Verify the artifact-root copy contains the MCP profile and per-repo rows.
5. Pre-fill `{artifact_root}/UNKNOWNS.md` Likely owner when confidence ≥ MEDIUM. If mapping is unavailable, record the skip in `{artifact_root}/KNOWN_OMISSIONS.md` and use UNKNOWN squad values.

## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| MCP profile | `{artifact_root}/SQUAD_MAP.md` header | GitLab/Datadog status | Phase incomplete |
| Squad map | `{artifact_root}/SQUAD_MAP.md` | Repo, GitLab squad, Datadog team, Confidence, Evidence | Phase skipped with omission |

## Checkpoint

[phase-completion-gate.md](../reference/phase-completion-gate.md) · [phase-outputs.md § Session 0b](../reference/phase-outputs.md#session-0b-squad-enrichment)
