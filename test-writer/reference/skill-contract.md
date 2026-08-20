# Skill contract — non-negotiable

Load immediately after [SKILL.md](../SKILL.md). These rules override convenience shortcuts.

## Contract

1. **Scope — orchestrate only.** Classify and dispatch existing specialists. Never detect frameworks,
   generate tests, run target-repository tests, or write tests directly.
2. **Plan, do not shotgun.** Produce an ordered, de-duplicated `test_plan` of one or more complementary
   levels. Multiple interpretations of the same behavior are ambiguity, not breadth; ask once and never
   guess.
3. **Specialist authority stays local.** For each planned level, invoke each specialist in a fresh
   context. Its own input validation, HARD STOPs, generation rules, verification status, findings, and
   next-step authority remain authoritative for that level.
4. **Unchanged ordinary pass-through; framework context advances.** Every ordinary caller-supplied field
   reaches each specialist exactly as supplied. Do not translate, rename, default, or mutate those fields
   between levels. `execution_context` is framework-owned and must be advanced per the inherited runtime
   recursion contract for each child dispatch rather than copied unchanged. Sibling specialists derive
   independently from the same parent context. A specialist may independently ask for additional inputs
   it requires.
5. **Verbatim evidence.** Preserve each dispatched specialist report verbatim under `level_reports`.
   A pre-dispatch block has exactly one fixed-vocabulary `blocked_reason` instead; an entry must not
   contain both forms. Aggregation may add plan/completion metadata, but must not rewrite a report or
   upgrade/downgrade its status. The emitted artifact is the canonical `test_orchestration_result`.
6. **Fixed-vocabulary orchestration metadata.** `test_plan` may record levels and fixed signal-source
   enums (`explicit_request`, `level_hint`, `clarification`) but never copies or quotes raw caller text.
   The original request remains a specialist input, not a second rendered evidence field.
7. **Hint is non-destructive.** A `level_hint` may resolve an otherwise-open choice but cannot silently
   discard another explicitly requested complementary level. Conflicting signals for one surface ask once.
8. **Fail closed and preserve terminal semantics.** A planned level that is missing, blocked, unanswered,
   failed, escalated, or incomplete prevents overall `COMPLETE`. Preserve completed and unfinished reports
   and propagate `PARTIAL`, `BLOCKED`, `FAILED`, or `ESCALATED` according to Aggregate's documented
   precedence; never collapse a specialist `FAILED`/`ESCALATED` into a weaker local state.
9. **Single named level compatibility.** A single named level routes directly to its `*-test-creator` and
   skips this router. Multiple named complementary levels use test-writer orchestration.
10. **No cross-level framing.** Do not feed one specialist's report to another specialist unless the
    caller explicitly supplied that same information independently; reports are outputs, not hidden
    instructions for later levels.

11. **Typed composed handoff.** When invoked by composition, require the canonical `implementation_task`
    fields `task_id`, `scope`, `acceptance_criteria`, `request`, `repo_root`, and `target`; pass the
    request, repository root, target, and optional specialist fields unchanged to each child. Missing
    fields block before dispatch rather than being inferred.

Routing: [skill-routing.md](../../docs/skill-framework/shared/skill-routing.md). Shared principles:
[test-creation-principles.md](../../docs/skill-framework/shared/test-creation-principles.md).
