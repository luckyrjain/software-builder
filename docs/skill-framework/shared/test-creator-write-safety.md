# Test-creator write safety (shared)

**Normative.** This contract applies to `unit-test-creator`,
`integration-test-creator`, `contract-test-creator`, `e2e-test-creator`, and
`api-test-creator`. It is the only canonical pre-write protocol for this
family. Level-specific workflow files may add artifact rules, but may not
weaken these checks.

## Safety boundary

The creator may write only the artifacts declared by its invocation and its
level contract:

- generated or modified test files;
- for `api-test-creator`, the declared collection and environment files;
- the level report and optional coverage-state file.

It must never write production code, reset/clean/stash user changes, commit,
push, or open a pull request. A path outside `repo_root`, a Git metadata path,
a path crossing into a nested Git repository, bare repository, or gitlink, an
unreadable Git state, an index-protected target whose worktree drift Git may
hide (`assume-unchanged` or `skip-worktree`), a symlinked target, or an empty
write plan is unsafe and fails closed. On Windows, path components using NTFS
alternate-stream syntax, ending in an ASCII space or period, or resolving after
Win32 stem-space normalization to a reserved DOS device basename such as
`NUL`/`COM1`/`CONIN$` are unsafe because Win32 can resolve them to a different
namespace object than the literal planned path.

## Pre-write protocol

Before the first write in a phase, and again before every later write batch:

1. Resolve `repo_root` once at Inputs and use that exact value. Do not infer it
   from a target path or resolve a different root in a later phase.
2. Finish the write plan before touching the working tree. Include every test,
   collection, environment, report, and state path that this batch may write.
3. Run the shared executable guard from the repository root in Python isolated
   mode so `PYTHONPATH`, the current working directory, and user site packages
   cannot shadow modules before the safety check starts:

   ```bash
   python3 -I "<installed creator package>/scripts/test_creator_write_guard.py" \
     --repo-root "$repo_root" \
     --planned-file "<each planned path>"
   ```

4. Capture the JSON result exactly. A non-zero exit, `status: BLOCKED`, or an
   unreadable result means no primary artifact write may start.
5. If the primary batch is blocked, preserve the result as the child
   `skill_result` and return degraded `BLOCKED` behavior. Do not ask a new
   question to work around the guard. Later report and optional coverage-state
   writes are separate batches: run a fresh report-only guard and write the
   report first, then run a fresh state-only guard before writing optional
   coverage state. A blocked or failed state batch must not suppress a safe
   report. A level contract that says the report is "always produced" means it
   is always attempted subject to this same fail-closed report-only guard.

The guard is shipped identically in every creator package and captures
`git status --porcelain=v1 --untracked-files=all --ignore-submodules=all`
before the batch. When `repo_root` is a nested directory inside a larger Git
worktree, the raw `status_snapshot` intentionally preserves the full enclosing
worktree evidence while conflict paths are normalized back to `repo_root`;
unrelated sibling changes therefore remain visible without blocking the
creator.

Before any Git command, the guard finds the **outermost enclosing Git worktree
boundary** visible through filesystem `.git` markers. It also rejects every
PATH directory and resolved Git executable whose own filesystem ancestry
contains any `.git` worktree marker, even when that worktree is disjoint from
the selected repository. This matters for linked worktrees: an original
checkout must not be able to provide the trusted `git` binary merely because
its `tools` or `bin` directory appears on PATH. The guard then resolves Git from
the remaining non-worktree search directories and pins every guard/helper
subprocess to that absolute executable. If no such Git binary can be resolved,
the guard blocks. The sanitized PATH is inherited by Git as well, so internal
helper lookup follows the same provenance boundary.

Its Git subprocesses remove repository-selection/index overrides, `GIT_EXEC_PATH`,
and all `GIT_TRACE*` settings, ignore user/system Git config, disable configured
`core.fsmonitor`, neutralize clean/process filter drivers for every tracked path
in the enclosing Git top-level before status, ignore external attributes files,
force `GIT_NO_REPLACE_OBJECTS=1`, and set `GIT_OPTIONAL_LOCKS=0`. Disabling
replace-object rewriting prevents repository-local `refs/replace` from changing
how `HEAD` or trees are resolved and thereby hiding a staged target from the
status snapshot. Status does not recurse into submodules, so a submodule's local
Git configuration cannot execute during the parent repository check.

