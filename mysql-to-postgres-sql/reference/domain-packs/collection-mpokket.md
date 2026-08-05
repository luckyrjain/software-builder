# Domain pack: collection (mpokket)

Workspace: `collection` (mpokket GitLab group). JPQL-heavy CLMS mostly needs dialect only; this list is **native SQL** that breaks on PG.

Comprehension artifact mirror (when present): `collection/MYSQL_TO_PG_SQL_REWRITES.md`

**Extract once:** RCM + CAAS + `collection-module` `SmsDisposition.php` share cooling logic — consolidate after rewrite.

## P0 — Consent / SMS cooling

### `TblSmsCaptureRecordRepository.java`
Path: `neo/relationship-consent-manager/app/src/main/java/in/mpokket/rcm/repository/mpokket/TblSmsCaptureRecordRepository.java`

| Method | MySQL fragment | PostgreSQL |
|--------|----------------|------------|
| `findCoolingForToday` | `DATE_ADD(NOW(), INTERVAL :cool MINUTE)` | `NOW() + (:cool * INTERVAL '1 minute')` |
| | `TIMESTAMPDIFF(HOUR, MAX(...), CURRENT_TIMESTAMP())` | `FLOOR(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - MAX(added_timestamp))) / 3600)::int` — positive intervals only; see edge cases |
| | `(TIMESTAMPDIFF(MINUTE, MAX(...), CURRENT_TIMESTAMP()) > :cool)` | `(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - MAX(added_timestamp))) / 60 > :cool)` |
| | `DATE(tsc.added_timestamp) = :today` | `tsc.added_timestamp::date = :today` |
| `findCoolingWithinWindow` | `DATE_ADD(MAX(added_timestamp), INTERVAL :cool MINUTE)` | `MAX(added_timestamp) + (:cool * INTERVAL '1 minute')` |
| | `TIMESTAMPDIFF(MINUTE, tsc.added_timestamp, CURRENT_TIMESTAMP()) < :cool` | `EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - tsc.added_timestamp)) / 60 < :cool` |

Legacy mirrors: `legacy/collection-module/app/Models/SmsDisposition.php`, `app/Repositories/SmsCaptureRecordsRepository.php`

### `TblSmsCaptureRecordsRepository.java`
Path: `neo/relationship-consent-manager/.../TblSmsCaptureRecordsRepository.java`

| MySQL | PostgreSQL |
|-------|------------|
| `DATE_ADD(MAX(added_timestamp), INTERVAL :coolingPeriod MINUTE)` | `MAX(added_timestamp) + (:coolingPeriod * INTERVAL '1 minute')` |
| `TIMESTAMPDIFF(MINUTE, MAX(...), CURRENT_TIMESTAMP()) > :coolingPeriod` | `(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - MAX(added_timestamp))) / 60 > :coolingPeriod)` |

### `DefaulterSmsQueryRepository.java`
Path: `neo/collection-admin-api-service/.../DefaulterSmsQueryRepository.java` — method `findMobilesWithinCoolingPeriod`

| MySQL | PostgreSQL |
|-------|------------|
| `TIMESTAMPDIFF(MINUTE, tsc.added_timestamp, CURRENT_TIMESTAMP()) < :coolingMinutes` | `EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - tsc.added_timestamp)) / 60 < :coolingMinutes` |

## P1 — EMS, SWS, CAAS

### `DefaulterSmsRepository.java` (EMS)
Path: `neo/exception-management-service/.../DefaulterSmsRepository.java`

| MySQL | PostgreSQL |
|-------|------------|
| `DATE_FORMAT(sms_sent_timestamp, '%Y-%m-%d')` | `to_char(..., 'YYYY-MM-DD')` or `sms_sent_timestamp::date` |
| `CAST(d.fk_user_id AS CHAR)` | `d.fk_user_id::text` |

### `CAST AS CHAR` repos (EMS)

| File | Replace |
|------|---------|
| `UserRepository.java` | `CAST(u.id AS CHAR)` → `u.id::text` |
| `UserProfileBasicRepository.java` | `CAST(fk_user_id AS CHAR)` → `fk_user_id::text` |
| `RiskManagerCommentRepository.java` | `CAST(u.id AS CHAR)` → `u.id::text` |
| `AdminRepository.java` | `CAST(a.id AS CHAR)` → `a.id::text` |

### SWS penalty SQL

| File | Replace |
|------|---------|
| `LoanPenaltyRepository.java` | `CAST(rs.loan_attributes AS CHAR)` → `rs.loan_attributes::text` |
| `TblUserLoanRepository.java` ~L148, ~L184 | same |

### `UserLoanTransListSql.java` (CAAS)
Constant `WALLET_TXNS_HISTORY`: `IFNULL(paytm_order_id, rbl_order_id)` → `COALESCE(paytm_order_id, rbl_order_id)`

Other constants (`CONCAT_WS`, `REPLACE`) — portable.

## P2 — Legacy PHP

| File | Patterns |
|------|----------|
| `legacy/collection-module/app/Models/CollectionModel.php` | `DATE_FORMAT`, `IFNULL` |
| `legacy/collection-module/app/Models/SmsDisposition.php` | `DATE_ADD`, `TIMESTAMPDIFF` |
| `legacy/collection-module/app/Libraries/Helpers.php` | `CONVERT_TZ` |
| `legacy/collection-salaried-api/app/adminModel/Disposition.php` | `ADDTIME`, `SUBSTRING_INDEX`, `IF`, `TIMESTAMPDIFF` |

## P2 — CLMS semantic (portable SQL, verify types)

`neo/collection-loan-management/.../TblUserLoanRepository.java` — native SQL uses `is_canceled = 0`; change to `= false` if PG column is boolean.

## Services with MySQL JDBC (config change required)

| Service | MySQL role |
|---------|------------|
| collection-loan-management | Read-heavy + 2 narrow writes |
| collection-admin-api-service | Read + consent writes |
| relationship-consent-manager | Relative contact writes |
| exception-management-service | Read mpokketlive |
| system-waiver-service | Read mpokket |
| collection-agency-service | Pincode read only |
| repay-adjustment-service | Read mpokket |

Already PG-only: `collection-service`, `hvod`, `collection-kafka`.

## Test plan (collection)

| Flow | Assert |
|------|--------|
| SMS inside cooling window | blocked mobile list matches MySQL shadow |
| SMS after cooling | `isExceed` / allowed send |
| Defaulter SMS date (EMS) | date string parity |
| Waiver penalty (SWS) | `loan_attributes` text/JSON parse |
| Loan trans wallet orders (CAAS) | `COALESCE(paytm, rbl)` order_id |

Run on PG staging; shadow-compare 10–20 known `userId`s from prod.
