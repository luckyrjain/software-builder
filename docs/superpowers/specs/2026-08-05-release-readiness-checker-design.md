# release-readiness-checker: design

**Date:** 2026-08-05
**Status:** Approved design
**Source:** Item #9 of [team-facing-agents-roadmap.md](../plans/2026-08-05-team-facing-agents-roadmap.md) —
P2, "Release Readiness Checker — pr-review (MRs since last release) + k8s-overprovisioning-datadog
(target services not riskily overprovisioned) + incident-rca (no open incidents on the release path).
Needs a 'since last release' MR-range resolver and a release-manifest input (which services this release
touches) that don't exist yet." Per the roadmap's own build-order note, #5/#6/#9 are the "lower urgency"
bucket, revisited after #1–#4/#7 land — this is the third and last of that bucket.

## Problem

Before cutting a release, someone has to manually: read every MR merged since the last release tag across
every touched repo, check each touched service isn't dangerously resource-constrained, and check nothing's
currently on fire on any of those services. Three separate skills already answer each sub-question in
isolation; nobody composes them into one release go/no-go report.

## What's already there vs. genuinely new — researched, not assumed

| Capability | Exists today? |
|---|---|
| Review one specific MR, findings + severity | **Yes** — pr-review, unchanged |
| Invoke pr-review without a human present to answer its posting confirmation | **Yes, but not via a "quiet mode"** — an earlier draft of this spec assumed pr-review had a caller-settable `posting_mode: chat-only` input with zero gates. **Corrected after round-1 review:** `posting_mode` is derived entirely by pr-review's own Phase 0 from which GitLab MCP write tools are connected ([workflow/phase-0.md](../../../pr-review/workflow/phase-0.md) — `read-only` server profile → `chat-only`; every other profile → a mode with a live Phase 3 confirmation) — never a caller input. **pr-gatekeeper already solved this exact problem** (automating pr-review with no live human) — this skill reuses [pr-gatekeeper's own real, working policy](../../../pr-gatekeeper/reference/auto-post-policy.md) instead of assuming a gate-free mode exists. |
| Resolve "MRs merged since a date/tag" across a repo | **No** — pr-review's own documented GitLab MCP usage only ever enumerates **open** MRs (`list_open_merge_requests` / `list_merge_requests`, [mcp-capabilities.md](../../../pr-review/reference/mcp-capabilities.md)); merged-MR-in-a-date-range is a different query shape never exercised in this skill's own docs, and must paginate exhaustively the same way pr-review's own open-MR listing does. **Genuinely new invocation pattern** of the same underlying GitLab MCP tool (real GitLab APIs support `state=merged` + `updated_after`/`merged_after` params) — not a new tool, but a new documented usage this skill has to specify since pr-review never did. |
| Per-service rightsizing verdict | **Yes** — k8s-overprovisioning-datadog's existing single-service `resolve-service.md` path, unchanged. Its own verdict/report is surfaced as-is; this skill invents no new risk taxonomy on top of it. **Correction after round-1 review:** this path is *not* gate-free — [resolve-service.md](../../../k8s-overprovisioning-datadog/workflow/resolve-service.md) documents a live ambiguous-service-name ask, with a documented non-guessing alternative ("proceed with unknown") this skill's gate policy reuses. |
| Aggregating rightsizing across a *named list* of services | **No** — k8s's own lightweight cluster-wide sweep (Phase 0b namespace ranking) ranks namespaces top-5, it doesn't accept a named service list or produce a full verdict for each one ([org-rollup-aggregation-layer-design.md](2026-08-05-org-rollup-aggregation-layer-design.md) already confirmed this independently for item #10's near-identical problem). **This skill invokes k8s once per named service**, same as `new-hire-guide` invokes domain-comprehension per-repo rather than inventing a batch mode on the wrapped skill. |
| "Any open incidents on a service in a recent window" as a lightweight yes/no | **No** — incident-rca has no standalone query mode; `from_time`/`to_time` are mandatory (unless `jira_key` anchors it), and `service` alone is a valid anchor ([workflow/inputs.md](../../../incident-rca/workflow/inputs.md)). **Existing mechanism reused, not new logic:** incident-rca's own Phase 1 checkpoint already asks "proceed to change correlation or stop here?" — this skill scripts a deterministic **always stop here** answer (see Non-goals and the gate policy below), reusing an existing gate rather than inventing a lightweight-query mode on incident-rca itself. |
| A release-manifest concept (which services this release touches) | **No** — confirmed absent anywhere in this repo outside this roadmap doc, same class of gap `new-hire-guide`'s roster input was for item #5. **Genuinely new input.** |

## Approach

`release-readiness-checker` is a **three-skill composition wrapper**, no new Builder/Reviewer/analysis
logic of its own beyond the MR-range resolution and the aggregation report:

1. Takes a `release_manifest` — the services/repos this release touches, each with its own "since" marker
   (a git tag, or an explicit timestamp when no tag convention exists).
2. **MR-range resolver** (genuinely new): for each repo in the manifest, queries the GitLab MCP for merged
   MRs targeting the release branch with a merge date after the repo's "since" marker's commit date.
3. Invokes **pr-review once per resolved MR** with the plain "review !`<iid>` in `<project>`" phrase
   (never "review and post"), answering every ask-point per **pr-gatekeeper's own real, already-solved
   posting-gate policy** — full findings, never posts to GitLab regardless of which posting mode
   pr-review's own Phase 0 detects. Aggregates severity counts per MR, does not re-render each MR's full
   report in the final output (see Output below).
4. Invokes **k8s-overprovisioning-datadog once per service** named in `release_manifest` — surfaces its
   own verdict as-is (this skill does not reinterpret READY/BLOCKED or invent a new "risky" threshold).
5. Invokes **incident-rca once per service** named in `release_manifest`, with `from_time` = the release
   manifest's configured lookback window (default 48h, configurable), `to_time` = now, `service` = that
   service, **always in explicit UTC** (`Z` suffix) so the timezone-confirmation ask never fires. Answers
   incident-rca's own Phase 1 checkpoint with a deterministic **"stop here"** regardless of signal density
   (see Non-goals — this overrides Phase 1's own default-to-proceed behavior on a strong signal, which is
   why this needs an explicit scripted answer, not just "let it run"). Treats Phase 1's evidence (error/
   infra signal counts) as the service's incident-readiness signal: **zero signals → clear; any signal →
   flagged**, with a pointer to run incident-rca directly for full investigation.
