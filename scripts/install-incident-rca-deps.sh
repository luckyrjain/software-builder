#!/usr/bin/env bash
#
# Install incident-rca's external skill dependency (kubesense-mcp).
#
# Supply-chain policy: nothing here executes code fetched from npm until that code
# has been checked against a digest recorded in incident-rca/skills-lock.json. The
# `skills` CLI tarball is downloaded with `npm pack` (which only writes a file --
# it runs no install scripts), verified against `skillsCliIntegrity`, and only then
# executed via `npx --package=<verified tarball>`. A version tag alone is not a pin:
# it constrains which release npm is asked for, not which bytes npm returns.
#
# Residual risk, stated plainly: the verified tarball's own dependencies are still
# resolved from npm at run time and are not covered by this digest. Closing that
# would require vendoring a full npm lockfile for the CLI. The digest here closes
# the larger hole -- a substituted or re-published `skills` package.
#
# Refreshing the pin (do all of these together, in one commit):
#   1. Pick the new CLI version V.
#   2. npm view "skills@V" dist.integrity
#   3. In incident-rca/skills-lock.json set "skillsCliVersion" to V and
#      "skillsCliIntegrity" to the exact sha512-... string from step 2.
#   4. Re-run this script. If the upstream skill tree also moved, update
#      "commitSha" and re-record "computedHash" from the installed SKILL.md
#      (the mismatch error below prints the observed value).
# Both fields must move together: a version without its matching digest fails closed.
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOCK_FILE="${REPO_ROOT}/incident-rca/skills-lock.json"

if [[ ! -f "${LOCK_FILE}" ]]; then
  echo "error: missing ${LOCK_FILE}" >&2
  exit 1
fi

read -r SKILLS_CLI_VERSION SKILLS_CLI_INTEGRITY COMMIT_SHA COMPUTED_HASH <<<"$(
  python3 - "${LOCK_FILE}" <<'PY'
import json
import sys

lock = json.load(open(sys.argv[1], encoding="utf-8"))
skill = lock["skills"]["kubesense-mcp"]
print(
    lock["skillsCliVersion"],
    lock["skillsCliIntegrity"],
    skill["commitSha"],
    skill.get("computedHash", ""),
)
PY
)"

if [[ "${SKILLS_CLI_INTEGRITY}" != sha512-* ]]; then
  echo "error: skillsCliIntegrity must be a sha512-... subresource integrity string" >&2
  echo "  found: ${SKILLS_CLI_INTEGRITY}" >&2
  exit 1
fi

SOURCE_URL="https://github.com/kubesense-ai/kubesense-mcp-skills/tree/${COMMIT_SHA}"

echo "Installing incident-rca external skill dependencies..."
echo "  skills CLI: ${SKILLS_CLI_VERSION}"
echo "  source pin: ${COMMIT_SHA}"

WORK_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "${WORK_DIR}"
}
trap cleanup EXIT

# `npm pack` writes the registry tarball verbatim and runs none of its scripts, so
# this fetch is inert until the digest below has passed.
(cd "${WORK_DIR}" && npm pack "skills@${SKILLS_CLI_VERSION}" >/dev/null)

CLI_TARBALL="${WORK_DIR}/skills-${SKILLS_CLI_VERSION}.tgz"
if [[ ! -f "${CLI_TARBALL}" ]]; then
  echo "error: npm pack did not produce ${CLI_TARBALL}" >&2
  exit 1
fi

actual_integrity="$(
  python3 - "${CLI_TARBALL}" <<'PY'
import base64
import hashlib
import sys

digest = hashlib.sha512()
with open(sys.argv[1], "rb") as handle:
    for chunk in iter(lambda: handle.read(1 << 20), b""):
        digest.update(chunk)
print("sha512-" + base64.b64encode(digest.digest()).decode("ascii"))
PY
)"

if [[ "${actual_integrity}" != "${SKILLS_CLI_INTEGRITY}" ]]; then
  echo "error: skills CLI tarball integrity mismatch -- refusing to execute it" >&2
  echo "  expected: ${SKILLS_CLI_INTEGRITY}" >&2
  echo "  actual:   ${actual_integrity}" >&2
  echo "  see the refresh procedure at the top of $0" >&2
  exit 1
fi
echo "  CLI integrity ok (${actual_integrity})"

npx --yes --package="${CLI_TARBALL}" skills add "${SOURCE_URL}" \
  --skill kubesense-mcp \
  -g \
  -a cursor \
  -y

installed_path=""
for path in \
  "${HOME}/.cursor/skills/kubesense-mcp/SKILL.md" \
  "${REPO_ROOT}/.agents/skills/kubesense-mcp/SKILL.md"; do
  if [[ -f "${path}" ]]; then
    echo "Verified kubesense-mcp skill at ${path}"
    installed_path="${path}"
    break
  fi
done

if [[ -z "${installed_path}" ]]; then
  echo "error: kubesense-mcp skill not found after install" >&2
  echo "  expected ~/.cursor/skills/kubesense-mcp/SKILL.md or .agents/skills/kubesense-mcp/SKILL.md" >&2
  exit 1
fi

if [[ -n "${COMPUTED_HASH}" ]]; then
  expected="${COMPUTED_HASH#sha256:}"
  actual="$(shasum -a 256 "${installed_path}" | awk '{print $1}')"
  if [[ "${actual}" != "${expected}" ]]; then
    echo "error: kubesense-mcp SKILL.md hash mismatch" >&2
    echo "  expected: sha256:${expected}" >&2
    echo "  actual:   sha256:${actual}" >&2
    exit 1
  fi
  echo "  hash ok (sha256:${actual})"
fi

echo "Skill pin: ${LOCK_FILE}"
echo "Done. Restart Cursor to load kubesense-mcp."
