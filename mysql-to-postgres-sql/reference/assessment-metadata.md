# Assessment metadata footer (mysql-to-postgres-sql)

Machine-readable YAML emitted at per-service migrate closeout. Normative shared shape:
[review-metadata-schema.md](../../docs/skill-framework/shared/review-metadata-schema.md) §8.5.

**Risk tier vs confidence:** P0/P1/P2 are `migration_risk_tier` only — see
[confidence-bands.md](../../docs/skill-framework/shared/confidence-bands.md) §2.2.

## When to emit

Append a fenced ` ```yaml ` block with `SERVICE_PG_MIGRATION.md` deliverable or in chat after gate pass.
Fleet rollup: workspace `MIGRATION_STATUS.yaml` from [templates/MIGRATION_STATUS.yaml](../templates/MIGRATION_STATUS.yaml).

| Block | When |
|-------|------|
| **Core** (`service`, `service_path`, `migration_risk_tier`, `scan_gate`, `confidence`) | Every service migration closeout |
| **`precision`** | When scan + rewrite stats recorded |
| **`history`** | Re-run on same service when prior footer parseable |
| **`investigation_quality`** | When shadow compare completed |

Never set `confidence` from P0/P1 tier — use shadow-compare and scan completeness only.

Omit `history` on first migration attempt with no prior footer.
