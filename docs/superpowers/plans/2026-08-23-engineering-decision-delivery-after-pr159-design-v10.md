Engineering Decision & Delivery Skills — Design Spec v10 After PR #159

Date: 2026-08-23
Repository: luckyrjain/software-builder
Reviewed baseline: main at PR #159 merge commit 319eb2200264f5b2a4cdf327686d98e5383387ef; PR #159 final head 5566ffe52dd4095f0de71c3a7c39d6418ad07ea4 passed Lint, Secret Scan, Dependency Review, and CodeQL
Execution baseline: before every follow-up PR, fetch fresh origin/main, record its exact SHA, verify 319eb2200264f5b2a4cdf327686d98e5383387ef is an ancestor, and revalidate any contract paths changed since this reviewed baseline
Status: Candidate for final top-tier certification; implementation follows eight small, reviewable companion plans
Supersedes: 2026-08-23-engineering-decision-delivery-after-pr159-design-v9.md

────────

1. Decision summary

PR #159 already adds the architecture/design/specialist review primitives needed for this initiative. Do not recreate them.

Reuse from PR #159

• architecture-review
• system-design
• api-design-review
• database-review
• security-review
• performance-review
• capacity-planner
• observability-review
• deployment-risk-review
• dependency-upgrade-review
• tech-debt-assessor

Add only four new skills

1. change-impact-analyzer
2. resilience-review
3. implementation-planner
4. production-readiness-review

Add three small foundation PRs before those skills

The foundation work fixes machine composition contracts and the incorrect default design lifecycle exposed by PR #159. It adds no new skill. It is split into A/B1/B2 because a combined foundation change would exceed the repository’s own review-size guard once producer workflows, tests, docs, and generated projections are included.

Delivery sequence

PR #159 is merged and is the reviewed baseline, not a pending delivery step. Follow-up work starts from fresh main:

1. Foundation A — lifecycle + artifact-runtime primitives + target/trust/provenance helpers + dynamic-count cleanup.
2. Foundation B1 — common machine-summary validation + v2 migration for PRD/MR/architecture/system/API/DB artifacts.
3. Foundation B2 — v2 migration for security/performance/capacity/observability/deployment/dependency artifacts.
4. PR A — change-impact-analyzer.
5. PR B — resilience-review + focused integrations.
6. PR C — implementation-planner + loop-task plan bridge/internal execution state.
7. PR D — production-readiness-review, including safe prerequisite refresh.
8. PR E — release-readiness manifest v2 + conditional production-readiness invocation.

Each PR should remain below the repository’s default review hard stop (40 changed files / 1500 changed lines) where practical. If generated projections push a PR above the file threshold, split generated/docs publication into a no-behavior follow-up rather than authorizing a larger behavioral review by default.

1.1 Normative requirement ownership

|Contract/change                                                                                  |Owning PR    |
|-------------------------------------------------------------------------------------------------|-------------|
|lifecycle order + runtime alternate-state primitive + target/trust helpers + dynamic counts      |Foundation A |
|common nested machine-summary validation + PRD/MR/architecture/system/API/DB v2                  |Foundation B1|
|security/performance/capacity/observability/deployment/dependency v2                             |Foundation B2|
|impact completeness/materiality/repos/criticality/triggers                                       |PR A         |
|resilience leaf + system-design recommendations + deployment-risk impact input                   |PR B         |
|deterministic single-repo plan + traceability + internal resume state + loop bridge              |PR C         |
|source/deployable scopes + trusted CI/build/review + operational gates + specialist orchestration|PR D         |
|release manifest v2 + trusted reuse/conditional production-readiness invoke + lifecycle E2E proof|PR E         |

Every normative requirement must have exactly one owning PR. A later PR may consume the contract but must not redefine it.

1.2 Mandatory baseline-drift preflight

Before Foundation A/B1/B2 or PR A–E changes code:

1. git fetch origin main (or authoritative equivalent) and record fresh origin/main SHA;
2. verify PR #159 merge commit 319eb2200264f5b2a4cdf327686d98e5383387ef is an ancestor of that SHA;
3. compare the fresh SHA with the previous delivery PR’s reviewed base;
4. re-read every changed runtime/composition/capability/routing contract touched by this program;
5. rerun the relevant existing contract tests before writing new behavior;
6. if baseline drift changes an assumption in this spec, stop and amend the owning plan before implementation.

Do not stack new work on PR #159’s old feature branch. The final PR #159 head 5566ffe52dd4095f0de71c3a7c39d6418ad07ea4 completed the required Lint, Secret Scan, Dependency Review, and CodeQL workflows successfully before merge.

A baseline SHA is evidence, not a forever pin: each later PR starts from the latest reviewed main after the preceding PR merges.

────────

2. Corrected lifecycle

The previous plan used the wrong generic order.

architecture-review requires a proposal and a concrete design description. system-design can start from a PRD. Therefore the default PRD flow is:

```text
prd-architect
  -> system-design
  -> architecture-review
  -> change-impact-analyzer
  -> applicable specialist reviews
  -> implementation-planner
  -> loop-task-implementer       # implementation + required tests + internal review/CI
  -> pr-review                   # fresh external PR/MR review when policy/workflow requires it
  -> change-impact-analyzer       # current candidate impact
  -> deployment-risk-review
  -> applicable current-candidate specialist reviews
  -> production-readiness-review
  -> release-readiness-checker
```

2.1 Architecture rework loop

If architecture-review returns Needs rework or Rejected, the next action is a new system-design invocation using the review findings as input.

Do not automatically recurse system-design -> architecture-review -> system-design inside one execution context. The platform recursion guard blocks revisits by default. Each rework generation starts a new invocation with a new source-artifact digest.

2.2 Existing architecture/ADR path

The existing PR #159 path remains valid when the caller already has an architecture proposal/ADR with enough design detail:

```text
architecture-review
  -> system-design
```

That is an alternate entry path, not the generic PRD path.

2.3 PR/MR routing by intent

A numbered PR/MR no longer overrides the user’s actual requested decision. The routing invariant is intent first, target second:

• Review PR #123 / find bugs in PR #123 -> pr-review
• Impact analysis for PR #123 -> change-impact-analyzer
• Deployment risk for PR #123 -> deployment-risk-review
• Is PR #123 production ready? -> production-readiness-review

This is deliberate. pr-review remains a framework leaf, and leaves cannot declare child invokes. Production readiness is the orchestrator and, for a PR/MR candidate, may invoke pr-review itself to obtain a gate-trusted exact-head mr_review_report.

PR/MR-aware intent owners (change-impact-analyzer, deployment-risk-review, production-readiness-review) accept the existing external mr_context locator when supplied. When only a URL/number is supplied, they may resolve the exact target through optional host.scm.change.read. They lock analysis to the retrieved head_sha; if the target/diff cannot be retrieved or the head moves before the final freshness check, they return UNKNOWN/BLOCKED rather than analyzing an assumed local branch. Standalone design/local-material inputs remain valid without SCM capability.

Collision rules:

• generic words such as “review” or “issues” select pr-review;
• explicit change impact|affected services|affected contracts|what does this change touch selects change impact;
• explicit deployment risk|release risk|blast radius|rollback risk selects deployment risk;
• explicit production ready|production readiness|safe to launch selects production readiness;
• if two decision intents are explicitly requested together, route to the higher-level orchestrator only when it owns composition of the lower-level decision; otherwise ask/return separate recommendations according to normal routing policy.

No pr-review -> production-readiness-review runtime invoke edge is added. pr-review may recommend the readiness skill in human-facing follow-up text, but that recommendation is not a composition handoff.

2.4 Test-generation mutation boundary

test-writer is not a mandatory post-implementation stage. implementation_plan.tasks[].required_tests are executed through the normal implementation task, and loop-task-implementer remains responsible for validating the resulting code/tests before it reports a task ready.

If test-writer is explicitly used to add tests to an implementation branch, it must run before the final review/CI gate. Any repository write from test-writer or its creator children creates a new change identity and invalidates prior clean review, CI, deployment-risk, and readiness evidence; those gates must be rerun against the new head.

────────

3. Foundation program — platform composition contracts

Foundation A, B1, and B2 are required before the four new skills. Foundation A adds reusable platform primitives and fixes lifecycle/routing; B1/B2 migrate producers/consumers to the strict v2 machine contracts in review-sized groups. None adds a new skill.

3.1 Foundation A — fix PR #159 design handoffs

Update the normative routing/escalation chain:

```text
prd-architect -> system-design       : prd_report gate/identity + full Final PRD content/ref
system-design -> architecture-review : system_design_spec gate/identity + full System Design Spec content/ref + PRD/proposal context
architecture-review -> system-design : only as a rework recommendation, new invocation
```

Remove the generic prd-architect -> architecture-review direct path unless a design description is already supplied.

Machine summary is not semantic content. prd_report and system_design_spec are machine gates/identity summaries; they do not replace the human PRD/design body. A lifecycle transition must also carry either the complete human document in the current invocation/handoff or a retrievable immutable reference whose digest/identity is tied to the machine artifact. If only the machine summary is available, the receiving skill returns BLOCKED (or asks for the missing document in an interactive standalone invocation) rather than inventing the missing design. Foundation B1 later makes this linkage machine-verifiable by migrating prd_report and system_design_spec to v2: the producer records the immutable source-document ref/digest in assessment_target.source_artifact_ref / source_artifact_digest, and the receiver recomputes/resolves the supplied document and requires an exact match before treating the machine gate and semantic document as one input. Foundation A must already enforce the behavioral rule before that schema exists.

Update at least:

• docs/skill-framework/shared/skill-routing.md
• docs/skill-framework/shared/cross-skill-escalation.md
• prd-architect/SKILL.md
• system-design/SKILL.md
• architecture-review/SKILL.md
• system-design/CHANGELOG.md
• architecture-review/CHANGELOG.md
• prd-architect/CHANGELOG.md

3.2 Normalized machine summary

Standalone Markdown reports remain human-readable. Composable durable artifacts gain a machine summary so downstream skills never parse Markdown.

Use these common fields for composable decision/review artifacts whose purpose is to return a review/readiness decision. Structural mapping/planning artifacts such as change_impact_report and implementation_plan keep their purpose-specific schemas; they still use typed provenance and explicit evidence_refs, but they do not acquire synthetic decision fields merely to look uniform:

```yaml
assessment_target:
  repo: string|null
  service: string|null
  environment: string|null
  source_type: prd|system_design|pr|mr|release_candidate|repository|caller_supplied
  base_revision: string|null
  head_revision_or_digest: string|null
  source_artifact_ref: string|null
  source_artifact_digest: string|null
normalized_decision:
  status: PASS|CONDITIONAL|FAIL|UNKNOWN|NOT_APPLICABLE
  raw_verdict: string
findings: list
conditions: list
required_actions: list
evidence_refs: list
```

Artifact-specific fields remain alongside these common fields. Foundation A adds the generic target/decision validators; Foundation B adds nested machine-summary validation so conditions cannot be silently dropped or reinterpreted downstream.

Required assessment_target keys are exactly repo, service, environment, source_type, base_revision, head_revision_or_digest, source_artifact_ref, and source_artifact_digest. Nullable fields may be null; source_type and any present digest/revision must be non-empty strings.

Required normalized_decision keys are exactly status and raw_verdict. status must be one of PASS|CONDITIONAL|FAIL|UNKNOWN|NOT_APPLICABLE; raw_verdict must be a non-empty string.

Each findings[] item is:

```yaml
id: string
category: string
summary: string
blocking: boolean
evidence_status: OBSERVED|INFERRED|UNKNOWN|CONFLICTED|NOT_APPLICABLE
evidence_refs: list
```

Each conditions[] item is:

```yaml
id: string
summary: string
required_before: IMPLEMENTATION|MERGE|DEPLOY|FOLLOW_UP
evidence_refs: list
```

Each required_actions[] item is:

```yaml
id: string
summary: string
required_before: IMPLEMENTATION|MERGE|DEPLOY|FOLLOW_UP
verification: string
evidence_refs: list
```

Rules:

• IDs are stable within one artifact (FIND-001, COND-001, ACT-001 or an equally deterministic producer-local convention).
• evidence_refs at the artifact root is the de-duplicated union of item-level evidence refs plus report-wide evidence.
• a required-check evidence gap is represented by a finding with evidence_status: UNKNOWN and participates in producer-side normalized-decision derivation;
• downstream consumers may use these structured items for traceability, but may not override the producer’s validated normalized_decision;
• extra keys in these common item mappings fail validation. Domain-specific details remain in the human report or artifact-specific fields.

Canonical target identity

assessment_target comparison is exact after lossless normalization only:

