## Context

A read-only repository review (structure, packaging, CI, dependency health, release hygiene, security
posture, maintainability) was done against `main` at `a620bd9` on 2026-08-06. Full verdict: **WATCH** —
strong prompt-engineering foundation, but the repository wasn't yet hardened as a dependable public skill
*platform* (registry, versioning, generated adapters, transactional install, behavioral evals).

**Quick wins from that review are already done:** #8 adds LICENSE (MIT), SECURITY.md, CONTRIBUTING.md,
CODEOWNERS, PR/issue templates, an expanded `.gitignore`, GitHub Actions pinned to SHAs, and the npx-resolved
MCP package examples in SETUP docs pinned to specific versions.

**Related:** #20 tracks a separate, earlier backlog — unaddressed items from the original skills-behavior
audit (not this platform review). Different scope (skill correctness/robustness vs. repository platform
engineering), filed separately on purpose.

This issue tracked everything else from that review as a prioritized backlog.

**Status update (2026-08-09):** P0–P2 and substantive P3 platform engineering are **complete** on `main`
via PRs #29–#42. Child issues #10–#19 are closed. Remaining items below are explicitly deferred (settings
access or out-of-scope polish) — not blockers for closing this tracker.

## P0 — infrastructure/governance (beyond the quick wins in #8)

- [x] #10 — Enforce CI as a required merge gate on `main` — PR #30
- [x] #11 — Reproducible dependency resolution (`requirements.txt` lockfile/hashes) — PR #27 + `requirements.lock`

## P1 — platform engineering

- [x] #12 — Skill registry + generic validator — PR #31 (`skills.yaml`, `scripts/registry/`, `make validate-registry`)
- [x] #13 — Generated host adapters — PR #31 (thin `.cursor/rules/*.mdc` + `.kiro/steering/*.md` from registry)
- [x] #14 — Transactional installer — PR #32 (staging, allowlist, `--dry-run`/`--list`/`--verify`/`--uninstall`)
- [x] #15 — Installed-package shared-reference integrity — PR #29 (`package_skill.py`, vendored framework, `make verify-install`)
- [x] #16 — Behavioral evaluation framework — PR #33 (Tier 1) + PR #37 (Tier 2 transcripts) + PR #40 (Tier 3 golden outputs; static replay in CI)

## P2 — scale and ecosystem

- [x] #17 — Release and compatibility model — PR #33 (v1) + PR #36 (GitHub Releases workflow, tag verification, `compatibility-matrix.md`, `docs/RELEASE.md` breaking-change policy)
- [x] #18 — Capability preflight / `doctor` command — PR #33 + PR #34 (`capabilities` for all 22 skills, `backfill-capabilities`)
- [x] #19 — Cross-skill dependency-graph validator — PR #33 (v1) + PR #35 (composition contracts, write-authority) + PR #39 (producer/consumer field schema matching)

## P3 — polish

- [ ] Repository description/topics on GitHub *(needs repository settings access — not automatable from CI)*
- [x] Architecture decision records — PR #38 (`docs/adr/`)
- [x] Split docs into normative vs. historical — PR #41 (`docs/history/README.md` + `docs/superpowers/` archive guidance)
- [ ] Freshness ownership/review-date metadata on external-service SETUP docs *(deferred)*
- [x] Terminology glossary — PR #38 (`docs/skill-framework/shared/terminology-glossary.md`)
- [x] Provenance headers on generated files — PR #31 (`GENERATED from skills.yaml` markers)
- [x] Machine-readable platform metadata in registry — PR #41 (`risk_class` on all 22 skills in `skills.yaml`; SKILL.md frontmatter JSON schema deferred)
- [x] Defined risk classes per skill — PR #41
- [x] Handoff field contracts + behavioral output checks — PR #39 (composition `artifact_schemas`) + PR #37/#40 (transcript + golden eval fixtures)
- [x] CI installing all 22 skills outside checkout — PR #38 (`make verify-install-all` in `make lint`)
- [x] Stop hand-maintaining skill-count badge/inventory — PR #31 (marker-generated README + `docs/REPOSITORY.md`)

## Deferred (track elsewhere if picked up)

| Item | Notes |
|------|-------|
| GitHub repo topics/description | Org/repo settings |
| SETUP.md freshness metadata | Per-skill doc hygiene sweep |
| Live LLM golden replay refresh | Tier 3 today is static `recorded_output` replay; add refresh workflow when needed |
| Full SKILL.md frontmatter schema | Registry owns platform facts; agent prose stays in `SKILL.md` |

## Suggested sequencing (completed)

P0 unblocked trustworthy CI; #12 was the highest-leverage change — #13–#15 and #17–#19 were sequenced from the registry as planned. Follow-on work landed in PRs #34–#42.
