# AI Skills Platform — Evolution Strategy (12–24 Months)

**Date:** 2026-07-02
**Status:** Approved design (brainstorming output)
**Scope:** This repository — the four shipped skills (`pr-review`, `incident-rca`, `k8s-overprovisioning-datadog`, `domain-comprehension`) and the shared `docs/skill-framework/` layer.
**Context:** Solo builder, 10–50 active users and growing, Cursor-only harness, GitLab (self-hosted) + Jenkins + Jira + Datadog + KubeSense stack. Output serves both the working backlog and a leadership-facing strategy narrative.

---

## 1. Maturity assessment

Grounded scorecard. Each score reflects what is actually in the repo today, not intent.

| Dimension | Score | Evidence |
|-----------|-------|----------|
| Skill engineering | 4/5 | Phase-per-file workflows, lazy-load indexes, phase exit criteria, line-limit lint, per-skill pytest |
| Evidence discipline | 4/5 | Evidence hierarchies, confidence caps, "no defensible root cause" policy, UNKNOWN-over-speculation, trap-aware red-flag lists |
| Artifact rigor | 4/5 | Typed validated artifacts: causal graph v1 (CG-01–08), decision graph v3 (INV-01–12), `manifest.yaml` + validator |
| Behavioral evaluation | 1/5 | Lint validates artifact *shape*; nothing validates *conclusions*. No golden cases, no replay, no regression suite |
| Telemetry / adoption measurement | 0/5 | `review-metadata-schema.md` defines footers; no collection destination exists |
| Distribution | 1/5 | Copy to `~/.cursor/skills/` + restart; no version pinning, no rollback, no update channel |
| Workflow orchestration | 2/5 | Symmetric escalation matrix exists; all hops are manual, no typed handoff inputs |
| Action capability | 0/5 | All skills stop at a report (pr-review comment posting is the one confirmed-write precedent) |

**Verdict: advanced prototype, pre-platform.** The reasoning and evidence rigor are ahead of most industry AI-tooling efforts, including commercial ones. The operational infrastructure around that rigor — evals, telemetry, distribution — is behind, and that is what breaks first as usage grows.

Leadership framing: the hard part (making AI conclusions trustworthy) is largely solved here; the remaining work is conventional platform engineering to make that trust durable at scale.

---

## 2. Panel challenges — five contrarian theses

### T1. "More skills" is the wrong goal

The instinct at this stage is to grow the catalog toward 15–20 skills. The panel rejects this. A solo builder with four deep skills (~100+ workflow/reference files) is already at maintenance capacity; every new skill adds a permanent tax of drift, calibration, and doc upkeep. The right goal is to **drop the marginal cost of skill #5 before building it** — extract the shared runtime (evidence collectors, validators, report gates) so a new skill is a thin domain layer rather than 30 new files.

- **Why it matters:** skill velocity is capped by maintenance load, not authoring speed.
- **Impact:** roughly 3× faster skill delivery once landed; prevents quality collapse.
- **Effort:** medium (extraction of already-similar code and docs).
- **Risk:** premature abstraction. Mitigation: extract only what is duplicated three or more times today.
- **Horizon:** next quarter.

### T2. An eval harness beats every new feature

At 10–50 users, one confidently-wrong RCA presented to leadership destroys more trust than ten good ones earn. The repo has validators for artifact shape and zero tests for conclusions. A golden-case suite — 5–10 past incidents with known root causes, a set of MRs with known findings, replayed and scored per release — is the single highest-leverage investment available. It also unlocks safe prompt refactoring: today every `SKILL.md` edit is an untested behavior change shipped to all users.

- **Impact:** protects the platform's core asset (trust); enables everything in Sections 4–5.
- **Effort:** medium; the raw cases already exist in incident and MR history.
- **Quick win:** the first three golden cases and a manual replay checklist, inside two weeks.

### T3. Distribution is the silent platform-killer

Copy-to-`~/.cursor/skills` means no version pinning, no rollback, no forced update, and no knowledge of who runs what. At 50 users, "the skill misbehaved" reports will arrive against unknown stale versions and be undebuggable. Fix: versioned releases (git tags), `skill_version` surfaced in every report footer, install script that checks and updates, one announce channel for releases.

