# Node.js migration guide

ARCH wiki lists **Spring Boot, Python, and Node.js** as impacted. Node has no separate wiki section — use **general SQL** rules from [function-translations.md](function-translations.md) plus ORM/driver changes below.

## Inventory

```bash
rg -l "mysql2|dialect:\s*['\"]mysql|TYPEORM_.*mysql|knex.*mysql" <service_dir> --glob '*.{js,ts}' --glob '!**/node_modules/**'
rg "mysql2|sequelize|typeorm|knex|@prisma/client" <service_dir>/package.json
rg -n "TIMESTAMPDIFF|DATE_FORMAT|IFNULL|REGEXP" <service_dir> --glob '*.{js,ts}' --glob '!**/node_modules/**'
```

## Driver & connection

### mysql2 → pg (raw SQL)

**MySQL:**
```javascript
const mysql = require('mysql2/promise');
const pool = mysql.createPool({
  host: process.env.DB_HOST,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
});
```

**PostgreSQL:**
```javascript
const { Pool } = require('pg');
const pool = new Pool({
  host: process.env.DB_HOST,
  port: process.env.DB_PORT || 5432,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
  // schema + app name for PG observability (ARCH §6 / §9)
  options: `-c search_path=${process.env.DB_SCHEMA}`,
  application_name: process.env.APP_NAME || 'your-service-name',
});
```

**Placeholder change:** MySQL `?` → PG `$1`, `$2`, … (or named params via ORM).

**Remove:** `mysql` / `mysql2` from `package.json`; add `pg`.

### Sequelize

| Setting | MySQL | PostgreSQL |
|---------|-------|------------|
| `dialect` | `'mysql'` | `'postgres'` |
| Package | `mysql2` (driver) | `pg` |
| Schema | implicit / database | `dialectOptions: { prependSearchPath: true }` + `searchPath: process.env.DB_SCHEMA` (v6+) |
| SSL | varies | `dialectOptions.ssl` if required |

```javascript
const sequelize = new Sequelize(process.env.DB_NAME, process.env.DB_USER, process.env.DB_PASSWORD, {
  host: process.env.DB_HOST,
  port: process.env.DB_PORT || 5432,
  dialect: 'postgres',
  logging: false,
  dialectOptions: {
    application_name: process.env.APP_NAME || 'your-service-name',
  },
  // schema (Sequelize 6+):
  // dialectOptions: { prependSearchPath: true },
  // searchPath: process.env.DB_SCHEMA,
});
```

**Timestamps:** Enable `timestamps: true` on models; use `hooks` for custom column names (see [timestamp-handling.md](timestamp-handling.md)).

**ENUM:** Sequelize `ENUM` on MySQL → `DataTypes.ENUM` backed by PG enum or prefer `DataTypes.STRING` + app validation.

**BOOLEAN:** MySQL `TINYINT(1)` → `DataTypes.BOOLEAN`; queries using `1`/`0` need `true`/`false`.

### TypeORM

```typescript
// ormconfig / DataSource
{
  type: 'postgres',
  host: process.env.DB_HOST,
  port: parseInt(process.env.DB_PORT || '5432', 10),
  username: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
  schema: process.env.DB_SCHEMA,
  extra: {
    application_name: process.env.APP_NAME || 'your-service-name',
  },
}
```

**Timestamps:** `@CreateDateColumn()` / `@UpdateDateColumn()` replace MySQL `ON UPDATE CURRENT_TIMESTAMP`.

**ENUM:** `@Column({ type: 'enum', enum: MyEnum })` — verify PG enum type migration or use `varchar`.

### Knex

```javascript
const knex = require('knex')({
  client: 'pg',
  connection: {
    host: process.env.DB_HOST,
    port: process.env.DB_PORT || 5432,
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
    database: process.env.DB_NAME,
    searchPath: [process.env.DB_SCHEMA],
    application_name: process.env.APP_NAME || 'your-service-name',
  },
});
```

Change `client: 'mysql2'` → `'pg'`. Raw SQL in `.raw()` must follow [function-translations.md](function-translations.md).

### Prisma

```prisma
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}
```

`DATABASE_URL` example:
```
postgresql://user:pass@host:5432/db?schema=my_schema&application_name=my-service
```

Run `prisma migrate` / introspect after schema cutover. `@updatedAt` handles `updated_at` (replaces MySQL ON UPDATE).

## Raw SQL in Node

Template literals and `pool.query()` strings are scanned by `scan-mysql-dialect.sh` (`.js` / `.ts`).

Common fixes:
- `` `SELECT … LIMIT ${offset}, ${limit}` `` → `` `LIMIT ${limit} OFFSET ${offset}` ``
- `` `IFNULL(col, 0)` `` → `` `COALESCE(col, 0)` ``
- Backtick-quoted MySQL identifiers → double quotes or lowercase unquoted

## Case sensitivity

Same as Java/Python — see [case-sensitivity.md](case-sensitivity.md). Normalize email/username with `.toLowerCase()` before persist and query, or use `ILIKE` in raw SQL.

## Verification

- `npm test` / integration tests against PG (Testcontainers `postgres` image or staging)
- Datadog APM: `postgresql.query` spans, not `mysql.query`
- `sequelize.authenticate()` / health check against PG before deploy

## Collection domain

No active Node.js MySQL services in collection workspace (legacy UI packages are front-end only). This guide applies **org-wide** to Node services in other GitLab groups.
