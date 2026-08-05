#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOCK_FILE="${REPO_ROOT}/incident-rca/skills-lock.json"

if [[ ! -f "${LOCK_FILE}" ]]; then
  echo "error: missing ${LOCK_FILE}" >&2
  exit 1
fi

read -r SKILLS_CLI_VERSION COMMIT_SHA COMPUTED_HASH <<<"$(
  python3 - "${LOCK_FILE}" <<'PY'
import json
import sys

lock = json.load(open(sys.argv[1], encoding="utf-8"))
skill = lock["skills"]["kubesense-mcp"]
print(
    lock.get("skillsCliVersion", "1.5.14"),
    skill["commitSha"],
    skill.get("computedHash", ""),
)
PY
)"

SOURCE_URL="https://github.com/kubesense-ai/kubesense-mcp-skills/tree/${COMMIT_SHA}"

echo "Installing incident-rca external skill dependencies..."
echo "  skills CLI: ${SKILLS_CLI_VERSION}"
echo "  source pin: ${COMMIT_SHA}"

npx "skills@${SKILLS_CLI_VERSION}" add "${SOURCE_URL}" \
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
