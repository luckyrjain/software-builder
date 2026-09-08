# Matt Architecture Parity Bridge — Approved Requirements

## Goal

Bring Software Builder's codebase-architecture and module-design experience to
behavioral parity with Matt Pocock's `codebase-design` and
`improve-codebase-architecture` skills, while retaining Software Builder's
stronger evidence, authority, artifact, routing, portability, and eval
contracts.

Parity means the host is taught to find and explain deepening opportunities,
not merely to produce a generic architecture review. The result must preserve
the distinction between an observed architectural friction, a proposed
deepening direction, a settled engineering decision, and an authorized code
change.

## Source comparison

The parity source contains these normative behaviors:

- prioritize active hotspots from bounded Git history;
- use the vocabulary `module`, `interface`, `depth`, `seam`, `adapter`,
  `leverage`, and `locality`;
- apply the deletion test;
- distinguish deep modules from shallow pass-throughs;
- reject speculative interfaces;
- produce a visual HTML report in OS temporary storage;
- show a before/after structural model for every candidate;
- label candidate strength as `Strong`, `Worth exploring`, or `Speculative`;
- wait for candidate selection before concrete interface design; and
- grill the user on the selected engineering decision.

Software Builder already supplies the following stronger guarantees and they
remain authoritative:

- bounded scope and explicit read budgets;
- observed/inferred/unknown evidence classification;
- candidate falsification;
- safe rendered-output and prompt-injection rules;
- canonical registry and typed result envelopes;
- read-only architecture and module-design authority;
- six-host coverage and generated projections;
- optional handoffs rather than synthesized approval; and
- eval-gated admission.

## Repository gap baseline

The comparison was checked against `origin/main` at revision
`f4d478a9d5d9c80cee8bd8232de85b15bc40cc1e` on 2026-09-05. The gaps below are
absence-of-contract findings, not claims that the implementation is defective:

| Gap | Repository evidence | Bridge owner |
|---|---|---|
| Depth/deletion vocabulary is not normative | `docs/skill-framework/shared/codebase-design-principles.md` has contract, locality, leverage, seam, adapter, and abstraction-cost sections but no explicit depth, deletion-test, or real-versus-hypothetical-seam sections | Child Plan A, Tasks 1–2 |
| Candidate presentation lacks Matt's visual semantics | `codebase-architecture-review/reference/report-format.md` has typed metadata and candidate fields but no strength badge, dependency category, or before/after structural model requirement | Child Plan A, Task 3 |
| Visual report contract is absent | `codebase-architecture-review/reference/` contains Markdown report references but no ephemeral HTML-report reference | Child Plan A, Task 4 |
| Module-design depth checks are implicit | `module-design/workflow/design.md` covers contract, seams, and migration but does not require a depth comparison or deletion test | Child Plan A, Task 5 |
| Behavioral evals cover authority more than judgment quality | Existing foundation Tier-2/Tier-3 cases cover read-only/no-refactor behavior but not depth, falsification quality, or visual models | Child Plan A, Task 6 |
| Post-selection grilling has no dedicated owner | The current registry and routing matrix contain no `engineering-decision-discovery` skill or decision-frontier artifact | Child Plan B, Tasks 1–4 |

## Scope

### Child Plan A — architecture and module parity

- extend shared design doctrine with depth, deletion-test, and seam-depth rules;
- extend `codebase-architecture-review` with Matt's visual candidate model;
- extend `module-design` with explicit depth and deletion-test analysis;
- add the ephemeral visual HTML report contract;
- add Tier-2/Tier-3 behavior coverage for the missing judgment behaviors; and
- keep the canonical durable artifact schemas stable unless a consumer proves
  a schema change is necessary.

### Child Plan B — decision-discovery bridge

- add `engineering-decision-discovery` as the explicit post-selection grilling
  capability;
- model dependent and independent engineering decisions as a decision tree;
- require recommended answers without converting recommendations into approval;
- block unattended runs when a material human decision remains unresolved; and
- connect the architecture-review handoff without automatic invocation.

## Non-goals

- no automatic code refactoring;
- no new skill-type or `behavior.kind` taxonomy;
- no replacement of `architecture-review`, `system-design`,
  `implementation-planner`, or `loop-task-implementer`;
- no canonical HTML artifact stored in the repository;
- no host-specific workflow fork;
- no interface created solely to enable mocking;
- no forced `module-design` step for every implementation; and
- no P2 `large-change-decision-map` unless a separate RED evaluation proves
  that `implementation-planner` cannot represent the remaining decision graph.

## Normative requirements

### R1 — Design vocabulary and depth

The shared doctrine MUST define:

- module depth;
- interface surface;
- shallow pass-through module;
- deep module;
- deletion test;
- real versus hypothetical seam; and
- interface-as-test-surface.

`depth` is not a file-size metric. A deep module hides substantial behavior
behind a smaller meaningful contract. A shallow module exposes nearly the same
knowledge callers need to perform the behavior themselves.

### R2 — Evidence-first deepening

