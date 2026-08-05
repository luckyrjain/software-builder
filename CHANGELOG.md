# Changelog

Change history for the skills in this repo. Per-skill sections, newest first. This file replaces the
inline "Recent changes" blocks that previously lived in each `SKILL.md` (those go stale in-context; see
the create-skill anti-pattern on time-sensitive info).

Human-readable overviews: each skill's `README.md` and [docs/README.md](docs/README.md).

## loop-task-implementer

### Rename, framework compliance, and safety fixes (2026-08-05)

- Renamed from `software-builder` to `loop-task-implementer`; updated all internal references,
  `.cursor/rules/`, and `.kiro/steering/`.
- Brought into the same shared-framework conventions as the other 6 skills: added `SETUP.md`,
  `README.md`, `examples.md`, `report-template.md`, and `reference/{phase-index,lazy-load-index,
  mcp-capabilities,smoke-test,pressure-tests}.md`.
- Fixed a real installability bug: `orchestrator.md`, `builder.md`, `reviewer.md`, and
  `state-schema.yaml` lived at the repo root, outside the skill directory, so `scripts/install.sh`
  shipped installs missing its own role prompts. Moved them into `workflow/` and `reference/` with
  proper frontmatter.
- Safety fixes (autonomous-merge skill): assigned review-thread resolution to the Orchestrator
  explicitly (previously unowned, could stall completion); tightened `autonomous_merge_authorized` so
  repository-file prose can't grant it; added a response-wait budget for a hung Builder/Reviewer
  dispatch; gave the "sequential role simulation" fallback a concrete procedure; added the missing
  "When NOT to use" table; fixed `report-template.md`'s completion-state vocabulary to match
  `state-schema.yaml`'s actual enum.

## pr-gatekeeper

### Initial release (2026-08-05)

- New skill — item #2 of the [team-facing agents roadmap](docs/superpowers/plans/2026-08-05-team-facing-agents-roadmap.md):
  a thin push-webhook-triggered wrapper that auto-runs **pr-review** on every push to an open MR and
  posts inline when pr-review's own rules allow unattended posting.
- `reference/auto-post-policy.md` — a deterministic two-message protocol (opening phrase depends on
  `auto_post_authorized`; a single "Hold — don't post" reply whenever pr-review's Phase 3 stops and
  waits) that never bypasses pr-review's `general-only`/draft-MR confirmation gates — those still always
  hold, by pr-review's own non-negotiable rules.
- `disable-model-invocation: true` — does not compete with pr-review's ambient chat invocation.
- Design spec: [docs/superpowers/specs/2026-08-05-pr-gatekeeper-design.md](docs/superpowers/specs/2026-08-05-pr-gatekeeper-design.md).
- Wired into `make install-pr-gatekeeper` / `make lint-pr-gatekeeper`, root README, docs/README,
  docs/REPOSITORY, skill-routing.md, phase-glossary.md, cross-skill-escalation.md, prompt-injection.md —
  and added to `lint-framework`'s 4 hardcoded per-skill loops from the start (a gap found and fixed
  after-the-fact on who-owns-x-bot).

## incident-triage-agent

### Initial release (2026-08-05)

- New skill — items #3+#4 of the [team-facing agents roadmap](docs/superpowers/plans/2026-08-05-team-facing-agents-roadmap.md):
  a paging-webhook-triggered composition of **incident-rca** (root cause) and **squad-map** (owning
  team), two modes in one agent — Triage on page-fire, Postmortem on incident-resolved.
- `reference/unattended-gate-policy.md` — exhaustive enumeration of every blocking gate in both wrapped
  skills with a deterministic answer, written exhaustive from the start using the lesson from
  pr-gatekeeper's `auto-post-policy.md` (which needed three review rounds to reach full coverage for a
  single wrapped skill — this file covers two).
- Postmortem mode reuses incident-rca's own Corrective/Preventive/Post-RCA-actions tables verbatim — its
  only original contribution is squad-map owner-column substitution, no new action-item schema.
- `disable-model-invocation: true` — does not compete with incident-rca's or squad-map's ambient chat
  invocation.
- Design spec: [docs/superpowers/specs/2026-08-05-incident-triage-agent-design.md](docs/superpowers/specs/2026-08-05-incident-triage-agent-design.md).
- Wired into `make install-incident-triage-agent` / `make lint-incident-triage-agent`, root README,
  docs/README, docs/REPOSITORY, skill-routing.md, phase-glossary.md, cross-skill-escalation.md,
  prompt-injection.md — and added to `lint-framework`'s 4 hardcoded per-skill loops from the start.

## backlog-runner

### Initial release (2026-08-05)

