# Task 6 — Make integration report

## Scope

Implemented only the Task 6 Make integration in `make/core.mk`:

- Added `install-module-design` and `install-codebase-architecture-review`.
- Added `install-claude-module-design` and `install-claude-codebase-architecture-review`.
- Added matching `.PHONY` declarations.
- Added `lint-module-design` and `lint-codebase-architecture-review`.
- Added the new lint targets to `lint-static` and `lint-framework`.
- Kept both out of `lint-suites` and made no changes to registry, routing, skills,
  tests, evals, generated files, or other source.

The skill-local lint targets check the 180-line `SKILL.md` cap, ambient invocation,
workflow frontmatter, required headings, required reference files, smoke-test
Invocation and pressure-test links, framework/safe-output/prompt-injection/
cross-skill-escalation links, and dangling Markdown links. The codebase architecture
review lint additionally checks its report format for prompt-injection and safe-output
links plus escape/fence/backtick/redaction language.

## Verification

### `make lint-module-design`

```text
lint-module-design: SKILL.md line count (<= 180)
  ok (103 lines)
lint-module-design: disable-model-invocation NOT set (ambiently invocable)
  ok
lint-module-design: required SKILL.md headings
lint-module-design: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)
  ok
lint-module-design: dangling markdown links
  ok
lint-module-design: required reference files
  ok (framework refs)
```

Exit code: `0`.

### `make lint-codebase-architecture-review`

```text
lint-codebase-architecture-review: SKILL.md line count (<= 180)
  ok (99 lines)
lint-codebase-architecture-review: disable-model-invocation NOT set (ambiently invocable)
  ok
lint-codebase-architecture-review: required SKILL.md headings
lint-codebase-architecture-review: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)
  ok
lint-codebase-architecture-review: dangling markdown links
  ok
lint-codebase-architecture-review: required reference files
  ok (framework refs)
```

Exit code: `0`.

### `make lint-framework`

