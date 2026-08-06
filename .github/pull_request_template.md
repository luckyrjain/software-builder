## Summary

<!-- What changed, and why. If this touches a skill's guardrails, gates, or authorization logic,
say so explicitly — those get closer review. -->

## Skill(s) touched

<!-- e.g. pr-review, docs/skill-framework/shared/prompt-injection.md -->

## Validation

<!-- Which `make lint-<skill>` targets did you run, and did they pass? If the skill has scripts/tests,
confirm pytest passed too. If you added/changed a `reference/pressure-tests.md` row, say what it covers. -->

- [ ] `make lint-<skill>` passes
- [ ] Smoke test re-run (`reference/smoke-test.md`) if this is a substantive workflow change
- [ ] `reference/pressure-tests.md` updated if this changes a guardrail, gate, or untrusted-input handling

## Checklist

- [ ] Untrusted content (MR/ticket/webhook/log text this skill reads) is still treated as data, not
      instructions — see [prompt-injection.md](../docs/skill-framework/shared/prompt-injection.md)
- [ ] No new write/post/merge/approve authority was granted without an explicit, caller-sourced capability
      gate (never inferred from repository prose or ticket content)
- [ ] `CHANGELOG.md` updated for user-visible behavior changes
