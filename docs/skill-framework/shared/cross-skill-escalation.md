# Cross-skill escalation (shared)

**Normative.** Symmetric escalation matrix for pr-review, incident-rca, k8s-overprovisioning-datadog, domain-comprehension, squad-map, mysql-to-postgres-sql, and loop-task-implementer.

**Consumers:** `SKILL.md` in each skill (link here; keep ≤10 skill-specific rows max).

## 1. Symmetric matrix (forward escalations)

| Trigger | From → To | Handoff artifact | User prompt template |
|---------|-----------|------------------|----------------------|
| Critical security / bad deploy in prod | pr-review → incident-rca | Incident window + MR link + service | "RCA for `{service}` {window} — deploy regression from MR !{iid}" |
| K8s/infra perf regression in MR | pr-review → k8s | Deployment + env + resource diff | "Assess rightsizing for `{deployment}` in `{env}` — MR !{iid} reduced resources" |
| Resource-down MR merged + outage | pr-review → k8s + incident-rca | MR + post-merge window | "RCA `{service}` {window}; then k8s assessment for `{deployment}`" |
| Deploy regression confirmed | incident-rca → pr-review | Causative MR URL/IID + window | "Review MR !{iid} for deploy regression tied to `{service}` outage {window}" |
| Infra capacity (OOM/throttle/crashloop) | incident-rca → k8s | [report-template.md#k8s-skill-handoff](../../../incident-rca/report-template.md#k8s-skill-handoff-infra-capacity-confirmed) block | "Assess rightsizing for `{service}` in `{env}` — OOMKilled during {window}" |
| Kafka consumer lag | incident-rca → k8s | Service + consumer group + lag metrics | "Assess `{deployment}` replicas vs partitions — consumer lag spike {window}" |
| OOM / crashloop on assessed deployment | k8s → incident-rca | Time window + OBS evidence | "RCA for `{service}` {window} — OOMKilled pods on `{deployment}`" |
| Manifest drift + active incident | k8s → incident-rca | Drift summary + deploy timeline | "RCA `{service}` {window} — manifest drift detected during assessment" |
| Spike + recent deploy | k8s → pr-review | Suspect MR from deploy event | "Review MR !{iid} — deploy preceded utilization spike on `{deployment}`" |
| Squad ownership only (no domain map) | domain-comprehension → squad-map | In-scope repo census + `domain-config.yaml` ownership | "Map squads for repos in `{workspace}` — org prefix `{org}`, segment `{n}`" |
| Full domain map after squad map | squad-map → domain-comprehension | `SQUAD_MAP.md` + workspace root | "Map bounded contexts and data ownership for `{domain}` — full domain comprehension" |
| Incident + unclear service owner | incident-rca → squad-map | Service name + window | "Who owns `{service}`? — need squad for RCA follow-up" |
| Security finding in domain analysis (P3b) | domain-comprehension → pr-review | Repo + file path + finding type | "Review MR !{iid} for credential exposure in `{service}`" |
| Architecture smell needs RCA context | domain-comprehension → incident-rca | Service + smell + time window | "RCA for `{service}` {window} — recurring {smell} identified in domain analysis" |
| Domain map reveals overprovisioned service | domain-comprehension → k8s | Service + env from runtime validation | "Assess rightsizing for `{service}` in `{env}` — domain analysis found low utilization" |
| Domain analysis produced `MYSQL_TO_PG_SQL_REWRITES.md` | domain-comprehension → mysql-to-postgres-sql | Comprehension artifact + repo list | "Implement PG rewrites for `{service}` per domain-comprehension artifact" |
| Migration MR needs review | mysql-to-postgres-sql → pr-review | Service path + MR !IID | "Review MR !{iid} for MySQL→PostgreSQL migration in `{service}`" |
| Cutover wrong results / outage | mysql-to-postgres-sql → incident-rca | Service + window + shadow diff | "RCA for `{service}` {window} — PG cutover query regression" |
| RCA recommends monitor/alert fix | incident-rca → kubesense-alerts | Monitor query + threshold from RCA | "Create or update alert for `{query}` — RCA `{service}` {window}" |
| RCA needs dashboard for verification | incident-rca → kubesense-dashboards | Metric panels from RCA evidence | "Dashboard for `{service}` post-incident / soak verification" |
| Builder needs an MR reviewed beyond its own lenses | loop-task-implementer → pr-review | MR !IID + task ID | "Review MR !{iid} for task `{task_id}`" |
| Task implementation causes or needs incident investigation | loop-task-implementer → incident-rca | Service + window + task ref | "RCA for `{service}` {window} — regression from task `{task_id}`" |
| Task requires understanding an unfamiliar domain/codebase first | loop-task-implementer → domain-comprehension | Repo/workspace + task ref | "Map domain for `{workspace}` before implementing task `{task_id}`" |
| Task touches MySQL-dialect SQL during a PG migration | loop-task-implementer → mysql-to-postgres-sql | Service + repo | "Scan/rewrite MySQL dialect in `{service}` for task `{task_id}`" |

Skill-specific rows in each `SKILL.md` MUST be a subset of this table plus local deltas only.

## 2. Reverse escalations

| After skill completes | Next action | User prompt template |
|-----------------------|-------------|----------------------|
| k8s recommends Ready cut applied | Re-run k8s in **7d** (PostChangeVerification) | "Re-run rightsizing assessment for `{deployment}` `{env}` — 7d post-change verification" |
| incident-rca ranks `deploy_regression` HIGH | pr-review on identified MR | "Review MR !{iid} for deploy regression tied to `{service}` outage {window}" |
| pr-review flags underprovisioned resources | k8s assessment before merge | "Assess rightsizing for `{deployment}` in `{env}` before merging MR !{iid}" |
| pr-review finds critical security in deployed code | incident-rca on incident window (if outage) | "RCA for `{service}` {window} — security finding PRR-{id} in MR !{iid}" |
| incident-rca finds `configuration_change` + code MR | pr-review on code MR if not yet reviewed | "Review MR !{iid} — config spike + code change in `{service}` window" |
| k8s assessment during active incident | incident-rca if not already run | "RCA for `{service}` {window} — correlate with k8s OBS findings" |
| domain-comprehension P3b flags security issue | pr-review on affected MR/repo | "Review MR !{iid} for `{finding_type}` in `{service}` — flagged during domain analysis" |
| domain-comprehension completes P5 | squad-map refresh if ownership changed | "Refresh squad map — domain comprehension found new services in `{workspace}`" |
| PG cutover regression confirmed in RCA | mysql-to-postgres-sql audit on failing query | "Audit native SQL in `{service}` for PG semantic mismatch — RCA found query regression" |
| Migration rewrites complete | pr-review on migration MR | "Review MR !{iid} for MySQL→PostgreSQL migration in `{service}`" |
| pr-review approves a loop-task-implementer task MR | loop-task-implementer resumes and selects the next task | "Continue loop-task-implementer — MR !{iid} merged, select next task" |
| incident-rca confirms a regression tied to a task branch | loop-task-implementer dispatches Builder remediation | "Dispatch Builder remediation for task `{task_id}` — RCA confirmed regression {window}" |

## 3. Handoff block (required fields)

Paste into chat from `report-template.md` anchors or generate inline:

```markdown
**Handoff → <skill>**
- Service: `<name>`
- Env: `<env>`
- Window: `<from>` – `<to>` (UTC)
- Trigger: `<hypothesis or finding>`
- Evidence: <links, MR !IID, metric queries>
- Ask: "<one-line user prompt>"
```

Confidence at handoff: use categorical band from [confidence-bands.md](confidence-bands.md); receiving skill recomputes per its own rules.

### domain-comprehension → mysql-to-postgres-sql (artifact)

When `MYSQL_TO_PG_SQL_REWRITES.md` exists in the workspace deliverable directory:

```markdown
**Handoff → mysql-to-postgres-sql**
- Artifact: `<workspace>/<deliverable_dir>/MYSQL_TO_PG_SQL_REWRITES.md`
- Service: `<primary service from artifact header>`
- Repos: `<paths listed in artifact>`
- Risk tier focus: P0 / P1 (from artifact tables)
- Ask: "Implement PG rewrites for `{service}` per domain-comprehension MYSQL_TO_PG_SQL_REWRITES.md"
```

## 4. When NOT to escalate

| User request | Correct skill |
|--------------|---------------|
| Size K8s deployment / rightsizing | k8s-overprovisioning-datadog |
| Review GitLab MR | pr-review |
| Post-incident RCA / root cause | incident-rca |
| Squad / repo ownership mapping | squad-map |
| Domain / subsystem map, bounded contexts, data ownership | domain-comprehension |
| MySQL scrub / native SQL PG migration / jdbc:postgresql cutover | mysql-to-postgres-sql |
| Autonomous multi-task implement → review → remediate → PR loop | loop-task-implementer |
| Live rollback / kubectl apply | Out of scope — human operator |
| Security-only deep review | pr-review with security persona |
| Cost/billing investigation across services | Canvas + appropriate skill; not auto-routed |

See each skill's **when NOT to use** table in `SKILL.md`.

## 5. Canvas hint

Use [canvas skill](~/.cursor/skills-cursor/canvas/SKILL.md) when the deliverable is multi-tabular, timeline-heavy, or benefits from interactive layout. Chat markdown suffices for single MR summary or short RCA.

| Skill | Canvas when | Chat suffices when |
|-------|-------------|---------------------|
| incident-rca | Multi-service timeline, hypothesis score comparison, correlation across 3+ services | Single-service RCA with ≤2 hypotheses |
| k8s | Cost/waste table, decision graph summary, namespace ranking across deployments | Single deployment Human Report |
| pr-review | Finding severity distribution, dimension scores heatmap, large MR finding map | Single MR executive summary |
| domain-comprehension | Multi-repo dependency graph, bounded context map, data ownership matrix | Single-repo orientation or quick five-questions summary |
| squad-map | Multi-repo ownership table, conflict matrix across squads | Single-repo ownership lookup |
| mysql-to-postgres-sql | Multi-service migration status table, scan hit matrix across repos | Single-service scan + rewrite summary |

Trigger phrases: "show in canvas", billing/timeline investigations, or when user has canvas open beside chat.
