# Platform Adapters

The skill remains the source of truth. Platform files should only help discovery and invocation; do not duplicate the full workflow into every platform configuration.

## Recommended repository layout

```text
software-builder/
  SKILL.md
  references/
    orchestrator.md
    builder.md
    reviewer.md
    platform-adapters.md
  templates/
    state-schema.yaml
```

## Claude Code

Preferred installation:

```bash
mkdir -p ~/.claude/skills
cp -R software-builder ~/.claude/skills/software-builder
```

Cross-runtime installation:

```bash
mkdir -p ~/.agents/skills
cp -R software-builder ~/.agents/skills/software-builder
```

Natural-language examples:

- “Use the software-builder skill for issue 42.”
- “Resume software-builder on the current branch.”
- “Act as the read-only Lens A reviewer using software-builder.”

Use Claude Code subagents or fresh sessions for role isolation. Use worktrees when Builder and Reviewer need concurrent repository access.

## ChatGPT / Codex

Install under the runtime’s supported skills directory, commonly:

```bash
mkdir -p ~/.agents/skills
cp -R software-builder ~/.agents/skills/software-builder
```

Natural-language examples:

- “Use software-builder to implement the next GitHub issue.”
- “Run the Builder role, then dispatch isolated Reviewer lenses.”
- “Adjudicate the current PR findings using software-builder.”

Prefer separate Codex tasks or fresh agent sessions. Use repository connectors only for authoritative remote state; use local git for implementation when available.

## Cursor

Cursor may not automatically discover Agent Skills in every configuration. Keep the canonical skill folder in the repository and add a small discovery rule.

Create `.cursor/rules/software-builder.mdc`:

```markdown
---
description: Invoke the repository software-builder skill for autonomous task implementation, independent review, remediation, and PR completion.
alwaysApply: false
---

When the user asks to implement a task through review, remediation, CI, or PR completion, read `software-builder/SKILL.md` and follow it.

Load only the active role prompt:
- Orchestrator: `software-builder/references/orchestrator.md`
- Builder: `software-builder/references/builder.md`
- Reviewer: `software-builder/references/reviewer.md`

Keep Builder and Reviewer contexts isolated. Treat CI and exact-commit checks as authoritative.
```

Natural-language examples:

- “Use software-builder for this task.”
- “Continue the software-builder loop.”
- “Review this PR with Lens B only.”

Use Cursor background agents, separate chats, or worktrees as available. Do not pass implementation chat history into Reviewer chats.

## Kiro

Keep the skill in the repository and add a steering file that points to it.

Create `.kiro/steering/software-builder.md`:

```markdown
---
inclusion: manual
---

For autonomous implementation, independent review, remediation, CI validation, or pull-request completion, read `software-builder/SKILL.md`.

Load only the active role reference. Preserve role isolation and use `software-builder/templates/state-schema.yaml` for official state.
```

Natural-language examples:

- “Use the software-builder steering workflow for this spec task.”
- “Resume the Builder role.”
- “Run an isolated Lens A review.”

Use Kiro specs for task requirements, but keep workflow state separate from product requirements.

## Generic agent fallback

For an agent without skill discovery:

1. Provide `software-builder/SKILL.md`.
2. State the active role.
3. Provide only that role’s reference prompt.
4. Provide the task and objective evidence.
5. Do not provide other roles’ private context.

Example:

```text
Use the attached software-builder skill.
Active role: Reviewer
Lens: LENS_A
Review commit <sha> against base <sha>.
Return only the structured reviewer report.
```

## Cross-agent handoff envelope

Use this neutral envelope when moving work between platforms:

```yaml
skill: software-builder
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
