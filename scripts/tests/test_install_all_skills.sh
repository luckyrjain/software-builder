#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP_HOME="$(mktemp -d)"
TMP_REPO="$(mktemp -d)"
trap 'rm -rf "${TMP_HOME}" "${TMP_REPO}"' EXIT

export HOME="${TMP_HOME}"
export PYTHONDONTWRITEBYTECODE=1

tar -C "${REPO_ROOT}" \
  --exclude='.git' \
  --exclude='dist' \
  --exclude='__pycache__' \
  --exclude='.pytest_cache' \
  -cf - . | tar -C "${TMP_REPO}" -xf -

bash "${TMP_REPO}/scripts/install.sh" --agent cursor

rm -rf "${TMP_REPO}"

SKILLS=()
while IFS= read -r line; do
  SKILLS+=("${line}")
done < <(
  PYTHONPATH="${REPO_ROOT}" python3 "${REPO_ROOT}/scripts/install_support.py" list
)

if ((${#SKILLS[@]} != 23)); then
  echo "error: expected 23 registry skills, got ${#SKILLS[@]}" >&2
  exit 1
fi

for skill in "${SKILLS[@]}"; do
  INSTALLED="${HOME}/.cursor/skills/${skill}"
  test -f "${INSTALLED}/SKILL.md"
  test -f "${INSTALLED}/.software-builder-manifest.json"
  PYTHONPATH="${REPO_ROOT}" python3 "${REPO_ROOT}/scripts/install_support.py" verify "${INSTALLED}"
  python3 "${REPO_ROOT}/scripts/validate_references.py" --installed-package "${INSTALLED}"
done

echo "install-all-skills test: ok (${#SKILLS[@]} skills)"
