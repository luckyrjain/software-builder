#!/usr/bin/env bash
# Marker-file definitions for scripts/detect-integration-setup.sh.
# Three groups of functions, each side-effect-free so they can be sourced from tests too:
#   1. FRAMEWORK_NAMES / FRAMEWORK_CHECKS — base test runner (same ecosystem set as unit-test-creator).
#   2. Orchestration checks — check_testcontainers / check_docker_compose / check_embedded_db.
#   3. check_integration_convention — informational naming/tag-convention signal.
# Each function prints "CONFIDENCE|MARKER" on a match, nothing on no match.
set -euo pipefail

# ---------------------------------------------------------------------------
# 1. Base test runner
# ---------------------------------------------------------------------------

# shellcheck disable=SC2317  # functions are invoked indirectly via the FRAMEWORK_CHECKS loop in the caller
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
# shellcheck disable=SC2034  # consumed by detect-integration-setup.sh, which sources this file
FRAMEWORK_NAMES=(pytest unittest jest vitest mocha "go test" junit rspec minitest dotnet-test "cargo test")
# shellcheck disable=SC2034  # consumed by detect-integration-setup.sh, which sources this file
FRAMEWORK_CHECKS=(check_pytest check_unittest check_jest check_vitest check_mocha check_go_test check_junit check_rspec check_minitest check_dotnet check_cargo_test)

# ---------------------------------------------------------------------------
# 2. Real-dependency orchestration mechanism
# ---------------------------------------------------------------------------

check_testcontainers() {
  local root="$1"
  local gradle
  gradle="$(compgen -G "$root/build.gradle*" || true)"
  local req
  for req in "$root"/requirements*.txt; do
    if [ -f "$req" ] && grep -qi 'testcontainers' "$req"; then
      echo "HIGH|$(basename "$req") (testcontainers)"
      return
    fi
  done
  if [ -f "$root/pyproject.toml" ] && grep -qi 'testcontainers' "$root/pyproject.toml"; then
    echo "HIGH|pyproject.toml (testcontainers)"
  elif [ -f "$root/package.json" ] && grep -q '"testcontainers"' "$root/package.json"; then
    echo "HIGH|package.json (testcontainers)"
  elif { [ -f "$root/pom.xml" ] && grep -q 'org.testcontainers' "$root/pom.xml"; } \
    || { [ -n "$gradle" ] && grep -ql 'org.testcontainers' "$gradle" 2>/dev/null; }; then
    echo "HIGH|pom.xml/build.gradle (org.testcontainers)"
  elif [ -f "$root/go.mod" ] && grep -q 'github.com/testcontainers/testcontainers-go' "$root/go.mod"; then
    echo "HIGH|go.mod (testcontainers-go)"
  fi
}

check_docker_compose() {
  local root="$1"
  local f
  for f in docker-compose.yml docker-compose.yaml docker-compose.test.yml docker-compose.test.yaml \
    docker-compose.override.yml docker-compose.override.yaml; do
    if [ -f "$root/$f" ]; then
      echo "HIGH|$f"
      return
    fi
  done
  local d
  for d in docker test; do
    if compgen -G "$root/$d/docker-compose*.yml" >/dev/null 2>&1 \
      || compgen -G "$root/$d/docker-compose*.yaml" >/dev/null 2>&1; then
      echo "HIGH|$d/docker-compose*.yml"
      return
    fi
  done
}

check_embedded_db() {
  local root="$1"
  local pom="$root/pom.xml"
  local gradle
  gradle="$(compgen -G "$root/build.gradle*" || true)"
  if { [ -f "$pom" ] && grep -qi 'com\.h2database' "$pom"; } \
    || { [ -n "$gradle" ] && grep -qil 'com\.h2database' "$gradle" 2>/dev/null; }; then
    echo "MEDIUM|H2 in-memory DB dependency"
    return
  fi
  local req
  for req in "$root"/requirements*.txt; do
    if [ -f "$req" ] && grep -Eqi 'fakeredis|mongomock' "$req"; then
      echo "MEDIUM|$(basename "$req") (fakeredis/mongomock)"
      return
    fi
  done
  if [ -f "$root/package.json" ] && grep -Eq '"ioredis-mock"|"mongodb-memory-server"' "$root/package.json"; then
    echo "MEDIUM|embedded DB npm dependency"
  fi
}

# ---------------------------------------------------------------------------
# 3. Integration naming/tag convention (informational only)
# ---------------------------------------------------------------------------

check_integration_convention() {
  local root="$1"
  if [ -d "$root/tests/integration" ]; then
    echo "x|tests/integration/ directory"
  elif [ -d "$root/test/integration" ]; then
    echo "x|test/integration/ directory"
  elif [ -d "$root/it" ]; then
    echo "x|it/ directory"
  elif [ -f "$root/pytest.ini" ] && grep -qi 'integration' "$root/pytest.ini"; then
    echo "x|pytest.ini markers = integration"
  elif [ -f "$root/pyproject.toml" ] && grep -q '\[tool\.pytest\.ini_options\]' "$root/pyproject.toml" \
    && grep -qi 'integration' "$root/pyproject.toml"; then
    echo "x|pyproject.toml pytest markers"
  elif [ -f "$root/pom.xml" ] && grep -Eq 'maven-failsafe-plugin' "$root/pom.xml"; then
    echo "x|Maven Failsafe plugin (*IT.java convention)"
  elif find "$root" -maxdepth 4 -name '*IT.java' 2>/dev/null | grep -q .; then
    echo "x|*IT.java naming convention"
  elif grep -rlq '@Tag("integration")' "$root" --include='*.java' 2>/dev/null; then
    echo "x|@Tag(\"integration\") usage"
  elif find "$root" -maxdepth 4 -name '*.integration.test.*' 2>/dev/null | grep -q .; then
    echo "x|*.integration.test.* naming"
  elif grep -rlq '//go:build integration' "$root" --include='*.go' 2>/dev/null; then
    echo "x|//go:build integration tag"
  fi
}
