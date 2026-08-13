# Workspace Scope Detection

Load when resolving PR/MR targets without an explicit URL/number (step 4 in Inputs).

This file is the **single source of truth** for the project-level warning text. `workflow/inputs.md` references
it rather than restating it. The warning is **displayed** (informational) — there is no separate
acknowledgment prompt; the user choosing a PR/MR from the list is the gate before any review or posting.

## Single-repo vs project-level scope

| Scope | How to detect | Review listing |
|-------|---------------|------------|
| **single-repo** | Workspace root = `git rev-parse --show-toplevel` and one provider remote | Open PRs/MRs for that repository |
| **project-level** | Workspace root is above the git toplevel, or 2+ provider repositories share the resolved provider and host | Open reviews for those compatible repos |

### Detect project-level scope

1. `workspace_root` = Cursor workspace folder.
2. `git rev-parse --show-toplevel` from cwd → if it is a **parent** of workspace or workspace is **not** inside one repo, flag project-level.
3. Locate git repos by finding `.git` directories under the workspace with your file-search tools
   (e.g. `Glob` for `**/.git`), skipping `node_modules`, `vendor`, build dirs, and **git submodule
   internals** (paths inside `.git/modules/` — do not treat submodule checkouts as separate repos).
   Avoid shelling out to `find`.
4. For each repo, `git -C <repo> remote get-url origin` → normalize provider, host, and repository path.
5. Exclude remotes that do not match the target provider and host. Collect unique repository paths.
   **Count > 1** → project-level scope.

## Mandatory warning (project-level)

Show **before listing reviews** and **before starting a review** when scope is project-level:

> ⚠️ **Project-level workspace scope**
>
> This workspace contains **N compatible <GitHub|GitLab> repositories**. Open PRs/MRs will be listed
> (and reviews run) across **all**
> of them — not just the repo for your current file or terminal cwd:
>
> - `group/repo-a`
> - `group/repo-b`
> - …
>
> To limit scope, open a single-repo workspace, pass an explicit PR/MR URL or provider-marked number,
> or name a repository (`review #42 in owner/repo-a` / `review !482 in group/repo-a`).

If the user only asked to list reviews, still show the warning once at the top of the table.

## Aggregated review table

Add **Provider** and **Repository** columns when needed at project level:

| Provider | Repository | Review | Title | Source → Target | Author | Draft | Current branch? |

Fetch per repository on the resolved exact host. **Enumeration depends on the provider/server** (see
`mcp-capabilities.md`): use a list tool when present; for GitLab search-only installs, `search` needs a
query term and is **not exhaustive** — say so in the table caption. Sort by `updated_at`, or by provider,
repository, then review number.

## Narrowing scope

User can escape project-level behavior by:
- Explicit PR/MR URL, `#N in owner/repo`, or `!IID in group/repo`
- Opening the single repo as the workspace root
- Saying "only in `<project>`" → list/review that project only
