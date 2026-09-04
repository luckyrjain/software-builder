# Context Map

How domain language is split across this repository. Platform concepts describe **software-builder itself**; target-system concepts describe **what skills discover about customer workspaces**.

## Contexts

- [Software Builder platform](./CONTEXT.md) — skills, hosts, composition, evidence doctrine, multi-agent roles, and change-delivery vocabulary for the library itself
- [Target system analysis](./domain-comprehension/CONTEXT.md) — bounded contexts, ownership, as-built requirements, and org rollups produced when skills operate on a target workspace

## Relationships

- **Platform → Target system analysis**: Specialist and composer skills (`domain-comprehension`, `squad-map`, `prd-architect`, `migration-program-manager`, …) run *on* a target workspace and emit artifacts defined in the target context. The platform context defines *how* those skills run; the target context defines *what they mean* about customer systems.
- **Target system analysis → Platform**: `domain-comprehension` always invokes `squad-map` at Session 0b (mandatory subroutine, not optional escalation). Squad assignments from `SQUAD_MAP.md` feed bounded-context cards and downstream platform skills (release-readiness, org rollups).
- **Shared confidence bands**: HIGH / MEDIUM / LOW / UNKNOWN apply in both contexts but measure different things — platform skills use them for findings; target analysis uses them for section- and document-level evidence strength.
- **Separated decision concepts** (evidence completeness, review verdict, repository readiness, external-action authorization, final repository action) are defined in the platform context and apply wherever a skill emits a verdict or takes an external action.

## Where to look

| Question | Context |
|----------|---------|
| What is a wrapper vs router vs aggregator? | [CONTEXT.md § Skill shapes](./CONTEXT.md#skill-shapes) |
| Why does the registry say `leaf`/`orchestrator` when CONTEXT.md says specialist/composer? | [CONTEXT.md § Composition topology](./CONTEXT.md#composition-topology-type-in-skillsyaml) |
| What does `evidence_status` or `state_semantic` mean on a result? | [CONTEXT.md § Verification and evidence](./CONTEXT.md#verification-and-evidence) |
| Which sense of "ownership" is this? | [CONTEXT.md § Ownership](./CONTEXT.md#ownership-three-senses) |
| What is a bounded context or as-built PRD? | [domain-comprehension/CONTEXT.md](./domain-comprehension/CONTEXT.md) |
| What do `skills.yaml` fields mean? | [terminology-glossary.md](./docs/skill-framework/shared/terminology-glossary.md) |
| What is a profile / `extends:` / an optional layer / a shadow? | [terminology-glossary.md](./docs/skill-framework/shared/terminology-glossary.md) |
| Why was the registry canonical? | [ADR 0001](./docs/adr/0001-skills-registry.md) |
| Where is a skill's registry entry authored? | [ADR 0005](./docs/adr/0005-registry-authoring-model.md) |
| How does a host earn `VERIFIED`, and why are there two host files? | [ADR 0006](./docs/adr/0006-host-registry-and-evidence-model.md) |
| What do I do when an install lock or the generated roster breaks? | [docs/OPERATIONS.md](./docs/OPERATIONS.md) |
