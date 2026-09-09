# Org migration coverage vs ARCH wiki

Generic coverage map for MySQL→PostgreSQL migrations. **Org-specific wiki URLs and trackers** live in
[domain-packs/](domain-packs/README.md).

This skill spans **native SQL + connection config** (scan gate) and **application-layer gaps** documented in sibling reference files.

**No org wiki?** The `Wiki §` column below maps to an example org's ARCH Confluence guide — if your org has no
equivalent migration wiki, treat that column as `N/A` and use the `Skill reference` / `Scan gate`
columns directly; they're the org-agnostic part and don't depend on a wiki existing at all.

## Coverage map

| Wiki § | Topic | Skill reference | Scan gate |
|--------|-------|-----------------|-----------|
| §1 | `ON UPDATE CURRENT_TIMESTAMP` | [timestamp-handling.md](timestamp-handling.md) | No — JPA/listener audit |
| §2 | Custom timestamp column names (14 tables) | [timestamp-handling.md](timestamp-handling.md) | No |
| §3 | ENUM → PG | [data-type-mapping.md](data-type-mapping.md) | No — entity mapping |
| §4 | SQL syntax differences | [function-translations.md](function-translations.md) | Yes — `scan-mysql-dialect.sh` |
| §5 | Data type mapping | [data-type-mapping.md](data-type-mapping.md) | Partial — semantic review |
| §6 | Driver & connection config | [workflow/migrate-service.md](../workflow/migrate-service.md), [spring-datasource-example.yaml](spring-datasource-example.yaml), [python-migration.md](python-migration.md), [nodejs-migration.md](nodejs-migration.md) | `rg jdbc:mysql` / `rg mysql2` / `rg pymysql` |
| §7 | Case sensitivity | [case-sensitivity.md](case-sensitivity.md) | No — team convention |
| §8 | Affected repos | Fleet [MIGRATION_STATUS.yaml](../templates/MIGRATION_STATUS.yaml) or org tracker (domain pack) | Per-repo status |
| §9 | Backticks, `application_name`, schema param | migrate workflow + §6 | Partial — backticks in scan |

## Domain-specific checklists

Load [domain-packs/README.md](domain-packs/README.md) for the full pack index.

## Per-service PR gate (org-wide scrub)

1. `scan-mysql-dialect.sh` clean on service path
2. Timestamp listeners / auditing for tables with `ON UPDATE CURRENT_TIMESTAMP` (see timestamp-handling)
3. JDBC / Python / Node connection includes `currentSchema` or `search_path`; `application_name` set
4. ENUM and boolean columns verified against [data-type-mapping.md](data-type-mapping.md)
5. Case-sensitive fields (email, PAN, IFSC) convention documented per [case-sensitivity.md](case-sensitivity.md)

Fleet rollup: maintain `MIGRATION_STATUS.yaml` at workspace root from [templates/MIGRATION_STATUS.yaml](../templates/MIGRATION_STATUS.yaml).