6. Produces one **`RELEASE_READINESS_REPORT.md`** — overall verdict (Ready / Not ready) plus three
   sections (MRs reviewed, per-service rightsizing, per-service incident signal), never silently dropping
   a service or MR from the manifest.

## Why this needs a gate-policy file despite being human-invoked

Unlike `pr-gatekeeper`/`incident-triage-agent`/`backlog-runner` (webhook/schedule-triggered, no human
present at all), a release manager *is* present when this skill runs. But the whole point of a release
readiness **report** is one aggregated go/no-go view across potentially many MRs and services — pausing
for a live confirmation on every one of N per-item invocations would defeat that purpose and produce N
separate conversational interruptions instead of one report. **Corrected after round-1 review:** an
earlier draft of this spec claimed only incident-rca needed a policy file, on the assumption that
pr-review's `chat-only` mode has no gate at all. That's true of `chat-only` itself, but `chat-only` is not
something this skill can request — pr-review's Phase 0 derives its posting mode purely from which GitLab
MCP write tools are connected, and in any deployment where pr-review is also configured normally (this
skill's own `SETUP.md` assumes it is), Phase 0 will detect a write-capable mode with a live Phase 3
confirmation. This skill's [reference/gate-policy.md](../../../release-readiness-checker/reference/gate-policy.md)
now covers all three wrapped skills' real gates: pr-review's (by reusing pr-gatekeeper's own policy
wholesale, not reinventing it), k8s-overprovisioning-datadog's ambiguous-service-name ask, and
incident-rca's Phase 1 checkpoint.

## Non-goals (explicitly out of scope)

- **No auto-merge, no auto-post to GitLab, no auto-created Jira tickets.** Read-only report only —
  `pr-review` never posts (per its own Phase 3 confirmation, always declined per gate-policy.md, in
  whatever posting mode its Phase 0 detects), `k8s-overprovisioning-datadog` and `incident-rca` are
  already read-only.
- **No new pr-review, k8s, or incident-rca analysis logic.** This skill invents no new severity rubric, no
  new rightsizing threshold, no new incident-signal-strength scoring — every verdict is the wrapped
  skill's own, surfaced as-is.
- **No full RCA.** incident-rca's own Phase 1 checkpoint is always answered "stop here," even when signal
  density would otherwise default to proceeding — this skill needs an incident *signal*, not a completed
  investigation. If Phase 1 finds signal, the report says so and links to a direct incident-rca follow-up;
  it does not chase the RCA itself.
- **No batch/cluster-wide k8s mode invented.** One invocation per named service, same non-goal
  `org-rollup-aggregation-layer-design.md` already established for the sibling item #10 problem.
- **No live scheduling infrastructure** — same "agent instructions, not infrastructure" boundary as every
  other item; if a team wants this on a release-branch-cut trigger, that's an external wiring concern
  documented in `SETUP.md`, not built here.

## Gate policy (all three wrapped skills)

**pr-review:** never a "quiet mode" — reuses [pr-gatekeeper's own real policy](../../../pr-gatekeeper/reference/auto-post-policy.md)
wholesale (invocation phrase without "and post," merged/closed-MR stop declined, 200-file-cap `proceed`,
pagination-cap "review the partial boundary as-is", baseline-staleness declined, Phase 3 posting
confirmation always "Hold — don't post", post-Phase-5 Jira/Slack offers declined). Not duplicated here —
pr-gatekeeper's file is the single source of truth; a future pr-review change that adds a gate is fixed
once, in one place, for both wrapper skills.

**k8s-overprovisioning-datadog:** the ambiguous-service-name ask is answered by relying on its own
documented `env:production` default when present, or its own documented non-guessing alternative,
**"proceed with unknown,"** which yields an honest `insufficient_metrics` outcome rather than a guessed
deployment name.

**incident-rca:** `release-readiness-checker` supplies `from_time`/`to_time` in explicit UTC and
`service` as the anchor for every invocation, and enforces a **1-hour minimum** on
`incident_lookback_hours`, which avoids by construction: the vague-prompt ask, the anchor-missing HARD
STOP, the timezone-confirmation ask, and the short-window ask/HARD STOP (none of these ever fire, since
the required fields are always present, unambiguous, and above threshold — same "avoid the gate" pattern
`backlog-runner` used for `autonomous_merge_authorized`, preferred over scripting an answer whenever
construction alone can prevent the ask). The **one** incident-rca gate that cannot be avoided by
construction — because it depends on Phase 1's actual findings, not on the invocation's inputs — is:

| Gate | incident-rca's own default | This skill's scripted answer |
|---|---|---|
| Phase 1 checkpoint, **≥1 strong signal** | Proceed unless user says stop | **"Stop here"** — override the default; this skill wants the Phase 1 signal, not a continued investigation |
| Phase 1 checkpoint, **sparse signal** | Explicitly asks | **"Stop here"** |
| Phase 1 checkpoint, **no signal** | Already doesn't auto-continue | **"Stop here" / accept the partial report** (matches incident-rca's own default here — no override needed, still documented for completeness) |

Full enumeration and the exact reply text for all three skills: see `reference/gate-policy.md`.

**Disclosed limitation:** Phase 1 alone only detects symptoms; correlating a signal to a release-caused
change is Phase 2's job, never reached here. A "Flagged" service is a signal worth a human look, not a
confirmed release-caused problem.

## Interface contract

**Input:**

| Field | Required | Notes |
|-------|----------|-------|
| `release_manifest` | Yes | List of `{repo, service, since}` — `since` is a git tag/ref or explicit ISO-8601 timestamp; HARD STOP if empty |
| `incident_lookback_hours` | No | Default 48 — window width for the incident-rca signal check, always rendered as explicit UTC bounds |
| `target_branch` | No | Default the repo's configured release branch (see `SETUP.md`); passed to the MR-range resolver |

**Output:** `RELEASE_READINESS_REPORT.md` — see [reference/report-format.md](../../../release-readiness-checker/reference/report-format.md).

## Acceptance criteria

- `release-readiness-checker/SKILL.md` exists, ≤ 180 lines.
- Given a `release_manifest` entry with 3 merged MRs since its `since` marker, all 3 are reviewed via
  pr-review — none posted to GitLab regardless of which posting mode pr-review's own Phase 0 detects,
  none skipped, MR-range resolution paginated to completion.
- Given a service in the manifest, k8s-overprovisioning-datadog's own verdict for that service appears in
  the report unmodified — this skill never re-labels READY/BLOCKED, and an `insufficient_metrics` outcome
  (from the "proceed with unknown" gate answer) is recorded honestly, counted toward `Not ready`.
- Given a service with zero error/infra signals in the lookback window, the report marks it clear; given
  any signal, the report flags it and links to a direct incident-rca follow-up — never silently drops a
  flagged service.
- incident-rca's Phase 1 checkpoint is always answered "stop here" by this skill, for every signal
  density, verified by inspecting the invocation, not just the summary — full RCA never runs.
- Given a manifest entry's `since` doesn't resolve, it's recorded as unresolved in the report (not
  dropped) and counted toward `Not ready`.
