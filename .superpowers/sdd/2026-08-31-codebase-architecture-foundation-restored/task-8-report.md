# Task 8 — Generation projections report

> **Final status (branch as submitted in PR #201):** the blockers recorded below were intermediate.
> Later tasks added the missing Framework references, registry rows, generated adapters, and Make
> targets. At the PR head `make generate-check`, `make validate-registry`, `make validate-evals`,
> `make lint-static`, and the full `scripts/tests` suite all pass. Read the command output below as a
> record of the state at the time this task ran, not of the branch.

## Scope

Ran the canonical generation entry points from the current Task 7 branch state.
Generation is blocked before writing because the two new skill sources fail the
existing Framework-reference validation. Per Task 8 scope, I did not modify
canonical registry/routing data, skill sources, Make targets, eval fixtures, or
any unrelated source, and I did not hand-edit generated files.

Added one focused foundation generation assertion in
`scripts/tests/test_codebase_architecture_foundation.py`. It verifies the
in-memory canonical generator projections for both skills on Cursor, Kiro,
catalogue/composition, and docs surfaces, plus the deterministic generic bundle
contents for both `SKILL.md` files and the shared
`codebase-design-principles.md` doctrine.

No generated files were written: `make generate` never passes validation and the
currently checked-in Cursor and Kiro adapters for these two skills remain absent.

## Exact command results

### `make generate`

Exit code: `2`.

```text
error: codebase-architecture-review: SKILL.md's Framework section does not reference: skill_result, action_gates, blocked_conditions, runtime-contract.md
error: module-design: SKILL.md's Framework section does not reference: skill_result, action_gates, runtime-contract.md
make: *** [make/core.mk:406: generate] Error 1
```

### `make generate-check`

Exit code: `2`.

```text
error: codebase-architecture-review: SKILL.md's Framework section does not reference: skill_result, action_gates, blocked_conditions, runtime-contract.md
error: module-design: SKILL.md's Framework section does not reference: skill_result, action_gates, runtime-contract.md
make: *** [make/core.mk:409: generate-check] Error 1
```

Both commands fail in the pre-write validation phase. This is a repository source
blocker, not an environment failure: the missing references must be added to the
two canonical `SKILL.md` Framework sections by the task authorized to edit skill
sources, then Task 8 generation can be rerun.

### Generic package check

Command:

```text
python3 -m scripts.registry package-generic --output /tmp/.../generic-skills.tar.gz
tar -tzf /tmp/.../generic-skills.tar.gz | rg '(^|/)(module-design|codebase-architecture-review)/(SKILL\\.md|README\\.md)$|docs/skill-framework/shared/codebase-design-principles\\.md'
```

Exit code: `0`.

```text
ok: wrote deterministic generic package to <tmpdir>/generic-skills.tar.gz
software-builder/codebase-architecture-review/README.md
software-builder/codebase-architecture-review/SKILL.md
software-builder/docs/skill-framework/shared/codebase-design-principles.md
software-builder/module-design/README.md
software-builder/module-design/SKILL.md
```

### Registry discovery check

Command:

```text
python3 -m scripts.registry list | rg '^(module-design|codebase-architecture-review)\\b'
```

Exit code: `0`.

```text
codebase-architecture-review | 1.0.0 | leaf | architecture | ambient | read-only
module-design | 1.0.0 | leaf | architecture | ambient | read-only
```

`python3 -m scripts.registry explain` for both skills also exited `0` and reported
all six supported hosts: `chatgpt, claude, codex, cursor, generic, kiro`.

### Generated-projection inspection

Calling the canonical generator's non-writing `_collect_outputs` produced all
required projections in memory:

- Cursor: `.cursor/rules/module-design.mdc` and
  `.cursor/rules/codebase-architecture-review.mdc`.
- Kiro: `.kiro/steering/module-design.md` and
  `.kiro/steering/codebase-architecture-review.md`.
- Catalogue/composition: `generated/catalogue/compatibility-matrix.md`,
  `composition-deps.mmd`, and `composition-runtime.mmd`.
- Documentation: `docs/README.md` and `docs/REPOSITORY.md`.

Each required projection contains both skill identifiers where its aggregate
format permits it. Each per-skill Cursor/Kiro adapter contains its own skill
identifier and the generated-file marker. The shared doctrine is bundled by the
generic package; it is not a string rendered into the per-skill adapters.

The checked-in adapter files are still absent because generation is blocked:

```text
MISSING .cursor/rules/module-design.mdc
MISSING .cursor/rules/codebase-architecture-review.mdc
MISSING .kiro/steering/module-design.md
MISSING .kiro/steering/codebase-architecture-review.md
```

### Focused foundation tests

Command:

```text
python3 -m pytest -q scripts/tests/test_codebase_architecture_foundation.py
```

Exit code: `0`.

```text
...........                                                              [100%]
11 passed in 6.92s
```

### Diff integrity

Command: `git diff --check`

Exit code: `0`.

Exact output: none.

## Concerns

- Task 8 cannot generate or commit the requested derived projections until the
  two Framework-reference source validation errors are resolved by an authorized
  upstream task.
- The focused assertion confirms the canonical generator and generic package
  would project the required surfaces after that repair, without bypassing the
  canonical `make generate` gate.

## Task 8 unblock report

Added the existing architecture-review Framework contract sentence to
`module-design/SKILL.md` and `codebase-architecture-review/SKILL.md`, explicitly
covering `skill_result`, `action_gates`, `blocked_conditions`, and
`runtime-contract.md`. Both skills remain ambient, read-only, report-only, and
within the 180-line cap.

Canonical generation then succeeded and produced 94 files with no stale
adapters. `make generate-check` confirmed the projections are current. The
focused foundation tests, registry validation, both skill-specific lint targets,
and `git diff --check` all passed. Generated Cursor/Kiro adapters and the
registry, catalogue, composition, compatibility, documentation, and roster
projections were committed with the two source corrections.
