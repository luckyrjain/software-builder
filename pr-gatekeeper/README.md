# pr-gatekeeper

**Runs pr-review automatically on every push** to an open GitLab MR, posting inline exactly as pr-review
already supports — when pr-review's own rules allow unattended posting. A thin wrapper: no review logic
of its own.

Unlike pr-review, this skill does **not** auto-invoke from ambient chat (`disable-model-invocation:
true`). It's called explicitly by the webhook integration described in [SETUP.md](SETUP.md).

## What it does

1. **Fires on a push webhook** — new commit on an open MR's source branch.
2. **Invokes pr-review** for that MR — same phases, findings, severity rubric, posting templates,
   cross-session dedupe as an interactive `/pr-review` run.
3. **Decides whether posting may happen**, per pr-review's own confirmation rules — auto-posts only when
   the project is authorized (`auto_post_authorized`) **and** pr-review's mode is `full`/`summary-only`
   **and** the MR isn't a draft. Otherwise it holds and routes the review to a human notification
   instead — never invents a posting bypass pr-review itself doesn't already define.
4. **Never reposts on an unchanged push** — short-circuits before invoking pr-review at all when the
   webhook's `head_sha` matches the last one already handled for that MR.

## When to use

| Use pr-gatekeeper | Use instead |
|---------------------|--------------|
| GitLab push webhook, want automatic review on every commit | Interactive "review this MR" → **pr-review** |
| Team wants a standing review bot on an MR | One-off review → **pr-review** |
| — | Auto-fixing findings (not built yet — roadmap follow-up) |

## Invocation examples

```
project: acme/backend, merge_request_iid: 482, head_sha: 9f1a2c3, auto_post_authorized: true
project: acme/backend, merge_request_iid: 482, head_sha: 9f1a2c3, auto_post_authorized: false
```

## What you get

Whatever pr-review itself would produce — inline threads + summary note (`full`), one summary note
(`summary-only`), a general comment (`general-only`, always held for a human), or a chat-only render.
When posting is held, pr-gatekeeper additionally routes that same review via a notification (Slack/email/
whatever [SETUP.md](SETUP.md) § Config points at) so a human still sees it.

## Install

```bash
cd software-builder
make install-pr-gatekeeper
```

Restart Cursor. Requires **pr-review** installed and configured for GitLab posting (the make target
chains it automatically) — see [pr-review/SETUP.md](../pr-review/SETUP.md) — plus the webhook integration
contract in [SETUP.md](SETUP.md).

## Related skills

- **pr-review** — does the actual review; this skill only decides whether a given push may auto-post
- **incident-rca**, **k8s-overprovisioning-datadog** — pr-review's own cross-skill escalations, unchanged

Agent instructions: [SKILL.md](SKILL.md).
