# understand-anything integration

Resolve plugin skill dir via glob `**/skills/understand/SKILL.md` if install hash changed.

Required skills:

- `.../skills/understand/SKILL.md` — `/understand --full`
- `.../skills/understand-domain/SKILL.md` — `/understand-domain` (**no `--full`**)
- `.../skills/understand-explain/SKILL.md` — hotspot deep dives

| Skill | When | Output |
|-------|------|--------|
| `/understand --full` | P0.5 per repo (Tier 0/1/2; Tier 3 optional) | per-repo `knowledge-graph.json` → copy to workspace |
| `/understand-domain` | P0.5 after merge | `domain-graph.json` |
| `/understand-explain <path>` | P0.5 top-5 hotspots | summaries for Mechanical Insights |
| Grep on `knowledge-graph.json` | All graph queries | never load full JSON into context |

> **`/understand-domain` WITHOUT `--full`:** `--full` ignores merged graph and re-scans. Run plain so it
> derives from workspace `.understand-anything/knowledge-graph.json`.

## Batch policy (multi-repo scale)

Auto-proceed past interactive gates for unattended runs:

1. **`.understandignore` confirmation** — pre-create; do not wait
2. **`>100 files` gate** — proceed (scoping via ignore files)
3. **Language-detect prompt (Understand Phase 3.6)** — assume English

### Workspace ignore

Pre-create `workspace_root/.understand-anything/.understandignore`:

```
node_modules/
vendor/
target/
dist/
build/
.git/
*.min.js
**/.venv/
**/Pods/
```

Add domain-specific test sandboxes from `exclude_patterns`.

### Per-repo ignore (required)

Workspace ignore does **not** cascade into sub-repos. Before `/understand` in each repo, ensure
`.understand-anything/.understandignore` includes at minimum:

```
vendor/
**/aws-sdk-*/
**/generated/
**/*.min.js
node_modules/
**/Pods/
**/.venv/
target/
dist/
build/
```

### Per-repo scratch dirs

Running `/understand` inside a sibling repo writes `.understand-anything/` into that repo's tree.
Copy graph to workspace, then treat per-repo dir as throwaway — **do not commit**.

## Merge and domain graph

```bash
mkdir -p <workspace_root>/.understand-anything
cd <repo>
# /understand --full
cp .understand-anything/knowledge-graph.json \
   <workspace_root>/.understand-anything/<repo>-knowledge-graph.json
```

Append `manifest.json` entry:
`{repo, tier, branch, sha, analyzedAt, nodeCount, edgeCount, graphPath, status}`

Merge (re-resolve script path via glob if plugin hash changed):

```bash
python <plugin-root>/skills/understand/merge-subdomain-graphs.py <workspace_root>
```

Then at workspace root: `/understand-domain` (no `--full`).

## Graph query scripts

Save reusable scripts under `.understand-anything/scripts/` (e.g. `top-complexity.sh`, `fan-in-endpoints.sh`).
Record paths in Mechanical Insights.

**Limitation:** file-level complexity may be incomplete for per-function cyclomatic metrics — state honestly.

## Sub-agent guardrail

Before delegating `/understand` to `generalPurpose`, verify sub-agent can read plugin skill dir.
If not, run `/understand` sequentially in main session.

## Fallback (plugin unavailable)

`dependency-cruiser`/`madge` (JS/TS), `jdeps`/Maven (Java), `pydeps` (Python) + `metrics.csv`.
Record tool in Mechanical Insights.
