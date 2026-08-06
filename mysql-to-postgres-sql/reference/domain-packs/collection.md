# Domain pack: collection

Workspace: `collection`. Most Hibernate access in this workspace is JPQL and only needs the dialect
change; the exceptions are the native `@Query(nativeQuery=true)` repositories below, which need actual
SQL rewrite.

Comprehension artifact mirror (when present): `collection/MYSQL_TO_PG_SQL_REWRITES.md`

**Repo paths not captured yet.** The `[repo]/[path]` cells below are placeholders — fill them in from
an actual `scripts/scan-mysql-dialect.sh` run over the workspace (see
[collection-checklist-refresh.md](../collection-checklist-refresh.md)) rather than guessing; don't let
an agent invent a path to close the gap.

## P0 — SMS cooling / compliance timestamp comparisons

### `TblSmsCaptureRecordRepository.java`
Path: `[repo]/[path]/TblSmsCaptureRecordRepository.java` — fill in from scan output.

| Method | MySQL fragment | PostgreSQL |
|--------|----------------|------------|
| `findCoolingForToday` | `TIMESTAMPDIFF(MINUTE, …) / DATE_ADD(…)` | `EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - …)) / 60` — see [function-translations.md](../function-translations.md) |

Timestamp column: `added_timestamp` on `tbl_sms_capture_*` tables — these are **not** `created_at` /
`updated_at`, so they need the custom-column pattern in
[timestamp-handling.md](../timestamp-handling.md#custom-named-columns-last-updated-only-arch-wiki-2),
not the standard-column one.

`LIKE '%%'` in this repository's cooling query is an intentional wildcard, not a typo — keep it as-is
on PG (see SKILL.md § Semantic traps).

Legacy mirrors (if any): none known — confirm during scan.

## P1 — Core reads (CLMS, EMS)

### `TblUserLoanRepository.java` (CLMS)
Path: `[repo]/[path]/TblUserLoanRepository.java` — fill in from scan output.

| MySQL | PostgreSQL |
|-------|------------|
| `is_canceled = 0` | `is_canceled = false` — verify the PG column is actually `boolean` and not an integer carried over from MySQL before doing the literal swap; see [data-type-mapping.md](../data-type-mapping.md) |

### EMS defaulter flows
Path: not yet mapped to a specific repository class — fill in from scan output.

| MySQL | PostgreSQL |
|-------|------------|
| `CAST(… AS CHAR)` | `::text` — see [function-translations.md](../function-translations.md) |

EMS defaulter-flow lookups also match on email/mobile; apply the case-sensitivity convention below
rather than relying on MySQL's default case-insensitive collation.

## P2 — Legacy PHP

None known in this workspace as of this pack's authoring — omit or add a tier here once a scan turns
up a legacy PHP mirror.

## Case sensitivity

Fields to review for case-insensitive MySQL comparisons that will silently stop matching on PG (see
[case-sensitivity.md](../case-sensitivity.md) for the options table):

- Email / mobile lookups (CAAS, EMS defaulter flows)
- PAN, IFSC, bank codes

## Node.js

No active Node.js MySQL services in this workspace as of this pack's authoring (legacy UI packages are
front-end only) — [nodejs-migration.md](../nodejs-migration.md) applies org-wide to Node services in
other workspaces, not here.

---

## Authoring checklist

1. Fill in every `[repo]/[path]` placeholder above with real repo paths from an actual scan
   (`scripts/scan-mysql-dialect.sh` output over this workspace).
2. Re-run [collection-checklist-refresh.md](../collection-checklist-refresh.md) after PRs land so this
   table doesn't rot.
3. See [README.md § Authoring a new pack](README.md#authoring-a-new-pack) for the general process this
   pack followed.
