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

### Fixed (round-3 review, same day)
- **Round-2's JSON-artifact-path fix was applied to `workflow/run-sweep.md` but not propagated to two
  other reference files that describe the identical mechanism.** `reference/sweep-policy.md`'s
  `decision_graph_ref` state comment and `reference/report-format.md`'s `evidence_ref` rule both still
  asserted the disproven round-1 mechanism verbatim — "this skill's own invocation always requests [a
  per-deployment filename], never the renderer's own single default filename" — the literal opposite of
  what `run-sweep.md` §2 now correctly says (the renderer only ever supports its own single default
  filename; this skill's own workflow moves/renames it afterward). Since both files are independently
  lazy-loadable during the Run sweep phase, an implementer loading either one without cross-checking
  `run-sweep.md` word-for-word would be pointed straight back at the retired mechanism. Fixed: both files
  now match `run-sweep.md`'s corrected description exactly.
- **`cost_rate.provider` had no enforced HARD STOP.** `workflow/inputs.md`'s Required table only
  triggered its HARD STOP on `cost_rate` being entirely absent — a `cost_rate` present but missing
  `provider` would silently pass Inputs despite prose elsewhere (and `reference/gate-policy.md`'s own
  non-AWS CCM gate) treating `provider` as required. `sweep_scope`'s own row in the same table already
  demonstrated the right pattern (a sub-field-level HARD STOP condition); extended it to `cost_rate` too.
- Tightened the `squad_confidence` normalization instruction to call out the empty/whitespace-only
  Confidence cell case explicitly (`UNKNOWN` directly), matching migration-program-manager's real
  `normalize_confidence()` guard as precisely as the earlier round's fix only did in spirit.

Found by a third adversarial review agent specifically hunting for "fixed the concept in one place but
left contradicting prose elsewhere" — the same failure shape round 2 found twice in round 1's fixes,
recurring once more in round 2's own JSON-artifact-path fix.

### Fixed (round-4 review, same day)
- **`cost_rate.provider`'s new HARD STOP (round 3) didn't go far enough — `dollars_per_core_month` and
  `dollars_per_gib_month` were just as effectively required as `provider` but still unenforced.**
  `workflow/inputs.md`'s prose only ever called out `provider` as "a required field within `cost_rate`,"
  and the Required table's HARD STOP only checked for it. But whether any given deployment's own graph
  will have real CCM cost data isn't knowable until that deployment is actually assessed
  (`reference/gate-policy.md`'s own "CCM empty" row) — a `cost_rate` that HARD-STOP-passed Inputs with
  `provider` set but no dollar figures would leave `cost-estimation.md`'s `monthly_savings_cpu`/
  `monthly_savings_mem` formulas with no `$/core/mo`/`$/GiB/mo` to multiply by on the first CCM-empty
  deployment the sweep hit — undefined cost math on `monthly_savings_total`, the field this skill ranks
  its entire report by. Fixed: `workflow/inputs.md`'s Required table and prose, `SKILL.md`'s mirrored
  table, `reference/phase-index.md`, and `examples.md`'s HARD STOP scenario row now all HARD STOP on
  `cost_rate` missing `provider`, `dollars_per_core_month`, *or* `dollars_per_gib_month` — not `provider`
  alone.

Found by a fourth adversarial review agent, tasked specifically with re-running round 3's own
"propagation failure" hunt as a general methodology rather than a one-off — the JSON-artifact-path and
`AUTH_FAILURE` mechanisms, the `cost_rate.provider`/`squad_confidence`/`service_aliases`/`output_dir`
facts, and the `stopped_reason` six-value enum were all re-checked across every file that asserts them and
found consistent; this was the one genuinely new gap, a completeness gap in round 3's own fix rather than
a contradiction between files.

### Fixed (round-5 review, same day)
- **`sweep_scope.env` was marked "required" in its own shape comment but, like `cost_rate`'s dollar fields
  before round 4, had no enforced HARD STOP.** `workflow/inputs.md`'s Required table only checked that one
  of `deployments`/`namespace_prefilter` was set — a `sweep_scope` with one of those but no `env` would
  pass Inputs cleanly, then leave `workflow/run-sweep.md` §2 and `reference/sweep-policy.md` §3's "assess
  `<deployment>` in `<env>`" invocation template with no environment to scope the metrics query against on
  every deployment in the sweep — a silent wrong-environment result, not a caught error, and exactly the
  kind of unenforced-but-load-bearing sub-field round 4's reviewer flagged as worth a follow-up skim.
- **`sweep_scope.namespace_prefilter.top_n_namespaces`/`top_n_deployments_per_namespace` had no stated
  default and no enforcement when one was missing while the other was present.**
  `reference/sweep-policy.md` §2 uses both directly with no documented fallback; guessing `0` would
  silently produce an empty candidate list indistinguishable from a genuinely empty scope, guessing
  "unbounded" would silently assess every deployment in every ranked namespace, blowing past the bounded
  pre-filter the caller asked for and burning far more of `session_token_budget`/wall-clock time than
  intended.
- Fixed: `workflow/inputs.md`'s Required table and `sweep_scope` shape prose, `SKILL.md`'s mirrored table,
  `reference/phase-index.md`'s quick-paths table, and `examples.md`'s HARD STOP scenario row now all HARD
  STOP on `sweep_scope` missing `env`, missing both `deployments` and `namespace_prefilter`, or
  `namespace_prefilter` being the active mode but missing `top_n_namespaces`/`top_n_deployments_per_namespace`
  — the same file set round 4 touched for `cost_rate`, updated the same way for `sweep_scope`'s own
  equivalent gap.

Found by a fifth adversarial review agent, tasked narrowly with (a) confirming round 4's `cost_rate` fix
propagated cleanly (it had — no further fix needed there; `docs/superpowers/specs/2026-08-05-
cost-optimization-sprint-planner-design.md`'s Interface Contract table is stale against it, but design
specs in this repo are established as point-in-time planning artifacts, not living docs — confirmed by
checking migration-program-manager's own design spec, never touched across that skill's seven review
rounds — so left as-is) and (b) one more skim for the same "effectively required but unenforced sub-field"
shape elsewhere in `sweep_scope`/`cost_rate`. `cost_rate.cost_basis` and the stated Optional-table defaults
(`max_deployments_per_run`/`deadline`/`session_token_budget`/`output_dir`/`squad_map_config_path`) were all
re-checked and found genuinely fine — cleared, not just unexamined.
