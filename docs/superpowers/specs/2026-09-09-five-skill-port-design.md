# Five-Skill Port — Approved Requirements

## Goal

Close the five genuine gaps found in the mattpocock-skills gap analysis (session record:
domain-modeling PR #223/#228 established the port pattern and registry-wiring locations) by adding
five new report-only, ambient skills to Software Builder, each adapted from a mutating
mattpocock-skills original into this repo's non-mutating doctrine — inspect and emit a typed
report/artifact, never edit source, tests, configuration, or docs, and offer every cross-skill
handoff rather than invoking it automatically.

Each of the five is independent of the other four (no shared code, no ordering dependency between
them) and gets its own implementation branch, PR, and 3-round review cycle (max → high → high
effort, mirroring domain-modeling), per the user's explicit choice. This document specs the shape
of all five together because the scaffolding template, registry-wiring locations, and eval/lint
conventions are now identical and already proven — the design decisions that differ are the
per-skill ones captured below (name, deliverable, scope boundary, escalation targets, and inputs).

## Source comparison

The mattpocock-skills originals are active tools with no report/action split:

| mattpocock skill | What it does today |
|---|---|
| `engineering/code-review` | Reviews the diff since a fixed point (commit/branch/tag/merge-base) along two axes — Standards (repo conventions) and Spec (does the code match the originating issue/spec) — via two parallel sub-agents, reported side by side. No repository mutation in the original either, but no typed artifact, registry entry, or eval coverage. |
| `engineering/diagnosing-bugs` | A diagnosis loop for hard bugs and performance regressions: build a repro, form and falsify hypotheses, converge on root cause. Ends with the bug still present — diagnosis only, no fix — but again with no typed report or registry presence. |
| `engineering/research` | Open-ended cited research: investigate a question against primary sources, track claim-to-source provenance. |
| `engineering/triage` | Classifies raw incoming bugs/feature-requests into a category+state label machine and writes labels/state directly in the tracker. |
| `engineering/wayfinder` | Plans a large, foggy, multi-session effort as a map of decision tickets, writing ticket files as it goes. |

Software Builder already supplies, and each port inherits unchanged:

- the canonical `skill_result` envelope, `action_gates`, `definition_of_done`/`blocked_conditions`
  framework (`docs/skill-framework/shared/runtime-contract.md`);
- OBSERVED/INFERRED/UNKNOWN/CONFLICTED evidence-status vocabulary
  (`docs/skill-framework/shared/confidence-bands.md`);
- prompt-injection and safe-rendered-output rules for all untrusted content;
- the offered-never-automatic cross-skill escalation convention
  (`docs/skill-framework/shared/cross-skill-escalation.md`);
- six-host packaging, eval-gated admission (five dimensions: positive, negative, ambiguous,
  adversarial, degraded), and the registry-wiring locations enumerated below.

## Repository gap baseline

Checked against `origin/main` at `8e569a1` on 2026-09-09 (post domain-modeling PR #223/#228 merge).
Confirmed absent, not merely undocumented:

| Gap | Nearest existing skill | Why it doesn't already cover this |
|---|---|---|
| Local diff/branch review since an arbitrary fixed point | `pr-review` | `pr-review`'s own SKILL.md: "Not for local-only diffs, RCA, or K8s rightsizing"; `skill-routing.md` lists local/unstaged diff review as an explicitly unowned row |
| Non-incident bug/perf-regression diagnosis | `incident-rca` | Scoped to "outages, error spikes, deploy regressions" with a required time window; explicitly "Not for... live remediation" and has no non-incident, non-windowed entry point |
| General cited research | *(none)* | No skill produces a cited-findings artifact against primary sources; nothing in the registry uses "primary source"/citation language |
| Raw issue/bug/feature-request classification | `incident-triage-agent`, `backlog-runner` | Both dispatch already-known, already-scoped work to existing skills; neither classifies an unscoped raw issue stream |
| Large, foggy, too-big-for-one-session effort decomposition | `prd-architect`, `implementation-planner` | `prd-architect` needs one already-scoped idea; `implementation-planner` needs an already-approved design — nothing bridges "I don't even know what the sub-questions are yet" |

## Scope

Five independent child efforts, each a full skill addition:

### A — `local-diff-review`

- **Deliverable**: `LOCAL_DIFF_REVIEW.md` / `local_diff_review`.
- **Required inputs**: `diff_scope` (a fixed point: commit SHA, branch, tag, or merge-base
  expression — HARD STOP if absent). **Optional**: `spec_context` (issue/ticket text the diff is
  supposed to satisfy).
- **Workflow**: `Inputs → Standards` (evaluate the diff against this repo's documented conventions —
  CLAUDE.md/CONTRIBUTING.md/lint config) `→ Spec` (evaluate the diff against `spec_context` if
  supplied, else report `not applicable — no spec_context given`, never fabricate an implied spec)
  `→ Report`. Standards and Spec are independent findings lists in the same report, not a merged
  verdict — a diff can pass one and fail the other.
- **Boundary rules**: never posts a comment, never opens a PR; a caller who wants that uses
  `pr-review` once the diff is actually a PR/MR. Does not duplicate `pr-review`'s security/dimension
  review depth — a security-sensitive Standards finding is escalated, not resolved here.
- **Escalation targets**: `security-review` (security-sensitive finding), `pr-review` (caller wants
  this posted once it's a real PR/MR).
- **Permissions**: `repository: read`, `external_actions: none` — same shape as `module-design`.

### B — `bug-diagnosis`

- **Deliverable**: `BUG_DIAGNOSIS_REPORT.md` / `bug_diagnosis_report`.
- **Required inputs**: `symptom` (the observed wrong behavior, test failure, or regression — HARD
  STOP if absent). **Optional**: `repro_hint` (steps or command the caller already knows).
- **Workflow**: `Inputs → Repro` (establish and confirm a minimal repro from evidence; record
  confidence if repro cannot be confirmed) `→ Hypotheses` (form candidate root causes, actively try
  to falsify each with evidence — same falsification discipline as
  `codebase-architecture-review`'s candidate rules) `→ Report`.
- **Boundary rules**: never edits source to fix the bug — the fix is `loop-task-implementer`'s job,
  handed the confirmed root cause. May run existing tests/build/lint commands read-only to observe
  behavior (this is the one skill in the batch needing `external_actions: read` rather than `none`,
  matching `domain-comprehension`'s existing "optional MCP query, degrade to static evidence" shape)
  — it never writes a file, migration, or config change.
- **Escalation targets**: `loop-task-implementer` (confirmed root cause, ready to fix),
  `incident-rca` (evidence reveals this is actually a live production incident),
  `codebase-architecture-review` (root cause is structural, not a local bug).
- **Permissions**: `repository: read`, `external_actions: read`.

### C — `research-brief`

- **Deliverable**: `RESEARCH_BRIEF.md` / `research_brief`.
- **Required inputs**: `research_question` (HARD STOP if absent).
- **Workflow**: `Inputs → Gather` (collect evidence from repository and, when available, external
  primary sources) `→ Report` (every claim tagged with its evidence status and source; no claim
  without a cited source or an explicit UNKNOWN).
- **New capability**: no skill in this registry has ever needed external web access.
  `scripts/registry/capability_catalog.yaml` gets one new **optional** capability,
  `host.web.search` (and `host.web.fetch` for following a specific link), with a documented degraded
  mode: without it, the skill answers from repository evidence only and marks every
  external-source-dependent claim `UNKNOWN` rather than fabricating a citation. This mirrors the
  existing optional-capability-with-degrade pattern (`domain-comprehension`'s `gitlab.search_code`,
  `datadog.query_metrics`) rather than inventing a new capability shape.
- **Boundary rules**: every claim in the report carries a source (repository path, or an external
  URL actually fetched this session) — no claim rendered as fact without one.
- **Escalation targets**: `engineering-decision-discovery` (research surfaces a decision that needs
  interrogating), `prd-architect` (research becomes the input to a PRD), `domain-comprehension`
  (question turns out to be about this codebase's own current behavior, not external research).
- **Permissions**: `repository: read`, `external_actions: read` (host.web.search/fetch optional).

### D — `issue-triage`

- **Deliverable**: `ISSUE_TRIAGE_REPORT.md` / `issue_triage_report`.
- **Required inputs**: `issues` (one or more raw issue/ticket texts — HARD STOP if absent).
- **Workflow**: `Inputs → Classify` (per issue: category — bug/feature/question/duplicate/security;
  severity; duplicate-of, if evidence supports it; recommended owning skill or squad) `→ Report`.
- **Boundary rules**: never writes a label, state transition, or tracker field — recommends only.
  Distinct from `incident-triage-agent` (paging-webhook-triggered, one live incident at a time, no
  human turn available) and `backlog-runner` (an already-scoped tracker query it works through, not
  raw unclassified issues).
- **Escalation targets**: `security-review` (security-flavored issue), `incident-rca` (issue
  describes an active incident, not a backlog bug), `prd-architect` (feature request needs a PRD),
  `tech-debt-assessor` (debt item needs ranking), `squad-map` (ownership unclear).
- **Permissions**: `repository: read`, `external_actions: none`.

### E — `initiative-mapper`

- **Deliverable**: `INITIATIVE_MAP.md` / `initiative_map`.
- **Required inputs**: `initiative_description` (the large, foggy effort — HARD STOP if absent).
- **Workflow**: `Inputs → Decompose` (break the initiative into decision tickets with dependency
  edges — same tree/frontier shape as `engineering-decision-discovery`'s decision tree, but at the
  initiative-sub-question level rather than one bounded decision) `→ Report` (which tickets are
  scoped enough for `prd-architect` directly, which need `engineering-decision-discovery` first,
  suggested sequencing).
- **Boundary rules**: never writes a ticket, PRD, or plan itself — every ticket in the map is a
  recommendation for a separate, explicitly authorized skill invocation.
- **Escalation targets**: `engineering-decision-discovery` (a mapped ticket is one unresolved
  decision), `prd-architect` (a mapped ticket is scoped enough for a PRD), `implementation-planner`
  (a mapped ticket already has an approved design).
- **Permissions**: `repository: read`, `external_actions: none`.

## Registry wiring (identical for all five, per the domain-modeling precedent)

For each skill: `skills/<id>/{SKILL.md,README.md,SETUP.md,CHANGELOG.md,examples.md,workflow/*.md,
reference/*.md}`; `scripts/registry/skills.d/<id>.yaml` fragment (category, capabilities,
permissions, `output_contract.produces`, `degraded_behavior`, `routing.patterns`/`exclude_patterns`,
`composition.escalation_targets`); hand-authored additions to `skills.yaml`'s
`contracts.platform.artifact_runtime.{durable_artifacts,artifact_schema_versions,state_semantics,
allowed_state_semantics,payload_types}`, `contracts.platform.artifact_ownership`, and
`contracts.composition.{artifact_types,artifact_schemas}` for the new artifact type (everything else
`make generate` re-derives from the fragment); `docs/skill-framework/shared/skill-routing.md` row +
disambiguation rule; `docs/skill-framework/shared/cross-skill-escalation.md` forward + reverse rows
for every escalation target above, in both directions where the target also escalates back;
`docs/REPOSITORY.md` layout tree row; `make/core.mk` `lint-<id>` target + `.PHONY`/`lint-static`
wiring; `evals/{positive,negative,ambiguous,adversarial,degraded}/cases.yaml` one row each;
`evals/golden/<id>/{golden-contract,golden-injection}.yaml`; `scripts/tests/test_<id>_routing.py`
regression test asserting every documented `examples.md` invocation-table row resolves against the
live dispatch oracle (`scripts.evals.dispatcher.dispatch_prompt`) — added directly this time,
learned from the domain-modeling review cycle rather than discovered after the fact.

## Testing

Per skill: `make generate` / `make generate-check` clean; `python3 -m scripts.registry validate`
clean; `python3 -m scripts.evals` zero failures; the new routing-regression test passes and is
verified to have teeth (temporarily revert the routing pattern, confirm the test fails, restore);
`make lint-static` clean including `verify-install-all`; full `python3 -m pytest scripts/tests`
green. Then a 3-round review (max effort → high effort → high effort, mirroring the domain-modeling
cycle) with fixes applied and re-verified between rounds, before merge.

## Sequencing

Independent — implement and PR in the order A, B, C, D, E for no reason other than the order
presented above; any could be first. `research-brief` (C) is the only one touching
`capability_catalog.yaml`'s capability *set* (a new capability, not just a new skill referencing
existing ones) — worth doing after at least one of the others lands, so its capability-catalog
change is reviewed against a settled registry rather than stacked on four simultaneous new-skill
diffs.
