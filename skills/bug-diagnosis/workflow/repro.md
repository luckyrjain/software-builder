---
workflow_version: 1.0
phase: repro
produces:
  - repro_status
  - repro_evidence
  - repro_command
consumes:
  - symptom
  - repro_hint
---

# Repro — confirm a minimal repro from evidence

Using `repro_hint` if supplied, or deriving one from the `symptom` and the relevant code/tests,
establish the smallest set of conditions that reproduces the symptom. Record `repro_status` as
`confirmed` only when you can cite the specific evidence that reproduces it (a failing test run, a
specific input/state combination traced through the code); record `unconfirmed` with the reason
otherwise.

Never report `confirmed` on the strength of "this looks like it would cause that" alone — that is
inference toward a hypothesis, not a confirmed repro. An unconfirmed repro does not block the
Hypotheses phase, but every hypothesis formed from it must be labeled accordingly.

## Populating `repro_command`

When `repro_status: confirmed` and the confirming evidence is a single, directly runnable
test-runner invocation (not a manual repro, an external-system state, or a multi-step sequence),
also populate `repro_command` with that exact command — this is what lets
`loop-task-implementer`'s Reviewer re-run the same repro at the task's base and head commits (the
`regression_gate`, see `docs/superpowers/specs/2026-09-29-b3-regression-gate-design.md`).

Before recording it, validate the command with `validate_repro_command` (the fixed,
delimiter-agnostic validator — see
[`reference/report-format.md`](../reference/report-format.md) and
`skills/bug-diagnosis/tests/test_repro_command_validation.py` for its exact behavior and full
regression suite). Only `pytest`, `python3 -m pytest`, `make <target>`, `npm test`, and
`npm run <script>` invocations validate, and only when no argument anywhere in the command contains
an absolute-path marker or a `..` traversal segment — the validator rejects the whole command
(returns `None`) rather than trying to sanitize it.

- Validator accepts the command unchanged → record it verbatim in `repro_command`.
- Validator rejects it, or the repro isn't expressible as a single command at all → `repro_command:
  null`, and `repro_evidence` states why (unchanged fallback; this is the expected, common case, not
  an error).

Never hand-construct a "cleaned up" version of a rejected command to make it pass — a rejection means
the repro isn't safely automatable as given, not that it needs reformatting.
