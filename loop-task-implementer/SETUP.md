# loop-task-implementer — Setup

## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-08-21 |
| **Review cadence** | Quarterly — or when lifecycle/shared review contracts change |
| **External services** | Git provider/API, CI provider (both repo-specific; no fixed MCP) |

See [setup-freshness.md](../docs/skill-framework/shared/setup-freshness.md) for the shared contract.
Platform-neutral autonomous task-implementation skill: isolated build → adjudicated independent review →
portable review evidence → lifecycle validation → pull-request/completion action. No Datadog/GitLab/Jira MCP
is required — see [reference/mcp-capabilities.md](reference/mcp-capabilities.md).

## Ambient discovery is intended

This skill deliberately does **not** set `disable-model-invocation` in its frontmatter, so the agent can
auto-apply it for natural-language implementation/task-loop requests. Leave it unset unless invocation
must require an explicit ask.

## Quickstart

1. `git clone` this repo, then `make install-loop-task-implementer` (or `bash scripts/install.sh loop-task-implementer`).
2. Restart your agent / start a new session so the skill reloads.
3. Confirm the host can isolate roles — native subagents, fresh sessions, or worktrees. Sequential role
   simulation is a fallback; whenever the resulting lens is recorded `NOT_ISOLATED`, lifecycle readiness
   requires an explicit human exception with provenance bound to that exact reviewed change identity and
   the lens's current positive integer `review_generation`.
4. Confirm repository read/write capabilities required by the authorized action and visibility of required CI.
5. Say: "Use loop-task-implementer to implement `<task>` and open a PR."

## What's in here

```text
loop-task-implementer/
├── SKILL.md
├── SETUP.md
├── README.md
├── examples.md
├── report-template.md
├── scripts/
│   └── validate_loop_lifecycle.py    # fail-closed READY/COMPLETE/merge validator
├── workflow/
│   ├── orchestrator.md               # primary Orchestrator role prompt
│   ├── orchestrator-lifecycle.md     # mandatory Batch 5.2C lifecycle overlay
│   ├── builder.md
│   ├── reviewer.md
│   ├── reviewer-evidence.md          # post-adjudication portable evidence adapter
│   └── lifecycle-gate.md             # fresh pre-READY / pre-write revalidation
├── reference/
│   ├── phase-index.md
│   ├── lazy-load-index.md
│   ├── review-lifecycle-contract.yaml
│   ├── mcp-capabilities.md
│   ├── smoke-test.md
│   ├── pressure-tests.md
│   ├── platform-adapters.md
│   └── state-schema.yaml
└── docs/skill-framework/shared/      # vendored by package_skill for installed execution
    └── review_contract_runtime.py
```

The installed package is self-contained. `validate_loop_lifecycle.py` loads only the vendored shared
runtime inside the skill package and fails closed if it is missing; it must not fall back to an unrelated
parent checkout.

## 1. Requirements

- A repository-capable host agent: Cursor, Claude Code, ChatGPT/Codex, Kiro, or the generic adapter path.
- Repository access appropriate to the authorized actions. Reviewer contexts remain read-only.
- Visibility of authoritative required CI/checks for the exact current head. Without it, the workflow may
  implement/review but cannot reach verified readiness.
- For every lifecycle-CLEAN lens, `review_generation` must be a positive integer and
  `review_evidence_generation` must equal that exact generation. Advancing the review generation without
  newly validated/persisted evidence deliberately leaves the lens stale and blocks readiness.
- An isolation primitive suitable for the change. Any lens recorded `NOT_ISOLATED` blocks lifecycle
  readiness unless an authorized human explicitly accepts the degraded isolation with non-empty provenance
  bound to that exact `reviewed_change_identity` and current `review_generation`; never relabel the pass as
  isolated or reuse an exception from an earlier identity or reviewer generation.
- Explicit merge authorization before any merge. Verified readiness and merge authority are separate gates.

## 2. Install the skill

From the repo root: `make install-loop-task-implementer` (or `bash scripts/install.sh loop-task-implementer`).
The packager copies the skill plus its referenced shared framework tree, including
`docs/skill-framework/shared/review_contract_runtime.py`.

After installation, verify the installed tree contains:

- `workflow/orchestrator-lifecycle.md`
- `workflow/reviewer-evidence.md`
- `workflow/lifecycle-gate.md`
- `reference/review-lifecycle-contract.yaml`
- `scripts/validate_loop_lifecycle.py`
- `docs/skill-framework/shared/review_contract_runtime.py`

## 3. In-repo discovery (no install step)

When working directly inside this repo, Cursor and Kiro can discover the skill from:

