# RELEASE_READINESS_REPORT.md format

**Normative.** The exact structure [workflow/run-check.md](../workflow/run-check.md) § 5 must produce.

## Structure (order fixed)

```markdown
# Release readiness — <release name/date>

**Verdict: <READY | CONDITIONAL | NOT_READY | UNKNOWN>**

<When CONDITIONAL or UNKNOWN, one line naming which contributing condition(s) set the verdict — never
just the bare state.>
> e.g. `CONDITIONAL — payments-api flagged with an incident signal; see Per-service incident signal below.`
> e.g. `UNKNOWN — 1 manifest entry's since could not be resolved; see Notes.`

## MRs reviewed

| Repo | MR | Severity summary | pr-review posting mode |
|------|----|--------------------|--------------------------|
| <repo> | !<iid> | <N Critical, N High, N Medium, N Low — or 📋 Retrospective observation, per pr-review's retrospective matrix> | <mode pr-review's own Phase 0 detected — full \| summary-only \| general-only \| chat-only — never posted regardless, per gate-policy.md> |

<Repos with zero MRs since `since` still get a row: "No MRs since `<since>`".>
<A repo whose `since` didn't resolve gets a row: "Unresolved — `since` could not be resolved" (see Notes).>

## Per-service rightsizing

| Service | k8s verdict | Notes |
|---------|-------------|-------|
| <service> | <k8s-overprovisioning-datadog's own verdict, unmodified, including `insufficient_metrics`/`ambiguous_unresolved` recorded honestly as such — never upgraded to READY or treated as BLOCKED> | <one-line pointer to the full k8s report if BLOCKED, insufficient_metrics, or ambiguous_unresolved> |

## Per-service incident signal

| Service | Signal | Window | Notes |
|---------|--------|--------|-------|
| <service> | Clear \| Flagged | `<from_time>`–`<to_time>` UTC | <error/infra signal counts if flagged; "Run incident-rca directly on `{service}` `{window}` for full investigation" if flagged> |

## Notes

<Any MR-range-resolver fallback used (e.g. GitLab MCP didn't support a merge-date filter, client-side
filtering was used instead, pagination spanned N pages); any manifest entry whose `since` didn't resolve;
any `release_ref` pin recorded per repo (`caller-supplied` git SHA or image digest) and, for git SHAs,
whether `target_branch` HEAD matched the pin; any k8s `insufficient_metrics`/`ambiguous_unresolved` outcome and what tag strategies were attempted; any incident-rca escalation
per gate-policy.md § Escalation, not override.>
```

## Rules

- **Every `release_manifest` entry appears somewhere in the report** — a clear/uneventful entry still
  gets a row in each relevant section; never silently dropped for having nothing to report, and an
  unresolved `since` or an `insufficient_metrics`/`ambiguous_unresolved` k8s outcome is recorded honestly, not silently excluded.
- **k8s and incident-rca verdicts are surfaced as-is** — this skill never re-labels a k8s READY/BLOCKED
  recommendation or invents its own "risky" threshold on top of it, and never re-scores an incident
  signal beyond Clear/Flagged with the raw counts from incident-rca's own partial report.
- **The MRs-reviewed table is a severity summary, not the full pr-review render** — link to or note where
  the full chat-only review output can be found if the caller wants it re-run, don't duplicate the whole
  thing here.
- **Overall verdict derivation is fixed, four states, precedence `NOT_READY` > `UNKNOWN` > `CONDITIONAL`
  > `READY`** (per [workflow/run-check.md](../workflow/run-check.md) § 5):
  - `NOT_READY` — a **proven** blocker: any MR has a Critical/High finding, or any service's k8s verdict
    is `BLOCKED`.
  - `UNKNOWN` — an **evidence gap**, not a proven blocker and not verified-safe either: a manifest
    entry's `since` didn't resolve, a service's k8s verdict is `insufficient_metrics` or
    `ambiguous_unresolved`, or a manifest entry's `release_ref` git SHA does not match `target_branch`
    HEAD. Never folded into `NOT_READY` (that would fabricate a finding no check actually made) or into
    `READY` (that would hide a real gap).
  - `CONDITIONAL` — a flagged incident signal with no proven blocker or evidence gap otherwise present.
  - `READY` — none of the above.
- **Evidence gaps and proven blockers are reported as different states, not merged.** `insufficient_metrics`,
  `ambiguous_unresolved`, and an unresolved `since` were previously collapsed into the same `Not ready` bucket as a Critical
  finding or a `BLOCKED` k8s verdict — a reader could not tell "we found a real problem" from "we
  couldn't check." `UNKNOWN` exists specifically so the report says which one happened.
- **A flagged incident signal is a signal worth a human look, not a confirmed release-caused problem** —
  see [gate-policy.md § incident-rca](gate-policy.md#incident-rca)'s disclosed Phase-1-only limitation;
  the report's follow-up pointer exists so a human can make the correlation call this skill doesn't
  attempt. This is exactly why a flagged signal alone produces `CONDITIONAL`, not `NOT_READY` — treating
  unconfirmed chronic noise as a hard release blocker would produce false blockers on every release with
  any ambient incident activity, training readers to ignore the verdict.
