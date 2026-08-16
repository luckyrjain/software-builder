#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP_HOME="$(mktemp -d)"
TMP_REPO="$(mktemp -d)"
TMP_DIST="$(mktemp -d)"
TMP_SRC="$(mktemp -d)"
trap 'rm -rf "${TMP_HOME}" "${TMP_REPO}" "${TMP_DIST}" "${TMP_SRC}"' EXIT

export HOME="${TMP_HOME}"
export PYTHONDONTWRITEBYTECODE=1

# Build and extract a real release bundle rather than a raw tar copy, so this
# exercises the actual documented flow (docs/RELEASE.md: download bundle,
# extract, run install.sh) -- an extracted bundle never contains .git since
# .git is never a tracked file, but it does carry RELEASE-MANIFEST.json,
# which package_skill.py now needs as its provenance source in exactly this
# no-.git case.
#
# package_release.py now requires a clean Git worktree and reads inputs from
# `git ls-files`, so this snapshots HEAD's tracked tree into an isolated Git
# commit rather than pointing package_release.py at REPO_ROOT directly --
# packaging straight from REPO_ROOT made this test fail on any uncommitted
# edit to a tracked file anywhere in the real repo, even one with nothing to
# do with installation (same problem, same fix, as
# scripts/tests/test_release.py's _minimal_release_repo).
git -C "${REPO_ROOT}" archive HEAD | tar -x -C "${TMP_SRC}"
git init -q "${TMP_SRC}"
git -C "${TMP_SRC}" config user.email "test@example.com"
git -C "${TMP_SRC}" config user.name "Test"
git -C "${TMP_SRC}" add -A
git -C "${TMP_SRC}" commit -qm snapshot
PYTHONPATH="${REPO_ROOT}" python3 "${REPO_ROOT}/scripts/package_release.py" \
  --repo-root "${TMP_SRC}" --output-dir "${TMP_DIST}"
ARCHIVE="$(ls "${TMP_DIST}"/software-builder-*.tar.gz)"
tar -xzf "${ARCHIVE}" -C "${TMP_REPO}" --strip-components=1

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
