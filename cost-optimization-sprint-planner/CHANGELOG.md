# Changelog — cost-optimization-sprint-planner

All notable changes to the cost-optimization-sprint-planner skill. Per-file `workflow_version` in
`workflow/*.md` frontmatter should match the version of the latest entry below that names that file.

## [1.0.0] — 2026-08-05

### Added
- Initial skill release — org-wide sweep wrapper around k8s-overprovisioning-datadog, implementing
  [org-rollup-schema.md](../docs/skill-framework/shared/org-rollup-schema.md)'s `k8s_waste` adapter
  (already fully specified in Phase 4, before this skill existed)
- `workflow/inputs.md` — `sweep_scope` (explicit deployment list or namespace pre-filter config) +
  `cost_rate` (no default — an operational policy decision) + `max_deployments_per_run`/`deadline`/
  `session_token_budget` parsing, HARD STOP on missing required fields
- `workflow/run-sweep.md` — optional namespace/deployment waste-ranking pre-filter (Datadog MCP queries
  run directly, reusing k8s-overprovisioning-datadog's own Phase 0b query definitions rather than
  delegating to a standalone-ranking mode that skill doesn't document), sequential per-deployment sweep
  loop, join, rank, render
- `reference/gate-policy.md` — every live k8s-overprovisioning-datadog gate (ambiguous service/tag
  confirmation, insufficient-metrics/name-mismatch, VPA-active-unconfirmed, cost-rate confirmation,
  CCM-empty fallback, manifest-lookup-not-found) with a scripted answer reused from k8s's own documented
  fallback — the cost-rate gate is the one genuinely new resolution: asked once, sweep-wide, before the
  loop starts, never re-derived per deployment
- `reference/sweep-policy.md` — the sweep loop's own session-level state, candidate-list construction,
  per-deployment failure isolation, and batch-level stop conditions, modeled directly on
  [backlog-runner/reference/queue-policy.md](../backlog-runner/reference/queue-policy.md) — **not**
  loop-task-implementer's own orchestrator, which works exactly one task at a time and has no
  multi-item batch loop of its own (a fabrication risk caught during design research and corrected before
  this skill was built, not after)
- No `disable-model-invocation` — ambiently invocable, like release-readiness-checker; a human is present
  for this flow but a gate-policy file is still needed because the fan-out over potentially many
  deployments would otherwise interrupt once per deployment
- No scripts of its own — k8s-overprovisioning-datadog has no CLI to wrap (unlike mysql-to-postgres-sql,
  which migration-program-manager wraps via a real Python script); this skill is pure markdown-workflow,
  like release-readiness-checker
- Shared framework compliance (confidence-bands, cross-skill-escalation, prompt-injection, skill-routing,
  phase-glossary)
- Design spec: [docs/superpowers/specs/2026-08-05-cost-optimization-sprint-planner-design.md](../docs/superpowers/specs/2026-08-05-cost-optimization-sprint-planner-design.md)
  — corrects two claims in the roadmap item's own wording that didn't match the actual code (the
  loop-task-implementer modeling claim above, and Phase 0b's namespace ranking not actually being
  documented as a standalone report-only mode) before designing against them

### Fixed (round-1 review, same day)
- **`auth_failure` — a real, Critical, sweep-wide k8s-overprovisioning-datadog gate — was missing
  entirely.** `gate-policy.md`'s per-deployment table and `sweep-policy.md`'s "no circuit breaker needed"
  claim covered every *per-deployment* gate but missed this one, which is an environment-level failure
  (broken/expired Datadog MCP credentials) that would recur identically on every remaining candidate.
  Added as a genuine sweep-stopping condition (`outcome: AUTH_FAILURE` / `stopped_reason: AUTH_FAILURE`),
  distinct from every other gate's isolate-and-continue treatment.
- **`evidence_ref`/`decision_graph_ref` pointed at an artifact k8s-overprovisioning-datadog never
  produces.** k8s-overprovisioning-datadog's own deliverable is chat-rendered markdown; it only writes a
  `decision-graph.json` file when explicitly asked (`render/json.md`). `workflow/run-sweep.md` § 2 now
  explicitly requests that file artifact per deployment, written to
  `<output_dir>/decision-graph-<deployment>.json` (new optional `output_dir` input) — `evidence_ref` now
  points at a file this skill's own invocation actually causes to exist.
- **`squad_confidence` was entirely absent from the join logic and report**, despite being part of
  `org_rollup_item`'s own shape and despite migration-program-manager's own CHANGELOG recording a
  dedicated fix for the identical field on the identical schema. Added to the Join step, the report's
  Confidence column, and a Notes callout for LOW/UNKNOWN matches.
- **The `ownership.datadog.service_aliases` fallback was under-specified to the point of not actually
  working as described** — it's a repo-name→service-name map (squad-map's own resolution direction), so
  using it here requires a *reverse* lookup (search values for a match, join on the resulting repo name)
  that no file described, and no file said where this skill would even read the config from. Specified
  the reverse-lookup mechanics explicitly and added a new optional `squad_map_config_path` input the join
  step actually reads.
