#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP_HOME="$(mktemp -d)"
trap 'rm -rf "${TMP_HOME}"' EXIT

export HOME="${TMP_HOME}"
export PYTHONDONTWRITEBYTECODE=1

bash "${REPO_ROOT}/scripts/install.sh" --agent cursor unit-test-creator

INSTALLED="${HOME}/.cursor/skills/unit-test-creator"
test -f "${INSTALLED}/SKILL.md"
test -f "${INSTALLED}/.software-builder-manifest.json"
test -f "${INSTALLED}/docs/skill-framework/shared/test-creation-principles.md"

python3 "${REPO_ROOT}/scripts/validate_references.py" --installed-package "${INSTALLED}"

echo "install integration test: ok"
