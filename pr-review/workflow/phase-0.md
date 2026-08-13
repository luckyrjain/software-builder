---
workflow_version: 1.5
phase: "0"
produces: {posting_mode: string, jira_write_available: boolean, mcp_tool_map: object, provider_capabilities: object}
consumes:
  required: {review_target: object}
  optional: {project_id: string, merge_request_iid: string}
  conditional: {}
---

# Phase 0 — Detect capabilities (before gather)

**Read this file** at the start of Phase 0, after inputs resolve to a target MR (or before listing MRs
when branch 4 needs a list-tool probe).

## Prerequisites (run before Phase 0 if not already done)

Load `reference/provider-adapters.md`; select only tools for the immutable target provider and host.

Check MCP availability before proceeding. Tell the user what is missing and how to fix it.

1. **Provider read access** (required): for GitLab, verify `get_merge_request` or an equivalent GitLab
tool. For GitHub, verify a GitHub App/MCP read tool or authenticated `gh` against the exact target host.
If unavailable, stop with provider-specific setup guidance; never cross-host fallback.
   > GitLab MCP is not installed. Install it by following **SETUP.md § 3** (Cursor plugin for `general-only` posting, or `@zereight/mcp-gitlab` for full inline comments). Without it this skill cannot run.

   **Multiple GitLab instances:** more than one GitLab MCP server may be connected. Parse each
   configured `GITLAB_API_URL`; normalize its lowercase hostname plus explicit/effective port, and
   compare it with the MR target by **exact normalized authority equality**. Never use substring,
   prefix, or hostname-only matching (`gitlab.example:8443` and `gitlab.example:9443` are different
   authorities, and `gitlab.example.evil` is unrelated). Use only the uniquely matching server's tools
   for that MR. If zero servers match, warn and stop; if more than one provider/server claims the same
   authority, treat selection as ambiguous and stop. If only a bare IID was given, derive the exact
   authority from `git remote get-url origin` before selecting a server.

   **HTTP GitHub input:** reject an HTTP GitHub or GHES review URL, or an HTTP origin used for
   discovery, before any App/MCP selection or `gh` call, whether port 80 is implicit or explicit. Do
   not upgrade the URL to HTTPS or substitute another authority. This input rule does not remove
   intentionally configured GitLab HTTP support.

   **GitHub Enterprise Server on a non-default port:** evaluate the immutable
   `review_target.authority` before any CLI probe. GitHub CLI accepts a hostname, not an authority with
   a port, so CLI fallback is unavailable for a target such as `forge.company.internal:8443`. Make
   zero `gh` calls for that target: no `gh auth status`, `gh pr list`, `gh pr view`, `gh pr diff`,
   `gh pr checks`, or `gh api`. Require a complete GitHub App/MCP read pair bound to the exact
   authority, covering metadata/current head plus changed files/diff hunks.
   Never strip the port or make a hostname-only call, even for authentication or discovery; if the
   exact-authority read pair is absent, stop as unavailable. This prevents every auth, list, view,
   diff, checks, and API path from
   crossing to a default-port service.

2. **Jira / Atlassian MCP** (optional): verify by attempting `getAccessibleAtlassianResources`. If unavailable:
   > Jira MCP is not connected. The review will proceed without ticket context — acceptance criteria and linked ticket checks will be skipped. To enable, add the Atlassian MCP to your `mcp.json` (see **SETUP.md § 3 → Jira / Atlassian**).

Jira absence is non-blocking. Continue with only the selected provider capability; a GitHub target never
requires a GitLab MCP and a GitLab target never requires GitHub access.

## MCP retry policy (all phases)

Provider writes use the provider-specific recovery rule below, not the automatic read retry.

