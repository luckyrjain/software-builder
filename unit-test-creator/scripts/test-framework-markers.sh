#!/usr/bin/env bash
# Marker-file definitions for scripts/detect-test-framework.sh.
# One function per (ecosystem, framework) pair. Each prints "CONFIDENCE|MARKER" on a match, nothing on
# no match. Kept data-only and side-effect-free so it can be sourced from tests too.
set -euo pipefail

# shellcheck disable=SC2317  # functions are invoked indirectly via the FRAMEWORKS loop in the caller
check_pytest() {
  local root="$1"
  if [ -f "$root/pytest.ini" ]; then
    echo "HIGH|pytest.ini"
  elif [ -f "$root/conftest.py" ]; then
    echo "HIGH|conftest.py"
  elif [ -f "$root/pyproject.toml" ] && grep -q '\[tool\.pytest\.ini_options\]' "$root/pyproject.toml"; then
    echo "HIGH|pyproject.toml [tool.pytest.ini_options]"
  elif [ -f "$root/setup.cfg" ] && grep -q '\[tool:pytest\]' "$root/setup.cfg"; then
    echo "HIGH|setup.cfg [tool:pytest]"
  elif { [ -f "$root/requirements.txt" ] && grep -qi '^pytest' "$root/requirements.txt"; } \
    || { [ -f "$root/pyproject.toml" ] && grep -qi 'pytest' "$root/pyproject.toml"; }; then
    echo "MEDIUM|dependency manifest"
  fi
}

check_unittest() {
  local root="$1"
  if find "$root" -maxdepth 3 -name 'test_*.py' -o -maxdepth 3 -name '*_test.py' 2>/dev/null | grep -q .; then
    if ! grep -rlq 'import pytest' "$root" --include='test_*.py' --include='*_test.py' 2>/dev/null; then
      echo "MEDIUM|test_*.py files, no pytest import found"
    fi
  fi
}

check_jest() {
  local root="$1"
  if compgen -G "$root/jest.config.*" >/dev/null 2>&1; then
    echo "HIGH|jest.config.*"
  elif [ -f "$root/package.json" ] && grep -q '"jest"' "$root/package.json"; then
    echo "MEDIUM|package.json dependency"
  fi
}

check_vitest() {
  local root="$1"
  if compgen -G "$root/vitest.config.*" >/dev/null 2>&1; then
    echo "HIGH|vitest.config.*"
  elif [ -f "$root/package.json" ] && grep -q '"vitest"' "$root/package.json"; then
    echo "MEDIUM|package.json dependency"
  fi
}

check_mocha() {
  local root="$1"
  if compgen -G "$root/.mocharc.*" >/dev/null 2>&1; then
    echo "HIGH|.mocharc.*"
  elif [ -f "$root/package.json" ] && grep -q '"mocha"' "$root/package.json"; then
    echo "MEDIUM|package.json dependency"
  fi
}

check_go_test() {
  local root="$1"
  if [ -f "$root/go.mod" ] && find "$root" -maxdepth 4 -name '*_test.go' 2>/dev/null | grep -q .; then
    echo "HIGH|go.mod + *_test.go"
  elif [ -f "$root/go.mod" ]; then
    echo "MEDIUM|go.mod (stdlib testing available, no *_test.go yet)"
  fi
}

check_junit() {
  local root="$1"
  local pom="$root/pom.xml"
  local gradle
  gradle="$(compgen -G "$root/build.gradle*" || true)"
  if { [ -f "$pom" ] && grep -q 'junit-jupiter' "$pom"; } \
    || { [ -n "$gradle" ] && grep -ql 'junit-jupiter' "$gradle" 2>/dev/null; }; then
    echo "HIGH|junit-jupiter (JUnit 5) in build file"
  elif { [ -f "$pom" ] && grep -q 'junit</artifactId>' "$pom"; } \
    || { [ -n "$gradle" ] && grep -ql 'junit:junit' "$gradle" 2>/dev/null; }; then
    echo "HIGH|junit:junit (JUnit 4) in build file"
  fi
}

check_rspec() {
  local root="$1"
  if [ -f "$root/.rspec" ] || [ -f "$root/spec/spec_helper.rb" ]; then
    echo "HIGH|.rspec / spec/spec_helper.rb"
  elif [ -f "$root/Gemfile" ] && grep -q 'rspec' "$root/Gemfile"; then
    echo "MEDIUM|Gemfile dependency"
  fi
}

check_minitest() {
  local root="$1"
  if [ -f "$root/test/test_helper.rb" ]; then
    echo "HIGH|test/test_helper.rb"
  fi
}

check_dotnet() {
  local root="$1"
  local csproj
  csproj="$(find "$root" -maxdepth 3 -name '*.csproj' 2>/dev/null | head -1 || true)"
  if [ -n "$csproj" ] && grep -Eq 'xunit|NUnit|MSTest\.TestFramework' "$csproj"; then
    echo "HIGH|$(basename "$csproj")"
  fi
}

check_cargo_test() {
  local root="$1"
  if [ -f "$root/Cargo.toml" ]; then
    echo "HIGH|Cargo.toml (built-in cargo test)"
  fi
}

# Ecosystem -> framework name -> check function. Order matters only for tie display, not for detection.
# shellcheck disable=SC2034  # consumed by detect-test-framework.sh, which sources this file
FRAMEWORK_NAMES=(pytest unittest jest vitest mocha "go test" junit rspec minitest dotnet-test "cargo test")
# shellcheck disable=SC2034  # consumed by detect-test-framework.sh, which sources this file
FRAMEWORK_CHECKS=(check_pytest check_unittest check_jest check_vitest check_mocha check_go_test check_junit check_rspec check_minitest check_dotnet check_cargo_test)