- New skill — item #7 of the [team-facing agents roadmap](docs/superpowers/plans/2026-08-05-team-facing-agents-roadmap.md):
  a scheduled queue-management wrapper around **loop-task-implementer** — pulls N tickets from a
  Jira/GitHub Issues query, works through them overnight in dependency order, opens a PR per task, never
  merges.
- Confirmed (not assumed) that loop-task-implementer, unlike pr-review/incident-rca, already has no live
  synchronous "ask and wait" chat gates — every stop resolves to a terminal per-task report state
  (`HUMAN_ACTION_REQUIRED`/`ESCALATED`). This skill needed no `pr-gatekeeper`-style "answer every gate"
  policy, only new session-level queue bookkeeping loop-task-implementer's own per-task
  `state-schema.yaml` doesn't cover.
- `reference/queue-policy.md` resolves one real ambiguity in loop-task-implementer's own documented
  workflow explicitly: `HUMAN_ACTION_REQUIRED` (PR opened, not merged) continues the run — the expected
  outcome every night — while a new session-level circuit breaker (task cap, deadline, token budget, or
  3 consecutive escalations) is what actually stops it early.
- `autonomous_merge_authorized` has no input path in this skill at all — hardcoded never-`true`.
- `disable-model-invocation: true` — does not compete with loop-task-implementer's ambient invocation.
- Design spec: [docs/superpowers/specs/2026-08-05-backlog-runner-design.md](docs/superpowers/specs/2026-08-05-backlog-runner-design.md).
- Wired into `make install-backlog-runner` / `make lint-backlog-runner`, root README, docs/README,
  docs/REPOSITORY, skill-routing.md, cross-skill-escalation.md, prompt-injection.md — and added to
  `lint-framework`'s 4 hardcoded per-skill loops from the start. `phase-glossary.md` doesn't apply,
  inheriting loop-task-implementer's own exemption.

## new-hire-guide

### Initial release (2026-08-05)

- New skill — item #5 of the [team-facing agents roadmap](docs/superpowers/plans/2026-08-05-team-facing-agents-roadmap.md):
  a thin composition wrapper around **domain-comprehension** + **squad-map** that resolves a new hire's
  squad to its repos, runs domain-comprehension **unscoped**, and curates `ONBOARDING_TOUR.md` down to
  just those repos afterward.
- No `disable-model-invocation` — ambiently invocable, unlike who-owns-x-bot/pr-gatekeeper/
  incident-triage-agent/backlog-runner, since a human is always present for this flow. Both wrapped
  skills' own live gates (domain-comprehension's Session 0 checkpoint, squad-map's `squad_path_segment`
  HARD STOP) surface unscripted — no gate-policy override file.
- Zero-match squad-name handling: never produces a silent empty tour — asks for confirmation, listing the
  squad names that actually exist in `SQUAD_MAP.md`.
- **Round-1 review fix (same day):** the initial design scoped domain-comprehension via
  `scope.seed_repos`, which cascaded through its mandatory Session 0b squad-map delegation and silently
  archived every other squad's rows out of the shared `SQUAD_MAP.md` on every run (squad-map's own
  scope-shrink rule, triggered as an unintended side effect). Fixed by always running domain-comprehension
  unscoped and curating downstream instead. Also corrected a false claim about no ambient-routing
  collision with domain-comprehension (its "subsystem onboarding" trigger phrase does overlap — resolved
  via an explicit person-named disambiguation rule in `skill-routing.md`).
- Design spec: [docs/superpowers/specs/2026-08-05-new-hire-guide-design.md](docs/superpowers/specs/2026-08-05-new-hire-guide-design.md).
- Wired into `make install-new-hire-guide` / `make lint-new-hire-guide`, root README, docs/README,
  docs/REPOSITORY, skill-routing.md, cross-skill-escalation.md, prompt-injection.md, phase-glossary.md.

## release-readiness-checker

### Initial release (2026-08-05)

- New skill — item #9 of the [team-facing agents roadmap](docs/superpowers/plans/2026-08-05-team-facing-agents-roadmap.md):
  a release go/no-go report composing **pr-review** (MRs merged since each repo's last release marker,
  never posts to GitLab), **k8s-overprovisioning-datadog** (per-service rightsizing verdict, surfaced
  as-is), and **incident-rca** (per-service open-incident signal, Phase 1 evidence only — never a full
  RCA).
- Genuinely new logic: the MR-range resolver (pr-review's own docs only ever enumerate open MRs, never a
  merged-in-a-date-range query, paginated exhaustively) and the three-way aggregation into
  `RELEASE_READINESS_REPORT.md`.
