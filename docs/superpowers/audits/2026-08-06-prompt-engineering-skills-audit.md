# Prompt-Engineering Audit — All 16 Skills (2026-08-06)

**Scope:** every skill in the repo — `mysql-to-postgres-sql`, `backlog-runner`,
`cost-optimization-sprint-planner`, `domain-comprehension`, `incident-rca`, `incident-triage-agent`,
`k8s-overprovisioning-datadog`, `loop-task-implementer`, `migration-program-manager`, `new-hire-guide`,
`pr-gatekeeper`, `pr-review`, `release-readiness-checker`, `squad-map`, `weekly-squad-digest`,
`who-owns-x-bot`.

**Method:** four independent audits (four skills each), acting as an expert prompt engineer, read every
`SKILL.md`, `SETUP.md`, `examples.md`, `workflow/*.md`, and `reference/*.md` in full or near-full, and
cross-checked claims against the actual source of every skill they referenced (not just self-reports).
Audits deliberately did **not** re-check mechanical structure/line-budget compliance already enforced by
`make lint-<skill>` / `make lint-framework` — they focused on defects a linter cannot catch: frontmatter
description quality for auto-invocation, instruction clarity/ambiguity for the executing LLM, guardrail
completeness, redundancy vs. progressive disclosure, cross-file consistency, examples quality, and
cross-skill routing/escalation correctness against `docs/skill-framework/shared/skill-routing.md` and
`cross-skill-escalation.md`.

**Headline:** this is an unusually mature skill library. Every skill's "When NOT to use" table was
checked against the shared routing table's 18 disambiguation rules — **zero routing contradictions or
dangling handoffs found** across all 16 skills. Confidence-band vocabulary, finding-ID conventions, and
read-only/write boundaries were consistently and correctly applied. No skill had a structural defect that
would cause it to misfire on an unrelated request. The findings below are real but mostly Low/Medium —
polish and drift-prevention, not foundational problems.

---

## Repo-wide patterns (same defect, multiple skills)

These recur enough to fix once, systematically, rather than skill-by-skill.

1. **Frontmatter uses `Triggers:` instead of the framework's own documented `Keywords:` label.**
   `incident-rca`, `pr-review`, `loop-task-implementer` — 3 of 16 skills — diverge from the design spec's
   own canonical template (`docs/superpowers/specs/2025-06-30-unified-skill-framework-design.md:86-92`:
   `description: >- Use when … Keywords: …`) and from the other 13 skills, which all use `Keywords:`.
   Notably **pr-review is the framework's own named reference implementation**, so this is the one skill
   most likely to be copied as a template — perpetuating the drift. **Severity: Medium.** Fix: normalize
   all three to `Keywords:`, or update the design spec to officially bless `Triggers:` as a synonym if
   that's actually preferred — pick one, once, normatively.

