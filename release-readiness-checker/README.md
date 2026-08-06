# release-readiness-checker

**Release go/no-go report** composing three existing skills over a `release_manifest`: **pr-review**
(every MR merged since each repo's last release marker — never posts to GitLab, by reusing
**pr-gatekeeper's own real posting-gate policy**, not an invented "quiet mode"),
**k8s-overprovisioning-datadog** (each touched service's own rightsizing verdict), and **incident-rca**
(each touched service's open-incident signal, Phase 1 evidence only — never a full RCA). No new
Builder/Reviewer/analysis logic of its own; the only new pieces are the MR-range resolver, the fan-out,
and the aggregated report.

## Why a gate policy, despite being human-invoked

A release manager is present when this runs — but the fan-out over potentially many MRs and services
means pausing for a live confirmation inside every one of those invocations would turn one report into N
interruptions. All three wrapped skills have real gates somewhere: pr-review's posting confirmation
(pr-review has **no caller-settable quiet mode** — its posting mode is derived entirely by its own Phase
0 from which GitLab MCP write tools are connected; this skill reuses pr-gatekeeper's own real,
already-solved policy instead), k8s's ambiguous-service-name ask (answered with k8s's own documented
"proceed with unknown" fallback), and incident-rca's Phase 1 checkpoint (always answered "stop here") —
see [reference/gate-policy.md](reference/gate-policy.md).

## What it does

1. **Resolves each repo's MR range** — merges since a tag/ref or timestamp, against the release branch,
   paginated exhaustively. Genuinely new: pr-review's own docs only ever enumerate *open* MRs, never a
   merged-in-a-date-range query.
2. **Reviews every resolved MR via pr-review**, always with the plain "review !`<iid>` in `<project>`"
   phrase (never "review and post"), answering every pr-review ask-point per pr-gatekeeper's own real
   policy — never posts to GitLab regardless of which posting mode pr-review's Phase 0 detects.
3. **Gets each service's own k8s rightsizing verdict** — surfaced as-is, including an honest
   `insufficient_metrics` when k8s can't resolve the service — no new risk taxonomy invented.
4. **Checks each service for an incident signal** — incident-rca, Phase 1 only, always stopped at the
   checkpoint per [reference/gate-policy.md](reference/gate-policy.md) (overriding incident-rca's own
   default-to-proceed on a strong signal).
5. **Writes `RELEASE_READINESS_REPORT.md`** — overall verdict + three sections, every manifest entry
   present, reporting `UNKNOWN` on anything unverified (an unresolved MR range, an
   `insufficient_metrics` service) rather than silently assuming clean **or** conflating an evidence
   gap with a proven `NOT_READY` blocker.

## When to use

| Use release-readiness-checker | Use instead |
|---------------------------------|--------------|
| "Is this release ready to ship?" with a `release_manifest` | Reviewing one specific MR → **pr-review** directly |
| Pre-release go/no-go across several repos/services | One service's rightsizing question → **k8s-overprovisioning-datadog** directly |
| — | Full root-cause investigation → **incident-rca** directly |

## Invocation example

```
release_manifest: [{repo: api-disbursement, service: disbursement-service, since: v2.3.0}]
```

## What you get

`RELEASE_READINESS_REPORT.md` — format spec: [reference/report-format.md](reference/report-format.md).
Overall verdict (READY / CONDITIONAL / NOT_READY / UNKNOWN), MRs reviewed (severity summary), per-service rightsizing (k8s's own
verdict, unmodified), per-service incident signal (clear / flagged with a direct incident-rca follow-up
pointer).

## Install

```bash
cd software-builder
make install-release-readiness-checker
```

Restart Cursor. Requires **pr-review**, **k8s-overprovisioning-datadog**, and **incident-rca** installed
too (the make target chains all three automatically). MCP setup is each wrapped skill's own — see
[pr-review/SETUP.md](../pr-review/SETUP.md), [k8s-overprovisioning-datadog/SETUP.md](../k8s-overprovisioning-datadog/SETUP.md),
[incident-rca/SETUP.md](../incident-rca/SETUP.md).

## Related skills

- **pr-review** — does the actual MR review; this skill only resolves which MRs and answers its gates per pr-gatekeeper's own policy, always declining to post
- **k8s-overprovisioning-datadog** — does the actual rightsizing analysis; this skill only fans it out per service
- **incident-rca** — does the actual incident investigation; this skill only takes its Phase 1 signal
- **pr-gatekeeper** — a different pr-review wrapper, for unattended webhook-triggered auto-review, not a
  release-wide sweep

Agent instructions: [SKILL.md](SKILL.md).
