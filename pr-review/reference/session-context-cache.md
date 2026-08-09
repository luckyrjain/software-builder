# Session context cache (immutable repo metadata)

Repo-level files **rarely change mid-review** — especially across incremental re-reviews on the same MR
in one session. **Load once, extract decisions, reuse** until invalidated. This cuts latency and token
use on Phase 1 step 7 and avoids re-quoting large convention docs in later turns.

Load rules in **Phase 1 step 7** (`workflow/phase-1.md`). Apply on **every re-review** of the same
`project_id` in the same conversation unless invalidated.

## What to cache

| Cache key | Sources | Extract and retain (not full re-read) |
|-----------|---------|--------------------------------------|
| **codeowners** | `.gitlab/CODEOWNERS`, `CODEOWNERS`, `docs/CODEOWNERS` | Required-owner rules for paths under review; which owners apply to changed dirs |
| **mr_template** | `.gitlab/merge_request_templates/*.md` (applicable template) | Expected MR sections for template-compliance check |
| **architecture** | `ARCHITECTURE.md`, `docs/architecture/**` (index only unless §16 needs detail) | Layer names, package boundaries, documented forbidden edges |
| **conventions** | `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.cursorrules`, scoped `.cursor/rules/**` | Style/test/security conventions that apply to changed paths |
| **review_rules** | `review-rules.yaml` (repo paths) | Parsed domains, `persona:`, `fast_path:`, `always_review:`, `context:` |
| **capability_profile** | Root manifests + changed paths | Stack flags (k8s, terraform, react, llm, …) for Phase 2 detectors |
| **repo_skill_overrides** | `.cursor/skills/pr-review/*.md` in repo | Which override files exist; key constraints (architecture-lens layers, domain overrides) |
| **flaky_jobs** | `.flaky-tests`, `.flaky-jobs`, flaky list in `CLAUDE.md` | Job name list for CI classification |

**Do not cache** (always fresh each run):

- MR diff / review boundary (`get_merge_request_diffs`) — including per-run `review_boundary.one_hop_reads[]`
  (direct caller/callee files read under the one-hop policy in Phase 1 step 7 after boundary full-file reads;
  not reused across pushes)
- `diff_refs.head_sha`, pipelines, approvals, discussions, Jira ticket body
- Changed source files under review
- Prior `<!-- cursor-pr-review -->` summary content (re-fetch for baseline SHA)

## Session record

After the **first** Phase 1 on a `project_id`, build **`context_cache`**:

```
context_cache: {
  project_id,
  repo_root,
  loaded_at_head_sha,        # head when cache was built
  file_fingerprints: {       # path → last seen blob id or mtime if available; else head_sha at load
    "CODEOWNERS": "<sha or mtime>",
    "CLAUDE.md": "...",
    ...
  },
  extracted: {               # short structured notes for Phase 2 — not full file text
    codeowners_rules: "...",
    mr_template_sections: [...],
    architecture_layers: [...],
    conventions_summary: "...",
    review_rules_parsed: {...},
    capability_profile: {...},
    flaky_jobs: [...]
  }
}
```

**Retain `extracted` in working memory** for the session. Do **not** re-invoke `Read` on cached paths
on re-review unless invalidated.

## Invalidation (must reload)

Reload **only** invalidated entries — not the whole cache when one file changes.

| Trigger | Action |
|---------|--------|
| **Cached file in new diff** | That cache key invalid — re-read that file, update fingerprint + `extracted` |
| **Different `project_id` / repo root** | New cache — do not reuse |
| **User says** `refresh context`, `reload conventions`, `full review` | Invalidate all; reload step 7 |
| **Squash/force-push** invalidating baseline | Revalidate fingerprints if repo files might have changed |
| **First review** (no cache) | Build cache |

If **no** cached path appears in the incremental diff, announce once:

> ℹ️ **Context cache:** reusing CODEOWNERS, conventions, architecture notes — unchanged in this delta.

## Phase 1 step 7 algorithm

1. If `context_cache` exists for this `project_id` and user did not request refresh → skip reads for
   valid keys; use `extracted`.
2. Else (or partial invalidation) → read only **missing or stale** files; merge into cache.
3. Scope conventions to repo root + directories of **changed files** (unchanged from today — cache
   stores per-directory convention notes when monorepo).
4. Pass `extracted` to Phase 2 — CODEOWNERS cross-check, template compliance, §16 boundaries, persona/rules.

## Re-review (incremental)

On re-review (Phases 1 → 2 → …):

- **Always** refresh: diff boundary, commits since baseline, discussions, pipeline, Jira if ticket updated.
- **Reuse cache** for immutable keys when incremental diff does not touch those paths.
- Do **not** re-read `ARCHITECTURE.md` or `CLAUDE.md` on every push if the delta is only `src/foo.go`.

## Cross-session hint (optional)

When posting a summary, you may record cache freshness for debugging (omit if noisy):

```
- context_cache: CODEOWNERS, CLAUDE.md, review-rules.yaml @ head_sha abc123
```

Not required for correctness — same-chat session reuse is the primary win.

## Anti-patterns

- **Do not** bulk re-read all convention files on every re-review "to be safe."
- **Do not** keep full file contents in active reasoning after extract — store **extracted** summaries only (attention boundary).
- **Do not** skip invalidation when `CODEOWNERS` is in the diff — owner rules may have changed.
