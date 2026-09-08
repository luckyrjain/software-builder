# PostgreSQL migration — `{{SERVICE_NAME}}`

**Workspace path:** `{{SERVICE_DIR}}`  
**Tier focus:** P0 / P1 / P2 / dialect-only  
**Date:** {{DATE}}

## Scan gate

| Check | Status |
|-------|--------|
| `scripts/scan-mysql-dialect.sh {{SERVICE_DIR}}` | ☐ pass / ☐ fail |
| Open hits (if fail) | |

## Files rewritten

| File | Method / query | MySQL fragment | PostgreSQL fragment | Tier |
|------|----------------|----------------|---------------------|------|
| | | | | |

## Config changes

| Layer | Before | After |
|-------|--------|-------|
| JDBC / driver | | |
| Hibernate dialect | | |
| Pool / env | | |

## Application-layer audit

| Item | Reviewed | Notes |
|------|----------|-------|
| `ON UPDATE CURRENT_TIMESTAMP` / listeners | ☐ | |
| ENUM / boolean / UNSIGNED | ☐ | |
| Email / PAN / IFSC case | ☐ | |
| OAuth `expires` columns untouched | ☐ | |

## Verification

| Flow | Shadow userIds | PG result matches MySQL |
|------|----------------|-------------------------|
| SMS cooling | | ☐ |
| | | |

## Gate status

- [ ] Scan exit 0
- [ ] Manual audit checklist complete
- [ ] Shadow compare on staging
- [ ] Ready for MR → **pr-review**
