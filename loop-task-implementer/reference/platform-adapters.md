# Platform Adapters

The skill remains the source of truth. Platform files should only help discovery and invocation; do not duplicate the full workflow into every platform configuration.

## Claude Code

Install the repository skill folder under either supported location:

```bash
mkdir -p ~/.claude/skills
cp -R loop-task-implementer ~/.claude/skills/loop-task-implementer
```

or:

```bash
mkdir -p ~/.agents/skills
cp -R loop-task-implementer ~/.agents/skills/loop-task-implementer
```

Natural-language examples:

- “Use the loop-task-implementer skill for issue 42.”
- “Resume loop-task-implementer on the current branch.”
- “Act as the read-only Lens A reviewer using loop-task-implementer.”

Use subagents or fresh sessions for role isolation. Use worktrees when Builder and Reviewer need separate repository contexts.

## ChatGPT / Codex

Install under the runtime’s supported skills directory, commonly:

```bash
mkdir -p ~/.agents/skills
cp -R loop-task-implementer ~/.agents/skills/loop-task-implementer
```

Natural-language examples:

- “Use loop-task-implementer to implement the next GitHub issue.”
- “Run the Builder role, then dispatch isolated Reviewer lenses.”
- “Adjudicate the current PR findings using loop-task-implementer.”

Prefer separate Codex tasks or fresh agent sessions. Use repository connectors for authoritative remote state and local git for implementation when available.

## Cursor

Keep the canonical skill folder in the repository and use `.cursor/rules/loop-task-implementer.mdc` for discovery.

Natural-language examples:

- “Use loop-task-implementer for this task.”
- “Continue the loop-task-implementer loop.”
- “Review this PR with Lens B only.”

Use background agents, separate chats, or worktrees as available. Do not pass implementation chat history into Reviewer chats.

## Kiro

Keep the canonical skill folder in the repository and use `.kiro/steering/loop-task-implementer.md` for discovery.

Natural-language examples:

- “Use the loop-task-implementer steering workflow for this spec task.”
- “Resume the Builder role.”
- “Run an isolated Lens A review.”

Use Kiro specs for task requirements, but keep workflow state separate from product requirements.

## Sequential role simulation (last-resort fallback)

Use only when the host has no subagent, fresh-session, or worktree primitive at all. This is the
riskiest isolation mode — it runs every role in the same conversation, so an explicit context reset
is not optional narration, it is a concrete step:

1. Before switching role, write and keep only a **role handoff note** — the exact fields
   `workflow/orchestrator.md` §6 lists for the neutral review package (or the Builder inputs list,
   when switching to Builder). Discard everything else from working memory: prior role's scratchpad,
   self-review language, PR narrative, branch/commit-message framing.
2. State explicitly, in the conversation, which role is now active and that prior-role reasoning is
   being disregarded — e.g. "Switching to Reviewer, Lens A. Ignoring all Builder reasoning above;
   working only from the handoff note below."
3. Re-derive facts the new role needs from the repository directly (re-read the diff, re-run checks)
   rather than trusting a summary carried over from the prior role's turn.
4. Never let the same turn both implement/fix code and adjudicate whether that fix is acceptable —
   even in sequential simulation, adjudication happens only after the role-switch step above.

If you cannot honestly perform steps 1–3, do not claim role isolation — report degraded-mode findings
as `NEEDS_EVIDENCE` rather than `PROPOSED_BLOCKING`/`CLEAN`, since the review is not truly independent.

**This primitive is `NOT_ISOLATED`, not a weaker form of independent review, for security-sensitive
diffs.** Even when steps 1–4 above are honestly followed, a model cannot reliably discard prior-role
reasoning from the same context the way a real process/session boundary does — the reset is a discipline,
not a guarantee. `workflow/orchestrator.md` §7 records this primitive's `isolation_status` as
`NOT_ISOLATED` whenever the diff touches authentication, authorization, secrets/credential handling, or a
trust boundary, and §17's completion gates treat a `NOT_ISOLATED` lens on such a diff as an open blocking
finding — not a `CLEAN` verdict with a footnote. Prefer escalating for a genuinely isolated primitive
(subagent, fresh session, or worktree) over completing a security-sensitive task on this fallback alone.

## Generic agent fallback

For an agent without skill discovery:

1. Provide `loop-task-implementer/SKILL.md`.
2. State the active role.
3. Provide only that role’s prompt.
4. Provide the task and objective evidence.
5. Do not provide other roles’ private context.

Example:

```text
Use the attached loop-task-implementer skill.
Active role: Reviewer
Lens: LENS_A
Review commit <sha> against base <sha>.
Return only the structured reviewer report.
```

## Cross-agent handoff envelope

```yaml
skill: loop-task-implementer
role: ORCHESTRATOR | BUILDER | REVIEWER
lens: null | LENS_A | LENS_B
task_id:
repository:
base_commit:
head_commit:
diff_fingerprint:
task_ref:
acceptance_criteria_ref:
repository_policy_ref:
state_ref:
accepted_findings_ref:
authoritative_evidence_refs:
```

Never include hidden reasoning, self-review, previous clean verdicts, or persuasive implementation framing.
