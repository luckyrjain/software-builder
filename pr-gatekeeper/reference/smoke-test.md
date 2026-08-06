# Smoke test — expected minimal output

Run after install or any edit to this skill. Use an open MR you're authorized to post to, with GitLab
MCP configured for `full` or `summary-only` posting (see
[pr-review/reference/smoke-test.md](../../pr-review/reference/smoke-test.md) to confirm pr-review itself
works first).

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

## Invocation

> `project: <project>`, `merge_request_iid: <iid>`, `head_sha: <sha>`, `auto_post_authorized: true`

## Expected first output

pr-review's own Phase 0 posting-mode announcement, followed by its normal review — no pr-gatekeeper-
specific preamble (this skill adds no findings of its own).

## A correct minimal output contains

1. **`auto_post_authorized: true`, `full`/`summary-only` mode, non-draft MR** — pr-review posts without a
   Phase 3 prompt appearing at all (skip condition met automatically).
2. **`auto_post_authorized: false`** (same MR, re-run) — Phase 3 prompt appears, gets the literal reply
   `"Hold — don't post"`, review still completes through Phase 5, and pr-gatekeeper reports a routed
   notification instead of a posted comment.
3. **Duplicate `head_sha`** (re-invoke Inputs with the same SHA already processed) — Gatekeep never runs;
   no second pr-review invocation.
4. **No fabricated posting** — pr-gatekeeper never posts anything pr-review itself didn't post; it only
   decides whether Phase 4 runs.

## Pass criteria

- No application source modified; no GitLab writes beyond what pr-review itself performs.
- Exactly one pr-review invocation per genuinely new `head_sha`.
- The "Hold — don't post" reply is used, and only that reply, whenever Phase 3 stops.

## Degraded path

When pr-review itself detects `chat-only` (read-only GitLab MCP): Phase 3 is skipped entirely by
pr-review's own rules; pr-gatekeeper routes the chat-rendered review to notification the same as a Hold
outcome, since nothing was posted either way.
