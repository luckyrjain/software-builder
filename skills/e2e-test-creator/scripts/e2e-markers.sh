#!/usr/bin/env bash
# Marker-file definitions for scripts/detect-e2e-tooling.sh.
# One check_<framework> function and one layout_<framework> function per browser-automation
# framework. check_* prints "CONFIDENCE|MARKER" on a match, nothing on no match. layout_* always
# prints a directory-convention string (falling back to the framework's own default when no
# existing layout is found on disk). Kept data-only and side-effect-free so it can be sourced from
# tests too.
set -euo pipefail

# shellcheck disable=SC2317  # functions are invoked indirectly via the FRAMEWORK_* loops in the caller
check_playwright() {
  local root="$1"
  if compgen -G "$root/playwright.config.*" >/dev/null 2>&1; then
    echo "HIGH|playwright.config.*"
  elif [ -f "$root/package.json" ] && grep -q '"@playwright/test"' "$root/package.json"; then
    echo "MEDIUM|package.json devDependency"
  fi
}

layout_playwright() {
  local root="$1"
  local d
  for d in "e2e" "tests/e2e" "playwright-tests"; do
    if [ -d "$root/$d" ] && find "$root/$d" -maxdepth 4 -name '*.spec.ts' 2>/dev/null | grep -q .; then
      echo "$d/ (*.spec.ts)"
      return
    fi
  done
  echo "playwright-tests/ (default — no existing layout found)"
}

check_cypress() {
  local root="$1"
  if compgen -G "$root/cypress.config.*" >/dev/null 2>&1; then
    echo "HIGH|cypress.config.*"
  elif [ -f "$root/package.json" ] && grep -q '"cypress"' "$root/package.json"; then
    echo "MEDIUM|package.json devDependency"
  fi
}

layout_cypress() {
  local root="$1"
  if [ -d "$root/cypress/e2e" ]; then
    echo "cypress/e2e/ (*.cy.ts)"
  elif [ -d "$root/cypress/integration" ]; then
    echo "cypress/integration/ (*.spec.ts, legacy Cypress <10 layout)"
  else
    echo "cypress/e2e/ (default — no existing layout found)"
  fi
}

check_selenium() {
  local root="$1"
  local gradle req
  gradle="$(compgen -G "$root/build.gradle*" || true)"
  req="$(compgen -G "$root/requirements*.txt" || true)"
  if [ -f "$root/package.json" ] && grep -q '"selenium-webdriver"' "$root/package.json"; then
    echo "MEDIUM|package.json dependency (selenium-webdriver)"
  elif [ -n "$req" ] && grep -qil '^selenium' "$req" 2>/dev/null; then
    echo "MEDIUM|requirements*.txt dependency (selenium)"
  elif [ -f "$root/pom.xml" ] && grep -q 'org.seleniumhq.selenium' "$root/pom.xml"; then
    echo "MEDIUM|pom.xml dependency (org.seleniumhq.selenium)"
  elif [ -n "$gradle" ] && grep -ql 'org.seleniumhq.selenium' "$gradle" 2>/dev/null; then
    echo "MEDIUM|build.gradle* dependency (org.seleniumhq.selenium)"
  fi
}

layout_selenium() {
  local root="$1"
  local d
  for d in "e2e" "tests/e2e"; do
    if [ -d "$root/$d" ]; then
      echo "$d/"
      return
    fi
  done
  echo "e2e/ (default — no existing layout found)"
}

# Framework name -> check function -> layout function. Order matters only for tie display, not for
# detection.
# shellcheck disable=SC2034  # consumed by detect-e2e-tooling.sh, which sources this file
FRAMEWORK_NAMES=(playwright cypress selenium)
# shellcheck disable=SC2034  # consumed by detect-e2e-tooling.sh, which sources this file
FRAMEWORK_CHECKS=(check_playwright check_cypress check_selenium)
# shellcheck disable=SC2034  # consumed by detect-e2e-tooling.sh, which sources this file
FRAMEWORK_LAYOUTS=(layout_playwright layout_cypress layout_selenium)
