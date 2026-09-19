#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

run_python() {
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="${REPO_ROOT}" python3 "$@"
}

# Runs install_engine.py as a child this script can forward signals to, and returns its exit
# status. A plain foreground `run_python` can't be reached by `kill <this script's pid>` -- the
# most common way a supervisor stops it: bash dies at once, and the engine is orphaned to init
# and keeps running, holding the lock and a staging directory, with nothing left to roll it back.
# Backgrounding it and trapping TERM/INT lets the engine run its own SIGTERM cleanup (rollback,
# lock release, exit 130) before this script exits with that status. (An async child of a
# non-interactive shell has SIGINT ignored, so Ctrl-C is delivered as the TERM forwarded here.)
run_engine() {
  local engine_pid="" status=0 interrupted=false
  # Installed before the engine starts so a signal in the gap can't orphan it; the flag makes
  # a signal that beats the launch still stop the run once the engine is up.
  trap 'interrupted=true; if [[ -n "${engine_pid}" ]]; then kill -TERM "${engine_pid}" 2>/dev/null || true; fi' TERM INT
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="${REPO_ROOT}" python3 "$@" &
  engine_pid=$!
  if [[ "${interrupted}" == true ]]; then
    kill -TERM "${engine_pid}" 2>/dev/null || true
  fi
  # Poll for exit instead of blocking in `wait`: a trapped signal makes `wait` return at once
  # (128+n) while the engine is still cleaning up, and if the engine has already exited by then
  # bash may have collected its status in a way a second `wait` can't recover -- the run would
  # report the signal's 143 instead of the engine's own code (e.g. 130, which callers key on).
  # Nothing interrupts the single `wait` below: the engine is already gone, so it returns the
  # status bash kept for it immediately.
  while kill -0 "${engine_pid}" 2>/dev/null; do
    sleep 0.05
  done
  if wait "${engine_pid}"; then status=0; else status=$?; fi
  trap - TERM INT
  # A stop request must stop the run even when the engine happened to finish first.
  if [[ "${interrupted}" == true ]] && ((status == 0)); then
    status=130
  fi
  return "${status}"
}

# install_skill/uninstall_skill below delegate their whole mutating section -- locking,
# staging, backup, atomic replace, rollback-on-failure -- to scripts/install_engine.py's CLI,
# the single implementation of that state machine also used in-process by `sb install`/
# `sb uninstall` (cli/sb/__main__.py). install.sh no longer holds its own lock or performs its
# own staging; LOCK_WAIT_TIMEOUT_SECONDS/LOCK_STALE_SECONDS, if set in the environment, are
# read directly by install_engine.py, not by this script. See docs/adr/0007-shared-install-engine.md.

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
  --agent <cursor|claude-user|claude-project|all|agents>  Target host (default: all)
                                                    "agents" installs to the universal
                                                    Agent Skills target (.agents/skills)
                                                    instead of a host-specific directory
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

# The valid selectors come from scripts/registry/install_resolver.py's own routing table rather
# than a Bash `case` repeating it -- one list, so a selector added there is immediately accepted
# here and can never drift out of sync with what resolve-targets can actually resolve. Called
# only just before destination resolution, after the pure-Bash skill-name gate below, so a
# malformed skill name is still rejected without spawning a Python process.
validate_agent_selector() {
  local selectors selector
  if ! selectors="$(run_python "${REPO_ROOT}/scripts/install_support.py" list-selectors)"; then
    echo "${selectors}" >&2
    return 1
  fi
  while IFS= read -r selector; do
    if [[ "${AGENT}" == "${selector}" ]]; then
      return 0
    fi
  done <<< "${selectors}"
  echo "error: unknown --agent '${AGENT}' (expected $(printf '%s' "${selectors}" | tr '\n' '|'))" >&2
  return 1
}

# --target-dir <repo> → project-local skills dir(s).
# No --target-dir → global user install (~/.cursor/skills and/or ~/.claude/skills).
# Destination + host-label resolution is driven by agent-hosts.yaml via
# scripts/registry/install_resolver.py, not hard-coded here -- one call per install.sh
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

