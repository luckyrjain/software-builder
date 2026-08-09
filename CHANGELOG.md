# Changelog

Change history for the skills in this repo. Per-skill sections, newest first. This file replaces the
inline "Recent changes" blocks that previously lived in each `SKILL.md` (those go stale in-context; see
the create-skill anti-pattern on time-sensitive info).

Human-readable overviews: each skill's `README.md` and [docs/README.md](docs/README.md).

## Platform

### Skills-audit backlog (#20) — atomic writes, provenance, idempotency

- **migration-program-manager:** atomic state and rollup writes via temp file + `os.replace`.
- **weekly-squad-digest:** digest header now requires SHA-256 source revision fingerprints per rollup file.
- **pr-gatekeeper:** added `reference/idempotency.md` documenting caller-side per-MR locking beyond head_sha dedupe.

### Behavioral evals Tier 3 — golden recorded outputs (#16 follow-up)

- Added `evals/golden/` fixtures with `recorded_output` blobs and structured assertions.
- Added `scripts/evals/golden.py` and wired Tier-3 cases into `python3 -m scripts.evals` (`--tier 3`).
- Four golden cases for pr-review, pr-gatekeeper, incident-rca, and loop-task-implementer high-risk outcomes.

### P3 remaining — risk_class registry field and docs/history split

- Added required `risk_class` list to every skill in `skills.yaml` (posting, merge, unattended, read-only,
  repository-write).
- Registry validation requires `risk_class` and enforces `unattended` on automation-only skills.
- Added `docs/history/README.md` separating normative framework docs from dated `docs/superpowers/` specs.

### P3 platform polish — ADRs, glossary, install-all CI

- Added `docs/adr/` with ADRs for the skills registry, self-contained packages, and tiered behavioral evals.
- Added `docs/skill-framework/shared/terminology-glossary.md` (risk classes, capabilities, eval tiers).
- Added `scripts/tests/test_install_all_skills.sh` and `make verify-install-all` (all 22 skills, isolated temp repo).

### Behavioral evals Tier 2 — transcript policy fixtures (#16 follow-up)

- Added `evals/transcripts/` fixture schema with replayable `events` (tool, gate, outcome) and policy
  assertions (`tool_not_called`, `tool_order`, `gate_decision`, `forbid_tool_before_gate`, etc.).
- Added `scripts/evals/transcript.py` and wired Tier-2 cases into `python3 -m scripts.evals` with
  optional `--tier` filter.
- Six high-risk transcript fixtures for pr-review, pr-gatekeeper, and loop-task-implementer.

### Composition graph v2 — contracts and write-authority validation (#19 follow-up)

- Added `scripts/registry/composition_contracts.yaml` with per-skill `produces`/`consumes`/`write_authority`.
- Registry validation now checks aggregate rollup inputs and blocks write-authority escalation through invoke wrappers.

### Capabilities catalog + backfill for all 22 skills (#18 follow-up)

- Added `scripts/registry/capability_catalog.yaml` as the canonical capability contract per skill.
- Added `python3 -m scripts.registry backfill-capabilities` to insert missing `capabilities` blocks into `skills.yaml`.
- Registry validation now requires every skill to declare a `capabilities` block; `make lint` runs `backfill-capabilities-check`.

### Behavioral evals, composition graph, doctor, and release model (#16, #17, #18, #19)

- Added Tier-1 behavioral eval harness: `python3 -m scripts.evals` with global happy/adversarial
  contract checks for all 22 skills plus high-risk skill fixtures under `evals/fixtures/`.
- Extended `skills.yaml` with `composition` (invokes, escalation targets, aggregate mode) and
  `capabilities` blocks; CI validates composition cycles and dangling edges.
- Generated `generated/catalogue/composition-deps.mmd` composition graph alongside install-deps.
- Added `python3 scripts/doctor.py` preflight command for capability and install status.
- Added root `VERSION` (1.4.0), `docs/RELEASE.md`, and `scripts/package_release.py` for checksummed
  release bundles; installed manifests now record `distribution_version`.
- `make lint` runs `make validate-evals`; new targets: `make doctor`, `make package-release`.

