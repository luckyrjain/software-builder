#!/usr/bin/env bash
# Detect Postman/Newman black-box API test tooling in use under a target directory, and — when 2+
# collection files exist — which one is the canonical target.
# Usage: detect-postman-tooling.sh <root> [--hint <collection-file-path-or-basename>]
#
# Exit codes: 0 DETECTED, 2 AMBIGUOUS, 3 NONE_DETECTED, 1 usage/internal error.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=postman-markers.sh
source "$SCRIPT_DIR/postman-markers.sh"

ROOT="${1:-}"
HINT=""
if [ -z "$ROOT" ] || [ "$ROOT" = "--hint" ]; then
  echo "usage: detect-postman-tooling.sh <root> [--hint <collection-file-path-or-basename>]" >&2
  exit 1
fi
shift
while [ $# -gt 0 ]; do
  case "$1" in
  --hint)
    HINT="${2:-}"
    shift 2
    ;;
  *)
    echo "usage: detect-postman-tooling.sh <root> [--hint <collection-file-path-or-basename>]" >&2
    exit 1
    ;;
  esac
done

if [ ! -d "$ROOT" ]; then
  echo "ERROR: not a directory: $ROOT" >&2
  exit 1
fi

COLLECTIONS=()
while IFS= read -r line; do
  [ -n "$line" ] && COLLECTIONS+=("$line")
done < <(find_collection_files "$ROOT")
COLLECTION_COUNT="${#COLLECTIONS[@]}"

ENV_FILES=()
while IFS= read -r line; do
  [ -n "$line" ] && ENV_FILES+=("$line")
done < <(find_environment_files "$ROOT")
ENVIRONMENT_COUNT="${#ENV_FILES[@]}"

NEWMAN="$(has_newman_dependency "$ROOT")"

# Printed on every branch — informational fields never gate detection status on their own.
print_common_footer() {
  echo "COLLECTION_COUNT: $COLLECTION_COUNT"
  echo "ENVIRONMENT_COUNT: $ENVIRONMENT_COUNT"
  echo "NEWMAN: $NEWMAN"
  echo "ROOT: $ROOT"
}

report_detected() {
  local marker="$1" confidence="$2"
  echo "STATUS: DETECTED"
  echo "FRAMEWORK: postman"
  echo "CONFIDENCE: $confidence"
  echo "MARKER: $marker"
  print_common_footer
}

# Zero collection files.
if [ "$COLLECTION_COUNT" -eq 0 ]; then
  if [ "$NEWMAN" = "yes" ]; then
    report_detected "package.json newman dependency (no collection file yet)" "MEDIUM"
    exit 0
  fi
  echo "STATUS: NONE_DETECTED"
  print_common_footer
  exit 3
fi

# Exactly one collection — unambiguous regardless of hint.
if [ "$COLLECTION_COUNT" -eq 1 ]; then
  report_detected "${COLLECTIONS[0]} (only collection file found)" "HIGH"
  exit 0
fi

# 2+ collections — resolve which one is canonical. Resolution order documented in
# reference/framework-detection.md: hint, then naming convention, then CI reference, then ask.

if [ -n "$HINT" ]; then
  for c in "${COLLECTIONS[@]}"; do
    if [ "$c" = "$HINT" ] || [ "$(basename "$c")" = "$(basename "$HINT")" ]; then
      report_detected "$c (selected via --hint)" "HIGH"
      exit 0
    fi
  done
  echo "WARNING: --hint '$HINT' matched no discovered collection file; falling back to normal resolution" >&2
fi

NAMED=()
for c in "${COLLECTIONS[@]}"; do
  base_lc="$(basename "$c" | tr '[:upper:]' '[:lower:]')"
  if [[ "$base_lc" == *main* || "$base_lc" == *primary* ]]; then
    NAMED+=("$c")
  fi
done
if [ "${#NAMED[@]}" -eq 1 ]; then
  report_detected "${NAMED[0]} (named main/primary among $COLLECTION_COUNT candidates)" "HIGH"
  exit 0
fi

REFERENCED=()
for c in "${COLLECTIONS[@]}"; do
  if [ "$(collection_referenced_in_ci "$ROOT" "$(basename "$c")")" = "yes" ]; then
    REFERENCED+=("$c")
  fi
done
if [ "${#REFERENCED[@]}" -eq 1 ]; then
  report_detected "${REFERENCED[0]} (only collection referenced from a CI config among $COLLECTION_COUNT candidates)" "HIGH"
  exit 0
fi

echo "STATUS: AMBIGUOUS"
CANDIDATES_STR=""
for c in "${COLLECTIONS[@]}"; do
  [ -n "$CANDIDATES_STR" ] && CANDIDATES_STR="${CANDIDATES_STR}, "
  CANDIDATES_STR="${CANDIDATES_STR}${c}"
done
echo "CANDIDATES: $CANDIDATES_STR"
print_common_footer
exit 2