• repo: prefer the canonical repository locator returned by the host adapter. Normalize surrounding whitespace, Unicode NFC, lower-case the hostname, and remove one trailing .git. Do not alias different paths.
• service: trim surrounding whitespace and Unicode-normalize. Do not guess aliases.
• environment: trim, Unicode-normalize, and lower-case. prod and production remain different identifiers unless authoritative repository/runtime metadata explicitly maps them.
• source_type: exact enum match.
• base_revision: exact string match after trimming when present.
• head_revision_or_digest: exact string match after trimming.
• source_artifact_ref: trim surrounding whitespace and Unicode-normalize (NFC), then require exact string equality. Do not alias URLs, paths, branches, document IDs, or revisions.
• source_artifact_digest: exact lower-case SHA-256 hex match.

If two identities cannot be proven equivalent under these rules, treat them as different. Fuzzy matching is forbidden for readiness gates.

3.3 Foundation B1/B2 — artifact schema v2 scope

Upgrade only artifacts used by the delivery chain. Do not upgrade tech_debt_assessment in this wave.

Schema v2 applies to:

• prd_report
• mr_review_report
• architecture_review_report
• system_design_spec
• api_design_review_report
• database_review_report
• security_review_report
• performance_review_report
• capacity_plan
• observability_review_report
• deployment_risk_report
• dependency_upgrade_report

Migration ownership is split for reviewability:

• Foundation B1: prd_report, mr_review_report, architecture_review_report, system_design_spec, api_design_review_report, database_review_report, plus common nested-machine validation and the pr-gatekeeper delegate.
• Foundation B2: security_review_report, performance_review_report, capacity_plan, observability_review_report, deployment_risk_report, dependency_upgrade_report.

A mixed repository state with some artifacts at v2 and others at v1 is valid because artifact schema versions are registered per artifact. B2 depends on B1. No artifact is switched to v2 until every producer/delegate and known consumer for that artifact is updated in the same PR.

B1 adds two artifact-specific invariants on top of the nullable common target schema:

• prd_report v2 MUST have assessment_target.source_type: prd and a non-null valid source_artifact_digest of the complete Final PRD semantic document;
• system_design_spec v2 MUST have assessment_target.source_type: system_design and a non-null valid source_artifact_digest of the complete System Design semantic document.

A missing/wrong semantic-document digest makes those machine artifacts invalid; it is not downgraded to a usable PASS/CONDITIONAL artifact. source_artifact_ref remains optional when the complete document is carried in the invocation, but any supplied ref must obey the exact identity rules in §3.2.

For each migrated artifact, retain every existing v1 field and add the common machine-summary fields.

Example:

```yaml
security_review_report:
  title: string
  verdict: string
  assessment_target: mapping
  normalized_decision: mapping
  findings: list
  conditions: list
  required_actions: list
  evidence_refs: list
```

deployment_risk_report additionally keeps:

```yaml
risk: string
deployment_confidence: string
```

capacity_plan additionally keeps:

```yaml
headroom: string
```

observability_review_report additionally keeps:

```yaml
coverage: string
```

mr_review_report keeps its existing metadata and adds a machine verdict:

```yaml
mr_review_report:
  review_metadata: mapping
  posted: boolean
  head_sha: string
  integrated_revision: string   # authoritative merge/squash revision when known, otherwise `UNKNOWN`
  posting_mode: string
  assessment_target: mapping
  normalized_decision: mapping
  findings: list
  conditions: list
  required_actions: list
  evidence_refs: list
```

integrated_revision is populated only from authoritative SCM merge/squash metadata and is UNKNOWN while unmerged. Never infer it from the PR/MR head.

For mr_review_report.normalized_decision.status:

• PASS — no accepted blocking finding for the reviewed head.
• CONDITIONAL — no accepted blocker, but unresolved non-blocking conditions remain.
• FAIL — at least one accepted blocking finding exists.
• UNKNOWN — required review evidence or head identity is unavailable/stale.
• NOT_APPLICABLE is not used for a real PR/MR review.

3.4 Artifact v1 compatibility policy

Do not build an artifact upcaster in this wave.

The current validator supports one exact artifact schema version. After an artifact is upgraded to v2:

• new producers emit v2;
• new consumers require v2;
• supplied v1 machine artifacts are rejected with a clear artifact_schema_version unsupported; regenerate with current producer error;
• human Markdown can still be supplied as caller context, but it is not treated as a validated machine artifact.

This is simpler and safer than silent v1 parsing.

3.5 Foundation A — state-semantic support

Do not duplicate every specialist into separate design-time and implementation-time artifact types.

Extend contracts.platform.artifact_runtime with an optional map:

```yaml
allowed_state_semantics:
  api_design_review_report: [proposed_state, current_state]
  database_review_report: [proposed_state, current_state]
  security_review_report: [proposed_state, current_state]
  performance_review_report: [proposed_state, current_state]
  observability_review_report: [proposed_state, current_state]
  dependency_upgrade_report: [proposed_state]
  deployment_risk_report: [proposed_state]
```

Keep the existing state_semantics map as the default for backward compatibility.

Validation rules:

1. allowed_state_semantics is optional.
2. Keys must be durable artifact IDs.
3. Values are non-empty unique lists drawn from the existing state vocabulary.
4. The default state_semantics[artifact] value must appear in the allowed list.
5. If no allowed list exists, result state must equal the default exactly.
6. If an allowed list exists, result state may be any value in the list.

New resilience_review_report will use the same [proposed_state, current_state] policy from v1.

Do not change the global state vocabulary.

3.6 Foundation A — deterministic target digest

Use SHA-256.

For a validated durable machine artifact source:

```text
source_artifact_digest = SHA256(canonical_json(payload))
```

Canonical JSON means:

• UTF-8;
• keys sorted recursively;
• separators , and : with no insignificant whitespace;
• JSON scalar values preserved exactly;
• the payload only, excluding freshness timestamps and outer result-envelope metadata.

For raw text supplied as the assessment source, including the complete Final PRD behind prd_report and the complete System Design body behind system_design_spec:

```text
source_artifact_digest = SHA256(normalized_utf8_text)
```

In those two lifecycle artifacts the digest binds the compact machine result to the full semantic source document. It is not the hash of the compact prd_report / system_design_spec payload. The receiver recomputes or resolves this full-document digest before accepting the machine summary and semantic body as one input.

Normalization:

• decode as UTF-8;
• replace CRLF/CR with LF;
• do not trim leading/trailing content;
• hash the resulting UTF-8 bytes.

For Git-backed code/config, head_revision_or_digest is the authoritative commit SHA. A content digest is still allowed for a specific source document, but it does not replace the commit SHA.

3.7 Freshness and evidence scope

Freshness is consumer-specific. Do not require every artifact to match the final deployable identity.

Static/source-backed evidence is primarily revision/digest driven; runtime observations also require source-specific temporal freshness. Do not invent a universal TTL. If a runtime source has a repository/service policy for freshness, use it; otherwise acquire it in the current invocation or mark the affected claim UNKNOWN.

Generic direct reuse outside production readiness compares every non-null target field relevant to the artifact’s own source. Production readiness uses the explicit evidence-scope matrix in §8.11:

• SOURCE_SCOPED — reviews/impact/risk tied to the source revision;
• PLANNING_BASIS_SCOPED — capacity planning tied to source revision plus its demand/baseline input digest;
• DEPLOYABLE_SCOPED — final readiness tied to the immutable deployable SHA/image digest.

A mismatch means stale. Unknown identity means the affected claim is UNKNOWN; do not silently reuse the artifact. prod and production never fuzzy-match.

3.8 Artifact trust and provenance

Schema-valid is not the same as trusted. Downstream gating carries trust outside the artifact payload:

```yaml
artifact_trust:
  artifact_type: string
  producer_skill: string|null
  acquisition: direct_child|runtime_validated|caller_supplied|repository_file
  trusted_for_gate: boolean
  evidence_ref: string|null
```

Rules:

1. producer_skill comes from trusted runtime/dispatch context, never from skill_result.skill alone.
2. direct_child is trusted only after validate_artifact_result(root, artifact_type, result, producer_skill=runtime_child_id) succeeds.
3. runtime_validated is trusted only when the runtime retained trusted producer context from the production event.
4. caller_supplied and repository_file artifacts may be parsed as untrusted evidence, but cannot independently satisfy a PASS/READY gate.
5. Untrusted artifacts may trigger a fresh child run or contribute to UNKNOWN/CONDITIONAL analysis; they cannot promote a dimension to PASS.
6. Host-owned SCM/CI facts use separate authoritative evidence contracts; fetching a skill artifact through an authoritative host does not make that artifact gate-trusted.
7. Artifact trust metadata is execution metadata, never a self-asserted durable-artifact field.

Add regression tests proving a caller-supplied payload with normalized_decision.status: PASS cannot satisfy production or release readiness without trusted producer context.

3.8.1 Evidence authority is independent of producer trust

A trusted producer can still analyze untrusted evidence. Producer trust must never launder input authority. Every artifact used for machine composition in this initiative uses typed entries in the existing envelope provenance.sources list. For existing artifacts this becomes mandatory when they migrate to schema v2 in B1/B2; every new artifact introduced by PR A–D uses the same typed provenance from its first schema version:

```yaml
provenance:
  source_revision: string|UNKNOWN|null
  sources:
    - ref: string
      authority: authoritative_host|repository|trusted_runtime|caller|model_knowledge
      kind: scm|repo_content|ci|runtime_metric|service_metadata|build_provenance|artifact|caller_input|model_knowledge
      observed_at: string|UNKNOWN|null
      source_revision: string|UNKNOWN|null
      source_environment: string|UNKNOWN|null
      derived_from: list
```

Rules:

1. every root evidence_refs item in a v2 composable payload resolves to exactly one provenance.sources[].ref; dangling or duplicate refs fail validation;
2. caller stays caller through every handoff/child invocation; repository stays repository-scoped; model knowledge is always model_knowledge;
3. trusted_runtime is reserved for a fact produced from runtime-owned state. A derived source using other evidence lists those refs in derived_from; it does not upgrade their original authority;
4. authoritative_host means a host/API is authoritative for that fact (for example exact SCM/CI state), not that arbitrary file contents fetched through the host become authoritative;
5. a direct child result can be producer-trusted while one or more of its claims remain caller/model-knowledge-backed. Dimension gate policy evaluates both producer trust and the authority of the evidence refs supporting the decision;
6. conflicting authoritative sources remain CONFLICTED/UNKNOWN; lower-authority evidence cannot override them.

Foundation A’s external assessment_context carries the same rule per input:

```yaml
assessment_context:
  assessment_target: mapping
  inputs: mapping
  input_provenance: mapping   # input key -> {authority, evidence_refs}
  evidence_refs: list
  unresolved: list
```

The parent copies or derives input_provenance; the child preserves it when writing provenance.sources. Parent dispatch itself never upgrades authority.

input_provenance.authority is descriptive metadata, not self-authenticating. The runtime also carries context trust outside the external artifact:

```yaml
assessment_context_trust:
  acquisition: runtime_handoff|caller_supplied
  parent_skill: string|null
  parent_execution_validated: boolean
```

Only the runtime sets this metadata. Rules:

• caller_supplied: all authority labels inside the context are treated as caller until the child independently resolves/retrieves the cited source; a caller cannot write authority: authoritative_host and promote a gate;
• runtime_handoff: authority labels are usable only when parent_execution_validated=true and the runtime knows the invoking parent_skill; the child preserves the parent’s effective authorities and never upgrades them;
• missing/invalid context-trust metadata defaults to caller_supplied;
• the runtime handoff envelope remains context, not authority; actual host/repository claims still require resolvable evidence refs.

Foundation B1 owns the reusable deep typed-provenance validator. B1/B2 call it for migrated v2 artifacts; PR A–D call the same helper for every new composable artifact even when that artifact starts at schema version 1.

3.9 Producer-side normalized-decision derivation

Downstream consumers never parse Markdown and never infer normalized status from the human verdict alone when that verdict can represent either a finding or an evidence gap. Every producer derives normalized_decision from its structured findings, conditions, and unknowns.

Common rule:

• PASS: every required check completed and clean;
• CONDITIONAL: required checks completed; only known, nonblocking findings/conditions remain;
• FAIL: at least one proven blocking defect/risk exists;
• UNKNOWN: a required check or applicability decision remains unresolved because evidence is missing/conflicted;
• NOT_APPLICABLE: the producer deterministically established the dimension does not apply.

Producer-specific derivation:

