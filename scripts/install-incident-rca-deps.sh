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

read -r SKILLS_CLI_VERSION SKILLS_CLI_INTEGRITY REPO_SOURCE COMMIT_SHA COMPUTED_HASH <<<"$(
  python3 - "${LOCK_FILE}" <<'PY'
import json
import sys

lock = json.load(open(sys.argv[1], encoding="utf-8"))
skill = lock["skills"]["kubesense-mcp"]
print(
    lock["skillsCliVersion"],
    lock["skillsCliIntegrity"],
    skill["source"],
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

REPO_URL="https://github.com/${REPO_SOURCE}.git"

echo "Installing incident-rca external skill dependencies..."
echo "  skills CLI: ${SKILLS_CLI_VERSION}"
echo "  source pin: ${COMMIT_SHA}"

WORK_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "${WORK_DIR}"
}
trap cleanup EXIT

# Neither network call below (npm pack, git fetch) had any retry -- a single transient
# registry/GitHub hiccup aborted the whole script under set -e. The script is otherwise
# safe to rerun (WORK_DIR is a fresh mktemp -d each time, cleaned by the trap above), so
# a bounded retry with backoff turns "rerun the script by hand" into "usually just works."
retry() {
  local description="$1"
  shift
  local attempt
  for attempt in 1 2 3; do
    if "$@"; then
      return 0
    fi
    if [[ "${attempt}" -lt 3 ]]; then
      echo "warning: ${description} failed (attempt ${attempt}/3), retrying in $((attempt * 2))s..." >&2
      sleep "$((attempt * 2))"
    fi
  done
  echo "error: ${description} failed after 3 attempts" >&2
  return 1
}

# `npm pack` writes the registry tarball verbatim and runs none of its scripts, so
# this fetch is inert until the digest below has passed.
_npm_pack_skills_cli() {
  (cd "${WORK_DIR}" && npm pack "skills@${SKILLS_CLI_VERSION}" >/dev/null)
}
retry "npm pack skills@${SKILLS_CLI_VERSION}" _npm_pack_skills_cli

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

# The `skills` CLI clones non-allowlisted GitHub owners with
# `git clone --depth 1 --branch <ref>`, and `--branch` only resolves ref names
# (branches/tags) via the remote's advertised refs -- it rejects a bare commit
# SHA outright. kubesense-ai/kubesense-mcp-skills has no tag at our pinned
# commit, so passing the GitHub tree URL straight to `skills add` fails here.
# `git fetch <url> <sha>` has no such restriction (GitHub keeps loose objects
# fetchable by SHA even off the branch tips), so we do the pinned fetch
# ourselves and hand `skills add` a local checkout instead -- that path skips
# its clone step entirely.
SOURCE_DIR="${WORK_DIR}/source"
mkdir -p "${SOURCE_DIR}"
git -C "${SOURCE_DIR}" init -q
retry "git fetch ${REPO_URL} ${COMMIT_SHA}" \
  git -C "${SOURCE_DIR}" fetch -q --depth 1 "${REPO_URL}" "${COMMIT_SHA}"
git -C "${SOURCE_DIR}" checkout -q FETCH_HEAD

checked_out_sha="$(git -C "${SOURCE_DIR}" rev-parse HEAD)"
if [[ "${checked_out_sha}" != "${COMMIT_SHA}" ]]; then
  echo "error: fetched commit does not match pinned commitSha" >&2
  echo "  expected: ${COMMIT_SHA}" >&2
  echo "  actual:   ${checked_out_sha}" >&2
  exit 1
fi

npx --yes --package="${CLI_TARBALL}" skills add "${SOURCE_DIR}" \
  --skill kubesense-mcp \
  -g \
  -a cursor \
  -y

installed_path=""
for path in \
  "${HOME}/.agents/skills/kubesense-mcp/SKILL.md" \
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
  echo "  expected ~/.agents/skills/kubesense-mcp/SKILL.md, ~/.cursor/skills/kubesense-mcp/SKILL.md, or .agents/skills/kubesense-mcp/SKILL.md" >&2
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