- No `disable-model-invocation` — ambiently invocable, like `new-hire-guide`. Unlike `new-hire-guide`,
  this skill **does** need a gate-policy file (`reference/gate-policy.md`) covering all three wrapped
  skills' own real gates — pr-review's posting confirmation (reuses pr-gatekeeper's own real policy,
  always "Hold — don't post"; pr-review has no caller-settable quiet mode), k8s's ambiguous-service-name
  ask ("proceed with unknown," k8s's own documented fallback), and incident-rca's Phase 1 checkpoint
  (always "stop here," overriding its own default-to-proceed on a strong signal) — every other
  incident-rca gate is avoided by construction (explicit UTC times, `service` anchor always supplied,
  1-hour minimum lookback), not scripted. A round-1 review caught and fixed a fabricated assumption that
  pr-review had a settable gate-free posting mode; see `release-readiness-checker/CHANGELOG.md`.
- Design spec: [docs/superpowers/specs/2026-08-05-release-readiness-checker-design.md](docs/superpowers/specs/2026-08-05-release-readiness-checker-design.md).
- Wired into `make install-release-readiness-checker` / `make lint-release-readiness-checker`, root
  README, docs/README, docs/REPOSITORY, skill-routing.md, cross-skill-escalation.md, prompt-injection.md,
  phase-glossary.md.

## migration-program-manager

### Initial release (2026-08-05)

- New skill — item #8 of the [team-facing agents roadmap](docs/superpowers/plans/2026-08-05-team-facing-agents-roadmap.md):
  an org-wide rollup over **mysql-to-postgres-sql**'s per-workspace `MIGRATION_STATUS.yaml`, joined to
  squad ownership via **squad-map**'s `SQUAD_MAP.md`, implementing
  [org-rollup-schema.md](docs/skill-framework/shared/org-rollup-schema.md)'s `pg_migration_gate` adapter
  designed in Phase 4.
- A **pure read-only aggregator**: never invokes mysql-to-postgres-sql or squad-map live, only reads their
  already-produced files — a deliberate design choice to eliminate the entire class of risk that caused
  new-hire-guide's round-1 bug (a narrowed live wrapped-skill invocation cascading into an unintended
  side effect on shared state). No gate-policy file, because nothing is ever invoked live to have gates.
- Genuinely new logic, none of it borrowed from an existing skill: the first "many workspaces at once"
  input (`program_manifest`) in the repo; the first programmatic `SQUAD_MAP.md` table parser
  (`scripts/aggregate_migration_status.py`, tolerant of the Conflicts/Unmapped/Archived sections that
  follow the join table in the same file); and the first persisted cross-run state
  (`migration_program_state.json`, `{gate_signature, first_observed_at}` per `(workspace_root,
  service_name)`) to compute per-gate staleness that `MIGRATION_STATUS.yaml` itself has no timestamp for
  — owned exclusively by this skill, never read or written by mysql-to-postgres-sql.
- `scripts/aggregate_migration_status.py` — stdlib + PyYAML only, `main(argv) -> int` CLI entrypoint,
  31 pytest cases under `tests/test_aggregate_migration_status.py` covering the squad-map parser, the
  path/name join, status derivation, and staleness reset-vs-accrue behavior.
- No `disable-model-invocation` — ambiently invocable, like new-hire-guide/release-readiness-checker; no
  wrapped-skill gate to police since nothing is invoked live.
