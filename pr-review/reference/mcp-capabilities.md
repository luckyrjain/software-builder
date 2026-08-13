# MCP Capability Matrix

> **Re-verify tool names against the connected MCP descriptors in Phase 0 each run** — this matrix is
> indicative, not authoritative. Server versions and Cursor plugin updates change tool names and
> surfaces.

Tool names differ by server. **Discover what is connected before reviewing** — inspect the GitLab MCP
tool descriptors (Cursor Settings → MCP) and set posting mode in Phase 0. Match **capabilities**, not
exact names.

## GitLab servers

Every selected server must expose the **complete read pair**: MR metadata/current head and MR
diff/changed files. Metadata-only and diff-only servers are unavailable and must stop, regardless of
write tools; writes never compensate for a missing read. A complete read pair with no writes is
read-only `chat-only`; a complete read pair plus writes may select a posting mode below.

| Capability | `@zereight/mcp-gitlab` | GitLab Duo / Cursor plugin |
|------------|------------------------|----------------------------|
| Get MR metadata | `get_merge_request` | `get_merge_request` |
| List **all** open MRs | `list_open_merge_requests` ✅ | ❌ no list tool |
| Find open MRs | `list_*` or `search` | `search` only — **requires a query term, not exhaustive** |
| Get diffs | `get_merge_request_diffs` | `get_merge_request_diffs` |
| List discussions | `mr_discussions` | `get_workitem_notes` (read) |
| Post **inline** diff thread | `create_merge_request_thread` | ❌ |
| Post MR summary note | `create_note` | ❌ |
| Post **general** MR comment | varies | `create_workitem_note` ✅ |
| Draft notes | `create_draft_note` | ❌ |

### Posting modes (set in Phase 0)

| Mode | Detected tools | What gets posted | User warning |
|------|----------------|------------------|--------------|
| **full** | `create_merge_request_thread` + note tool | Inline threads + summary | None |
| **summary-only** | `create_note` / `add_merge_request_comment`, no inline | One MR note with `file:line` refs | None |
| **general-only** | `create_workitem_note` only | One general note on the MR (work item API) | **⚠️ Required** — not inline on diff |
| **chat-only** | No write tools | Chat only | Explain how to enable posting |

### Phase 0 detection checklist

```
1. List GitLab MCP tool names.
2. create_merge_request_thread present?  → inline capable
3. create_note OR add_merge_request_comment present?  → MR note capable
4. create_workitem_note present?  → general comment capable
5. list_open_merge_requests / list_merge_requests present?  → can enumerate all open MRs
   (else only `search` with a required term — not exhaustive; or ask the user for the MR)
6. Assign mode (see table above).
7. If general-only → show the mandatory ⚠️ warning once after Phase 0 detection;
   repeat it verbatim in Phase 3 before posting.
```

Announce detected profile, e.g.:

> **MCP check:** GitLab official MCP — mode `general-only`. Inline diff comments unavailable.

### Server profiles (record one per connected GitLab server)

| Profile | Write tools present | Posting mode |
|---------|---------------------|--------------|
| **zereight / full** | `create_merge_request_thread` + a note tool (`create_note`) | `full` |
| **MR-notes** | `create_note` or `add_merge_request_comment`, no inline thread tool | `summary-only` |
| **gitlab-official** | `create_workitem_note` only (no `create_merge_request_thread`) | `general-only` |
| **read-only** | none of the above | `chat-only` |

## Tools referenced by the workflow (phase → tool → fallback)

Capability-match these, not exact names. "Fallback" is what to do when the tool is absent.

