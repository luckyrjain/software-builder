# Enforcement layer: `.claude/settings.json`

**gap-backlog A6.** See
`docs/superpowers/specs/2026-09-25-a6-enforcement-layer-design.md` (revision 3) for the full design,
its two rounds of adversarial review, and the reasoning this document only summarizes.

## What this actually is: the first tool-enforced gate in this repository

Every other gate `loop-task-implementer` relies on is **instruction-level**: an LLM reading prose and
choosing to follow it. `orchestrator.md`'s `allowed_actions` capability grant (§1), the write-authority
doctrine in ADR 0008, the CAS-checked `plan_execution_state` this skill maintains — all of these depend
on the agent correctly interpreting and honoring text. Nothing structurally stops a session from
ignoring them if its reasoning goes wrong or if it is misled by untrusted content it read.

`.claude/settings.json` is different in kind, not just in strictness. It is read and enforced by the
Claude Code host itself, outside the model's own reasoning: a `deny`-matched Bash command is refused
by the host before the model's intent matters at all, and an `allow`-matched command runs without the
per-use confirmation prompt the host would otherwise show. This is a real, structural difference from
every other gate in this repository, and it is worth naming plainly rather than leaving implicit.

## What it constrains — and what it does not

`.claude/settings.json` governs exactly one thing: **the Bash commands one local Claude Code session,
running on this repository checkout, may run without a per-use prompt.** That is the entire scope.

It does **not**:

- Constrain any other host or coding agent this skill supports (Cursor, ChatGPT/Codex, GitHub Copilot,
  Kiro) — each has its own permission model, if any, entirely outside this file.
- Reach the git server, CI, or any cross-host boundary. A branch protection rule, a required status
  check, a CODEOWNERS review requirement — none of these are affected by this file in any way. A
  Builder or Reviewer session running under a different host or a different agent gets none of this
  file's protection.
- Protect against a person who runs commands directly in their own shell, outside any agent session.
- Verify that the commands it allows are actually safe in every context they might be invoked from —
  see the no-override tradeoff below for what a narrow `deny` list does and does not buy.

In short: this is a single local session's own safety rail, not a repository-wide or organization-wide
control. Treat it as exactly that scope, no more.

## The no-override tradeoff, stated explicitly

A command matched by `deny` is refused outright, with **no in-session escape hatch** — there is no
prompt, no override flag, no way for the session itself to talk its way past it. This is deliberate,
not an oversight.

The denied set is kept narrow on purpose (`git reset --hard`, `git clean -f`, `git branch -D`,
`git merge`, `rm -rf`), and each entry is one this repository's own standing doctrine already names as
an operation that **must never run autonomously** — always destructive, always without a
straightforward undo, and never something a task's own text should be able to talk an agent into
running on its own judgment. Because the set stays this narrow, the friction of "no escape hatch" stays
narrow too: a human who genuinely needs one of these operations runs it themselves, outside the agent,
or edits `.claude/settings.json` directly to change what the file allows. That is accepted friction, not
a gap to be routed around.

This repository has direct, recent experience with the alternative failure mode: a mechanism that ends
up too restrictive for actual solo-maintainer use gets removed rather than fixed (see F1's
review-evidence-gate removal, `docs/superpowers/specs/2026-09-25-a6-enforcement-layer-design.md`'s
revision history for the cross-reference). A silent, undocumented "there is no way around this" is
exactly the kind of friction that invites exactly that failure. Naming the tradeoff here, plainly, is
this design's mitigation for it — not a heavier escape-hatch mechanism, which would reopen the same
exploit surface the narrow `deny` list exists to close.

## Why the highest-value operations are not on the `allow` list at all

`git add`, `git commit`, `git push`, `gh pr create`, and `gh pr comment` — the operations a Builder
actually performs most often — are **not** allow-listed in the current `.claude/settings.json`, despite
being exactly the operations this template would most reduce friction for. This is a deliberate choice,
made after two full rounds of adversarial security review, not an oversight worth "fixing" by adding
them back.

Revision 1 of the design allow-listed prefix patterns for these commands and a working, zero-prompt
secret-exfiltration chain was found against it (`git add -f .env && git commit -m wip --no-verify &&
git push origin claude/exfil-1`). Revision 2 tightened the patterns and a second review round still
found two further bypasses the tighter patterns did not cover: `gh pr comment -F <file>` (posts an
arbitrary local file's contents to a public PR comment in one allowed command) and a `git push origin
claude/foo:main` refspec trick that matches a `claude/*`-scoped allow prefix literally while actually
writing to `main`.

Both rounds converged on the same underlying problem: a prefix/pattern allow list cannot be made
provably safe against a command whose dangerous content lives in a variable argument (a commit message,
a branch name, a comment body) without either confirmed, precise knowledge of exactly how Claude Code's
permission matcher tokenizes and evaluates a compound or flag-appended invocation, or simply not
allow-listing the highest-value targets for this attack class. This repository could not establish the
first with certainty after two dedicated review rounds, so the current `.claude/settings.json` takes the
second: these five commands fall through to the host's default per-use prompt instead. See the design
spec's `.claude/settings.json content` section (linked above) for the full chain-by-chain history if you
are evaluating whether to widen this list later — do not re-add these patterns without that context.

## What is left, and why it is believed safe

Every remaining `allow` entry is either strictly read-only (`git status`, `git diff`, `git log`,
`git fetch origin`, `gh pr view`, `gh pr checks`, `gh pr diff`) or an exact, argument-free, non-destructive
fixed command (`git checkout -b claude/*` only ever creates a new branch, never overwrites one;
`git checkout main` only switches context) plus the loop-task-implementer tooling itself
(`run_log.py`, `validate_loop_lifecycle.py`, `pytest`, `make lint-*`). None of these accept free-form
trailing content with a "safe verb, dangerous flag or argument" shape for an attacker to exploit — that
absence of free-form content is precisely why they were judged safe to allow-list where `add`/`commit`/
`push`/`gh pr create`/`gh pr comment` were not.

## This has not been verified against the live host

Every claim in this document about what `.claude/settings.json` actually does — that `deny` wins over a
broader `allow` match, that an `allow` entry truly never prompts, that a `deny` entry is genuinely
refused — is the *documented, expected* behavior of Claude Code's permission system as of this design's
authoring. **It has not been executed against the live host and confirmed.** The design's own Rollout
Phase 1 names this as a required, not optional, follow-up: a person must open a fresh Claude Code
session on this repository after this file merges and manually exercise each `allow` entry (confirm it
doesn't prompt) and each `deny` entry (confirm it is genuinely refused) before treating this template as
load-bearing. Do not assume this file works as described until that verification has actually happened.
