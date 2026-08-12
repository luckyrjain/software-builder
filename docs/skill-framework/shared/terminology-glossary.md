# Terminology glossary

Shared vocabulary for **software-builder** platform docs, `skills.yaml`, and behavioral evals. Prefer these terms consistently across skills and ADRs.

## Core objects

| Term | Definition |
|------|------------|
| **Skill** | A portable agent workflow package: `SKILL.md`, `workflow/`, `reference/`, optional scripts. Identified by directory name and registry id (e.g. `pr-review`). |
| **Registry** | Root `skills.yaml` — canonical list of skills plus install edges, hosts, invocation mode, composition, and capabilities. |
| **Framework** | `docs/skill-framework/` shared normative reference library vendored into installed packages. |
| **Capability** | A named external tool or API contract a skill may call, declared under `capabilities` in `skills.yaml` as globally required, optional/degraded, or a complete alternative `any_of` path. |
| **Composition** | How skills invoke or escalate to each other. `skills.yaml` holds `invokes` and `escalation_targets`; `scripts/registry/composition_contracts.yaml` holds per-skill `produces` / `consumes` / `write_authority` contracts validated at registry lint time. |
| **Invocation envelope** | The typed field shape a wrapper skill hands to a child skill (exact scope, interaction policy, allowed actions, expected SHA, source revisions) — see [invocation-envelope.md](invocation-envelope.md) (#52). `mr_context` in `composition_contracts.yaml` is the reference implementation. |
| **Result envelope** | The typed field shape a skill returns (`review_metadata` / `assessment_metadata`) — see [review-metadata-schema.md](review-metadata-schema.md) §8. |

## Invocation and risk

| Term | Definition |
|------|------------|
| **Invocation mode** | `ambient` (model may load from chat), `automation-only` (explicit external trigger only; requires `disable-model-invocation: true` in `SKILL.md`). |
| **Risk class** | Operational category for guardrail strictness: **posting** (GitLab writes), **merge** (branch/PR merge), **unattended** (webhook with no human), **read-only** (reports only), **repository-write** (commits/PRs in target repo). High-risk skills combine multiple classes. Declared per skill in `skills.yaml`. |
| **Write authority** | Composition contract flag: only the skill that owns a write scope may perform that write; wrappers may gate but not escalate writes. |
| **Degraded mode** | Documented fallback when an optional capability is absent (e.g. `chat-only` when inline posting unavailable). Missing every complete `any_of` readiness path is blocked, not degraded. |

## Distribution and quality

| Term | Definition |
|------|------------|
| **Installed package** | Self-contained skill directory under `~/.cursor/skills/<id>/` with vendored framework files and `.software-builder-manifest.json`. |
| **Distribution version** | Release version from root `VERSION`, recorded in installed manifests and release tarballs. |
| **Eval tier** | Behavioral test depth: Tier 1 = static contracts; Tier 2 = transcript policy replay; Tier 3 = (planned) LLM golden replay. |
| **Transcript fixture** | Tier-2 YAML under `evals/transcripts/` with ordered `events` and policy `assertions`. |
| **Doctor** | `python3 scripts/doctor.py` preflight: registry health, capability/install status checks before a run. |

## Workflow conventions

| Term | Definition |
|------|------------|
| **Phase** | Numbered pipeline stage in `workflow/phase-*.md` with required frontmatter (`workflow_version`, `phase`, `produces`, `consumes`). |
| **Gate** | A decision point that must resolve before later side effects (e.g. Phase 3 confirmation before GitLab post). |
| **Pressure test** | Manual scenario matrix in `reference/pressure-tests.md`; Tier-2 transcripts automate subsets of these for CI. |
| **Escalation** | Handoff from one skill to another via documented typed inputs (`docs/skill-framework/shared/cross-skill-escalation.md`). |

## Five separated concepts

Repo-wide audit in [five-concept-separation-audit.md](five-concept-separation-audit.md) (#53) —
these five must never share a single field/code path in any skill:

| Term | Definition |
|------|------------|
| **Evidence completeness (EC)** | Has enough evidence been gathered to speak with confidence — e.g. `review_metadata.review_complete`, `evidence_summary` counters. |
| **Review verdict (RV)** | The judgment given the evidence — e.g. `recommendation`, a confidence-banded conclusion. Distinct from EC: a verdict can be UNKNOWN precisely because EC is low, but the two are separate fields, not one collapsing into the other. |
| **Repository readiness (RR)** | Is the *target* itself (repo, release, service) ready — distinct from "is my review done" (EC) and "what do I think" (RV). Only meaningful for skills that evaluate a target's own readiness, e.g. release-readiness-checker's `Verdict: READY|CONDITIONAL|NOT_READY|UNKNOWN`. |
| **External-action authorization (EA)** | Is external posting/writing/merging permitted right now — e.g. `auto_post_authorized`, `autonomous_merge_authorized`. A positive RV never implies EA on its own. |
| **Final repository action (FA)** | Did the write/post/merge actually happen — e.g. `posted`, "Posted?" — a fact recorded separately from the authorization that permitted it. |

See also: [phase-glossary.md](phase-glossary.md) for per-skill phase name mapping.
