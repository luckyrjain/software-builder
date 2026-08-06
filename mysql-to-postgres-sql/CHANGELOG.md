# Changelog — mysql-to-postgres-sql

All notable changes to the mysql-to-postgres-sql skill. Per-file `workflow_version` in `workflow/*.md`
frontmatter should match the version of the latest entry below that names that file.

This changelog was added retrospectively — versions 1.0–1.5 predate it and aren't individually
reconstructed here. The entry below documents the skill's current state at `skill_version: 1.6`.

## [1.6] — 2026-08-06

### Current state
- Single-workflow checklist skill (scan → classify → rewrite → config → verify → gate) for native MySQL
  SQL and datasource/driver config, covering Java Spring, legacy PHP, Python, and Node.js services — no
  `reference/phase-index.md` by design, since this isn't a multi-phase investigation skill
- `scripts/scan-mysql-dialect.sh` — scan gate; exit 1 on MySQL-only dialect hits, required clean before
  merge
- Priority tiers (P0 compliance/consent-window timestamps, P1 core read paths, P2 legacy PHP mirrors,
  portable) and full function-translation table:
  [reference/function-translations.md](reference/function-translations.md)
- Per-language config migration guides: [reference/python-migration.md](reference/python-migration.md),
  [reference/nodejs-migration.md](reference/nodejs-migration.md),
  [reference/spring-datasource-example.yaml](reference/spring-datasource-example.yaml)
- Semantic-trap coverage (`TINYINT(1)`/boolean projection, `LIKE '%%'` intentional wildcards, timestamp
  columns) — [reference/timestamp-handling.md](reference/timestamp-handling.md),
  [reference/data-type-mapping.md](reference/data-type-mapping.md),
  [reference/case-sensitivity.md](reference/case-sensitivity.md)
- Optional org-specific domain packs for P0/P1 file lists and wiki links:
  [reference/domain-packs/README.md](reference/domain-packs/README.md)
- Fleet-wide status tracking via [templates/MIGRATION_STATUS.yaml](templates/MIGRATION_STATUS.yaml),
  consumed by migration-program-manager's org-wide rollup
- Shadow/dual-run cutover verification: [reference/shadow-migration.md](reference/shadow-migration.md)
- Shared framework compliance (cross-skill-escalation, prompt-injection, skill-routing); no
  `confidence-bands.md`/`phase-glossary.md` — not a bounded-context investigation skill
- Cross-skill escalation to domain-comprehension (full domain map), pr-review (migration MR), and
  incident-rca (cutover regression); receives handoffs from domain-comprehension's
  `MYSQL_TO_PG_SQL_REWRITES.md` artifact and loop-task-implementer (task touches MySQL-dialect SQL)