```text
lint-module-design: SKILL.md line count (<= 180)
  ok (103 lines)
lint-module-design: disable-model-invocation NOT set (ambiently invocable)
  ok
lint-module-design: required SKILL.md headings
lint-module-design: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)
  ok
lint-module-design: dangling markdown links
  ok
lint-module-design: required reference files
  ok (framework refs)
lint-codebase-architecture-review: SKILL.md line count (<= 180)
  ok (99 lines)
lint-codebase-architecture-review: disable-model-invocation NOT set (ambiently invocable)
  ok
lint-codebase-architecture-review: required SKILL.md headings
lint-codebase-architecture-review: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)
  ok
lint-codebase-architecture-review: dangling markdown links
  ok
lint-codebase-architecture-review: required reference files
  ok (framework refs)
lint-framework: shared docs present
lint-framework: required sections
lint-framework: SETUP.md freshness tables
ok — SETUP.md freshness validated for /workspace/scratch/9733ba304959/software-builder-worktree
  ok
lint-framework: dangling markdown links
  ok
lint-framework: first-ingest untrusted-content wiring
lint-framework: PRD rendered-output safety wiring
lint-framework: all SETUP.md links ok
lint-framework: cross-agent discovery files (.cursor/rules + .kiro/steering)
  ok
lint-framework: metadata footer examples present
lint-framework: metadata footer validator
docs/skill-framework/shared/examples/review-metadata.example.yaml: ok
docs/skill-framework/shared/examples/assessment-metadata-rca.example.yaml: ok
docs/skill-framework/shared/examples/assessment-metadata-k8s.example.yaml: ok
pr-review/tests/fixtures/phase5-review-metadata.yaml: ok
lint-framework: source-tree reference validation (anchors + local links, cross-cutting docs)
/workspace/scratch/9733ba304959/software-builder-worktree/.superpowers/sdd/2026-08-31-codebase-architecture-foundation-restored/task-2-review.md: dangling anchor '../../../module-design/SKILL.md#L58-L66' in /workspace/scratch/9733ba304959/software-builder-worktree/module-design/SKILL.md
/workspace/scratch/9733ba304959/software-builder-worktree/.superpowers/sdd/2026-08-31-codebase-architecture-foundation-restored/task-2-review.md: dangling anchor '../../../CONTRIBUTING.md#L26-L30' in /workspace/scratch/9733ba304959/software-builder-worktree/CONTRIBUTING.md
/workspace/scratch/9733ba304959/software-builder-worktree/.superpowers/sdd/2026-08-31-codebase-architecture-foundation-restored/task-2-review.md: dangling anchor '../../../module-design/SKILL.md#L20-L24' in /workspace/scratch/9733ba304959/software-builder-worktree/module-design/SKILL.md
/workspace/scratch/9733ba304959/software-builder-worktree/.superpowers/sdd/2026-08-31-codebase-architecture-foundation-restored/task-2-review.md: dangling anchor '../../../module-design/reference/report-format.md#L6-L15' in /workspace/scratch/9733ba304959/software-builder-worktree/module-design/reference/report-format.md
/workspace/scratch/9733ba304959/software-builder-worktree/.superpowers/sdd/2026-08-31-codebase-architecture-foundation-restored/task-2-review.md: dangling anchor '../../../module-design/workflow/inputs.md#L13-L24' in /workspace/scratch/9733ba304959/software-builder-worktree/module-design/workflow/inputs.md
/workspace/scratch/9733ba304959/software-builder-worktree/.superpowers/sdd/2026-08-31-codebase-architecture-foundation-restored/task-2-review.md: dangling anchor '../../../module-design/workflow/design.md#L16-L19' in /workspace/scratch/9733ba304959/software-builder-worktree/module-design/workflow/design.md
/workspace/scratch/9733ba304959/software-builder-worktree/.superpowers/sdd/2026-08-31-codebase-architecture-foundation-restored/task-2-review.md: dangling anchor '../../../module-design/reference/phase-index.md#L1-L11' in /workspace/scratch/9733ba304959/software-builder-worktree/module-design/reference/phase-index.md
/workspace/scratch/9733ba304959/software-builder-worktree/.superpowers/sdd/2026-08-31-codebase-architecture-foundation-restored/task-2-review.md: dangling anchor '../../../module-design/reference/lazy-load-index.md#L1-L14' in /workspace/scratch/9733ba304959/software-builder-worktree/module-design/reference/lazy-load-index.md
/workspace/scratch/9733ba304959/software-builder-worktree/.superpowers/sdd/2026-08-31-codebase-architecture-foundation-restored/task-2-review.md: dangling anchor '../../../module-design/SKILL.md#L13-L15' in /workspace/scratch/9733ba304959/software-builder-worktree/module-design/SKILL.md
/workspace/scratch/9733ba304959/software-builder-worktree/.superpowers/sdd/2026-08-31-codebase-architecture-foundation-restored/task-2-review.md: dangling anchor '../../../module-design/SKILL.md#L40-L46' in /workspace/scratch/9733ba304959/software-builder-worktree/module-design/SKILL.md
/workspace/scratch/9733ba304959/software-builder-worktree/.superpowers/sdd/2026-08-31-codebase-architecture-foundation-restored/task-2-review.md: dangling anchor '../../../module-design/workflow/report.md#L13-L21' in /workspace/scratch/9733ba304959/software-builder-worktree/module-design/workflow/report.md
/workspace/scratch/9733ba304959/software-builder-worktree/.superpowers/sdd/2026-08-31-codebase-architecture-foundation-restored/task-2-review.md: dangling anchor '../../../module-design/reference/report-format.md#L17-L89' in /workspace/scratch/9733ba304959/software-builder-worktree/module-design/reference/report-format.md
/workspace/scratch/9733ba304959/software-builder-worktree/.superpowers/sdd/2026-08-31-codebase-architecture-foundation-restored/task-2-review.md: dangling anchor '../../../module-design/SKILL.md#L68-L76' in /workspace/scratch/9733ba304959/software-builder-worktree/module-design/SKILL.md
/workspace/scratch/9733ba304959/software-builder-worktree/.superpowers/sdd/2026-08-31-codebase-architecture-foundation-restored/task-2-review.md: dangling anchor '../../../module-design/SETUP.md#L30-L40' in /workspace/scratch/9733ba304959/software-builder-worktree/module-design/SETUP.md
/workspace/scratch/9733ba304959/software-builder-worktree/.superpowers/sdd/2026-08-31-codebase-architecture-foundation-restored/task-2-review.md: dangling anchor '../../../module-design/reference/smoke-test.md#L16-L34' in /workspace/scratch/9733ba304959/software-builder-worktree/module-design/reference/smoke-test.md
/workspace/scratch/9733ba304959/software-builder-worktree/.superpowers/sdd/2026-08-31-codebase-architecture-foundation-restored/task-2-review.md: dangling anchor '../../../module-design/reference/pressure-tests.md#L5-L30' in /workspace/scratch/9733ba304959/software-builder-worktree/module-design/reference/pressure-tests.md
/workspace/scratch/9733ba304959/software-builder-worktree/.superpowers/sdd/2026-08-31-codebase-architecture-foundation-restored/task-2-review.md: dangling anchor '../../../module-design/examples.md#L5-L32' in /workspace/scratch/9733ba304959/software-builder-worktree/module-design/examples.md
/workspace/scratch/9733ba304959/software-builder-worktree/.superpowers/sdd/2026-08-31-codebase-architecture-foundation-restored/task-2-review.md: dangling anchor '../../../module-design/SKILL.md#L13-L15' in /workspace/scratch/9733ba304959/software-builder-worktree/module-design/SKILL.md
/workspace/scratch/9733ba304959/software-builder-worktree/.superpowers/sdd/2026-08-31-codebase-architecture-foundation-restored/task-2-review.md: dangling anchor '../../../module-design/reference/report-format.md#L80-L89' in /workspace/scratch/9733ba304959/software-builder-worktree/module-design/reference/report-format.md
/workspace/scratch/9733ba304959/software-builder-worktree/codebase-architecture-review/reference/report-format.md: unclosed fenced code block (a ``` marker opens a fence that's never closed before EOF — check for a stray or unmatched ``` elsewhere in the file)
make: *** [make/core.mk:1871: lint-framework] Error 1
```

Exit code: `2`. These failures predate Task 6 and are outside the allowed edit
scope: the Task 2 review report contains line-number anchors that the source-tree
validator cannot resolve, and the codebase architecture report-format document has
an unmatched nested three-backtick fence.

### `make lint-static`

```text
ok: all 8 required platform files are present
error: codebase-architecture-review: SKILL.md's Framework section does not reference: skill_result, action_gates, blocked_conditions, runtime-contract.md
error: module-design: SKILL.md's Framework section does not reference: skill_result, action_gates, runtime-contract.md
error: Cursor skill surface drift: missing=['codebase-architecture-review', 'module-design'], extra=[]
error: Kiro skill surface drift: missing=['codebase-architecture-review', 'module-design'], extra=[]
make: *** [make/core.mk:360: validate-registry] Error 1
```

Exit code: `2`. These failures are pre-existing Task 5/current-branch state:
the new skills are registered but their generated framework/agent projections
were intentionally not part of the Task 6 scope.

### Install target dry-run

Command:

```text
make -n install-module-design install-codebase-architecture-review install-claude-module-design install-claude-codebase-architecture-review
```

Output:

```text
bash scripts/install.sh module-design
bash scripts/install.sh codebase-architecture-review
bash scripts/install.sh --agent claude-user module-design
bash scripts/install.sh --agent claude-user codebase-architecture-review
```

Exit code: `0`.

### Foundation regression test

Command: `python3 -m pytest -q scripts/tests/test_codebase_architecture_foundation.py`

```text
.........                                                                [100%]
9 passed in 0.63s
```

Exit code: `0`.

### Structural checks

`make -qp` listed all six requested targets, including their `.PHONY`
declarations. `git diff --check` passed with no output. The final diff contains
only `make/core.mk` plus this required Task 6 report.

## Concerns

- The two repository-wide lint commands remain blocked by the pre-existing
  registry/generated-projection and documentation-link/fence issues listed above.
- No unrelated files were changed to bypass those failures.

---

# Task 6 fix — round 1 report

## Scope

- Fixed `forbid_disable_model_invocation` so a forbidden frontmatter key makes
  the lint recipe fail instead of being masked by `|| true`.
- Added a CommonMark-aware balanced-fence check to
  `lint-codebase-architecture-review`, using
  `scripts.reference_utils.has_unclosed_fenced_code_block`.
- Corrected the report-format's outer example fence to four backticks, leaving
  its nested YAML fence at three backticks.

## Pass/fail coverage

- Ambient invocation: both real skills pass with no
  `disable-model-invocation` key; an isolated temporary `SKILL.md` containing
  the key fails the same Make helper.
- Fenced blocks: the corrected real report format passes the lint target; a
  temporary unclosed ````markdown` fence appended to that same source makes
  `lint-codebase-architecture-review` fail at the new check. The temporary
  fixture was removed before final verification.
