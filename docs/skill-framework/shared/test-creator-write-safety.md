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
an unreadable Git state, an index-protected target whose worktree drift Git may
hide (`assume-unchanged` or `skip-worktree`), a symlinked target, or an empty
write plan is unsafe and fails closed.

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
`git status --porcelain=v1 --untracked-files=all` before the batch. Its Git
subprocesses remove repository-selection/index overrides and all `GIT_TRACE*`
settings, ignore user/system Git config, disable configured `core.fsmonitor`,
and set `GIT_OPTIONAL_LOCKS=0`. The pre-write check therefore cannot be
redirected to another repository, execute an ambient fsmonitor program, create
an ambient trace file, or refresh Git index metadata while it is deciding.
Dirty paths outside the planned set are reported and left exactly as found.
A planned path that is tracked-but-dirty, staged, renamed, an existing untracked
output, or index-protected with `assume-unchanged`/`skip-worktree` is a conflict;
the entire primary batch fails closed. Existing clean tracked files may be
modified only when explicitly in the plan. Hard-linked outputs are also
rejected because a normal path write could mutate another user-visible inode
outside the repository. Ignored or symlinked existing outputs and Git metadata
paths are unsafe as well.

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
filenames or Git text and are therefore untrusted render data: they **must not be
rendered verbatim** into Markdown. If a human-facing report summarizes guard
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