### Transactional installer v1 (#14)

- `scripts/install.sh` now stages packages in a temp directory, validates, then atomically
  `mv`s into place — the previous install is only removed after the staged package passes validation.
- Default install set comes from `skills.yaml` (registry allowlist), not implicit `*/SKILL.md` glob.
- Added `--dry-run`, `--list`, `--verify <path>`, and `--uninstall <skill>` via `install_support.py`.

### Skills registry + generated adapters (2026-08-08)

- Added root `skills.yaml` as the canonical platform registry (install dependency edges, hosts,
  invocation mode, lint metadata) with split ownership: agent facts stay in each `SKILL.md`.
- Added `scripts/registry/` CLI: `make validate-registry`, `make generate`, `make generate-check`.
- Regenerated all `.cursor/rules/*.mdc` and `.kiro/steering/*.md` as thin discovery wrappers (no
  duplicated routing/policy prose).
- README skill-count badge and `docs/REPOSITORY.md` skill inventory table are marker-generated;
  `generated/catalogue/install-deps.mmd` documents install dependency graph.
- `make lint` now runs registry validation and generate drift check before existing lint targets.
- Closes the repo-side work for #12 milestone C; Makefile per-skill lint recipes unchanged in v1.

### Merge gate spec + ruleset verifier (2026-08-08)

- Added [`docs/github-ruleset-main.json`](docs/github-ruleset-main.json) as the canonical solo-maintainer
  ruleset for `main`: enforcement active, required status check `lint`, squash-only merges, zero required
  approvals, no CODEOWNER review, conversation resolution required.
- Added `scripts/check_github_ruleset.py` and `make verify-github-ruleset` to compare the live GitHub
  ruleset (via `gh api`) against the checked-in spec — run after applying settings in the GitHub UI.
- Added [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) (Contributor Covenant 2.0).
- `docs/REPOSITORY.md` documents the canonical ruleset file, verifier command, and one-time GitHub
  metadata steps (description, topics, delete head branches).

### Self-contained skill installs + distribution integrity P0 (2026-08-08)

- `scripts/install.sh` now packages skills via `scripts/package_skill.py`: vendored
  `docs/skill-framework/` references, rewritten local links, and `.software-builder-manifest.json`
  (source SHA + file hashes). Addresses the critical broken-copy install defect from the August 2026
  repository review.
- Added `scripts/validate_references.py` (`--source-tree` / `--installed-package`) and CI-covered
  install integration test (`make verify-install`) that installs from an isolated temp repo copy and
  validates after the source tree is removed.
- `make setup` now installs hash-pinned `requirements.lock` (matching CI); `make lint-requirements-lock`
  fails when direct manifest and lock entries drift in either direction.
- `lint-framework` enforcement loops now cover all 22 skills (fixes 16-vs-22 drift); framework README
  documents actual packaging behavior instead of claiming installed skills symlink to the repo.
- Post-review hardening: skill-name path traversal rejected in both installer and packager, symlink
  destinations refused, negative reference-validation tests added, install rollback on validation
  failure, and verify-install now covers weekly-squad-digest (superpowers-linked workflow files).

### Scheduled lint run + documented branch-protection checklist (2026-08-07)

- `.github/workflows/lint.yml` gained `schedule` (weekly, Monday 04:17 UTC) and `workflow_dispatch`
  triggers so drift is caught even with no open PR against `main`.
- `docs/REPOSITORY.md § CI/CD` now spells out the exact ruleset steps a repo admin needs to run once
  from **Settings** to make the `Lint` check an actual required merge gate — a workflow file existing
  was previously easy to mistake for "changes can't merge without it passing," which isn't true today.
- This is partial: the ruleset itself must still be applied by someone with repo-admin access — no
  tool in this environment can create GitHub rulesets/branch-protection rules. See #10. For a solo
  maintainer, do **not** require PR approvals (authors cannot self-approve); see
  `docs/REPOSITORY.md § Merge gate`.

### Hash-pinned CI dependencies (2026-08-07)

