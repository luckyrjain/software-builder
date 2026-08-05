# Domain Comprehension Coverage Gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the 3 remaining coverage gaps found by a deep audit against the org's extraction prompt — KubeSense (P2b), feature-toggle/non-entity Redis/ES investigation (P4), entity→repository-method/@Query inventory (P1's `DATA_OWNERSHIP.md`).

**Architecture:** Pure documentation change — three independent additive edits, each following the existing "investigation recipe + required-output row" pattern already used successfully twice this session.

**Tech Stack:** Markdown only. No code, no new tests.

## Global Constraints

- Skill source of truth is `/Users/luckyjain/Projects/ai-skills/domain-comprehension/` inside this worktree (`/Users/luckyjain/Projects/ai-skills/.claude/worktrees/domain-comprehension-add-repo-mode/domain-comprehension/`).
- No changes to the three already-shipped features (`ADD_REPO`, `api_tooling`, Time & Effort) — this plan only touches P1/P2b/P4 files those features didn't touch.
- Every markdown edit must keep `scripts/lint-dangling-md-links.sh` clean (run from repo root).
- `workflow_version` bumps: `workflow/phase-2b.md` `1.3` → `1.4`, `workflow/phase-4.md` `1.2` → `1.3`, `workflow/phase-1.md` `1.6` → `1.7` (task C touches its required-output row text).
- `reference/workflow-changelog.md` owes a new row for this bump set (its rule: "When bumping: update every file in the same commit, add a row to this table") — handled in Task D.

---

### Task 1: KubeSense (P2b, alongside Datadog)

**Files:**
- Modify: `domain-comprehension/reference/mcp-capabilities.md`
- Modify: `domain-comprehension/workflow/phase-2b.md`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing consumed by other tasks in this plan (independent).

- [ ] **Step 1: `reference/mcp-capabilities.md` — add the KubeSense section**

Find:
```markdown
For service catalog / team tags (Session 0b), use **squad-map** skill.

**Setup:** If P2b tools missing → **ddsetup** / **ddconfig**; skip P2b runtime validation.

## understand-anything
```

Replace with:
```markdown
For service catalog / team tags (Session 0b), use **squad-map** skill.

**Setup:** If P2b tools missing → **ddsetup** / **ddconfig**; skip P2b runtime validation.

## KubeSense — P2b only

| Capability | Tool | Phase | Use |
|------------|------|-------|-----|
| Log search | `search-logs` | P2b | Error message patterns, last 24h default |
| Log analysis | `analyze-logs` | P2b | Workload/namespace-scoped error pattern summary |

Quote exact error message strings — do not paraphrase. Record: workload, namespace, log filter SQL.

**Setup:** If P2b tools missing → treat as ❌; skip KubeSense evidence, note in `KNOWN_OMISSIONS.md`.

## understand-anything
```

- [ ] **Step 2: `reference/mcp-capabilities.md` — update the profile line**

Find:
```markdown
> **Comprehension MCP profile:** GitLab ✅ (queried) | Datadog ✅ (queried) | understand-anything ✅
```

Replace with:
```markdown
> **Comprehension MCP profile:** GitLab ✅ (queried) | Datadog ✅ (queried) | KubeSense ✅ (queried) | understand-anything ✅
```

- [ ] **Step 3: `reference/mcp-capabilities.md` — update the Degraded modes table**

Find:
```markdown
## Degraded modes

| Profile | Behavior |
|---------|----------|
| GitLab ✅, Datadog ❌ | Session 0b: GitLab squad only (via squad-map); skip P2b |
| GitLab ❌, Datadog ✅ | Session 0b: Datadog team only (via squad-map); P2b if enabled |
| Both ❌ | Session 0b: CODEOWNERS fallback via squad-map; skip P2b |
| Partial pagination | Note truncated results; continue with mapped subset |
```

