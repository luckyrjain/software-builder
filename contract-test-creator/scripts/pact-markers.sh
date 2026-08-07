#!/usr/bin/env bash
# Marker definitions for scripts/detect-pact-tooling.sh.
# One function per (ecosystem, Pact library) pair. Each prints "CONFIDENCE|MARKER" on a match, nothing on
# no match. Kept data-only and side-effect-free so it can be sourced from tests too.
set -euo pipefail

# A local pacts/ directory with at least one *.json file is this skill's analog of test-writer's
# "dedicated config file present" HIGH-confidence signal: the ecosystem's Pact library isn't just
# declared as a dependency, it has already produced or consumed a real contract file.
_has_local_pacts() {
  local root="$1"
  compgen -G "$root/pacts/*.json" >/dev/null 2>&1
}

# shellcheck disable=SC2317  # functions are invoked indirectly via the FRAMEWORKS loop in the caller
check_pact_js() {
  local root="$1"
  if [ -f "$root/package.json" ] && grep -q '@pact-foundation/pact' "$root/package.json"; then
    if _has_local_pacts "$root"; then
      echo "HIGH|package.json dependency + pacts/ directory"
    else
      echo "MEDIUM|package.json dependency (no pacts/ directory yet)"
    fi
  fi
}

check_pact_python() {
  local root="$1"
  local hit=""
  if grep -hq 'pact-python' "$root"/requirements*.txt 2>/dev/null; then
    hit=1
  elif [ -f "$root/pyproject.toml" ] && grep -q 'pact-python' "$root/pyproject.toml"; then
    hit=1
  fi
  if [ -n "$hit" ]; then
    if _has_local_pacts "$root"; then
      echo "HIGH|dependency manifest + pacts/ directory"
    else
      echo "MEDIUM|dependency manifest (no pacts/ directory yet)"
    fi
  fi
}

check_pact_jvm() {
  local root="$1"
  local gradle
  gradle="$(compgen -G "$root/build.gradle*" || true)"
  if { [ -f "$root/pom.xml" ] && grep -q 'au\.com\.dius\.pact' "$root/pom.xml"; } \
    || { [ -n "$gradle" ] && grep -ql 'au\.com\.dius\.pact' "$gradle" 2>/dev/null; }; then
    if _has_local_pacts "$root"; then
      echo "HIGH|build file dependency + pacts/ directory"
    else
      echo "MEDIUM|build file dependency (no pacts/ directory yet)"
    fi
  fi
}

check_pact_go() {
  local root="$1"
  if [ -f "$root/go.mod" ] && grep -q 'github.com/pact-foundation/pact-go' "$root/go.mod"; then
    if _has_local_pacts "$root"; then
      echo "HIGH|go.mod dependency + pacts/ directory"
    else
      echo "MEDIUM|go.mod dependency (no pacts/ directory yet)"
    fi
  fi
}

check_pact_ruby() {
  local root="$1"
  local pattern="gem[[:space:]]+[\"']pact[\"']"
  if [ -f "$root/Gemfile" ] && grep -Eq "$pattern" "$root/Gemfile"; then
    if _has_local_pacts "$root"; then
      echo "HIGH|Gemfile dependency + pacts/ directory"
    else
      echo "MEDIUM|Gemfile dependency (no pacts/ directory yet)"
    fi
  fi
}

# Informational only — never a candidate in the FRAMEWORK_NAMES/FRAMEWORK_CHECKS loop, never gates
# confidence. Scoped to CI config files only, per reference/framework-detection.md.
check_pact_broker() {
  local root="$1"
  local ci_files=()
  while IFS= read -r -d '' f; do
    ci_files+=("$f")
  done < <(find "$root/.github/workflows" -maxdepth 1 -name '*.yml' -print0 2>/dev/null)
  if [ -f "$root/.gitlab-ci.yml" ]; then
    ci_files+=("$root/.gitlab-ci.yml")
  fi
  if [ "${#ci_files[@]}" -eq 0 ]; then
    echo "no"
    return
  fi
  if grep -lE 'PACT_BROKER_BASE_URL|pact-broker' "${ci_files[@]}" >/dev/null 2>&1; then
    echo "yes"
  else
    echo "no"
  fi
}

# Ecosystem -> Pact library name -> check function. Order matters only for tie display, not detection.
# shellcheck disable=SC2034  # consumed by detect-pact-tooling.sh, which sources this file
FRAMEWORK_NAMES=(pact-js pact-python pact-jvm pact-go pact-ruby)
# shellcheck disable=SC2034  # consumed by detect-pact-tooling.sh, which sources this file
FRAMEWORK_CHECKS=(check_pact_js check_pact_python check_pact_jvm check_pact_go check_pact_ruby)