|Artifact                     |Human verdict                                                                                            |Normalized rule                                                                                                       |
|-----------------------------|---------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|`architecture_review_report` |`Approved`                                                                                               |`PASS`                                                                                                                |
|                             |`Approved with conditions`                                                                               |`CONDITIONAL` when conditions are known/nonblocking; `UNKNOWN` if a required evidence gap is what caused the condition|
|                             |`Needs rework`                                                                                           |`FAIL` for a proven material risk; `UNKNOWN` when caused only by a missing required input/check                       |
|                             |`Rejected`                                                                                               |`FAIL`                                                                                                                |
|`system_design_spec`         |`Ready to implement`                                                                                     |`PASS`                                                                                                                |
|                             |`Ready with open questions`                                                                              |`CONDITIONAL`; every open question must be carried downstream and may still block safe task decomposition             |
|                             |`Not ready`                                                                                              |`FAIL`                                                                                                                |
|`api_design_review_report`   |`Approved`                                                                                               |`PASS`                                                                                                                |
|                             |`Approved with conditions`                                                                               |`CONDITIONAL` when all required checks ran; `UNKNOWN` if any required check is `Unknown`                              |
|                             |`Changes required` / `Rejected`                                                                          |`FAIL`                                                                                                                |
|`database_review_report`     |`Approved`                                                                                               |`PASS`                                                                                                                |
|                             |`Approved with conditions`                                                                               |`CONDITIONAL` when all required checks ran; `UNKNOWN` if any required check is `Unknown`                              |
|                             |`Changes required` / `Rejected`                                                                          |`FAIL`                                                                                                                |
|`security_review_report`     |`Pass` / `Pass with findings` / `Fail — Critical/High findings present` / `Blocked — insufficient access`|`PASS` / `CONDITIONAL` / `FAIL` / `UNKNOWN`                                                                           |
|`performance_review_report`  |`Pass`                                                                                                   |`PASS`                                                                                                                |
|                             |`Pass with findings`                                                                                     |`CONDITIONAL` when all required areas were evaluated; `UNKNOWN` when any required area remains an evidence gap        |
|                             |`Fail — regression risk` / `Blocked — insufficient evidence`                                             |`FAIL` / `UNKNOWN`                                                                                                    |
|`capacity_plan`              |`Sufficient` / `Marginal` / `Insufficient` / `Unknown — insufficient historical data`                    |`PASS` / `CONDITIONAL` / `FAIL` / `UNKNOWN`                                                                           |
|`observability_review_report`|`Adequate` / `Partial gaps` / `Critical gaps` / `Unknown — insufficient input`                           |`PASS` / `CONDITIONAL` / `FAIL` / `UNKNOWN`                                                                           |
|`dependency_upgrade_report`  |`Safe to upgrade` / `Upgrade with mitigations` / `Do not upgrade yet` / `Blocked — insufficient info`    |`PASS` / `CONDITIONAL` / `FAIL` / `UNKNOWN`                                                                           |

deployment_risk_report is two-dimensional and is derived from both risk and deployment_confidence:

• Critical -> FAIL;
• High + LOW|UNKNOWN confidence -> UNKNOWN;
• High + HIGH|MEDIUM -> CONDITIONAL;
• Moderate -> CONDITIONAL unless confidence is UNKNOWN, then UNKNOWN;
• Low + HIGH|MEDIUM -> PASS;
• Low + LOW|UNKNOWN -> UNKNOWN.

mr_review_report uses its structured review outcome, accepted blocking findings, unresolved evidence, and exact-head freshness—not posting metadata. Any new/unrecognized human verdict or contradictory structured finding set fails producer-contract validation; it never falls through to a guessed normalized state.

3.10 Execution status vs decision status

skill_result.status describes whether the analysis workflow executed correctly. normalized_decision.status describes what the analysis found. They are intentionally different axes.

Common rule for review/planning artifacts:

• proven blocker -> normalized_decision: FAIL, but skill_result.status: SUCCESS when all required checks completed and the blocker was established correctly;
• clean result -> PASS + SUCCESS;
• known nonblocking conditions with complete evidence -> CONDITIONAL + SUCCESS;
• deterministic non-applicability -> NOT_APPLICABLE + SUCCESS;
• report produced but a required check/evidence area remains unresolved -> UNKNOWN + PARTIAL;
• mandatory identity/input/capability absent before the analysis can validly run -> BLOCKED;
• internal invariant/schema/validator failure after execution starts -> FAILED;
• ESCALATED only when the skill contract explicitly transfers the next primary decision to a human/skill rather than merely recommending follow-up.

A child returning FAILED or BLOCKED never becomes a parent FAIL finding by itself; it becomes parent UNKNOWN unless separate trusted evidence proves a blocker.

For production-readiness-review specifically:

• verdict READY|CONDITIONAL|NOT_READY with every required applicable dimension resolved -> skill_result.status: SUCCESS;
• if any required applicable dimension remains unresolved, skill_result.status: PARTIAL even when a separate proven FAIL already fixes the decision verdict at NOT_READY;
• verdict UNKNOWN because one or more required dimensions are unresolved -> PARTIAL;
• candidate identity cannot be established -> BLOCKED;
• deterministic aggregator/schema failure -> FAILED.

3.10.1 Aggregate evidence status

For new/v2 composable artifacts, derive the envelope’s single evidence_status deterministically from decision-critical evidence:

1. any unresolved material authoritative conflict -> CONFLICTED;
2. else any required unknown/unavailable evidence -> UNKNOWN;
3. else any decision-critical claim inferred rather than directly observed -> INFERRED;
4. else all decision-critical evidence observed -> OBSERVED;
5. NOT_APPLICABLE only when the entire produced assessment is deterministically non-applicable.

A proven FAIL can therefore carry OBSERVED evidence and high confidence; FAIL is not synonymous with execution/evidence failure. Downstream consumers do not upgrade UNKNOWN|CONFLICTED evidence to PASS merely because raw_verdict sounds positive.

3.11 Version ledger

Version ownership is explicit so split PRs do not guess or double-apply a bump. Each row is relative to the immediately preceding PR in this delivery sequence. If the live baseline/version differs from the reviewed sequence, stop and re-review/update this design and the affected implementation plan before coding; do not silently substitute a different bump.

|PR           |Skill                        |Expected transition from merged PR #159/main baseline|Reason                                                              |
|-------------|------------------------------|-----------------------------------------------------:|---------------------------------------------------------------------|
|Foundation A |`prd-architect`              |`1.2.0 -> 1.3.0`                                     |lifecycle/routing recommendation changes                            |
|Foundation A |`system-design`              |`1.0.0 -> 1.1.0`                                     |PRD input/architecture-review handoff contract changes              |
|Foundation A |`architecture-review`        |`1.0.0 -> 1.1.0`                                     |system-design input/rework recommendation contract changes          |
|Foundation B1|`prd-architect`              |`1.3.0 -> 1.4.0`                                     |`prd_report` v2 source-document binding + normalized machine outcome|
|Foundation B1|`pr-review`                  |`1.1.0 -> 1.2.0`                                     |`mr_review_report` v2 machine outcome/integrated revision           |
|Foundation B1|`pr-gatekeeper`              |`1.0.0 -> 1.1.0`                                     |delegated v2 `mr_review_report`                                     |
|Foundation B1|`system-design`              |`1.1.0 -> 1.2.0`                                     |`system_design_spec` v2                                             |
|Foundation B1|`architecture-review`        |`1.1.0 -> 1.2.0`                                     |`architecture_review_report` v2                                     |
|Foundation B1|`api-design-review`          |`1.0.0 -> 1.1.0`                                     |artifact v2 producer                                                |
|Foundation B1|`database-review`            |`1.0.0 -> 1.1.0`                                     |artifact v2 producer                                                |
|Foundation B2|`security-review`            |`1.0.0 -> 1.1.0`                                     |artifact v2 producer                                                |
|Foundation B2|`performance-review`         |`1.0.0 -> 1.1.0`                                     |artifact v2 producer                                                |
|Foundation B2|`capacity-planner`           |`1.0.0 -> 1.1.0`                                     |artifact v2 producer                                                |
|Foundation B2|`observability-review`       |`1.0.0 -> 1.1.0`                                     |artifact v2 producer                                                |
|Foundation B2|`deployment-risk-review`     |`1.0.0 -> 1.1.0`                                     |artifact v2 producer                                                |
|Foundation B2|`dependency-upgrade-review`  |`1.0.0 -> 1.1.0`                                     |artifact v2 producer                                                |
|PR A         |`change-impact-analyzer`     |new `1.0.0`                                          |new leaf                                                            |
|PR B         |`resilience-review`          |new `1.0.0`                                          |new leaf                                                            |
|PR B         |`system-design`              |`1.2.0 -> 1.3.0`                                     |add change-impact + resilience recommendations together             |
|PR B         |`deployment-risk-review`     |`1.1.0 -> 1.2.0`                                     |optional trusted change-impact input                                |
|PR C         |`implementation-planner`     |new `1.0.0`                                          |new leaf                                                            |
|PR C         |`loop-task-implementer`      |`1.2.0 -> 1.3.0`                                     |implementation-plan input/internal plan execution state             |
|PR D         |`production-readiness-review`|new `1.0.0`                                          |new orchestrator                                                    |
|PR E         |`release-readiness-checker`  |`1.0.0 -> 1.1.0`                                     |manifest v2 + conditional production-readiness composition          |

Embedded assessment_context consumption is included in the same B1/B2 minor bump for API/DB and specialist leaves that production readiness may invoke; do not add a second version bump later just for embedded invocation. New change-impact/resilience/readiness skills include it at 1.0.0.

B1 bumps prd-architect once more because prd_report now joins the strict v2 migration; B2 does not touch it. PR A intentionally does not modify system-design or pr-review; system-design recommendations are added once in PR B, while PR/MR intent routing changes live in the shared routing table without turning pr-review into an orchestrator.

No root distribution version bump is required unless preparing a release.

3.12 Foundation A — remove hard-coded skill/scenario counts

Foundation A should de-hardcode counts that are registry-derived so later skill additions do not require unrelated edits.

Update:

• scripts/tests/test_install_all_skills.sh
• scripts/tests/test_install_support.py
• scripts/tests/test_p1_runtime_manifest.py
• scripts/tests/test_platform_eval_contract.py
• scripts/tests/test_risk_class.py
• scripts/tests/test_batch3_eval_contract.py
• scripts/tests/test_batch3_scenario_harness.py
• scripts/tests/test_evals_tier3.py

Rules:

• expected registered-skill count comes from skills.yaml/registry;
• expected scenario count is len(registry.skills) * len(REQUIRED_DIMENSIONS);
• golden coverage remains enforced per registered skill;
• remove the exact global 65 fixture count because per-skill coverage + unique fixture IDs are the meaningful invariants.

────────

3.13 Security-scanner-safe adversarial fixtures

PR #159 demonstrates that prompt-injection fixtures can accidentally look like real credentials and fail Secret Scan.

For every new or modified committed eval/golden fixture:

• never commit randomized or realistic AWS/GitHub/private-key/token-shaped values;
• when a secret-shaped example is necessary, use the repository/workflow-documented well-known non-functional ...EXAMPLE form or a clearly non-matching sentinel;
• do not add .gitleaksignore fingerprints merely to make a new fixture pass unless the repository security policy explicitly approves that exact fixture;
• the real scanner negative test remains generated at runtime in .github/workflows/secret-scan.yml, not committed;
• before merge, require the actual GitHub Secret Scan workflow to be green in addition to local lint/evals.

4. New skill: change-impact-analyzer

4.1 Purpose

Answer:

> What is affected by this design/change, what evidence supports that impact, and which specialist reviews are applicable?

It does not assign deployment risk and does not execute child reviews.

4.2 Type and permissions

```yaml
name: change-impact-analyzer
type: leaf
invocation: ambient
risk_class: [read-only]
permissions:
  repository: read
  external_actions: none
  unattended: false
  merge: false
version: 1.0.0
```

4.3 Capabilities

```yaml
required:
  - host.report.write
optional:
  - name: host.repository.read
    enables: repository-backed dependency/caller/config impact discovery
```

Degraded behavior:

• no repository read: analyze supplied artifacts only and mark undiscoverable code/config impact UNKNOWN;
• no ownership evidence: keep owners UNKNOWN and recommend squad-map when material;
• no domain map/current-system evidence: do not invent bounded-context impact; recommend domain-comprehension when material.

4.4 Inputs

At least one primary source is required:

• system_design_spec v2;
• mr_context or exact normalized PR/MR diff context supplied directly/authoritatively;
• caller-supplied design/change text.

Optional:

• current repository context;
• current domain map;
• ownership map;
• prior specialist reports.

4.5 change_impact_report v1

State semantic: source-dependent, allowed [proposed_state, current_state].

