#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP_HOME="$(mktemp -d)"
TMP_REPO="$(mktemp -d)"
trap 'rm -rf "${TMP_HOME}" "${TMP_REPO}"' EXIT

export HOME="${TMP_HOME}"
export PYTHONDONTWRITEBYTECODE=1

cp -a "${REPO_ROOT}/scripts" "${TMP_REPO}/scripts"
cp -a "${REPO_ROOT}/skills.yaml" "${TMP_REPO}/skills.yaml"
cp -a "${REPO_ROOT}/unit-test-creator" "${TMP_REPO}/unit-test-creator"
cp -a "${REPO_ROOT}/weekly-squad-digest" "${TMP_REPO}/weekly-squad-digest"
mkdir -p "${TMP_REPO}/docs"
cp -a "${REPO_ROOT}/docs/skill-framework" "${TMP_REPO}/docs/skill-framework"
if [[ -d "${REPO_ROOT}/docs/superpowers" ]]; then
  cp -a "${REPO_ROOT}/docs/superpowers" "${TMP_REPO}/docs/superpowers"
fi

# package_skill.py records distribution_version/source_sha via
# release_info.py, which now fails closed instead of falling back to
# "0.0.0"/"unknown" -- give this checkout-style fixture a real VERSION file
# and Git repo so it still exercises the code paths that need one.
echo "0.0.0" >"${TMP_REPO}/VERSION"
git init -q "${TMP_REPO}"
git -C "${TMP_REPO}" config user.email "test@example.com"
git -C "${TMP_REPO}" config user.name "Test"
git -C "${TMP_REPO}" add -A
git -C "${TMP_REPO}" commit -qm fixture

bash "${TMP_REPO}/scripts/install.sh" --agent cursor unit-test-creator weekly-squad-digest

rm -rf "${TMP_REPO}"

for skill in unit-test-creator weekly-squad-digest; do
  INSTALLED="${HOME}/.cursor/skills/${skill}"
  test -f "${INSTALLED}/SKILL.md"
  test -f "${INSTALLED}/.software-builder-manifest.json"
  test -f "${INSTALLED}/docs/skill-framework/shared/test-creation-principles.md"
  python3 "${REPO_ROOT}/scripts/validate_references.py" --installed-package "${INSTALLED}"
done

echo "install integration test: ok"