- **A non-AWS CCM metric-path gate** (`queries.md`: *"`aws.cost.*` is AWS-specific — for GCP/Azure ask the
  user for their CCM metric paths"*) wasn't enumerated in `gate-policy.md`, risking an un-scripted
  per-deployment ask on a non-AWS sweep despite the "cost-rate resolved once" guarantee. Added with a
  scripted answer (skip CCM sweep-wide on non-AWS `cost_basis` unless the caller separately supplies CCM
  metric paths).
- **The ambiguous-service-tag scripted answer over-generalized k8s's own documented default.** k8s's real
  fallback is specifically "default `env:production`," not "default to whatever `sweep_scope.env` is." A
  non-production sweep (e.g. `staging`) hitting a genuinely ambiguous tag would have silently trusted an
  env value k8s's own docs never describe as a safe default. Restricted the scripted default to
  `sweep_scope.env == production`; other envs fall through to "proceed with unknown."
- **`stopped_reason: "completed"` wasn't a value in the skill's own declared enum**, and the `SCOPE_EXHAUSTED`
  value it substituted for conflated two different conditions (nothing to assess at all, vs. every
  candidate successfully assessed). Added `COMPLETED` as a genuine sixth enum value, distinct from
  `SCOPE_EXHAUSTED` (now reserved for a genuinely empty candidate list).

Found by an adversarial review agent that cross-checked every quoted gate/field/schema claim against the
real k8s-overprovisioning-datadog, squad-map, and org-rollup-schema.md source files rather than trusting
this skill's own docs.

### Fixed (round-2 review, same day)
- **Round-1's `squad_confidence` fix carried the `SQUAD_MAP.md` Confidence cell through unnormalized.**
  A real Confidence cell can carry an annotation (`MEDIUM ⚠️` on a Conflicts-adjacent row), which round 1
  claimed to carry through "unchanged" — that would violate `org-rollup-schema.md`'s own `HIGH | MEDIUM |
  LOW | UNKNOWN` enum, the exact bug migration-program-manager's `normalize_confidence()` was built to
  close on this identical schema, cited by round 1's own commit message but not actually applied. Fixed:
  take the leading enum token, uppercased, falling back to `UNKNOWN`.
- **Round-1's per-deployment JSON file artifact request asked k8s-overprovisioning-datadog for a
  capability its own docs don't support.** `render/json.md` documents only one hardcoded filename
  (`decision-graph.json`), no parameter for a caller-specified path — so requesting
  `decision-graph-<deployment>.json` per invocation wasn't achievable through k8s's documented interface,
  and `evidence_ref` risked pointing at nothing reliable (or a collided file across deployments). Fixed:
  this skill's own workflow now moves/renames the resulting `decision-graph.json` to
  `<output_dir>/decision-graph-<deployment>.json` itself, immediately after each invocation returns — a
  file-move step this skill controls, never a capability requested of the wrapped skill.
- **`workflow/run-sweep.md`'s frontmatter `consumes` list was stale** — missing the two new inputs
  (`output_dir`, `squad_map_config_path`) round 1 itself introduced and the workflow body already read.
- **The `service_aliases` reverse-lookup had no tie-break for an ambiguous map** (two repo-name keys
  mapping to the same Datadog service name — plausible in a monorepo-heavy org per
  `config-schema.md`'s own monorepo section). Fixed: an ambiguous match is treated as no match at all
  (falls through to `squad: UNKNOWN`) rather than silently picking whichever key the search hits first.
- **The non-AWS CCM gate's scripted answer required parsing `cost_rate.cost_basis`'s free text** for a
  cloud-provider name, with no defined algorithm for the no-provider-named or ambiguous case — and sat in
  tension with `workflow/inputs.md`'s own "never parsed for instructions" framing of that field. Fixed:
  added a required, structured `cost_rate.provider` enum (`aws | gcp | azure | other`) that the gate
  branches on directly; `cost_basis` stays purely descriptive, never parsed to drive behavior.
- **`reference/smoke-test.md` had no scenario for the new `AUTH_FAILURE` sweep-stop path or the new
  `cost_rate.provider` gate**, both genuinely new behavior with no smoke coverage. Added both to the
  Degraded paths table.

Found by a second adversarial review agent verifying round-1's fixes against the sources they cited
rather than trusting the round-1 commit message — in three of six cases, the fix's own cited source
didn't actually support the conclusion drawn from it.
