# Proposal check report

**Proposal:** <name/one-line description>
**Checked against:** manifest.yaml as of <engagement.last_updated>

## Verdict: <Clear | N conflict(s) found>

| Claim | Category | Verdict | Colliding existing entry | Evidence | Confidence |
|-------|----------|---------|---------------------------|----------|------------|
| <claim text> | Bounded context \| Data ownership \| API path | Clear \| Conflict | <repo/table/path, or —> | <repo>/path:Line, or —> | HIGH \| MEDIUM \| LOW \| UNKNOWN |

## Notes

- This report does not modify `BOUNDED_CONTEXTS.md`, `DATA_OWNERSHIP.md`, `API_CATALOG.md`,
  `EVENT_CATALOG.md`, `RISK_MAP.md`, or `manifest.yaml`. If this proposal is built, re-check it (claims
  may have changed) and, once real code exists, onboard it via `ADD_REPO`.
