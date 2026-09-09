# Data ownership (normative)

**Artifact:** `DATA_OWNERSHIP.md`. **Produced in:** P1 (initial), refined P3.

Every architectural question eventually becomes *who owns this data?* Document authoritatively.

## Per-entity table (required)

| Entity | Authoritative source (repo + table/API) | Repository methods (@Query) | Schema evidence | Replicas | Caches | Search indexes | Consumers | Confidence |
|--------|----------------------------------------|------------------------------|-----------------|----------|--------|----------------|-----------|------------|

### Column rules

| Column | Evidence priority |
|--------|-------------------|
| **Authoritative source** | Migration author repo > producer of create API > consumer assumption |
| **Repository methods** | Repository interface method signatures touching this entity; full `@Query` JPQL/native SQL text when present, else method-name-derived-query note |
| **Schema evidence** | `@Column` constraints (nullable, unique, length), `@OneToMany`/`@ManyToOne`/`@JoinColumn` relationships, foreign keys from migration DDL — cite the entity class or migration file, not a guess from field naming |
| **Replicas** | Read-only copies in other DBs/services |
| **Caches** | Redis/Memcached keys, TTL config |
| **Search indexes** | ES/OpenSearch index writers |
| **Consumers** | Services reading but not authoring |

## Example row

```
Entity: Loan
Authoritative: loan-product-service / loans (migration V12)
Repository methods: LoanRepository.findByStatus(status) — derived query; LoanRepository.findOverdue()
  — @Query("SELECT l FROM Loan l WHERE l.dueDate < :now AND l.status = 'ACTIVE'")
Replicas: analytics-pipeline (read replica)
Caches: Redis loan:{id} (loan-product-service config)
Search: — 
Consumers: disbursement-service, collections-service, notifications
Confidence: HIGH
```

## Multi-writer detection

If 2+ repos write same table/entity → smell **Multiple writers** in `RISK_MAP.md` § Smells.

## No single source of truth

If state scattered as string constants → flag `⚠️` and list all locations; confidence cap **MEDIUM**.
