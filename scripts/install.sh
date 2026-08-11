#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

run_python() {
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="${REPO_ROOT}" python3 "$@"
}

AGENT="all"
TARGET_DIR=""
DRY_RUN=false
MODE="install"
SKILLS=()

usage() {
  cat <<'EOF'
Usage: install.sh [options] [skill ...]

Install portable skill packages to Cursor/Claude skill directories.

Options:
  --agent <cursor|claude-user|claude-project|all>  Target host (default: all)
  --target-dir <path>                              Project root for claude-project
  --dry-run                                        Print actions without writing
  --list                                           Print registry skill ids and exit
  --verify <path>                                  Verify an installed skill package
  --uninstall <skill>                              Remove installed skill from targets

With no skill arguments, installs all skills listed in skills.yaml.
Only skills.yaml-registered skills may be installed.
EOF
}

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
  --dry-run)
    DRY_RUN=true
    shift
    ;;
  --list)
    MODE="list"
    shift
    ;;
  --verify)
    MODE="verify"
    VERIFY_PATH="$2"
    shift 2
    ;;
  --uninstall)
    MODE="uninstall"
    SKILLS+=("$2")
    shift 2
    ;;
  -h | --help)
    usage
    exit 0
    ;;
  *)
    SKILLS+=("$1")
    shift
    ;;
  esac
done

case "${MODE}" in
list)
  run_python "${REPO_ROOT}/scripts/install_support.py" list --repo-root "${REPO_ROOT}"
  exit
  ;;
verify)
  run_python "${REPO_ROOT}/scripts/install_support.py" verify "${VERIFY_PATH}"
  exit
  ;;
esac

case "${AGENT}" in
cursor | cursor-project | claude-user | claude-project | all) ;;
*)
  echo "error: unknown --agent '${AGENT}' (expected cursor|cursor-project|claude-user|claude-project|all)" >&2
  exit 1
  ;;
esac

# --target-dir <repo> → project-local skills dir(s).
# No --target-dir → global user install (~/.cursor/skills and/or ~/.claude/skills).
dest_roots() {
  case "${AGENT}" in
  cursor)
    if [[ -n "${TARGET_DIR}" ]]; then
      echo "${TARGET_DIR}/.cursor/skills"
    else
      echo "${HOME}/.cursor/skills"
    fi
    ;;
  cursor-project)
    # Project-local Cursor discovery. Without --target-dir, same as global cursor.
    if [[ -n "${TARGET_DIR}" ]]; then
      echo "${TARGET_DIR}/.cursor/skills"
    else
      echo "${HOME}/.cursor/skills"
    fi
    ;;
  claude-user)
    echo "${HOME}/.claude/skills"
    ;;
  claude-project)
    if [[ -n "${TARGET_DIR}" ]]; then
      echo "${TARGET_DIR}/.claude/skills"
    else
      echo "${HOME}/.claude/skills"
    fi
    ;;
  all)
    if [[ -n "${TARGET_DIR}" ]]; then
      printf '%s\n%s\n' "${TARGET_DIR}/.cursor/skills" "${TARGET_DIR}/.claude/skills"
    else
      printf '%s\n%s\n' "${HOME}/.cursor/skills" "${HOME}/.claude/skills"
    fi
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
  */.cursor/skills)
    echo "cursor-project"
    ;;
  *)
    echo "claude-project"
    ;;
  esac
}

registry_check_skill() {
  local skill="$1"
  run_python "${REPO_ROOT}/scripts/install_support.py" check "${skill}" --repo-root "${REPO_ROOT}"
}

uninstall_skill() {
  local skill="$1"
  local dest_root="$2"
  local skill_dest="${dest_root}/${skill}"

  if [[ "${skill}" == *"/"* || "${skill}" == "." || "${skill}" == ".." ]]; then
    echo "error: invalid skill name '${skill}'" >&2
    return 1
  fi

  registry_check_skill "${skill}"

  if [[ ! -e "${skill_dest}" ]]; then
    echo "warning: not installed: ${skill_dest}" >&2
    return 0
  fi
  if [[ -L "${skill_dest}" ]]; then
    echo "error: refusing to remove symlink at ${skill_dest}" >&2
    return 1
  fi

  if [[ "${DRY_RUN}" == true ]]; then
    echo "dry-run: would remove ${skill_dest}"
    return 0
  fi

  rm -rf "${skill_dest}"
  echo "Uninstalled ${skill} from ${skill_dest}"
}

