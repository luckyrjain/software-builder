# pr-review

GitHub **pull request (PR)** and GitLab **merge request (MR)** review skill for Cursor. Invoke with
**`/pr-review`** or natural language when the request clearly targets a GitHub.com, GitHub Enterprise
Server, GitLab.com, or self-hosted GitLab review.

## What it does

1. **Resolves the target PR/MR** from a URL, number plus repository, or the current branch's open review.
2. **Loads context** — review metadata, paginated diff, CI/check status, linked Jira ticket and acceptance
   criteria when available.
3. **Reviews the changed diff as the finding boundary**, then performs bounded cross-file/consumer,
   compatibility, rollout, test-quality, and dependency/config/IaC inspections when triggered. Findings still
   require valid changed-line anchors; contextual consumer/caller reads support impact evidence rather than
   expanding the inline finding boundary.
4. **Emits machine review evidence** bound to the current change identity, including explicit
   `unable_to_inspect` coverage when a required surface cannot be verified.
5. **Outputs a full review in chat** — severity table, coverage gaps when applicable, executive summary, and
   merge recommendation.
6. **Optionally posts comments** — GitLab threads/summary notes or GitHub RIGHT-side inline comments/issue
   summaries when the provider write capability is configured and posting gates pass.

Supports **incremental re-review** after new commits: dedupes prior findings, regression-checks resolved
threads, validates freshness against the current change/requirements state, and emits a structured re-review note
with `review_metadata` YAML.

## When to use

| Use pr-review | Use something else |
|---------------|-------------------|
| Review a GitHub PR or GitLab MR by URL or number | Local uncommitted diff → the host's local diff/code-review workflow (no registered skill) |
| Re-review after fixes pushed | Security-only local diff → the host's local diff/code-review workflow (no registered skill) |
| Post severity-tagged inline comments | Security-only local diff → the host's local diff/code-review workflow (no registered skill) |
| Check Jira AC against the MR diff | Keep MR merge-ready as new commits land (webhook-triggered) → **pr-gatekeeper** |
| — | Release-wide go/no-go sweep across many MRs/services → **release-readiness-checker** |

## Invocation examples

**Slash command:**

```
/pr-review
/pr-review !482 in backend/payments
/pr-review https://gitlab.example.com/group/repo/-/merge_requests/123
/pr-review https://github.com/acme/payments/pull/482
/pr-review https://github.example.com/platform/payments/pull/91
```

**Natural language** (same workflow):

```
review this pr https://gitlab.example.com/group/repo/-/merge_requests/123
review this MR !482
review this PR #482
review and post !482
review !482, focus on migrations
review as SRE
re-review !482
list open MRs
```

Full table: [examples.md](examples.md)

## What you get

A fragment of a real review (fictional MR, shape matches actual output):

> | ID | Score | Overall | Conf | Business impact | Location | Finding |
> |----|-------|---------|------|-----------------|----------|---------|
> | PRR-DATA-001 | 9 | 🟠 High | High | Wrong amount debited → dispute risk | `RefundHandler.java:88` | Refund amount uses `int` cents; webhook payload is decimal string — truncation on values ≥ $10.24 |
>
> **Recommendation:** 🔴 Request changes — one High data-integrity issue on amount parsing should be
> fixed before merge. CI green on head; linked Jira AC partially met.

Full shape: [reference/gold-review-excerpt.md](reference/gold-review-excerpt.md). More scenarios: [examples.md](examples.md).

- Findings grouped by severity; **thematic clusters** (Resilience, Jackson, payment date) → ~8 rows not ~15
- Business impact column on Code blockers (High/Critical only) · ~4–5 High max via certainty gate
- Code blockers → Decision gates → Technical vs Process blockers
- Not raised (suppressed) + Positive observations sections
- Explicit **Coverage gaps** when triggered review surfaces cannot be inspected
- Security score **Needs attention** when app-level auth gap (not Clear)
- Architecture lens (§16) when structural change triggers
- **Review modes** — Pre-merge · Incremental · Post-merge retrospective (`reference/review-modes.md`)
- Optional GitLab/GitHub comments + `<!-- cursor-pr-review -->` summary note

## Workflow (agent)

| Phase | Purpose |
|-------|---------|
| Inputs | Resolve provider-neutral target |
| 0 | Detect posting mode from provider capabilities |
| 1 | PR/MR metadata, diff boundary, CI/checks, Jira AC |
| 1→2 coverage | Build current change identity and six-surface inspection plan |
| 2 | Core review, finding pipeline, stop-search cap |
| 2 coverage review | Execute missing cross-file/consumer/compatibility/readiness inspections and regroup findings |
| 2 evidence | Emit/validate portable review evidence and project partial coverage into incomplete-review state |
| 2→3 gate | Rebuild current identity/requirements; fail closed on stale/invalid or mandatory-unavailable evidence |
| 3–4 | Explicit confirmation when required, then guarded provider comments/summary |
| 5 | Executive summary, coverage gaps, optional Jira comment |

Partial/unavailable coverage never implies merge readiness. Mandatory unavailable coverage blocks provider posting;
non-mandatory partial coverage requires explicit confirmation and is capped below Approve.

Agent entry point: [SKILL.md](SKILL.md). Install and MCP: [SETUP.md](SETUP.md).

## Repo-specific rules

Teams can add `review-rules.yaml` at the repo root to raise/lower severity thresholds, suppress
checklist dimensions, or set default focus areas. Starter template:
[examples/review-rules.yaml](examples/review-rules.yaml).

## Quality checks

From repo root: `make lint-pr-review` (workflow/contract checks, validator tests, pytest, and helper compile checks).