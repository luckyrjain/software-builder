---
workflow_version: 1.1
phase: "2"
produces: {deploy_events: list}
consumes:
  required: {mcp_profile: string}
  optional: {from_time: string, to_time: string, service: string, environment: string}
  conditional: {}
---

# Phase 2 — Change correlation (deploys)

**Read this file** at the start of Phase 2.

There is **no GitLab `list_deployments`** in this toolset — build the deploy timeline in
`[from_time − 30min, to_time]` from these sources, in order of preference:

1. **Datadog `get_change_stories`** (preferred) — change events for the APM service: `deployment`,
   `kubernetes`, `scale`, `feature_flag`, `crashloopbackoff`. Pass `service_name`, `start_ts`,
   `end_ts`, `env`, and `telemetry.intent`. **Feature flag events** are separate from deploy events — record them in `deploy_events` with `event_type: "feature_flag"` and treat them as candidates for the `feature_flag_regression` hypothesis.
2. **Jenkins** — `findJobsWithScmUrl` (repo → prod job) → `getBuild` (timestamp in window) →
   `getBuildScm` (SHA) → `getBuildChangeSets` (change summary).
3. **GitLab fallback** — `list_merge_requests` with `state: merged`, `updated_after`/`updated_before`
   in the window; match a deploy SHA to an MR via `get_commit` (merge / source / squash commit). Use
   `get_commit_diff` on the top suspect for a blast-radius note.

Collect into `deploy_events`. See [query-playbook.md](../reference/query-playbook.md#gitlab) for field
mapping.

## Canary / blue-green deploy detection

Full deploys show error spikes across **all** pods/instances shortly after rollout. **Canary** or
**blue-green** partial rollouts show a different pattern:

| Pattern | Indicators | Hypothesis impact |
|---------|------------|-------------------|
| **Full deploy** | Error spike correlates with 100% rollout; all replicas on new version | Standard `deploy_regression` |
| **Canary / partial** | Errors on **subset** of pods/instances; error rate ∝ canary traffic %; old version healthy | Still `deploy_regression` but note *partial rollout* — blast radius limited to canary slice |
| **Blue-green switch** | Step change at traffic flip; errors spike only after cutover timestamp | Check change story for traffic switch, not just image push |

Investigation steps:

1. Compare error counts **by host/pod/version tag** if available (`analyze_datadog_logs` GROUP BY
   `version`, `kube_pod_name`, or `host`).
2. Check `get_change_stories` for canary/rollout events (progressive delivery, Argo Rollouts, Flagger).
3. When errors affect < 50% of instances, state *"Partial rollout pattern — likely canary/blue-green;
   not a full-fleet deploy regression."*
4. Recommend validating canary metrics before full promotion — do not assume fleet-wide bad deploy.

## Phase 2 checkpoint (before Phase 3)

**Exit:** [phase-exit-criteria.md](../reference/phase-exit-criteria.md) §Phase 2 before Phase 3.

Summarize the deploy/change timeline in chat. Present options based on signal density:

| Signal state | Options to offer |
|---|---|
| **Strong deploy + error overlap confirmed** | A) Continue to Phase 3 (Jira / recurrence) → Phase 4 · B) Skip Phase 3, go straight to Phase 4 · C) Stop — partial report |
| **No deploy events; Phase 1 sparse** | A) Continue to Phase 3 · B) Stop — partial report |
| **Strong `deploy_regression` evidence** | Suggest skipping Phase 3 proactively: *"Strong deploy signal found. Skip Jira lookup and proceed directly to Phase 4?"* |

User says *"stop"* → Phase 5 partial report. User says *"skip Jira"* / *"skip Phase 3"* → jump directly to Phase 4; note *"Phase 3 skipped by user"* in Gaps.
