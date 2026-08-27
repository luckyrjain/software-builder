# production-readiness-review — Setup

## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-08-27 |
| **Review cadence** | Quarterly — or when a composed child skill's own input contract changes |
| **External services** | Whatever each composed skill needs (SCM/CI/build-provenance/observability hosts), plus this skill's own `host.*` read capabilities |

See [setup-freshness.md](../docs/skill-framework/shared/setup-freshness.md) for the shared contract.

## Ambient discovery is intended

This skill deliberately does not set `disable-model-invocation` — the agent can auto-apply it when you
ask "is this PR/MR/release-candidate production ready?" with an `assessment_target`, as well as an
explicit invocation. It fans out over up to ten child skills to produce **one** aggregated verdict, so
every one of those children's own live gates needs a scripted or constructed-away answer — see
[reference/gate-policy.md](reference/gate-policy.md).

## Install

```bash
cd software-builder
make install-production-readiness-review
```

This chains the install targets for `pr-review`, `change-impact-analyzer`, `deployment-risk-review`,
`security-review`, `observability-review`, `resilience-review`, `api-design-review`,
`database-review`, `performance-review`, `capacity-planner`, and `dependency-upgrade-review` first —
this skill has no code-review, impact, risk, or specialist-analysis logic of its own and is useless
without them installed alongside it. Restart Cursor so all twelve skills reload.

### Claude Code

`make install-production-readiness-review` above already installs this skill for Claude Code too
(default installs to both editors). For Claude Code **only**:

```bash
cd software-builder
make install-claude-production-readiness-review
```

No restart needed — a new Claude Code session picks it up. See the shared
[skill-framework](../docs/skill-framework/README.md) conventions and
[claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).

### Kiro / in-repo discovery

Working directly in this repo? `.cursor/rules/production-readiness-review.mdc` and
`.kiro/steering/production-readiness-review.md` point Cursor/Kiro at
`production-readiness-review/SKILL.md` without an install step.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| `host.report.write` | Required — emitting `production_readiness_report` |
| `pr-review` installed and configured | Always invoked, retrospective mode, posting forbidden — see [pr-review/SETUP.md](../pr-review/SETUP.md) |
| `change-impact-analyzer` and `deployment-risk-review` installed | Refreshed or reused as dispatch prerequisites — see each skill's own `SETUP.md` |
| The eight specialist skills installed | Dispatched only when the change-impact evidence says they apply — see each skill's own `SETUP.md` |
| `host.repository.read`, `host.scm.change.read`, `host.scm.change_history.read` | Candidate diff/config, exact-head PR/MR metadata, and material-change enumeration — see [reference/evidence-authority-policy.md](reference/evidence-authority-policy.md) |
| `host.ci.status`, `host.scm.policy.read` | Authoritative CI and approvals/CODEOWNERS/branch-rule evidence |
| `host.build.provenance.read` | Source-revision → deployable-digest linkage; `build_provenance_ref` is `NOT_APPLICABLE` when there's no separate build step |
| `host.service.metadata.read` | Criticality/ownership/on-call/recovery-policy evidence for [reference/operational-gates.md](reference/operational-gates.md) |
| `host.dependency.advisories.read` | Current advisory evidence for changed dependencies at the exact source revision |

Every capability above is optional individually — a missing one degrades its own dimension(s) to
`UNKNOWN`, never to a fabricated `PASS`. No capability failure blocks the whole run.

## Config

No config file of its own. `assessment_target` and `criticality` are passed at invocation time — this
skill has no per-repo default table. `build_provenance_ref` defaults to `NOT_APPLICABLE`; only set it
when the deployable artifact differs from the reviewed source revision.

## Framework links

- [skill-framework README](../docs/skill-framework/README.md)
- [confidence-bands](../docs/skill-framework/shared/confidence-bands.md)
- [cross-skill-escalation](../docs/skill-framework/shared/cross-skill-escalation.md)

## Smoke test

After install, run the invocation in [reference/smoke-test.md](reference/smoke-test.md) against a real
PR/MR with at least one CI check, at least one approval/policy signal, and a change shape that triggers
at least one specialist dispatch (e.g. a schema migration or a public API change).

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| A dimension is `UNKNOWN` even though the specialist skill is installed | Check the mandatory-input map in [reference/child-input-map.md](reference/child-input-map.md) — a knowingly-incomplete mandatory input is never dispatched, it's recorded `UNKNOWN` by design |
| pr-review posts to the PR/MR | Bug — verify `workflow/dispatch.md` invokes pr-review with `posting_policy: forbidden` and that any Phase 3 confirmation it still renders is answered "Hold — don't post" per [reference/gate-policy.md](reference/gate-policy.md) |
| Verdict is `READY` but a specialist never actually ran | Should never happen — a dimension the evidence says applies but that wasn't dispatched is `UNKNOWN`, not silently excluded from the verdict; file a bug |
| Operational-gate finding looks too lenient for a critical service | Check `criticality` resolved correctly — `tier0`/`tier1`/`unknown` require authoritative (not caller-only) evidence to `PASS`; see [reference/operational-gates.md](reference/operational-gates.md) |
| A child skill returns an interactive question mid-run | Expected to surface as `BLOCKED` to this skill, never as a live prompt mid-aggregation — see [reference/gate-policy.md](reference/gate-policy.md) |
