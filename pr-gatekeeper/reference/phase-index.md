# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `project`, `merge_request_iid`, `head_sha`, `auto_post_authorized`, `last_processed_head_sha` |
| **Gatekeep** | [workflow/gatekeep.md](../workflow/gatekeep.md) | `review_outcome` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Webhook event | Phases |
|-----------------|--------|
| Push to an open MR, `auto_post_authorized: true`, `full`/`summary-only`, non-draft | Inputs → Gatekeep → posted |
| Push to an open MR, `general-only` or draft, any `auto_post_authorized` | Inputs → Gatekeep → Hold → notification |
| Push to an open MR, `auto_post_authorized: false` | Inputs → Gatekeep → Hold → notification |
| Push where `head_sha` == caller-supplied `last_processed_head_sha` (duplicate webhook delivery) | Inputs short-circuit — Gatekeep never runs |
| Non-push event, or push to a branch with no open MR | Inputs short-circuit — Gatekeep never runs |