Replace with:
```markdown
## Degraded modes

| Profile | Behavior |
|---------|----------|
| GitLab ✅, Datadog ❌ | Session 0b: GitLab squad only (via squad-map); skip P2b Datadog table |
| GitLab ❌, Datadog ✅ | Session 0b: Datadog team only (via squad-map); P2b if enabled |
| Both ❌ | Session 0b: CODEOWNERS fallback via squad-map; skip P2b Datadog table |
| Datadog ✅, KubeSense ❌ | P2b runs on Datadog evidence only; note missing KubeSense in `KNOWN_OMISSIONS.md` |
| Datadog ❌, KubeSense ✅ | P2b runs on KubeSense log evidence only; note missing Datadog in `KNOWN_OMISSIONS.md` |
| Both Datadog and KubeSense ❌ | Skip P2b entirely; record skip reason |
| Partial pagination | Note truncated results; continue with mapped subset |
```

- [ ] **Step 4: `workflow/phase-2b.md` — bump workflow_version**

Edit line 2 from:
```
workflow_version: 1.3
```
to:
```
workflow_version: 1.4
```

- [ ] **Step 5: `workflow/phase-2b.md` — add the KubeSense required-output row**

Find:
```markdown
| Runtime validation table | `{map_file}` § Runtime validation **or** `E2E_FLOW.md` § Runtime validation (with map stub+link) | From→To, Code (P2), Graph, Datadog, Verdict, Confidence, Evidence | Phase incomplete if Datadog ✅ |
| Runtime graph | `DEPENDENCY_GRAPH.md` § Runtime | Datadog-confirmed edges, Mermaid | Phase incomplete if Datadog ✅ |
```

Replace with:
```markdown
| Runtime validation table | `{map_file}` § Runtime validation **or** `E2E_FLOW.md` § Runtime validation (with map stub+link) | From→To, Code (P2), Graph, Datadog, Verdict, Confidence, Evidence | Phase incomplete if Datadog ✅ |
| KubeSense log evidence | `{map_file}` § Runtime validation | Exact quoted error strings, workload, namespace, filter SQL | Phase incomplete if KubeSense ✅ |
| Runtime graph | `DEPENDENCY_GRAPH.md` § Runtime | Datadog-confirmed edges, Mermaid | Phase incomplete if Datadog ✅ |
```

- [ ] **Step 6: Verify**

```bash
grep -n "KubeSense" domain-comprehension/reference/mcp-capabilities.md domain-comprehension/workflow/phase-2b.md
```
Expected: matches in both files (section heading, profile line, degraded-modes rows, required-output row — at least 5 total).

- [ ] **Step 7: Link-check**

```bash
bash scripts/lint-dangling-md-links.sh domain-comprehension/reference/mcp-capabilities.md domain-comprehension/workflow/phase-2b.md
```
Expected: no output, exit 0.

- [ ] **Step 8: Commit**

```bash
git add domain-comprehension/reference/mcp-capabilities.md domain-comprehension/workflow/phase-2b.md
git commit -m "feat(domain-comprehension): add KubeSense log evidence to P2b, alongside Datadog"
```

---

### Task 2: Feature toggles + non-entity Redis/Elasticsearch (P4)

**Files:**
- Modify: `domain-comprehension/workflow/phase-4.md`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing consumed by other tasks in this plan (independent).

- [ ] **Step 1: Bump workflow_version**

Edit line 2 from:
```
workflow_version: 1.2
```
to:
```
workflow_version: 1.3
```

- [ ] **Step 2: Extend the Quality & ops required-output row**

Find:
```markdown
| Quality & ops section | `{map_file}` § Quality & Ops | Tests, observability, correlation IDs, debt | Phase incomplete |
```

Replace with:
```markdown
| Quality & ops section | `{map_file}` § Quality & Ops | Tests, observability, correlation IDs, debt, feature toggles, non-entity Redis/ES usage | Phase incomplete |
```

- [ ] **Step 3: Add the Investigation recipes section**

Find:
```markdown
## Checkpoint

[phase-completion-gate.md](../reference/phase-completion-gate.md)
```

Replace with:
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

## Checkpoint