- **Effort:** low. **Quick win:** yes — this is the cheapest item with platform-level payoff.

### T4. The read-only ceiling

All four skills stop at a report. The panel split on whether to add write capability; the consensus position: keep analysis read-only, add **draft-action outputs** with human approval — RCA drafts preventive-action Jira tickets, the k8s skill drafts a manifest-change MR the user reviews and merges. The confirmed-write pattern is already proven in pr-review Phase 3 posting; extend it, do not invent a new one.

- **Impact:** converts reports into closed loops; the value ceiling lifts materially.
- **Effort:** low–medium per skill. **Risk:** scope creep into automation; the approval gate is non-negotiable.

### T5. The moat is the evidence discipline, not the skills

Cursor, Copilot, and Devin will commoditize generic "review a PR" and "explain this code." They will not have: the acme-specific evidence hierarchy, KubeSense-primary log routing, calibrated confidence caps, the cross-skill escalation matrix, or a golden corpus of this organization's incidents. Strategy: double down on the org-specific evidence layer and the eval corpus; never compete on generic capability.

---

## 3. Gap analysis → next skills

Selection filter: reuses existing MCPs/collectors, high usage frequency, output fits the evidence-scored framework. In priority order:

| # | Skill | Why | Reuse | Horizon |
|---|-------|-----|-------|---------|
| 1 | **release-readiness / deployment-risk** (one skill, two modes) | Pre-deploy GO/NO-GO gate: diff + recent incidents + k8s state + Jira acceptance criteria. Completes the incident loop (pr-review → release-readiness → incident-rca) | ~80% of existing GitLab/Datadog/Jira collectors | Next quarter |
| 2 | **datadog-monitor-audit** | Alert quality: noisy, dead, and missing monitors scored against incident history; feeds the RCA detection-analysis section | Datadog MCP, incident corpus | Next quarter |
| 3 | **tech-debt / hotspot-map** | Churn × complexity × incident-linkage per repo; leadership-facing like the domain exec summary | domain-comprehension artifacts, GitLab MCP | 12 months |
| 4 | **onboarding-copilot** | Q&A over generated domain-comprehension deliverables; near-zero new collection, high visibility | domain corpus | 12 months |

**Deliberately deferred** (candidates, not roadmap): AWS cost beyond k8s, Java/SDK upgrade, security review, API governance, capacity planning, data engineering. Each requires new collectors or a new domain corpus — wrong sequencing before T1/T2 land.

---

## 4. Multi-agent workflows

The escalation matrix already defines the hops; today every hop is manual. Evolve in three stages:

**Stage 1 (now): typed handoff artifacts.** Each skill already emits a validated artifact. Define the handoff contract: skill B accepts skill A's artifact as an input anchor. Example: an incident-rca causal graph node of type `deploy_regression` hands pr-review the MR ID plus a failing-path hint, skipping discovery. Cheap — schema work only.

**Stage 2 (quarter → 12 months): orchestrated chains.** The three highest-value chains:

1. **Incident loop:** incident-rca → pr-review on the causative MR → draft preventive Jira tickets → release-readiness check on the fix MR.
2. **Efficiency loop:** k8s-overprovisioning → draft manifest MR → automated 7-day post-change verification re-run (the re-run offer already exists in the skill; automate it).
3. **Comprehension loop:** domain-comprehension → onboarding-copilot → tech-debt hotspots. One corpus, three consumers.

**Stage 3 (12 months+): event-triggered headless runs.** GitLab webhook triggers pr-review on MR open; a Datadog alert triggers RCA evidence pre-collection so the bundle is ready before a human asks. **Hard dependency: the eval harness (T2) must exist first** — unattended runs without behavioral tests are an incident generator.

---

## 5. Platform architecture

Target: **shared runtime + thin skills.** Extract from the four existing skills:

