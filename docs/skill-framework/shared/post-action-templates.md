# Post-action templates (shared)

**Normative.** Jira, Slack, and canvas output patterns after a skill completes.

**Consumers:** pr-review `workflow/phase-5.md`, incident-rca `workflow/phase-5.md`, k8s `workflow/report.md`, domain-comprehension `workflow/phase-5.md`, squad-map `workflow/phase-1.md`, mysql-to-postgres-sql `workflow/migrate-service.md`.

## 1. Jira — RCA complete (incident-rca)

```markdown
h3. RCA Summary — {{service}} {{window}}

*Primary hypothesis:* {{hypothesis}} ({{confidence}})
*Evidence gaps:* {{gaps_or_none}}

h4. Timeline
{{bullet_timeline}}

h4. Recommendations
{{numbered_actions}}

h4. Follow-up
{{jira_tickets_or_monitoring}}
```

## 2. Jira — PR review verdict (pr-review)

```markdown
h3. MR Review — {{project}} !{{iid}}

*Recommendation:* {{approve|comment|request_changes}}
*Risk:* {{low|medium|high}}
*Blocking:* {{none_or_list}}

{{executive_summary_2_sentences}}

[Full review in GitLab|{{mr_url}}]
```

## 3. Jira — k8s rightsizing (k8s)

```markdown
h3. Rightsizing — {{deployment}}/{{env}}

*Assessment confidence:* {{band}}
*Recommendations:* {{ready_count}} ready, {{hold_count}} hold

{{executive_decision_paragraph}}

_Details in attached Human Report._
```

## 3b. Jira — domain comprehension complete (domain-comprehension)

```markdown
h3. Domain Comprehension — {{domain}} ({{delivery_mode}})

*Overall confidence:* {{band}}
*Repos analyzed:* {{repo_count}} / {{total_repos}}
*Bounded contexts:* {{context_count}}

h4. Five Questions (summary)
{{q1_through_q5_one_line_each}}

h4. Top Architecture Smells
{{top_3_smells}}

h4. Unknowns
{{unknown_count}} open questions — see UNKNOWNS.md

_Full deliverables at {{workspace_root}}/{{deliverable_dir}}_
```

## 3c. Jira — squad map complete (squad-map)

```markdown
h3. Squad Map — {{workspace}}

*Repos mapped:* {{mapped_count}} / {{total_repos}}
*Conflicts:* {{conflict_count}}
*Confidence:* HIGH {{high_count}} · MEDIUM {{medium_count}} · LOW {{low_count}}

h4. Conflicts (GitLab ≠ Datadog)
{{conflict_rows_or_none}}

_Full map: SQUAD_MAP.md at workspace root_
```

## 3d. Jira — MySQL→PG migration gate (mysql-to-postgres-sql)

```markdown
h3. PG Migration — {{service}}

*Risk tier:* {{P0|P1|P2|dialect-only}} *(priority — not confidence)*
*Scan gate:* {{pass|fail}}
*Shadow compare:* {{pass|pending|n/a}}
*Confidence:* {{band}} *(verification quality only)*

h4. Files rewritten
{{file_count}} native SQL files — see SERVICE_PG_MIGRATION.md

h4. Next
{{mr_url_or_pr_review_handoff}}
```

### Jira ticket update fields

| Field | incident-rca | pr-review | k8s | domain-comprehension | squad-map | mysql-to-postgres-sql |
|-------|--------------|-----------|-----|----------------------|-----------|----------------------|
| Labels | `rca-complete` | `mr-reviewed` | `rightsizing-ready` | `domain-mapped` | `squad-mapped` | `pg-migration` |
| Priority | unchanged unless P1 outage | per blocking count | per REC severity | unchanged | unchanged | per P0 compliance tier |
| Comment | §1 template | §2 template | §3 template | §3b template | §3c template | §3d template |
| Attachment | optional evidence JSON export | link to GitLab MR | Human Report paste or export | `EXEC_SUMMARY.md` paste or link to deliverables | `SQUAD_MAP.md` paste | `SERVICE_PG_MIGRATION.md` |

## 4. Slack — incident channel brief

One-line summary for incident channel; full report in thread.

```markdown
:mag: *RCA complete* — `{{service}}` ({{window}})
• Hypothesis: {{hypothesis}} ({{confidence}})
• Gaps: {{gaps_short}}
• Next: {{top_action}}
Full report in thread ↓
```

## 5. Slack — PR review 🔴

```markdown
:gitlab: *Review* `{{project}}` !{{iid}} — :red_circle: *Request changes*
• {{blocking_count}} blocking ({{top_theme}})
• {{mr_url}}
```

Approve/comment variants: replace emoji and headline; keep blocking count line when applicable.

## 6. Canvas hints

| Skill | Canvas when | Invocation hint |
|-------|-------------|-----------------|
| incident-rca | Multi-service timeline, hypothesis score comparison | Open canvas after Phase 5 when ≥3 services correlated |
| k8s | Cost/waste table, decision graph summary | Open canvas for namespace ranking or REC comparison table |
| pr-review | Finding severity distribution, dimension scores | Open canvas when findings table exceeds ~15 rows |
| domain-comprehension | Multi-repo dependency graph, bounded context map, data ownership matrix | Open canvas for DEPENDENCY_GRAPH views or cross-repo flow diagrams |

See [cross-skill-escalation.md §5](cross-skill-escalation.md#5-canvas-hint) and [canvas skill](~/.cursor/skills-cursor/canvas/SKILL.md).

## 7. Confirmation gates

| Skill | Gate | Behavior |
|-------|------|----------|
| **pr-review** | Phase 3 confirmation | User MUST confirm before Jira post or GitLab comment (except explicit `chat-only` skip note) |
| **incident-rca** | Read-only | Offer Jira/Slack paste blocks; **never** auto-post without explicit user request |
| **k8s** | Read-only | Offer Jira paste + canvas hint; **never** auto-post or apply changes without explicit user request |
| **domain-comprehension** | Read-only on application source | Writes only markdown deliverables + config; **never** run builds, tests, deploys, or mutate application source/infra. Offer Jira paste on completion. |
| **squad-map** | Read-only | Writes only `SQUAD_MAP.md`; offer Jira paste on completion. |
| **mysql-to-postgres-sql** | Read-only on application source | Rewrites SQL/config in user-approved paths only; scan gate before merge; offer pr-review handoff. |

Agents MUST NOT invoke Jira write tools, Slack post APIs, or GitLab comment tools unless the user explicitly confirms in the current turn.
