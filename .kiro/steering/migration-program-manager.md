---
inclusion: manual
---

For an org-wide rollup of mysql-to-postgres-sql migration status across many workspaces (stalled/blocked
services grouped by squad), read `migration-program-manager/SKILL.md`. A single workspace's own migration
status routes to `mysql-to-postgres-sql/SKILL.md` instead; a plain ownership lookup routes to
`squad-map/SKILL.md` instead.

Phase index: `migration-program-manager/reference/phase-index.md`. Reference loads:
`migration-program-manager/reference/lazy-load-index.md`.
Read-only — never invokes mysql-to-postgres-sql or squad-map live, only reads their existing output
files. Only writes its own report, rollup JSON, and state file.
