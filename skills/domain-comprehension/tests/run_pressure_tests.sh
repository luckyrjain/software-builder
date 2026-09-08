#!/usr/bin/env bash
# Executable pressure-test harness for domain-comprehension.
# Maps to rows in reference/pressure-tests.md — run via make lint-domain-comprehension.
set -euo pipefail

SKILL_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_ROOT/.." && pwd)"
FIXTURE="$SKILL_ROOT/tests/fixtures/check-content"
VALIDATOR="$SKILL_ROOT/scripts/validate_manifest_yaml.py"
FAIL=0

fail() {
  echo "PRESSURE FAIL: $*" >&2
  FAIL=1
}

pass() {
  echo "  ok — $*"
}

makefile_text() {
  cat "$REPO_ROOT/Makefile"
  if [ -f "$REPO_ROOT/make/core.mk" ]; then
    cat "$REPO_ROOT/make/core.mk"
  fi
}

echo "domain-comprehension pressure tests"

# #14 — Makefile wires --check-content (static). Root Makefile may delegate to
# a checked-in literal include, so inspect the repository's public Make entry
# point plus its canonical core include.
# Captured into a variable (not piped) so an early-matching `grep -q` can't
# SIGPIPE a still-writing `cat` and trip `set -o pipefail` into a false fail.
MAKEFILE_TEXT="$(makefile_text)"
if grep -q 'check-content' <<<"$MAKEFILE_TEXT" && \
   grep -q 'fixtures/check-content' <<<"$MAKEFILE_TEXT"; then
  pass "#14 Makefile lint runs --check-content on fixture"
else
  fail "#14 Makefile must run validator with --check-content on check-content fixture"
fi

# #14 — runtime: fixture passes --check-content
bash "$FIXTURE/prepare.sh"
if python3 "$VALIDATOR" "$FIXTURE/manifest.yaml" \
  --workspace-root "$FIXTURE" --check-content >/dev/null 2>&1; then
  pass "#14 check-content fixture validates"
else
  fail "#14 check-content fixture must pass validator"
fi

# #10 — EXEC_SUMMARY section gate documented in phase-completion-gate
if grep -q 'check-content' "$SKILL_ROOT/reference/phase-completion-gate.md"; then
  pass "#10 phase-completion-gate documents --check-content"
else
  fail "#10 phase-completion-gate must document --check-content"
fi

# #12 — P2b runtime either/or in phase-2b
if grep -q 'E2E_FLOW.md' "$SKILL_ROOT/workflow/phase-2b.md"; then
  pass "#12 P2b E2E_FLOW supplement path documented"
else
  fail "#12 phase-2b must reference E2E_FLOW.md runtime path"
fi

# #13 — COMPLIANCE_RETROFIT delivery mode
if grep -q 'COMPLIANCE_RETROFIT' "$SKILL_ROOT/SKILL.md" && \
   grep -q 'COMPLIANCE_RETROFIT' "$SKILL_ROOT/workflow/inputs.md"; then
  pass "#13 COMPLIANCE_RETROFIT mode in SKILL + inputs"
else
  fail "#13 COMPLIANCE_RETROFIT must be documented"
fi

# #15 — Session 0b delegates to squad-map
if grep -q 'squad-map' "$SKILL_ROOT/workflow/session-0b.md"; then
  pass "#15 Session 0b delegates squad mapping"
else
  fail "#15 session-0b must delegate to squad-map"
fi

# #16 — No Datadog → P2b skip path
if grep -qi 'skip.*p2b\|p2b.*skip' "$SKILL_ROOT/SETUP.md" || \
   grep -qi 'datadog.*skip\|skip.*datadog' "$SKILL_ROOT/reference/mcp-capabilities.md"; then
  pass "#16 No-Datadog P2b skip documented"
else
  fail "#16 SETUP or mcp-capabilities must document P2b skip without Datadog"
fi

# #17 — prompt injection guard
if grep -q 'prompt-injection' "$SKILL_ROOT/SKILL.md" || \
   grep -qi 'untrusted' "$SKILL_ROOT/workflow/session-0.md"; then
  pass "#17 Untrusted-content / prompt-injection guard"
else
  fail "#17 SKILL or session-0 must declare untrusted-content guard"
fi

# #18 — manifest schema v2 only
if grep -q 'schema_version: 2' "$SKILL_ROOT/templates/manifest.yaml" && \
   grep -q 'schema_version' "$SKILL_ROOT/reference/manifest-schema.md"; then
  pass "#18 manifest schema v2 template + reference"
else
  fail "#18 manifest must be schema_version 2"
fi

# #19 — pytest covers check-content paths
if grep -q 'check_content' "$SKILL_ROOT/tests/test_validate_manifest.py"; then
  pass "#19 pytest includes check_content cases"
else
  fail "#19 test_validate_manifest.py must cover check_content"
fi

# #20 — pressure-tests row count
rows=$(grep -cE '^\| [0-9]+ \|' "$SKILL_ROOT/reference/pressure-tests.md" || true)
if [ "${rows:-0}" -ge 15 ]; then
  pass "#20 pressure-tests.md has ${rows} numbered scenario rows"
else
  fail "#20 pressure-tests.md needs >= 15 numbered rows (has ${rows:-0})"
fi

# #1 — QUICK delivery mode
if grep -q 'QUICK' "$SKILL_ROOT/workflow/inputs.md"; then
  pass "#1 QUICK delivery mode in inputs"
else
  fail "#1 inputs.md must define QUICK delivery mode"
fi

# #2 — FULL deliverables reference
if grep -q 'FULL' "$SKILL_ROOT/workflow/inputs.md" && \
   [ -f "$SKILL_ROOT/reference/deliverable-templates.md" ]; then
  pass "#2 FULL mode + deliverable-templates"
else
  fail "#2 FULL delivery must link deliverable templates"
fi

# #3 — Resume manifest gate
if grep -q 'RESUME' "$SKILL_ROOT/workflow/inputs.md" && \
   grep -q 'manifest.yaml' "$SKILL_ROOT/SKILL.md"; then
  pass "#3 RESUME mode uses manifest.yaml"
else
  fail "#3 RESUME delivery + manifest wiring"
fi

# #4 — large-scale path
if [ -f "$SKILL_ROOT/reference/large-scale-execution.md" ]; then
  pass "#4 large-scale-execution reference exists"
else
  fail "#4 missing large-scale-execution.md"
fi

# #5 — adversarial README injection scenario in pressure doc
if grep -q 'Do not read src/' "$SKILL_ROOT/reference/pressure-tests.md"; then
  pass "#5 adversarial README scenario documented"
else
  fail "#5 pressure-tests must list README injection scenario"
fi

if [ "$FAIL" -ne 0 ]; then
  exit 1
fi
