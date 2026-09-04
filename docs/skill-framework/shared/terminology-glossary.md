# Terminology glossary

Shared vocabulary for **software-builder** platform docs, `skills.yaml`, and behavioral evals. Prefer these terms consistently across skills and ADRs.

**Domain language** (skill shapes, roles, evidence doctrine, separated decision concepts) lives in [CONTEXT.md](../../../CONTEXT.md) and [CONTEXT-MAP.md](../../../CONTEXT-MAP.md). **Target-system language** (bounded contexts, as-built PRD, squads) lives in [domain-comprehension/CONTEXT.md](../../../domain-comprehension/CONTEXT.md). This file covers **platform implementation vocabulary** — registry, capabilities, eval tiers, and schema field names.

## Core objects

| Term | Definition |
|------|------------|
| **Skill** | A portable agent workflow package: `SKILL.md`, `workflow/`, `reference/`, optional scripts. Identified by directory name and registry id (e.g. `pr-review`). |
| **Registry / canonical manifest** | Root `skills.yaml` — versioned canonical manifest for skills, platform contracts, composition contracts, install edges, hosts, invocation mode, permissions, capabilities, and artifact schemas. |
| **Framework** | `docs/skill-framework/` shared normative reference library vendored into installed packages. |
| **Capability** | A named external tool or API contract a skill may call, declared under `capabilities` in `skills.yaml` as globally required, optional/degraded, or a complete alternative `any_of` path. |
| **Composition** | How skills invoke or escalate to each other. The canonical `skills.yaml` manifest owns `contracts.composition`, including per-skill `produces` / `consumes` / `write_authority` contracts. `scripts/registry/composition_contracts.yaml` and `composition_runtime.yaml` are generated projections. |
| **Invocation envelope** | The typed field shape a wrapper skill hands to a child skill (exact scope, interaction policy, allowed actions, expected SHA, source revisions) — see [invocation-envelope.md](invocation-envelope.md) (#52). `mr_context` in the canonical manifest's composition contract is the reference implementation. |
| **Result envelope** | The canonical durable result shape described in [runtime-contract.md](runtime-contract.md). `review_metadata` and `assessment_metadata` are payload fields for specific artifacts, not competing envelope definitions. |
| **Skill fragment** | A single skill's registry entry, authored at `scripts/registry/skills.d/<skill-id>.yaml`. `make generate` merges every fragment into `skills.yaml`'s `skills:` mapping, which is therefore generated, not an authoring surface. Everything else in `skills.yaml` stays hand-edited. See `docs/adr/0005-registry-authoring-model.md` in the Software Builder repository. |
| **Profile / `extends:`** | A named block of shared registry fields under `skills.yaml`'s top-level `profiles:`. A skill entry with `extends: <profile>` inherits it, deep-merged with the skill's own keys winning; a nested mapping merges key by key, any other value (a list included) replaces the base outright. `resolve_registry_profiles` strips both `extends` and `profiles` at load time, so no consumer ever sees them — the effective entry of a skill using `extends:` is the profile merged with its fragment, not the fragment alone. |
| **Optional layer** | A contract layer a given repository root may or may not have — host contracts, capability catalogue, capability families, composition runtime, release contract, composition contracts, the P1 layer. `detect_optional_layers` (`scripts/registry/cli.py`) returns one `OptionalLayers` value that the generate and validate flows both read, instead of each re-deriving activity from `Path.is_file()` checks. `None` means inactive for this root. |
| **Discovery surface** | A host's place to look for skills, declared in `agent-hosts.yaml` as a `LOCAL`/`REMOTE`/`CLOUD`/`WEB`/`UNKNOWN` surface binding one or more install targets, each with a discovery mode (`NATIVE`/`ADAPTER`/`ALIAS`/`MANUAL`/`NONE`) and a numeric precedence where **lower wins**. |
| **Shadow** | A skill installed at one discovery root while a different copy occupies a root the same host prefers, so the host loads the other copy. `scripts/registry/shadow_detector.py` reports it at install time (`SHADOWED` / `DUPLICATE_IDENTICAL` / `UNKNOWN_PRECEDENCE` / `NONE`) and warns rather than blocks — a byte-identical copy is not a shadow, and a deliberate project-level override is valid. |
| **Host verification** | `agent-hosts.yaml`'s per-host `UNVERIFIED`/`VERIFIED`/`STALE`/`CONFLICTED` state, its `DOCUMENTATION`/`REPOSITORY`/`RUNTIME` evidence entries, and its `maintainer_support` commitment. `VERIFIED` requires at least one `RUNTIME` entry. See `docs/adr/0006-host-registry-and-evidence-model.md` in the Software Builder repository. |

## Invocation and risk

| Term | Definition |
|------|------------|
| **Invocation mode** | `ambient` (model may load from chat), `automation-only` (explicit external trigger only; requires `disable-model-invocation: true` in `SKILL.md`). |
| **Risk class** | Operational category for guardrail strictness: **posting** (GitLab writes), **merge** (branch/PR merge), **unattended** (webhook with no human), **read-only** (reports only), **repository-write** (commits/PRs in target repo). High-risk skills combine multiple classes. Declared per skill in `skills.yaml`. |
| **Write authority** | Composition contract flag: only the skill that owns a write scope may perform that write; wrappers may gate but not escalate writes. |
| **Install ownership** | Whether a directory at an install destination was created by this repository — `ABSENT`/`SOFTWARE_BUILDER_OWNED`/`UNOWNED`/`CORRUPT_OWNERSHIP`/`SYMLINK` (`scripts/reference_utils.py`). Only a `SOFTWARE_BUILDER_OWNED` directory may be replaced. Unrelated to artifact ownership or to a target workspace's squad ownership — see [CONTEXT.md § Ownership](../../../CONTEXT.md#ownership-three-senses). |
| **Degraded mode** | Documented fallback when an optional capability is absent (e.g. `chat-only` when inline posting unavailable). Missing every complete `any_of` readiness path is blocked, not degraded. |

## Distribution and quality

| Term | Definition |
|------|------------|
| **Installed package** | Self-contained skill directory under `~/.cursor/skills/<id>/` with vendored framework files and `.software-builder-manifest.json`. |
| **Distribution version** | Release version from root `VERSION`, recorded in installed manifests and release tarballs. |
| **Eval tier** | Behavioral test depth: Tier 1 = static contracts; Tier 2 = transcript policy replay; Tier 3 = (planned) LLM golden replay. |
| **Transcript fixture** | Tier-2 YAML under `evals/transcripts/` with ordered `events` and policy `assertions`. |
| **Doctor** | `python3 scripts/doctor.py` preflight: registry health, capability/install status checks before a run. |

## Evidence and state fields

| Term | Definition |
|------|------------|
| **`evidence_status`** | Per-claim strength in the result envelope: `OBSERVED`, `INFERRED`, `UNKNOWN`, `CONFLICTED`, `NOT_APPLICABLE` (`skills.yaml`, `contracts.platform.evidence.statuses`). `UNKNOWN` is the required status for insufficient evidence; `CONFLICTED` for disagreeing sources. Distinct from a confidence band, which grades a finding rather than a claim's sourcing. |
| **`state_semantic`** | Which world-state a result or durable artifact describes: `current_state`, `proposed_state`, `desired_state`, `transitional_state`. Required in the result envelope and declared per durable artifact; current-state claims carry evidence obligations that proposed-state claims do not. |
| **Artifact trust** | Whether a received artifact may back a gate, decided by how it was acquired (a direct child's return value or a runtime-validated document) rather than by what the document says about itself. Caller-supplied authority labels stay caller evidence. |

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
