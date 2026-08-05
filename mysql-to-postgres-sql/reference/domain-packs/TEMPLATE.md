# Domain pack: [pack name]

Workspace: `[workspace/group name]`. One-line note on what's JPQL-only (dialect change only) vs. what
needs native-SQL rewrite in this workspace.

Comprehension artifact mirror (when present): `[workspace]/MYSQL_TO_PG_SQL_REWRITES.md`

**Extract once:** name any logic duplicated across repos here so a rewrite doesn't get done twice —
delete this line if nothing applies.

## P0 — [compliance/critical-path tier name]

### `[RepositoryClassName.java]`
Path: `[repo]/[path]/[RepositoryClassName].java`

| Method | MySQL fragment | PostgreSQL |
|--------|----------------|------------|
| `[methodName]` | `[MySQL fragment]` | `[PostgreSQL equivalent]` — link [function-translations.md](../function-translations.md) row if it's a direct swap |

Legacy mirrors (if any): `[legacy repo/path]`

## P1 — [core-read tier name]

### `[RepositoryClassName].java`
Path: `[repo]/[path]/[RepositoryClassName].java`

| MySQL | PostgreSQL |
|-------|------------|
| `[fragment]` | `[equivalent]` |

## P2 — [legacy/PHP tier name, if applicable]

Same table shape as P0/P1. Omit this section if the workspace has no legacy tier.

---

## Authoring checklist

1. Fill in every `[bracketed placeholder]` above with real repo paths and MySQL→PG fragment pairs from
   an actual scan (`scripts/scan-mysql-dialect.sh` output over the workspace).
2. Delete tiers that don't apply (e.g. no P2 if there's no legacy PHP).
3. Add a row for this pack to [README.md](README.md)'s "Available packs" table.
4. Add one invocation example to [examples.md](../../examples.md).
5. See [README.md § Authoring a new pack](README.md#authoring-a-new-pack) for the full steps —
   this file is the blank starting point that section refers to.
