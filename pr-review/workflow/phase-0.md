---
workflow_version: 1.4
phase: 0
produces:
  - posting_mode
  - jira_write_available
  - mcp_tool_map
consumes:
  - project_id
  - merge_request_iid
---

# Phase 0 — Detect capabilities (before gather)

**Read this file** at the start of Phase 0, after inputs resolve to a target MR (or before listing MRs
when branch 4 needs a list-tool probe).

## Prerequisites (run before Phase 0 if not already done)

**GitHub early-exit** runs in [inputs.md](inputs.md) before this phase — do not duplicate here.

Check MCP availability before proceeding. Tell the user what is missing and how to fix it.

1. **GitLab MCP** (required): verify by attempting `get_merge_request` or any GitLab tool. If unavailable:
   > GitLab MCP is not installed. Install it by following **SETUP.md § 3** (Cursor plugin for `general-only` posting, or `@zereight/mcp-gitlab` for full inline comments). Without it this skill cannot run.

   **Multiple GitLab instances:** more than one GitLab MCP server may be connected. When resolving an MR, match the MR URL host to the server whose `GITLAB_API_URL` contains that host — use that server's tools for all calls on that MR. If only a bare IID was given, derive the host from `git remote get-url origin`. Warn the user if no configured server matches the host.

2. **Jira / Atlassian MCP** (optional): verify by attempting `getAccessibleAtlassianResources`. If unavailable:
   > Jira MCP is not connected. The review will proceed without ticket context — acceptance criteria and linked ticket checks will be skipped. To enable, add the Atlassian MCP to your `mcp.json` (see **SETUP.md § 3 → Jira / Atlassian**).

Do not attempt capability detection below until GitLab MCP is confirmed available. Jira absence is non-blocking.

## MCP retry policy (all phases)

**Normative — stated once here, applies to every MCP call in this skill** (this Phase 0 probe, Phase 1
gather, and Phase 4 posting): follow the shared 1-retry policy —
[mcp-error-handling.md](../../docs/skill-framework/shared/mcp-error-handling.md) §3. `timeout`,
`rate_limited`, and `server_error` responses get **one retry** (5s delay for `timeout`/`server_error`,
30s for `rate_limited`); if the retry also fails, mark that tool unavailable for this session and fall
through to the degraded path — the Prerequisites messages above for GitLab/Jira, or the fallback column
in `reference/mcp-capabilities.md` for the Phase 1/4 tools listed there. **Do not retry** `auth_failure`,
`not_configured`, or `invalid_request` — these are deterministic; surface them immediately (see the
Prerequisites messages above for the GitLab/Jira wording). Phase 1 and Phase 4 reference this section
rather than restating it.

## Capability detection

**Required:** inspect connected GitLab MCP tool descriptors (Cursor Settings → MCP, or each server's
tool JSON under the agent MCP descriptor path — e.g. `mcps/<server-name>/tools/*.json`) and identify
which write tools exist. **Do not read `reference/*.md` files in bulk here.** Read
`reference/mcp-capabilities.md` only if descriptor inspection is ambiguous.

**Record the server profile per connected GitLab MCP server** — there may be more than one:

| Profile | Write tools present | Posting mode |
|---------|---------------------|--------------|
| **zereight / full** | `create_merge_request_thread` + note tool | `full` |
| **MR-notes** | `create_note` or `add_merge_request_comment`, no inline thread | `summary-only` |
| **gitlab-official** | `create_workitem_note` only (no `create_merge_request_thread`) | `general-only` |
| **read-only** | none of the above | `chat-only` |

For **each** connected GitLab MCP server, detect its profile and record `{ server_name, GITLAB_API_URL, posting_mode }`. When the resolved MR belongs to a specific instance, use that instance's server and apply its posting mode for all Phase 4 operations. If two servers have different posting modes, announce the active mode for this MR explicitly.

**Jira write-tool detection (mirror the GitLab profile check):** the Prerequisites probe only confirmed
Jira **read** (`getAccessibleAtlassianResources`). Here, inspect the Atlassian MCP tool descriptors for
the **write** tools `addCommentToJiraIssue` / `transitionJiraIssue` and record `jira_write_available`
(true only if at least `addCommentToJiraIssue` is present) — many installs are read-only. Phase 5's
write-back offer keys off this flag.

**Workspace scope:** if Inputs step 4 applies, run scope detection (`reference/workspace-scope.md`) and
show the project-level ⚠️ warning when multiple repos are in scope — before listing MRs and before Phase 1.

## ⚠️ Mandatory warning for `general-only`

When mode is `general-only` (typical for the **Cursor GitLab plugin** / official GitLab Duo MCP),
show this **once, right after Phase 0 detection**, and **repeat it verbatim in Phase 3** before posting:

> ⚠️ **GitLab MCP posting limitation**
>
> Connected server: **GitLab official MCP** (`create_workitem_note` only).
>
> Comments will be posted as a **single general note** on the merge request — **not** as inline
> threads on specific diff lines. There is no line anchoring, no "Apply suggestion" on the diff,
> and findings appear only as `file:line` references inside the note body.
>
> ⚠️ **Once posted, this comment cannot be edited or retracted by the skill.** Confirm the review is complete and correct before proceeding.
>
> For line-level review comments, install `@zereight/mcp-gitlab` (see `SETUP.md`).

Do not proceed to Phase 4 posting until the user acknowledges this (Phase 3 confirm). Even if they
said "review and post", show the warning once and require explicit confirmation for `general-only`.
Acknowledgment requires user text input — see `workflow/posting.md` §User text input gates.

For `chat-only`, still run Phases 1–3; skip Phase 4 and point to `SETUP.md` for posting options.

**Phase 0 announcement:** tell the user posting mode (`full` / `summary-only` / `general-only` /
`chat-only`) and GitLab server name. See `examples.md` for announcement examples.
