# RELEASE_READINESS_REPORT.md format

**Normative.** The exact structure [workflow/run-check.md](../workflow/run-check.md) § 5 must produce.

## Structure (order fixed)

```markdown
# Release readiness — <release name/date>

**Verdict: <Ready | Not ready>**

## MRs reviewed

| Repo | MR | Severity summary | pr-review mode |
|------|----|--------------------|-----------------|
| <repo> | !<iid> | <N Critical, N High, N Medium, N Low> | chat-only |

<Repos with zero MRs since `since` still get a row: "No MRs since `<since>`".>

## Per-service rightsizing

| Service | k8s verdict | Notes |
|---------|-------------|-------|
| <service> | <k8s-overprovisioning-datadog's own verdict, unmodified> | <one-line pointer to the full k8s report if BLOCKED> |

## Per-service incident signal

| Service | Signal | Window | Notes |
|---------|--------|--------|-------|
| <service> | Clear \| Flagged | `<from_time>`–`<to_time>` UTC | <error/infra signal counts if flagged; "Run incident-rca directly on `{service}` `{window}` for full investigation" if flagged> |

## Notes

<Any MR-range-resolver fallback used (e.g. GitLab MCP didn't support a merge-date filter, client-side
filtering was used instead); any incident-rca escalation per gate-policy.md § Escalation, not override.>
```

## Rules

- **Every `release_manifest` entry appears somewhere in the report** — a clear/uneventful entry still
  gets a row in each relevant section; never silently dropped for having nothing to report.
- **k8s and incident-rca verdicts are surfaced as-is** — this skill never re-labels a k8s READY/BLOCKED
  recommendation or invents its own "risky" threshold on top of it, and never re-scores an incident
  signal beyond Clear/Flagged with the raw counts from incident-rca's own partial report.
- **The MRs-reviewed table is a severity summary, not the full pr-review render** — link to or note where
  the full chat-only review output can be found if the caller wants it re-run, don't duplicate the whole
  thing here.
- **Overall verdict derivation is fixed** (per [workflow/run-check.md](../workflow/run-check.md) § 5):
  `Not ready` if any MR has a Critical/High finding, any service's k8s verdict is `BLOCKED`, or any
  service is flagged — `Ready` only when none of those hold.