```yaml
change_impact_report:
  title: string
  assessment_target: mapping
  coverage_status: string
  material_unknowns: list
  impacted_repositories: list
  criticality: string
  change_classes: list
  impacted_services: list
  impacted_contracts: list
  impacted_data: list
  impacted_dependencies: list
  impacted_owners: list
  required_tests: list
  operational_impacts: list
  review_triggers: list
  unknowns: list
  evidence_refs: list
```

Allowed change_classes:

```text
docs_only
test_only
build_tooling
runtime_code
api_contract
schema_or_data
infra_or_config
dependency
operational
```

Allowed review_triggers:

```text
api
database
security
performance
capacity
observability
resilience
dependency_upgrade
k8s_rightsizing
```

Impact completeness and repository scope

coverage_status is exactly COMPLETE|PARTIAL|UNKNOWN.

• COMPLETE: all material surfaces discoverable from supplied/retrieved evidence were evaluated and no applicability-affecting unknown remains.
• PARTIAL: at least one material surface is known to be unverified.
• UNKNOWN: there is not enough scope evidence to make safe trigger decisions.

material_unknowns names unresolved items that could change specialist applicability. Planner/readiness cannot be READY while coverage_status != COMPLETE unless each material unknown is resolved by newer trusted evidence. For a PR/MR current-candidate analysis, COMPLETE additionally requires repository-backed evidence for the exact base/head diff plus bounded caller/consumer/contract discovery; supplied prose or a partial diff alone can never claim COMPLETE.

impacted_repositories uses canonical repo identities and may contain multiple repositories. criticality is tier0|tier1|tier2|tier3|unknown. Source precedence is authoritative service/repository metadata, then trusted release/change metadata. Caller text may raise criticality conservatively but cannot lower an authoritative value. Conflicting authoritative values resolve to unknown, which uses the strictest readiness policy.

change-impact-analyzer remains a true leaf: it may consume supplied/retrieved domain and ownership evidence and recommend domain-comprehension or squad-map, but has no child *.invoke capability and no composition invokes entry.

Bounded discovery rule: repository-backed impact analysis starts from changed/declared targets and follows direct callers, direct consumers, public contracts, schema/config/dependency manifests, and ownership metadata. It does not recursively crawl the entire dependency graph; unresolved deeper impact remains a material unknown.

4.6 Trigger rules

• api_contract -> api
• schema_or_data -> database
• authn/authz/secrets/crypto/trust-boundary/data exposure -> security
• hot-path complexity/N+1/cache/concurrency/pool/fanout -> performance
• changed expected demand/headroom/replica requirement -> capacity
• logging/metrics/traces/SLO/alert/correlation changes or operational visibility gap -> observability
• timeout/retry/backpressure/circuit-breaker/partial-failure/recovery behavior -> resilience
• dependency/framework/lockfile version change -> dependency_upgrade
• Kubernetes requests/limits/HPA/replicas/resource sizing -> capacity and k8s_rightsizing (capacity is the pre-release readiness dimension; K8s rightsizing remains advisory/current-live evidence and is already owned by release readiness)

A trigger is evidence-derived. Missing evidence belongs in unknowns.

────────

5. New skill: resilience-review

5.1 Purpose

Independently review a proposed design or current implementation for resilience behavior.

5.2 Review dimensions

• timeout budgets;
• retry policy and retry amplification;
• circuit breaking;
• load shedding;
• backpressure;
• queue backlog and poison-message handling;
• duplicate delivery/idempotency;
• downstream outage and latency behavior;
• partial-failure consistency;
• recovery/reconciliation.

5.3 Boundaries

Not for:

• live incident diagnosis -> incident-rca;
• demand forecasting -> capacity-planner;
• current K8s rightsizing -> k8s-overprovisioning-datadog;
• generic code review of a PR/MR -> pr-review entry first.

5.4 resilience_review_report v1

Allowed state semantics: [proposed_state, current_state].

```yaml
resilience_review_report:
  title: string
  verdict: string
  assessment_target: mapping
  normalized_decision: mapping
  findings: list
  conditions: list
  required_actions: list
  evidence_refs: list
```

Human verdict vocabulary:

```text
Approved
Approved with conditions
Changes required
Blocked — insufficient evidence
```

Normalized mapping:

• Approved -> PASS
• Approved with conditions -> CONDITIONAL
• Changes required -> FAIL
• Blocked — insufficient evidence -> UNKNOWN

────────

6. New skill: implementation-planner

6.1 Purpose

Turn a fresh approved system design, architecture review, change-impact report, and applicable specialist evidence into an executable dependency-aware implementation plan.

It is a leaf in this wave. It does not invoke architecture/design/review skills and it does not write production code.

6.2 Required inputs

• system_design_spec v2 with readiness not Not ready;
• architecture_review_report v2 with normalized status PASS or CONDITIONAL;
• change_impact_report v1;
• all design-time specialist reports triggered by change_impact_report.review_triggers for api, database, security, performance, capacity, observability, resilience, and dependency_upgrade. k8s_rightsizing is a current-runtime/release check and is not a design-time prerequisite for implementation planning. A triggered review that cannot produce a usable result is an explicit planning blocker rather than an omitted input.

Repository read is required so target paths/modules and repository-specific verification can be grounded.

6.3 Capabilities

```yaml
required:
  - host.report.write
  - host.repository.read
optional: []
```

6.4 implementation_plan v1

State semantic: proposed_state.

```yaml
implementation_plan:
  plan_set_id: string
  plan_id: string
  title: string
  readiness: string
  assessment_target: mapping
  target_repo: string
  external_dependencies: list
  source_refs: list
  tasks: list
  execution_waves: list
  sequencing_constraints: list
  verification_gates: list
  traceability: mapping
```

Allowed readiness:

```text
READY
PARTIAL
BLOCKED
```

Each task is:

```yaml
task_id: string
title: string
task_type: code|config|schema|migration|other
executor: loop-task-implementer
scope: string
target_paths: list
acceptance_criteria: list
dependencies: list
required_tests: list
verification: list
rollout_notes: list
completion_evidence: list
source_condition_refs: list
source_action_refs: list
estimated_scope: mapping
```

6.5 Deterministic plan identity

plan_set_id identifies all per-repository plans derived from the same immutable change-impact/design source set.

```text
plan_set_id = "PLANSET-" + first12(SHA256(canonical_json({
  change_impact_digest,
  system_design_digest,
  architecture_review_digest
})))
```

plan_id is deterministic per target repository:

```text
plan_id = plan_set_id + "-" + first8(SHA256(canonical_target_repo))
```

Regenerating a plan from unchanged source artifacts yields the same IDs. Any material source digest change yields a new plan set. This makes resume/idempotency and cross-repo coordination auditable without a global orchestrator.

6.6 Condition/action traceability

implementation_plan.traceability contains:

```yaml
condition_coverage: mapping
action_coverage: mapping
required_test_coverage: mapping
```

Every upstream conditions[] / required_actions[] item with required_before: IMPLEMENTATION|MERGE|DEPLOY must map to at least one task, verification gate, or explicit external_dependency. Every change_impact_report.required_tests entry must map to a task’s required_tests or a verification gate.

A READY plan with an uncovered required condition/action/test is invalid.

6.7 Repository scope

implementation_plan v1 is intentionally single-repository.

• target_repo equals the canonical repo identity used by every executable task.
• target_paths are inside target_repo; tasks cannot silently target another repository.
• If impact names multiple repos, invoke implementation-planner once per repo.
• Cross-repo ordering is modeled as external_dependencies, each with repo, required_state_or_artifact, reason, and evidence_ref.
• When all sibling plans for a plan_set_id are available, validate the cross-repository external-dependency graph and reject a proven cycle. If a sibling plan is unavailable, keep the dependency unresolved; never assume it complete.
• Missing required external plans/artifacts caps plan readiness at PARTIAL/BLOCKED.
• loop-task-implementer never edits more than one repository from one plan in this wave.

6.8 Execution-size compatibility

Planner tasks must be realistically executable by loop-task-implementer. Each task carries:

```yaml
estimated_scope:
  estimate_known: boolean
  files_upper_bound: integer
  changed_lines_upper_bound: integer
  confidence: HIGH|MEDIUM|LOW|UNKNOWN
```

Rules:

• use repository evidence and target paths to make a conservative upper-bound estimate;
• when estimate_known: false, both numeric bounds MUST be 0, confidence MUST be UNKNOWN, and the plan cannot be READY; zero is only a schema sentinel and must never be interpreted as zero work;
• when estimate_known: true, both bounds must be non-negative integers and confidence must be HIGH|MEDIUM;
• if the estimate exceeds the current loop-task hard stop (default >40 files or >1500 changed lines), split the task before plan readiness can be READY;
• if repository policy/config has stricter limits, use the stricter values; the planner never raises executor circuit breakers;
• actual execution still enforces loop-task’s authoritative size guards; the estimate never overrides them.

6.9 Single dependency source of truth

tasks[].dependencies is the only dependency graph.

Do not add a second dependency_edges field.

6.10 Execution waves

Do not call the output a critical_path unless task durations exist.

execution_waves is a deterministic topological layering:

```yaml
execution_waves:
  - [TASK-001, TASK-002]
  - [TASK-003]
  - [TASK-004, TASK-005]
```

Every task appears exactly once. A task may only appear after all dependencies appear in an earlier wave.

6.11 Readiness rules

• READY: DAG valid, no planning-critical upstream FAIL/UNKNOWN, all tasks concrete and verifiable.
• PARTIAL: useful plan exists but one or more non-blocking optional details remain unknown.
• BLOCKED: invalid/stale source, architecture FAIL, required specialist FAIL/UNKNOWN, cycle, missing dependency, missing acceptance criteria, or target cannot be grounded.

6.12 Validator

Create scripts/implementation_plan.py with a CLI validation mode and tests.

Validate:

• unique task IDs;
• every dependency exists;
• no self-dependency;
• DAG has no cycle;
• every task appears exactly once in execution_waves;
• wave order respects dependencies;
• executor is exactly loop-task-implementer in this wave;
• required task fields are non-empty;
• READY is forbidden when a blocking source status is present.

6.13 Loop-task integration

loop-task-implementer continues to accept legacy implementation_task unchanged.

When given implementation_plan:

1. validate it;
2. require readiness == READY;
3. select one dependency-satisfied task from the earliest incomplete execution wave;
4. normalize that task into the existing internal task structure;
5. before dispatch, re-read official per-task state and SCM state using a deterministic plan_id + task_id + target_repo execution identity; branch/PR creation is idempotent and a create race causes re-read/adopt-or-BLOCK, never a random duplicate branch;
6. run the existing builder/reviewer/CI lifecycle unchanged;
7. do not mutate the canonical plan.

6.14 Internal plan_execution_state

Do not register a second durable composition artifact for plan progress.

The current runtime result envelope carries one state_semantic and artifact_schema_version per result. loop-task-implementer already produces implementation_pr (proposed_state); making the same result also canonically produce a transitional_state plan artifact would violate that contract.

Instead extend loop-task’s official internal state with a separate host/runtime state file:

```yaml
plan_execution_state:
  schema_version: 1
  plan_id: string
  plan_digest: string
  target_repo: string
  state_generation: integer
  current_task_id: string|null
  task_statuses: mapping
  completed_evidence_refs: list
  observed_head_revision: string|null
  blocked_reason: string|null
  updated_at: string
```

This is workflow state, not a durable composition artifact and is not listed in skill_result.artifacts.

Rules:

1. plan_digest = SHA256(canonical_json(implementation_plan.payload)).
2. Per-task status remains authoritative in the existing task state; plan_execution_state.task_statuses is the plan index/checkpoint and must reconcile to task state + authoritative SCM evidence.
3. Caller/file-supplied state is advisory until reconciled. It cannot make a task COMPLETE by assertion.
4. state_generation increases monotonically; a stale generation cannot overwrite a newer runtime state.
5. On resume, verify plan digest, target repo, current repository head, existing branch/PR, and completion evidence before choosing another task.
6. If two invocations race, deterministic task/branch identity plus re-read-after-create must prevent duplicate execution; a conflicting active branch/PR blocks the later invocation.
7. Repository-head drift revalidates completed evidence, external dependencies, and pending task eligibility.
8. No generic artifact store or cryptographic attestation service is introduced in this wave.
9. The canonical implementation_plan is immutable.

7. Existing deployment-risk-review extension

Keep it a leaf.

7.1 New optional input

Allow a fresh change_impact_report v1.

Use it for:

• blast radius;
• affected services/users/data;
• upstream/downstream dependency scope;
• identified migrations/config surfaces.

Do not let it replace the existing required change_description contract unless the report contains an explicit equivalent description.

7.2 Machine result

Foundation B2 already moves deployment_risk_report to v2.

Production readiness must evaluate both:

• risk; and
• deployment_confidence.

