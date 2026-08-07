#!/usr/bin/env bash
# Detect the base test runner AND the real-dependency orchestration mechanism under a target directory.
# Usage: detect-integration-setup.sh <root> [--hint <framework-name>]
#
# Exit codes: 0 DETECTED, 2 AMBIGUOUS, 3 NONE_DETECTED, 1 usage/internal error.
# STATUS and the exit code reflect the base FRAMEWORK dimension only, mirroring
# unit-test-creator's own detect-test-framework.sh contract. ORCHESTRATION/CONVENTION are additional
# dimensions always reported alongside — they never change the exit code themselves; see
# reference/framework-detection.md.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=integration-markers.sh
source "$SCRIPT_DIR/integration-markers.sh"

ROOT="${1:-}"
HINT=""
if [ -z "$ROOT" ] || [ "$ROOT" = "--hint" ]; then
  echo "usage: detect-integration-setup.sh <root> [--hint <framework-name>]" >&2
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
    echo "usage: detect-integration-setup.sh <root> [--hint <framework-name>]" >&2
    exit 1
    ;;
  esac
done

if [ ! -d "$ROOT" ]; then
  echo "ERROR: not a directory: $ROOT" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Dimension 1: base test runner (same contract as unit-test-creator's own script)
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Dimension 2: real-dependency orchestration mechanism (priority: testcontainers >
# docker-compose > embedded > none — see reference/framework-detection.md §2)
# ---------------------------------------------------------------------------
ORCHESTRATION="none"
ORCHESTRATION_CONFIDENCE="NONE"
ORCHESTRATION_MARKER="none"

orch_result="$(check_testcontainers "$ROOT")"
if [ -n "$orch_result" ]; then
  ORCHESTRATION="testcontainers"
  ORCHESTRATION_CONFIDENCE="${orch_result%%|*}"
  ORCHESTRATION_MARKER="${orch_result#*|}"
else
  orch_result="$(check_docker_compose "$ROOT")"
  if [ -n "$orch_result" ]; then
    ORCHESTRATION="docker-compose"
    ORCHESTRATION_CONFIDENCE="${orch_result%%|*}"
    ORCHESTRATION_MARKER="${orch_result#*|}"
  else
    orch_result="$(check_embedded_db "$ROOT")"
    if [ -n "$orch_result" ]; then
      ORCHESTRATION="embedded"
      ORCHESTRATION_CONFIDENCE="${orch_result%%|*}"
      ORCHESTRATION_MARKER="${orch_result#*|}"
    fi
  fi
fi

# ---------------------------------------------------------------------------
# Dimension 3 (informational): integration naming/tag convention
# ---------------------------------------------------------------------------
CONVENTION="none"
conv_result="$(check_integration_convention "$ROOT")"
if [ -n "$conv_result" ]; then
  CONVENTION="${conv_result#*|}"
fi

emit_orchestration_fields() {
  echo "ORCHESTRATION: $ORCHESTRATION"
  echo "ORCHESTRATION_CONFIDENCE: $ORCHESTRATION_CONFIDENCE"
  echo "ORCHESTRATION_MARKER: $ORCHESTRATION_MARKER"
  echo "CONVENTION: $CONVENTION"
}

if [ "${#CANDIDATE_NAMES[@]}" -eq 0 ]; then
  echo "STATUS: NONE_DETECTED"
  emit_orchestration_fields
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
      emit_orchestration_fields
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
  emit_orchestration_fields
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
emit_orchestration_fields
echo "ROOT: $ROOT"
exit 2
