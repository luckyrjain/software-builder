#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

AGENT="all"
TARGET_DIR=""
SKILLS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
  --agent)
    AGENT="$2"
    shift 2
    ;;
  --target-dir)
    TARGET_DIR="$2"
    shift 2
    ;;
  *)
    SKILLS+=("$1")
    shift
    ;;
  esac
done

case "${AGENT}" in
cursor | claude-user | claude-project | all) ;;
*)
  echo "error: unknown --agent '${AGENT}' (expected cursor|claude-user|claude-project|all)" >&2
  exit 1
  ;;
esac

dest_roots() {
  case "${AGENT}" in
  cursor)
    echo "${HOME}/.cursor/skills"
    ;;
  claude-user)
    echo "${HOME}/.claude/skills"
    ;;
  claude-project)
    local base="${TARGET_DIR:-$(pwd)}"
    echo "${base}/.claude/skills"
    ;;
  all)
    printf '%s\n%s\n' "${HOME}/.cursor/skills" "${HOME}/.claude/skills"
    ;;
  esac
}

host_label_for_dest() {
  local dest_root="$1"
  case "${dest_root}" in
  "${HOME}/.cursor/skills")
    echo "cursor"
    ;;
  "${HOME}/.claude/skills")
    echo "claude-user"
    ;;
  *)
    echo "claude-project"
    ;;
  esac
}

install_skill() {
  local skill="$1"
  local dest_root="$2"

  # Reject path-traversal / directory-separator components before building
  # skill_dest, since it's later passed to `rm -rf` — a skill name should
  # always be a single directory-name component, never `../` or an absolute
  # path.
  if [[ "${skill}" == *"/"* || "${skill}" == "." || "${skill}" == ".." ]]; then
    echo "error: invalid skill name '${skill}' (must be a single directory name, no path separators)" >&2
    return 1
  fi

  local skill_src="${REPO_ROOT}/${skill}"
  local skill_dest="${dest_root}/${skill}"
  local host_label
  host_label="$(host_label_for_dest "${dest_root}")"

  if [[ ! -f "${skill_src}/SKILL.md" ]]; then
    echo "error: skill not found at ${skill_src}/SKILL.md" >&2
    return 1
  fi

  mkdir -p "${dest_root}"
  if [[ -d "${skill_dest}" ]]; then
    if [[ -L "${skill_dest}" ]]; then
      echo "error: refusing to replace symlink at ${skill_dest}" >&2
      return 1
    fi
    echo "warning: replacing existing install at ${skill_dest}" >&2
  fi
  rm -rf "${skill_dest}"

  PYTHONDONTWRITEBYTECODE=1 python3 "${REPO_ROOT}/scripts/package_skill.py" \
    --skill "${skill}" \
    --dest "${skill_dest}" \
    --repo-root "${REPO_ROOT}" \
    --host "${host_label}"

  PYTHONDONTWRITEBYTECODE=1 python3 "${REPO_ROOT}/scripts/validate_references.py" \
    --installed-package "${skill_dest}"

  echo "Installed ${skill} → ${skill_dest}"
}

if [[ ${#SKILLS[@]} -eq 0 ]]; then
  shopt -s nullglob
  for skill_src in "${REPO_ROOT}"/*/SKILL.md; do
    SKILLS+=("$(basename "$(dirname "${skill_src}")")")
  done
  shopt -u nullglob
fi

while IFS= read -r dest_root; do
  for skill in "${SKILLS[@]}"; do
    install_skill "${skill}" "${dest_root}"
  done
done < <(dest_roots)

case "${AGENT}" in
cursor)
  echo "Restart Cursor to load the skill(s)."
  ;;
claude-user | claude-project)
  echo "Skill(s) available in your next Claude Code session."
  ;;
all)
  echo "Restart Cursor and start a new Claude Code session to load the skill(s)."
  ;;
esac