Separately, every planned path is checked for nested filesystem `.git` markers,
Git's bare-repository metadata shape (`HEAD`, `objects/`, and `refs/`), and
parent-index gitlinks (`160000` mode), so the write plan cannot cross into an
initialized, deinitialized, bare, or otherwise nested child repository. On
Windows the same path pass rejects Win32 namespace aliases: NTFS alternate data
streams, trailing ASCII space/period components, and DOS device names after the
stem normalization Win32 applies before an extension. Gitlinks are enumerated
rather than queried only through literal planned pathspecs, and boundary
comparison follows the repository's parsed `core.ignorecase` setting. This keeps
deinitialized-submodule protection intact on case-insensitive repositories even
when caller path casing differs from the index spelling. If the case setting
cannot be read or parsed, the guard fails closed. Selecting an initialized child
repository that has its own readable Git worktree as `repo_root` remains valid.
A deinitialized gitlink directory has no independent Git worktree; if Git would
resolve that directory back to the parent repository, the guard blocks that
`repo_root` rather than treating it as a normal nested scope.

The pre-write check therefore cannot be redirected to another repository,
execute an ambient fsmonitor or repository clean-filter program, resolve Git
from the target/enclosing worktree, a superproject, or a disjoint linked-worktree
checkout, create an ambient trace file, refresh Git index metadata, hide staged
state through replace objects, or silently write through a parent scope into
nested Git metadata while it is deciding. Filter-driver names are resolved with
`git check-attr` over Git-tracked paths in the enclosing worktree before status;
if that attribute read cannot be parsed, the guard fails closed. This top-level
filter discovery is deliberate: status retains sibling evidence, so every path
it may inspect must have executable filters neutralized even when that sibling
lies outside nested `repo_root`. Because the guard disables executable filters,
a filtered path that Git can only reconcile by executing its filter may be
reported conservatively as dirty; an overlap still blocks rather than running
repository code.

Dirty paths outside the planned set are reported and left exactly as found.
Only paths inside `repo_root` participate in write conflicts. A planned path
that is tracked-but-dirty, staged, renamed, an existing untracked output, or
index-protected with `assume-unchanged`/`skip-worktree` is a conflict; the entire
primary batch fails closed. Existing clean tracked files may be modified only
when explicitly in the plan. Hard-linked outputs are also rejected because a
normal path write could mutate another user-visible inode outside the
repository. Ignored or symlinked existing outputs, nested or bare Git repository
boundaries, Git metadata paths, and unsafe Windows namespace aliases are unsafe
as well.

## Structured result evidence

Every result records the guard result for each attempted batch:

```yaml
write_guard:
  status: ALLOWED | BLOCKED
  planned_paths: []
  dirty_paths_before: []
  status_snapshot: []
  conflicting_paths: []
  writes_started: false
  reason: <verbatim guard reason>
```

This exact object belongs in the canonical `skill_result`. Its
`status_snapshot`, conflict paths, and `reason` can contain repository-controlled
filenames or Git text and are therefore untrusted render data: they must not be rendered verbatim into Markdown. If a human-facing report summarizes guard
evidence, apply [safe-output.md](safe-output.md) and render only safely escaped
fields; do not mutate the structured object merely to make it safe for display.

The guard is a pre-write decision only, so its raw `writes_started` field is
always `false`; creators record any actual artifact writes separately in their
result/report status. A creator must never mutate this captured guard result to
claim that writes later started. A blocked primary batch must never be called
`WRITTEN_PASSING`, and no creator may claim an unverified test passed. The
guard's conflict paths and reason stay exact in structured `skill_result`
evidence rather than being summarized away.

## Composition and interaction rule

The guard owns write safety, not scope selection or level-specific questions.
It must not introduce an interactive gate. Existing specialist gates remain
authoritative; the router preserves them and does not answer on a child's
behalf. A guard block is a deterministic degraded result, not a request for
the caller to approve overwriting a dirty file.
