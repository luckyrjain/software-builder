# Domain packs

Optional org- and domain-specific checklists for MySQL→PG migrations. The core skill is **org-agnostic**;
load a pack when you need file-level P0/P1 paths, service inventories, or org wiki links.

## When to load

| Trigger | Pack |
|---------|------|
| User names a workspace/domain (e.g. collection, disbursement) | Matching pack below |
| `MIGRATION_STATUS.yaml` has `domain_pack:` set | That pack |
| domain-comprehension produced `MYSQL_TO_PG_SQL_REWRITES.md` | Pack for that domain, if listed |

## Available packs

| Pack | File | Use when |
|------|------|----------|
| collection | [collection.md](collection.md) | Migrating a service in the `collection` workspace (SMS cooling, CLMS, EMS) |
| *(blank starting point)* | [TEMPLATE.md](TEMPLATE.md) | A different workspace/org with no pack yet |

## Fleet tracking

Copy [templates/MIGRATION_STATUS.yaml](../../templates/MIGRATION_STATUS.yaml) to the workspace root.
Update per-service rows as scan gate, shadow compare, and config cutover complete.

## Authoring a new pack

1. Copy [TEMPLATE.md](TEMPLATE.md) (blank P0/P1/P2 skeleton).
2. Add a row to the table above.
3. Add an invocation example to [examples.md](../../examples.md).
4. Link refresh steps from [collection-checklist-refresh.md](../collection-checklist-refresh.md) (paths are generic).

Packs are **hints** — always run `scan-mysql-dialect.sh` on the actual service path.
