# RELEASE_READINESS_REPORT.md format

**Normative.** The exact structure [workflow/run-check.md](../workflow/run-check.md) § 5 must produce.

## Structure (order fixed)

```markdown
# Release readiness — <release name/date>

**Verdict: <Ready | Not ready>**

## MRs reviewed

| Repo | MR | Severity summary | pr-review posting mode |
|------|----|--------------------|--------------------------|
| <repo> | !<iid> | <N Critical, N High, N Medium, N Low> | <mode pr-review's own Phase 0 detected — full \| summary-only \| general-only \| chat-only — never posted regardless, per gate-policy.md> |

<Repos with zero MRs since `since` still get a row: "No MRs since `<since>`".>
<A repo whose `since` didn't resolve gets a row: "Unresolved — `since` could not be resolved" (see Notes).>

## Per-service rightsizing

| Service | k8s verdict | Notes |
|---------|-------------|-------|
| <service> | <k8s-overprovisioning-datadog's own verdict, unmodified, including `insufficient_metrics` recorded honestly as such — never upgraded to READY or treated as BLOCKED> | <one-line pointer to the full k8s report if BLOCKED or insufficient_metrics> |

## Per-service incident signal

| Service | Signal | Window | Notes |
|---------|--------|--------|-------|
| <service> | Clear \| Flagged | `<from_time>`–`<to_time>` UTC | <error/infra signal counts if flagged; "Run incident-rca directly on `{service}` `{window}` for full investigation" if flagged> |

## Notes

<Any MR-range-resolver fallback used (e.g. GitLab MCP didn't support a merge-date filter, client-side
filtering was used instead, pagination spanned N pages); any manifest entry whose `since` didn't resolve;
any k8s `insufficient_metrics` outcome and what tag strategies were attempted; any incident-rca escalation
per gate-policy.md § Escalation, not override.>
```

## Rules

- **Every `release_manifest` entry appears somewhere in the report** — a clear/uneventful entry still
  gets a row in each relevant section; never silently dropped for having nothing to report, and an
  unresolved `since` or an `insufficient_metrics` k8s outcome is recorded honestly, not silently excluded.
- **k8s and incident-rca verdicts are surfaced as-is** — this skill never re-labels a k8s READY/BLOCKED
  recommendation or invents its own "risky" threshold on top of it, and never re-scores an incident
  signal beyond Clear/Flagged with the raw counts from incident-rca's own partial report.
- **The MRs-reviewed table is a severity summary, not the full pr-review render** — link to or note where
  the full chat-only review output can be found if the caller wants it re-run, don't duplicate the whole
  thing here.
- **Overall verdict derivation is fixed** (per [workflow/run-check.md](../workflow/run-check.md) § 5):
  `Not ready` if any MR has a Critical/High finding, any service's k8s verdict is `BLOCKED` **or
  `insufficient_metrics`** (unverified is not the same as verified-safe — err toward `Not ready`, never
  silently toward `Ready`), a manifest entry's `since` didn't resolve (an unreviewed MR range is not a
  verified-clean one), or any service is flagged with an incident signal — `Ready` only when none of
  those hold.
- **A flagged incident signal is a signal worth a human look, not a confirmed release-caused problem** —
  see [gate-policy.md § incident-rca](gate-policy.md#incident-rca)'s disclosed Phase-1-only limitation;
  the report's follow-up pointer exists so a human can make the correlation call this skill doesn't
  attempt.
