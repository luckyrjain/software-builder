# shellcheck shell=bash
# shellcheck disable=SC2034
# This file is a library, sourced by scan-mysql-dialect.sh and scan-report.sh — the variables
# below are used by the sourcing scripts, not within this file itself.
# Shared MySQL-only dialect patterns. Sourced by scan-mysql-dialect.sh (the gate) and
# scan-report.sh (the report-only variant) so the two can never drift out of sync — do not
# hand-copy these patterns into either script again.
#
# DATE_FORMAT\( — avoid Java DateTimeFormatter constant false positives.
# No backtick identifiers: false positives on JS template literals and PHP shell execution.
# DIV — uppercase only, must be followed by SQL operand (not HTML <div>).
# -U/dotall (below) lets CAST/LIMIT/DIV match when a source-level concatenated string literal
# splits the construct across lines (e.g. "CAST(x " + "AS CHAR)") — [^)] spans are bounded to
# {0,80} so a match can't run away across unrelated code looking for a distant closing paren.
# LIMIT/DIV glue is restricted to [\s"'+.] (plausible string-literal-concatenation punctuation)
# rather than a negated class — a negated class (e.g. [^,]) matches ANY code between the tokens,
# which false-positives on ordinary identifiers like LIMIT_KEY or a comment mentioning "DIV".
# JSON_* — function-style only; MySQL's `->`/`->>` shorthand operators are excluded (PG's own
# jsonb operators use identical syntax, so they're not a MySQL-only dialect signal).
# MATCH...AGAINST — require both tokens together (fulltext idiom); bare AGAINST is too common
# a word to scan alone.
#
# Two pattern groups, scanned separately:
#   PATTERN_CI (case-insensitive): tokens that are not plausible English words/identifiers
#   regardless of case (TIMESTAMPDIFF, DATE_FORMAT(, JSON_*(, etc.) — safe to catch lowercase SQL,
#   which ORMs and some style guides emit routinely and which an all-uppercase-only pattern
#   would silently miss.
#   PATTERN_CS (case-sensitive, uppercase-only): DIV, LIMIT, IF(, YEAR(, MONTH(, WEEK(, REGEXP,
#   RLIKE — tokens where case-sensitivity is load-bearing to avoid false positives on ordinary
#   code identifiers and control flow (HTML <div>, `if (`, `getYear()`, `LIMIT_KEY`, a `regexp`/
#   `rlike` variable name in JS/TS/Python, etc.). Do not relax these to -i.
# shellcheck disable=SC2016
PATTERN_CI='TIMESTAMPDIFF|DATE_FORMAT\(|DATE_ADD\(|IFNULL\(|ISNULL\(|ADDTIME\(|SUBSTRING_INDEX|CONVERT_TZ|CAST\([^)]{0,80}AS CHAR\)|ON DUPLICATE KEY|INSERT IGNORE|GROUP_CONCAT\(|FIND_IN_SET\(|UNIX_TIMESTAMP\(|CURDATE\(|LAST_INSERT_ID\(|INSTR\(|DATEDIFF\(|STR_TO_DATE\(|JSON_EXTRACT\(|JSON_UNQUOTE\(|JSON_ARRAYAGG\(|JSON_OBJECTAGG\(|JSON_CONTAINS\(|JSON_SET\(|JSON_REMOVE\(|JSON_MERGE\(|\bMATCH\s*\([^)]{0,80}\)\s*AGAINST\s*\('
# shellcheck disable=SC2016
PATTERN_CS='\bIF\(|\bYEAR\(|\bMONTH\(|\bWEEK\(|\bREGEXP\b|\bRLIKE\b|LIMIT[\s"'"'"'+.]{1,40}[0-9]+[\s"'"'"'+.]{0,10},[\s"'"'"'+.]{0,20}[0-9]+|(?<![</a-zA-Z])\bDIV\b(?=[\s"'"'"'+.]{0,20}[0-9'"'"'(])'

GLOB_ARGS=(
  --glob '*.java'
  --glob '*.php'
  --glob '*.sql'
  --glob '*.py'
  --glob '*.js'
  --glob '*.ts'
  --glob '!**/vendor/**'
  --glob '!**/node_modules/**'
  --glob '!**/dist/**'
  --glob '!**/.understand-anything/**'
)
