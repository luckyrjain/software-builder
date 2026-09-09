# bug-diagnosis

Diagnoses one bug, test failure, or performance regression from repository evidence — not a live
production incident. It produces a report-only `BUG_DIAGNOSIS_REPORT.md` / `bug_diagnosis_report`; it
never edits source, tests, or configuration to fix the bug, and never commits, pushes, or opens a PR.

Use it to confirm a minimal repro from evidence, form candidate root causes and actively try to
falsify each one, and report the confirmed root cause with cited evidence and confidence.

A root cause is reported confirmed only when an active falsification attempt failed to disprove it and
the evidence for it is stronger than for any rejected alternative. An unfalsified hypothesis is
reported unresolved, never presented as confirmed.

## When to use

- A bug, test failure, or perf regression needs its root cause found before it can be fixed.
- A repro needs to be confirmed from evidence before hypotheses are formed.
- Candidate root causes need to be actively falsified rather than accepted on first plausibility.

Do not use it for a live production incident with an active time window (`incident-rca`), or to apply
an already-diagnosed fix (`loop-task-implementer`).

## Pipeline

`Inputs → Repro → Hypotheses → Report`

See [SKILL.md](SKILL.md) for the full contract and [examples.md](examples.md) for invocation patterns.