- The independent prompt-injection, safe-output, escape/fence/backtick, and
  redaction-language checks remain unchanged and run before the new structural
  fence check.

## Verification

### Focused positive checks

Command:

```text
make lint-module-design
make lint-codebase-architecture-review
```

Output:

```text
lint-module-design: SKILL.md line count (<= 180)
  ok (103 lines)
lint-module-design: disable-model-invocation NOT set (ambiently invocable)
  ok
lint-module-design: required SKILL.md headings
lint-module-design: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)
  ok
lint-module-design: dangling markdown links
  ok
lint-module-design: required reference files
  ok (framework refs)
lint-codebase-architecture-review: SKILL.md line count (<= 180)
  ok (99 lines)
lint-codebase-architecture-review: disable-model-invocation NOT set (ambiently invocable)
  ok
lint-codebase-architecture-review: required SKILL.md headings
lint-codebase-architecture-review: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)
  ok
lint-codebase-architecture-review: dangling markdown links
  ok
lint-codebase-architecture-review: required reference files
lint-codebase-architecture-review: balanced report-format fenced code blocks
  ok (framework refs)
```

Exit code: `0`.

Command:

```text
python3 -m pytest -p no:cacheprovider scripts/tests/test_reference_utils.py scripts/tests/test_validate_references.py scripts/tests/test_codebase_architecture_foundation.py -q
```