A high risk caused by missing rollback/migration evidence is not a confident conditional approval; it is an evidence gap that prevents READY.

────────

8. New skill: production-readiness-review

8.1 Type

orchestrator, read-only.

8.2 Purpose

Answer:

> Is this exact implementation/release candidate operationally safe enough to proceed to release readiness?

It aggregates specialists. It does not duplicate their analysis logic.

8.3 Required candidate identity

```yaml
candidate:
  repo: string
  service: string
  environment: string|null
  source_revision: string
  head_revision_or_digest: string
  source_type: pr|mr|release_candidate
  criticality: tier0|tier1|tier2|tier3|unknown
```

8.4 Required evidence and prerequisite refresh

Production readiness requires fresh gate-trusted change_impact_report and deployment_risk_report, but they may be reused or refreshed rather than forced on the caller as precomputed artifacts.

Resolution order for each prerequisite:

1. reuse a gate-trusted compatible artifact;
2. otherwise, if repository/change inputs are sufficient and the corresponding invoke capability exists, invoke the leaf producer once;
3. otherwise mark readiness UNKNOWN with the missing prerequisite named.

production-readiness-review may therefore have optional invokes for:

• change-impact-analyzer.invoke;
• deployment-risk-review.invoke.

It remains the only new orchestrator. The two prerequisite leaves do not invoke it or each other.

Candidate identity rules:

• source_revision is the immutable source-control revision that code review and CI prove;
• head_revision_or_digest is the exact deployable/review target. For PR/MR it equals source_revision; for a release candidate it may be an immutable image/artifact digest;
• if those differ, trusted build provenance is mandatory.

For PR/MR candidates, verification requires a fresh gate-trusted mr_review_report v2 whose head_sha == source_revision.

For release candidates, verification uses trusted code-review coverage for every included material change plus trusted build provenance from source_revision to the deployable digest.

Failed required checks -> NOT_READY; missing/stale required-check visibility -> UNKNOWN.

8.5 Trusted CI evidence

Do not invent a generic durable CI artifact in this wave, but READY requires authoritative CI evidence.

```yaml
trusted_ci_evidence:
  provider: string
  repo: string
  head_revision: string
  required_checks: list
  observed_checks: list
  all_required_green: boolean
  observed_at: string
  acquisition: authoritative_host|trusted_runtime
  evidence_ref: string
```

Rules:

• repo and head_revision exactly match the candidate.
• required_checks comes from authoritative branch/repository policy, not caller text.
• observed_checks contains check name, status/conclusion, and provider run/check-suite identity.
• all_required_green is derived by the collector; never trust a caller-supplied boolean.
• caller-supplied CI summaries are untrusted context only.
• inability to retrieve authoritative required-check state -> CI dimension UNKNOWN.

8.6 Trusted build provenance

Required only when candidate.head_revision_or_digest != candidate.source_revision.

```yaml
build_provenance:
  provider: string
  repo: string
  source_revision: string
  deployable_digest: string
  build_run_id: string
  build_status: SUCCESS|FAILED|UNKNOWN
  observed_at: string
  acquisition: authoritative_host|trusted_runtime
  evidence_ref: string
```

Rules:

• exact repo/source/digest match;
• build status must be SUCCESS;
• acquisition must be authoritative host/runtime;
• caller/file claims never establish the link;
• missing/mismatched provenance -> readiness UNKNOWN.
• if authoritative repository/service policy requires artifact signature/attestation, SBOM/provenance validation, or another build-supply-chain control, that policy result is part of build provenance: missing required proof -> UNKNOWN; proven failed required control -> FAIL. No such control is made globally mandatory when policy does not require it.

8.7 Capabilities

```yaml
required:
  - host.report.write
optional:
  - name: host.repository.read
    enables: collecting child inputs from the candidate repository
  - name: host.scm.change.read
    enables: resolving an exact PR/MR/commit target and diff when the candidate is remote
  - name: host.scm.change_history.read
    enables: authoritative material-change enumeration for direct release-candidate readiness
  - name: host.ci.status
    enables: authoritative current required-check verification
  - name: host.scm.policy.read
    enables: authoritative approvals/CODEOWNERS/branch-rule/thread policy evidence
  - name: host.build.provenance.read
    enables: authoritative source-revision to deployable-digest linkage
  - name: host.service.metadata.read
    enables: authoritative criticality/ownership/on-call/recovery-policy metadata
  - name: host.dependency.advisories.read
    enables: current vulnerability/advisory evidence when dependency review applies
  - name: host.runtime.metrics.read
    enables: authoritative current demand/history and capacity evidence
  - name: pr-review.invoke
    enables: exact-head PR/MR code-review evidence refresh
  - name: change-impact-analyzer.invoke
    enables: change-impact prerequisite refresh
  - name: deployment-risk-review.invoke
    enables: deployment-risk prerequisite refresh
  - name: security-review.invoke
    enables: security dimension refresh
  - name: observability-review.invoke
    enables: observability dimension refresh
  - name: resilience-review.invoke
    enables: resilience dimension refresh
  - name: api-design-review.invoke
    enables: API-contract dimension refresh
  - name: database-review.invoke
    enables: database dimension refresh
  - name: performance-review.invoke
    enables: performance dimension refresh
  - name: capacity-planner.invoke
    enables: capacity dimension refresh
  - name: dependency-upgrade-review.invoke
    enables: dependency dimension refresh
```

A fresh compatible gate-trusted child artifact may satisfy a dimension without child invocation capability. Caller/file artifacts remain discovery evidence only.

8.7.1 Exact composition contract

PR D declares static possible invoke targets in skills.yaml; runtime applicability decides which are actually called.

production-readiness-review:

```yaml
install.requires:
  - pr-review
  - change-impact-analyzer
  - deployment-risk-review
  - security-review
  - observability-review
  - resilience-review
  - api-design-review
  - database-review
  - performance-review
  - capacity-planner
  - dependency-upgrade-review

composition:
  mode: invoke
  invokes:
    - pr-review
    - change-impact-analyzer
    - deployment-risk-review
    - security-review
    - observability-review
    - resilience-review
    - api-design-review
    - database-review
    - performance-review
    - capacity-planner
    - dependency-upgrade-review
```

Its composition contract consumes the durable reports it aggregates and also consumes assessment_context when another orchestrator invokes production readiness. Each invoked child must consume assessment_context.

The PR D manifest contract is explicit: production-readiness-review produces production_readiness_report; consumes mr_context, assessment_context, and every child report it may aggregate; consume_fields.assessment_context is exactly [assessment_target, inputs, input_provenance, evidence_refs, unresolved]. The production-readiness payload field list in §8.15 is its full produce_fields set. PR E adds production_readiness_report to release-readiness-checker.consumes with the fields needed for deployable-scope matching and verdict capping.

composition_runtime.handoffs contains one edge per possible child. pr-review uses the existing external [mr_context] carrier that it already consumes. Every other child uses [assessment_context]. The actual handoff envelope still carries reason, evidence_refs, assumptions, unresolved, and execution_context; child-specific specialist fields live under handoff.inputs.assessment_context.inputs.

No generic durable change_context or per-reviewer input artifact is introduced.

Nested-child gate policy

Production readiness is read-only. When it invokes pr-review, the posting gate is deterministically answered Hold — do not post; the child may read/review and emit its trusted machine result but performs no PR/MR comment write. No nested child receives merge/deploy/rollback authority. A child that unexpectedly reaches an interactive mandatory-input gate returns BLOCKED to the parent; the parent converts the affected required dimension to UNKNOWN/PARTIAL rather than interrupting an orchestrated sweep or fabricating input.

8.8 Trusted code-review coverage

Production readiness distinguishes a single PR/MR from an integrated release candidate.

```yaml
code_review_coverage:
  candidate_source_revision: string
  status: COMPLETE|PARTIAL|UNKNOWN
  included_change_refs: list
  trusted_review_refs: list
  uncovered_change_refs: list
  evidence_refs: list
  acquisition: trusted_runtime|authoritative_host
```

Rules:

• for source_type: pr|mr, COMPLETE requires one gate-trusted mr_review_report whose head_sha exactly equals the candidate source revision;
• for source_type: release_candidate, COMPLETE requires authoritative enumeration of every included material change plus trusted review evidence covering each one; an authoritative mr_review_report.integrated_revision may tie a reviewed PR/MR to its merge/squash revision;
• a PR head and integrated revision are never assumed equivalent without authoritative SCM linkage;
• caller-supplied coverage claims cannot set COMPLETE;
• partial/unavailable coverage -> code-review dimension UNKNOWN; any covered report with a blocking FAIL -> NOT_READY.
• authoritative enumeration must include direct commits, cherry-picks and reverts, not only merged PR/MR objects. Any material change that repository policy requires to be reviewed but lacks trusted review evidence makes coverage incomplete/violating according to scm_policy_evidence; it is never silently omitted because no PR object exists.

No new durable artifact type is introduced for this runtime evidence bundle.

8.8.1 Authoritative SCM policy evidence

AI/code-analysis cleanliness is necessary but not sufficient when the repository itself requires approvals, CODEOWNERS, current branches, or unresolved-thread gates.

Runtime evidence:

```yaml
scm_policy_evidence:
  provider: string
  repo: string
  source_revision: string
  required_approvals: integer
  observed_approvals: integer
  codeowners_required: boolean
  codeowners_satisfied: boolean|unknown
  blocking_threads_open: integer|unknown
  branch_current_required: boolean
  branch_current: boolean|not_applicable|unknown
  integration_state: valid|invalid|not_applicable|unknown
  policy_bypass_refs: list
  observed_at: string
  acquisition: authoritative_host|trusted_runtime
  evidence_refs: list
```

Rules:

• required policy comes from authoritative repository/branch rules, not PR prose;
• for open PR/MR candidates, approvals/CODEOWNERS/threads/branch-current/integration-state are evaluated against the exact source_revision;
• for integrated release history, branch-current is not_applicable, but authoritative review/merge policy coverage for included material changes is still required when policy demands it;
• a known policy violation -> code-review/SCM gate FAIL -> readiness NOT_READY;
• missing required policy visibility -> UNKNOWN;
• an explicit administrative bypass is not silently equivalent to satisfaction. If authoritative policy marks the bypass approved/allowed, record it as a condition; otherwise UNKNOWN/FAIL according to the policy evidence.

8.9 Applicability matrix

change_impact_report drives applicability.

|Change class / trigger                              |Required dimension                                                                  |
|------------------------------------------------------|---------------------------------------------------------------------------------------|
|`runtime_code`                                      |security, observability, resilience                                                 |
|`api` trigger                                       |API design review                                                                   |
|`database` trigger                                  |database review                                                                     |
|`security` trigger                                  |security review                                                                     |
|`performance` trigger                               |performance review                                                                  |
|`capacity` trigger                                  |capacity plan/headroom                                                              |
|`observability` trigger                             |observability review                                                                |
|`resilience` trigger                                |resilience review                                                                   |
|`dependency_upgrade` trigger                        |dependency-upgrade review                                                           |
|`k8s_rightsizing` trigger                           |capacity plan/headroom (K8s live rightsizing stays advisory/release-readiness-owned)|
|`docs_only` with no other class                     |all specialist dimensions NOT_APPLICABLE                                            |
|`test_only` with no runtime/config/dependency impact|all specialist dimensions NOT_APPLICABLE                                            |

For schema/data and infra/config changes, the specific triggers generated by change-impact are authoritative; do not infer PASS from lack of invocation.

Direct operational applicability:

|Change class                                   |code review + SCM policy|CI      |ownership                                        |rollback/abort       |post-deploy verification|recovery           |
|-------------------------------------------------|--------------------------|--------|----------------------------------------------------|-----------------------|--------------------------|---------------------|
|docs-only                                      |required                |required|N/A                                              |N/A                  |N/A                     |N/A                |
|test-only, no runtime/config/dependency effect |required                |required|N/A                                              |N/A                  |N/A                     |N/A                |
|build-tooling only, no produced-runtime change |required                |required|N/A unless operator-owned release tooling changes|conditional by impact|conditional by impact   |N/A unless stateful|
|runtime/API/schema/data/infra/config/dependency|required                |required|required                                         |required             |required                |statefulness-driven|

A docs/test-only classification is accepted only when change_impact_report.coverage_status == COMPLETE and no other material class/trigger exists.

8.10 Core operational readiness dimensions

In addition to specialist reviews, runtime-code/release candidates evaluate:

1. code_review — trusted exact-head mr_review_report or authoritative release coverage plus scm_policy_evidence;
2. ci — trusted_ci_evidence;
3. operational_ownership — named owning team/on-call/escalation path;
4. rollback_and_abort — rollback or safe roll-forward strategy plus measurable abort thresholds;
5. post_deploy_verification_plan — smoke/health/SLO signals, observation window, and decision owner after deployment.

