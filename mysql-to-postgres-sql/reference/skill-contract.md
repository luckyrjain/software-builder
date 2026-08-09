# Skill contract — non-negotiable

Load immediately after [SKILL.md](../SKILL.md). These rules override convenience shortcuts.

## Contract

1. **Scope** — Native SQL, JDBC/config, raw PHP/Node/Python SQL only. JPQL/Criteria/ORM-only paths = dialect + driver change only; do not rewrite JPQL strings.
2. **Scan gate** — Run `scripts/scan-mysql-dialect.sh` on the service path before declaring done. Exit **0** required for merge gate. When the service includes standalone `.sql` files, also run `scripts/ast_check_mysql_dialect.py` on them — a comment/string-aware secondary pass covering a different construct subset than the regex scan; see [ast-vs-regex-scan.md](ast-vs-regex-scan.md). Not a merge gate itself — findings feed the same manual-audit/rewrite step as scan hits.
3. **Priority** — P0 (compliance/cooling) before P1 before P2. One PR per service or per tier unless user requests otherwise.
4. **Manual audit** — Timestamps (`ON UPDATE`), ENUM/boolean, case rules, backticks, `sql_mode` GROUP BY are **not** in scan — checklist in SKILL.md §Per-service PR checklist.
5. **Lazy-load** — Only the file(s) named for the current trigger in [lazy-load-index.md](lazy-load-index.md) (some triggers pair 2 files, e.g. Scan hits / SQL rewrite); do not bulk-read all `reference/`.
6. **OAuth `expires`** — Never `@PreUpdate` / `before_update` on `oauth_authorization_codes.expires` or `oauth_refresh_tokens.expires` ([migration-edge-cases.md](migration-edge-cases.md) §B).
7. **Shadow verify** — Staging: shadow-compare 10–20 known `userId`s on critical flows before merge ([shadow-migration.md](shadow-migration.md)).
8. **Deliverable** — Emit [SERVICE_PG_MIGRATION.md](../templates/SERVICE_PG_MIGRATION.md) for multi-file migrations; chat summary suffices for scan-only audits.
9. **Complete means gated** — Never report "migration complete" while scan returns hits or manual-audit items are unchecked.

Routing: [skill-routing.md](../../docs/skill-framework/shared/skill-routing.md).
