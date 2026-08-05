# Domain Comprehension Final Coverage Gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close 3 residual coverage gaps found by a re-verification audit — error code catalog (P0.25), datasource env var grep hint (P0), entity constraints/relationships column rule (`data-ownership.md`).

**Architecture:** Pure documentation change — one genuinely new required-output table (error codes), two extensions of guidance that already has the right structural home (datasource vars reuse P0's existing Config surface table; entity constraints reuse `DATA_OWNERSHIP.md`'s existing Schema evidence column).

**Tech Stack:** Markdown only. No code, no new tests.

## Global Constraints

- Skill source of truth is `/Users/luckyjain/Projects/ai-skills/domain-comprehension/` inside this worktree (`/Users/luckyjain/Projects/ai-skills/.claude/worktrees/domain-comprehension-add-repo-mode/domain-comprehension/`) — use ABSOLUTE paths for every file operation. A task in an earlier round on this branch misread a file from the stale main-repo checkout instead of the worktree; do not repeat that.
- `workflow_version` bumps: `workflow/phase-0-25.md` `1.2` → `1.9`, `workflow/phase-0.md` `1.3` → `1.9`. **Both must land on `1.9` to match the changelog row that documents them** — NOT an independent per-file increment. This exact mistake (per-file increments colliding with other features' claimed versions) was made twice already on this branch and took two separate fix rounds to correct (`dfe6fa6`, then again `e8e4bb3`). Before setting these values, run `grep -n "^| 1\." domain-comprehension/reference/workflow-changelog.md | tail -1` yourself and confirm the last row really is `1.8` — if it isn't, use the actual next integer instead of `1.9` and say so in your report rather than guessing.
- `reference/data-ownership.md` gets no version bump — it's a `reference/` file, not a `workflow/*.md` phase file with its own `workflow_version` header (same as prior rounds' treatment of this file).
- Every markdown edit must keep `scripts/lint-dangling-md-links.sh` clean (run from repo root).

---

### Task 1: Error code catalog (P0.25 § Contracts)

**Files:**
- Modify: `domain-comprehension/workflow/phase-0-25.md`

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
workflow_version: 1.9
```

- [ ] **Step 2: Add the Error codes investigation recipe**

Find:
```markdown
### Idempotency / correlation keys

```bash
rg -l 'idempotency.key|requestId|X-Idempotency|x-request-id|correlationId' \
  --glob '!test*' <repo>
```

## Producer vs. consumer detection
```

Replace with:
```markdown
### Idempotency / correlation keys

```bash
rg -l 'idempotency.key|requestId|X-Idempotency|x-request-id|correlationId' \
  --glob '!test*' <repo>
```

### Error codes

```bash
rg -l 'enum.*Error|ErrorCode|@ExceptionHandler|ErrorResponse' --glob '!test*' --glob '!vendor' <repo>
```

## Producer vs. consumer detection
```

- [ ] **Step 3: Add the Error code catalog table**

Find:
```markdown
## Contract inventory table (required)

| Contract | Type | Producer repo | Consumer repo(s) | Schema location | Evidence |
|----------|------|--------------|------------------|-----------------|----------|

## Sub-agents
```

Replace with:
```markdown
## Contract inventory table (required)

| Contract | Type | Producer repo | Consumer repo(s) | Schema location | Evidence |
|----------|------|--------------|------------------|-----------------|----------|

## Error code catalog (required)

| Code | Message | HTTP status | Repo | Evidence |
|------|---------|-------------|------|----------|

## Sub-agents
```

- [ ] **Step 4: Add the required-output row**

Find:
```markdown
| Event catalog | `EVENT_CATALOG.md` | topic, schema, producer, consumers, implementation, exercise | Phase incomplete — UNKNOWN rows with reason allowed |

## Checkpoint
```

Replace with:
```markdown
| Event catalog | `EVENT_CATALOG.md` | topic, schema, producer, consumers, implementation, exercise | Phase incomplete — UNKNOWN rows with reason allowed |
| Error code catalog | `{map_file}` § Contracts | Code, message, HTTP status, repo, evidence | Phase incomplete — UNKNOWN rows with reason allowed |

