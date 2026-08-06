# Gate policy — all three wrapped skills (normative)

**Correction (round-1 review):** an earlier version of this file claimed pr-review's `chat-only` posting
mode could be requested as an input (`posting_mode: chat-only`) and therefore had no gate to answer. This
was wrong — `chat-only` is **derived by pr-review's own Phase 0** purely from which GitLab MCP write
tools are connected ([phase-0.md](../../pr-review/workflow/phase-0.md): *"read-only [server profile] |
none of the above [write tools] | `chat-only`"*); it is never a caller-supplied input, and pr-review's
`workflow/inputs.md`/`phase-0.md` frontmatter has no field for it at all. In any realistic deployment
where pr-review is also configured for normal write-capable use (which this skill's own
[SETUP.md](../SETUP.md) assumes), pr-review's Phase 0 will detect write tools and enter `full`/
`summary-only`/`general-only` — every one of which has a live Phase 3 posting-confirmation gate. This
file is corrected below to give pr-review its own real gate policy instead of assuming one away.

## pr-review — reuses pr-gatekeeper's own policy, unchanged

pr-gatekeeper already solved exactly this problem — automating pr-review with no live human to answer
its posting confirmation — and its policy is exactly what this skill needs too, with one input fixed
permanently: **`auto_post_authorized` is always treated as `false`.** This skill invokes pr-review the
same way pr-gatekeeper's own automation does when `auto_post_authorized: false`
([pr-gatekeeper/reference/auto-post-policy.md](../../pr-gatekeeper/reference/auto-post-policy.md)):

1. **Invocation phrase:** `"review !<merge_request_iid> in <project>"` — **never** "review and post,"
   for every resolved MR. This is the exact example phrase pr-review's own
   [SETUP.md](../../pr-review/SETUP.md) (`"/pr-review !482 in backend/payments — or review !482 in
   backend/payments"`) and [README.md](../../pr-review/README.md) document — `workflow/inputs.md`'s own
   Resolution branches section describes the resolution *logic* (IID + explicit project) but doesn't
   itself contain a literal example phrase.
2. Every other ask-point pr-review may hit follows
   [pr-gatekeeper's own enumerated policy](../../pr-gatekeeper/reference/auto-post-policy.md) verbatim —
   merged/closed-MR stop (decline the post-merge audit), early 200-file cap warning (`proceed`),
   pagination cap hit (`review the partial boundary as-is`), baseline staleness offer (decline, continue
   incrementally), **Phase 3 posting confirmation** (`"Hold — don't post"` — one of pr-review's own
   offered options, in every mode, including `general-only`'s always-on prompt and any draft-MR warning),
   and the post-Phase-5 Jira/Slack write-back offers (decline both).
3. Whether pr-review's Phase 0 detects `chat-only` (no prompt, nothing to reply to) or a write-capable
   mode (`full`/`summary-only`/`general-only`, Phase 3 always answered "Hold"), **nothing is ever posted
   to GitLab** — the outcome is identical either way, per pr-gatekeeper's own Outcome table. This skill
   takes pr-review's Phase 5 chat-rendered findings (severity-tagged), same as pr-gatekeeper does for its
   own held-review notification path, for the MRs-reviewed section of `RELEASE_READINESS_REPORT.md`.

No separate enumeration duplicated here — [pr-gatekeeper's own file](../../pr-gatekeeper/reference/auto-post-policy.md)
is the single source of truth for pr-review's gates; if pr-review adds a new ask-point, fixing
pr-gatekeeper's policy fixes this skill's too.

## k8s-overprovisioning-datadog

The wrapped skill starts with Kubernetes MCP-first source discovery. Authentication and capability
failures are **source-scoped**: Datadog failure does not block a service when Kubernetes MCP supplies
sufficient evidence, and Kubernetes MCP failure does not block a service when Datadog supplies sufficient
evidence. Preserve the wrapped verdict; only its `auth_failure` for **all viable sources** produces a
blocked assessment for that service.

**Correction (round-1 review):** an earlier version of this file claimed k8s-overprovisioning-datadog's
single-service path has no live gate. It does —
[resolve-service.md](../../k8s-overprovisioning-datadog/workflow/resolve-service.md) documents two:

| Gate | k8s's own text | This skill's scripted answer |
|---|---|---|
| Ambiguous service→tag confirmation | *"Confirm with `get_datadog_metric_context`... If ambiguous, ask the user **or default `env:production` when present**"* | Rely on the documented default — always resolve with `env:production` when present; only if genuinely still ambiguous with no `env:production` scope available does this become the next row |
| Service name mismatch (`insufficient_metrics` path) | *"Ask the user to confirm the correct deployment name... Only emit `insufficient_metrics` after ≥2 tag strategies and user confirmation (**or explicit "proceed with unknown"**)"* | **"Proceed with unknown."** This is k8s's own documented non-guessing alternative to a live ask — never invent a deployment/namespace name on this skill's own judgment |
| One Kubernetes MCP or Datadog source is unavailable/unauthorized | Source-scoped failure; continue when the other source covers required capabilities | Record the wrapped skill's degraded assessment as-is; never convert it into a release-wide auth failure |

A service that resolves to `insufficient_metrics` this way is recorded in
`RELEASE_READINESS_REPORT.md` **as `insufficient_metrics`, honestly** — not silently upgraded to
`READY` (which would hide a real gap) and not treated as `BLOCKED` (which would fabricate a finding k8s
never made). See [reference/report-format.md](report-format.md).

## incident-rca

Everything below is **avoided by construction** except the Phase 1 checkpoint, which cannot be:

| incident-rca gate | Why it never fires here |
|---|---|
| Vague-prompt ask | `service`, `from_time`, `to_time` are always supplied together |
| Anchor-missing HARD STOP | `service` is always a valid anchor on its own |
| Timezone-confirmation ask | Every timestamp this skill passes is explicit UTC (`Z` suffix) |
| Large-window-cost recommendation (>6h) | `incident_lookback_hours` default (48h) exceeds this; if a caller sets a larger window, this skill accepts the recommendation's advice silently rather than narrowing on its own — a wider release lookback is often intentional |
| **Short-window ask/HARD STOP** (<10 min warns-and-asks; <5 min blocks Phase 4 without confirmation) | `incident_lookback_hours` has a documented **minimum of 1 hour**, enforced in [workflow/inputs.md](../workflow/inputs.md) — well above both thresholds. A caller cannot configure this skill into the short-window ask at all |

**incident-rca's Phase 1 checkpoint always fires** (not conditional on signal density) and cannot be
avoided by construction — it depends on what Phase 1 finds, not on this skill's inputs:

| Signal density | incident-rca's own default | This skill's scripted answer |
|---|---|---|
| **≥1 strong signal** (error rate spike, top messages, OOM) | *"Announce counts + top finding; proceed unless user says stop"* — **proceeds by default** | **"Stop here."** Overrides incident-rca's own default — this skill wants the Phase 1 signal, not a continued investigation, regardless of how strong |
| **Sparse** (1 weak signal, partial coverage) | Explicitly asks | **"Stop here."** |
| **None** (both arrays empty) | Already stops by default | **Accept the partial report; do not widen the window.** No override needed — documented for completeness |

**Every density answer is "stop here"** — deliberate and uniform, not signal-dependent.

**Known limitation, not a bug — disclosed:** Phase 1 is scoped to symptom *detection* only
([phase-1.md](../../incident-rca/workflow/phase-1.md)); correlating a signal to a release-relevant cause
is Phase 2's job, which this skill deliberately never reaches. A flagged service may therefore be
flagging baseline/chronic noise unrelated to this release, not something the release itself caused.
`report-format.md`'s "Flagged" state is a **release readiness signal worth a human look**, not a
confirmed release-caused problem — the report's follow-up pointer ("run incident-rca directly...") exists
specifically so a human can make that correlation call, which this skill does not attempt.

Per incident-rca's own **Partial report path (user says stop)**
([workflow/phase-5.md](../../incident-rca/workflow/phase-5.md)): a partial RCA rendered from completed
phases only (Phase 1 here), header marked "Partial RCA — investigation stopped early." This skill reads
that partial report's Phase 1 evidence (error/infra signal counts) as the service's incident-readiness
signal — it does not re-render the partial RCA itself into the release report, only the counts and a
follow-up pointer.

## Escalation, not override

If any of the three wrapped skills reaches a state this policy doesn't cover, treat it as genuine — this
skill never bypasses a wrapped skill's own judgment. Record the anomaly in the report's relevant row and
fall back to flagging that MR/service as needing direct follow-up with the wrapped skill, same as any
other flagged item.
