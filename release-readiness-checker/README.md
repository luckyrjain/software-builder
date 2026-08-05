# release-readiness-checker

**Release go/no-go report** composing three existing skills over a `release_manifest`: **pr-review**
(every MR merged since each repo's last release marker, `chat-only` — never posts to GitLab),
**k8s-overprovisioning-datadog** (each touched service's own rightsizing verdict), and **incident-rca**
(each touched service's open-incident signal, Phase 1 evidence only — never a full RCA). No new
Builder/Reviewer/analysis logic of its own; the only new pieces are the MR-range resolver, the fan-out,
and the aggregated report.

## Why a gate policy, despite being human-invoked

A release manager is present when this runs — but the fan-out over potentially many MRs and services
means pausing for a live confirmation inside every one of those invocations would turn one report into N
interruptions. pr-review's own `chat-only` mode has nothing to answer at all. incident-rca's Phase 1
checkpoint does, and this skill always answers it "stop here" — see [reference/gate-policy.md](reference/gate-policy.md).

## What it does

1. **Resolves each repo's MR range** — merges since a tag/ref or timestamp, against the release branch.
   Genuinely new: pr-review's own docs only ever enumerate *open* MRs, never a merged-in-a-date-range query.
2. **Reviews every resolved MR via pr-review, `chat-only`** — zero live gates, never posts.
3. **Gets each service's own k8s rightsizing verdict** — surfaced as-is, no new risk taxonomy invented.
4. **Checks each service for an incident signal** — incident-rca, Phase 1 only, always stopped at the
   checkpoint per [reference/gate-policy.md](reference/gate-policy.md) (overriding incident-rca's own
   default-to-proceed on a strong signal).
5. **Writes `RELEASE_READINESS_REPORT.md`** — overall verdict + three sections, every manifest entry
   present.

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
Overall verdict (Ready / Not ready), MRs reviewed (severity summary), per-service rightsizing (k8s's own
verdict, unmodified), per-service incident signal (clear / flagged with a direct incident-rca follow-up
pointer).

## Install

```bash
cd ai-skills
make install-release-readiness-checker
```

Restart Cursor. Requires **pr-review**, **k8s-overprovisioning-datadog**, and **incident-rca** installed
too (the make target chains all three automatically). MCP setup is each wrapped skill's own — see
[pr-review/SETUP.md](../pr-review/SETUP.md), [k8s-overprovisioning-datadog/SETUP.md](../k8s-overprovisioning-datadog/SETUP.md),
[incident-rca/SETUP.md](../incident-rca/SETUP.md).

## Related skills

- **pr-review** — does the actual MR review; this skill only resolves which MRs and runs them `chat-only`
- **k8s-overprovisioning-datadog** — does the actual rightsizing analysis; this skill only fans it out per service
- **incident-rca** — does the actual incident investigation; this skill only takes its Phase 1 signal
- **pr-gatekeeper** — a different pr-review wrapper, for unattended webhook-triggered auto-review, not a
  release-wide sweep

Agent instructions: [SKILL.md](SKILL.md).
