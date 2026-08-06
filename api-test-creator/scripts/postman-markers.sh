#!/usr/bin/env bash
# Marker definitions for scripts/detect-postman-tooling.sh.
# Kept data-only and side-effect-free so it can be sourced from tests too.
set -euo pipefail

# Prints one *.postman_collection.json path per line (sorted), skipping generated/vendored paths. Empty
# output = none found.
find_collection_files() {
  local root="$1"
  find "$root" \
    \( -path "*/node_modules" -o -path "*/vendor" -o -path "*/dist" -o -path "*/build" \
       -o -path "*/.venv" -o -path "*/target" -o -path "*/__pycache__" -o -path "*/.git" \) -prune -o \
    -type f -name '*.postman_collection.json' -print 2>/dev/null | sort
}

# Prints one *.postman_environment.json path per line (sorted) — informational only, never a confidence
# signal on its own.
find_environment_files() {
  local root="$1"
  find "$root" \
    \( -path "*/node_modules" -o -path "*/vendor" -o -path "*/dist" -o -path "*/build" \
       -o -path "*/.venv" -o -path "*/target" -o -path "*/__pycache__" -o -path "*/.git" \) -prune -o \
    -type f -name '*.postman_environment.json' -print 2>/dev/null | sort
}

# yes/no — a "newman" entry exists in the nearest package.json's dependencies/devDependencies under root
# (excluding generated/vendored paths).
has_newman_dependency() {
  local root="$1"
  local pkg
  pkg="$(find "$root" \
    \( -path "*/node_modules" -o -path "*/vendor" -o -path "*/dist" -o -path "*/build" \
       -o -path "*/.venv" -o -path "*/target" -o -path "*/__pycache__" -o -path "*/.git" \) -prune -o \
    -type f -name 'package.json' -print 2>/dev/null | sort | head -n1)"
  if [ -n "$pkg" ] && grep -q '"newman"' "$pkg" 2>/dev/null; then
    echo "yes"
  else
    echo "no"
  fi
}

# yes/no — a CI config under .github/workflows/*.yml or .gitlab-ci.yml references the given collection
# file's basename (e.g. a `newman run <path>` invocation naming it).
collection_referenced_in_ci() {
  local root="$1" basename="$2"
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
  if grep -lF "$basename" "${ci_files[@]}" >/dev/null 2>&1; then
    echo "yes"
  else
    echo "no"
  fi
}
