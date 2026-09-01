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
# Destination + host-label resolution is driven by agent-hosts.yaml via
# scripts/registry/legacy_install_resolver.py, not hard-coded here -- one call per install.sh
# invocation (not per skill/destination) prints "<dest_root>\t<host_label>" per line.
resolve_targets() {
  local args=("resolve-targets" "${AGENT}" "--home" "${HOME}")
  if [[ -n "${TARGET_DIR}" ]]; then
    args+=("--target-dir" "${TARGET_DIR}")
  fi
  run_python "${REPO_ROOT}/scripts/install_support.py" "${args[@]}"
}

registry_check_skill() {
  local skill="$1"
  run_python "${REPO_ROOT}/scripts/install_support.py" check "${skill}" --repo-root "${REPO_ROOT}"
}

# Pure-Bash, no-subprocess format check, callable before anything that shells out to Python
# (registry_check_skill, resolve_targets) so a malformed skill name is rejected as cheaply and
# early as possible -- not just as defense in depth inside install_skill/uninstall_skill below,
# but as the actual first gate the SKILLS array goes through, before destination resolution.
validate_skill_name_format() {
  local skill="$1"
  if [[ "${skill}" == *"/"* || "${skill}" == "." || "${skill}" == ".." ]]; then
    echo "error: invalid skill name '${skill}' (must be a single directory name, no path separators)" >&2
    return 1
  fi
  return 0
}

# Ownership classification (Candidate 6): only a directory this repository itself installed --
# proven by a valid .software-builder-manifest.json naming the same skill -- is safe to replace or
# remove. ABSENT/SOFTWARE_BUILDER_OWNED/UNOWNED/CORRUPT_OWNERSHIP/SYMLINK; see
# scripts/reference_utils.py's classify_install_destination for the full state definitions.
classify_destination() {
  run_python "${REPO_ROOT}/scripts/install_support.py" classify-destination "$1" "$2"
}

uninstall_skill() {
  local skill="$1"
  local dest_root="$2"
  local skill_dest="${dest_root}/${skill}"

  validate_skill_name_format "${skill}" || return 1

  registry_check_skill "${skill}"

  local ownership
  ownership="$(classify_destination "${skill_dest}" "${skill}")"
  case "${ownership}" in
  ABSENT)
    echo "warning: not installed: ${skill_dest}" >&2
    return 0
    ;;
  SYMLINK)
    echo "error: refusing to remove symlink at ${skill_dest}" >&2
    return 1
    ;;
  UNOWNED)
    echo "error: refusing to remove unowned directory at ${skill_dest} (not installed by software-builder)" >&2
    return 1
    ;;
  CORRUPT_OWNERSHIP)
    echo "error: refusing to remove ${skill_dest}: install manifest is missing, unreadable, or names a different skill" >&2
    return 1
    ;;
  esac

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
  local host_label="$3"

  validate_skill_name_format "${skill}" || return 1

  registry_check_skill "${skill}"

  local skill_src="${REPO_ROOT}/${skill}"
  local skill_dest="${dest_root}/${skill}"

  if [[ ! -f "${skill_src}/SKILL.md" ]]; then
    echo "error: skill not found at ${skill_src}/SKILL.md" >&2
    return 1
  fi

  # Early ownership check: fail fast before staging work (package_skill.py,
  # validate_references.py) starts, and gives --dry-run an accurate preview. Re-checked fresh
  # immediately before the actual replace below, since staging takes real time and this is a
  # check-then-act sequence -- mirrors this function's pre-existing early/late symlink
  # double-check pattern.
  local ownership
  ownership="$(classify_destination "${skill_dest}" "${skill}")"
  case "${ownership}" in
  SYMLINK)
    echo "error: refusing to replace symlink at ${skill_dest}" >&2
    return 1
    ;;
  UNOWNED)
    echo "error: refusing to replace unowned directory at ${skill_dest} (not installed by software-builder)" >&2
    return 1
    ;;
  CORRUPT_OWNERSHIP)
    echo "error: refusing to replace ${skill_dest}: install manifest is missing, unreadable, or names a different skill" >&2
    return 1
    ;;
  esac

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

  ownership="$(classify_destination "${skill_dest}" "${skill}")"
  case "${ownership}" in
  SYMLINK)
    rm -rf "${stage_dir}"
    clear_install_trap
    echo "error: refusing to replace symlink at ${skill_dest}" >&2
    return 1
    ;;
  UNOWNED)
    rm -rf "${stage_dir}"
    clear_install_trap
    echo "error: refusing to replace unowned directory at ${skill_dest} (not installed by software-builder)" >&2
    return 1
    ;;
  CORRUPT_OWNERSHIP)
    rm -rf "${stage_dir}"
    clear_install_trap
    echo "error: refusing to replace ${skill_dest}: install manifest is missing, unreadable, or names a different skill" >&2
    return 1
    ;;
  SOFTWARE_BUILDER_OWNED)
    echo "warning: replacing existing install at ${skill_dest}" >&2
    backup_dir="$(mktemp -d)"
    mv "${skill_dest}" "${backup_dir}/skill"
    ;;
  esac

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
  for skill in "${SKILLS[@]}"; do
    validate_skill_name_format "${skill}" || exit 1
  done
  # Command substitution (not < <(resolve_targets) process substitution): a process
  # substitution's internal failure only kills that subshell, not this script -- with
  # set -e/-o pipefail unable to see it, install.sh would silently do nothing and still exit
  # 0. Capturing into a variable first, exactly like the LIST_OUTPUT pattern below, makes a
  # resolve_targets failure abort this script instead of silently skipping every destination.
  if ! RESOLVED_TARGETS="$(resolve_targets)"; then
    echo "${RESOLVED_TARGETS}" >&2
    exit 1
  fi
  while IFS=$'\t' read -r dest_root host_label; do
    for skill in "${SKILLS[@]}"; do
      uninstall_skill "${skill}" "${dest_root}"
    done
  done <<< "${RESOLVED_TARGETS}"
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
  SKILLS=()
  while IFS= read -r line; do
    SKILLS+=("${line}")
  done <<< "${LIST_OUTPUT}"
fi

for skill in "${SKILLS[@]}"; do
  validate_skill_name_format "${skill}" || exit 1
done

# See the matching comment in the uninstall branch above for why this is a command
# substitution, not < <(resolve_targets).
if ! RESOLVED_TARGETS="$(resolve_targets)"; then
  echo "${RESOLVED_TARGETS}" >&2
  exit 1
fi
while IFS=$'\t' read -r dest_root host_label; do
  for skill in "${SKILLS[@]}"; do
    install_skill "${skill}" "${dest_root}" "${host_label}"
  done
done <<< "${RESOLVED_TARGETS}"

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
