# pr-review

GitHub **pull request (PR)** and GitLab **merge request (MR)** review skill for Cursor. Invoke with
**`/pr-review`** or natural language when the request clearly targets a GitHub.com, GitHub Enterprise
Server, GitLab.com, or self-hosted GitLab review.

## What it does

1. **Resolves the target PR/MR** from a URL, number plus repository, or the current branch's open review.
2. **Loads context** — review metadata, paginated diff, CI/check status, linked Jira ticket and acceptance
   criteria when available.
3. **Reviews changed files only** through a phased workflow: capability detection → boundary → checklist →
   finding pipeline (detect, evidence, severity, value filter).
4. **Outputs a full review in chat** — severity table, executive summary, merge recommendation.
5. **Optionally posts comments** — GitLab threads/summary notes or GitHub RIGHT-side inline comments/issue
   summaries when the provider write capability is configured and you confirm posting.

Supports **incremental re-review** after new commits: dedupes prior findings, regression-checks resolved
threads, and emits a structured re-review note with `review_metadata` YAML.

## When to use

| Use pr-review | Use something else |
|---------------|-------------------|
| Review a GitHub PR or GitLab MR by URL or number | Local uncommitted diff → `/review-bugbot` |
| Re-review after fixes pushed | Security-only local diff → `/review-security` |
| Post severity-tagged inline comments | Security-only local diff → `/review-security` |
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
| 2 | Review, finding pipeline, stop-search cap |
| 2→3 gate | Skip posting if nits-only or zero findings |
| 3–4 | User confirmation, post threads + summary |
| 5 | Executive summary, optional Jira comment |

Agent entry point: [SKILL.md](SKILL.md). Install and MCP: [SETUP.md](SETUP.md).

## Repo-specific rules

Teams can add `review-rules.yaml` at the repo root to raise/lower severity thresholds, suppress
checklist dimensions, or set default focus areas. Starter template:
[examples/review-rules.yaml](examples/review-rules.yaml).

## Quality checks

From repo root: `make lint-pr-review` (pytest + `diff-to-positions.py` compile check).
