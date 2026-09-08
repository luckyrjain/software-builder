# Smoke test — expected minimal output

Run after install or any edit to this skill. Use a workspace where squad-map already resolves at least
one repo at HIGH or MEDIUM confidence (see [squad-map/reference/smoke-test.md](../../squad-map/reference/smoke-test.md)
to set that up first if needed).

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

## Invocation

> `query: <repo-name>`, `workspace_root: <workspace>`

Example: `query: api-disbursement`, `workspace_root: ./services`

## Expected first output

One Slack-formatted reply — no intermediate chatter, no file written by this skill.

## A correct minimal output contains

1. **Exactly one reply**, matching one of the three shapes in
   [reference/slack-format.md](slack-format.md) (Resolved / Ambiguous / Unknown).
2. **Resolved case** — squad name and confidence band both present, evidence line present.
3. **No fabricated squad** — if squad-map itself returns UNKNOWN or LOW confidence, the reply must be
   the Unknown shape, never a guessed squad name.
4. **Empty query** — reply is the usage-hint line, and Lookup never runs (no squad-map invocation).

## Pass criteria

- No application source modified; no file written by this skill (squad-map may write/update its own
  `SQUAD_MAP.md` — that's expected and out of this skill's scope).
- Exactly one reply per invocation.
- Read-only throughout.

## Degraded path

When squad-map itself has no MCP available (CODEOWNERS fallback, confidence capped LOW): reply is
**Unknown**, per [reference/slack-format.md](slack-format.md) — LOW confidence never surfaces as
Resolved in a single-shot reply.

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
