#!/usr/bin/env bash
# Executable pressure-test harness for mysql-to-postgres-sql.
# Maps to rows in reference/pressure-tests.md — run via make lint-mysql-to-postgres-sql.
set -euo pipefail

SKILL_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_ROOT/.." && pwd)"
SCAN="$SKILL_ROOT/scripts/scan-mysql-dialect.sh"
FAIL=0

fail() {
  echo "PRESSURE FAIL: $*" >&2
  FAIL=1
}

pass() {
  echo "  ok — $*"
}

echo "mysql-to-postgres-sql pressure tests"

# #2 / scan gate — hits fixture must fail
if "$SCAN" "$SKILL_ROOT/tests/fixtures/mysql-dialect/hits" >/dev/null 2>&1; then
  fail "#2/#11 scan hits fixture should exit non-zero"
else
  pass "#2 scan detects TIMESTAMPDIFF in hits fixture"
fi

# #2 — clean fixture must pass
if "$SCAN" "$SKILL_ROOT/tests/fixtures/mysql-dialect/clean" >/dev/null 2>&1; then
  pass "#2 scan clean on portable SQL fixture"
else
  fail "#2 scan clean fixture should exit 0"
fi

# #13 — split-across-concatenated-string-literals must not false-negative
if "$SCAN" "$SKILL_ROOT/tests/fixtures/mysql-dialect/hits/SplitLiteralQuery.java" >/dev/null 2>&1; then
  fail "#13 scan must detect CAST(...AS CHAR) split across concatenated string literals"
else
  pass "#13 scan detects multi-line-split dialect construct"
fi

# #14 — JSON_EXTRACT / MATCH...AGAINST must not false-negative; bare -> must not false-positive
if "$SCAN" "$SKILL_ROOT/tests/fixtures/mysql-dialect/hits/JsonFulltextQuery.java" >/dev/null 2>&1; then
  fail "#14 scan must detect JSON_EXTRACT and MATCH...AGAINST fulltext search"
else
  pass "#14 scan detects JSON_EXTRACT and fulltext MATCH...AGAINST"
fi
if "$SCAN" "$SKILL_ROOT/tests/fixtures/mysql-dialect/clean/PortableQuery.java" >/dev/null 2>&1; then
  pass "#14 scan does not false-positive on lambda -> or bare jsonb ->"
else
  fail "#14 scan false-positived on lambda arrow or bare jsonb -> operator"
fi

# #15 — LIMIT_*/DIV-mentioning identifiers and comments must not false-positive
# (regression: the multiline fix for #13 originally widened LIMIT/DIV lookaheads to a negated
# character class, matching ANY code between the tokens — caught by cross-skill gap audit review)
if "$SCAN" "$SKILL_ROOT/tests/fixtures/mysql-dialect/clean/PortableQuery.java" >/dev/null 2>&1; then
  pass "#15 scan does not false-positive on LIMIT_KEY/RATE_LIMIT_THRESHOLD identifiers or DIV mentions"
else
  fail "#15 scan false-positived on ordinary LIMIT_*/DIV-mentioning code (see PortableQuery.java)"
fi

# #16 — IF() SQL function must be detected; lowercase `if (` control flow must not false-positive
if "$SCAN" "$SKILL_ROOT/tests/fixtures/mysql-dialect/hits/IfFunctionQuery.java" >/dev/null 2>&1; then
  fail "#16 scan must detect MySQL IF(...) SQL expression function"
else
  pass "#16 scan detects IF(...) SQL function"
fi
if "$SCAN" "$SKILL_ROOT/tests/fixtures/mysql-dialect/clean/PortableQuery.java" >/dev/null 2>&1; then
  pass "#16 scan does not false-positive on lowercase if(...)/getYear()-style control flow"
else
  fail "#16 scan false-positived on lowercase if(...) control flow or getYear()-style identifier"
fi

# #18 — lowercase MySQL SQL (ORMs, some style guides) must not be invisible to the scan; the
# case-insensitive pattern group must catch it while the case-sensitive group (IF/YEAR/MONTH/
# WEEK/DIV/LIMIT) stays uppercase-only per #16 above.
if "$SCAN" "$SKILL_ROOT/tests/fixtures/mysql-dialect/hits/LowercaseQuery.java" >/dev/null 2>&1; then
  fail "#18 scan must detect lowercase timestampdiff(...)/date_format(...)"
else
  pass "#18 scan detects lowercase MySQL SQL via case-insensitive pattern group"
fi

# #17 — remaining previously-untested dialect constructs (GROUP_CONCAT, ON DUPLICATE KEY, INSERT
# IGNORE, FIND_IN_SET, INSTR, REGEXP/RLIKE, ISNULL, ADDTIME, SUBSTRING_INDEX, CONVERT_TZ, JSON_*,
# YEAR/MONTH/WEEK) must each still be caught — one line per construct in the fixture, so dropping
# any single pattern from the regex fails this check.
if "$SCAN" "$SKILL_ROOT/tests/fixtures/mysql-dialect/hits/RemainingConstructs.java" >/dev/null 2>&1; then
  fail "#17 scan must detect every construct in RemainingConstructs.java"