| Phase | Purpose | Tool (varies by server) | Fallback if absent |
|-------|---------|-------------------------|--------------------|
| 0 | Detect write surface | tool descriptor listing | Assume `chat-only`; warn |
| 1 | MR metadata, SHAs, draft flag | `get_merge_request` | Cannot run — required |
| 1 | Diffs / review boundary | `get_merge_request_diffs` | `get_merge_request_file_diff` (per file); else stop |
| 1 | Per-file unified diff | `get_merge_request_file_diff` (`unidiff: true`) | Use `get_merge_request_diffs` hunks (headerless) |
| 1 | Changed-file list | `list_merge_request_changed_files` | Derive `new_path`s from `get_merge_request_diffs` |
| 1 | Commit baseline (re-review) | `get_merge_request_commits` | Skip incremental; full review |
| 1 | Approvals for verdict | `get_merge_request_approval_state` | Omit approvals line in verdict |
| 1 | Pipeline status | `get_merge_request_pipelines` | Note pipeline ❓ unavailable |
| 1 | Existing feedback / baseline | `mr_discussions` / `get_workitem_notes` | Treat as first review |
| 4 | Inline thread | `create_merge_request_thread` | `summary-only`/`general-only` per profile |
| 4 | Summary note | `create_note` / `add_merge_request_comment` | `general-only` note, else `chat-only` |
| 4 | General MR comment | `create_workitem_note` | `chat-only` |
| 4 | Draft batch | `create_draft_note` | Post directly (no drafts offered) |
| 5 | Jira write-back | `addCommentToJiraIssue` / `transitionJiraIssue` | Skip — read-only context |

## Atlassian / Jira servers

| Capability | Official Rovo MCP | `sooperset/mcp-atlassian` |
|------------|-------------------|---------------------------|
| Cloud ID | `getAccessibleAtlassianResources` | N/A (Server/DC) |
| Get issue | `getJiraIssue` | `jira_get_issue` (name varies) |
| Search | `searchJiraIssuesUsingJql` | JQL search tool |
| Remote links | `getJiraIssueRemoteIssueLinks` | varies |
| Teamwork graph | `getTeamworkGraphContext` | ❌ |
| Comment on issue | `addCommentToJiraIssue` | varies — **often read-only** |
| Transition issue | `transitionJiraIssue` | varies — **often read-only** |

Only run Jira write-back (Phase 5) if write tools exist. The official Rovo server commonly exposes
**read tools only** (`getJiraIssue`, `getTransitionsForJiraIssue`, search, remote links) with no
`addCommentToJiraIssue` / `transitionJiraIssue` — in that case treat Jira as read-only context and
state: *"Jira write-back skipped — MCP is read-only."*

**On write failure:** Jira comment/transition calls can fail due to permissions, Epic restrictions, or
mandatory workflow fields. Log the error in chat per ticket and continue — Jira write-back must never
halt or roll back a completed GitLab review (see `workflow/phase-5.md`).

## GitHub

GitHub.com and GitHub Enterprise Server are supported through the target host resolved in Inputs. Match
semantic capability, not connector name.

Require a complete read pair of PR metadata/current head plus PR files/diff before classifying posting.
Metadata-only and diff-only connectors are unavailable; writes never compensate for a missing read.
Complete read-only access selects `chat-only`. Every posting-enabled profile also requires both
paginated complete review-comment readback and paginated complete issue-comment readback. A
`metadata+files+writes` connector without either complete readback remains `chat-only`.

| Profile | Read path | Write path | Posting mode |
|---|---|---|---|
| full | PR metadata, files/diff, paginated complete review-comment and issue-comment readback, checks | inline comment + issue comment | `full` |
| summary-only | PR metadata, files/diff, paginated complete review-comment and issue-comment readback | issue comment | `summary-only` |
| CLI read-only | authenticated `gh pr view` + `gh pr diff` on target host | none | `chat-only` |
| unavailable | no MCP/App and no authenticated `gh` on target host | none | stop |

Use a connected GitHub App/MCP first. `gh pr view`, `gh pr diff`, `gh pr list`, and `gh pr checks` do
**not** accept `--hostname`; bind their exact host with repository syntax instead:

```bash
gh pr view <number> --repo <host>/<owner>/<repo> --json headRefOid,isDraft,url
gh pr diff <number> --repo <host>/<owner>/<repo>
```

Command-scoped `GH_HOST=<host>` with `--repo <owner>/<repo>` is also valid. Keep `--hostname` only for
commands that support it (for example `gh auth status --hostname <host>` and `gh api --hostname <host>`).
Never send a GHES request to GitHub.com.