- `.cursor/rules/loop-task-implementer.mdc`
- `.kiro/steering/loop-task-implementer.md`

Both point at `loop-task-implementer/SKILL.md`. See
[reference/platform-adapters.md](reference/platform-adapters.md) for Codex and generic fallback.

## 4. Use it

Invoke with natural language; there is no slash command. Examples:

- "Use loop-task-implementer to complete the next task."
- "Implement issue 42, review it deeply, fix findings, and open a PR."
- "Resume the loop-task-implementer workflow for the current branch."

Full scenarios: [examples.md](examples.md).

The Orchestrator must load [workflow/orchestrator-lifecycle.md](workflow/orchestrator-lifecycle.md) with its
normal role prompt. After each reviewer returns it increments that lens's `review_generation` and leaves the
prior `review_evidence_generation` stale, adjudicates, then runs the
[reviewer-evidence adapter](workflow/reviewer-evidence.md). Only with newly validated evidence does it persist
`review_evidence_generation = review_generation`. Before `READY`, `COMPLETE`, and immediately before an
authorized merge/write, it refreshes current identity/requirements/repository gates and runs the
[lifecycle gate](workflow/lifecycle-gate.md).

## 5. Tuning

Budgets (dirty review cycles, contested rounds, review size thresholds, CI polling) remain configured by the
Orchestrator per task — see `workflow/orchestrator.md` §3. Batch 5.2C does not silently relax those existing
circuit breakers.

## Framework

This skill follows the shared framework conventions:
[docs/skill-framework/README.md](../docs/skill-framework/README.md) ·
[cross-skill-escalation](../docs/skill-framework/shared/cross-skill-escalation.md) ·
[smoke-test-conventions](../docs/skill-framework/shared/smoke-test-conventions.md) ·
[examples-conventions](../docs/skill-framework/shared/examples-conventions.md) ·
[post-action-templates](../docs/skill-framework/shared/post-action-templates.md) ·
[claude-code-setup](../docs/skill-framework/shared/claude-code-setup.md).

## Smoke test

After install, run [reference/smoke-test.md](reference/smoke-test.md) against a small repo. A correct run must
build a current `change_identity`, perform isolated reviewer lenses with positive integer `review_generation`
values and matching `review_evidence_generation`, adjudicate findings, create portable `review_evidence`,
attach authoritative CI to the exact current head, and produce **zero lifecycle validation errors** before
claiming verified readiness. A manual conflict/rebase, requirements change, third-party push, reviewer rerun,
or crash/resume between reviewer return and evidence persistence must leave stale state blocked rather than
reuse old evidence or approvals.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Reviewer sees Builder PR narrative/commit framing | Rebuild the neutral review package; see `workflow/orchestrator.md` §6. |
| Rejected reviewer false-positive still blocks lifecycle as a defect | Adjudication must happen before `reviewer-evidence.md`; rejected proposals stay in rich audit state but not `findings.defect`. |
| CLEAN lens has `partial`/`unable` evidence | Invalid lifecycle state: CLEAN requires complete inspection, no unavailable surfaces, zero portable defects, positive integer `review_generation`, and matching `review_evidence_generation`. |
| Review generation advanced but old CLEAN evidence remains | Expected fail-closed state: keep `review_evidence_generation` stale until the new generation's adjudicated evidence validates and is persisted. |
| Review stays stale after a clean base transition | Record explicit conflict-resolution boolean **and provenance** for the SHA transition; unknown provenance fails closed. |
| Fresh post-conflict rerun remains blocked | Do not apply a historic conflict flag to evidence already produced against the current post-conflict identity. |
| `NOT_ISOLATED` review appears as `ISOLATED` after human acceptance | Bug: preserve `NOT_ISOLATED`; record `isolation_exception_authorized`, non-empty provenance, `isolation_exception_change_identity`, and `isolation_exception_review_generation` separately. |
| Same-head reviewer rerun reuses an older isolation waiver | Bug: increment `review_generation`, leave old evidence generation stale, clear old exception fields, and require new evidence plus a new exception if the rerun remains `NOT_ISOLATED`. |
| CI is green but lifecycle refuses readiness | Confirm `ci.commit` exactly equals `workspace.current_head_commit` and all legacy approval/thread/integration/circuit-breaker gates are satisfied. |
| Installed validator cannot find shared runtime | Reinstall/package the skill; the vendored `docs/skill-framework/shared/review_contract_runtime.py` is mandatory and no parent fallback is allowed. |
| Run merges without explicit authorization | Treat as a bug. A zero-error lifecycle gate establishes readiness only; merge authority remains a separate explicit grant. |
