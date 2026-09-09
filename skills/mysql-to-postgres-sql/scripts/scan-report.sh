#!/usr/bin/env bash
# Emit file:line hits for MySQL dialect (always exit 0). Use to refresh the domain pack checklist
# (reference/collection-checklist-refresh.md) — see reference/domain-packs/README.md.
set -euo pipefail

ROOT="${1:-.}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=mysql-dialect-patterns.sh
source "$SCRIPT_DIR/mysql-dialect-patterns.sh"

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
echo "# case-insensitive pattern: $PATTERN_CI"
echo "# case-sensitive pattern:   $PATTERN_CS"
echo

count=0
while IFS= read -r line; do
  echo "$line"
  count=$((count + 1))
done < <(
  { rg -n -U -i --pcre2 "$PATTERN_CI" "${GLOB_ARGS[@]}" "$ROOT" || true
    rg -n -U --pcre2 "$PATTERN_CS" "${GLOB_ARGS[@]}" "$ROOT" || true
  } | sort -u
)

echo
echo "# total hits: $count"
if [ "$count" -eq 0 ]; then
  echo "# OK: no MySQL-only dialect constructs found"
fi
