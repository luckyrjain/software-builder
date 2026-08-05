# Lazy-load index

Load reference files on demand — do not read all up front.

**Always load with SKILL.md:** [skill-contract.md](skill-contract.md)

| Trigger | Read |
|---------|------|
| Scan hits / SQL rewrite | [calibration-snippets.md](calibration-snippets.md), [function-translations.md](function-translations.md) |
| JDBC / Spring config | [spring-datasource-example.yaml](spring-datasource-example.yaml), [workflow/migrate-service.md](../workflow/migrate-service.md) |
| Python service | [python-migration.md](python-migration.md) |
| Node service | [nodejs-migration.md](nodejs-migration.md) |
| Timestamps / ON UPDATE | [timestamp-handling.md](timestamp-handling.md) |
| ENUM / boolean types | [data-type-mapping.md](data-type-mapping.md) |
| Email / PAN case rules | [case-sensitivity.md](case-sensitivity.md) |
| ARCH wiki gap check | [org-migration-gaps.md](org-migration-gaps.md) |
| Domain P0/P1 file list | [domain-packs/README.md](domain-packs/README.md) |
| Old collection-domain-files.md link followed | [collection-domain-files.md](collection-domain-files.md) — redirect stub |
| Shadow / dual-run / rollback | [shadow-migration.md](shadow-migration.md) |
| Translation caveats, scan limits, OAuth | [migration-edge-cases.md](migration-edge-cases.md) |
| Refresh domain pack hit list | [collection-checklist-refresh.md](collection-checklist-refresh.md) |
| Per-service deliverable | [templates/SERVICE_PG_MIGRATION.md](../templates/SERVICE_PG_MIGRATION.md) |
| Fleet status rollup | [templates/MIGRATION_STATUS.yaml](../templates/MIGRATION_STATUS.yaml) |
| Calibration / invocation routing | [examples.md](../examples.md) (human calibration; not required live) |

Cross-skill routing: [cross-skill-escalation.md](../../docs/skill-framework/shared/cross-skill-escalation.md).