- Added `requirements.lock` (generated via `uv pip compile requirements.txt --generate-hashes
  --python-version 3.12 -o requirements.lock`) and switched `.github/workflows/lint.yml` to
  `pip install --require-hashes -r requirements.lock` so every CI run resolves identical dependency
  versions instead of re-resolving `pytest`/`PyYAML`'s loose lower bounds. Bumping a dependency now
  means editing `requirements.txt` and regenerating the lockfile in the same PR — a reviewable diff
  instead of a silent resolution change.
- Added `.github/dependabot.yml` for weekly, reviewable update PRs on both the `pip` (this lockfile)
  and `github-actions` (SHA-pinned Action refs) ecosystems.
- Fixes #11.

## test-writer

### Incremental backfill state across all five dispatch targets (2026-08-06)

- Each of unit/integration/contract/e2e/api-test-creator now persists a small
  `<LEVEL>_TEST_COVERAGE_STATE.yaml` file at `output_dir` after a backfill run (never diff mode) —
  target/journey/endpoint identifier, final status, a content hash for staleness detection, and a
  `pending_backlog` of targets discovered but cut off by `max_files_per_run`. A later backfill run on the
  same repo reads it back: already-covered targets whose hash is unchanged are skipped, and
  `pending_backlog` entries are worked through before newly discovered ones — so repeated runs on a large
  repo make forward progress instead of re-scanning and re-ordering from scratch each time.