| Component | Today | Target |
|-----------|-------|--------|
| Evidence collectors | Query recipes duplicated per skill (`query-playbook.md`, `queries.md`) | One shared collectors library with per-skill deltas (the skill-framework already proves this pattern for conventions) |
| Validators | CG, INV, and manifest validators share the same shape (schema + invariants + pytest) | Generalized `validate_artifact` runner + per-skill invariant configs |
| Telemetry sink | Metadata footers defined, no destination | Simplest viable: runs-log appended to a GitLab repo or Confluence page; queryable, no new infra |
| Corpus store | Artifacts scattered per run | Versioned repo directory of golden cases + generated artifacts; feeds evals and the onboarding copilot |

**Explicitly rejected:** a central reasoning engine, a knowledge-graph service, a custom agent framework. Each is infrastructure a solo builder would maintain alone, and Cursor already provides the runtime. Markdown + scripts + MCP is the scale-appropriate architecture for the next 12 months.

---

## 6. Governance and reliability

Gaps in priority order:

1. **Behavioral regression suite** (T2): golden cases replayed per release; scored on conclusion match, evidence-citation validity, and confidence calibration.
2. **Prompt versioning discipline:** `workflow_version` frontmatter exists; add a CHANGELOG gate and surface the version in every report footer so users report bugs against a known version.
3. **Confidence calibration audit:** periodically sample HIGH-confidence conclusions and check ground truth. A HIGH that is wrong 30% of the time means the framework is miscalibrated, and that must be caught by process, not by embarrassment.
4. **Cost visibility:** lazy-loading controls tokens per run but nothing measures it. Add token/runtime estimates to the metadata footer.
5. **Hallucination containment:** already strong (evidence caps, UNKNOWN policy). Extend with **trap cases** in the eval suite — scenarios with deliberately insufficient evidence where the passing answer is UNKNOWN.

---

## 7. Distribution and developer experience

1. **Versioned releases** (T3): git tags, install-script pinning and update, version in report footers. Immediate.
2. **Update notification:** CI or the install script posts "skill vX released" with the CHANGELOG delta to the team channel.
3. **Feedback capture:** a one-line thumbs-down-plus-reason mechanism that lands in repo issues. At 50 users this becomes the eval-case pipeline — every bad run is a future golden case.
4. **Skill discovery:** users know pr-review and little else. The escalation matrix already suggests cross-skill hops; add a "related skills" footer and a short internal demo doc per skill.
5. **Onboarding path:** a new engineer runs the onboarding copilot on day one. This converts the platform's identity from "reviewer tools" to "the org default way to ask engineering questions."

---

## 8. Scale path

**→ 50 engineers (now–6 months).** Bottlenecks: trust and version drift. Required: versioned distribution, telemetry sink, eval suite v1. No organizational changes needed.

**→ 200 engineers (6–18 months).** The solo-builder model breaks here. Required: 2–3 volunteer skill maintainers by domain (SRE owns incident-rca calibration, platform team owns the k8s skill); a contribution guide and skill template so others add golden cases and query recipes without the founder; per-team config overlays (generalize the existing `review-rules.yaml` pattern). The founder's role shifts from author to framework owner and eval gatekeeper.

**→ 1,000 engineers / multiple business units (18 months+).** Federation. Central: framework, validators, eval harness, shared collectors. Per-BU: skill forks with local evidence hierarchies and their own corpora. Language diversity hits domain-comprehension hardest — verify understand-anything coverage per language before promising multi-language support. Governance becomes a real function: changes that alter conclusions org-wide need an approval path.

---

## 9. Competitive positioning

The platform runs *on* Cursor; Cursor, Copilot, and Devin are substrate and adjacent tooling, not rivals to beat on codegen. Genuine differentiators:

1. **Org evidence layer** — the acme-specific source hierarchy, KubeSense routing, and escalation matrix. Not replicable by any vendor.
2. **Calibrated-confidence culture** — reports leadership trusts because UNKNOWN is an allowed answer. Vendor tools optimize for always answering.
3. **Golden corpus** — accumulating org-specific ground truth on incidents, MRs, and domains. It compounds; a vendor starts from zero on this organization.
4. **Cross-domain chains** — vendor tools are single-surface (IDE or PR page). The incident → code → infra → cost chains here span surfaces under one evidence framework.

**Named risk:** vendors will ship "good enough" versions of individual skills. The defense is chains, corpus, and calibration — never feature parity.