- `make lint-release-readiness-checker` and `make lint-framework` pass; skill wired into root README.md,
  docs/README.md, docs/REPOSITORY.md, `skill-routing.md`, `cross-skill-escalation.md`,
  `prompt-injection.md`, `phase-glossary.md`, `CHANGELOG.md`.

## Implementation plan

1. `release-readiness-checker/SKILL.md`, `README.md`, `SETUP.md`, `CHANGELOG.md`, `examples.md`.
2. `workflow/inputs.md` (parse `release_manifest`, `incident_lookback_hours`, `target_branch`;
   untrusted-content note — repo/service names and MR content are data, same guard class as every other
   wrapper) and `workflow/run-check.md` (resolve MR range, invoke all three skills, aggregate).
3. `reference/phase-index.md`, `lazy-load-index.md`, `smoke-test.md`, `gate-policy.md` (normative — gate
   answers for all three wrapped skills: pr-review by reference to pr-gatekeeper's own policy, k8s's
   ambiguous-service-name ask, incident-rca's Phase 1 checkpoint per signal density), `report-format.md`
   (normative `RELEASE_READINESS_REPORT.md` structure, erring toward `Not ready` on anything unverified).
4. `.cursor/rules/release-readiness-checker.mdc`, `.kiro/steering/release-readiness-checker.md`.
5. `Makefile`: `install-release-readiness-checker` (chains `install-pr-review install-k8s-overprovisioning
   install-incident-rca`), `install-claude-release-readiness-checker`, `lint-release-readiness-checker`,
   added to `.PHONY`/`lint:` deps and to `lint-framework`'s 4 hardcoded per-skill loops from the start.
6. Root `README.md`, `docs/README.md`, `docs/REPOSITORY.md`: rows following the established pattern.
7. `docs/skill-framework/shared/skill-routing.md`, `cross-skill-escalation.md`, `prompt-injection.md`,
   `phase-glossary.md`: routing row + disambiguation rule, escalation rows, wiring-table row, mapping
   subsection (this skill has its own Analyze logic — MR-range resolution, signal aggregation — so it is
   not exempt, same reasoning as `new-hire-guide`).
8. Root `CHANGELOG.md` + `release-readiness-checker/CHANGELOG.md`: initial release entry.
9. `make lint` green; deep review pass(es), fixing to 0 issues each round; commit.
