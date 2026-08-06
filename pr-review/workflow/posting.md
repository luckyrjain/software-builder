---
workflow_version: 1.4
phase: 3-4
produces:
  - posted_threads
  - summary_note
consumes:
  - findings
  - posting_mode
  - posting_decision
---

# Phase 3–4 — Confirm and post

**Read this file** for Phase 3 (confirm) and Phase 4 (post), after the Phase 2→3 gate allows posting.

**Also load when posting:**
- `reference/comment-templates.md` — always for Phase 4 summary
- `reference/gitlab-inline-comments.md` — Phase 4 `full` mode only

## User text input gates

When the skill must **wait for the user** — MR pick (ambiguous target), `general-only` acknowledgment,
Phase 3 posting confirmation, or any numbered option list when `ask-question` is unavailable:

1. **Pause execution** until the user's **next message** contains an explicit choice (number, option
   label, URL/IID, or clear yes/no).
2. **Do not** use `<ElicitationsGroup>`, auto-generated clickable chips, or other simulated UI that
   pretends to collect input while continuing the workflow.
3. **Do not** treat silence, an unrelated follow-up, or your own suggested default as consent.

If `ask-question` is available, use it (Claude Code: `AskUserQuestion` —
[claude-code-setup.md §4](../../docs/skill-framework/shared/claude-code-setup.md#4-user-input-gates-ask-question-equivalent));
otherwise print numbered options and apply the rules above.

---

## Phase 3 — Confirm before posting

**Typed `posting_policy: forbidden`** (caller-supplied per
[inputs.md § Typed invocation](inputs.md#typed-invocation-skill-to-skill-callers)): skip Phase 3 and
Phase 4 entirely, identical to `chat-only` — render the full review in chat and stop. No confirmation
prompt, nothing posted, regardless of the posting mode Phase 0 detected.

> **Terminology:** "Draft" in the **Draft option** column below means posting comments as GitLab
> **Draft Review notes** (`create_draft_note`) — *not* the same as a **Draft/WIP MR**.

| Mode | Confirmation required | Draft option | Skip on "review and post"? |
|------|----------------------|--------------|---------------------------|
| `full` | Yes | Yes (if `create_draft_note` detected) | Yes, for non-draft MRs |
| `summary-only` | Yes | No | Yes |
| `general-only` | Always (after ⚠️ warning) | No | No |
| `chat-only` | None — skip Phase 3 entirely | N/A | N/A |

Render full review grouped by severity + executive summary (Phase 5 content can be previewed here).

- **`full`:** ask-question:
  > "Post this review to !<iid>? — [Post all comments] [Post as drafts]* [Post summary only] [Hold — don't post] [Cancel]"
  > *Include `[Post as drafts]` only when `create_draft_note` was detected in Phase 0.*
- **`summary-only`:** ask-question:
  > "Post this review to !<iid>? — [Post summary only] [Hold — don't post] [Cancel]"
- **`general-only`:** repeat the ⚠️ warning from Phase 0 (`workflow/phase-0.md`), then ask:
  > "Post as a **general MR comment** (no inline threads) to !<iid>? — [Post general comment] [Hold — don't post] [Cancel]"
- **`chat-only`:** skip Phase 3 — render the full review in chat and stop. Note that posting requires
  a GitLab MCP with write tools (`SETUP.md`). No confirmation prompt.

Never offer an option the connected MCP cannot perform (e.g. drafts without `create_draft_note`).

**No ask-question tool?** Print the same options as a numbered list and follow **User text input gates** above.

**Draft / WIP MRs:** if the MR is draft (title starts with `Draft:` or `WIP:`, or the
`work_in_progress` flag is set), display before the posting options:
> ⚠️ **This MR is a draft** — review findings are ready but posting to a draft MR may clutter
> early work. Post anyway, or hold until the MR is marked ready?

**Incomplete review** (`review_metrics.review_complete: false` — stop-search fired, or a partial diff
boundary accepted after a pagination/file cap, per `reference/review-metrics.md` §Recommendation
matrix): display before the posting options, same as the draft warning:
> ⚠️ **This review is incomplete** — [state the reason: stop-search threshold hit / diff truncated at
> the page-or-file cap]. The recommendation below reflects only the portion reviewed and cannot be
> Approve. Post the partial findings anyway, or hold for a complete review?

Proceed only on explicit confirmation (any choice other than Hold or Cancel).

Skip confirmation only when user said "review and post" **and** mode is `full` or `summary-only`
**and** the MR is not a draft **and** the review is complete (`review_metrics.review_complete` is not
`false`). An incomplete review always confirms — the same as a draft MR — even on "review and post",
and even for an unattended caller scripted to always answer "review and post" (e.g. pr-gatekeeper with
`auto_post_authorized: true`): that automation's own deterministic reply to a Phase 3 prompt is always
"Hold — don't post" (`pr-gatekeeper/reference/auto-post-policy.md`), so forcing this confirmation to
render is what keeps an incomplete review from being silently auto-posted as a finished, clean review.
For `general-only`, always confirm after the warning.

## Critical findings — second-reviewer signal

When Phase 2 emitted **≥1 Critical** finding, prepend
to the Phase 3 confirmation prompt (and Phase 4 summary when posting):

> 🛑 **Critical finding(s) require human review before merge** — do not merge until a second reviewer
> has validated the Critical item(s) listed below.

List Critical finding titles/locations. This is advisory (no pipeline block) but must appear in chat
and in the posted summary **Blocking Issues** section. See also
[phase-5.md](phase-5.md#pipeline-vote-merge-gate-maintainer-checklist) — the skill cannot vote `-2` or block
merge via API; recommend a human maintainer gate and link GitLab approval rules when available.

---

## Phase 4 — Post (when mode allows)

**MCP retry policy:** posting calls (`create_merge_request_thread`, `create_note`,
`create_workitem_note`, `create_draft_note`) follow the 1-retry policy stated once in
[phase-0.md § MCP retry policy](phase-0.md#mcp-retry-policy-all-phases) — retry once on `timeout` /
`rate_limited` / `server_error` before a thread is counted as a failure under **Partial-post recovery**
below.

Post **only** findings that survived Phase 2 finding dedupe — never re-post same location, root cause,
stack, or API misuse already on the MR. **Cross-session dedupe:** before posting, re-fetch MR notes and
confirm no open thread or prior summary already covers the same finding (match by `file:line` + snippet
hash per `reference/incremental-rerun.md`) — applies even when this session has no prior
`<!-- cursor-pr-review -->` tag in memory.

**Root cause groups** → one inline thread per group (anchored to
first location; all sites in body), not one thread per location.

- **`full`:** up to the **inline thread cap** (default **15** — see `reference/gitlab-inline-comments.md`);
  summary via `create_note`. Use `scripts/diff-to-positions.py` when anchoring. If
  `create_merge_request_thread` rejects a position needing `line_code`, follow that file's **line_code
  handling** section before falling back to summary note. Renamed files → pass `--old-path`; deleted-only
  files cannot be anchored inline → summary note.
  **Renamed-file fast fallback:** when `old_path ≠ new_path` (or `renamed_file: true`), attempt **at most
  one** inline post with `--old-path`. If rejected, **do not** retry position tweaks — include in summary
  note and record under **Posting notes** (*inline failed — renamed file*).
- **`summary-only`:** one MR note (`create_note`) with all findings and `file:line` references.
- **`general-only`:** one note via `create_workitem_note` — pass MR `web_url` (preferred) or
  `project_id` + `work_item_iid` (= MR IID) and the full summary body from
  `reference/comment-templates.md`. **Do not** attempt `create_merge_request_thread`. Prefix the body:
  `> ⚠️ Posted via Cursor /pr-review as a general comment (not inline on the diff).`
  **Verify it landed** (re-fetch via `get_workitem_notes`); on failure, fall back to `chat-only` and tell the user.
- **`chat-only`:** skip; explain which MCP profile enables posting (`SETUP.md`).

Summary template: `reference/comment-templates.md`. First line: `<!-- cursor-pr-review -->`; include
`**Reviewed:**` (ISO-8601 timestamp), the machine-parseable **`- head_sha: \`<full_sha>\``** line, and
the **actual** posting mode from Phase 0 for future re-reviews.

**Always** re-fetch `get_merge_request` immediately before the first Phase 4 post and compare
`diff_refs.head_sha` to the SHA captured in Phase 1 step 1. If it changed, follow
`reference/gitlab-inline-comments.md` §SHA staleness (rebuild positions or summary-only).

**Draft batch mode:** only when `create_draft_note` exists (`full` mode).

**Partial-post recovery (never stop-on-error):** post threads independently — a failure on **any**
thread does **not** abort the run. Continue all remaining threads, collect failures, include failed
findings in the summary note and **Posting notes** section.

**Batch position-mapping failures:** `scripts/diff-to-positions.py --batch` exits **1** on partial
failure — post the non-`error` threads and list `error` entries in **Posting notes**.

**Verify:** re-fetch notes (`get_workitem_notes`, `mr_discussions`) when possible.

After Phase 4 (or if posting was skipped), **read `workflow/phase-5.md`**.

## Slack / Teams notification (optional)

After Phase 5 (or after Phase 4 when posting ran), optionally notify stakeholders. **Never block**
the review on notification failure. Shared template:
[post-action-templates.md](../../docs/skill-framework/shared/post-action-templates.md) §5.

### When Slack MCP is available (`plugin-slack-slack`)

If the user named a channel or the repo has a `#code-review` / `#deployments` convention:

1. **Offer** to post a one-line summary — proceed only on user confirmation.
2. Use `chat_postMessage` (or equivalent) with:

```text
:gitlab: MR !<iid> reviewed — <Recommendation emoji> <Approve|Comment|Request changes>
Critical: <count> | High: <count> | MR: <web_url>
```

3. On MCP error, print failure line and continue — do not retry in a loop.

### Manual notify template (no Slack MCP)

When Slack/Teams MCP is unavailable, offer this copy-paste template in chat:

```text
Subject: MR !<iid> review — <Recommendation>

Reviewed <timestamp> on head <short_sha>.
Recommendation: <Approve | Comment | Request changes>
Blocking: <Critical/High count or "None">
Summary: <one sentence>
MR: <web_url>
Full review: <link to GitLab summary note or paste executive summary>
```

For **Critical** findings, add: *Human merge gate recommended — do not merge until Critical items resolved.*

Teams: same body works in a channel post or adaptive-card text field.
