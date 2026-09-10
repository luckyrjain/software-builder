# issue-triage

Classifies raw incoming issues, bugs, or feature requests from repository and caller-supplied evidence
— category, severity, duplicate-of, and a recommended owning skill or squad. It produces a report-only
`ISSUE_TRIAGE_REPORT.md` / `issue_triage_report`; it never writes a label, state transition, or
tracker field, commits, pushes, or opens a PR.

Use it to classify one or more raw issues before anyone acts on them, check a duplicate claim against
real evidence (matching symptom, stack trace, or repro) rather than proximity, flag ownership as
unclear when no evidence supports a guess, and catch an incident-shaped issue before it's treated as
routine backlog.

A `duplicate_of` claim is recorded only when real evidence supports it. Time proximity or vague
topical similarity alone never earns a duplicate claim.

## When to use

- One or more raw, unscoped issues need category/severity/duplicate/owner classification.
- Recommend routing before anyone acts, without writing a label.
- Group possible duplicates and flag unclear ownership.

Do not use it for a live paging-webhook incident with no human turn available
(`incident-triage-agent`), or an already-scoped tracker query to work through (`backlog-runner`).

## Pipeline

`Inputs → Classify → Report`

See [SKILL.md](SKILL.md) for the full contract and [examples.md](examples.md) for invocation patterns.