Conditional dimension:

6. recovery — required for schema_or_data, stateful runtime changes, or tier0|tier1|unknown; includes backup/restore or reconciliation evidence plus RPO/RTO where applicable.

Missing required operational evidence -> UNKNOWN; proven unsafe/irreversible recovery/rollback -> FAIL. unknown criticality uses the strictest dimension set. These are direct evidence checks owned by production-readiness-review, not new skills.

Operational evidence authority policy

Operational readiness mixes observed facts with declared controls. Do not apply artifact-trust rules blindly to both.

Every direct operational evidence item records:

```yaml
operational_evidence_item:
  dimension: string
  evidence_kind: observed_fact|declared_control
  source_authority: authoritative_host|repository|trusted_runtime|caller
  status: PASS|CONDITIONAL|FAIL|UNKNOWN|NOT_APPLICABLE
  evidence_refs: list
  limitations: list
```

Deterministic policy:

Operational ownership

• PASS: authoritative service/ownership/on-call metadata proves a named owner plus an actionable escalation route.
• CONDITIONAL: caller declares a named owner + escalation route, no authoritative source conflicts, and criticality is tier2|tier3.
• UNKNOWN: caller-only ownership for tier0|tier1|unknown, missing escalation route, or authoritative sources conflict.
• FAIL: authoritative metadata explicitly proves the production path is unowned / has no accountable escalation route.

Rollback and abort
PASS always requires trigger signal/threshold, rollback or safe roll-forward action, accountable actor, bounded decision window, and consistency with migration/deployment evidence. For tier0|tier1|unknown, the mechanism and trigger must be corroborated by repository-controlled deployment/runbook/config evidence or authoritative deployment/observability state; caller prose alone -> UNKNOWN. For tier2|tier3, a complete caller-authored future control can be CONDITIONAL, never PASS, until the mechanism/trigger is corroborated. A proven irreversible unsafe path with no recovery -> FAIL. The plan never grants deploy/rollback authority.

Post-deploy verification plan
PASS requires named health/functional signals, explicit observation window, decision owner, success criteria, abort criteria, and abort/rollback action. Every named signal used for PASS must be proven to exist by repository-controlled observability definitions or authoritative observability/service metadata. For stateful changes include a data-correctness/reconciliation signal. For tier0|tier1|unknown, include user/business success plus errors/latency and dependency/saturation signals when applicable. Caller-only signal names -> UNKNOWN for tier0/tier1/unknown and at most CONDITIONAL for tier2/tier3. monitor normally is always UNKNOWN.

Recovery
Applicability is based on whether the change can mutate/persist state or relies on stateful dependencies; criticality changes evidence strength, not applicability. Stateless changes may be NOT_APPLICABLE when ordinary rollback fully restores the previous state.

For tier0|tier1|unknown stateful paths, PASS requires:

• authoritative backup/restore or reconciliation mechanism;
• authoritative RPO/RTO policy targets;
• dated successful restore/reconciliation exercise satisfying the policy-defined freshness window; and
• no conflicting evidence that the mechanism is invalid for the candidate change.

If the policy does not define required targets/freshness, or the latest exercise cannot be proven current, result is UNKNOWN, not an invented default such as 90 days.

For tier2|tier3 stateful paths, PASS requires a documented mechanism plus dated successful verification and any repository/service policy requirements. Missing date/evidence -> UNKNOWN. A proven destructive path with no viable recovery -> FAIL.

Waivers can document accepted residual risk but never rewrite an UNKNOWN/FAIL operational dimension to PASS or promote the overall verdict to READY.

Production gate evidence-authority matrix

Producer trust is necessary but not sufficient. To count a child result as PASS in production readiness, the decision-supporting provenance must meet these minimums:

|Dimension                                 |Minimum evidence authority for PASS                                                                                                                                                                                  |
|--------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|code review                               |gate-trusted `mr_review_report` tied to authoritative SCM identity; release coverage additionally satisfies authoritative SCM policy                                                                                 |
|change impact                             |exact candidate diff/change enumeration from `authoritative_host` plus repository-backed bounded impact discovery for PR/MR; release change enumeration may be trusted runtime derived from authoritative SCM history|
|deployment risk                           |changed migration/config/release controls grounded in `repository`/`authoritative_host`/validated trusted-runtime sources; caller-only rollback/traffic claims cannot PASS tier0/tier1/unknown                       |
|security, API, DB, performance, resilience|current candidate source/config/spec grounded in `repository` or `authoritative_host` for the exact source revision; caller-only candidate material cannot PASS                                                      |
|observability                             |candidate observability definitions grounded in `repository` and, when claiming existing environment state, environment-matching `authoritative_host` evidence; caller-only material cannot PASS                     |
|capacity                                  |policy in §8.12: authoritative runtime demand/history plus authoritative current baseline for tier0/tier1/unknown                                                                                                    |
|dependency                                |trusted dependency report plus current authoritative advisory evidence or authoritative dependency-security CI coverage; model knowledge alone cannot PASS                                                           |
|operational direct dimensions             |policy in §8.10: authority thresholds vary by criticality, but caller-only controls never PASS tier0/tier1/unknown                                                                                                    |

model_knowledge never independently satisfies a production PASS. caller evidence may supplement/corroborate but cannot override a stricter required source. For tier2/tier3, where a policy explicitly permits caller-authored future controls/projections, the ceiling is CONDITIONAL until corroborated.

Accepted state semantics by readiness dimension

|Dimension/artifact           |Accepted candidate semantic                             |
|------------------------------|------------------------------------------------------------|
|`mr_review_report`           |`current_state`                                         |
|`security_review_report`     |`current_state`                                         |
|`observability_review_report`|`current_state`                                         |
|`resilience_review_report`   |`current_state`                                         |
|`api_design_review_report`   |`current_state`                                         |
|`database_review_report`     |`current_state`                                         |
|`performance_review_report`  |`current_state`                                         |
|`capacity_plan`              |`desired_state` with trusted current-baseline comparison|
|`dependency_upgrade_report`  |`proposed_state`                                        |
|`deployment_risk_report`     |`proposed_state`                                        |
|`change_impact_report`       |`current_state` for PR/MR candidate analysis            |

Any incompatible required semantic -> rerun if possible, otherwise UNKNOWN.

8.11 Evidence-scope matrix

Production-readiness reuse uses three explicit scopes:

|Scope                  |Artifacts/evidence                                                                                                                                 |Required identity                                                                                                                                 |
|--------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------|
|`SOURCE_SCOPED`        |`mr_review_report`, `change_impact_report`, `deployment_risk_report`, security, observability, resilience, API, DB, performance, dependency reviews|canonical repo/service/environment + `assessment_target.head_revision_or_digest == candidate.source_revision`; source-artifact digest when present|
|`PLANNING_BASIS_SCOPED`|`capacity_plan`                                                                                                                                    |repo/service/environment + candidate source revision when repository-bound + exact digest of the demand/horizon/current-baseline input bundle     |
|`DEPLOYABLE_SCOPED`    |final `production_readiness_report`                                                                                                                |`assessment_target.head_revision_or_digest == candidate.head_revision_or_digest`                                                                  |

For a release candidate where deployable digest differs from source revision, build_provenance is the only bridge from source-scoped evidence to the deployable-scoped report.

Environment-sensitivity matrix

Environment matching is deterministic, not “as applicable” prose:

|Dimension                                                                                                                          |Environment rule                                                                                                                                                             |
|--------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|`mr_review`, static security code review, API contract review, static performance review, dependency breaking/API/transitive review|environment may be null when the reviewed behavior is source-identical across environments; if artifact declares a non-null environment it must exactly match candidate      |
|`change_impact`                                                                                                                    |may be environment-null only when no environment-specific config/infra overlay is material; otherwise exact candidate environment is required for `coverage_status: COMPLETE`|
|`resilience`                                                                                                                       |environment-null only for source-defined behavior; runtime/config-driven timeout/retry/breaker behavior requires exact environment                                           |
|`database`                                                                                                                         |source-only schema/migration review may be null; comparison against deployed schema/replication/locking baseline requires exact environment                                  |
|`observability`, `capacity`, `deployment_risk`, ownership, rollback/abort, post-deploy verification, recovery                      |exact non-null candidate environment required                                                                                                                                |
|final `production_readiness_report`                                                                                                |exact candidate environment for release/deployable candidates; a PR/MR with unknown target environment cannot be READY while an environment-sensitive dimension is required  |

prod and production are different unless authoritative metadata provides an explicit alias. Caller text cannot create an alias.

The final result envelope must set:

```text
skill_result.source_revision = candidate.source_revision
production_readiness_report.assessment_target.head_revision_or_digest = candidate.head_revision_or_digest
```

Do not require a source-scoped review’s head to equal an image digest. Do not accept a source review for another source revision merely because the deployable service/environment matches.

8.12 Child evidence collection

Create:

• production-readiness-review/workflow/collect-evidence.md
• production-readiness-review/reference/child-input-map.md

For each child define exact mandatory inputs and sources.

security-review

Inputs:

• current candidate diff/code/config/design target;
• scope hint from impact findings.

If neither supplied artifact nor repository read can provide the target, dimension = UNKNOWN.

observability-review

Inputs:

• service_name;
• observability_material containing at least one metrics/logs/tracing/dashboard/alert/SLO source.

Foundation B2 adds the embedded assessment_context path while preserving this hard stop. Production readiness must supply both mandatory fields; if no material can be assembled, the parent does not invoke the child and records the dimension UNKNOWN. An unexpected incomplete embedded call returns BLOCKED to the parent, never an interactive question.

resilience-review

Inputs:

• current implementation/design behavior for timeouts/retries/failure handling;
• affected dependency paths from impact report.

api-design-review

Inputs:

• current API/event contract;
• previous contract when compatibility is being judged.

database-review

Inputs:

• at least one of schema/migration/queries;
• DB engine if material and not inferable.

performance-review

Inputs:

• changed/current code/query/service content;
• profiling excerpts when available.

capacity-planner

Inputs:

• demand_data;
• forecast_horizon;
• candidate/current baseline when available.

Foundation B2 adds the embedded assessment_context path while preserving the required demand/horizon hard stop. The parent only dispatches with complete mandatory fields; missing demand data or horizon at the parent means readiness dimension UNKNOWN, not a synthetic plan.

Production-readiness authority is stricter than standalone planning:

• tier0|tier1|unknown capacity PASS requires current demand/history from an authoritative runtime/telemetry source plus current configured/observed capacity baseline from authoritative host or version-controlled deployment config; caller-only demand/baseline cannot PASS;
• tier2|tier3 caller-only projections may be CONDITIONAL, not PASS, until corroborated;
• source-specific freshness applies to runtime metrics; absent policy means acquire them in the current invocation or return UNKNOWN;
• a capacity report can be producer-trusted yet still be UNKNOWN for production gating if its decisive inputs have insufficient authority.

dependency-upgrade-review

Inputs:

• dependency name;
• current version;
• target version;
• optional changelog/manifest evidence.

The merged dependency-review leaf has no live advisory lookup and explicitly treats model training-cutoff CVE knowledge as a standing limitation rather than an evidence gap. Therefore its normalized PASS is necessary but not sufficient for a production dependency PASS. When the dependency trigger is applicable, production readiness additionally requires one of:

• current authoritative advisory/vulnerability evidence for the target dependency/revision; or
• an authoritative required dependency-security CI check for the exact source revision whose documented scope covers the changed manifest/lockfile/dependency.

Training/model-knowledge-only CVE evidence -> production dependency dimension UNKNOWN; a proven vulnerable target with no accepted fix/mitigation -> FAIL.

K8s rightsizing boundary

k8s-overprovisioning-datadog is not a production-readiness child in this wave. Its existing contract is a current/live resource-optimization decision graph and does not expose a candidate-specific PASS/FAIL machine verdict. change-impact-analyzer may still emit k8s_rightsizing as a recommendation trigger, and release-readiness-checker keeps its existing per-service K8s signal. Pre-release resource changes make the capacity dimension required.

8.12.1 Final freshness fence

Readiness snapshots are invalid if the candidate moves while children are running. Immediately before rendering the final report:

1. re-read authoritative candidate identity;
2. re-read required CI/check conclusions for the exact source revision;
3. re-read SCM policy state that can change after review (approvals, blocking threads, branch-current/integration state);
4. verify every trusted child artifact still matches the original source/planning/deployable scope;
5. for mutable release references, require they were resolved to an immutable source SHA/digest at start and still resolve consistently.

