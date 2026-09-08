# Jira write-back (optional)

Isolated reference for Phase 5 post-review Jira actions. **Never auto-post** — offer only after the
executive summary renders and the user confirms.

**Prerequisites:** `jira_write_available: true` from Phase 0; linked ticket from Phase 1 step 6.

**Shared template:** [post-action-templates.md](../../docs/skill-framework/shared/post-action-templates.md) §2.

## Workflow

1. **Offer** — after Phase 5 completes, ask whether to post the Jira comment (and optional transition).
2. **Comment first** — `addCommentToJiraIssue` using `reference/comment-templates.md` or shared §2 template. Include MR link, recommendation, blocking summary.
3. **Transition second (optional)** — only after successful comment and explicit user confirmation for Approve outcomes. `transitionJiraIssue` once.
4. **On failure** — print a short failure line; **continue**. Never retry in a loop; never roll back GitLab posts.

## Suggested transitions (best-effort)

| Review outcome | Suggested transition | Preconditions |
|----------------|---------------------|---------------|
| **Approve** | *Ready for QA* / *Done* / project-specific "review passed" | User confirms; ticket in review state |
| **Request changes** + Critical | Comment only — suggest *In Progress* or leave state | Do not close ticket on Critical |
| **Comment** | Comment only | No transition unless user asks |

## Multi-ticket MRs

Post to each ticket the user confirmed. Failures on one ticket do not abort others.

## Graceful failure example

> ⚠️ Jira write-back failed for `PAY-1421` (`addCommentToJiraIssue`): permission denied — Epic comments
> may be restricted. GitLab review is complete; post the summary link to Jira manually if needed.
