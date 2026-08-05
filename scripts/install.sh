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

install_skill() {
  local skill="$1"
  local dest_root="$2"
  local skill_src="${REPO_ROOT}/${skill}"
  local skill_dest="${dest_root}/${skill}"

  if [[ ! -f "${skill_src}/SKILL.md" ]]; then
    echo "error: skill not found at ${skill_src}/SKILL.md" >&2
    return 1
  fi

  mkdir -p "${dest_root}"
  if [[ -d "${skill_dest}" ]]; then
    echo "warning: replacing existing install at ${skill_dest}" >&2
  fi
  rm -rf "${skill_dest}"
  cp -r "${skill_src}" "${skill_dest}"
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
