# Domain pack: mpokket org wiki & trackers

Org-specific links for ARCH Confluence alignment and fleet tracking. Generic coverage map:
[org-migration-gaps.md](../org-migration-gaps.md).

## Source of truth

[Consolidated Page - MySQL to PostgreSQL Migration: Problems & Solutions](https://mpokket.atlassian.net/wiki/spaces/ARCH/pages/2320433200) (Java Spring Boot, Python, **Node.js**; PHP excluded on wiki).

## Related org docs (Confluence)

- [Comparability Check List](https://mpokket.atlassian.net/wiki/spaces/MPOKKET/pages/938115098)
- [MySQL to PostgreSQL Migration Prompts](https://mpokket.atlassian.net/wiki/spaces/ARCH/pages/2061861388) → [migration-prompts.md](../migration-prompts.md)
- [Repayment Database Migration Plan](https://mpokket.atlassian.net/wiki/spaces/MPOKKET/pages/2066448387)

## Tracking & analysis (external)

- [Architect Analysis (Google Drive)](https://drive.google.com/drive/folders/1Cxm-5dB6wQ4XhU72qOna_tfFvWb2qAPx)
- [Table names reference sheet](https://docs.google.com/spreadsheets/d/1Mw2iHK_XhxN_NH1hAv2z7Ou2r2waPkqKxgsyTra5KAM/edit?usp=sharing)
- [Detailed migration tracker](https://docs.google.com/spreadsheets/d/1TzlHh-tfc-usiF3qAEUIeGbND9-9yZ9L5pBRBXFY0ZA/edit?usp=sharing)

Wiki §8 lists Spring Boot, Python, and Node.js as impacted; use the tracker for per-repo status or
maintain [MIGRATION_STATUS.yaml](../../templates/MIGRATION_STATUS.yaml) at workspace root.

## Collection domain beyond wiki

| Topic | Reference |
|-------|-----------|
| SMS cooling P0 (`TIMESTAMPDIFF`, `DATE_ADD`) | [collection-mpokket.md](collection-mpokket.md) |
| Legacy PHP P2 | [collection-mpokket.md](collection-mpokket.md) |

## Per-service PR gate (mpokket org scrub)

1. `scan-mysql-dialect.sh` clean on service path
2. Timestamp listeners / auditing for tables with `ON UPDATE CURRENT_TIMESTAMP` (see timestamp-handling)
3. JDBC / Python / Node connection includes `currentSchema` or `search_path`; `application_name` set
4. ENUM and boolean columns verified against [data-type-mapping.md](../data-type-mapping.md)
5. Case-sensitive fields (email, PAN, IFSC) convention documented per [case-sensitivity.md](../case-sensitivity.md)