- Design spec: [docs/superpowers/specs/2026-08-05-migration-program-manager-design.md](docs/superpowers/specs/2026-08-05-migration-program-manager-design.md).
- Wired into `make install-migration-program-manager` / `make lint-migration-program-manager` (the first
  lint target in this phase's build to also run a real pytest suite), root README, docs/README,
  docs/REPOSITORY, skill-routing.md, cross-skill-escalation.md, prompt-injection.md, phase-glossary.md.

## who-owns-x-bot

### Initial release (2026-08-05)

- New skill — item #1 of the [team-facing agents roadmap](docs/superpowers/plans/2026-08-05-team-facing-agents-roadmap.md):
  a thin Slack-bot-facing wrapper that delegates ownership computation entirely to **squad-map** and
  returns a single formatted Slack reply (Resolved / Ambiguous / Unknown — never a fabricated squad).
- `disable-model-invocation: true` — does not compete with squad-map's ambient chat invocation; meant to
  be called explicitly by a `/who-owns` Slack slash-command handler with a structured `query`.
- Design spec: [docs/superpowers/specs/2026-08-05-who-owns-x-bot-design.md](docs/superpowers/specs/2026-08-05-who-owns-x-bot-design.md).
- Wired into `make install-who-owns-x-bot` / `make lint-who-owns-x-bot`, root README, docs/README,
  docs/REPOSITORY, skill-routing.md, phase-glossary.md.

## Repository

### Cross-agent discovery for all skills (2026-08-05)

- Added `.cursor/rules/<skill>.mdc` and `.kiro/steering/<skill>.md` for pr-review, incident-rca,
  k8s-overprovisioning-datadog, domain-comprehension, squad-map, and mysql-to-postgres-sql, matching
  the in-repo discovery pattern loop-task-implementer already had — lets Cursor/Kiro find any skill
  directly in a cloned working copy with no install step.
- `lint-framework` now enforces both discovery files exist for every skill.

### Deep gap analysis and fixes across all 7 skills (2026-08-05)

- Multi-pass deep content/logic audit (beyond structural framework compliance) found and fixed real
  bugs: a confidence-cap that could promote UNKNOWN→LOW (incident-rca); a workload-routing bug that
  misrouted non-autoscaled K8s workloads into the KEDA path (k8s-overprovisioning-datadog); a fuzzy
  squad-match that silently dropped its own conflict flag (squad-map); an inline-comment
  mis-anchoring risk on headerless multi-file diff batches (pr-review); three undetected MySQL
  dialect constructs (`IF()`, `YEAR()`/`MONTH()`/`WEEK()`) in the PG-migration scan gate
  (mysql-to-postgres-sql); a leaked real internal tracker URL (mysql-to-postgres-sql).
- Closed 4 missing reverse rows in the cross-skill escalation matrix
  ([cross-skill-escalation.md](docs/skill-framework/shared/cross-skill-escalation.md)) to restore the
  symmetry the file claims.
- See each skill's section below/above for the skill-specific entries.

### Six-skill framework rollout + org-content scrub (2026-08-05)

- Landed the shared skill-framework scaffolding (docs, scripts, templates, tests) for pr-review,
  incident-rca, k8s-overprovisioning-datadog, domain-comprehension, squad-map, and
  mysql-to-postgres-sql in this repo.
- Removed all references to a specific former employer/organization from skill docs, fixtures, and
  domain packs, replacing real internal URLs/company names with generic placeholders — skills ship
  portable, with no leaked org-specific content.

## mysql-to-postgres-sql

### v1.6 — framework compliance & prompt review (2026-07-07)

- Initial merge to `master`: scan gate, references, collection P0/P1, Node/Python paths, framework wiring.
- Added `skill-contract.md`, `examples.md`, `pressure-tests.md`, `calibration-snippets.md`, `templates/SERVICE_PG_MIGRATION.md`, scan fixtures, `tests/run_pressure_tests.sh`.
- `make lint-mysql-to-postgres-sql` + `install-mysql-to-postgres-sql`; registered in `skill-routing.md` and cross-skill escalation matrix.
- MR !19 fixes: `ripgrep` in CI; root `README.md` / `docs/REPOSITORY.md` parity; `skill_version: 1.6`.

_Pre-merge WIP on `feat/squad-map-skill` (internal v1.0–v1.5) is consolidated into this first public release._

## squad-map

### v1.0 — standalone extraction (2026-07-06)

- New **squad-map** skill extracted from domain-comprehension Session 0b.
- Maps repos to GitLab org squads + Datadog runtime teams → `SQUAD_MAP.md`.
- domain-comprehension Session 0b now delegates to squad-map (workflow v1.3).
- Install: `make install-squad-map`; lint: `make lint-squad-map`.

## domain-comprehension

### PROPOSAL_CHECK delivery mode (2026-08-05)

- New `PROPOSAL_CHECK` delivery mode (Architecture Decision Assistant, roadmap item #6): compare a
  proposed feature/service against the existing engagement's `BOUNDED_CONTEXTS.md` / `DATA_OWNERSHIP.md`
  / `API_CATALOG.md` / `EVENT_CATALOG.md`, reusing `ADD_REPO`'s merge-gate overlap taxonomy read-only.
- Writes only `PROPOSAL_CHECK_REPORT.md` — never merges into shared deliverables or `manifest.yaml`.
- HARD STOP if `manifest.yaml` is absent, `engagement.status` isn't `IN_PROGRESS`/`FIRST_PASS_COMPLETE`,
  or a touched repo's `inventory`/`deep_dive` isn't complete-or-skipped — no automatic fallback to `FULL`,
  no partial check against incomplete deliverables.

### ADD_REPO delivery mode (2026-07-30)

- New `ADD_REPO` delivery mode: onboard one repo into an already-established multi-repo engagement without re-running `FULL`.
- Merge-conflict gate: `RISK_MAP.md` § Merge Conflicts blocks `phases.p0`/`phases.p1` from `complete` while a conflict is `open` ([validate_manifest_yaml.py](domain-comprehension/scripts/validate_manifest_yaml.py)).
- Reuses `DELTA` mode's affected-phases re-synthesis rules for downstream phases.

### Session 0b delegation (2026-07-06)

- Session 0b squad mapping delegated to **squad-map** skill.
- Removed local `reference/squad-mapping.md` and `templates/SQUAD_MAP.md` (live in squad-map/).
- `reference/mcp-capabilities.md` trimmed to P2b Datadog tools only.

## Repository

### Claude Code compatibility (2026-07-09)

- `scripts/install.sh` gained `--agent cursor|claude-user|claude-project|all` and `--target-dir`;
  default (no-flag) behavior unchanged.
- New `make install-claude` / `make install-claude-<skill>` targets.
- New `docs/skill-framework/shared/claude-code-setup.md` — install paths + MCP config location
  mapping for Claude Code, linked from every skill's `SETUP.md`.

### Repo hygiene (2026-07-02)

- domain-comprehension added to root [README.md](README.md) (skills table, install, lint, MCP, usage) and
  [docs/README.md](docs/README.md) (skills index, routing, file map).
- `make setup` — installs `requirements.txt` dev deps + git hooks.
- Fixed stale `schema_version: 3` note for `evidence.example.json` in docs/README.md.

### Documentation index (skill-improvements-r3)

- Added [docs/README.md](docs/README.md) — full documentation index with file maps and cross-skill routing.
- Added [docs/REPOSITORY.md](docs/REPOSITORY.md) — repo layout, Makefile, lint, git hooks.
- Added per-skill [README.md](pr-review/README.md) files (human "what it does" vs agent `SKILL.md`).
- Added [scripts/README.md](scripts/README.md) — what `install.sh` does.
- Updated root [README.md](README.md) with documentation links.

## k8s-overprovisioning-datadog

### v3.0 — graph-first audit engine (2026-06-29)

- **Decision graph** as primary artifact (`schema_version: 3`) — [decision-graph-schema.md](k8s-overprovisioning-datadog/reference/decision-graph-schema.md)
- **Pipeline:** BUILD_GRAPH → VALIDATE_INVARIANTS → RENDER (reasoning separated from markdown)
- **Invariants** INV-01–INV-11 — [invariants.md](k8s-overprovisioning-datadog/reference/invariants.md)
- **Renderers:** [render/markdown.md](k8s-overprovisioning-datadog/render/markdown.md), [render/json.md](k8s-overprovisioning-datadog/render/json.md)
- **Human Report + Technical Appendix** — prose-first DORA deliverable; [templates/human-report.md](k8s-overprovisioning-datadog/templates/human-report.md) + appendix A–E
- Templates refactored to renderer layout specs (15 files under `templates/`)
- [workflow/report.md](k8s-overprovisioning-datadog/workflow/report.md) — human-first presentation rules (ID translation, smoke tests); [workflow/render.md](k8s-overprovisioning-datadog/workflow/render.md) — RENDER phase
- Example: [decision-graph.example.yaml](k8s-overprovisioning-datadog/reference/decision-graph.example.yaml)

### v2.0 — deterministic confidence and namespaced IDs (2026-06-29)

- **Weighted-sum confidence** — `0.35×completeness + 0.35×quality + 0.15×contradiction + 0.15×telemetry`; show arithmetic
- **Separate scores** — `ASSESSMENT_CONFIDENCE` vs `RECOMMENDATION_CONFIDENCE`
- **ID namespaces** — `OBS_`, `EVID_`, `DEC_`, `REC_` ([id-namespaces.md](k8s-overprovisioning-datadog/reference/id-namespaces.md))
- **Structured rationale** — `Reasons: ✓ OBS_*` + `Explanation` on `DEC_*`
- **DRY rule** — values only in Observations/Evidence; reference IDs elsewhere
- **ASSESSMENT_SEVERITY** — INFO / WARNING / CRITICAL
- **DecisionHistory** — previous/current decision, review count
- **threshold_hash** in fingerprint
- **Recommendation FSM** — READY / BLOCKED / DEFERRED / REJECTED / COMPLETED

### v2.0 — versioned audit schema (2026-06-29)

- **Immutable schema contract** — `SCHEMA_VERSION=2`; PascalCase section slugs; [reference/report-schema.md](k8s-overprovisioning-datadog/reference/report-schema.md)
- **Modular templates** — 13 files under `templates/`; `report-template.md` is index only
- **Observations ≠ Evidence** — values in Observations; provenance in Evidence (no duplication)
- **Semantic IDs** — `CPU_USAGE_AVG`, `CPU_KEEP_REQUEST` (stable; no E1/R1)
- **Assessment fingerprint** — manifest_hash + metric_query_hash for comparability
- **Computed confidence** — formula with factor breakdown; 1 decimal + bands
- **Decision rationale** + **WhyThisMatters** paragraphs for blocked decisions
- **Risk scoring** — Likelihood × Impact + Residual risk per recommendation
- **Structured dependencies** — `Depends on` / `Blocked by` graph (observation, recommendation, assumption, decision)
- **ChangedSinceLastAssessment** — diff subsection when prior report comparable
- New references: `observation-ids.md`, `recommendation-ids.md`, `confidence-formula.md`
- `workflow_version` bumped to 2.0

### v1.8 — production-grade report schema (2026-06-29)

- **Facts split:** Observed vs Derived sections; ban combined value strings in evidence.
- **Evidence provenance:** Source, Metric, Aggregation, Window, Scope, Weight on every E* row.
- **Decision dependencies:** Depends on, Blocking evidence, Missing evidence on decision objects.
- **Assumptions section:** explicit implicit beliefs with violation impact.
- **Recommendation impact:** Cost, latency, risk, availability, engineering effort per R*.
- **Prerequisites:** "Before executing" checklist distinct from blockers.
- **Quality enum:** `missing` vs `unknown` vs `not_applicable` (replaces merged Unknown labels).
- **Lifecycle status:** Observe / Ready / Blocked / Rejected / Completed per recommendation.
- **Evidence weighting:** critical/high/medium/low tiers with confidence propagation
  (`reference/evidence-weights.md`).
- **Assessment metadata:** reproducibility block (metrics queried, skill version, threshold set, duration).
- **Ordering rule:** safety → confidence → benefit → effort (P0/P1/P2 derived from sort).
- **Contradiction gate:** Resolved/Unresolved; Unresolved caps assessment confidence at 0.60.
- **`FINAL_DECISION` block:** machine-readable executive decision enum.
- **Fixed 13-section report order;** detail moved to Appendix.
- New reference files: `reference/evidence-schema.md`, `reference/evidence-weights.md`.
- `workflow_version` bumped to 1.8 in report/evidence/reason/validate/confidence/collect/orchestrator.

### Round 4 (skill-improvements-r3)

- Removed misplaced RCA findings table from the cross-skill escalation section (escalation table now
  lists k8s → incident-rca / pr-review paths only).

### Re-review fixes (MR !7, round 2)

- Added the HPA metric-suitability table (`thresholds.md`) and linked it from SKILL Step 5 (fixes a
  dangling reference).
- Quick paths now include Step 4 (unit conversion) and Step 4a (cyclic check) on CPU-sizing paths, with
  an explicit skip-4a note.
- Split the bursty Java+Kafka calibration example into Scenario A (fleet `.dist` available) and
  Scenario B (unavailable) to remove the contradictory p95 facts.
- Documented the deployment-totals `{scope}` as application-container-only and warned that the
  `get_widget` timeseries are sidecar-inclusive.
- Added the `Mixed / defer` verdict label consistently (thresholds, report template, smoke test) with a
  dimension→overall mapping.
- Prerequisites now require `datadog/traces` and `search_datadog_monitors`.
- Added a Peak-window queries (Step 4a) section to `queries.md`.
- Added a `Priority: P0/P1/P2` field distinct from decision confidence; normalized examples.
- Trimmed the frontmatter description to triggers + keywords (CSO); clarified numeric vs legacy
  qualitative confidence; throttle >5% cross-reference; DORA disambiguation note.

### Earlier

- Active firing-monitor check before downsizing; cyclic detection promoted to Step 4a;
  decision-confidence rubric bands; rolling-update side-effect callout.
- HPA scale-down stabilization-window blindspot; Cluster Autoscaler activity + spot-node caveats; VPA
  min/max discovery via git provider; network I/O as an optional I/O-bound scaling signal.

## domain-comprehension

### v1.5 — large-scale convergence (2026-07-01)

- **Repository classification** — normative enum ([repo-classification.md](domain-comprehension/reference/repo-classification.md))
- **Four architecture views** — logical context / service call / deployment / runtime in `DEPENDENCY_GRAPH.md`
- **Overall confidence** — document-level + per-question table in `EXEC_SUMMARY.md`
- **Evidence summary** — counters in manifest + `EXEC_SUMMARY.md` ([evidence-summary.md](domain-comprehension/reference/evidence-summary.md))
- **Exercise axis** — implemented vs exercised ([implementation-status.md](domain-comprehension/reference/implementation-status.md))
- **Evidence precedence** — runtime → code → config → tests → … ([evidence-precedence.md](domain-comprehension/reference/evidence-precedence.md))
- **Business flows** — `BUSINESS_FLOWS.md` (≥3 journeys)
- **Change impact** — per bounded context + Top 10 smells
- **Known omissions** — `KNOWN_OMISSIONS.md` (scope ≠ unknowns)
- **Large-scale execution** — 100–500 repo guidance ([large-scale-execution.md](domain-comprehension/reference/large-scale-execution.md))
- **Manifest schema v2** — `overall_confidence`, `evidence_summary`, updated diagrams/artifacts

### v1.4 — manifest.yaml completion tracking (2026-07-01)

- **`manifest.yaml`** — machine-readable phase + artifact state
- **Validator** — [validate_manifest_yaml.py](domain-comprehension/scripts/validate_manifest_yaml.py)

## kubesense-skills

### Agent skills vendored under `.agents/skills/` (2026-07-01)

- **kubesense-mcp** — APM, logs, metrics sub-skills; `multi-query.md` (external skill, not in this repo)
- **kubesense-alerts** — alert authoring; `datadog-migration.md` (external skill, not in this repo)
- **kubesense-dashboards** — dashboard workflows
- **incident-rca** — `dependencies.md` resolves `~/.cursor/skills/kubesense-mcp` or `.agents/skills/kubesense-mcp`

## incident-rca

### Causal-graph invariant validator (2026-07-02)

- `causal_graph` YAML artifact + `validate_causal_graph.py` (CG-01–CG-08) — machine-checks acyclicity,
  evidence-backed edges, hypothesis score arithmetic, confidence caps, and the no-best-guess-primary rule.
- Phase 4 emits and validates the artifact; Phase 5 gates rendering on it. Lint + 22 tests wired in.

### query_signals validator (2026-07-01)

- Deep validation for `query_signals[]` entries (`query_text`, `source`, `detected_at` required).
- `lint-incident-rca` validates `evidence.example.opensearch-query-governance.json`; expanded pytest coverage.

### Senior RCA depth bar (2026-06-30)

- Added [reference/root-cause-depth.md](incident-rca/reference/root-cause-depth.md) — layered causality
  (failure / trigger / systemic), 5 Whys, known vs unknown, mechanism narrative, P0/P1/P2 actions.
- Expanded [report-template.md](incident-rca/report-template.md) — causal chain, blast radius, key
  metrics snapshot, resolution split, appendix-only `assessment_metadata`.
- Phase 5 loads root-cause-depth; query-playbook adds dependency blast radius + infra capacity snapshot.
- OpenSearch saturation example in [examples.md](incident-rca/examples.md).
- **Datadog RUM** — supplementary source for client-side / user-behavior symptoms.

### Executive RCA polish (2026-06-30, round 2)

- Evidence-safe systemic wording (avoid "undersized" without proof); anti-repetition across sections.
- Confidence: band + Reason / Remaining uncertainty — decimals only in `assessment_metadata`.
- Recovery timeline + MTTR; lessons learned table; tiered risks; blast-radius dependency sentence.
- Renamed **Trigger workload analysis**; recovery cascade in causal chain.

### Query investigation (2026-06-30)

- Added [reference/query-investigation.md](incident-rca/reference/query-investigation.md) — Phase 3 pipeline
  for search/DB saturation (APM spans, logs, DBM).
- Report section **Executed queries investigated**; optional `query_signals[]` in evidence JSON.

### Phase 1 OpenSearch APM pass (2026-06-30)

- **Phase 1** requires `aggregate_spans` on OpenSearch/ES incidents (`service:elasticsearch`, group by
  `resource_name` + `@base_service`) — index + caller + HTTP status without slow logs.
- New report section **Query execution profile**; `query_signals[]` may start in Phase 1.
- Phase 3 reuses Phase 1 APM results for ES; pressure tests and OpenSearch example updated.

### Round 4 (skill-improvements-r3)

- Evidence schema bumped to **`schema_version: 2`** with optional `recurrence_history[]` (Phase 3
  recurrence JQL — escalate to "Systemic / requires architectural fix" when ≥3 similar incidents).
- KubeSense tool table: **`get-trace-or-log-fields`** must be called first to discover available fields.
- Query playbook: Kafka consumer lag recipes (Datadog `kafka.consumer_lag` + KubeSense `analyze-metrics`);
  hypothesis types `feature_flag_regression` and `kafka_lag_spike`.
- Report template checklist item for recurrence escalation.

### Initial release + team-rollout hardening

- Trimmed the frontmatter `description` to triggers + keywords only (CSO) — no workflow summary.
- Made the Python correlator an **optional external dependency**: documented detection
  (`incident-rca --help`) and a manual-scoring fallback (`reference/manual-scoring.md`); Phase 4 gates
  on CLI presence and labels the report's Gaps section when ranking by hand.
- Removed reliance on the nonexistent GitLab `list_deployments`. Phase 2 now uses Datadog
  `get_change_stories` (preferred), Jenkins, and merged-MR fallback (`list_merge_requests` + `get_commit`).
- Required `telemetry.intent` on every Datadog MCP call (with example, ddsetup/ddconfig on 403,
  `load_datadog_skill` for metrics/logs/traces).
- Fixed log aggregation: `analyze_datadog_logs` (SQL GROUP BY) for counts/top-N; `search_datadog_logs`
  for raw samples only. Added metric-discovery guidance (`get_datadog_metric_context` /
  `search_datadog_metrics`) instead of guessing `trace.<framework>.request.errors`.
- Added recipes for `get_change_stories`, org-wide error discovery, and `search_datadog_incidents`.
- Added Phase 0b (anchor the window from Jira before observability), a "When NOT to use" routing table,
  a read-only boundary (forbids Jenkins `triggerBuild`/`updateBuild`, GitLab/Jira write tools),
  multi-instance GitLab/Atlassian handling, correlation-vs-causation guardrails (≥2 independent signal
  types for HIGH; single source caps at MEDIUM), a Common-mistakes table, and a Red flags section.
- Removed user-specific absolute paths and `file://` links; made KNOWN_ISSUES optional/relative.
- Expanded the evidence schema + field mapping; added `schema_version: 1`. Standardized JQL
  (`summary ~ … OR description ~ … OR labels = …`). Renamed "Out of scope (Phase 1)" → "(v1)".
- Added `reference/manual-scoring.md`, `reference/smoke-test.md`, `reference/pressure-tests.md`,
  `examples.md`, a Reference-files table, and Quick paths. Documented why `disable-model-invocation`
  is unset. Added the `make lint-incident-rca` target (line check + JSON parse + anchor check).

## pr-review

### Natural-language invocation (2026-06-30)

- Removed `disable-model-invocation` — skill auto-invokes on clear GitLab MR review phrases
  ("review this pr …", "review this MR", `!IID`, re-review, list open MRs) as well as `/pr-review`.
- Expanded `SKILL.md` description triggers and added Invocation section with false-positive guards.
- Updated `examples.md`, `SETUP.md`, `README.md`, and root README usage section.

### Round 4 (skill-improvements-r3)

- Stop-search guardrail: **Critical findings do not count toward the 5-High threshold**; pointer to
  `severity-rubric.md` for current thresholds.
- **Severity vs verdict distinction** for failed CI: always emit High finding for head pipeline failure;
  Comment verdict allowed when failure is demonstrably unrelated to the MR diff.
- Phase 1 large-MR cap note: at `per_page: 100`, the 200-file cap binds at page 2.

### Round 3 — re-review output polish (merged to master)

- Re-review template: verification vs inference blocks, review scale stats, **"No actionable findings"**
  wording, machine-readable `review_metadata` YAML footer.
- Incremental Phase 5 checklist expanded to 15 blocks in `reference/incremental-rerun.md`.

### Re-review fixes (MR !7, round 2)

- Quick paths "Re-review" row now routes through the full incremental flow (Phases 1→2→3→4→5; Phase 4
  skipped when `head_sha` is unchanged).
- Standardized the machine-parseable `- head_sha: \`<full_sha>\`` line in both summary templates;
  aligned Phase 1 extraction and examples.
- Added explicit Jira write-tool detection (`addCommentToJiraIssue` / `transitionJiraIssue`) in Phase 0;
  Phase 5 write-back keys off the recorded flag.
- Documented the snippet-hash dedupe fallback for summary-only / general-only modes.
- Phase 5 now emits merge-train status when `merge_trains_enabled: true`.
- Refreshed the SETUP.md file tree; wired batch-script partial failures into Phase 4 posting.
- Added the >30-commit re-run decision row; trimmed the description (CSO); slimmed SKILL.md by moving
  the Phase 1 step-1 metadata sub-checks into `reference/phase-1-gather.md`.
- Added script tests for new-file / deleted-file diffs, `--diff-file` mode, and `--line`/`--old-line`
  validation; fixed `diff-to-positions.py` to anchor deleted-file (`+++ /dev/null`) removed lines by old
  path. Added a repo-local override note and the `make lint-pr-review` smoke-test step; reconciled the
  draft-MR warning between Quick paths and Phase 1.

### Earlier

- Early MR-size cap warning from `changes_count` (before diff pagination); CODEOWNERS approval check;
  MR-template completeness check; flaky-job handling in the CI verdict.
- Explicit snippet-hash definition for re-run dedupe; AI/LLM checklist trigger signals; very-old
  baseline warning; clarified partial-post (no stop-on-error) and draft-note vs draft-MR wording.