[phase-completion-gate.md](../reference/phase-completion-gate.md)
```

- [ ] **Step 4: Verify**

```bash
grep -n "Investigation recipes\|feature toggles\|Non-entity" domain-comprehension/workflow/phase-4.md
```
Expected: at least 4 matches.

- [ ] **Step 5: Link-check**

```bash
bash scripts/lint-dangling-md-links.sh domain-comprehension/workflow/phase-4.md
```
Expected: no output, exit 0.

- [ ] **Step 6: Commit**

```bash
git add domain-comprehension/workflow/phase-4.md
git commit -m "feat(domain-comprehension): add feature-toggle/non-entity Redis/ES investigation recipes to P4"
```

---

### Task 3: Entity → repository-method → @Query inventory (P1 / DATA_OWNERSHIP.md)

**Files:**
- Modify: `domain-comprehension/reference/data-ownership.md`
- Modify: `domain-comprehension/templates/DATA_OWNERSHIP.md`
- Modify: `domain-comprehension/workflow/phase-1.md`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing consumed by other tasks in this plan (independent).

- [ ] **Step 1: `reference/data-ownership.md` — extend the per-entity table header**

Find:
```markdown
## Per-entity table (required)

| Entity | Authoritative source (repo + table/API) | Schema evidence | Replicas | Caches | Search indexes | Consumers | Confidence |
|--------|----------------------------------------|-----------------|----------|--------|----------------|-----------|------------|
```

Replace with:
```markdown
## Per-entity table (required)

| Entity | Authoritative source (repo + table/API) | Repository methods (@Query) | Schema evidence | Replicas | Caches | Search indexes | Consumers | Confidence |
|--------|----------------------------------------|------------------------------|-----------------|----------|--------|----------------|-----------|------------|
```

- [ ] **Step 2: `reference/data-ownership.md` — add the column rule**

Find:
```markdown
### Column rules

| Column | Evidence priority |
|--------|-------------------|
| **Authoritative source** | Migration author repo > producer of create API > consumer assumption |
```

Replace with:
```markdown
### Column rules

| Column | Evidence priority |
|--------|-------------------|
| **Authoritative source** | Migration author repo > producer of create API > consumer assumption |
| **Repository methods** | Repository interface method signatures touching this entity; full `@Query` JPQL/native SQL text when present, else method-name-derived-query note |
```

- [ ] **Step 3: `reference/data-ownership.md` — update the example row**

Find:
```markdown
## Example row

```
Entity: Loan
Authoritative: loan-product-service / loans (migration V12)
Replicas: analytics-pipeline (read replica)
Caches: Redis loan:{id} (loan-product-service config)
Search: — 
Consumers: disbursement-service, collections-service, notifications
Confidence: HIGH
```
```

Replace with:
```markdown
## Example row

