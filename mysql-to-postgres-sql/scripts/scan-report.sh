#!/usr/bin/env bash
# Emit file:line hits for MySQL dialect (always exit 0). Use to refresh the domain pack checklist
# (reference/collection-checklist-refresh.md) — see reference/domain-packs/README.md.
set -euo pipefail

ROOT="${1:-.}"

# Keep in sync with scan-mysql-dialect.sh
# shellcheck disable=SC2016
PATTERN='TIMESTAMPDIFF|DATE_FORMAT\(|DATE_ADD\(|IFNULL\(|ISNULL\(|ADDTIME\(|SUBSTRING_INDEX|CONVERT_TZ|CAST\([^)]{0,80}AS CHAR\)|ON DUPLICATE KEY|INSERT IGNORE|GROUP_CONCAT\(|FIND_IN_SET\(|UNIX_TIMESTAMP\(|CURDATE\(|LAST_INSERT_ID\(|INSTR\(|\bREGEXP\b|\bRLIKE\b|DATEDIFF\(|STR_TO_DATE\(|LIMIT[\s"'"'"'+.]{1,40}[0-9]+[\s"'"'"'+.]{0,10},[\s"'"'"'+.]{0,20}[0-9]+|(?<![</a-zA-Z])\bDIV\b(?=[\s"'"'"'+.]{0,20}[0-9'"'"'(])|JSON_EXTRACT\(|JSON_UNQUOTE\(|JSON_ARRAYAGG\(|JSON_OBJECTAGG\(|JSON_CONTAINS\(|JSON_SET\(|JSON_REMOVE\(|JSON_MERGE\(|\bMATCH\s*\([^)]{0,80}\)\s*AGAINST\s*\('

if ! command -v rg >/dev/null 2>&1; then
  echo "error: ripgrep (rg) required" >&2
  exit 1
fi

if ! rg --pcre2-version >/dev/null 2>&1; then
  echo "error: ripgrep must be built with PCRE2 (check: rg --pcre2-version)" >&2
  exit 1
fi

echo "# MySQL dialect scan report"
echo "# root: $ROOT"
echo "# pattern: $PATTERN"
echo

count=0
while IFS= read -r line; do
  echo "$line"
  count=$((count + 1))
done < <(rg -n -U --pcre2 "$PATTERN" \
  --glob '*.java' \
  --glob '*.php' \
  --glob '*.sql' \
  --glob '*.py' \
  --glob '*.js' \
  --glob '*.ts' \
  --glob '!**/vendor/**' \
  --glob '!**/node_modules/**' \
  --glob '!**/dist/**' \
  --glob '!**/.understand-anything/**' \
  "$ROOT" || true)

echo
echo "# total hits: $count"
if [ "$count" -eq 0 ]; then
  echo "# OK: no MySQL-only dialect constructs found"
fi