## Checkpoint
```

- [ ] **Step 5: Verify**

```bash
grep -n "Error codes\|Error code catalog" domain-comprehension/workflow/phase-0-25.md
```
Expected: at least 3 matches (recipe heading, table heading, required-output row).

- [ ] **Step 6: Link-check**

```bash
bash scripts/lint-dangling-md-links.sh domain-comprehension/workflow/phase-0-25.md
```
Expected: no output, exit 0.

- [ ] **Step 7: Commit**

```bash
git add domain-comprehension/workflow/phase-0-25.md
git commit -m "feat(domain-comprehension): add error code catalog to P0.25 Contracts"
```

---

### Task 2: Datasource env vars (P0, extend existing guidance)

**Files:**
- Modify: `domain-comprehension/workflow/phase-0.md`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing consumed by other tasks in this plan (independent).

- [ ] **Step 1: Bump workflow_version**

Edit line 2 from:
```
workflow_version: 1.3
```
to:
```
workflow_version: 1.9
```

- [ ] **Step 2: Extend the External dependencies bullet**

Find:
```markdown
- **External dependencies:** DBs, caches, queues, third-party APIs
```

Replace with:
```markdown
- **External dependencies:** DBs, caches, queues, third-party APIs — grep for datasource-specific env
  vars explicitly: `rg -o 'spring\.datasource\.\w+|DATABASE_URL|DB_HOST|DB_NAME|jdbc:' application*.yml
  .env* 2>/dev/null` (names only, never values, per the Config surface table's existing rule)
```

- [ ] **Step 3: Verify**

```bash
grep -n "datasource" domain-comprehension/workflow/phase-0.md
```
Expected: at least 1 match.

- [ ] **Step 4: Link-check**

```bash
bash scripts/lint-dangling-md-links.sh domain-comprehension/workflow/phase-0.md
```
Expected: no output, exit 0.

- [ ] **Step 5: Commit**

```bash
git add domain-comprehension/workflow/phase-0.md
git commit -m "feat(domain-comprehension): add datasource env var grep hint to P0 config surface"
```

---

### Task 3: Entity constraints/relationships (data-ownership.md, extend existing rule)

**Files:**
- Modify: `domain-comprehension/reference/data-ownership.md`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing consumed by other tasks in this plan (independent).

- [ ] **Step 1: Add the Schema evidence column rule**

Find:
```markdown
| **Repository methods** | Repository interface method signatures touching this entity; full `@Query` JPQL/native SQL text when present, else method-name-derived-query note |
| **Replicas** | Read-only copies in other DBs/services |
```

Replace with:
```markdown
| **Repository methods** | Repository interface method signatures touching this entity; full `@Query` JPQL/native SQL text when present, else method-name-derived-query note |
| **Schema evidence** | `@Column` constraints (nullable, unique, length), `@OneToMany`/`@ManyToOne`/`@JoinColumn` relationships, foreign keys from migration DDL — cite the entity class or migration file, not a guess from field naming |
| **Replicas** | Read-only copies in other DBs/services |
```

- [ ] **Step 2: Verify**

```bash
grep -n "Schema evidence" domain-comprehension/reference/data-ownership.md
```
Expected: 2 matches (table header, new column rule row).

- [ ] **Step 3: Link-check**

```bash
bash scripts/lint-dangling-md-links.sh domain-comprehension/reference/data-ownership.md
```
Expected: no output, exit 0.

- [ ] **Step 4: Commit**

```bash
git add domain-comprehension/reference/data-ownership.md
git commit -m "feat(domain-comprehension): add Schema evidence column rule to data-ownership.md"
```

---

### Task 4: workflow-changelog.md row + full-suite smoke check

**Files:**
- Modify: `domain-comprehension/reference/workflow-changelog.md`

**Interfaces:**
- Consumes: Tasks 1, 2, 3 (must run after all three, to list their combined file set accurately).
- Produces: nothing (terminal task).

- [ ] **Step 1: Confirm the last changelog row's version**

```bash
grep -n "^| 1\." domain-comprehension/reference/workflow-changelog.md | tail -1
```
Expected: the last row is `1.8`. If it is not, use the actual next integer for the new row (and for Tasks
1/2's `workflow_version` values, if you're re-running those tasks) instead of `1.9` — note the discrepancy
in your report rather than silently adjusting.

- [ ] **Step 2: Add the changelog row**

Find the table's last row (`1.8`) and the `## Versioning rule` heading right after it — insert a new `1.9`
row between them:

```markdown
| 1.9 | 2026-07-31 | phase-0-25.md, phase-0.md, data-ownership.md | Error code catalog in P0.25 § Contracts; datasource env var grep hint in P0 Config surface; Schema evidence column rule (entity constraints/relationships) in data-ownership.md |
```

- [ ] **Step 3: Verify the changelog table stays well-formed**

```bash
grep -n "^| 1\." domain-comprehension/reference/workflow-changelog.md
```
Expected: one row per version, no broken pipe count (each row exactly 4 `|`-delimited columns).

- [ ] **Step 4: Link-check**

```bash
bash scripts/lint-dangling-md-links.sh domain-comprehension/reference/workflow-changelog.md
```
Expected: no output, exit 0.

- [ ] **Step 5: Confirm no version collisions**

```bash
grep -n "workflow_version" domain-comprehension/workflow/*.md
```
Expected: `phase-0.md` and `phase-0-25.md` both show `1.9`; no other workflow file shows `1.9`.

- [ ] **Step 6: Full-suite regression check**

```bash
cd domain-comprehension && python3 -m pytest tests/ -v
```
Expected: all 45 tests still pass (this whole plan adds zero code, zero new tests).

- [ ] **Step 7: Template manifest still valid**

```bash
python3 domain-comprehension/scripts/validate_manifest_yaml.py domain-comprehension/templates/manifest.yaml
```
Expected: `ok:`.

- [ ] **Step 8: Repo-wide link check on everything this plan touched**

```bash
bash scripts/lint-dangling-md-links.sh \
  domain-comprehension/workflow/phase-0-25.md \
  domain-comprehension/workflow/phase-0.md \
  domain-comprehension/reference/data-ownership.md \
  domain-comprehension/reference/workflow-changelog.md
```
Expected: no output, exit 0.

- [ ] **Step 9: Commit**

```bash
git add domain-comprehension/reference/workflow-changelog.md
git commit -m "docs(domain-comprehension): backfill workflow-changelog.md for error-codes/datasource/schema-evidence changes"
```
