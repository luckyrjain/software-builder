# Gate policy — incident-rca (normative)

**The one skill this wrapper needs a gate policy for.** pr-review's `chat-only` posting mode
([workflow/posting.md](../../pr-review/workflow/posting.md)) has no live gate at all — nothing to
document here. k8s-overprovisioning-datadog's single-service path has none either. Every entry below is
incident-rca's own, cited from its real source files, with this skill's scripted answer.

## Gates avoided by construction (not scripted)

These never fire because [workflow/inputs.md](../workflow/inputs.md) and
[workflow/run-check.md](../workflow/run-check.md) always supply the fields that would otherwise trigger
them — same "avoid the ask" preference `backlog-runner` used for `autonomous_merge_authorized`, over
scripting an answer whenever construction alone prevents it:

| incident-rca gate | Why it never fires here |
|---|---|
| Vague-prompt ask ("ask for time window and at least one anchor") — [workflow/inputs.md](../../incident-rca/workflow/inputs.md) | `service`, `from_time`, `to_time` are always supplied together |
| Anchor-missing HARD STOP | `service` is always a valid anchor on its own |
| Timezone-confirmation ask ("if `from_time`/`to_time` have no timezone suffix... ask") | Every timestamp this skill passes is explicit UTC (`Z` suffix) — see `workflow/inputs.md` § Normalization |
| Large-window-cost recommendation (">6 hours... recommend narrowing") | `incident_lookback_hours` defaults to 48h and is caller-configurable; if a caller sets a window >6h, this skill accepts the recommendation's advice silently (proceeds anyway) rather than narrowing on its own — a wider release lookback window is often intentional, not a mistake to second-guess |

## The one gate that cannot be avoided by construction

**incident-rca's Phase 1 checkpoint** ([workflow/phase-1.md](../../incident-rca/workflow/phase-1.md) §
"Phase 1 checkpoint (before Phase 2)") always fires after Phase 1 collection completes — it depends on
what Phase 1 actually found, not on this skill's inputs, so it cannot be constructed away.

incident-rca's own signal-density table:

| Signal density | incident-rca's own default | This skill's scripted answer |
|---|---|---|
| **≥1 strong signal** (error rate spike, top messages, OOM) | *"Announce counts + top finding; proceed unless user says stop"* — **proceeds by default** | **"Stop here."** This overrides incident-rca's own default — this skill wants the Phase 1 signal, not a continued investigation, regardless of how strong the signal is |
| **Sparse** (1 weak signal, partial coverage) | Explicitly asks: *"Signal is thin — continue to deploy correlation or stop here?"* | **"Stop here."** |
| **None** (both arrays empty) | *"Do not auto-continue — offer partial report... or widen window"* — already stops by default | **Accept the partial report; do not widen the window.** No override needed here — documented for completeness, since a caller reading this table should see all three densities handled explicitly, not assume the third is silently different |

**Every density answer is "stop here"** — this is deliberate and uniform, not signal-dependent. A strong
signal is exactly the case this skill most needs to catch and flag, which is why the default-to-proceed
behavior is overridden rather than left alone.

## What "stop here" produces

Per incident-rca's own **Partial report path (user says stop)**
([workflow/phase-5.md](../../incident-rca/workflow/phase-5.md)): a partial RCA rendered from completed
phases only (Phase 1 in this skill's case), header marked "Partial RCA — investigation stopped early,"
required sections including "Evidence collected" and "Gaps." [workflow/run-check.md](../workflow/run-check.md)
§ 4 reads this partial report's Phase 1 evidence (error/infra signal counts) as the service's
incident-readiness signal for `RELEASE_READINESS_REPORT.md` — it does not re-render the partial RCA
itself into the release report, only the counts and a follow-up pointer.

## Escalation, not override

If incident-rca reaches a state this policy doesn't cover (a gate not enumerated above, or a stop
request incident-rca itself refuses), treat it as genuine — this skill never bypasses incident-rca's own
judgment. Record the anomaly in the report's per-service row and fall back to flagging that service as
needing a direct incident-rca follow-up, same as any other flagged service.