```
Entity: Loan
Authoritative: loan-product-service / loans (migration V12)
Repository methods: LoanRepository.findByStatus(status) — derived query; LoanRepository.findOverdue()
  — @Query("SELECT l FROM Loan l WHERE l.dueDate < :now AND l.status = 'ACTIVE'")
Replicas: analytics-pipeline (read replica)
Caches: Redis loan:{id} (loan-product-service config)
Search: — 
Consumers: disbursement-service, collections-service, notifications
Confidence: HIGH
```
```

- [ ] **Step 4: `templates/DATA_OWNERSHIP.md` — mirror the column addition**

Find:
```markdown
| Entity | Authoritative source | Schema evidence | Replicas | Caches | Search indexes | Consumers | Confidence |
|--------|---------------------|-----------------|----------|--------|----------------|-----------|------------|
```

Replace with:
```markdown
| Entity | Authoritative source | Repository methods (@Query) | Schema evidence | Replicas | Caches | Search indexes | Consumers | Confidence |
|--------|---------------------|------------------------------|-----------------|----------|--------|----------------|-----------|------------|
```

- [ ] **Step 5: `workflow/phase-1.md` — bump workflow_version**

Edit line 2 from:
```
workflow_version: 1.6
```
to:
```
workflow_version: 1.7
```

- [ ] **Step 6: `workflow/phase-1.md` — update the stale required-output row**

Find:
```markdown
| Data ownership (initial) | `DATA_OWNERSHIP.md` | Per entity: authoritative source, replicas, caches | Phase incomplete |
```

Replace with:
```markdown
| Data ownership (initial) | `DATA_OWNERSHIP.md` | Per entity: authoritative source, repository methods, replicas, caches | Phase incomplete |
```

- [ ] **Step 7: Verify**

```bash
grep -n "Repository methods" domain-comprehension/reference/data-ownership.md domain-comprehension/templates/DATA_OWNERSHIP.md domain-comprehension/workflow/phase-1.md
```
Expected: at least 4 matches (table header + column rule + example in data-ownership.md, table header in template, required-output row in phase-1.md).

- [ ] **Step 8: Link-check**

```bash
bash scripts/lint-dangling-md-links.sh domain-comprehension/reference/data-ownership.md domain-comprehension/templates/DATA_OWNERSHIP.md domain-comprehension/workflow/phase-1.md
```
Expected: no output, exit 0.

- [ ] **Step 9: Commit**

```bash
git add domain-comprehension/reference/data-ownership.md domain-comprehension/templates/DATA_OWNERSHIP.md domain-comprehension/workflow/phase-1.md
git commit -m "feat(domain-comprehension): add repository-method/@Query column to DATA_OWNERSHIP.md"
```

---

### Task 4: workflow-changelog.md row + full-suite smoke check

**Files:**
- Modify: `domain-comprehension/reference/workflow-changelog.md`

**Interfaces:**
- Consumes: Tasks A, B, C (must run after all three, to list their combined file set accurately).
- Produces: nothing (terminal task).

- [ ] **Step 1: Add the changelog row**

Find the table's last row (currently `1.7`) and the `## Versioning rule` heading right after it — insert a
new `1.8` row between them, listing the files Tasks A/B/C touched:

```markdown
| 1.8 | 2026-07-31 | mcp-capabilities.md, phase-2b.md, phase-4.md, data-ownership.md, DATA_OWNERSHIP.md, phase-1.md | KubeSense log evidence in P2b alongside Datadog; feature-toggle/non-entity Redis/ES investigation recipes in P4; repository-method/@Query column in DATA_OWNERSHIP.md |
```

(If the table's last row is not `1.7` when you reach this step — e.g. a concurrent change landed a
different version first — use the actual next integer instead of `1.8`, and note the discrepancy in your
report rather than guessing silently.)

- [ ] **Step 2: Verify the changelog table stays well-formed**

```bash
grep -n "^| 1\." domain-comprehension/reference/workflow-changelog.md
```
Expected: one row per version, no broken pipe count (each row has exactly 4 `|`-delimited columns).

- [ ] **Step 3: Link-check**

```bash
bash scripts/lint-dangling-md-links.sh domain-comprehension/reference/workflow-changelog.md
```
Expected: no output, exit 0.

- [ ] **Step 4: Full-suite regression check**

```bash
cd domain-comprehension && python3 -m pytest tests/ -v
```
Expected: all 45 tests still pass (this whole plan adds zero code, zero new tests).

- [ ] **Step 5: Template manifest still valid**

```bash
python3 domain-comprehension/scripts/validate_manifest_yaml.py domain-comprehension/templates/manifest.yaml
```
Expected: `ok:`.

- [ ] **Step 6: Repo-wide link check on everything this plan touched**

```bash
bash scripts/lint-dangling-md-links.sh \
  domain-comprehension/reference/mcp-capabilities.md \
  domain-comprehension/workflow/phase-2b.md \
  domain-comprehension/workflow/phase-4.md \
  domain-comprehension/reference/data-ownership.md \
  domain-comprehension/templates/DATA_OWNERSHIP.md \
  domain-comprehension/workflow/phase-1.md \
  domain-comprehension/reference/workflow-changelog.md
```
Expected: no output, exit 0.

- [ ] **Step 7: Commit**

```bash
git add domain-comprehension/reference/workflow-changelog.md
git commit -m "docs(domain-comprehension): backfill workflow-changelog.md for KubeSense/P4-recipes/DATA_OWNERSHIP changes"
```