Architecture review MUST use bounded history where available, inspect callers
and tests, and distinguish observations from inferences. Static smells may
select an area for investigation but cannot independently create a candidate.

Every retained candidate MUST explain:

1. recurring engineering friction;
2. evidence and source revision;
3. current interface/seam and leaked knowledge;
4. proposed concentration of behavior;
5. caller simplification;
6. test-surface improvement;
7. future change made easier;
8. abstraction cost;
9. migration risk; and
10. the result of the deletion test.

### R3 — Candidate presentation

Every retained candidate MUST include:

- recommendation strength: `Strong`, `Worth exploring`, or `Speculative`;
- dependency category: `in-process`, `local-substitutable`,
  `ports-and-adapters`, or `mock-only`;
- a before model showing the current modules, interface, leakage, and seam;
- an after model showing the proposed responsibility concentration and seam;
- one concise problem statement;
- one concise deepening direction; and
- no concrete production interface until the candidate is selected.

`mock-only` is a warning classification, never evidence that a seam should be
created.

### R4 — Visual report

The architecture review MUST emit:

- the existing `CODEBASE_ARCHITECTURE_REVIEW.md` report;
- the existing typed `codebase_architecture_report`; and
- a single portable visual HTML document at
  `architecture-review-20260905T120000Z.html` in the host's OS temporary directory; the timestamp is generated at runtime.

The HTML report is ephemeral and is not added to `skill_result.artifacts`.
It MUST use Tailwind and Mermaid from CDNs, contain safe-rendered repository
content, and include before/after models for every retained candidate. A
zero-candidate report remains valid and MUST clearly state that no candidate
survived falsification.

If a CDN is unavailable, the HTML MUST remain readable with the Markdown
content and fenced diagram source visible; CDN failure cannot block or upgrade
the canonical Markdown/artifact result.

### R5 — Module design parity

`module-design` MUST explicitly evaluate:

- interface surface versus implementation depth;
- whether the deletion test says the module earns its cost;
- whether dependencies are created inside the module or supplied at a real
  seam;
- whether callers and tests cross the same meaningful interface;
- whether a proposed seam has real variation or an integration boundary; and
- two materially different designs when the interface is uncertain.

The skill remains read-only and report-only.

### R6 — Human decision ownership

After a user selects a candidate, the optional handoff to
`engineering-decision-discovery` MUST carry the exact bounded candidate scope,
evidence references, unresolved questions, and allowed actions. The architecture
review result MUST keep `recommended_next_skill: null`; the handoff is a
human-visible offer, not synthesized approval or automatic dispatch.

`engineering-decision-discovery` MUST:

- ask only questions on the current decision frontier;
- retrieve repository facts itself where possible;
- provide a recommendation and rationale for each question;
- wait for the user's decision;
- recompute dependent decisions after each answer; and
- return `BLOCKED` in unattended execution when a material decision remains
  unresolved.

### R7 — Artifact and compatibility policy

Child Plan A MUST NOT widen `module_design_spec` or
`codebase_architecture_report` merely to make visual rendering convenient.
Visual fields belong to the ephemeral report or to a separately versioned
artifact only when a real consumer needs them.

Child Plan B adds `engineering_decision_record` v1 with `desired_state`
semantics. Existing artifact versions and existing skill contracts remain
unchanged.

### R8 — Eval admission

Before implementation, RED pressure scenarios MUST demonstrate that the
current catalog fails to require:

- depth analysis;
- deletion-test reasoning;
- visual before/after models;
- candidate strength classification;
- falsification quality;
- two materially different module designs; and
- decision-frontier ordering and human decision ownership.

GREEN admission MUST add Tier-2 transcript coverage and Tier-3 golden coverage
for those behaviors, plus routing, injection, authority, degraded, and
cross-host projection checks.

### R9 — Host and packaging parity

Both child plans MUST remain valid for Cursor, Claude, Codex, ChatGPT, Kiro,
and Generic. The ephemeral HTML report MUST not assume a host can launch a
browser. If opening the report is unavailable, return its safe path and retain
the report content in the response.

## Acceptance gate

The bridge is complete only when:

- every R1–R9 requirement maps to an implementation task and test;
- the RED baseline is recorded before the corresponding skill text changes;
- no existing valid route is stolen;
- `recommended_next_skill: null` remains fixed for architecture review;
- read-only skills cannot write source, tests, registry, commits, or PRs;
- unresolved interactive decisions block unattended composition;
- visual reports never enter the repository or canonical artifact list;
- generated projections and all six host surfaces are synchronized;
- Tier-1, Tier-2, and required Tier-3 evals pass;
- `make lint`, `make generate-check`, `make validate-registry`,
  `make validate-agent-skills`, `make validate-hosts`, and
  `make validate-evals` pass; and
- an independent review finds zero unresolved material findings.

## Delivery order

1. Execute the RED baseline for both child plans.
2. Implement Child Plan A and review its complete diff.
3. Implement Child Plan B only after Child Plan A's contracts and routes are
   stable.
4. Run the full repository verification and independent review.
5. Ship each child as an independently reviewable change.