**Normative — stated once here:** Phase 0 probes and Phase 1 reads follow the shared 1-retry policy —
[mcp-error-handling.md](../../docs/skill-framework/shared/mcp-error-handling.md) §3. `timeout`,
`rate_limited`, and `server_error` responses get **one retry** (5s delay for `timeout`/`server_error`,
30s for `rate_limited`); if the retry also fails, mark that tool unavailable for this session and fall
through to the degraded path — the Prerequisites messages above for GitLab/Jira, or the fallback column
in `reference/mcp-capabilities.md` for the Phase 1/4 tools listed there. **Do not retry** `auth_failure`,
`not_configured`, or `invalid_request` — these are deterministic; surface them immediately (see the
Prerequisites messages above for the GitLab/Jira wording).

**Non-idempotent provider writes are exempt from that global retry rule.** A comment POST that returns
`timeout` or `server_error` may already have succeeded, so do not blindly retry it. GitHub uses complete
paginated readback plus the deterministic marker/body hash and retries at most once only when absence is proven.
This recovery path guarantees no duplicate POST.
GitLab posting profiles do not guarantee complete discussion/note readback: on a GitLab
ambiguous write, do not read back or retry; report delivery uncertain, identify the possibly accepted
body and already-posted partial state, and stop all remaining provider writes. Phase 4 applies the
selected provider rule separately at every write boundary.

## Capability detection

Before posting-mode degradation, require the selected provider's **complete read pair**: target
metadata/current head plus changed files/diff hunks. A metadata-only or diff-only connector is
`unavailable`, even if it exposes write tools; writes never compensate for a missing read. A complete
read pair with no writes is valid read-only access and selects `chat-only`. For GitHub, posting also
requires both paginated complete review-comment readback and paginated complete issue-comment
readback for every posting-enabled profile. A `metadata+files+writes` surface without either complete
comment readback is `chat-only`, because it cannot deduplicate or recover an ambiguous
non-idempotent POST. A complete read pair plus the required write and readback capabilities selects
`full`, `summary-only`, or `general-only` as described below.

**GitLab target:** inspect connected GitLab MCP tool descriptors (Cursor Settings → MCP, or each server's
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

For **each** connected GitLab MCP server, first verify `get_merge_request` plus a complete diff/files
read operation, then detect its profile and record `{ server_name, GITLAB_API_URL, posting_mode }`.
Metadata-only and diff-only servers are unavailable. When the resolved MR belongs to a specific
instance, use that instance's server and apply its posting mode for all Phase 4 operations. If two
servers have different posting modes, announce the active mode for this MR explicitly.

**GitHub target:** inspect GitHub App/MCP descriptors for semantic read (`get_pull_request`, files/diff,
comments, checks) and comment operations. Prefer the app/MCP. If equivalent read tools are absent, run
`gh auth status --hostname <review_target.host>`; only an authenticated exact-host result enables the
`gh` fallback, and only when the normalized target uses the scheme's default port. For any non-default
port, CLI fallback is unavailable under the prerequisite above; do not probe it. Record one profile:

| GitHub profile | Capability | Posting mode |
|---|---|---|
| full | PR read + paginated complete review-comment and issue-comment readback + inline review comment + issue comment | `full` |
| summary-only | PR read + paginated complete review-comment and issue-comment readback + issue comment | `summary-only` |
| CLI read-only | exact-host authenticated `gh` read path | `chat-only` |
| unavailable | no exact-host read capability | stop |

The GitHub metadata and files/diff operations are an inseparable read pair: metadata-only and diff-only
profiles are unavailable; a complete read pair with no safe comment-write/readback pair is read-only
`chat-only`. Comment reads must enumerate every page; first-page-only access is not complete. For
GitHub `full`, comments are standalone line comments plus one issue summary; do not use
`add_review_to_pr`, `APPROVE`, `REQUEST_CHANGES`, or a review-submission endpoint. Record
`{provider, host, source, read_target, read_diff, read_comments, read_ci, post_inline, post_summary}`
as `provider_capabilities` and announce the provider, host, and active posting mode.

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
`chat-only`), provider, and host. See `examples.md` for announcement examples.
