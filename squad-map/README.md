# squad-map

**Repo-to-squad ownership mapping** skill for Cursor. Maps local repos to org squads (GitLab group
hierarchy) and runtime squads (Datadog service team tags), producing **`SQUAD_MAP.md`** with confidence
scores and conflict flags.

Auto-invokes from natural language when you ask about squad ownership, who owns a repo, or team mapping.

## What it does

1. **Discovers repos** — explicit list, single repo, or auto-scan under a workspace root.
2. **Queries GitLab MCP** — `get_project` / `search_repositories` → namespace → squad from group path.
3. **Queries Datadog MCP** — `search_datadog_services` → service `team` tag.
4. **Reconciles** — HIGH when both agree; MEDIUM + conflict flag when they differ; CODEOWNERS fallback
   when both MCP unavailable (LOW confidence).
5. **Writes `SQUAD_MAP.md`** — main table, conflicts, unmapped repos.

**Read-only boundary:** never invoke GitLab writes, Datadog mutations, deploys, or application source
changes.

## When to use

| Use squad-map | Use instead |
|---------------|-------------|
| "Map squads for repos in `/Projects`" | Full domain map → **domain-comprehension** |
| "Who owns api-disbursement?" | MR review → **pr-review** |
| "Which team runs neo-disbursement-service?" | Post-incident RCA → **incident-rca** |
| Datadog MCP missing | **ddsetup** / **ddconfig**, then return |

## Invocation examples

```
Map squads for repos in /Users/me/Projects — org prefix mpokket, squad segment 2
Who owns api-disbursement?
Refresh squad map for the disbursement workspace
Squad mapping for these repos: api-disbursement, disbursement-service
```

## What you get

A `SQUAD_MAP.md` at workspace root — real shape, illustrative values:

> | Repo | GitLab squad | Datadog team | Confidence | Evidence |
> |------|--------------|--------------|------------|----------|
> | api-disbursement | disbursement | disbursement | HIGH | `get_project`; `search_datadog_services` |
> | legacy-ledger | payments | collections | MEDIUM ⚠️ | Squad mismatch — see Conflicts |
>
> **Conflicts:** `legacy-ledger` — GitLab squad `payments` ≠ Datadog team `collections`.

Full excerpt: [reference/gold-squad-map-excerpt.md](reference/gold-squad-map-excerpt.md).

- **`SQUAD_MAP.md`** at workspace root with MCP profile header
- Per-repo: GitLab namespace, GitLab squad, Datadog service, Datadog team, confidence, evidence
- Conflicts table when GitLab squad ≠ Datadog team
- Summary in chat: mapped count, confidence breakdown, conflict count

## Install

```bash
cd ai-skills
make install-squad-map
```

Restart Cursor. MCP setup: [SETUP.md](SETUP.md).

## Related skills

- **domain-comprehension** — Session 0b delegates to squad-map; consumes `SQUAD_MAP.md` in later phases
- **incident-rca** — time-window investigation; squad-map for ownership context
- **pr-review** — MR review with optional ownership context from `SQUAD_MAP.md`

Agent instructions: [SKILL.md](SKILL.md).
