# Domain Comprehension — Close 3 Remaining Coverage Gaps

**Date:** 2026-07-31
**Skill:** `domain-comprehension`

---

## Problem statement

A deep phase-by-phase audit against the org's `Extract Service Knowledge Base` prompt (after `ADD_REPO`,
`api_tooling`, and Time & Effort closed the three previously-identified gaps) found three remaining real
gaps — everything else confirmed COVERED or deliberately out of scope:

1. **KubeSense has zero presence in the skill.** Datadog is fully covered (P2b), KubeSense is not
   mentioned anywhere (`grep -rl "KubeSense\|kubesense"` across the skill returns nothing). The prompt's
   Phase 6 wants both.
2. **No investigation recipe for feature toggles or non-entity-specific Redis/Elasticsearch usage.**
   `workflow/phase-4.md`'s "Quality & ops section" is a one-line generic bullet with zero grep guidance —
   unlike every other phase that captures something specific (P0.25, the new P1 Auth & Gateway).
3. **No structured entity → repository-method → @Query inventory.** P1 deep-dives cover this in prose
   only; there's no queryable table equivalent to the prompt's `REPOSITORY_QUERIES.md`.

---

## Scope

**In:** three additive changes, one per gap, following the exact "investigation recipe + required-output
row" pattern already used successfully twice this session (P0.25's contract recipes, the new P1 Auth &
Gateway subsection). No changes to the three already-shipped features (`ADD_REPO`, `api_tooling`, Time &
Effort).

**Out:** anything already covered. Specifically — **re-scoping gap 2 during spec-writing**: re-reading
`templates/DATA_OWNERSHIP.md` / `reference/data-ownership.md` found it *already* has `Caches` (Redis
keys/TTL) and `Search indexes` (ES/OpenSearch writers) columns — but scoped to **entity-specific**
caching/indexing only. Gap 2 is narrower than originally flagged: feature toggles, plus **non-entity**
Redis usage (session store, distributed locks, rate limiters) and **non-entity** Elasticsearch usage
(logging indices, non-domain search) that the entity-centric `DATA_OWNERSHIP.md` table structurally can't
capture. Don't duplicate what's already covered.

---

## Task A — KubeSense (P2b, alongside Datadog)

### `reference/mcp-capabilities.md`

Add a new section, sibling to the existing `## Datadog (\`plugin-datadog-datadog\`) — P2b only` section:

```markdown
## KubeSense — P2b only

| Capability | Tool | Phase | Use |
|------------|------|-------|-----|
| Log search | `search-logs` | P2b | Error message patterns, last 24h default |
| Log analysis | `analyze-logs` | P2b | Workload/namespace-scoped error pattern summary |

Quote exact error message strings — do not paraphrase. Record: workload, namespace, log filter SQL.

**Setup:** If P2b tools missing → treat as ❌; skip KubeSense evidence, note in `KNOWN_OMISSIONS.md`.
```

Update the profile line to include KubeSense:

```markdown
> **Comprehension MCP profile:** GitLab ✅ (queried) | Datadog ✅ (queried) | KubeSense ✅ (queried) | understand-anything ✅
```

Update the "Degraded modes" table — add a KubeSense column/row set mirroring the existing Datadog ✅/❌
rows (KubeSense failure doesn't block P2b entirely, same as Datadog — P2b runs with whichever runtime
evidence sources are available, notes what's missing).

### `workflow/phase-2b.md`

Add a new required-output row after the existing "Runtime validation table" row:

```markdown
| KubeSense log evidence | `{map_file}` § Runtime validation | Exact quoted error strings, workload, namespace, filter SQL | Phase incomplete if KubeSense ✅ |
```

Mirrors the existing Datadog rows' gating pattern exactly (`Phase incomplete if Datadog ✅` → same
convention, keyed on KubeSense's own availability).

---

## Task B — Feature toggles + non-entity Redis/Elasticsearch (P4)

### `workflow/phase-4.md`

Add a new "Investigation recipes" section (this file currently has none, unlike `phase-0-25.md`/`phase-1.md`)
before "## Checkpoint":

```markdown
## Investigation recipes

- **Feature toggles:** `rg -l 'FeatureFlag|feature\.toggle|toggle\.enabled|@ConditionalOnProperty' --glob '!test*'`
- **Non-entity Redis usage** (session store, locks, rate limiters — NOT entity caching, that's
  `DATA_OWNERSHIP.md` § Caches): `rg -l 'RedisTemplate|@RedisHash|redisson|rate.?limit' --glob '!test*'`
  — exclude matches already recorded as entity caches in `DATA_OWNERSHIP.md`.
- **Non-entity Elasticsearch usage** (logging indices, non-domain search — NOT entity search-indexing,
  that's `DATA_OWNERSHIP.md` § Search indexes): `rg -l 'ElasticsearchTemplate|@Document\(indexName' --glob '!test*'`
  — same exclusion rule.

Record findings in `{map_file}` § Quality & Ops. `UNKNOWN` with reason when a toggle/Redis/ES dependency
is referenced in config but no evidence of its runtime effect is found in code.
```

Extend the existing "Quality & ops section" required-output row:

```markdown
| Quality & ops section | `{map_file}` § Quality & Ops | Tests, observability, correlation IDs, debt, feature toggles, non-entity Redis/ES usage | Phase incomplete |
```

---

## Task C — Entity → repository-method → @Query inventory (P1)

### `reference/data-ownership.md`

Extend the per-entity table's columns — find:

```markdown
| Entity | Authoritative source (repo + table/API) | Schema evidence | Replicas | Caches | Search indexes | Consumers | Confidence |
```

Replace with:

```markdown
| Entity | Authoritative source (repo + table/API) | Repository methods (@Query) | Schema evidence | Replicas | Caches | Search indexes | Consumers | Confidence |
```

Add a column rule:

```markdown
| **Repository methods** | Repository interface method signatures touching this entity; full `@Query` JPQL/native SQL text when present, else method-name-derived-query note |
```

### `templates/DATA_OWNERSHIP.md`

Mirror the same column addition in the empty template table header.

### `workflow/phase-1.md`

The existing required-output row enumerates columns and is now stale — find:

```markdown
| Data ownership (initial) | `DATA_OWNERSHIP.md` | Per entity: authoritative source, replicas, caches | Phase incomplete |
```

Replace with:

```markdown
| Data ownership (initial) | `DATA_OWNERSHIP.md` | Per entity: authoritative source, repository methods, replicas, caches | Phase incomplete |
```

---

## Open items for implementation plan

- None — all three tasks are markdown-only, no code, no new tests (same shape as Time & Effort).
