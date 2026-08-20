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
push, or open a pull request. A path outside `repo_root`, an unreadable Git
state, a symlinked target, or an empty write plan is unsafe and fails closed.

## Pre-write protocol

Before the first write in a phase, and again before every later write batch:

1. Resolve `repo_root` once at Inputs and use that exact value. Do not infer it
   from a target path or resolve a different root in a later phase.
2. Finish the write plan before touching the working tree. Include every test,
   collection, environment, report, and state path that this batch may write.
3. Run the shared executable guard from the repository root:

   ```bash
   python3 "<installed creator package>/scripts/test_creator_write_guard.py" \
     --repo-root "$repo_root" \
     --planned-file "<each planned path>"
   ```

4. Capture the JSON result exactly. A non-zero exit, `status: BLOCKED`, or an
   unreadable result means no primary artifact write may start.
5. If the primary batch is blocked, preserve the result as the child
   `skill_result` and return degraded `BLOCKED` behavior. Do not ask a new
   question to work around the guard. A report may be written only as a
   separate report-only batch after a fresh successful guard check proves that
   the report/state paths themselves are safe.

The guard is shipped identically in every creator package and captures
`git status --porcelain=v1 --untracked-files=all` before
the batch. Dirty paths outside the planned set are reported and left exactly
as found. A planned path that is tracked-but-dirty, staged, renamed, or an
existing untracked output is a conflict; the entire primary batch fails
closed. Existing clean tracked files may be modified only when explicitly in
the plan. Hard-linked outputs are also rejected because a normal path write
could mutate another user-visible inode outside the repository. Ignored or
symlinked existing outputs are unsafe as well.

## Report evidence

Every result records the guard result for each attempted batch:

```yaml
write_guard:
  status: ALLOWED | BLOCKED
  planned_paths: []
  dirty_paths_before: []
  status_snapshot: []
  conflicting_paths: []
  writes_started: true | false
  reason: <verbatim guard reason>
```

`writes_started` is `false` for a blocked primary batch. A creator must never
call a blocked run `WRITTEN_PASSING`, and must not claim an unverified test
passed. The guard's conflict paths and reason are preserved verbatim rather
than summarized away.

## Composition and interaction rule

The guard owns write safety, not scope selection or level-specific questions.
It must not introduce an interactive gate. Existing specialist gates remain
authoritative; the router preserves them and does not answer on a child's
behalf. A guard block is a deterministic degraded result, not a request for
the caller to approve overwriting a dirty file.
