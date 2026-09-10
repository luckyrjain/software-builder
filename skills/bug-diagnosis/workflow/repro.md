---
workflow_version: 1.0
phase: repro
produces:
  - repro_status
  - repro_evidence
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