If a PR/MR head changed, a required approval was dismissed, a blocking thread appeared, CI changed, or a mutable reference resolves differently, do not combine old and new evidence. Return readiness UNKNOWN / skill_result: PARTIAL with candidate_changed_during_review; no unbounded automatic restart. The caller may rerun against the new immutable identity.

8.13 Reuse-before-rerun rule

For each applicable dimension:

1. validate supplied/existing artifact schema;
2. classify trust using §3.8; untrusted artifacts cannot satisfy a PASS gate;
3. validate identity using the §8.11 evidence-scope matrix;
4. validate state semantic against the §8.10 per-dimension table;
5. validate freshness;
6. if trusted and reusable, consume it;
7. otherwise invoke child if capability and mandatory inputs are available;
8. otherwise mark dimension UNKNOWN/BLOCKED according to whether the missing evidence is required.

Never invoke a child with known-missing mandatory inputs merely to obtain a predictable BLOCKED response.

8.14 Orchestration budget and partial failure

• each prerequisite/specialist dimension may be dispatched at most once per production-readiness invocation;
• reuse is attempted before dispatch;
• run at most four independent children concurrently when the host supports parallelism;
• child timeout/FAILED/BLOCKED becomes that required dimension UNKNOWN unless a separate trusted FAIL already exists;
• do not retry automatically inside the same invocation;
• aggregation order is fixed by dimension name, never child completion order;
• budget exhaustion preserves completed evidence and returns UNKNOWN for unexecuted required dimensions rather than silently reducing scope.

8.15 production_readiness_report v1

State semantic: current_state.

```yaml
production_readiness_report:
  title: string
  assessment_target: mapping
  source_revision: string
  build_provenance_ref: string  # `NOT_APPLICABLE` when source revision itself is the deployable
  criticality: string
  verdict: string
  dimension_statuses: list
  operational_evidence: mapping
  blockers: list
  conditions: list
  waivers: list
  required_actions: list
  evidence_refs: list
```

Verdict vocabulary:

```text
READY
CONDITIONAL
NOT_READY
UNKNOWN
```

Each dimension record:

```yaml
dimension: string
applicability: REQUIRED|NOT_APPLICABLE
status: PASS|CONDITIONAL|FAIL|UNKNOWN|NOT_APPLICABLE
artifact_ref: string|null
evidence_refs: list
reason: string
```

8.16 Verdict precedence

Worst-first:

1. any required dimension FAIL -> NOT_READY;
2. mr_review_report FAIL or required CI failed -> NOT_READY;
3. deployment risk Critical -> NOT_READY;
4. any required dimension UNKNOWN, stale required artifact, missing required CI visibility, or insufficient deployment-risk confidence -> UNKNOWN;
5. any required dimension CONDITIONAL or deployment risk High with HIGH/MEDIUM confidence and explicit mitigations -> CONDITIONAL;
6. otherwise -> READY.

NOT_APPLICABLE never counts as PASS; it is simply excluded from required-dimension aggregation.

8.17 Waivers

A waiver cannot turn a FAIL into PASS silently.

A waiver record must include:

```yaml
dimension: string
accepted_by: string
reason: string
evidence_ref: string
expires_at: string|null
```

The skill itself cannot invent accepted_by. Without explicit accountable-human acceptance, the waiver is not valid. A valid waiver is informational/accountability metadata: it never converts FAIL or UNKNOWN to PASS and never promotes NOT_READY/UNKNOWN to READY.

────────

9. Release-readiness integration

Release manifest v1 behavior remains unchanged.

Manifest v2 adds enough identity to either reuse or safely invoke production readiness:

```yaml
repo: string
service: string
environment: string|null
since: string
source_revision: string|null
release_ref: string|null
criticality: tier0|tier1|tier2|tier3|unknown|null
production_readiness_required: boolean
production_readiness_ref: string|null
```

release_ref is the immutable deployable ref (commit SHA when that is the deployable, otherwise image/artifact digest). source_revision is the source commit used to build it.

9.1 Backward compatibility

A v1 entry with only {repo, service, since, release_ref?} behaves exactly as today.

For v2 with production_readiness_required: true:

1. reuse a trusted, fresh, deployable-scoped production_readiness_report when available;
2. otherwise, if production-readiness-review.invoke is available and candidate identity can be established, invoke it in the same trusted runtime context;
3. otherwise release readiness is UNKNOWN.

Caller/file reports remain untrusted discovery evidence. Conditional invocation solves the cross-invocation trust problem without adding a generic artifact store.

9.2 Inputs supplied to conditional production-readiness invocation

Release readiness passes:

• candidate repo/service/environment;
• source_revision;
• head_revision_or_digest = release_ref;
• criticality when authoritative/known;
• release base/since context for impact discovery;
• trusted code-review coverage it already assembled from authoritative SCM + pr-review;
• rollback/traffic/release context when available;
• trusted build provenance when deployable ref differs from source revision.

production-readiness-review then reuses or refreshes impact/deployment/specialist evidence under its own contract.

If source_revision is absent for a non-source deployable digest and cannot be authoritatively resolved, do not invoke; release readiness is UNKNOWN.

9.3 Composition/recursion safety

PR E adds optional production-readiness-review.invoke and a true composition handoff from release-readiness-checker. It does not add production-readiness-review to release-readiness-checker.install.requires: the registry parser permits an explicit optional composition.invokes target independently of mandatory install requirements. This preserves the v1 mandatory installation footprint. For a v2 entry, absence of the separately available invoke capability/result yields UNKNOWN, never an implicit install or fabricated PASS.

Depth:

```text
release-readiness-checker (root)
  -> production-readiness-review (depth 1)
     -> prerequisite/specialist leaf (depth 2)
```

This remains inside default maximum depth 3.

There is no reverse invoke edge from production readiness to release readiness. Leaf escalation recommendations are not automatic recursion.

9.4 Matching

A reused production-readiness report must match:

• canonical repo;
• service;
• environment when supplied;
• assessment_target.head_revision_or_digest == release_ref;
• payload/result source_revision == manifest.source_revision when source revision is present.

9.5 Release verdict mapping

• production readiness NOT_READY -> release NOT_READY;
• a release verdict may remain NOT_READY because of a proven blocker while another required release dimension is UNKNOWN; in that case the release envelope status is PARTIAL, not SUCCESS, because the assessment is incomplete;
• production readiness UNKNOWN -> release UNKNOWN;
• production readiness CONDITIONAL -> release at most CONDITIONAL;
• production readiness READY -> continue existing release checks;
• required report absent/stale and invoke unavailable/unsafe -> release UNKNOWN.

Existing PR-review/K8s/incident checks remain intact.

Version ownership for PR D/E is defined once in §3.10; do not create a second independent version decision here.

10. Routing boundaries

Add explicit routes/collisions.

|Intent                                              |Owner                                                          |
|-------------------------------------------------------|------------------------------------------------------------------|
|PRD/product requirements                            |`prd-architect`                                                |
|implementation-oriented design from PRD             |`system-design`                                                |
|review an existing proposed design/ADR              |`architecture-review`                                          |
|affected services/contracts/data/tests/owners       |`change-impact-analyzer`                                       |
|resilience/failure-mode review outside live incident|`resilience-review`                                            |
|implementation task decomposition/DAG               |`implementation-planner`                                       |
|execute implementation                              |`loop-task-implementer`                                        |
|generic code review of one specific PR/MR           |`pr-review`                                                    |
|one change’s rollout/blast-radius/rollback risk     |`deployment-risk-review`                                       |
|exact candidate production readiness                |`production-readiness-review`, including numbered PR/MR targets|
|release-manifest go/no-go                           |`release-readiness-checker`                                    |
|live incident                                       |`incident-rca`                                                 |
|current K8s rightsizing                             |`k8s-overprovisioning-datadog`                                 |
|future demand/headroom forecast                     |`capacity-planner`                                             |

Mandatory collision evals:

1. PRD vs system design.
2. system design vs architecture review.
3. architecture review vs domain comprehension.
4. change impact vs deployment risk.
5. change impact vs PR review when PR number is present.
6. resilience review vs incident RCA.
7. resilience review vs capacity planning.
8. implementation planner vs loop-task implementer.
9. production readiness vs deployment risk.
10. production readiness vs release readiness.
11. production readiness vs PR review when PR number is present.
12. capacity planning vs K8s rightsizing.
13. database review vs MySQL-to-Postgres rewrite.
14. observability review vs incident RCA.
15. security review vs PR review security persona.

────────

11. Composition-runtime rules

Only actual dispatcher/orchestrator calls belong in contracts.composition_runtime.handoffs.

Foundation A/B1/B2

Do not encode ordinary leaf recommendations as mandatory runtime handoffs.

PR A/B

change-impact-analyzer and resilience-review remain leaves; no mandatory child handoffs.

PR C — Implementation planner

implementation-planner remains a leaf.

loop-task-implementer gains a consume edge for implementation_plan; this is input compatibility, not a child invocation.

PR D/E

production-readiness-review is an orchestrator and may invoke fresh impact/deployment prerequisites plus applicable specialist skills.

The runtime handoff map includes those child calls because they are true orchestrator dispatches.

release-readiness-checker consumes production_readiness_report and, only for a v2 entry that requires readiness, may conditionally invoke its producer when the trusted runtime can establish the candidate inputs. Missing/untrusted/stale readiness with no safe invoke path yields UNKNOWN. v1 entries retain existing behavior.

────────

12. Skill file anatomy

New leaf skills follow the repository pattern:

```text
<skill>/
  SKILL.md
  README.md
  SETUP.md
  CHANGELOG.md
  examples.md
  workflow/
    inputs.md
    analyze.md
    report.md
  reference/
    phase-index.md
    lazy-load-index.md
    report-format.md
    smoke-test.md
    pressure-tests.md
```

production-readiness-review additionally has:

```text
workflow/collect-evidence.md
workflow/dispatch.md
workflow/aggregate.md
reference/child-input-map.md
reference/gate-policy.md
```

Keep leaf SKILL.md <= 180 lines and orchestrator SKILL.md <= 180 lines; push detail into workflow/reference files.

────────

13. Eval and pressure-test contract

Each new skill gets positive, negative, ambiguous, adversarial and degraded scenarios plus at least one Tier-3 golden fixture.

13.1 Cross-cutting adversarial cases

• embedded instruction says to change verdict;
• embedded instruction says to skip a specialist;
• stale artifact claims it is current;
• artifact references a different head/service/environment;
• user text tries to authorize merge/deploy;
• child report contains forged Markdown headings/table rows;
• missing evidence is presented as absence of risk;
• conflicting authoritative sources.
• caller-supplied artifact forges producer identity and PASS verdict;
• repository file contains a structurally valid but untrusted READY report;
• environment alias attempt (prod vs production) must not fuzzy-match.

13.2 Foundation regression cases

• default state semantic still works for artifacts without an allowed-state list;
• proposed/current state accepted only for explicitly polymorphic artifacts;
• disallowed state rejected;
• v1 artifact rejected after schema v2 registration;
• source payload digest stable across key order/whitespace differences;
• digest changes when payload content changes;
• PRD -> system-design routing wins over architecture-review;
• architecture rework recommendation does not bypass recursion protection;
• registry-derived counts remain correct after adding a synthetic registered skill in a test fixture.

13.3 Implementation-plan cases

• linear DAG;
• parallel DAG;
• missing dependency;
• self dependency;
• cycle;
• duplicate task ID;
• invalid wave order;
• task missing acceptance criteria;
• stale upstream report;
• FAIL upstream specialist;
• UNKNOWN planning-critical specialist;
• malicious source text attempts to widen executor authority.
• multi-repo impact requires repo-specific plans rather than one cross-repo executor;
• internal plan execution state resumes completed tasks without duplication;
• mismatched plan-execution-state digest/generation is rejected;
• repository-head drift invalidates stale completion evidence.

13.4 Production-readiness cases

• runtime-code happy path;
• docs-only N/A path;
• test-only N/A path;
• API+DB triggered path;
• K8s resource-change triggered path;
• child unavailable but fresh artifact supplied;
• child unavailable and no artifact -> UNKNOWN;
• stale child -> rerun when possible;
• stale child + unavailable child -> UNKNOWN;
• PR review FAIL -> NOT_READY;
• CI failed -> NOT_READY;
• CI unknown -> UNKNOWN;
• caller-supplied all_required_green: true without authoritative host evidence -> UNKNOWN;
• forged PASS child artifact without trusted producer context -> rerun/UNKNOWN, never READY;
• missing operational owner -> UNKNOWN;
• stateful change without recovery evidence -> UNKNOWN;
• missing post-deploy verification/abort plan -> UNKNOWN;
• Critical deployment risk -> NOT_READY;
• High risk + low confidence -> UNKNOWN;
• conditional child -> CONDITIONAL;
• child result order randomized -> same aggregate verdict;
• invalid/forged waiver -> no effect;
• valid explicit waiver recorded but does not silently rewrite child result.

