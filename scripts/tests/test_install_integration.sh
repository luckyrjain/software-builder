#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP_HOME="$(mktemp -d)"
TMP_REPO="$(mktemp -d)"
trap 'rm -rf "${TMP_HOME}" "${TMP_REPO}"' EXIT

export HOME="${TMP_HOME}"
export PYTHONDONTWRITEBYTECODE=1

cp -a "${REPO_ROOT}/scripts" "${TMP_REPO}/scripts"
cp -a "${REPO_ROOT}/unit-test-creator" "${TMP_REPO}/unit-test-creator"
mkdir -p "${TMP_REPO}/docs"
cp -a "${REPO_ROOT}/docs/skill-framework" "${TMP_REPO}/docs/skill-framework"
if [[ -d "${REPO_ROOT}/docs/superpowers/specs" ]]; then
  mkdir -p "${TMP_REPO}/docs/superpowers"
  cp -a "${REPO_ROOT}/docs/superpowers/specs" "${TMP_REPO}/docs/superpowers/specs"
fi

bash "${TMP_REPO}/scripts/install.sh" --agent cursor unit-test-creator

rm -rf "${TMP_REPO}"

INSTALLED="${HOME}/.cursor/skills/unit-test-creator"
test -f "${INSTALLED}/SKILL.md"
test -f "${INSTALLED}/.software-builder-manifest.json"
test -f "${INSTALLED}/docs/skill-framework/shared/test-creation-principles.md"

python3 "${REPO_ROOT}/scripts/validate_references.py" --installed-package "${INSTALLED}"

echo "install integration test: ok"