---

## 10. Moonshots (2–5 years)

1. **Continuous production reasoning.** RCA collectors run on every alert; evidence bundles are pre-built; on-call opens an incident with hypothesis ranking already drafted.
2. **Self-tuning severity and confidence.** The review-feedback-learning pattern generalized: eval corpus plus user verdicts auto-adjust rubric weights, gated by the regression suite.
3. **Org digital twin.** Domain-comprehension artifacts refresh on merge and are queryable org-wide; every skill reads the twin as prior context. Architecture Q&A, impact analysis, and capacity planning become queries over one living model.
4. **Autonomous maintenance lane.** Dependency bumps, manifest rightsizing, doc refresh: agents open MRs continuously, humans only merge. Requires eval maturity from Stage 3 of Section 4.

---

## 11. Roadmap

### Immediate (next 2 weeks)
- Git-tag release versioning; install-script pinning; `skill_version` in report footers
- First 3 golden RCA cases + manual replay checklist
- Feedback-capture issue template

### Next quarter
- Eval harness v1: 10+ golden cases across three skills, scripted replay and scoring
- Telemetry sink (runs-log)
- release-readiness skill (mode 1: pre-deploy gate)
- Draft-action outputs: RCA → draft Jira preventive tickets
- Begin shared collector extraction

### Next 12 months
- Shared runtime complete — skill #5+ ships as a thin domain layer
- Orchestrated chains (Stage 2): incident loop, efficiency loop
- New skills: onboarding-copilot, datadog-monitor-audit, tech-debt hotspot map
- Event-triggered pr-review on MR open (post-eval-harness)
- Recruit 2–3 domain co-maintainers

### Long-term vision (2–5 years)
- Federation model for multiple business units
- Continuous production reasoning
- Org digital twin
- Autonomous maintenance lane

---

## Appendix — condensed deliverable lists

### A. Top improvement opportunities (ranked)

1. Behavioral eval harness with golden cases (T2)
2. Versioned distribution + report-footer versions (T3)
3. Telemetry sink for run metadata
4. Draft-action outputs behind approval gates (T4)
5. Shared evidence-collector library (T1)
6. Typed cross-skill handoff contracts
7. release-readiness skill
8. Feedback-capture → eval-case pipeline
9. Generalized artifact validator toolkit
10. Confidence calibration audits
11. Update-notification channel
12. datadog-monitor-audit skill
13. Corpus store for golden cases and artifacts
14. Per-team config overlays
15. Token/cost measurement in metadata
16. Trap cases (UNKNOWN-expected) in evals
17. onboarding-copilot skill
18. Skill-discovery footers and demo docs
19. Event-triggered pr-review
20. Contribution guide + skill template for co-maintainers

### B. New skill candidates (beyond the four prioritized in §3)

Deferred until the shared runtime lands, in rough value order: AWS cost optimization (beyond k8s), security review lens (extends pr-review personas), Java/SDK upgrade assistant, capacity planning (extends k8s skill trends), API governance/contract drift, CI pipeline health (Jenkins), data pipeline comprehension, performance regression analysis, documentation freshness audit, architecture-decision drift (ADRs vs. reality via domain corpus).

### C. Top multi-agent workflows

Incident loop; efficiency loop; comprehension loop (§4); then: alert-quality loop (monitor-audit → RCA detection feedback), release gate chain (pr-review → release-readiness → post-deploy watch), debt-remediation chain (hotspot map → draft refactor tickets → pr-review).

### D. Biggest risks to long-term success

1. One high-visibility wrong conclusion before evals exist (trust collapse)
2. Version drift across installs producing undebuggable reports
3. Solo-builder burnout / bus factor of one
4. Maintenance load from premature skill-count growth
5. Vendor "good enough" commoditization of single skills
6. Unattended automation shipped before behavioral testing

### E. Maturity summary

Advanced prototype, pre-platform (scorecard in §1). Strongest dimensions: evidence discipline and artifact rigor. Weakest: behavioral evaluation, telemetry, distribution. The 12-month plan converts the strengths into a durable platform by fixing exactly those three.
