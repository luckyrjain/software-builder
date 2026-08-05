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
