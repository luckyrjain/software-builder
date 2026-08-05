# Domain Comprehension — Final 3 Residual Gaps

**Date:** 2026-07-31
**Skill:** `domain-comprehension`

---

## Problem statement

A final re-verification audit — run after the 3-gap coverage fix (KubeSense, feature-toggle/Redis/ES,
repository-methods/@Query) shipped and passed its own final review — confirmed all prior fixes landed
correctly, then did one more fresh phase-by-phase pass against the extraction prompt and found 3 more real
gaps, none caught by either of the two prior audits:

1. **Error code enum + message documentation** — zero mentions anywhere in the skill
   (`grep -rn "ErrorCode\|error.*enum"` returns nothing).
2. **Datasource env var names** — zero mentions anywhere (`grep -rn "datasource\|DATASOURCE"` returns
   nothing), despite P0 already having a generic Config surface table that *could* capture this.
3. **Entity constraints/relationships** (FK, `@Column`, `@OneToMany`) — only implicit via the generic
   "Schema evidence" column in `DATA_OWNERSHIP.md`, which has no column-rule row at all (checked directly:
   the column exists in the table header, but `reference/data-ownership.md`'s "Column rules" table has no
   corresponding entry — every other column does).

---

## Scope

**In:** three small additive edits — one genuinely new required-output table, two extensions of guidance
that already has the right structural home. Same "investigation recipe + required-output row" pattern used
four times already this session.

**Out:** anything already covered.

---

## Decision: gaps 2 and 3 reuse existing structures, gap 1 needs one new table

Checked before designing (avoids inventing new tables/files where one already exists):

- **Gap 2 (datasource env vars):** `workflow/phase-0.md` already has a "Config surface table (required)"
  with columns `Key / Env var | Repo | Purpose | Prod-only? | Evidence` — generic, would already capture
  datasource vars if an agent thought to grep for them. The gap is prompt-specificity, not structure: no
  explicit instruction says "look for datasource vars." Fix: one grep hint added to P0's existing
  "External dependencies" guidance, no new table.
- **Gap 3 (entity constraints/relationships):** `reference/data-ownership.md`'s per-entity table already
  has a "Schema evidence" column — it's just never had a column-rule row telling the agent what evidence
  to look for (every other column in that table does). Fix: one new row in the existing "Column rules"
  table, no new column, no new file.
- **Gap 1 (error codes):** genuinely nothing exists — not a column, not a table, not a recipe, in any
  phase. `workflow/phase-0-25.md` (Contracts) is the natural home — it already handles HTTP/gRPC/Events/
  shared-db/shared-packages recipes writing to `{map_file}` § Contracts; error codes are a contract-surface
  concern in the same sense (they're part of the response contract), so this reuses that section rather
  than creating a new deliverable file.

---

## Task A — Error code catalog (P0.25 § Contracts)

### `workflow/phase-0-25.md`

Bumps `workflow_version` (currently `1.2`) — see the Changelog section below for the exact target version,
which must match whatever new row the implementation plan adds to `reference/workflow-changelog.md` (per
that file's rule: workflow-file version headers match the changelog row that documents them, not an
independent per-file increment — this was itself a defect the previous round's final review had to fix
twice already; do not repeat it a third time).

Add a new investigation-recipe subsection after "### Idempotency / correlation keys" and before
"## Producer vs. consumer detection":

```markdown
### Error codes

```bash
rg -l 'enum.*Error|ErrorCode|@ExceptionHandler|ErrorResponse' --glob '!test*' --glob '!vendor' <repo>
```
```

Add a new required table after the existing "Contract inventory table (required)":

```markdown
## Error code catalog (required)

| Code | Message | HTTP status | Repo | Evidence |
|------|---------|-------------|------|----------|
```

Add a new required-output row:

```markdown
| Error code catalog | `{map_file}` § Contracts | Code, message, HTTP status, repo, evidence | Phase incomplete — UNKNOWN rows with reason allowed |
```

---

## Task B — Datasource env vars (P0, extend existing guidance)

### `workflow/phase-0.md`

Bumps `workflow_version` (currently `1.3`) to match the same changelog row as Task A — see Changelog
section below.

Extend the existing "External dependencies" bullet in the P0 narrative to name datasource vars
explicitly, and add a grep hint to the Config surface table's instruction line.

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

---

## Task C — Entity constraints/relationships (data-ownership.md, extend existing rule)

### `reference/data-ownership.md`

Add a new row to the existing "Column rules" table — find:

```markdown
| **Repository methods** | Repository interface method signatures touching this entity; full `@Query` JPQL/native SQL text when present, else method-name-derived-query note |
```

Replace with:

```markdown
| **Repository methods** | Repository interface method signatures touching this entity; full `@Query` JPQL/native SQL text when present, else method-name-derived-query note |
| **Schema evidence** | `@Column` constraints (nullable, unique, length), `@OneToMany`/`@ManyToOne`/`@JoinColumn` relationships, foreign keys from migration DDL — cite the entity class or migration file, not a guess from field naming |
```

---

## Changelog

`reference/workflow-changelog.md`'s last row is currently `1.8` (verified at spec-writing time —
implementation plan must re-verify this itself before assuming, same discipline as every prior round).
This feature's new row is `1.9`, listing: `phase-0-25.md, phase-0.md, data-ownership.md`. Both bumped
workflow files (`phase-0-25.md`, `phase-0.md`) get `workflow_version: 1.9` — matching the changelog row,
not an independent per-file increment.

---

## Open items for implementation plan

- None — all three tasks are markdown-only, no code, no new tests (same shape as the prior 4 rounds).
