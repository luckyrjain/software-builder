#!/usr/bin/env bash
# Detect Pact consumer-driven-contract tooling in use under a target directory, plus whether a Pact
# Broker is configured for it.
# Usage: detect-pact-tooling.sh <root> [--hint <pact-library-name>]
#
# Exit codes: 0 DETECTED, 2 AMBIGUOUS, 3 NONE_DETECTED, 1 usage/internal error.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=pact-markers.sh
source "$SCRIPT_DIR/pact-markers.sh"

ROOT="${1:-}"
HINT=""
if [ -z "$ROOT" ] || [ "$ROOT" = "--hint" ]; then
  echo "usage: detect-pact-tooling.sh <root> [--hint <pact-library-name>]" >&2
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
    echo "usage: detect-pact-tooling.sh <root> [--hint <pact-library-name>]" >&2
    exit 1
    ;;
  esac
done

if [ ! -d "$ROOT" ]; then
  echo "ERROR: not a directory: $ROOT" >&2
  exit 1
fi

# Broker presence is informational only (never a detection candidate, never a gate) — computed once and
# printed on every branch below.
BROKER="$(check_pact_broker "$ROOT")"

CANDIDATE_NAMES=()
CANDIDATE_CONF=()
CANDIDATE_MARKER=()

for i in "${!FRAMEWORK_NAMES[@]}"; do
  name="${FRAMEWORK_NAMES[$i]}"
  check_fn="${FRAMEWORK_CHECKS[$i]}"
  result="$("$check_fn" "$ROOT")"
  if [ -n "$result" ]; then
    conf="${result%%|*}"
    marker="${result#*|}"
    CANDIDATE_NAMES+=("$name")
    CANDIDATE_CONF+=("$conf")
    CANDIDATE_MARKER+=("$marker")
  fi
done

if [ "${#CANDIDATE_NAMES[@]}" -eq 0 ]; then
  echo "STATUS: NONE_DETECTED"
  echo "BROKER: $BROKER"
  echo "ROOT: $ROOT"
  exit 3
fi

# Resolve via hint first, regardless of confidence tiering.
if [ -n "$HINT" ]; then
  for i in "${!CANDIDATE_NAMES[@]}"; do
    if [ "${CANDIDATE_NAMES[$i]}" = "$HINT" ]; then
      echo "STATUS: DETECTED"
      echo "FRAMEWORK: ${CANDIDATE_NAMES[$i]}"
      echo "CONFIDENCE: ${CANDIDATE_CONF[$i]}"
      echo "MARKER: ${CANDIDATE_MARKER[$i]}"
      echo "BROKER: $BROKER"
      echo "ROOT: $ROOT"
      exit 0
    fi
  done
  echo "WARNING: --hint '$HINT' matched no detected candidate; falling back to normal resolution" >&2
fi

# Top confidence tier: HIGH beats MEDIUM.
TOP="MEDIUM"
for c in "${CANDIDATE_CONF[@]}"; do
  if [ "$c" = "HIGH" ]; then
    TOP="HIGH"
    break
  fi
done

TOP_NAMES=()
TOP_MARKERS=()
for i in "${!CANDIDATE_NAMES[@]}"; do
  if [ "${CANDIDATE_CONF[$i]}" = "$TOP" ]; then
    TOP_NAMES+=("${CANDIDATE_NAMES[$i]}")
    TOP_MARKERS+=("${CANDIDATE_MARKER[$i]}")
  fi
done

if [ "${#TOP_NAMES[@]}" -eq 1 ]; then
  echo "STATUS: DETECTED"
  echo "FRAMEWORK: ${TOP_NAMES[0]}"
  echo "CONFIDENCE: $TOP"
  echo "MARKER: ${TOP_MARKERS[0]}"
  echo "BROKER: $BROKER"
  echo "ROOT: $ROOT"
  exit 0
fi

echo "STATUS: AMBIGUOUS"
CANDIDATES_STR=""
for i in "${!TOP_NAMES[@]}"; do
  [ -n "$CANDIDATES_STR" ] && CANDIDATES_STR="${CANDIDATES_STR}, "
  CANDIDATES_STR="${CANDIDATES_STR}${TOP_NAMES[$i]} ($TOP, ${TOP_MARKERS[$i]})"
done
echo "CANDIDATES: $CANDIDATES_STR"
echo "BROKER: $BROKER"
echo "ROOT: $ROOT"
exit 2