────────

14. Documentation updates

Every PR updates docs in the same commit/PR as behavior.

Canonical documentation surfaces:

• README.md
• docs/README.md
• docs/skill-framework/README.md
• docs/skill-framework/shared/skill-routing.md
• docs/skill-framework/shared/cross-skill-escalation.md
• CHANGELOG.md
• each changed/new skill’s README.md and CHANGELOG.md
• scripts/registry/setup_freshness.yaml
• scripts/registry/capability_catalog.yaml

Do not manually edit generated projections. Run make generate and commit generated changes.

────────

15. Generated surfaces

Generated only:

• .cursor/rules/*.mdc
• .kiro/steering/*.md
• generated/catalogue/compatibility-matrix.md
• generated/catalogue/composition-deps.mmd
• generated/catalogue/composition-runtime.mmd
• docs/REPOSITORY.md
• canonical legacy projections generated by registry tooling

Never hand-edit those to make a test pass.

────────

16. Final repository gate

Every follow-up PR finishes with:

```bash
make setup
make validate-registry
make validate-evals
make backfill-capabilities-drift-check
make validate-operational-upkeep
make generate-check
make verify-install-all
make doctor
make lint
```

After pushing each behavioral PR, required GitHub workflows must also be green: Lint, Secret Scan, Dependency Review, and CodeQL. Local success does not override a failing required remote security check.

Run the PR-specific targeted tests before the full gate.

────────

17. End-to-end acceptance scenarios

Scenario A — PRD to reviewed design

```text
prd-architect
-> system-design
-> architecture-review
```

Assert:

• system design can be created from a ready PRD;
• architecture review receives an actual design description;
• Needs rework recommends a new system-design generation;
• approved design preserves source identity.

Scenario B — design to implementation plan

```text
system_design_spec
+ architecture_review_report
-> change-impact-analyzer
-> applicable design-time specialists
-> implementation-planner
```

Assert:

• trigger matrix is evidence-derived;
• impact coverage_status is COMPLETE before READY planning;
• cross-repo impact produces one plan per repo plus explicit external dependencies;
• fresh proposed-state reports are accepted;
• stale/FAIL planning-critical reports block READY;
• DAG/waves are deterministic and valid.

Scenario C — plan execution

```text
implementation_plan
-> loop-task-implementer
```

Assert:

• legacy implementation_task path remains unchanged;
• earliest dependency-satisfied task is selected;
• internal plan_execution_state is resume-safe and never appears in skill_result.artifacts;
• plan-digest mismatch/head drift forces revalidation;
• actual/estimated task size respects loop-task circuit breakers;
• any explicit test-writer repository write invalidates prior review/CI evidence and forces revalidation;
• existing builder/reviewer/CI gates are unchanged;
• plan is not mutated.

Scenario D — current candidate production readiness

```text
pr-review
-> change-impact-analyzer
-> deployment-risk-review
-> production-readiness-review
```

Assert:

• exact candidate identity matches all reused artifacts;
• required CI is authoritative and current for the exact source revision;
• build provenance links source revision to deployable digest when they differ;
• caller/file-supplied PASS artifacts cannot satisfy gates without trusted provenance;
• applicable specialists use the per-dimension state-semantic policy;
• ownership, rollback/abort, post-deploy verification plan, and conditional recovery are evaluated;
• N/A dimensions are explicit;
• aggregate verdict follows fixed precedence.

Scenario E — release

```text
release-readiness-checker
  -> reuse trusted production_readiness_report
  OR
  -> production-readiness-review (v2 required entry only, when safe invoke inputs/capability exist)
```

Assert:

• v1 release manifests behave exactly as before and never invoke production readiness;
• v2 required readiness reuses a trusted fresh deployable-scoped report when available;
• otherwise v2 conditionally invokes production readiness in the same trusted runtime when candidate identity/coverage inputs are sufficient;
• missing/untrusted/stale readiness with no safe invoke path becomes UNKNOWN;
• NOT_READY cannot become READY;
• UNKNOWN cannot become READY;
• source revision, build provenance, environment, and release-ref mismatches are rejected;
• composition depth remains within the recursion guard and no reverse cycle exists.

────────

18. Explicit non-goals

Do not add in this wave:

• another architecture reviewer;
• another system/technical design writer;
• another security/database/performance/capacity/observability/dependency reviewer;
• a second deployment-risk skill;
• a global mega-orchestrator for the entire delivery chain;
• artifact v1 upcasting/migration framework;
• any production-readiness invocation for v1 release manifests; only v2 entries that explicitly require it may use the conditional invoke path;
• automatic post-deploy execution/monitoring; this wave requires a post-deploy verification plan and abort thresholds, but does not deploy or monitor production;
• chaos testing planner;
• DR reviewer;
• SLO authoring skill;
• Kafka-specific reviewer;
• provider-specific capabilities without a concrete acceptance-test need.

────────

19. Completion checklist

Foundation A — lifecycle/runtime primitives

☐ Live-baseline drift preflight runs before implementation.
☐ Correct PRD -> system-design -> architecture-review routing.
☐ allowed_state_semantics implemented without changing the global state vocabulary.
☐ Runtime contract text updated to allow a finite per-artifact allowed set while every individual result still emits one semantic.
☐ Canonical assessment-target identity/digest helpers implemented and tested.
☐ Artifact trust classification is runtime/context-owned, not self-asserted.
☐ Registry/scenario counts derive from the canonical registry where the exact number is not itself the contract.
☐ Security-scanner-safe fixture policy documented.
☐ Foundation A stays within review-size guard or is split before implementation.

Foundation B1/B2 — schema-v2 producer migration

☐ All 12 delivery-chain artifacts in scope are strict schema v2: prd_report plus the 11 PR #159 design/review artifacts.
☐ mr_review_report exposes machine blocking/clean status and authoritative integrated revision when known.
☐ Common findings / conditions / required_actions item schemas are deeply validated.
☐ prd_report v2 requires source_type: prd and a non-null digest of the complete Final PRD; system-design rejects a missing/mismatched full PRD body/ref.
☐ system_design_spec v2 requires source_type: system_design and a non-null digest of the complete design; architecture-review rejects a missing/mismatched full design body/ref.
☐ Contradictory immutable semantic-document refs remain a hard mismatch even when document digests are equal.
☐ Producer-side normalized-decision derivation distinguishes proven defects from evidence gaps.
☐ All affected producers and delegates emit the complete v2 shape.
☐ Every existing consumer has a v2 regression test; no consumer parses Markdown.
☐ v1 machine artifacts fail with a clear regenerate-current-artifact error.
☐ Producer versions/changelogs follow the §3.10 per-PR version ledger.
☐ B1 and B2 each stay within the review-size guard without a behavioral-review exception.

PR A — Change impact

☐ change-impact-analyzer v1 is a leaf.
☐ change_impact_report v1 has coverage status, material unknowns, impacted repositories, criticality, classes/triggers/tests/owners.
☐ PR/MR COMPLETE requires exact base/head repository-backed bounded discovery.
☐ Trigger matrix includes API/DB/security/performance/capacity/observability/resilience/dependency/K8s-rightsizing.
☐ No child *.invoke capabilities are added to the leaf.
☐ PR/MR routing is intent-based: generic review -> pr-review; change-impact/deployment-risk/readiness -> their explicit owners.
☐ PR-aware intent owners consume mr_context when available and use exact-head SCM retrieval; remote target without retrievable diff fails closed.

PR B — Resilience

☐ resilience-review v1 is a leaf with proposed/current allowed semantics.
☐ Timeouts/retries/backpressure/circuit-breaking/idempotency/queue/recovery/partial-failure dimensions are explicit.
☐ system-design may recommend resilience review when triggered.
☐ deployment-risk-review may consume fresh trusted change-impact evidence without requiring it for legacy standalone use.
☐ No mandatory leaf-to-leaf orchestration/cycle is introduced.

PR C — Implementation planner

☐ implementation-planner v1 and implementation_plan v1 are registered.
☐ Plan has deterministic plan_set_id/plan_id; it is single-repo and cross-repo dependencies are explicit.
☐ Cross-repository plan-set cycles are rejected when provable; unavailable sibling plans stay unresolved.
☐ Remote resume collisions use deterministic execution identity, expected-head/fast-forward writes, and cannot create a random duplicate task branch/PR; cross-process exactly-once local Builder dispatch is explicitly out of scope without a lease.
☐ tasks[].dependencies is the only internal DAG.
☐ Deterministic execution waves and size compatibility are validated.
☐ Every required upstream condition/action/test is mapped through traceability.
☐ Internal plan_execution_state supports generation-checked, SCM-reconciled resume and is not a durable artifact.
☐ An already-active deterministic branch/PR is reconciled or blocks; no second remote execution branch/PR is created.
☐ Legacy implementation_task behavior remains unchanged.
☐ loop-task-implementer version bump is explicit and its existing builder/reviewer/CI/merge gates are unchanged.

PR D — Production readiness

☐ production-readiness-review v1 is a read-only orchestrator.
☐ Fresh trusted impact/deployment prerequisites are reused or refreshed once through their leaf producers.
☐ Evidence scope distinguishes source revision, capacity planning basis, and deployable target.
☐ Trusted build provenance links source revision to deployable digest when they differ.
☐ Trusted exact-source code review + authoritative CI gate readiness.
☐ Child-input adapters are non-interactive and never dispatch knowingly incomplete mandatory input.
☐ Operational ownership, rollback/abort, post-deploy verification plan, and conditional recovery are machine-gated.
☐ Resource-sizing changes require capacity review; K8s rightsizing is not reinterpreted as a candidate PASS/FAIL.
☐ Fan-out is bounded, reuse-first, one dispatch per dimension, deterministic under partial failure.
☐ Caller/file PASS/READY artifacts cannot promote a gate without trusted provenance.
☐ Nested pr-review is always no-post and cannot widen action authority.
☐ Policy-required build attestation/SBOM/provenance controls are enforced without becoming global defaults.
☐ Context acquisition trust prevents forged assessment_context.input_provenance labels from laundering caller evidence.
☐ Dependency/current-advisory and capacity authority gates enforce current production evidence.
☐ Environment-sensitive dimensions exact-match the target environment.

PR E — Release integration

☐ Release manifest v1 remains byte/behavior compatible.
☐ Manifest v2 carries source revision, deployable ref, environment, criticality, and readiness requirement/ref.
☐ Trusted deployable-scoped production readiness is reused first.
☐ Missing/stale v2-required readiness conditionally invokes production readiness only with sufficient trusted candidate context.
☐ Unsafe/unavailable conditional invocation yields UNKNOWN, never a skipped gate.
☐ Release -> production -> leaf depth is within recursion limit and no reverse invoke edge exists.
☐ Release verdict caps preserve NOT_READY/UNKNOWN/CONDITIONAL.
☐ Automated end-to-end lifecycle contract test covers v1 and v2 paths.

Final

☐ All routing collision evals pass.
☐ All four new skills have five scenario dimensions and Tier-3 golden coverage.
☐ New committed adversarial fixtures are Secret-Scan-safe.
☐ Generated files match canonical sources.
☐ Install-all works for every registered skill without hard-coded total.
☐ Full local repository gate passes.
☐ Required remote workflows are green: Lint, Secret Scan, Dependency Review, CodeQL.
☐ Independent final review finds zero P0/P1 findings and no unresolved P2 that materially changes implementation architecture.

20. Final recommendation

Use this document as the architecture/design source of truth. Do not implement directly from any superseded v2–v9 plan.

Execution-package rule

The v10 design and implementation plans are a reviewed execution bundle and do not need to be committed into a behavioral PR merely to make their references resolvable. Each implementation plan references this design as a sibling artifact and records its SHA-256 digest. At execution time, supply the plan and this exact design artifact together; if the digest differs, stop and re-review before implementation. Repository docs/changelogs required by the product changes are still updated by their owning tasks. Archiving the planning bundle in-repo, if desired by maintainers, is a separate docs-only action and is not a prerequisite for Foundation A.

The missing capability surface is still exactly four skills. v10 additionally closes producer-vs-evidence trust, context-trust laundering, source/deployable provenance, bounded resume/concurrency, impact completeness, cross-repo, operational-readiness, current dependency-advisory, capacity-authority, environment-sensitivity, fixture-security, and merged-main baseline gaps without adding a fifth skill. The important revision is architectural: first make PR #159’s reports safely composable, then add impact/resilience, then planning, then production readiness.

The companion implementation plans break that work into independently testable PRs with TDD steps and exact repository paths.
