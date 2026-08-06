# Changelog — weekly-squad-digest

All notable changes to the weekly-squad-digest skill. Per-file `workflow_version` in `workflow/*.md`
frontmatter should match the version of the latest entry below that names that file.

## [1.0.0] — 2026-08-05

### Added
- Initial skill release — the first skill in this repo to read two already-computed `org_rollup_item`
  rollup files (migration-program-manager's `migration_program_rollup.json` and
  cost-optimization-sprint-planner's `cost_optimization_sprint_rollup.json`) and combine them, rather than
  producing a rollup of its own. Confirmed via design research: both producing skills already document
  "written so a future Weekly Squad Digest can reuse this" — this skill is that reuse, not new invention.
- `workflow/inputs.md` — `rollup_manifest` (both paths individually optional, HARD STOP only if neither
  is set) + `staleness_warning_days` (default 14, display-only — never changes a computed `status`,
  unlike migration-program-manager's own staleness threshold)
- `workflow/run-digest.md` — reads both rollups (a missing one is a gap, not a HARD STOP for the other),
  groups by squad then splits by `metric_type` into Migration status / Cost optimization sub-sections
  (never merged into one cross-metric ranking — the two `value` shapes aren't comparable), computes
  per-item staleness, renders
- **Corrects a claim made in two other places before designing against it**: the roadmap item's own
  wording ("squad-map — routing to the right channel") and
  [org-rollup-aggregation-layer-design.md](../docs/superpowers/specs/2026-08-05-org-rollup-aggregation-layer-design.md)
  (which stated as settled fact that squad-map has "its own routing convention" this skill would reuse)
  both imply a squad→channel delivery mechanism that doesn't exist anywhere in squad-map's actual schema
  (`SQUAD_MAP.md` has two ownership *name* columns, no channel/contact/webhook field) or in either cited
  precedent (who-owns-x-bot/incident-triage-agent both have one hardcoded/configured target, not a
  per-squad table). This skill produces one combined markdown digest instead, with per-squad-channel
  delivery left to an external handler documented in `SETUP.md` — the same pattern every other
  `disable-model-invocation: true` skill in this repo already uses (backlog-runner's morning summary,
  incident-triage-agent's triage doc)
- **No gate policy** — same reasoning as migration-program-manager: nothing is ever invoked live (neither
  producing skill, nor squad-map), so there's nothing to gate or confirm
- `disable-model-invocation: true` — same scheduled-trigger pattern as backlog-runner; a human asking for
  a single-source status question still routes to migration-program-manager or
  cost-optimization-sprint-planner directly
- No scripts of its own — pure markdown-workflow, like cost-optimization-sprint-planner
- Shared framework compliance (confidence-bands, cross-skill-escalation, prompt-injection, skill-routing,
  phase-glossary)
- Design spec: [docs/superpowers/specs/2026-08-05-weekly-squad-digest-design.md](../docs/superpowers/specs/2026-08-05-weekly-squad-digest-design.md)
  — this is the last item (#11) of the [team-facing agents roadmap](../docs/superpowers/plans/2026-08-05-team-facing-agents-roadmap.md)

### Fixed (round-1 review, same day)
- **`squad_confidence`'s "Notes callout" rule contradicted the report's own normative Structure
  template** — the template's Notes column was defined single-purpose (staleness only), with no room
  shown for a confidence callout, and the cited "same convention as cost-optimization-sprint-planner"
  precedent didn't actually match (that skill uses a dedicated Confidence column, not a Notes callout).
  Fixed: both tables now have a real Confidence column showing every item's `squad_confidence`, not just
  LOW/UNKNOWN ones — genuine parity with cost-optimization-sprint-planner's own report structure.
- **Migration items' staleness flag was effectively meaningless per-item.** migration-program-manager's
  `last_updated` is stamped at aggregation-run time (the same instant for every item that run), not a
  per-service signal — so a `last_updated`-derived age for migration items would tell you "how long since
  the aggregator last ran," not "which service's data is actually stale," despite this skill's own
  framing implying genuine per-item granularity. Fixed: migration items now prefer `staleness_days`
  (which genuinely does vary per service via persisted `gate_signature` comparison) when present, falling
  back to `last_updated`-derived age only if absent; cost items (no `staleness_days` equivalent) always
  use `last_updated`-derived age.
- **The same `service` appearing in both rollups under different squads** (a real, expected case — the
  two rollups resolve `squad` via different join mechanisms) **was acknowledged only in `SETUP.md`'s
  operator-facing troubleshooting table, never in the normative render spec.** A reader of
  `WEEKLY_SQUAD_DIGEST.md` could see the same service under two squad headings with no indication they're
  the same service. Fixed: added an explicit cross-referencing rule to `reference/report-format.md` and a
  detection step to `workflow/run-digest.md` § 2 — each side's Notes column now points at the other
  section/squad, never silently presented as two unrelated rows.

Found by an adversarial review agent that verified every field name, quote, and precedent claim against
the real source files (migration-program-manager's, cost-optimization-sprint-planner's, squad-map's own)
rather than trusting this skill's own docs — the central "squad-map has no routing convention" design
claim held up under scrutiny, but three implementation-level gaps in how the digest actually renders
staleness, confidence, and cross-rollup conflicts did not.

### Fixed (round-2 review, same day)
- **"Present" for `staleness_days` was undefined and readable as a truthiness check** — the round-1 fix
  said "prefer `staleness_days` when present" without defining "present," and `staleness_days: 0` (the
  normal value immediately after a gate signature changes, per migration-program-manager's own
  `compute_staleness`) is falsy in most implementations, so a naive read would silently fall back to the
  rollup-run-level `last_updated` age for exactly the items that had just made progress — reintroducing
  the bug round 1 fixed. Fixed: `workflow/inputs.md`, `workflow/run-digest.md` § 3, and
  `reference/report-format.md` now all say explicitly "present means the key exists, regardless of
  value — `staleness_days: 0` still counts and must still be used."
- **Cross-rollup `service` matching had no normalization rule**, despite the very precedent cited to
  justify it — [org-rollup-schema.md § 3](../docs/skill-framework/shared/org-rollup-schema.md#3-join-key-squad-map-is-the-only-authoritative-source)
  — explicitly documenting that service identifiers don't reliably match verbatim across systems. Fixed:
  `workflow/run-digest.md` § 2 step 4 and `reference/report-format.md` now state the match is
  exact-string only, best-effort, with a genuinely differing identifier string a known, accepted
  limitation rather than a guarantee.
- **The flagged staleness note's wording was inaccurate for migration items using `staleness_days`** — it
  read "last updated N days ago" even when the value actually measured "days since the gate last changed"
  (which is not the same as `last_updated`, always fresh for migration items). Fixed: the note text now
  differs by source — `"stale — gate unchanged for N days, re-run migration-program-manager"` for the
  `staleness_days` path, `"stale — last updated N days ago, re-run <aggregator skill>"` for the
  `last_updated`-derived path.
- **The re-run pointer in the stale note likely named the wrong skill.** The obvious reading pointed at
  `org_rollup_item.source_skill` (e.g. `mysql-to-postgres-sql`, `k8s-overprovisioning-datadog`) — the
  per-service/per-deployment tool, not the aggregator that actually regenerates the rollup file this skill
  reads. Fixed: the note always names the aggregator (migration-program-manager or
  cost-optimization-sprint-planner), never `source_skill`.
- `reference/smoke-test.md` and `examples.md` updated to match — the invocation table's staleness row was
  split into three (key-present-with-zero, migration stale, cost stale) and the same-service-different-squad
  scenario now also demonstrates the `; `-joined staleness + cross-reference Notes cell, so the joined
  format ships with at least one worked example instead of untested.

Found by a second adversarial review pass that re-verified round 1's fixes were correct and complete, then
re-read every consumer of the staleness/cross-reference mechanism looking specifically for the
"propagation failure" and "unenforced precision" patterns that recurred repeatedly in
cost-optimization-sprint-planner's own review rounds — all four findings were precision gaps in a
mechanism round 1 introduced correctly at the structural level but under-specified at the edge-case level.

### Fixed (round-3 review, same day)
- **`reference/report-format.md`'s own normative Notes-column template for the Migration status table was
  missing a required branch.** The file's cell formula only showed the `staleness_days`-present stale-flag
  case; `workflow/run-digest.md` § 3 (and this same file's own Rules prose) require a second, differently
  worded branch for when `staleness_days` is genuinely absent and a `last_updated`-derived age is used
  instead. An implementer following the literal template would never have flagged that case. Fixed: the
  template now shows both branches explicitly.
- **`examples.md` and `reference/phase-index.md` both said "ask" for the neither-rollup-path-set HARD
  STOP**, contradicting `workflow/inputs.md`'s own explicit "no human turn available for a scheduled
  run... do not guess" framing (mirrored correctly in `reference/smoke-test.md`). Fixed: both now say
  "stop and log the error," matching the rest of the skill.
- **The claimed sort order for the Migration status table only captured migration-program-manager's
  top-level status-bucket order** (blocked → stalled → in_progress → done), silently dropping its
  documented secondary sort — stalled items ranked by `staleness_days` descending, per
  migration-program-manager's own `workflow/run-rollup.md` § 2. Since this skill explicitly claims to
  reuse that ordering verbatim and forbids inventing its own, the gap meant a compliant implementer would
  render stalled rows in arbitrary order. Fixed: `workflow/run-digest.md` § 2 and
  `reference/report-format.md`'s template now state the secondary sort explicitly.
- **An unsupported claim about cost items' `last_updated` field** — three files asserted
  cost-optimization-sprint-planner's workflow "does set [it] per invocation" (implying genuine per-service
  precision, by contrast with migration's rollup-run-level stamp). Checked against
  cost-optimization-sprint-planner's own `SKILL.md`, `workflow/run-sweep.md`, `reference/report-format.md`,
  and `CHANGELOG.md`: none of them mention `last_updated` at all, let alone document how or when it's
  populated per item. Fixed: `workflow/inputs.md`, `workflow/run-digest.md` § 3, and
  `reference/report-format.md` no longer assert per-deployment precision for cost items' staleness signal
  — it's now described as "the only signal available," not a guaranteed per-service one.

Found by a third adversarial review pass that cross-checked every claim this skill makes about upstream
rollup producers' own conventions against those producers' actual source files, rather than trusting this
skill's own prose — a pattern that had already caught the squad-map routing fabrication during design and
recurred here at the implementation-detail level.

### Fixed (round-4 review, same day)
- **Root `README.md`'s Examples table still described the pre-round-1 (buggy) staleness mechanism** —
  "An item's `last_updated` is older than `staleness_warning_days`" as the universal trigger, with no
  mention of `staleness_days` precedence for migration items. Every one of this skill's own eight files
  was fixed in round 1 and stayed consistent through rounds 2-3, but the root README (added once in the
  initial commit, never touched by any fix commit) kept the original wrong claim — the exact
  "uniformly use `last_updated` for both" bug `workflow/inputs.md` explicitly warns against. Fixed to
  match the current mechanism.
- **`workflow/run-digest.md` § 3 — the normative step that actually builds the joined Notes string — never
  stated which of the staleness note / cross-rollup pointer comes first** when both apply, even though
  `reference/smoke-test.md`, `reference/report-format.md`'s template, and `examples.md`'s worked example
  all already agreed on "staleness note first" without that rule ever being stated in the one file that
  performs the join. Fixed: § 3 now states the order explicitly.

Found by a fourth adversarial review pass that re-verified rounds 1-3's fixes were consistent across all
eight in-skill files (found no new issues there — genuine convergence at that layer) and then widened scope
to the skill's own wiring into root-level shared docs, finding one propagation gap one level outside the
files rounds 1-3 had touched.