Output:

```text
.....s...................................                                [100%]
40 passed, 1 skipped in 0.65s
```

Exit code: `0`.

### Focused negative checks

Command (the temporary directory contained only a `SKILL.md` with
`disable-model-invocation: true`):

```text
make -f make/core.mk --eval='lint-ambient-negative: ; $(call forbid_disable_model_invocation,/tmp/task-6-ambient.mG033m)' lint-ambient-negative
```

Output:

```text
error: /tmp/task-6-ambient.mG033m/SKILL.md must NOT set disable-model-invocation
make: *** [<builtin>: lint-ambient-negative] Error 1
ambient-invocation negative check: correctly failed
```

Expected command exit code: `2`.

Command (with one temporary unclosed ````markdown` opener appended to
`codebase-architecture-review/reference/report-format.md`, then removed):

```text
make lint-codebase-architecture-review
```

Output:

```text
lint-codebase-architecture-review: SKILL.md line count (<= 180)
  ok (99 lines)
lint-codebase-architecture-review: disable-model-invocation NOT set (ambiently invocable)
  ok
lint-codebase-architecture-review: required SKILL.md headings
lint-codebase-architecture-review: workflow frontmatter (workflow_version, phase, produces, consumes in each workflow/*.md)
  ok
lint-codebase-architecture-review: dangling markdown links
  ok
lint-codebase-architecture-review: required reference files
lint-codebase-architecture-review: balanced report-format fenced code blocks
error: codebase-architecture-review/reference/report-format.md: unclosed fenced code block
make: *** [make/core.mk:1799: lint-codebase-architecture-review] Error 1
report-format unclosed-fence negative check: correctly failed
```

Expected command exit code: `2`.

### Framework/static checks

Command:

```text
make lint-framework
```

Exit code: `2`.

The new codebase-architecture-review fence check passed. The command then
failed at the existing source-tree validator because
`task-2-review.md` contains line-range anchors (for example,
`../../../module-design/SKILL.md#L58-L66`) that are not valid Markdown
anchors. No unclosed-fence error is now reported for the architecture
report-format.

Command:

```text
make lint-static
```

Output:

```text
ok: all 8 required platform files are present
error: codebase-architecture-review: SKILL.md's Framework section does not reference: skill_result, action_gates, blocked_conditions, runtime-contract.md
error: module-design: SKILL.md's Framework section does not reference: skill_result, action_gates, runtime-contract.md
error: Cursor skill surface drift: missing=['codebase-architecture-review', 'module-design'], extra=[]
error: Kiro skill surface drift: missing=['codebase-architecture-review', 'module-design'], extra=[]
make: *** [make/core.mk:360: validate-registry] Error 1
```

Exit code: `2`. These registry/generated-surface failures predate this scoped
fix and occur before static lint reaches the Task 6 lint targets.

Command:

```text
git diff --check
```

Output: none.

Exit code: `0`.

## Concerns

- `make lint-framework` and `make lint-static` remain blocked by the unrelated,
  pre-existing failures recorded above.
