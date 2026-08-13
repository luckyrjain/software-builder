# Compatibility matrix

<!-- GENERATED from skills.yaml + capability_catalog.yaml + composition_contracts.yaml — do not edit; run make generate -->

Distribution version: **1.4.0**

| Skill | Invocation | Cursor | Claude | Kiro | Required capabilities | Write authority |
|-------|------------|--------|--------|------|----------------------|-----------------|
| `api-test-creator` | ambient | rule | yes | manual | host.repository.read_write | repository-write |
| `backlog-runner` | automation-only | rule | yes | manual | scheduler.cron.trigger, host.issue_tracker.read | read-only |
| `contract-test-creator` | ambient | rule | yes | manual | host.repository.read_write | repository-write |
| `cost-optimization-sprint-planner` | ambient | rule | yes | manual | host.filesystem.read | read-only |
| `domain-comprehension` | ambient | rule | yes | manual | host.repository.read | read-only |
| `e2e-test-creator` | ambient | rule | yes | manual | host.repository.read_write | repository-write |
| `incident-rca` | ambient | rule | yes | manual | telemetry.logs.query | read-only |
| `incident-triage-agent` | automation-only | rule | yes | manual | pager.webhook.receive | read-only |
| `integration-test-creator` | ambient | rule | yes | manual | host.repository.read_write | repository-write |
| `k8s-overprovisioning-datadog` | ambient | rule | yes | manual | Kubernetes history-capable evidence: kubernetes.metrics.history OR Datadog historical evidence: datadog.query_metrics | read-only |
| `loop-task-implementer` | ambient | rule | yes | manual | host.repository.read_write, host.role.isolation, host.ci.status, host.pull_request.write | repository-write |
| `migration-program-manager` | ambient | rule | yes | manual | host.filesystem.read | read-only |
| `mysql-to-postgres-sql` | ambient | rule | yes | manual | host.repository.read_write | repository-write |
| `new-hire-guide` | ambient | rule | yes | manual | host.repository.read | read-only |
| `pr-gatekeeper` | automation-only | rule | yes | manual | gitlab.get_merge_request | comment |
| `pr-review` | ambient | rule | yes | manual | GitLab read: gitlab.get_merge_request + gitlab.get_merge_request_diffs OR GitHub read: github.get_pull_request + github.get_pull_request_files | comment |
| `prd-architect` | ambient | rule | yes | manual | host.report.write | read-only |
| `release-readiness-checker` | ambient | rule | yes | manual | host.report.write | read-only |
| `squad-map` | ambient | rule | yes | manual | gitlab.list_projects | read-only |
| `test-writer` | ambient | rule | yes | manual | host.repository.read | read-only |
| `unit-test-creator` | ambient | rule | yes | manual | host.repository.read_write | repository-write |
| `weekly-squad-digest` | automation-only | rule | yes | manual | scheduler.cron.trigger | read-only |
| `who-owns-x-bot` | automation-only | rule | yes | manual | slack.slash_command.receive | read-only |
