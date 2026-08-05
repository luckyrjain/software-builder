# Timestamp handling — `ON UPDATE CURRENT_TIMESTAMP`

PostgreSQL does **not** support MySQL `ON UPDATE CURRENT_TIMESTAMP`. The application must set timestamps on insert/update.

**Scale:** ~**200+** tables relied on MySQL `ON UPDATE` (org estimate). Most use standard `created_at` / `updated_at` (§1 below). The **custom-named column** table below covers non-standard **last-updated** names only — not every affected table.

Define table sets and column maps as **in-code constants** — do not load from files at runtime (ARCH wiki §9).

## Standard columns (`created_at` / `updated_at`)

### Java Spring Boot

**Option A — Spring Data JPA auditing (recommended for new code):**

```java
@EnableJpaAuditing
// entity fields:
@CreatedDate
private Instant createdAt;
@LastModifiedDate
private Instant updatedAt;
```

**Option B — `@EntityListeners` with table allowlist (ARCH wiki §1):**

```java
@Component
public class SpecTableTimestampListener {
    // Extend per service — example tables from ARCH wiki:
    private static final Set<String> SPEC_TABLES_CREATED_UPDATED_AT = Set.of(
        "acl_role_permission",
        "ameyo_dialer_details",
        "master_banks",
        "tbl_user_loans",
        "tbl_user_profile_basics"
    );

    @PrePersist
    public void prePersist(Object entity) {
        if (entity instanceof Auditable a && isSpecTable(getTableName(entity))) {
            Instant now = Instant.now();
            if (hasColumn(entity, "created_at")) a.setCreatedAt(now);
            if (hasColumn(entity, "updated_at")) a.setUpdatedAt(now);
        }
    }

    @PreUpdate
    public void preUpdate(Object entity) {
        if (entity instanceof Auditable a && isSpecTable(getTableName(entity))) {
            if (hasColumn(entity, "updated_at")) a.setUpdatedAt(Instant.now());
        }
    }
}
```

Replace `MySQL8Dialect` / `MySQLDialect` with `PostgreSQLDialect` on cutover.

### Python (SQLAlchemy) — table allowlist (ARCH wiki §1)

```python
from datetime import datetime, timezone

SPEC_TABLES_CREATED_UPDATED_AT = frozenset({
    "acl_role_permission",
    "master_banks",
    "tbl_user_loans",
})

@event.listens_for(Model, "before_insert")
def set_created_updated_at_insert(mapper, connection, target):
    table = target.__table__.name
    if table not in SPEC_TABLES_CREATED_UPDATED_AT:
        return
    now = datetime.now(timezone.utc)
    if hasattr(target, "created_at"):
        target.created_at = now
    if hasattr(target, "updated_at"):
        target.updated_at = now

@event.listens_for(Model, "before_update")
def set_updated_at_update(mapper, connection, target):
    table = target.__table__.name
    if table not in SPEC_TABLES_CREATED_UPDATED_AT:
        return
    if hasattr(target, "updated_at"):
        target.updated_at = datetime.now(timezone.utc)
```

**Django:** `pre_save` signal, `auto_now` / `auto_now_add`, or `save()` mixin — see [python-migration.md](python-migration.md).

## Node.js (Sequelize / TypeORM / Knex)

Set timestamps in ORM hooks or column decorators — see [nodejs-migration.md](nodejs-migration.md).

## Custom-named columns (last-updated only) — ARCH wiki §2

Columns that MySQL auto-updated on row change. **Exclude expiry deadlines** — see below.

| Table | Column(s) | Role |
|-------|-----------|------|
| master_banks | added_timestamp, update_timestamp | last-updated |
| master_configurations | update_timestamp | last-updated |
| master_product_credit_rating_benefits | update_timestamp | last-updated |
| tbl_admin_messages | added_timestamp | last-updated |
| tbl_collection_checklist_master | modified_date | last-updated |
| tbl_collection_disposition_master | modified_date | last-updated |
| tbl_hdfc_reconciliation | modified | last-updated |
| tbl_messageboard | last_updated_on | last-updated |
| tbl_rekyc_categories | last_updated_timestamp | last-updated |
| tbl_rekyc_sub_categories | last_updated_timestamp | last-updated |
| tbl_user_levels | update_timestamp | last-updated |

### Do not auto-set on `@PreUpdate` (ARCH list — different semantics)

| Table | Column | Why |
|-------|--------|-----|
| oauth_authorization_codes | expires | Token **expiry deadline** — only set at issue time |
| oauth_refresh_tokens | expires | Same — overwriting on update **breaks OAuth** |

ARCH wiki lists `expires` alongside update columns; treat as **application-managed expiry**, not `ON UPDATE` replacement. See [migration-edge-cases.md](migration-edge-cases.md#b-oauth-expires-columns-critical).

### Java

```java
private static final Map<String, List<String>> CUSTOM_TIMESTAMP_COLUMNS = Map.ofEntries(
    Map.entry("master_banks", List.of("added_timestamp", "update_timestamp")),
    Map.entry("master_configurations", List.of("update_timestamp")),
    Map.entry("master_product_credit_rating_benefits", List.of("update_timestamp")),
    Map.entry("tbl_admin_messages", List.of("added_timestamp")),
    Map.entry("tbl_collection_checklist_master", List.of("modified_date")),
    Map.entry("tbl_collection_disposition_master", List.of("modified_date")),
    Map.entry("tbl_hdfc_reconciliation", List.of("modified")),
    Map.entry("tbl_messageboard", List.of("last_updated_on")),
    Map.entry("tbl_rekyc_categories", List.of("last_updated_timestamp")),
    Map.entry("tbl_rekyc_sub_categories", List.of("last_updated_timestamp")),
    Map.entry("tbl_user_levels", List.of("update_timestamp"))
);

@PreUpdate
public void preUpdate(Object entity) {
    String table = getTableName(entity);
    List<String> columns = CUSTOM_TIMESTAMP_COLUMNS.get(table);
    if (columns != null) {
        for (String col : columns) {
            setTimestampIfPresent(entity, col, Instant.now());
        }
    }
}
```

### Python (SQLAlchemy) — ARCH wiki §2

```python
CUSTOM_TIMESTAMP_COLUMNS = {
    "master_banks": ["added_timestamp", "update_timestamp"],
    "master_configurations": ["update_timestamp"],
    "master_product_credit_rating_benefits": ["update_timestamp"],
    "tbl_admin_messages": ["added_timestamp"],
    "tbl_collection_checklist_master": ["modified_date"],
    "tbl_collection_disposition_master": ["modified_date"],
    "tbl_hdfc_reconciliation": ["modified"],
    "tbl_messageboard": ["last_updated_on"],
    "tbl_rekyc_categories": ["last_updated_timestamp"],
    "tbl_rekyc_sub_categories": ["last_updated_timestamp"],
    "tbl_user_levels": ["update_timestamp"],
}

@event.listens_for(Model, "before_update")
def set_custom_timestamps(mapper, connection, target):
    table = target.__table__.name
    cols = CUSTOM_TIMESTAMP_COLUMNS.get(table, [])
    now = datetime.now(timezone.utc)
    for col in cols:
        if hasattr(target, col):
            setattr(target, col, now)
```

## Collection domain note

RCM SMS cooling queries use `added_timestamp` on `tbl_sms_capture_*` — SQL rewrites in [collection-domain-files.md](collection-domain-files.md). Verify entity save paths still set timestamp columns on PG if MySQL relied on `ON UPDATE`.

## Verification

- Integration test: update row without explicit timestamp in SQL → `updated_at` (or custom column) advances
- Shadow compare PG vs MySQL after ORM update path
