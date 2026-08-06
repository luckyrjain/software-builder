# pr-review

GitLab **merge request (MR) review** skill for Cursor. Invoke with **`/pr-review`** or natural language
(e.g. "review this MR …", "review !482") when the request clearly targets a GitLab MR.

## What it does

1. **Resolves the target MR** from a GitLab URL, `!IID`, `!IID in group/repo`, or the current branch's open MR.
2. **Loads context** — MR metadata, paginated diff, CI pipeline status, linked Jira ticket and acceptance
   criteria when available.
3. **Reviews changed files only** through a phased workflow: capability detection → boundary → checklist →
   finding pipeline (detect, evidence, severity, value filter).
4. **Outputs a full review in chat** — severity table, executive summary, merge recommendation.
5. **Optionally posts to GitLab** — inline threads on diff lines plus one summary note (when GitLab MCP
   write tools are configured and you confirm posting).

Supports **incremental re-review** after new commits: dedupes prior findings, regression-checks resolved
threads, and emits a structured re-review note with `review_metadata` YAML.

## When to use

| Use pr-review | Use something else |
|---------------|-------------------|
| Review a GitLab MR by URL or `!IID` | GitHub PR → `/review-bugbot` or `gh pr view` |
| Re-review after fixes pushed | Local uncommitted diff → `/review-bugbot` |
| Post severity-tagged inline comments | Security-only local diff → `/review-security` |
| Check Jira AC against the MR diff | Keep MR merge-ready as new commits land (webhook-triggered) → **pr-gatekeeper** |
| — | Release-wide go/no-go sweep across many MRs/services → **release-readiness-checker** |

## Invocation examples

**Slash command:**

```
/pr-review
/pr-review !482 in backend/payments
/pr-review https://gitlab.example.com/group/repo/-/merge_requests/123
```

**Natural language** (same workflow):

```
review this pr https://gitlab.example.com/group/repo/-/merge_requests/123
review this MR !482
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
- Optional GitLab posts: inline threads + `<!-- cursor-pr-review -->` summary note

## Workflow (agent)

| Phase | Purpose |
|-------|---------|
| Inputs | Resolve `project_id` + `merge_request_iid` |
| 0 | Detect posting mode from GitLab MCP tools |
| 1 | MR metadata, diff boundary, CI, Jira AC |
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
