# Workspace Scope Detection

Load when resolving MR targets without an explicit URL/IID (step 4 in Inputs).

This file is the **single source of truth** for the project-level warning text. `workflow/inputs.md` references
it rather than restating it. The warning is **displayed** (informational) — there is no separate
acknowledgment prompt; the user choosing an MR from the list is the gate before any review or posting.

## Single-repo vs project-level scope

| Scope | How to detect | MR listing |
|-------|---------------|------------|
| **single-repo** | Workspace root = `git rev-parse --show-toplevel` and only one GitLab `origin` under workspace | Open MRs for that one `project_id` |
| **project-level** | Workspace root is **above** the git toplevel, **or** 2+ distinct GitLab project paths from `origin` under workspace | Open MRs for **every** GitLab repo in workspace |

### Detect project-level scope

1. `workspace_root` = Cursor workspace folder.
2. `git rev-parse --show-toplevel` from cwd → if it is a **parent** of workspace or workspace is **not** inside one repo, flag project-level.
3. Locate git repos by finding `.git` directories under the workspace with your file-search tools
   (e.g. `Glob` for `**/.git`), skipping `node_modules`, `vendor`, build dirs, and **git submodule
   internals** (paths inside `.git/modules/` — do not treat submodule checkouts as separate repos).
   Avoid shelling out to `find`.
4. For each repo, `git -C <repo> remote get-url origin` → normalize to GitLab `group/project` path.
5. Collect unique project paths. **Count > 1** → project-level scope.

## Mandatory warning (project-level)

Show **before listing MRs** and **before starting a review** when scope is project-level:

> ⚠️ **Project-level workspace scope**
>
> This workspace contains **N GitLab repos**. Open MRs will be listed (and reviews run) across **all**
> of them — not just the repo for your current file or terminal cwd:
>
> - `group/repo-a`
> - `group/repo-b`
> - …
>
> To limit scope, open a single-repo workspace, pass an explicit MR URL/IID, or name a project
> (`review !482 in group/repo-a`).

If the user only asked to list MRs, still show the warning once at the top of the table.

## Aggregated MR table

Add a **Project** column when scope is project-level:

| Project | IID | Title | Source → Target | Author | Draft | Current branch? |

Fetch per project. **Enumeration depends on the server** (see `mcp-capabilities.md`): use a list tool
when present; otherwise `search` (which needs a query term and is **not exhaustive**) — say so in the
table caption. Sort by updated_at, or by project then IID.

## Narrowing scope

User can escape project-level behavior by:
- Explicit MR URL or `!IID in group/repo`
- Opening the single repo as the workspace root
- Saying "only in `<project>`" → list/review that project only
