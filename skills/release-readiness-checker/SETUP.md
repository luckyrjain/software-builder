# release-readiness-checker — Setup


## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-08-09 |
| **Review cadence** | Quarterly — or when pinned MCP package versions change |
| **External services** | GitLab MCP, Kubernetes MCP, Datadog MCP (via composed skills); optional SCM history/policy and build-provenance host evidence for v2 conditional production-readiness invocation |

See [setup-freshness.md](../docs/skill-framework/shared/setup-freshness.md) for the shared contract.
## Ambient discovery is intended

This skill deliberately does **not** set `disable-model-invocation` — the agent can auto-apply it when
you ask "is this release ready to ship?" with a `release_manifest`, as well as an explicit invocation.
Unlike `who-owns-x-bot`/`pr-gatekeeper`/`incident-triage-agent`/`backlog-runner`, a human is present for
this flow; see [SKILL.md](SKILL.md) § "Why a gate policy, despite being human-invoked" for why it still
needs one — the fan-out over potentially many MRs/services means every one of pr-review's, k8s's, and
incident-rca's own real gates needs a scripted or constructed-away answer; see
[reference/gate-policy.md](reference/gate-policy.md) for the full, corrected enumeration (an earlier
draft of this skill wrongly assumed pr-review had a settable "quiet" posting mode with no gate at all —
it doesn't; see that file's own correction note).

## Install

```bash
cd software-builder
make install-release-readiness-checker
```

This chains `make install-pr-review install-k8s-overprovisioning install-incident-rca` first — this
skill has no review/rightsizing/incident-investigation logic of its own and is useless without all three
installed alongside it. Restart Cursor so all four skills reload.

### Claude Code

`make install-release-readiness-checker` above already installs this skill for Claude Code too (default
installs to both editors). For Claude Code **only**:

```bash
cd software-builder
make install-claude-release-readiness-checker
```

No restart needed — a new Claude Code session picks it up. See
[claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).

### Kiro / in-repo discovery

Working directly in this repo? `.cursor/rules/release-readiness-checker.mdc` and
`.kiro/steering/release-readiness-checker.md` point Cursor/Kiro at
`release-readiness-checker/SKILL.md` without an install step.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| pr-review installed and configured | GitLab MCP with `list_merge_requests` support — see [pr-review/SETUP.md](../pr-review/SETUP.md) |
| k8s-overprovisioning-datadog installed and configured | At least one sufficient rightsizing evidence source: Kubernetes MCP or Datadog — see [k8s-overprovisioning-datadog/SETUP.md](../k8s-overprovisioning-datadog/SETUP.md) |
| incident-rca installed and configured | ≥1 observability MCP (Datadog or KubeSense) — see [incident-rca/SETUP.md](../incident-rca/SETUP.md) |

No MCP of its own — every MCP requirement is inherited from the three wrapped skills.

## Config

No config file of its own. `release_manifest` is passed at invocation time. `target_branch` defaults to
whatever the caller's own GitLab project convention is for a release branch — if your team has a fixed
convention (e.g. always `release`, or a per-repo branch name), document it in your own runbook and pass
it explicitly per invocation; this skill has no per-repo default table of its own.

**GitLab MCP merge-date filter support:** the MR-range resolver (`workflow/run-check.md` § 1) queries
`list_merge_requests` with a merge-date filter — a query shape pr-review's own docs never exercise. If
your connected GitLab MCP server's `list_merge_requests` doesn't support a merge-date parameter, the
resolver falls back to client-side filtering (list all merged MRs against `target_branch`, filter by
`merged_at` locally) — verify this fallback works against your specific server during the smoke test, it
hasn't been exercised against every GitLab MCP implementation. **Both paths must paginate exhaustively**
(same requirement pr-review's own open-MR listing places on itself) — a repo with more merged MRs than
one page holds must not silently return only the first page.

## Framework links

- [skill-framework README](../docs/skill-framework/README.md)
- [confidence-bands](../docs/skill-framework/shared/confidence-bands.md)
- [cross-skill-escalation](../docs/skill-framework/shared/cross-skill-escalation.md)

## Smoke test

After install, run the invocation in [reference/smoke-test.md](reference/smoke-test.md) against a
`release_manifest` with at least one repo with a merged MR and one service with a recent observability
signal available through the configured incident-rca source.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| MR range looks wrong / includes MRs from before `since`, or is missing MRs from a large repo | Check the GitLab MCP merge-date filter fallback engaged correctly, and that pagination actually ran to completion (not just page 1) — see § Config above |
| A service never gets flagged even with a known recent incident | Check `incident_lookback_hours` covers the incident's actual time; verify incident-rca's Phase 1 checkpoint is really being answered "stop here," not silently continuing (inspect the invocation, not just the summary) |
| pr-review posts to GitLab | Bug — verify `workflow/run-check.md` § 2 is invoking pr-review with the plain "review !`<iid>` in `<project>`" phrase (never "review and post") and that its Phase 3 confirmation, whenever it fires, is answered "Hold — don't post" per [reference/gate-policy.md](reference/gate-policy.md) — pr-review has no settable "quiet" input to depend on instead |
| A repo/service silently missing from the report | Should never happen — every `release_manifest` entry gets a row per [reference/report-format.md](reference/report-format.md), including unresolved-`since` and `insufficient_metrics` cases; file a bug if one is missing |
