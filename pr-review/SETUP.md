# PR Review Skill for Cursor — Setup


## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-08-09 |
| **Review cadence** | Quarterly — or when pinned MCP package versions change |
| **External services** | GitLab MCP or GitHub App/MCP or gh, Jira MCP (optional) |

See [setup-freshness.md](../docs/skill-framework/shared/setup-freshness.md) for the shared contract.
A Cursor Agent Skill that reviews a GitHub pull request or GitLab merge request and posts severity-labelled
comments when the connected provider capability supports posting. Uses provider MCP/App tools (or `gh`
read fallback for GitHub) for code and
**Atlassian/Jira MCP** (optional — skip if you don't need Jira acceptance-criteria checks) for ticket
context.

## Quickstart

Install the skill first for either provider: clone `software-builder` (root
[README.md § Install](../README.md#install)), run `make install-pr-review`, and restart Cursor.

### GitHub quickstart

1. Connect a GitHub App/MCP with PR read/comment access, or install `gh` for a read-only fallback.
2. For CLI fallback, run `gh auth login --hostname github.com` and verify with
   `gh auth status --hostname github.com` (substitute an exact default-port GHES host when applicable).
3. Run `/pr-review https://github.com/owner/repo/pull/42` for an open PR.

This path does not require a GitLab PAT, GitLab MCP, Node.js, or an MR. CLI fallback is chat-only;
posting requires connected GitHub standalone inline-comment and issue-comment capabilities. For GHES
on a non-default port, CLI fallback is unavailable; connect a GitHub App/MCP complete read pair for the
exact authority instead.

### GitLab quickstart

1. Create a GitLab PAT with `api` scope
   ([§1](#create-a-gitlab-personal-access-token-pat)) and export it as
   `GITLAB_PERSONAL_ACCESS_TOKEN`.
2. Paste the `@zereight/mcp-gitlab` block from
   [§3](#gitlab--full-inline-posting-zereightmcp-gitlab) into `~/.cursor/mcp.json`, set the token
   reference and `GITLAB_API_URL`, then restart Cursor.
3. Run `/pr-review !<some-open-MR-IID>` in a repository you can access.

Jira is optional for both providers; add it later from [§3 Jira / Atlassian](#jira--atlassian) for
acceptance-criteria checks.

Stuck on any step? Jump to [§6 Troubleshooting](#6-troubleshooting).

### GitHub.com and GitHub Enterprise Server

Prefer a connected GitHub App/MCP that can read pull requests and create standalone inline and issue
comments. For read-only fallback, authenticate the GitHub CLI for the exact host:

```bash
gh auth login --hostname github.com
gh auth status --hostname github.com

# GitHub Enterprise Server
gh auth login --hostname github.example.com
gh auth status --hostname github.example.com
```

Use `/pr-review https://github.com/owner/repo/pull/42` or the equivalent GHES URL. A `gh` fallback is
chat-only; full or summary posting requires GitHub comment capabilities. The skill never approves,
requests changes, merges, closes, or submits a GitHub review verdict.

HTTP GitHub and GHES review URLs, including implicit or explicit port 80, are rejected during input
validation. Use an HTTPS review URL; the skill never upgrades HTTP or sends an App/MCP or `gh` request
to a substituted HTTPS authority.

`gh` host selection does not safely represent a GHES authority with a non-default port. For a URL such
as `https://forge.company.internal:8443/owner/repo/pull/42`, CLI fallback is unavailable for auth,
discovery, PR metadata, diff, checks, comments, and API reads. Do not authenticate or query the
portless hostname as a substitute. Connect a GitHub App/MCP that supplies both PR metadata/current head
and changed files/diff hunks for exactly `forge.company.internal:8443`; without that complete read pair,
the review stops.

## Ambient discovery is intended

This skill deliberately does **not** set `disable-model-invocation` in its frontmatter, so the agent
can auto-apply it when you ask to review a GitHub PR or GitLab MR in natural language — e.g. "review this pr …",
"review !482", "re-review" — as well as `/pr-review`. Leave it unset unless you want invocation to
be slash-command-only.

## What's in here

### Provider inventory

- **Shared:** `SKILL.md`, provider-neutral workflow phases, severity/finding policy, Jira integration,
  and summary templates.
- **GitHub:** App/MCP PR reads and standalone comments, exact-host `gh` read fallback,
  `reference/github-inline-comments.md`, and `scripts/github-comment-positions.py`.
- **GitLab:** MR/diff/pipeline MCP flow, inline threads or general notes,
  `reference/gitlab-inline-comments.md`, and `scripts/diff-to-positions.py`.

```
.cursor/skills/pr-review/
├── SKILL.md                    # thin orchestrator — workflow index + guardrails
├── workflow/
│   ├── inputs.md               # MR resolution, list MRs
│   ├── phase-0.md              # MCP capability detection
│   ├── phase-1.md              # gather steps
│   ├── phase-2.md              # review, dedupe, root-cause grouping
│   ├── phase-2-3-gate.md       # re-run decision
│   ├── posting.md              # Phase 3 confirm + Phase 4 post
│   └── phase-5.md              # executive summary, Jira write-back
├── SETUP.md                    # this file
├── examples.md
├── examples/
│   └── review-rules.yaml       # starter template for repos
├── scripts/
│   ├── diff-to-positions.py         # helper for inline comment anchoring
│   └── pr_review_policy_guards.py   # recommendation matrix + finding gates (pytest)
├── tests/
│   ├── test_diff_to_positions.py
│   ├── test_phase5_metadata_footer.py
│   ├── test_pr_review_policy_guards.py
│   └── fixtures/
│       └── phase5-review-metadata.yaml
└── reference/                  # lazy-loaded modules — full "when to load what" index: reference/lazy-load-index.md
    ├── mcp-capabilities.md     # tool matrix per GitLab/Jira server
    ├── severity-rubric.md
    ├── review-checklist.md
    ├── finding-pipeline.md     # authoritative detect → judge emit order
    ├── finding-gates.md        # don't-guess + execution path + non-negotiable (Phase 2 single load)
    ├── review-rules.md         # repo review-rules.yaml schema
    ├── smoke-test.md           # post-install verification + script self-test
    └── … (remaining reference/*.md — see lazy-load-index.md for the complete, authoritative list)
```

## 1. Requirements

### Shared requirements

- **Cursor 2.4+** with Agent Skills enabled (Settings → Rules → import skills, or project
  `.cursor/skills/`). Skills ship in stable Cursor builds as of early 2026; if `/pr-review` does not
  appear, update Cursor and restart.
- **Jira/Atlassian** account. Official remote server uses OAuth. **Optional** — the review runs fine
  without it; you just lose the acceptance-criteria checklist against linked Jira tickets.

### GitHub requirements

- A connected GitHub App/MCP for PR reads and posting, or `gh` authenticated to the exact host for
  chat-only read fallback.
- GHES on a non-default port requires a complete GitHub App/MCP read pair for that exact authority;
  CLI fallback is unavailable.
- No GitLab PAT, GitLab MCP, or Node.js requirement.

### GitLab requirements

- **GitLab PAT** with `api` scope for the `@zereight/mcp-gitlab` path (read MRs; write comments when
  posting), or the Cursor GitLab plugin/Duo MCP alternative.
- Node.js 18+ only when running `@zereight/mcp-gitlab` through `npx`; the Cursor plugin does not need it.

### Create a GitLab Personal Access Token (PAT)

1. Go to **GitLab → User menu (top-right) → Preferences → Access tokens** (or your self-hosted equivalent: `https://gitlab.yourco.com/-/user_settings/personal_access_tokens`).
2. Click **Add new token**.
3. Give it a descriptive name (e.g. `cursor-pr-review`).
4. Set an expiry date — **90 days or less** is recommended; set a calendar reminder to rotate.
5. Select scopes:
   - **`api`** — required for reading MRs, diffs, pipelines, and posting comments
   - Do **not** grant `write_repository` or `sudo` unless you have a specific reason
6. Click **Create personal access token** and **copy it immediately** — GitLab shows it only once.

**One PAT covers all repos on the same GitLab instance** — `api` scope is instance-wide, not per-repo.

**Multiple GitLab instances** (e.g. `https://gitlab.skillzi.org` and `https://gitlab.yourco.com`): each instance needs its own PAT and its own `mcpServers` entry. See § 3 — Multiple GitLab instances below.

### Store the token safely

**Never paste the raw token into `mcp.json`** — that file may be committed to git.

Set it as a shell environment variable:

```bash
# Add to ~/.zshrc or ~/.bashrc (not to any repo file)
export GITLAB_PERSONAL_ACCESS_TOKEN="glpat-..."
```

Then reload: `source ~/.zshrc`

The `mcp.json` snippet in § 3 already uses `"${GITLAB_PERSONAL_ACCESS_TOKEN}"` — this references the env var and keeps the raw token out of config files.

### Token security checklist

- [ ] Token has an expiry date set
- [ ] Token is stored in shell profile, not in any file tracked by git
- [ ] `mcp.json` uses `${GITLAB_PERSONAL_ACCESS_TOKEN}` (env var reference), not the raw token
- [ ] Scope is `api` only — no `sudo` or `write_repository`
- [ ] `.gitignore` includes `mcp.json` if it lives inside a repo directory

## 2. Install the skill

Already cloned `software-builder`? Run `make install-pr-review` (or `bash scripts/install.sh pr-review`) from
the repo root — see the root [README.md § Install](../README.md#install) for the full clone/install
steps and single-skill install targets, which apply the same way here.

Restart Cursor so skills and MCP servers reload.

### Claude Code

`make install` / `bash scripts/install.sh` above already installs this skill for Claude Code too
(default installs to both editors). For Claude Code **only**: `make install-claude-pr-review` (or
`bash scripts/install.sh --agent claude-project pr-review` from inside your repo). MCP servers: reuse
the same JSON snippets from § 3 below, placed in `.mcp.json` / via `claude mcp add-json` instead of
`~/.cursor/mcp.json` — the GitLab plugin / Duo MCP path in § 3 is Cursor-GUI-only, so use the
`@zereight/mcp-gitlab` inline-posting entry instead. Full mapping:
[claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).

### Kiro / in-repo discovery

Working directly in this repo (not via an installed copy)? `.cursor/rules/pr-review.mdc` and
`.kiro/steering/pr-review.md` point Cursor/Kiro at `pr-review/SKILL.md` without an install step.

## 3. Configure MCP servers (`.cursor/mcp.json`)

All snippets below go inside the top-level `mcpServers` object in `~/.cursor/mcp.json`. Use
environment variables for tokens — never commit real PATs.

```json
{
  "mcpServers": {
    "gitlab": { },
    "atlassian": { }
  }
}
```

Replace the inner `{ }` placeholders with one of the server configs below.

Two ways to connect GitLab. **Use `@zereight/mcp-gitlab` unless you have a reason not to** — it's the
richer experience (inline comments on the diff, not just a general note) and only needs Node.js. Use
the Cursor plugin instead only if you can't run `npx` locally or your org already standardizes on it.

### GitLab — full inline posting (`@zereight/mcp-gitlab`) — recommended

[`@zereight/mcp-gitlab`](https://github.com/zereight/gitlab-mcp) exposes MR threads, notes, and drafts.
The version below is pinned (not `-y @zereight/mcp-gitlab` alone, which resolves to whatever is newest
at `npx` run time) — a server receiving a GitLab token with API scope should not be silently upgraded
without a deliberate version bump. Check [the package's releases](https://github.com/zereight/gitlab-mcp/releases)
before bumping the pinned version here.

```json
"gitlab": {
  "command": "npx",
  "args": ["-y", "@zereight/mcp-gitlab@2.1.46"],
  "env": {
    "GITLAB_PERSONAL_ACCESS_TOKEN": "${GITLAB_PERSONAL_ACCESS_TOKEN}",
    "GITLAB_API_URL": "https://gitlab.example.com/api/v4",
    "GITLAB_READ_ONLY_MODE": "false"
  }
}
```

- Set `GITLAB_PERSONAL_ACCESS_TOKEN` in your shell or reference `"${GITLAB_PERSONAL_ACCESS_TOKEN}"`
  in config (the package also accepts `GITLAB_TOKEN` as an alias).
- Self-hosted: set `GITLAB_API_URL` to `https://gitlab.yourco.com/api/v4`.
- `GITLAB_READ_ONLY_MODE` must be `"false"` for posting.

**Linux only — `npx` path issue:** On Linux, Cursor may use its own bundled npm which fails with
`npm ERR! enoent … /usr/share/cursor/resources/app/resources/lib`. Fix: use the full path to your
system `npx`:

```bash
which npx   # e.g. /usr/bin/npx  or  /home/you/.nvm/versions/node/v20.x.x/bin/npx
```

Then set `"command": "/usr/bin/npx"` (your actual path) in the snippet above. Alternatively,
install globally and skip `npx` entirely:

```bash
npm install -g @zereight/mcp-gitlab
```

```json
"gitlab": {
  "command": "mcp-gitlab",
  "args": [],
  "env": { ... }
}
```

Restart Cursor after either fix.

### GitLab — Cursor plugin / official Duo MCP (`general-only`) — alternative

No Node.js/`npx` needed, but posts only a **general MR comment** via `create_workitem_note` — not
inline on the diff. `/pr-review` detects this in Phase 0 and shows a mandatory ⚠️ warning before
posting.

**Configure via Cursor Settings → MCP → Add GitLab** (OAuth or PAT). The Cursor GitLab plugin is not
activated by pasting a `url` entry into `mcp.json` — use the GUI installer. For self-hosted GitLab,
follow your admin's Cursor/GitLab Duo setup guide.

### Multiple GitLab instances

If your team uses more than one self-hosted GitLab (e.g. `gitlab.skillzi.org` and `gitlab.yourco.com`), add a separate entry per instance. Each needs its own PAT — PATs are scoped to one host.

**1. Create a PAT on each instance** (follow the steps in § 1 for each host).

**2. Export each token under a distinct name:**

```bash
# Add to ~/.zshrc or ~/.bashrc
export GITLAB_SKILLZI_TOKEN="glpat-..."
export GITLAB_SECONDARY_TOKEN="glpat-..."
```

**3. Add both entries to `~/.cursor/mcp.json`:**

```json
{
  "mcpServers": {
    "gitlab-skillzi": {
      "command": "npx",
      "args": ["-y", "@zereight/mcp-gitlab@2.1.46"],
      "env": {
        "GITLAB_PERSONAL_ACCESS_TOKEN": "${GITLAB_SKILLZI_TOKEN}",
        "GITLAB_API_URL": "https://gitlab.skillzi.org/api/v4",
        "GITLAB_READ_ONLY_MODE": "false"
      }
    },
    "gitlab-secondary": {
      "command": "npx",
      "args": ["-y", "@zereight/mcp-gitlab@2.1.46"],
      "env": {
        "GITLAB_PERSONAL_ACCESS_TOKEN": "${GITLAB_SECONDARY_TOKEN}",
        "GITLAB_API_URL": "https://gitlab.yourco.com/api/v4",
        "GITLAB_READ_ONLY_MODE": "false"
      }
    }
  }
}
```

**How the skill picks the right server:** when you pass a full MR URL (e.g.
`https://gitlab.skillzi.org/group/repo/-/merge_requests/42`), the skill parses each `GITLAB_API_URL`
and compares its normalized authority (lowercase hostname plus explicit/effective port) for exact
equality. It never uses a substring, prefix, or hostname-only match. If you pass only an IID (`!42`),
the skill derives the project and authority from `git remote get-url origin` — make sure your local
`origin` points to the correct instance and port.

**Phase 0 warning:** the skill warns if the MR URL authority doesn't uniquely match a configured
`GITLAB_API_URL`. If you see this, check that the right server entry and port exist in `mcp.json`.

### Jira / Atlassian

Official Rovo server (OAuth on first use):

```json
"atlassian": {
  "url": "https://mcp.atlassian.com/v1/mcp"
}
```

- **Jira Server / DC:** use [`sooperset/mcp-atlassian`](https://github.com/sooperset/mcp-atlassian).
- Many Atlassian MCP installs are **read-only** — Jira comment/transition write-back may be unavailable.

Confirm both servers show connected in Cursor Settings → MCP. See `reference/mcp-capabilities.md`
for the full matrix.

## 4. Use it

Invoke with `/pr-review` or natural language. The skill auto-invokes when a request clearly targets a
supported PR or MR.

### Use with GitHub

- `/pr-review https://github.com/owner/repo/pull/42`
- `review PR #42 in owner/repo`
- `/pr-review` — lists open PRs in a GitHub-scoped workspace, then asks you to choose when needed

### Use with GitLab

- `/pr-review https://gitlab.com/group/repo/-/merge_requests/482`
- `/pr-review !482 in backend/payments` — or `review !482 in backend/payments`
- `/pr-review` — lists open MRs, then reviews your current branch's MR (or asks you to pick)

For the full invocation table and edge cases, see [examples.md](examples.md).

**`review and post …`** does **not** unconditionally skip the Phase 3 confirmation gate. It skips
confirmation **only** when the posting mode is `full` or `summary-only` and the PR/MR is not a draft.
`general-only` always shows its ⚠️ warning and requires confirmation, and any draft PR/MR always
requires confirmation.

Phase 0 announces posting mode and workspace scope. Warnings when:
- **`general-only`** — comments are general MR notes, not inline on the diff.
- **Project-level workspace** — open MRs span all GitLab repos in the workspace.

## 5. Tuning

- **Tool-limit (~40 tools):** `"GITLAB_DENIED_TOOLS_REGEX": "wiki|milestone|epic|webhook"` in `mcp.json`.
- **Inline thread cap:** default **15** per review; override in `reference/gitlab-inline-comments.md`
  §Configuring the thread cap (not `domain-overrides.md`).
- **Severity bar:** edit `reference/severity-rubric.md`.
- **Domain focus (preferred):** add `review-rules.yaml` at the repo root or
  `.cursor/skills/pr-review/review-rules.yaml` — see `reference/review-rules.md` and
  `examples/review-rules.yaml`. Optional `persona:` key sets default review lens.
- **Domain focus (fallback):** edit `reference/domain-overrides.md` or repo-local
  `.cursor/skills/pr-review/domain-overrides.md` when no YAML is present.
- **Repo conventions:** keep `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, and Cursor rules current — the
  skill reads them during review.
- **Repo-local overrides:** any skill file can be overridden per-repo at
  `.cursor/skills/pr-review/<filename>` matching the skill file name (e.g.
  `.cursor/skills/pr-review/gitlab-inline-comments.md` for a custom thread cap); the repo-local copy
  takes precedence over the installed default when present.

## 6. Troubleshooting

### GitHub troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| GitHub `chat-only` — nothing posts | `gh` is read-only for this workflow or connected App/MCP lacks comment tools | Connect GitHub standalone inline-comment and issue-comment capabilities; verify the exact target host |
| GitHub PR lookup fails on GHES | CLI authenticated to a different host | Run `gh auth status --hostname <exact-host>` and use the canonical GHES PR URL |
| GHES URL uses a non-default port | `gh` cannot safely retain the target authority | CLI fallback is unavailable; connect a complete GitHub App/MCP read pair bound to the exact host and port |
| Current-branch PR appears missing | An old command used the 30-item CLI default | Use the documented `gh pr list --limit 1000 --head <branch>` path; exactly 1000 results is truncation, not “none” |

### GitLab troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `/pr-review` not in command list | Skill not installed or Cursor not restarted | Run `make install`; restart Cursor |
| `401 Unauthorized` from GitLab MCP | Wrong `GITLAB_API_URL` or token from different host | Point `GITLAB_API_URL` at your instance; PAT from same host |
| `authenticated: false` in health check | Expired/revoked PAT or missing `api` scope | Regenerate PAT with `api` scope |
| Inline comments fail with `line_code` | GitLab version/API needs `line_code`/`line_range` in position | Skill reads `line_code` from the diff API and retries once with `line_range`, then falls back to a summary note (see `reference/gitlab-inline-comments.md` § line_code handling) |
| Only general MR notes, no inline threads | Official GitLab plugin (`general-only`) | Install `@zereight/mcp-gitlab` for `full` mode |
| Jira ticket not found | Key absent from title, branch, description, labels, and remote links | Skill checks all of those paths — add the key to any one (title/branch/description/label) |
| `chat-only` — nothing posts | `GITLAB_READ_ONLY_MODE=true` or no write tools | Set read-only false; verify write tools in MCP settings |
| Open MR list empty (search-only MCP) | `search` needs a query term | Pass explicit MR URL/IID |
| Jira tools 401 / empty after OAuth | Session expired or wrong Atlassian cloud | Re-auth in Cursor MCP settings; run `getAccessibleAtlassianResources`; confirm cloud URL matches your site |
| `npm ERR! enoent … /usr/share/cursor/resources/app/resources/lib` (Linux) | Cursor's bundled npm can't find its own lib path on Linux | Use full system path: set `"command": "/usr/bin/npx"` (run `which npx` to find yours). Or install globally: `npm install -g @zereight/mcp-gitlab` and use `"command": "mcp-gitlab"`. Restart Cursor. |

## Notes

- **Contributors:** after changing `scripts/diff-to-positions.py`, run `make lint-pr-review` from the
  repo root (`py_compile` + `pytest pr-review/tests/`). Install pytest with `python3 -m pip install pytest`.
- Never auto-approves the MR in GitLab.
- Secrets flagged Critical; value never echoed.
- Re-runs detect `<!-- cursor-pr-review -->` and review only new commits.
- GitHub `chat-only` — run `gh auth status --hostname <host>`; a GitHub App/MCP with comment access is
  required for posting. The skill never approves or merges.

## Framework conventions

- Index: [docs/skill-framework/README.md](../docs/skill-framework/README.md)
- Confidence: [confidence-bands](../docs/skill-framework/shared/confidence-bands.md)
- Escalation: [cross-skill-escalation](../docs/skill-framework/shared/cross-skill-escalation.md)
- Smoke tests: [smoke-test-conventions](../docs/skill-framework/shared/smoke-test-conventions.md)
- Examples: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md)
- Phases: [phase-glossary](../docs/skill-framework/shared/phase-glossary.md)
- Post-actions: [post-action-templates](../docs/skill-framework/shared/post-action-templates.md)