# Deliberate divergence from a pre-consolidation install.sh: uninstall no longer re-checks
# registry membership the way install does, so a since-deregistered skill can still be
# uninstalled -- ownership classification alone (inside install_engine.py) still bounds what
# gets touched. Documented on install_engine.uninstall_skill()'s own docstring; this was
# already sb install's behavior before this function started delegating to it.
uninstall_skill() {
  local skill="$1"
  local dest_root="$2"

  validate_skill_name_format "${skill}" || return 1

  local dry_run_flag=()
  [[ "${DRY_RUN}" == true ]] && dry_run_flag=(--dry-run)

  local status
  if run_engine "${REPO_ROOT}/scripts/install_engine.py" uninstall \
    "${skill}" "${dest_root}" ${dry_run_flag[@]+"${dry_run_flag[@]}"}; then
    status=0
  else
    status=$?
  fi
  if ((status == 130)); then
    exit 130
  fi
  ((status == 0))
}

install_skill() {
  local skill="$1"
  local dest_root="$2"
  local host_label="$3"

  validate_skill_name_format "${skill}" || return 1

  # Explicit `|| return 1` rather than relying on `set -e`: the install loop invokes this
  # function from an `if` so one failure no longer aborts the run, and errexit is disabled for
  # everything an `if` condition calls. Also runs _check_selector_coverage as a side effect
  # (see install_support.py's cmd_check) -- an unrelated whole-registry check, but this is
  # still the cheapest place to catch a drift there before spending time on install_engine.py.
  registry_check_skill "${skill}" || return 1

  local skill_dest="${dest_root}/${skill}"
  local dry_run_flag=()
  [[ "${DRY_RUN}" == true ]] && dry_run_flag=(--dry-run)

  # Locking, staging, backup, atomic replace and rollback-on-failure all live in
  # install_engine.py now -- the same state machine `sb install` calls in-process. A bare
  # (unguarded) call would trip `set -e` on a normal failed-install exit; wrapping it as an
  # `if` condition is what disables errexit for it, the same trick this script already uses
  # everywhere else it needs a command's exit status instead of an abort.
  local status
  if run_engine "${REPO_ROOT}/scripts/install_engine.py" install \
    "${skill}" "${dest_root}" "${host_label}" --repo-root "${REPO_ROOT}" ${dry_run_flag[@]+"${dry_run_flag[@]}"}; then
    status=0
  else
    status=$?
  fi
  if ((status == 130)); then
    exit 130
  fi
  if ((status != 0)); then
    return 1
  fi

  [[ "${DRY_RUN}" == true ]] && return 0

  # Shadow check (Candidate 8): a divergent copy at a higher-precedence discovery root for this
  # host means the host will actually load THAT copy, not the one just written here -- the
  # completion message must say so instead of unconditionally claiming success. This is a report,
  # not a refusal: the write above already succeeded and stands regardless of what this finds.
  # Still calls install_support.py directly rather than folding into install_engine.py: the
  # shadow *detection* is already the one shared scripts/registry/shadow_detector.py
  # implementation both this and `sb install`'s _warn_if_shadowed call into. The warning
  # *wording* is shared too now (shadow_detector.render_shadow_warning) -- install_support.py's
  # check-shadow prints the fully rendered line for SHADOWED/UNKNOWN_PRECEDENCE, so this just
  # relays it verbatim instead of reformatting it itself.
  local shadow_args=("check-shadow" "${host_label}" "${skill_dest}" "--home" "${HOME}")
  if [[ -n "${TARGET_DIR}" ]]; then
    shadow_args+=("--target-dir" "${TARGET_DIR}")
  fi
  # Guarded, not a bare assignment: this runs after the install already succeeded, so a failure
  # here (e.g. an unexpected exception inside detect_shadow) must not abort the script under
  # set -e and discard the "Installed" confirmation install_engine.py already printed -- it's
  # downgraded to an unknown-shadow-status warning instead.
  local shadow_output
  if ! shadow_output="$(run_python "${REPO_ROOT}/scripts/install_support.py" "${shadow_args[@]}")"; then
    echo "warning: could not determine shadow status for ${skill_dest}" >&2
    return 0
  fi
  # A dumb relay, not a second status check: cmd_check_shadow only ever prints a second line
  # when render_shadow_warning() actually produced one (SHADOWED/UNKNOWN_PRECEDENCE) -- bash
  # doesn't need its own copy of which statuses warn, just "is there a second line."
  if [[ "${shadow_output}" == *$'\n'* ]]; then
    echo "${shadow_output#*$'\n'}" >&2
  fi
}