2. **Dangling reference to a "SKILL.md Non-goals" section that doesn't exist.** `incident-triage-agent`
   (`SKILL.md:49`, `workflow/postmortem.md:19`, `workflow/triage.md:18`) and `who-owns-x-bot`
   (`workflow/lookup.md:14`) all cite `SKILL.md` "Non-goals" as an authority section; no `SKILL.md` in the
   repo has a heading by that name. The real content lives elsewhere (a design spec, or the "When to use /
   NOT to use" table). Same copy-paste-shaped mistake, landed independently in two unrelated skills — a
   sign the "see SKILL.md Non-goals" phrase may have propagated from a shared template or one skill's
   scaffolding. **Severity: Medium** (guardrail content is genuinely reachable elsewhere, but the primary
   citation is wrong everywhere it appears). Fix: point each citation at the section that actually exists.

3. **`reference/pressure-tests.md` missing despite being normatively required.**
   `smoke-test-conventions.md` §7 requires every smoke doc to link a pressure-tests file with ≥2 rows.
   Missing in `weekly-squad-digest`, `release-readiness-checker`, and `who-owns-x-bot` — all three handle
   untrusted external text (rollup manifests, release manifests, Slack queries) and answer live gates on a
   wrapped skill's behalf, which is exactly the kind of adversarial surface `pressure-tests.md` exists to
   pin down. `squad-map`'s version (with real prompt-injection rows) is a good template to copy from.
   **Severity: Low-Medium** per skill. Fix: add the file to each, seeded from the prompt-injection and
   never-re-derive guarantees each skill already states in prose.

---

## Findings by severity

| # | Severity | Skill | Location | Defect |
|---|----------|-------|----------|--------|
| 1 | Medium | mysql-to-postgres-sql | `reference/collection-domain-files.md` + 4 referring files | Promised "collection domain pack" doesn't exist; org-specific residue (CLMS/EMS/RCM) leaks into an otherwise portable skill |
| 2 | Medium | incident-rca | `examples.md:332,458,464` | Golden few-shot example uses non-existent `MEDIUM–HIGH` compound confidence band, contradicting the skill's own 4-band vocabulary |
| 3 | Medium | incident-triage-agent | `SKILL.md:49`, `workflow/postmortem.md:19`, `workflow/triage.md:18` | Dangling "SKILL.md Non-goals" citation (see repo-wide #2) |
| 4 | Medium | pr-review | `SKILL.md:3-8` | `Triggers:` vs `Keywords:` (see repo-wide #1) — highest-impact instance since pr-review is the reference implementation |
| 5 | Medium | pr-gatekeeper | `reference/auto-post-policy.md:10-85` | Hardcoded enumeration of pr-review's 7 ask-points has no drift check against pr-review's independently-versioned workflow files; a new pr-review ask-point could make unattended webhook runs hang forever with no lint catching it |
| 6 | Medium | squad-map | `workflow/phase-1.md` Step 7.1 vs 7.4 | CODEOWNERS-derived squad guess is computed, then discarded — structured columns write `UNKNOWN` regardless, so `org-rollup-schema.md` consumers lose the signal entirely when both MCPs are down |
| 7 | Medium | who-owns-x-bot | `reference/slack-format.md` | "Surfaced as a suggestion in the reply" escalation (mid-incident query) has no defined format and no example — LLM will improvise inconsistent wording or drop it |
| 8 | Medium | who-owns-x-bot | `workflow/lookup.md` Step 3 / `squad-map/workflow/phase-1.md` | No documented guardrail for two concurrent single-shot invocations read-modify-writing the same `SQUAD_MAP.md` — a realistic race for a Slack bot |
| 9 | Low-Medium | incident-rca | `workflow/phase-5.md:110` | Cites "k8s skill v3.1 expected context"; k8s is now v3.4 — stale cross-skill version pin |
| 10 | Low-Medium | pr-review | SKILL.md §Framework / `workflow/phase-0.md` | Not linked to `mcp-error-handling.md` despite being a named consumer with an explicit 1-retry policy pr-review's Phase 0 never states |
| 11 | Low-Medium | new-hire-guide | `examples.md` | Only 1 true happy-path scenario and no proper handoff-block example; `examples-conventions.md` requires 3 happy-path + 1 handoff |
| 12 | Low-Medium | migration-program-manager | `examples.md` | Same examples-depth gap as new-hire-guide; a real handoff case (blocked MR → pr-review) is documented but never demonstrated |
| 13 | Low-Medium | weekly-squad-digest | `reference/` | Missing `pressure-tests.md` (repo-wide #3) |
| 14 | Low-Medium | release-readiness-checker | `reference/` | Missing `pressure-tests.md` (repo-wide #3) |
| 15 | Low | mysql-to-postgres-sql | `SKILL.md` frontmatter | No labeled `Keywords:` clause, unlike its three sibling skills in this batch |
| 16 | Low | mysql-to-postgres-sql | `docs/skill-framework/shared/skill-routing.md:23` | Shared, normative routing table embeds one org-specific term ("collection P0/P1 cooling SQL") despite the framework's portability goal |
| 17 | Low | domain-comprehension | `examples.md:59-60` | Duplicate step numbering ("4." twice) in the flagship worked example |
| 18 | Low | incident-rca | `SKILL.md:4` | `Triggers:` vs `Keywords:` (see repo-wide #1) |
| 19 | Low | loop-task-implementer | (repo-wide) | No `precedence.md` equivalent for resolving simultaneous stop conditions (circuit breaker vs. base-update invalidation vs. completion gate) — unlike incident-rca and k8s, which both found this worth codifying |
| 20 | Low | migration-program-manager | `SETUP.md:76` | "Exact-match, no fuzzy matching" stated as if schema-wide; actually adapter-specific (the shared schema's fuzzy-alias fallback applies to `k8s_waste`, which this skill doesn't implement) |
| 21 | Low | squad-map | `SKILL.md:27-32` | "When NOT to use" table pairs rows that aren't genuine near-miss confusions, unlike sibling skills' equivalent tables |
| 22 | Low | who-owns-x-bot | `workflow/lookup.md:14` | Dangling "SKILL.md Non-goals" citation (see repo-wide #2) |
| 23 | Low | release-readiness-checker | `reference/gate-policy.md` | Historical "Correction (round-1 review)" narrative left in the normative policy file rather than moved to CHANGELOG — cosmetic, low risk of the fix's rationale being dropped on a future edit |
| 24 | Low | cost-optimization-sprint-planner | `SKILL.md` vs `reference/gate-policy.md` | ~120 vs ~150-word near-duplicate rationale for cost-rate resolution — minor progressive-disclosure miss, a few hundred wasted tokens per invocation |

No High-severity findings — nothing found would misroute a request, silently corrupt an artifact, or bypass a stated guardrail undetected in normal operation.

---

## Per-skill detail

### mysql-to-postgres-sql
- **[Medium]** `reference/collection-domain-files.md` is a stub ("Moved to domain pack") linked from `data-type-mapping.md:49`, `timestamp-handling.md:180`, `nodejs-migration.md:160`, `case-sensitivity.md`, all of which cite specific org entities (CLMS `TblUserLoanRepository`, EMS `CAST(...AS CHAR)`, RCM SMS cooling tables) as if a curated "collection" domain pack exists. `domain-packs/README.md`'s "Available packs" table lists only a blank `TEMPLATE.md`. An agent asked to migrate the collection domain hits a dead end the docs implied was populated, and may fabricate specifics to fill the gap. Fix: author the pack for real, or strip the org-specific residue so the skill matches its own claimed portability.
- **[Low]** No labeled `Keywords:` clause in frontmatter, unlike siblings.
- **[Low]** Shared `skill-routing.md` line 23 embeds the org-specific phrase "collection P0/P1 cooling SQL" in an otherwise generic table.
- **Done well:** `reference/skill-contract.md` (compact non-negotiable rules, loaded up front) and `reference/pressure-tests.md` (every scan-script regex token tied to a dedicated fixture line) are strong patterns; `reference/migration-edge-cases.md` §F/§C catch semantic-correctness traps a syntax-only scan structurally can't.

### backlog-runner
- No material findings. `reference/queue-policy.md` §3 openly documents an unresolved ambiguity in the wrapped skill (loop-task-implementer's dependency-eligibility check) rather than papering over it — a pattern worth copying elsewhere. Cross-run dependency-satisfaction rules and `CONSECUTIVE_ESCALATION_BREAKER` counting semantics are precisely specified and match the actual `state-schema.yaml`.

### cost-optimization-sprint-planner
- **[Low]** Minor prose duplication between `SKILL.md` and `reference/gate-policy.md` on cost-rate resolution rationale.
- **Done well:** `gate-policy.md` quotes the wrapped k8s skill's actual documentation verbatim before stating "this skill's scripted answer" — strong anti-hallucination pattern. `SCOPE_EXHAUSTED` vs `COMPLETED` as distinct stop reasons, and never giving a sweep-gap deployment a `$0` row, both prevent a report from silently overstating coverage.

### domain-comprehension
- **[Low]** Duplicate step numbering in the flagship "Fintech payout" worked example (`examples.md:59-60`), cosmetic only.
- **Done well:** `evidence-precedence.md` + `confidence-rubric.md`'s mechanical `overall_confidence = minimum(...)` with an explicit "Forbidden HIGH from" list; `manifest-schema.md` + `scripts/validate_manifest_yaml.py` make artifact completeness scriptable, not honor-system; `workflow-changelog.md`'s dated, bug-named history (~16 entries) is a genuinely useful practice the other 15 skills mostly lack (only cost-optimization-sprint-planner has a comparable one).

### incident-rca
- **[Medium]** `examples.md` golden example uses `MEDIUM–HIGH`, a compound band outside the skill's own 4-band vocabulary — risk that future authors pattern-match the range notation from this few-shot.
- **[Low-Medium]** `phase-5.md:110` cites a stale "k8s skill v3.1" version pin; k8s is now v3.4.
- **[Low]** `Triggers:` instead of `Keywords:` in frontmatter.
- **Note (unscored):** `reference/org-profiles.md` bakes one customer's ("acme") topology and STOP-rule-level logic into the shared library; it self-flags as non-portable, but a `reference/org-profiles/` scaffold with acme as one example (not the only one) would reduce cargo-culting risk for new adopters.
- **Done well:** the "Common mistakes (rationalizations → reality)" table in `evidence-schema.md` names the exact plausible shortcuts an LLM takes under evidence pressure; the pre-render attestation checklist in `phase-5.md` is mirrored well by k8s and loop-task-implementer.

### incident-triage-agent
- **[Medium]** Dangling "SKILL.md Non-goals" citation in three files (see repo-wide #2).
- **Done well:** `reference/unattended-gate-policy.md` enumerates every stop-and-wait point in both wrapped skills with a deterministic answer for each — verified against incident-rca's actual current phase-2 checkpoint text and it matches exactly. `postmortem-format.md`'s owner-placeholder table correctly distinguishes three different placeholder strings across incident-rca's tables.

### k8s-overprovisioning-datadog
- No defects found above stylistic nitpicks. `reference/precedence.md`'s explicit conflict-resolution ranking (stop-reasons > validate gates > confidence formula > recommendation inputs > thresholds > dimension modules) is a strong deterministic-conflict pattern other skills should adopt more uniformly (see loop-task-implementer finding below). The `vpa_hpa_conflict_cpu/_memory` STOP_REASON reasoning is genuinely sophisticated domain logic, not boilerplate.

### loop-task-implementer
- **[Low]** No `precedence.md`-equivalent for resolving simultaneously-triggerable stop conditions (circuit breakers, base-update invalidation, completion gates). Low risk today given the sequential workflow, but a future extension could introduce an ordering ambiguity with nothing to check against.
- **Done well:** `SEQUENTIAL_SIMULATION` degraded-isolation handling (caps confidence, discloses degraded mode rather than a full-weight `CLEAN` verdict) and the explicit refusal to let repo-internal prose set `autonomous_merge_authorized` are first-rate prompt-injection-aware design. `review.lens_a/lens_b.isolation_primitive_used` makes the "independent review" guarantee auditable, not just asserted — the single strongest pattern found across all 16 skills.

### migration-program-manager
- **[Low-Medium]** `examples.md` has only 1 true happy-path scenario (needs 3 per `examples-conventions.md`) and no worked handoff-block example, despite documenting a real handoff case (blocked MR → pr-review).
- **[Low]** `SETUP.md:76`'s "exact-match, no fuzzy matching" claim is adapter-specific, not schema-wide as phrased.
- **Done well:** `SKILL.md`'s "why no gate policy, no live wrapped-skill invocation" section explicitly names and generalizes the risk class it avoids (new-hire-guide's `seed_repos` regression) — genuine cross-skill institutional learning captured in-repo. The "never re-derive `status` from underlying fields, since a service can be both `blocked` and stale simultaneously" guardrail is precise and reinforced identically in three places.

### new-hire-guide
- **[Low-Medium]** `examples.md` has only 1 true happy-path scenario and no handoff-block-format example.
- **Done well:** `workflow/run-tour.md` §3's justification for never narrowing domain-comprehension via `seed_repos` preserves *why* (cites the specific downstream corruption it caused when tried before) — exactly what prevents a future editor from reintroducing the bug. `reference/tour-format.md`'s rule that purpose/confidence values must trace to domain-comprehension's own output ("never upgraded for a friendlier tour") is a good anti-hallucination guardrail.

### pr-gatekeeper
- **[Medium]** `reference/auto-post-policy.md`'s hardcoded 7-ask-point enumeration has no mechanical check that it stays in sync with pr-review's independently-versioned workflow files; a future pr-review ask-point could hang unattended webhook runs indefinitely with nothing in `make lint-pr-gatekeeper` catching it.
- **Done well:** the ask-point protocol table (one designated literal reply per gate, all others forbidden) is an exemplary deterministic-reply design; the Outcome truth table over `{auto_post_authorized × posting_mode × draft_state}` makes the never-override-draft invariant impossible to miss; `SETUP.md` correctly places dedupe/persistence burden on the calling webhook handler rather than pretending the skill has its own state.

### pr-review (framework reference implementation)
- **[Medium]** `Triggers:` instead of `Keywords:` — highest-impact instance of repo-wide #1 since this is the named reference implementation other skills are told to match parity with.
- **[Low-Medium]** Not linked to `mcp-error-handling.md` despite being an explicitly named consumer with a stated 1-retry policy that `workflow/phase-0.md` doesn't implement or mention.
- **Done well:** `reference/finding-pipeline.md`'s 12-step deterministic pipeline (Detect → Evidence → Don't-guess → Execution-path → Dedupe → Non-negotiable → Severity → Confidence → Value filter → Rank/group → Classify → Output) is the strongest instruction-clarity artifact in the repo. `reference/precedence.md`'s 4-rank conflict resolution is consistently deferred to everywhere else. Deprecated reference files are left as one-line redirect stubs rather than duplicated or silently deleted.

### release-readiness-checker
- **[Low-Medium]** Missing `reference/pressure-tests.md` (repo-wide #3) — notable since this skill answers multiple wrapped skills' live gates on the caller's behalf.
- **[Low]** `reference/gate-policy.md` mixes a historical "Correction (round-1 review)" narrative into what should be pure normative policy.
- **Done well:** the most rigorous cross-skill citation discipline found — every quoted phrase from pr-review/k8s/incident-rca was independently verified against the actual source and was accurate. The "Escalation, not override" rule (never substitute its own judgment for a wrapped skill's on an uncovered state) is an excellent guardrail worth replicating in any future skill that answers gates on another skill's behalf.

### squad-map
- **[Medium]** CODEOWNERS-fallback squad guess is computed in `workflow/phase-1.md` Step 7.1 then discarded in Step 7.4 (structured columns still write `UNKNOWN`); `org-rollup-schema.md` only reads the structured columns, so the signal is silently lost for every rollup consumer when both MCPs are down.
- **[Low]** "When NOT to use" table pairs rows that aren't genuine likely confusions, unlike sibling skills.
- **Done well:** `reference/squad-mapping.md`, `config-schema.md`, and `gold-squad-map-excerpt.md` are exceptionally precise (exact indexing formula, worked walkthrough, a runnable script backing the confidence table) — a strong model for reference depth elsewhere. Its `pressure-tests.md` is the only one of the four batch-4 skills with real adversarial/prompt-injection rows.

### weekly-squad-digest
- **[Low-Medium]** Missing `reference/pressure-tests.md` (repo-wide #3).
- **Done well:** best-in-class handling of `staleness_days: 0` needing key-existence (not truthiness) checks — stated identically in three places with a matching example row, closing off a very plausible LLM mistake. The same-service-different-squad cross-rollup limitation is disclosed honestly rather than silently "fixed."

### who-owns-x-bot
- **[Medium]** "Surfaced as a suggestion in the reply" mid-incident escalation has no defined format or example in `reference/slack-format.md`, which otherwise declares itself the normative source for "the exact three reply shapes."
- **[Medium]** No documented guardrail for two concurrent single-shot Slack queries read-modify-writing the same `SQUAD_MAP.md`.
- **[Low]** Dangling "SKILL.md Non-goals" citation (repo-wide #2).
- **Done well:** excellent, consistent discipline on "single reply only" / "LOW confidence folds into Unknown, never Resolved," stated once and never re-derived across four files. Openly discloses the squad-map side effect (writing `SQUAD_MAP.md`) rather than hiding the fact that a "single-shot" bot triggers a multi-repo file write.

---

## Recommendations

1. Fix the three repo-wide patterns once, systematically, rather than as 8 separate skill-level edits:
   normalize `Triggers:` → `Keywords:` (3 skills), fix the dangling "SKILL.md Non-goals" citations (2
   skills, 4 files), and add `reference/pressure-tests.md` to the 3 skills missing one.
2. Close the two dead-end/drift risks with real blast radius: mysql-to-postgres-sql's missing "collection"
   domain pack (agents can hit it mid-migration), and pr-gatekeeper's unguarded ask-point enumeration
   (could hang an unattended webhook run indefinitely on a future pr-review change).
3. Fix squad-map's CODEOWNERS-guess discard — it's a real, silent signal loss for every downstream rollup
   skill when both MCPs are degraded, which is exactly the scenario the fallback exists for.
4. Everything else in the table is genuine but low-blast-radius polish; batch it opportunistically the
   next time each skill is touched rather than as a dedicated pass.
