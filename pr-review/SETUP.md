# PR Review Skill for Cursor — Setup

A Cursor Agent Skill that reviews a GitLab merge request and posts severity-labelled comments back
onto it when the connected GitLab MCP supports posting. Uses **GitLab MCP** for the code and
**Atlassian/Jira MCP** (optional — skip if you don't need Jira acceptance-criteria checks) for ticket
context.

## Quickstart

Already have a GitLab PAT and Cursor 2.4+? This is the whole path — details for each step are below.

1. `git clone` the `ai-skills` repo (see root [README.md § Install](../README.md#install)), then `make install-pr-review`. Restart Cursor.
2. Create a GitLab PAT with `api` scope ([§1](#create-a-gitlab-personal-access-token-pat)) and export it as `GITLAB_PERSONAL_ACCESS_TOKEN`.
3. Paste the `@zereight/mcp-gitlab` block from [§3](#gitlab--full-inline-posting-zereightmcp-gitlab) into `~/.cursor/mcp.json`, swap in your token and `GITLAB_API_URL`, restart Cursor.
4. Skip Jira for now — add it later from [§3 Jira / Atlassian](#jira--atlassian) if you need AC checks.
5. Run `/pr-review !<some-open-MR-IID>` in a repo you have access to.

Stuck on any step? Jump to [§6 Troubleshooting](#6-troubleshooting).

## Ambient discovery is intended

This skill deliberately does **not** set `disable-model-invocation` in its frontmatter, so the agent
can auto-apply it when you ask to review a GitLab MR in natural language — e.g. "review this pr …",
"review !482", "re-review" — as well as `/pr-review`. Leave it unset unless you want invocation to
be slash-command-only.

## What's in here

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
│   └── test_pr_review_policy_guards.py
└── reference/
    ├── mcp-capabilities.md     # tool matrix per GitLab/Jira server
    ├── phase-1-gather.md       # CI / coverage / security-scan / merge-train + MR metadata sub-checks
    ├── severity-rubric.md
    ├── review-checklist.md
    ├── fast-path.md            # cost optimization decision tree
    ├── session-context-cache.md  # reuse immutable repo context across re-reviews
    ├── finding-pipeline.md       # authoritative detect → judge emit order
    ├── detection-vs-judgment.md  # detector vs judge separation
    ├── finding-gates.md          # don't-guess + execution path + non-negotiable (Phase 2 single load)
    ├── gold-review-excerpt.md    # format few-shot for Phase 5 executive summary
    ├── pressure-tests.md         # happy/edge/adversarial scenarios + scripted eval map
    ├── dont-guess-gate.md        # stub → finding-gates.md
    ├── non-negotiable-checks.md  # stub → finding-gates.md
    ├── false-positive-suppression.md  # stub → finding-gates.md
    ├── precedence.md             # conflict resolution across modules
    ├── capability-discovery.md   # stack inference from manifests/paths
    ├── review-metrics.md         # optional framework self-metrics
    ├── review-personas.md      # Principal Engineer, SRE, Security, Architect, …
    ├── contextual-severity.md  # adaptive severity by path context
    ├── review-rules.md         # repo review-rules.yaml schema
    ├── domain-overrides.md     # fallback when no review-rules.yaml
    ├── comment-templates.md
    ├── gitlab-inline-comments.md
    ├── incremental-rerun.md    # re-review dedupe rules (snippet hash, resolved threads, squash caveat)
    ├── review-feedback-learning.md  # adapt confidence/frequency from prior bot reviews on this MR
    ├── smoke-test.md           # post-install verification + script self-test
    └── workspace-scope.md      # single-repo vs project-level scope detection
```

## 1. Requirements

- **Cursor 2.4+** with Agent Skills enabled (Settings → Rules → import skills, or project
  `.cursor/skills/`). Skills ship in stable Cursor builds as of early 2026; if `/pr-review` does not
  appear, update Cursor and restart.
- Node.js 18+ — required only for `@zereight/mcp-gitlab` via `npx`. The Cursor GitLab plugin and
  Atlassian Rovo MCP do not need Node.js locally.
- **GitLab PAT** with `api` scope (read MRs; write comments if posting) — see below. **Required.**
- **Jira/Atlassian** account. Official remote server uses OAuth. **Optional** — the review runs fine
  without it; you just lose the acceptance-criteria checklist against linked Jira tickets.

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

Already cloned `ai-skills`? Run `make install-pr-review` (or `bash scripts/install.sh pr-review`) from
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

```json
"gitlab": {
  "command": "npx",
  "args": ["-y", "@zereight/mcp-gitlab"],
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
      "args": ["-y", "@zereight/mcp-gitlab"],
      "env": {
        "GITLAB_PERSONAL_ACCESS_TOKEN": "${GITLAB_SKILLZI_TOKEN}",
        "GITLAB_API_URL": "https://gitlab.skillzi.org/api/v4",
        "GITLAB_READ_ONLY_MODE": "false"
      }
    },
    "gitlab-secondary": {
      "command": "npx",
      "args": ["-y", "@zereight/mcp-gitlab"],
      "env": {
        "GITLAB_PERSONAL_ACCESS_TOKEN": "${GITLAB_SECONDARY_TOKEN}",
        "GITLAB_API_URL": "https://gitlab.yourco.com/api/v4",
        "GITLAB_READ_ONLY_MODE": "false"
      }
    }
  }
}
```

**How the skill picks the right server:** when you pass a full MR URL (e.g. `https://gitlab.skillzi.org/group/repo/-/merge_requests/42`), the skill matches the host to the server whose `GITLAB_API_URL` starts with that host. If you pass only an IID (`!42`), the skill derives the project from `git remote get-url origin` and matches by host — make sure your local `origin` points to the correct instance.

**Phase 0 warning:** the skill warns if the MR URL host doesn't match any configured `GITLAB_API_URL`. If you see this, check that the right server entry exists in `mcp.json`.

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

Invoke with `/pr-review` **or** natural language (e.g. "review this MR …", "review !482"). The skill
auto-invokes when the request clearly targets a GitLab merge request. A few common forms:

- `/pr-review https://gitlab.com/group/repo/-/merge_requests/482`
- `review this pr https://gitlab.com/group/repo/-/merge_requests/482`
- `/pr-review !482 in backend/payments` — or `review !482 in backend/payments`
- `/pr-review` — lists open MRs, then reviews your current branch's MR (or asks you to pick)

For the full invocation table and edge cases, see [examples.md](examples.md).

**`review and post …`** does **not** unconditionally skip the Phase 3 confirmation gate. It skips
confirmation **only** when the posting mode is `full` or `summary-only` **and** the MR is **not** a
draft. `general-only` always shows its ⚠️ warning and requires confirmation, and any draft MR always
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
- GitHub PRs: this skill is GitLab-only and does not support GitHub pull requests.

## Framework conventions

- Index: [docs/skill-framework/README.md](../docs/skill-framework/README.md)
- Confidence: [confidence-bands](../docs/skill-framework/shared/confidence-bands.md)
- Escalation: [cross-skill-escalation](../docs/skill-framework/shared/cross-skill-escalation.md)
- Smoke tests: [smoke-test-conventions](../docs/skill-framework/shared/smoke-test-conventions.md)
- Examples: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md)
- Phases: [phase-glossary](../docs/skill-framework/shared/phase-glossary.md)
- Post-actions: [post-action-templates](../docs/skill-framework/shared/post-action-templates.md)
