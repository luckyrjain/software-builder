# who-owns-x-bot

**Single-shot "who owns X" answer**, formatted for a Slack slash command or any other automated caller
that gets exactly one reply and no follow-up turn. A thin wrapper around **squad-map** — no ownership
logic of its own.

Unlike squad-map, this skill does **not** auto-invoke from ambient chat (`disable-model-invocation:
true`). It's called explicitly by the automation described in [SETUP.md](SETUP.md).

## What it does

1. **Takes a `query`** — a repo/service/component name (a Slack slash-command argument).
2. **Delegates to squad-map** — reuses an existing `SQUAD_MAP.md` row if fresh, otherwise runs squad-map's
   own single-repo lookup.
3. **Classifies the result** using squad-map's own confidence band and conflict flag — Resolved,
   Ambiguous, or Unknown. Never guesses a squad name.
4. **Returns one Slack message** — no markdown file written by this skill.

## When to use

who-owns-x-bot is for a Slack `/who-owns api-disbursement` payload or any other single-shot, no-follow-up
automated lookup. An interactive "who owns X?" question inside a coding session should route to
**squad-map** directly — it can hold a follow-up conversation, this skill cannot — and a request for the
full bounded-context/domain map goes to **domain-comprehension**. Full routing table:
[SKILL.md](SKILL.md#when-to-use-not-to-use).

## Invocation examples

```
query: api-disbursement
query: legacy-ledger        (known GitLab/Datadog conflict → Ambiguous reply)
query: some-typo-repo       (no match → Unknown reply)
query: (empty)              (→ usage-hint reply, no lookup)
```

## What you get

One Slack message, one of three shapes:

> :white_check_mark: *api-disbursement* → *disbursement* squad (HIGH confidence)
> GitLab namespace acme/disbursement/api-disbursement; Datadog team disbursement-platform

> :warning: *legacy-ledger* — GitLab and Datadog disagree, need a human to confirm: …

> :grey_question: Couldn't find ownership for *some-typo-repo*. Try #ask-platform.

Full format spec: [reference/slack-format.md](reference/slack-format.md).

## Install

```bash
cd software-builder
make install-who-owns-x-bot
```

Restart Cursor. Requires **squad-map** installed too (the make target chains it automatically). MCP
setup is squad-map's — see [squad-map/SETUP.md](../squad-map/SETUP.md) — plus the Slack integration
contract in [SETUP.md](SETUP.md).

## Related skills

- **squad-map** — does the actual ownership computation; this skill only formats its answer for a
  single-shot caller
- **domain-comprehension** — full bounded-context/domain map, not just ownership

Agent instructions: [SKILL.md](SKILL.md).
