# mysql-to-postgres-sql — Setup

## Ambient discovery is intended

This skill deliberately does **not** set `disable-model-invocation` in its frontmatter, so the agent
can auto-apply it when you ask about a MySQL scrub, `jdbc:postgresql` migration, or native-query
dialect audit in natural language — as well as an explicit invocation. Leave it unset unless you want
invocation to require an explicit ask.

## Install

```bash
cd ai-skills
make install-mysql-to-postgres-sql
```

Restart Cursor so the skill reloads.

### Claude Code

`make install-mysql-to-postgres-sql` above already installs this skill for Claude Code too (default
installs to both editors). For Claude Code **only**:

```bash
cd ai-skills
make install-claude-mysql-to-postgres-sql
```

No restart needed — a new Claude Code session picks it up. This skill has no required MCP servers;
see [claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md) if you wire the
optional post-cutover Datadog check.

### Kiro / in-repo discovery

Working directly in this repo (not via an installed copy)? `.cursor/rules/mysql-to-postgres-sql.mdc`
and `.kiro/steering/mysql-to-postgres-sql.md` point Cursor/Kiro at
`mysql-to-postgres-sql/SKILL.md` without an install step.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Target codebase | Java Spring (`@Query(nativeQuery=true)`), legacy PHP, or raw SQL |
| ripgrep (`rg`) | Required for `scripts/scan-mysql-dialect.sh` gate |
| PG staging | Integration tests + shadow compare vs MySQL sample data |

No MCP required — code scan + rewrite only. Optional **Datadog MCP** for post-cutover `postgresql.query` span verification (see [shadow-migration.md](reference/shadow-migration.md)).

## Framework links

- [skill-framework README](../docs/skill-framework/README.md)
- [cross-skill-escalation](../docs/skill-framework/shared/cross-skill-escalation.md)

## Smoke test

After install, run the steps in [reference/smoke-test.md](reference/smoke-test.md) against the scan
fixtures under `tests/fixtures/mysql-dialect/` (or any service path with MySQL dialect).

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Scan exits 0 (clean) but hits expected | Missing `rg` is **not** the explanation — the script exits **1** with `ERROR: ripgrep (rg) not found` when `rg` is absent (see `scripts/scan-mysql-dialect.sh`), it never silently warns-and-skips to a 0 exit. A clean 0 exit with hits expected means either the scan genuinely found nothing or the glob/pattern excluded the file — check `PATTERN` and target path before assuming coverage. |
| False positive on `DATE_FORMAT` | Script uses `DATE_FORMAT\(` — Java `DateTimeFormatter DATE_FORMAT` constants are ignored |
| Scan flags all `.js`/`.ts` files | Backticks removed from scan — use manual SQL string audit per [migration-edge-cases.md](reference/migration-edge-cases.md) |
| OAuth tokens break after cutover | Do not `@PreUpdate` `expires` columns — see [timestamp-handling.md](reference/timestamp-handling.md) |
| JPQL still fails after dialect change | JPQL is usually portable; check native queries and `ONLY_FULL_GROUP_BY` — [migration-edge-cases.md](reference/migration-edge-cases.md) |
