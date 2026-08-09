# Terminology glossary

Shared vocabulary for **software-builder** platform docs, `skills.yaml`, and behavioral evals. Prefer these terms consistently across skills and ADRs.

## Core objects

| Term | Definition |
|------|------------|
| **Skill** | A portable agent workflow package: `SKILL.md`, `workflow/`, `reference/`, optional scripts. Identified by directory name and registry id (e.g. `pr-review`). |
| **Registry** | Root `skills.yaml` — canonical list of skills plus install edges, hosts, invocation mode, composition, and capabilities. |
| **Framework** | `docs/skill-framework/` shared normative reference library vendored into installed packages. |
| **Capability** | A named external tool or API contract a skill may call (required vs optional + degraded modes), declared under `capabilities` in `skills.yaml`. |
| **Composition** | How skills invoke or escalate to each other. `skills.yaml` holds `invokes` and `escalation_targets`; `scripts/registry/composition_contracts.yaml` holds per-skill `produces` / `consumes` / `write_authority` contracts validated at registry lint time. |

## Invocation and risk

| Term | Definition |
|------|------------|
| **Invocation mode** | `ambient` (model may load from chat), `automation-only` (explicit external trigger only; requires `disable-model-invocation: true` in `SKILL.md`). |
| **Risk class** | Operational category for guardrail strictness: **posting** (GitLab writes), **merge** (branch/PR merge), **unattended** (webhook with no human), **read-only** (reports only). High-risk skills combine multiple classes. |
| **Write authority** | Composition contract flag: only the skill that owns a write scope may perform that write; wrappers may gate but not escalate writes. |
| **Degraded mode** | Documented fallback when an optional capability is absent (e.g. `chat-only` when inline posting unavailable). |

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

See also: [phase-glossary.md](phase-glossary.md) for per-skill phase name mapping.
