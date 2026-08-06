# who-owns-x-bot — Setup

## Ambient discovery is deliberately disabled

Unlike squad-map, this skill sets `disable-model-invocation: true` — it does not auto-apply from a
human's natural-language chat turn. It's meant to be invoked explicitly, with a structured `query`
field, by the automation described below. A human asking "who owns X" in an interactive coding session
should keep routing to **squad-map** directly.

## Install

```bash
cd software-builder
make install-who-owns-x-bot
```

This chains `make install-squad-map` first — who-owns-x-bot has no ownership logic of its own and is
useless without squad-map installed alongside it. Restart Cursor so both skills reload.

### Claude Code

`make install-who-owns-x-bot` above already installs this skill for Claude Code too (default installs to
both editors). For Claude Code **only**:

```bash
cd software-builder
make install-claude-who-owns-x-bot
```

No restart needed — a new Claude Code session picks it up. See
[claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).

### Kiro / in-repo discovery

Working directly in this repo? `.cursor/rules/who-owns-x-bot.mdc` and
`.kiro/steering/who-owns-x-bot.md` point Cursor/Kiro at `who-owns-x-bot/SKILL.md` without an install
step.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| squad-map installed and configured | Its own prerequisites apply — see [squad-map/SETUP.md](../squad-map/SETUP.md) |
| A single-shot automation caller | The Slack slash-command HTTP handler itself — see § Integration contract below |

## Integration contract (for whoever builds the Slack slash-command handler)

This repo ships **agent instructions**, not a running Slack app — same boundary as pr-review's actual
GitLab webhook receiver, which also lives outside this repo. The handler you build:

1. Registers a Slack slash command (e.g. `/who-owns`) pointed at your handler's HTTPS endpoint.
2. On each invocation, starts (or reuses) an agent session that has this skill installed, and passes it
   the slash-command's text as `query` plus your configured default `workspace_root`.
3. Takes the single reply the agent returns and posts it back to Slack via the
   [`response_url`](https://api.slack.com/interactivity/handling#message_responses) from the slash-command
   payload (ephemeral or in-channel, your choice).
4. Enforces Slack's 3-second ack window — acknowledge immediately and post the actual reply as a delayed
   response via `response_url` once the agent (and squad-map's lookup) finishes, since a fresh squad-map
   query can take longer than 3 seconds.

## Config

| Setting | Where | Purpose |
|---------|-------|---------|
| Default `workspace_root` | Handler config, passed as input | Which repo checkout squad-map should scan when a fresh lookup is needed |
| `fallback_contact` | Handler config, passed to the skill or hardcoded in a local override of [reference/slack-format.md](reference/slack-format.md) | Channel/person named in the Unknown-shape reply, e.g. `#ask-platform` |

## Framework links

- [skill-framework README](../docs/skill-framework/README.md)
- [confidence-bands](../docs/skill-framework/shared/confidence-bands.md)
- [cross-skill-escalation](../docs/skill-framework/shared/cross-skill-escalation.md)

## Smoke test

After install, run the invocation in [reference/smoke-test.md](reference/smoke-test.md) against a
workspace where squad-map already resolves at least one repo.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Every reply is Unknown | Check squad-map itself resolves the same repo when asked directly — see [squad-map/SETUP.md § Troubleshooting](../squad-map/SETUP.md#troubleshooting) |
| Reply takes >3s and Slack shows "operation timed out" | Handler isn't using the delayed `response_url` pattern — see § Integration contract step 4 |
| Skill fires on ambient chat unexpectedly | Confirm `disable-model-invocation: true` survived your install/copy step |
