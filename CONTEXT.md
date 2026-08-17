# Software Builder

A portable library of agent **skills** — structured workflows that teach repository-capable coding agents how to perform software-delivery work with evidence, role separation, and explicit gates. This is not an agent runtime; **hosts** (Cursor, Claude Code, Codex, Kiro, and similar) load skills and execute them.

Implementation vocabulary (registry fields, YAML schemas, eval tiers) lives in [docs/skill-framework/shared/terminology-glossary.md](docs/skill-framework/shared/terminology-glossary.md). Target-system vocabulary (bounded contexts, as-built PRD) lives in [domain-comprehension/CONTEXT.md](domain-comprehension/CONTEXT.md). See [CONTEXT-MAP.md](CONTEXT-MAP.md) for how contexts relate.

## Platform boundary

**Software Builder repository**:
The canonical source tree that authors, packages, and validates skills. Changes here propagate to installed packages via the installer.

_Avoid_: Platform repo, meta-repo, this repo (when speaking normatively — use the full term in docs)

**Target workspace**:
Any repository or multi-repo workspace a skill operates on — the customer's code, infra, or program data. Skills analyze or modify target workspaces; they do not confuse the target with the Software Builder repository unless explicitly scoped to it.

_Avoid_: Workspace (alone, when ambiguous), repo (when multi-repo), project (overloaded)

**Host**:
The coding-agent environment that discovers a skill, loads its instructions, and executes tool calls. The host chooses the model and provides Git, MCP, and subagent capabilities.

_Avoid_: Agent (when meaning the host runtime), IDE (too narrow — Codex and Kiro are not IDEs), LLM (the model is not the host)

**Installed package**:
A self-contained copy of one skill, vendored for use on a machine that may not have the Software Builder checkout. Functionally equivalent to the canonical skill for runtime purposes.

_Avoid_: Plugin, extension, rule (those are host-specific discovery mechanisms, not the package itself)

## Core objects

**Skill**:
A named, portable workflow package identified by its directory name (e.g. `pr-review`). A skill owns its policy, phases, outputs, and risk posture. It is the unit of install, composition, and routing.

_Avoid_: Workflow (a skill contains workflows), tool (skills orchestrate tools; they are not tools), agent (skills instruct hosts)

**Framework**:
The shared normative reference library (`docs/skill-framework/`) vendored into installed packages — confidence bands, routing tables, escalation matrices, metadata schemas. Framework material is cross-skill convention, not any one skill's domain logic.

_Avoid_: SDK, library (in the programming sense), spec (too generic)

**Capability**:
A named external evidence or action source a skill may use (GitLab MR read, Datadog metrics query, Kubernetes workload read). Capabilities are declared per skill; absence of a required capability blocks the run rather than silently guessing.

_Avoid_: Integration, MCP (MCP is one delivery mechanism for capabilities), API (too broad)

## Skill shapes

Skills differ by how much original analysis they perform. These shapes are mutually exclusive labels for a skill's primary role.

**Specialist skill**:
Performs the full analysis or action itself — e.g. `pr-review`, `incident-rca`, `k8s-overprovisioning-datadog`, `loop-task-implementer`. Owns evidence gathering, verdict fields, and (where authorized) external actions.

_Avoid_: Leaf (implementation jargon), core skill

**Router skill**:
Classifies an underspecified request and dispatches to exactly one specialist without performing that specialist's work — e.g. `test-writer` routes to one of five test-creation skills. A router adds no detection or generation logic of its own.

_Avoid_: Gateway, proxy, dispatcher

**Wrapper skill**:
Triggered by an explicit external event (webhook, schedule, slash command) and invokes one or more specialists with a typed handoff — e.g. `pr-gatekeeper`, `backlog-runner`, `incident-triage-agent`, `who-owns-x-bot`. Wrappers own trigger policy and unattended authorization; they do not reimplement specialist analysis.