else
  pass "#17 scan detects GROUP_CONCAT/ON DUPLICATE KEY/INSERT IGNORE/FIND_IN_SET/INSTR/REGEXP/RLIKE/ISNULL/ADDTIME/SUBSTRING_INDEX/CONVERT_TZ/JSON_*/YEAR/MONTH/WEEK"
fi

# #11 — rg missing must not silently pass (static + runtime)
if ! grep -q 'ripgrep (rg) not found' "$SCAN"; then
  fail "#11 scan script must error when rg missing"
else
  pass "#11 scan script documents rg requirement"
fi
if PATH="/usr/bin:/bin" "$SCAN" "$SKILL_ROOT/tests/fixtures/mysql-dialect/clean" >/dev/null 2>&1; then
  if command -v rg >/dev/null 2>&1 && [[ ":$PATH:" != *":$(dirname "$(command -v rg)"):"* ]]; then
    : # rg exists outside stripped PATH — runtime skip
  elif ! command -v rg >/dev/null 2>&1; then
    fail "#11 scan should exit non-zero when rg absent"
  fi
fi

# #1 — JPQL-only scope in contract
if grep -q 'JPQL' "$SKILL_ROOT/reference/skill-contract.md"; then
  pass "#1 JPQL-only path documented in skill-contract"
else
  fail "#1 skill-contract must scope JPQL vs native SQL"
fi

# #3 — OAuth expires guard
if grep -q 'oauth_refresh_tokens.expires' "$SKILL_ROOT/reference/migration-edge-cases.md"; then
  pass "#3 OAuth expires documented in migration-edge-cases"
else
  fail "#3 migration-edge-cases must warn on OAuth expires"
fi

# #4 — MR review routes to pr-review
if grep -q 'mysql-to-postgres-sql → pr-review' "$REPO_ROOT/docs/skill-framework/shared/cross-skill-escalation.md"; then
  pass "#4 migration MR escalation to pr-review in cross-skill matrix"
else
  fail "#4 cross-skill-escalation missing mysql→pr-review row"
fi

# #5 — squad-map routing
if grep -q 'squad-map' "$REPO_ROOT/docs/skill-framework/shared/skill-routing.md" && \
   grep -q 'mysql-to-postgres-sql' "$REPO_ROOT/docs/skill-framework/shared/skill-routing.md"; then
  pass "#5/#6 skill-routing registers mysql and squad-map"
else
  fail "#5 skill-routing must list mysql-to-postgres-sql"
fi

# #7 — gate: complete means gated
if grep -q 'Never report' "$SKILL_ROOT/reference/skill-contract.md" || \
   grep -q 'Complete means gated' "$SKILL_ROOT/reference/skill-contract.md"; then
  pass "#7 skill-contract forbids premature completion"
else
  fail "#7 skill-contract must gate 'migration complete'"
fi

# #8 — cooling pattern in calibration
if grep -q 'TIMESTAMPDIFF' "$SKILL_ROOT/reference/calibration-snippets.md" && \
   grep -q 'EXTRACT(EPOCH' "$SKILL_ROOT/reference/calibration-snippets.md"; then
  pass "#8 calibration-snippets includes cooling rewrite pair"
else
  fail "#8 calibration-snippets must include P0 cooling few-shot"
fi

# #9 — Node placeholder guidance
if grep -qE '\$[0-9]|placeholder' "$SKILL_ROOT/reference/nodejs-migration.md"; then
  pass "#9 nodejs-migration covers placeholder migration"
else
  fail "#9 nodejs-migration must document ? → \$n placeholders"
fi

# #10 — lazy-load index present
if grep -q 'do not read all up front' "$SKILL_ROOT/reference/lazy-load-index.md"; then
  pass "#10 lazy-load-index enforces on-demand loading"
else
  fail "#10 lazy-load-index must discourage bulk load"
fi

# domain-packs + fleet status artifact
if [ -f "$SKILL_ROOT/reference/domain-packs/README.md" ] && \
   [ -f "$SKILL_ROOT/templates/MIGRATION_STATUS.yaml" ] && \
   grep -q 'domain-packs' "$SKILL_ROOT/SKILL.md"; then
  pass "domain-packs README + MIGRATION_STATUS.yaml wired in SKILL.md"
else
  fail "domain-packs and MIGRATION_STATUS.yaml must exist and be linked from SKILL.md"
fi

# #12 — incident-rca escalation
if grep -q 'mysql-to-postgres-sql → incident-rca' "$REPO_ROOT/docs/skill-framework/shared/cross-skill-escalation.md"; then
  pass "#12 cutover regression escalates to incident-rca"
else
  fail "#12 cross-skill-escalation missing mysql→incident-rca row"
fi

# Table row count >= 12
rows=$(grep -c '^| [0-9]' "$SKILL_ROOT/reference/pressure-tests.md" || true)
if [ "${rows:-0}" -ge 12 ]; then
  pass "pressure-tests.md has $rows scenario rows"
else
  fail "pressure-tests.md needs >= 12 rows (got ${rows:-0})"
fi

if [ "$FAIL" -ne 0 ]; then
  echo "error: pressure test harness failed" >&2
  exit 1
fi

echo "  ok (all pressure tests)"