# A run spans every (skill × destination) pair, and one failing pair used to abort the whole run
# under `set -e`: earlier pairs were already written, later ones never attempted, and nothing said
# which was which. Each pair now runs to completion and the run reports its own outcome. Per-skill
# atomicity is unchanged -- install_skill still stages, backs up and rolls back individually.
report_run_summary() {
  local verb="$1" succeeded="$2"
  shift 2
  local failed=("$@")
  if ((${#failed[@]} == 0)); then
    return 0
  fi
  echo "${verb}: ${succeeded}, failed: ${#failed[@]} (${failed[*]})" >&2
  return 1
}

if [[ "${MODE}" == "uninstall" ]]; then
  if [[ ${#SKILLS[@]} -eq 0 ]]; then
    echo "error: --uninstall requires a skill name" >&2
    exit 1
  fi
  for skill in "${SKILLS[@]}"; do
    validate_skill_name_format "${skill}" || exit 1
  done
  validate_agent_selector || exit 1
  # Command substitution (not < <(resolve_targets) process substitution): a process
  # substitution's internal failure only kills that subshell, not this script -- with
  # set -e/-o pipefail unable to see it, install.sh would silently do nothing and still exit
  # 0. Capturing into a variable first, exactly like the LIST_OUTPUT pattern below, makes a
  # resolve_targets failure abort this script instead of silently skipping every destination.
  if ! RESOLVED_TARGETS="$(resolve_targets)"; then
    echo "${RESOLVED_TARGETS}" >&2
    exit 1
  fi
  UNINSTALLED_COUNT=0
  FAILED_UNINSTALLS=()
  while IFS=$'\t' read -r dest_root host_label; do
    for skill in "${SKILLS[@]}"; do
      if uninstall_skill "${skill}" "${dest_root}"; then
        UNINSTALLED_COUNT=$((UNINSTALLED_COUNT + 1))
      else
        FAILED_UNINSTALLS+=("${skill} → ${dest_root}")
      fi
    done
  done <<< "${RESOLVED_TARGETS}"
  if report_run_summary "uninstalled" "${UNINSTALLED_COUNT}" "${FAILED_UNINSTALLS[@]+"${FAILED_UNINSTALLS[@]}"}"; then
    exit 0
  fi
  exit 1
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

validate_agent_selector || exit 1

# See the matching comment in the uninstall branch above for why this is a command
# substitution, not < <(resolve_targets).
if ! RESOLVED_TARGETS="$(resolve_targets)"; then
  echo "${RESOLVED_TARGETS}" >&2
  exit 1
fi
INSTALLED_COUNT=0
FAILED_INSTALLS=()
while IFS=$'\t' read -r dest_root host_label; do
  for skill in "${SKILLS[@]}"; do
    if install_skill "${skill}" "${dest_root}" "${host_label}"; then
      INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
    else
      FAILED_INSTALLS+=("${skill} → ${dest_root}")
    fi
  done
done <<< "${RESOLVED_TARGETS}"

if ! report_run_summary "installed" "${INSTALLED_COUNT}" "${FAILED_INSTALLS[@]+"${FAILED_INSTALLS[@]}"}"; then
  exit 1
fi

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
agents)
  echo "Skill(s) installed to the universal Agent Skills target. Restart your agent to load them."
  ;;
esac