- New shared doc section:
  [test-creation-principles.md §6](docs/skill-framework/shared/test-creation-principles.md#6-incremental-backfill-state-optional)
  — the file schema, the read/write contract, and the non-negotiables (optional and never a gate; hash
  not mtime; a corrupt/unreadable state file is ignored, never a hard failure; the state file accelerates
  ordering only, it's never authoritative over code evidence).
- Each skill's `workflow/select-targets.md` gained a new "Apply incremental backfill state" step
  (immediately before the `max_files_per_run` cap) and `workflow/report.md` gained a new "Write
  incremental backfill state" step (immediately before "Close the loop"); each `reference/report-format.md`
  documents the state file as a secondary artifact, distinct from the main report.

### api-test-creator added as a fifth dispatch target (2026-08-06)

- **unit-test-creator/integration-test-creator/contract-test-creator/e2e-test-creator** gained an
  optional, read-only, best-effort integration with **domain-comprehension**: a new shared doc,
  `docs/skill-framework/shared/domain-comprehension-integration.md`, documents which artifacts
  (`RISK_MAP.md`, `BUSINESS_FLOWS.md`, `DATA_OWNERSHIP.md`, `BOUNDED_CONTEXTS.md`, `API_CATALOG.md`)
  each skill may read — if they already exist at `workspace_root` — to prioritize backfill targets by
  business criticality and infer/enrich journeys from documented business flows, without ever becoming a
  hard dependency, a gate, or a live domain-comprehension invocation. Code evidence always wins over an
  artifact's claim.
- **api-test-creator** joins as a fifth dispatch target — black-box Postman/Newman request/response test
  suites against a real running API (no browser, no in-process mocking, no Pact consumer/provider
  agreement). See its own `CHANGELOG.md` for detail. `test-writer`'s dispatch table, level-classification
  keywords, and `make install-test-writer` chain all updated to include it.

### Rewritten into a thin router (2026-08-06)

- **Breaking**: split into five focused skills. All framework detection, target selection, generation,
  and verification logic moved to four new skills — **unit-test-creator**, **integration-test-creator**,
  **contract-test-creator**, **e2e-test-creator** — each with its own triggers, workflow, stack-specific
  references, examples, smoke tests, discovery files, lint target, installer target, and documentation
  entry (see their own sections below). test-writer now only classifies a level-unspecified "write tests"
  request and dispatches to exactly one of the four, relaying its report verbatim — mirrors the
  `who-owns-x-bot`/`release-readiness-checker` composition pattern.
- Shared principles across all four dispatch targets — test-first evidence, test-quality rules, refactor
  limits, and the report-format skeleton — moved into a new shared framework file:
  `docs/skill-framework/shared/test-creation-principles.md`. Each skill's own `reference/skill-contract.md`
  and `reference/test-quality-deltas.md` link there and state only their level-specific deltas.
- Removed from test-writer: `scripts/`, `tests/` (re-homed as unit-test-creator's own artifact),
  `workflow/{detect-conventions,select-targets,generate-tests,verify-and-iterate,report}.md`,
  `reference/{gate-policy,test-quality-checklist,framework-detection,report-format}.md`.
- Added to test-writer: `workflow/classify.md` (ask-once level gate, never guesses between levels),
  `workflow/delegate.md` (dispatch + verbatim relay), `reference/level-classification.md` (keyword
  heuristics mirroring `skill-routing.md`, so classification can't drift from the canonical routing
  table).
- `make install-test-writer` now chains installing all four dispatch targets — the router is useless
  without them.
- Callers who already know the level should invoke the matching `*-test-creator` skill directly and skip
  the router — new "level already named" rows in `skill-routing.md` and `SKILL.md § When to use`.

### Initial release (2026-08-06)

- New skill — generates and backfills automated tests for a target repository. Detects the repo's own
  test framework/conventions (pytest, Jest/Vitest/Mocha, Go `testing`, JUnit via Maven/Gradle,
  RSpec/Minitest, xUnit/NUnit/MSTest, `cargo test`) via `scripts/detect-test-framework.sh`, then writes
  tests matching that convention for changed code (diff mode) or an existing coverage gap (backfill
  mode), runs them, and iterates on failures.
- Non-negotiable: never modifies production code to force a failing test green, and never `.skip`/
  `xfail`/deletes an assertion to hide a failure without flagging it — a probable production bug found
  while testing is reported as a finding and handed to **loop-task-implementer**/**pr-review**, not
  silently resolved.
- No MCP of its own; composes with **pr-review** (existing-test-quality review, production-bug flags on
  an MR) and **loop-task-implementer** (production-bug fixes) via cross-skill handoffs only, never a hard
  install dependency.
- `scripts/detect-test-framework.sh` + `scripts/test-framework-markers.sh`, with a pytest suite
  (`tests/test_detect_test_framework.py`) over marker-file fixtures under
  `tests/fixtures/test-framework-detect/`.
- Full shared-framework compliance: `SETUP.md`, `README.md`, `examples.md`,
  `reference/{skill-contract,phase-index,lazy-load-index,gate-policy,test-quality-checklist,
  framework-detection,report-format,smoke-test,pressure-tests}.md`; new rows in `skill-routing.md`,
  `cross-skill-escalation.md`, `prompt-injection.md`, and `smoke-test-conventions.md`.

  Note: this initial-release entry describes test-writer's original design before the router rewrite
  above; its detection/generation logic now lives in **unit-test-creator** (see below).

## unit-test-creator

### Initial release (2026-08-06)

- New skill — split out of test-writer's original detection/generation logic. Isolated, fast,
  function/class-level tests with every external dependency mocked or stubbed. Detects the repo's test
  framework (pytest, unittest, Jest, Vitest, Mocha, Go `testing`, JUnit 4/5, RSpec, Minitest,
  xUnit/NUnit/MSTest, `cargo test`) via `scripts/detect-test-framework.sh` +
  `scripts/test-framework-markers.sh` (re-homed from test-writer, same 11-ecosystem coverage), writes
  tests for changed code (diff mode) or an existing coverage gap (backfill mode), runs them, and iterates
  on failures.
- A target that can't be isolated without a real dependency, with no existing mocking convention, gates
  `UNTESTABLE_WITHOUT_FIXTURE` and escalates to **integration-test-creator** rather than faking isolation.
- Shared rules (test-first evidence, quality checklist, refactor limits, report skeleton) linked from
  `docs/skill-framework/shared/test-creation-principles.md`; `reference/test-quality-deltas.md` states
  only the unit-specific delta (mock everything).
- `tests/test_detect_test_framework.py` pytest suite over fixtures under
  `tests/fixtures/test-framework-detect/`.

## integration-test-creator

### Initial release (2026-08-06)

- New skill — tests the real seam between a component and one real adjacent dependency (database, queue,
  cache, internal service); never mocks the dependency under test, unlike unit-test-creator. Detects both
  the base test runner and the real-dependency orchestration mechanism (testcontainers, docker-compose,
  embedded DB) plus the repo's integration-test naming/tag convention via
  `scripts/detect-integration-setup.sh` + `scripts/integration-markers.sh`.
- A target with no detected orchestration mechanism and no way to stand one up in-session gates
  `NEEDS_INTEGRATION_ENV` — a level-specific status on top of the shared vocabulary — rather than
  fabricating a fake dependency or silently mocking it (which would secretly make it a unit test).
- `tests/test_detect_integration_setup.py` pytest suite over fixtures under
  `tests/fixtures/integration-detect/`.

## contract-test-creator

### Initial release (2026-08-06)

- New skill — consumer-driven contract tests, Pact-style. Generates a **consumer** test (records
  expectations, produces a pact file) or a **provider verification** test (replays existing pact files
  against the real provider); `target.role` (`consumer`/`provider`) is required — HARD STOP if absent,
  never inferred from file location. Detects Pact tooling per ecosystem (pact-js, pact-python, Pact JVM,
  pact-go, Ruby pact) and whether a Pact Broker is configured, via `scripts/detect-pact-tooling.sh` +
  `scripts/pact-markers.sh`.
- Every interaction shape must trace to real, observed usage (an actual request-building call site, an
  existing API client method, or an OpenAPI/schema spec) — a target with none of these gates
  `NEEDS_OBSERVED_INTERACTION` rather than fabricating a plausible-looking payload.
- `tests/test_detect_pact_tooling.py` pytest suite over fixtures under `tests/fixtures/pact-detect/`.

## e2e-test-creator

### Initial release (2026-08-06)

- New skill — full user-journey tests through a real browser UI (Playwright, Cypress, or
  Selenium/WebDriver — web browser flows only, not API/CLI black-box journeys). Targets are **journeys**,
  not files: diff mode infers a journey from a new/changed route or page; backfill mode requires an
  explicit, non-empty `target.journeys` list (HARD STOP if absent). Detects browser tooling and layout
  convention via `scripts/detect-e2e-tooling.sh` + `scripts/e2e-markers.sh`.
- Asserts only on user-visible outcomes (text, ARIA role, URL, visible state) — never internal DOM/state
  details; never a hard-coded sleep, always the framework's own auto-waiting. Requires a reachable running
  app instance — gates `NEEDS_BROWSER_ENV` rather than fabricating what the UI would show.
- `tests/test_detect_e2e_tooling.py` pytest suite over fixtures under `tests/fixtures/e2e-detect/`.

## api-test-creator

### Initial release (2026-08-06)

- New skill — black-box API test suites (Postman collections, run via Newman) against a real, reachable
  running API instance. Targets are **endpoints**, not files: diff mode infers changed endpoints from
  route/handler diffs; backfill mode accepts an explicit endpoint list or file/directory paths that expand
  to the endpoints they define. Detects the repo's Postman/Newman tooling and canonical collection file
  via `scripts/detect-postman-tooling.sh` + `scripts/postman-markers.sh` — the live ambiguity gate here is
  "which collection file is canonical" (2+ collection files, no obvious naming convention) rather than
  "which tool," since Postman/Newman is this skill's only supported tool family.
- Writes request/assertion pairs (status code, response schema/fields, headers), chained via Postman
  variables/environment when a flow requires it (e.g. create-then-fetch). Every request/response shape
  traces to real observed usage (route-handler code, an OpenAPI spec, or domain-comprehension's
  `API_CATALOG.md`) — a target with none of these gates `NEEDS_OBSERVED_ENDPOINT` rather than fabricating
  a payload. Requires a reachable running API instance — gates `NEEDS_API_ENV` rather than fabricating a
  response.
- `reference/skill-contract.md` and `reference/test-quality-deltas.md` link
  `docs/skill-framework/shared/test-creation-principles.md` for shared rules and state only API-specific
  deltas (assert on status AND schema, not just "200 OK"; chain via variables, never hard-coded IDs from a
  prior manual run).
- `tests/test_detect_postman_tooling.py` pytest suite over fixtures under `tests/fixtures/postman-detect/`.
- New cross-skill escalation rows: api-test-creator ↔ integration-test-creator (in-process/testcontainers
  vs. black-box HTTP), api-test-creator ↔ contract-test-creator (standalone suite vs. consumer/provider
  agreement), api-test-creator ↔ e2e-test-creator (no browser involved).

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
  50 pytest cases under `tests/test_aggregate_migration_status.py` covering the squad-map parser, the
  path/name join, status derivation, and staleness reset-vs-accrue behavior.
- No `disable-model-invocation` — ambiently invocable, like new-hire-guide/release-readiness-checker; no
  wrapped-skill gate to police since nothing is invoked live.
- Design spec: [docs/superpowers/specs/2026-08-05-migration-program-manager-design.md](docs/superpowers/specs/2026-08-05-migration-program-manager-design.md).
- Wired into `make install-migration-program-manager` / `make lint-migration-program-manager` (the first
  lint target in this phase's build to also run a real pytest suite), root README, docs/README,
  docs/REPOSITORY, skill-routing.md, cross-skill-escalation.md, prompt-injection.md, phase-glossary.md.

## cost-optimization-sprint-planner

### Initial release (2026-08-05)

- New skill — item #10 of the [team-facing agents roadmap](docs/superpowers/plans/2026-08-05-team-facing-agents-roadmap.md):
  an org-wide cost/waste sweep that loops **k8s-overprovisioning-datadog** once per deployment in a
  `sweep_scope`, joined to squad ownership via **squad-map**'s `SQUAD_MAP.md`, implementing
  [org-rollup-schema.md](docs/skill-framework/shared/org-rollup-schema.md)'s `k8s_waste` adapter designed
  in Phase 4.
- Design research corrected two claims in the roadmap item's own wording before building against them:
  (1) "modeled on loop-task-implementer's per-task loop pattern" is inaccurate — loop-task-implementer's
  own orchestrator works exactly one task at a time; the real precedent for looping a single-item,
  gate-heavy skill over many items is **backlog-runner**'s `queue-policy.md`, reused here as
  `reference/sweep-policy.md`; (2) k8s-overprovisioning-datadog's Phase 0b "Namespace ranking" is not
  documented as a standalone, report-only mode — its own text ties it to "drill into worst deployment,
  then continue resolve" — so this skill reuses Phase 0b's *query pattern* directly via Datadog MCP as its
  own pre-filter step, rather than delegating to an unsupported standalone-ranking invocation.
- `reference/gate-policy.md` — every live k8s-overprovisioning-datadog gate (ambiguous service/tag
  confirmation, insufficient-metrics/name-mismatch, VPA-active-unconfirmed, cost-rate confirmation,
  CCM-empty fallback, manifest-lookup-not-found) answered with k8s's own documented, non-guessing
  fallback. The cost-rate gate is the one genuinely new resolution: k8s's own text says to ask the user
  for their $/core rate before citing dollar figures on every run — this skill resolves it **once, before
  the sweep loop starts**, never per deployment, since re-deriving it per deployment would otherwise be
  the single biggest threat to running this skill unattended over many deployments.
- `reference/sweep-policy.md` — session-level state layered outside k8s-overprovisioning-datadog's own
  (which has no cross-run state at all — this is the first skill in the repo to ever run it more than
  once in a session), per-deployment failure isolation (`insufficient_metrics`/ambiguous-name never
  aborts the sweep), and batch-level stop conditions (`max_deployments_per_run`/`deadline`/
  `session_token_budget`) — no consecutive-failure circuit breaker, unlike backlog-runner's, since every
  k8s-overprovisioning-datadog gate resolves to a documented non-blocking fallback rather than a genuine
  escalation.
- No `disable-model-invocation` — ambiently invocable, like release-readiness-checker; a human is present
  for this flow but a gate-policy file is still needed because the fan-out over potentially many
  deployments would otherwise interrupt once per deployment, same reasoning release-readiness-checker's
  own gate-policy.md documents.
- No scripts of its own — k8s-overprovisioning-datadog has no CLI to wrap (unlike mysql-to-postgres-sql,
  which migration-program-manager wraps via a real Python script); this skill is pure markdown-workflow,
  like release-readiness-checker.
- Design spec: [docs/superpowers/specs/2026-08-05-cost-optimization-sprint-planner-design.md](docs/superpowers/specs/2026-08-05-cost-optimization-sprint-planner-design.md).
- Wired into `make install-cost-optimization-sprint-planner` / `make lint-cost-optimization-sprint-planner`,
  root README, docs/README, docs/REPOSITORY, skill-routing.md, cross-skill-escalation.md,
  prompt-injection.md, phase-glossary.md — and `org-rollup-schema.md`'s `k8s_waste` adapter section
  updated from "pending item #10" to "implemented by cost-optimization-sprint-planner."

## weekly-squad-digest

### Initial release (2026-08-05)

- New skill — item #11 of the [team-facing agents roadmap](docs/superpowers/plans/2026-08-05-team-facing-agents-roadmap.md),
  the last item on that list: a scheduled digest combining **migration-program-manager**'s
  `migration_program_rollup.json` and **cost-optimization-sprint-planner**'s
  `cost_optimization_sprint_rollup.json` — both already-computed `org_rollup_item` files — into one
  squad-grouped view. Neither producing skill is invoked live; `squad`/`squad_confidence`/`status`/
  `priority` are surfaced exactly as each already computed them. Confirmed the first skill in this repo to
  read and combine two already-computed rollup files rather than producing one of its own — both
  producing skills already documented "written so a future Weekly Squad Digest can reuse this," which
  this skill's design research confirmed rather than assumed.
- **Corrects a claim made in two other places before designing against it**: the roadmap item's own
  wording ("squad-map — routing to the right channel") and
  [org-rollup-aggregation-layer-design.md](docs/superpowers/specs/2026-08-05-org-rollup-aggregation-layer-design.md)
  (which stated as settled fact that this skill would reuse "squad-map's own routing convention") both
  imply a squad→channel delivery mechanism that doesn't exist anywhere in squad-map's actual schema —
  confirmed by reading `SQUAD_MAP.md`'s real columns (two ownership *name* fields, no channel/contact/
  webhook column) and both cited precedents (who-owns-x-bot/incident-triage-agent each have one
  hardcoded/configured delivery target, not a per-squad table). This skill produces one combined markdown
  digest instead, with per-squad-channel delivery left to an external handler documented in its own
  `SETUP.md` — the same pattern backlog-runner's morning summary and incident-triage-agent's triage doc
  already use.
- `workflow/inputs.md` — `rollup_manifest` (both rollup paths individually optional, HARD STOP only if
  neither is set) + `staleness_warning_days` (default 14, display-only — never changes a computed
  `status`, unlike migration-program-manager's own staleness threshold, since this skill has no basis to
  recompute a status another skill already owns)
- `workflow/run-digest.md` — reads both rollups (a missing one is a gap, not a HARD STOP for the other),
  groups by squad then splits by `metric_type` into Migration status / Cost optimization sub-sections
  (never merged into one cross-metric ranking — a migration gate status and a dollar figure aren't
  comparable, and inventing a blended score would be new analysis logic the roadmap item's own text says
  this skill should not add)
- **No gate policy** — same reasoning as migration-program-manager: nothing is ever invoked live (neither
  producing skill, nor squad-map), so there's nothing to gate or confirm
- `disable-model-invocation: true` — same scheduled-trigger pattern as backlog-runner; a human asking a
  single-source status question still routes to migration-program-manager or
  cost-optimization-sprint-planner directly
- No scripts of its own — pure markdown-workflow, like cost-optimization-sprint-planner
- Design spec: [docs/superpowers/specs/2026-08-05-weekly-squad-digest-design.md](docs/superpowers/specs/2026-08-05-weekly-squad-digest-design.md).
- Wired into `make install-weekly-squad-digest` / `make lint-weekly-squad-digest`, root README,
  docs/README, docs/REPOSITORY, skill-routing.md, cross-skill-escalation.md, prompt-injection.md,
  phase-glossary.md — the last skill of the 11-item team-facing agents roadmap.

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
