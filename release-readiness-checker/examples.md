# Examples — invocation patterns

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation table

| # | Caller sends | Behavior |
|---|--------------|----------|
| 1 | `release_manifest: [{repo: api-disbursement, service: disbursement-service, since: v2.3.0}]`, 2 MRs merged since `v2.3.0` | Inputs → Run check → both MRs reviewed `chat-only`, k8s verdict for `disbursement-service`, incident-rca Phase 1 for `disbursement-service` → `RELEASE_READINESS_REPORT.md` |
| 2 | A repo entry with zero MRs merged since `since` | Recorded as "no changes this release" — not a HARD STOP, not omitted from the report |
| 3 | A reviewed MR has a `Critical` finding | Overall verdict: **Not ready** |
| 4 | A service's k8s verdict is `BLOCKED` | Overall verdict: **Not ready** |
| 5 | A service's incident-rca Phase 1 finds a strong error-rate signal | Answered "stop here" anyway per [gate-policy.md](reference/gate-policy.md) — service flagged, overall verdict **Not ready**, full RCA never runs |
| 6 | Every MR clean, every k8s verdict READY, every service's incident signal clear | Overall verdict: **Ready** |
| 7 | `release_manifest` empty | Inputs HARD STOP — ask, no Run check |
| 8 | GitLab MCP server has no merge-date filter param | MR-range resolver falls back to client-side filtering by `merged_at` — not a smaller, silently-incomplete MR set |
| 9 | "Review MR !482" | **Wrong skill** → pr-review directly |
| 10 | "Is disbursement-service overprovisioned?" (one service, no release context) | **Wrong skill** → k8s-overprovisioning-datadog directly |
| 11 | A flagged service — caller wants the full investigation | **Wrong skill for that** → incident-rca directly, service + window this skill already used |

---

### Scenario: Normal release check — happy path

**Caller:** `release_manifest: [{repo: api-disbursement, service: disbursement-service, since: v2.3.0}, {repo: api-payouts, service: payouts-worker, since: v1.8.0}]`

**Agent:**

1. Inputs — manifest parsed, `incident_lookback_hours` defaults to 48
2. Run check § 1 — resolves 2 MRs for `api-disbursement` since `v2.3.0`, 0 MRs for `api-payouts` since
   `v1.8.0`
3. Run check § 2 — both `api-disbursement` MRs reviewed `chat-only`: 1 clean, 1 with a `Medium` finding
4. Run check § 3 — `disbursement-service` k8s verdict `READY` (no cuts needed); `payouts-worker` verdict
   `READY`
5. Run check § 4 — both services' incident-rca Phase 1 finds zero signals in the last 48h; Phase 1
   checkpoint answered "stop here" for both, per policy, even though there was nothing to override
6. Run check § 5 — overall verdict `Ready` (no Critical/High findings, no BLOCKED verdicts, no flags)

**Expected fragment:**

```
# Release readiness — 2026-08-05

**Verdict: Ready**

## MRs reviewed

| Repo | MR | Severity summary | pr-review mode |
|------|----|--------------------|-----------------|
| api-disbursement | !210 | 0 Critical, 0 High, 1 Medium, 0 Low | chat-only |
| api-disbursement | !212 | 0 Critical, 0 High, 0 Medium, 0 Low | chat-only |
| api-payouts | — | No MRs since v1.8.0 | — |

## Per-service rightsizing

| Service | k8s verdict | Notes |
|---------|-------------|-------|
| disbursement-service | READY (no cuts needed) | — |
| payouts-worker | READY (no cuts needed) | — |

## Per-service incident signal

| Service | Signal | Window | Notes |
|---------|--------|--------|-------|
| disbursement-service | Clear | 2026-08-03T00:00Z–2026-08-05T00:00Z | — |
| payouts-worker | Clear | 2026-08-03T00:00Z–2026-08-05T00:00Z | — |
```

---

### Scenario: Flagged incident signal overrides "proceed" default

**Caller:** Same manifest, but `disbursement-service` had an error-rate spike in the last 12h.

**Agent:** incident-rca's own Phase 1 checkpoint would normally *"proceed unless user says stop"* on a
strong signal — this skill answers **"stop here"** anyway per [reference/gate-policy.md](reference/gate-policy.md),
takes the Phase 1 evidence as the signal, and never continues to Phase 2.

**Expected fragment:**

```
## Per-service incident signal

| Service | Signal | Window | Notes |
|---------|--------|--------|-------|
| disbursement-service | Flagged | 2026-08-03T00:00Z–2026-08-05T00:00Z | 3 error signals, 1 infra signal — run incident-rca directly on disbursement-service 2026-08-03T00:00Z–2026-08-05T00:00Z for full investigation |
```

**Verdict: Not ready** (a flagged service alone is enough).

---

### Scenario: Cross-skill — wrong entry point

**Caller:** "Review MR !482"

**Agent:** Routes to **pr-review** directly — this is a single-MR review, not a release-wide sweep (see
[SKILL.md](SKILL.md) § When to use / NOT to use).
