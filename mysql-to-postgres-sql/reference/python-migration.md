# Python migration guide

ARCH wiki §6 covers SQLAlchemy connection strings. This file adds inventory, engine options, and timestamp hooks (parity with [nodejs-migration.md](nodejs-migration.md)).

## Inventory

```bash
rg -l 'mysql\+pymysql|mysql\.connector|MySQLdb|pymysql' <service_dir> --glob '*.py'
rg -n 'TIMESTAMPDIFF|DATE_FORMAT|IFNULL|REGEXP' <service_dir> --glob '*.py'
rg 'pymysql|mysqlclient|psycopg2' <service_dir>/requirements.txt <service_dir>/pyproject.toml 2>/dev/null || true
```

## SQLAlchemy engine (PostgreSQL)

| Setting | MySQL | PostgreSQL |
|---------|-------|------------|
| URL | `mysql+pymysql://user:pass@host:3306/db` | `postgresql+psycopg2://user:pass@host:5432/db?options=-csearch_path=schema` |
| Driver | pymysql / mysqlclient | psycopg2 (or psycopg v3: `postgresql+psycopg://`) |

```python
from sqlalchemy import create_engine

def db_create_engine(cf):
    url = (
        "postgresql+psycopg2://{user}:{passw}@{host}:{port}/{db}"
        "?options=-csearch_path={schema}"
    ).format(
        host=cf.HOST,
        port=cf.PORT,
        db=cf.DBNAME,
        user=cf.USER,
        schema=cf.SCHEMA,
        passw=cf.PASSWORD,
    )
    connect_args = {"application_name": cf.APP_NAME or "your-service-name"}
    return create_engine(url, connect_args=connect_args, pool_recycle=85)
```

- **`pool_recycle=85`** — ARCH wiki example; set **below** your LB idle timeout (often 300s+). Increase if connection churn is high — see [migration-edge-cases.md](migration-edge-cases.md).
- Remove `pymysql` / `mysqlclient` from requirements when cutover complete.

## Django

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["DB_NAME"],
        "USER": os.environ["DB_USER"],
        "PASSWORD": os.environ["DB_PASSWORD"],
        "HOST": os.environ["DB_HOST"],
        "PORT": os.environ.get("DB_PORT", "5432"),
        "OPTIONS": {
            "options": f"-c search_path={os.environ['DB_SCHEMA']}",
            "application_name": os.environ.get("APP_NAME", "your-service-name"),
        },
    }
}
```

Timestamp handling: `auto_now` / `auto_now_add` on `DateTimeField`, or `pre_save` signal — see [timestamp-handling.md](timestamp-handling.md).

## Raw SQL

`cursor.execute()` strings are scanned by `scan-mysql-dialect.sh` (`.py` glob). Placeholders: MySQL `%s` often works with psycopg2; prefer SQLAlchemy `text()` with `:named` params.

## ENUM / boolean

MySQL `ENUM` columns → `String` + app validation, or PostgreSQL `ENUM` type via Alembic migration. `TINYINT(1)` → `Boolean` — filter with `is True` not `= 1`. See [data-type-mapping.md](data-type-mapping.md).

## Case sensitivity

Normalize with `.lower()` before persist/query, or use `ILIKE` in raw SQL — [case-sensitivity.md](case-sensitivity.md).

## Verification

- pytest against PG staging or Testcontainers `postgres` image
- Datadog APM: `postgresql.query` spans
- Shadow compare ORM update paths for `updated_at` / custom timestamp columns
