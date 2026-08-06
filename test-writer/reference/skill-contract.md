# Skill contract — non-negotiable

Load immediately after [SKILL.md](../SKILL.md). These rules override convenience shortcuts.

## Contract

1. **Scope** — classify and dispatch only. Never detect frameworks, generate tests, run anything, or
   write to the target repository directly — that is exclusively the dispatched skill's job.
2. **No guessed level** — ask per [workflow/classify.md](../workflow/classify.md) §3 whenever the request
   is genuinely ambiguous between two or more levels, or matches none. Never default to `unit` as a
   "safe" fallback — a wrong-level dispatch produces the wrong *kind* of test.
3. **Unchanged pass-through** — every field the caller supplied (`target`, `run_tests`,
   `max_files_per_run`, `role`, `journeys`, …) reaches the dispatched skill exactly as given. This router
   never translates, renames, defaults, or validates them itself.
4. **Verbatim relay** — the dispatched skill's own report is relayed as-is, never reformatted,
   summarized, or re-derived. Its own gates, findings, and next-step stay its own.
5. **Level already named — skip the router.** If the calling context already knows the level, invoke
   that `*-test-creator` skill directly; this skill's classification step is for when it isn't stated.

Routing: [skill-routing.md](../../docs/skill-framework/shared/skill-routing.md). Shared principles all
five dispatch targets honor:
[test-creation-principles.md](../../docs/skill-framework/shared/test-creation-principles.md).