_Avoid_: Middleware, adapter, orchestrator (reserved for loop-task-implementer's internal role)

**Aggregator skill**:
Reads pre-produced rollup artifacts from other skills or workspaces and ranks or combines them without re-running live analysis — e.g. `migration-program-manager`, `cost-optimization-sprint-planner`, `weekly-squad-digest`. Stale or missing upstream artifacts are reported, not invented.

_Avoid_: Dashboard, report generator (implies presentation-only; aggregators have ranking and policy logic)

**Composer skill**:
Invokes multiple specialists live over a caller-supplied manifest and synthesizes one combined report — e.g. `release-readiness-checker`. Differs from an aggregator: composers fan out fresh specialist runs; aggregators consume existing rollups.

_Avoid_: Wrapper (wrappers typically invoke one primary specialist), meta-skill

## Multi-agent roles

Used by `loop-task-implementer` and inherited conceptually by `backlog-runner`. Roles require isolated contexts when the host supports subagents, worktrees, or fresh sessions.

**Orchestrator**:
Owns workflow state, task selection, policy discovery, adjudication, CI evidence, completion gates, and escalation. Does not write implementation code or act as an independent reviewer.

_Avoid_: Manager, coordinator (too vague), agent (generic)

**Builder**:
Implements one task — code, tests, commits, pushes, PR create/update. May fix or rebut review findings with evidence. Must not approve its own work or decide completion gates.

_Avoid_: Implementer (acceptable in prose but prefer Builder for normative docs), author, developer

**Reviewer**:
Read-only assessment of the exact diff against an assigned lens. May run checks and disposable local mutations. Must not commit, push, or alter shared repository state. Proposes findings; does not hold unconditional veto — adjudication belongs to the Orchestrator.

_Avoid_: Auditor (implies compliance-only scope), critic

**Review lens**:
A fixed perspective applied to the same diff — Lens A (Safety and State) and Lens B (Contracts and Operations) in loop-task-implementer. Both lenses must be clean for the same normalized diff fingerprint before completion.

_Avoid_: Pass, stage, phase (phase is a pipeline step; a lens is a viewpoint)

## Evidence doctrine

**Evidence**:
Facts derivable from authoritative sources — repository state, exact-commit CI, diffs, logs, metrics, configuration, tests. Evidence outranks agent prose.

_Avoid_: Context, input, data (too weak)

**Claim**:
An agent-generated statement not yet tied to evidence. Claims are advisory until verified against repository or external sources.

_Avoid_: Hypothesis (a hypothesis is an explicit uncertain claim; plain claims may be presented as fact — the distinction matters in incident-rca), assumption

**Degraded mode**:
A documented fallback when an optional capability is absent — e.g. chat-only review when inline posting is unavailable. Missing every complete alternative capability path is a **block**, not degradation.

_Avoid_: Partial success, best effort (implies the run should continue silently)

**UNKNOWN**:
The correct verdict when evidence is insufficient. Prefer UNKNOWN over speculation.

_Avoid_: TBD, N/A (N/A means the concept does not apply to this skill; UNKNOWN means it applies but cannot be resolved)

## Separated decision concepts

Five concepts that must never collapse into a single field or code path. See [five-concept-separation-audit.md](docs/skill-framework/shared/five-concept-separation-audit.md).

**Evidence completeness**:
Whether enough evidence has been gathered to speak with confidence — e.g. review complete, evidence counters filled.

_Avoid_: Done, finished, thorough

**Review verdict**:
The judgment given the evidence — recommendation, root cause, rightsizing verdict, build/no-build assessment. A positive verdict does not imply permission to act externally.

_Avoid_: Result, outcome (too broad — includes action facts), decision (collapses with authorization)

**Repository readiness**:
Whether the *target* (release, service, repo) is in a shippable state — distinct from "my analysis is complete" and "my recommendation is positive." Only skills whose job is target readiness use this; e.g. release-readiness-checker's `READY | CONDITIONAL | NOT_READY | UNKNOWN`.

_Avoid_: Quality, health (component scores, not a ship gate)

**External-action authorization**:
Whether posting, writing, or merging externally is permitted *right now* — a gate distinct from verdict. Automation wrappers declare unattended authorization policy explicitly; interactive skills ask at posting gates.

_Avoid_: Approval, merge (those are specific actions, not the authorization concept)

**Final repository action**:
Whether the write, post, or merge actually happened — recorded separately from authorization. A report must not claim an action that did not occur.

_Avoid_: Success, completed (ambiguous with workflow completion)

## Invocation and triggers

**Ambient invocation**:
The host may load the skill from conversational context when user intent clearly matches — e.g. "review MR !123" triggers `pr-review`.

_Avoid_: Auto, implicit (prefer ambient for normative contrast with automation-only)

**Automation-only invocation**:
The skill runs only on an explicit external trigger (webhook, schedule, slash command) and carries `disable-model-invocation` so ambient chat must not load it — e.g. `pr-gatekeeper`, `backlog-runner`.

_Avoid_: Unattended (describes risk posture, not discovery mode), headless

**Gate**:
A decision point that must resolve before later side effects — e.g. posting confirmation before GitLab comments, build-readiness before PRD finalization. Gates are domain events, not implementation hooks.

_Avoid_: Checkpoint, step (a phase may contain zero or many gates)

**Phase**:
A numbered pipeline stage in a skill's workflow with declared inputs and outputs. Phases sequence work; they are not interchangeable with review lenses or confidence bands.

_Avoid_: Step, stage (acceptable in prose)

## Risk and write authority

**Risk class**:
The operational category governing guardrail strictness for a skill — read-only, posting, repository-write, merge, unattended. High-risk skills may combine multiple classes.

_Avoid_: Severity, priority (those rank findings or work items, not skill posture)

**Write authority**:
The maximum external write surface a skill may exercise — comment on an MR, commit to a target repo, unattended post. Only the skill that owns a write scope may perform that write; wrappers may gate but not escalate writes beyond the wrapped skill's authority.

_Avoid_: Permission, scope (scope also means task boundary in loop-task-implementer)

## Composition and handoffs

**Composition**:
How skills invoke or escalate to each other. Invocation is typed: wrappers pass an **invocation envelope** (exact scope, interaction policy, allowed actions, pinned revision); specialists return a **result envelope** (metadata, verdict fields, action facts).

_Avoid_: Pipeline, chain (implies sequential-only; composition includes escalation and optional handoffs)

**Escalation**:
An optional handoff from one skill to another after partial work — e.g. pr-review → incident-rca when a deploy regression is suspected. Distinct from mandatory subroutines (domain-comprehension always invokes squad-map at Session 0b).

_Avoid_: Referral, delegate (delegate implies the first skill stops owning the outcome)

**Handoff artifact**:
A typed payload crossing a composition boundary — e.g. `mr_context`, `mr_review_report`, `rca_report`, `implementation_pr`. Artifacts have declared producer and consumer fields validated at platform lint time.

_Avoid_: Message, payload (generic), DTO (implementation)

**Invocation envelope**:
What a wrapper hands to a child skill: precise scope (project + MR), interaction policy (review mode), allowed external actions, expected head SHA, and provenance. Prevents child skills from re-inferring scope from conversational fragments.

_Avoid_: Context object, params

**Result envelope**:
What a skill returns upstream: evidence completeness flags, verdict fields, and final action facts (`posted`, PR URL). Named `review_metadata` or `assessment_metadata` depending on skill family.

_Avoid_: Response, output (too generic)

## Confidence

**Confidence band**:
One of four categorical labels — HIGH, MEDIUM, LOW, UNKNOWN — applied to findings or overall conclusions based on evidence strength. Shared across pr-review, incident-rca, k8s-overprovisioning-datadog, squad-map, and domain-comprehension.

_Avoid_: Score, percentage (numeric mappings exist for analytics but band is canonical in prose), certainty

**Migration priority tier** (mysql-to-postgres-sql only):
P0 / P1 / P2 / Portable — compliance and rewrite **order**, not evidence confidence. Do not map P0 to HIGH.

_Avoid_: Priority (ambiguous with sprint priority), severity

## Change delivery concepts

**Merge request / Pull request**:
The reviewable unit of proposed change on GitLab (MR) or GitHub (PR). pr-review treats both symmetrically as "MR" in internal schemas; user-facing prose may say PR on GitHub.

_Avoid_: Diff (a diff is content; MR/PR is the review object), branch (a branch may hold many commits; review targets the MR/PR)

**Release manifest**:
Caller-supplied list of repos and services touched by a release — input to release-readiness-checker. Not inferred by the skill.

_Avoid_: Release notes, changelog

**Program manifest**:
Caller-supplied list of workspace roots for an org-wide migration status sweep — input to migration-program-manager.

_Avoid_: Repo list, inventory (inventory is broader)

**Sweep scope**:
Caller-supplied namespace or deployment filter for an org-wide cost-optimization ranking — input to cost-optimization-sprint-planner.

_Avoid_: Target list, cluster (too infra-specific)
