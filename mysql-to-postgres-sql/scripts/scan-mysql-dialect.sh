#!/usr/bin/env bash
# Scan for MySQL-only SQL dialect constructs. Exit 1 if any matches.
set -euo pipefail

ROOT="${1:-.}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=mysql-dialect-patterns.sh
source "$SCRIPT_DIR/mysql-dialect-patterns.sh"

echo "Scanning for MySQL-only SQL under: $ROOT"
echo "Case-insensitive pattern: $PATTERN_CI"
echo "Case-sensitive pattern:   $PATTERN_CS"
echo "Note: backtick identifiers and sql_mode GROUP BY issues require manual audit — see reference/migration-edge-cases.md"
echo

if ! command -v rg >/dev/null 2>&1; then
  echo "ERROR: ripgrep (rg) not found; install rg to run scan gate" >&2
  exit 1
fi

if ! rg --pcre2-version >/dev/null 2>&1; then
  echo "ERROR: ripgrep must be built with PCRE2 (check: rg --pcre2-version)" >&2
  exit 1
fi

FOUND=0
if rg -n -U -i --pcre2 "$PATTERN_CI" "${GLOB_ARGS[@]}" "$ROOT"; then
  FOUND=1
fi
if rg -n -U --pcre2 "$PATTERN_CS" "${GLOB_ARGS[@]}" "$ROOT"; then
  FOUND=1
fi

if [ "$FOUND" -eq 1 ]; then
  echo
  echo "FAIL: MySQL-only dialect constructs found. Rewrite before PG cutover."
  echo "See reference/function-translations.md and reference/migration-edge-cases.md"
  exit 1
fi

echo "OK: no MySQL-only dialect constructs found"
echo "Note: timestamps, ENUM, case sensitivity, backticks, GROUP BY strictness — see reference/"