install_skill() {
  local skill="$1"
  local dest_root="$2"

  if [[ "${skill}" == *"/"* || "${skill}" == "." || "${skill}" == ".." ]]; then
    echo "error: invalid skill name '${skill}' (must be a single directory name, no path separators)" >&2
    return 1
  fi

  registry_check_skill "${skill}"

  local skill_src="${REPO_ROOT}/${skill}"
  local skill_dest="${dest_root}/${skill}"
  local host_label
  host_label="$(host_label_for_dest "${dest_root}")"

  if [[ ! -f "${skill_src}/SKILL.md" ]]; then
    echo "error: skill not found at ${skill_src}/SKILL.md" >&2
    return 1
  fi

  if [[ -e "${skill_dest}" && -L "${skill_dest}" ]]; then
    echo "error: refusing to replace symlink at ${skill_dest}" >&2
    return 1
  fi

  if [[ "${DRY_RUN}" == true ]]; then
    echo "dry-run: would install ${skill} → ${skill_dest} (host=${host_label})"
    return 0
  fi

  mkdir -p "${dest_root}"
  local backup_dir=""
  local stage_dir
  local install_succeeded=false
  stage_dir="$(mktemp -d "${dest_root}/.${skill}.staging.XXXXXX")"

  cleanup_failed_install() {
    rm -rf "${stage_dir}"
    if [[ -n "${backup_dir}" && -d "${backup_dir}/skill" && ! -e "${skill_dest}" ]]; then
      mv "${backup_dir}/skill" "${skill_dest}"
      echo "warning: restored previous install at ${skill_dest}" >&2
    fi
    rm -rf "${backup_dir}"
  }

  clear_install_trap() {
    trap - INT TERM
  }

  on_install_interrupt() {
    if [[ "${install_succeeded}" != true ]]; then
      cleanup_failed_install
    fi
    clear_install_trap
    exit 130
  }

  trap on_install_interrupt INT TERM

  if ! run_python "${REPO_ROOT}/scripts/package_skill.py" \
    --skill "${skill}" \
    --dest "${stage_dir}" \
    --repo-root "${REPO_ROOT}" \
    --host "${host_label}"; then
    cleanup_failed_install
    clear_install_trap
    return 1
  fi

  if ! run_python "${REPO_ROOT}/scripts/validate_references.py" \
    --installed-package "${stage_dir}"; then
    cleanup_failed_install
    clear_install_trap
    return 1
  fi

  if [[ -e "${skill_dest}" ]]; then
    if [[ -L "${skill_dest}" ]]; then
      rm -rf "${stage_dir}"
      clear_install_trap
      echo "error: refusing to replace symlink at ${skill_dest}" >&2
      return 1
    fi
    echo "warning: replacing existing install at ${skill_dest}" >&2
    backup_dir="$(mktemp -d)"
    mv "${skill_dest}" "${backup_dir}/skill"
  fi

  if ! mv "${stage_dir}" "${skill_dest}"; then
    cleanup_failed_install
    clear_install_trap
    return 1
  fi

  install_succeeded=true
  clear_install_trap
  rm -rf "${backup_dir}"
  echo "Installed ${skill} → ${skill_dest}"
}

if [[ "${MODE}" == "uninstall" ]]; then
  if [[ ${#SKILLS[@]} -eq 0 ]]; then
    echo "error: --uninstall requires a skill name" >&2
    exit 1
  fi
  while IFS= read -r dest_root; do
    for skill in "${SKILLS[@]}"; do
      uninstall_skill "${skill}" "${dest_root}"
    done
  done < <(dest_roots)
  exit 0
fi

if [[ ${#SKILLS[@]} -eq 0 ]]; then
  if ! LIST_OUTPUT="$(run_python "${REPO_ROOT}/scripts/install_support.py" list --repo-root "${REPO_ROOT}")"; then
    echo "${LIST_OUTPUT}" >&2
    exit 1
  fi
  if [[ -z "${LIST_OUTPUT}" ]]; then
    echo "error: skills.yaml registry returned no skills" >&2
    exit 1
  fi
  mapfile -t SKILLS <<< "${LIST_OUTPUT}"
fi

while IFS= read -r dest_root; do
  for skill in "${SKILLS[@]}"; do
    install_skill "${skill}" "${dest_root}"
  done
done < <(dest_roots)

if [[ "${DRY_RUN}" == true ]]; then
  exit 0
fi

case "${AGENT}" in
cursor | cursor-project)
  if [[ -n "${TARGET_DIR}" ]]; then
    echo "Restart Cursor in ${TARGET_DIR} to load the project skill(s)."
  else
    echo "Restart Cursor to load the skill(s)."
  fi
  ;;
claude-user | claude-project)
  echo "Skill(s) available in your next Claude Code session."
  ;;
all)
  if [[ -n "${TARGET_DIR}" ]]; then
    echo "Restart Cursor in ${TARGET_DIR} and start a new Claude Code session to load the project skill(s)."
  else
    echo "Restart Cursor and start a new Claude Code session to load the skill(s)."
  fi
  ;;
esac
