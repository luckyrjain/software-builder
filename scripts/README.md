# Repository scripts

`scripts/` holds the installer, the registry tooling behind `make generate` / `make validate`, the
repo's own validators, the release pipeline, and the deterministic engines a few skills call. This
file documents the installer in detail and indexes everything else.

## The install script

`scripts/install.sh` builds a **self-contained package** per skill (per
[ADR 0002](../docs/adr/0002-self-contained-skill-packages.md)) rather than copying the source
directory. For each skill:

1. Resolves the repo root (parent of `scripts/`) and the destination root(s) from `--agent` and
   `--target-dir`.
2. Rejects any skill not registered in `skills.yaml`.
3. Takes a lock directory at `<dest_root>/.<skill>.lock` so two installs cannot race into the same
   destination. See [docs/OPERATIONS.md](../docs/OPERATIONS.md) if it ever reports a timeout.
4. **Stages** the package into a fresh `mktemp -d` directory alongside the destination —
   `scripts/package_skill.py` writes the skill tree plus every referenced `docs/skill-framework/`
   file, with links rewritten to package-local paths.
5. **Validates** the staged package with `scripts/validate_references.py --installed-package`. A
   failure discards the staging directory and leaves the existing install untouched.
6. **Classifies** the destination's ownership. Only a directory this repository installed (proven by
   a valid `.software-builder-manifest.json` naming the same skill) may be replaced. A symlink, an
   unowned directory, or a manifest that fails to parse or names a different skill is refused, not
   overwritten — which matters for the shared `.agents/skills` target other tools also write to.
7. **Backs up** an existing owned install by moving it to a same-filesystem backup directory, then
   **atomically `mv`s** the staged directory into place. Any failure after the backup restores it and
   prints `warning: restored previous install at ...`; an interrupt (`INT`/`TERM`) does the same.
8. Warns when the freshly-installed copy is **shadowed** — a different copy already sitting at a
   discovery root the host prefers, so the new install is not what will actually load.
9. Prints a restart/session reminder appropriate to the chosen `--agent`.

There is no `rm -rf` of a live install: the old copy is moved aside, never deleted before the new one
is in place.

### `--agent` selectors

| Selector | No `--target-dir` (global) | With `--target-dir <repo>` |
|----------|----------------------------|-----------------------------|
| `cursor`, `cursor-project` | `~/.cursor/skills/` | `<repo>/.cursor/skills/` |
| `claude-project` | `~/.claude/skills/` | `<repo>/.claude/skills/` |
| `claude-user` | `~/.claude/skills/` | `~/.claude/skills/` (always global) |
| `agents` | `~/.agents/skills/` | `<repo>/.agents/skills/` |
| `all` (default) | both Cursor and Claude roots | both project roots |

`agents` installs to the universal Agent Skills target — a shared, multi-tool discovery directory
that belongs to no single host, described in
[ADR 0006](../docs/adr/0006-host-registry-and-evidence-model.md).

Kiro has no `--agent` selector and needs no install step: `make generate` writes
`.kiro/steering/<skill>.md` into this checkout. Codex and GitHub Copilot have no dedicated selector
either. Copilot's published docs name `.agents/skills` as one of the directories it recognizes, and
Codex runtimes commonly use `~/.agents/skills/`, so `--agent agents` is the supported route for both;
Copilot's own dedicated paths (`.github/skills/`, `~/.copilot/skills/`) still need a manual copy. See root
[README.md § Install for your specific coding agent](../README.md#install-for-your-specific-coding-agent).

## Usage

```bash
# From repo root — all skills, both Cursor and Claude Code (global)
bash scripts/install.sh
make install

# One skill (global)
bash scripts/install.sh pr-review
bash scripts/install.sh k8s-overprovisioning-datadog
bash scripts/install.sh incident-rca
bash scripts/install.sh domain-comprehension
bash scripts/install.sh squad-map
bash scripts/install.sh mysql-to-postgres-sql
bash scripts/install.sh loop-task-implementer

# One agent only (global)
bash scripts/install.sh --agent cursor
bash scripts/install.sh --agent claude-user

# Universal Agent Skills target (.agents/skills), user- or project-scoped
bash scripts/install.sh --agent agents
bash scripts/install.sh --agent agents --target-dir /path/to/some/repo

# Project-local (into another repo's .cursor/skills / .claude/skills)
bash scripts/install.sh --target-dir /path/to/some/repo domain-comprehension squad-map
bash scripts/install.sh --agent cursor --target-dir /path/to/some/repo domain-comprehension
bash scripts/install.sh --agent claude-project --target-dir /path/to/some/repo domain-comprehension
```

Makefile wrappers: `make install`, `make install-<skill>` (per skill), `make install-claude`,
`make install-claude-<skill>`.

## Requirements

- Bash with `set -euo pipefail`, and `python3` (the staging and validation steps are Python)
- Write access to the resolved destination root(s) (`~/.cursor/skills/`, `~/.claude/skills/`,
  `~/.agents/skills/`, or the corresponding project directories when `--target-dir` is set)
- Each skill source must contain `SKILL.md` and be registered in `skills.yaml`, or the script exits
  with an error

## Module index

<!-- scripts-index:begin — hand-maintained snapshot. One line per file, taken from each module's first
     docstring paragraph. A future generator can own this block; until then, update it when a module is
     added, removed, or repurposed. -->

#### `scripts/` — top level

| File | Purpose |
|------|---------|
| `__init__.py` | Repository scripts package (enables `python3 -m scripts.registry`). |
| `apply_repo_metadata.py` | Apply .github/repo-metadata.yaml to the GitHub repository via gh. |
| `apply_repo_metadata.sh` | Thin shell wrapper around `apply_repo_metadata.py`. |
| `change_impact.py` | Deterministic, bounded change-impact analysis primitives. |
| `check_changelog_placement.py` | Flag root CHANGELOG.md entries that look like they duplicate a skill's own CHANGELOG.md. |
| `check_github_ruleset.py` | Verify the live GitHub main-branch ruleset matches docs/github-ruleset-main.json. |
| `check_golden_staleness.py` | Warn when a skill's SKILL.md changed after its golden fixtures were last refreshed. |
| `check_pinned_actions.py` | Fail on any GitHub Action reference not pinned to a full commit SHA. |
| `check_platform_files.py` | Assert every load-bearing platform file is present in the repository. |
| `check_requirements_lock.py` | Ensure requirements.lock pins every package declared in requirements.txt. |
| `deprecation_diff_guard.py` | Block removal of governed prompt-system identities before deprecation matures. |
| `deprecation_lifecycle.py` | Validate deprecated prompt/contract items against the configured lifecycle window. |
| `doctor.py` | Preflight / doctor command for software-builder skills. |
| `eval_tier_health.py` | Deterministic eval-tier coverage for the Batch 5 prompt-system health report. |
| `git_paths.py` | Small, byte-safe helpers for reading Git path lists. |
| `implementation_plan.py` | Fail-closed validation and identity helpers for implementation_plan v1. |
| `install-incident-rca-deps.sh` | Install incident-rca's prerequisite skills before incident-rca itself. |
| `install.sh` | The installer itself, documented in full above. |
| `install_support.py` | Helpers for scripts/install.sh: registry allowlist and installed-package verify. |
| `lint_skills.py` | Run the shared per-skill structural lint checks (SKILL.md length, workflow frontmatter, dangling links, required reference files, framework wiring, render-surface sanitization) over one skill or the whole registry. |
| `operational_upkeep.py` | Prompt-system upkeep policy: file-role classification, ownership, health report, and diff-risk gating. |
| `package_release.py` | Create a byte-reproducible, checksummed release bundle for software-builder. |
| `package_skill.py` | Package a skill directory into a self-contained install bundle. |
| `production_readiness.py` | Pure evidence-aggregation and gating logic for the production-readiness-review orchestrator. |
| `reference_utils.py` | Shared helpers for Markdown link extraction, framework path handling, and the install-package manifest workflow (packaging, verification) per ADR 0002. |
| `release_contract.py` | Machine-readable release contract: repository version, tag shape, release artifact names, compatibility policy, and required provenance fields. |
| `release_info.py` | Read distribution version and source identity for manifests and release tooling. |
| `release_readiness_v2.py` | Backward-compatible release manifest v2 parsing, trusted production-readiness reuse, and conditional production-readiness invocation for release-readiness-checker. |
| `resilience_review.py` | Runtime normalization for the resilience-review specialist. |
| `test_creator_catalog.py` | Canonical catalog shared by test-creator packaging and parity checks. |
| `test_creator_write_guard.py` | Fail-closed pre-write guard shared by the five test-creator skills. |
| `validate_metadata_footer.py` | Validate review_metadata / assessment_metadata YAML footers (shared schema v2). |
| `validate_references.py` | Validate local Markdown links in a source tree or installed skill package. |
| `validate_review_contracts.py` | Fail-closed validation for shared change identity and review evidence. |
| `validate_setup_freshness.py` | Validate (and optionally backfill) SETUP.md freshness tables per setup_freshness.yaml. |
| `validate_workflow_contracts.py` | Validate workflow producer/consumer contracts across every declared route. |
| `verify_release_bundle.py` | Independently verify a packaged release bundle before it is uploaded. |
| `verify_release_tag.py` | Verify git tag matches VERSION before release. |
| `yaml_safety.py` | Shared YAML-safety loader: rejects duplicate mapping keys and caps document size/nesting so a malformed file fails loudly instead of silently overwriting data (last-key-wins) or blowing the stack on deeply nested/recursive input. |

#### `scripts/registry/` — registry tooling

| File | Purpose |
|------|---------|
| `__init__.py` | Skill registry: validate skills.yaml and generate host adapters. |
| `__main__.py` | Entry point for `python3 -m scripts.registry`; delegates to `cli.py`. |
| `agent_skills.py` | Portable Agent Skills frontmatter conformance validation. |
| `artifact_contracts.py` | Validate durable artifact contracts and runtime result envelopes. |
| `artifact_trust.py` | Execution-owned trust classification for artifacts and embedded contexts. |
| `assessment_target.py` | Canonical identity and digest helpers for composable assessments. |
| `backfill_capabilities.py` | Read the generated capability catalogue; validate every skill's capabilities block. |
| `canonical_manifest.py` | Canonical versioned manifest loader and legacy projection renderer. |
| `capability_engine.py` | The single required/optional/any_of capability-resolution engine skills.yaml's capability contracts are evaluated against. |
| `capability_family_sync.py` | Validate that provider-branded capability ids resolve to an abstract family. |
| `cli.py` | The `python3 -m scripts.registry` command surface: generate, validate, package, check-handoff, validate-artifact. |
| `compatibility_resolver.py` | Host x skill compatibility resolution (Candidate 4 of the universal-agent-compatibility design, docs/superpowers/specs/2026-08-31-universal-agent-compatibility-design.md). |
| `composition.py` | Validate the composition graph and render its Mermaid diagram. |
| `composition_contracts.py` | Load and validate composition contracts (produces/consumes/write_authority). |
| `composition_runtime.py` | Load and validate the composition runtime (skill `type`, recursion guard, artifact ownership modes) and enforce handoff admission. |
| `cross_skill_routing.py` | Parse the escalation matrix out of cross-skill-escalation.md and re-anchor its relative links for docs/README.md. |
| `crosscheck.py` | Whole-registry validation and stale-generated-adapter detection. |
| `envelope_contract.py` | The canonical runtime vocabularies every contract validator checks the registry against. |
| `generate_agent_compatibility.py` | Generated agent-compatibility documentation (Candidate 11 of docs/superpowers/specs/2026-08-31-universal-agent-compatibility-design.md). |
| `generate_compatibility.py` | Render the generated host x skill compatibility matrix. |
| `generate_cursor.py` | Render the generated `.cursor/rules/*.mdc` discovery adapters. |
| `generate_docs.py` | Render the generated regions of README.md, docs/README.md, and docs/REPOSITORY.md. |
| `generate_kiro.py` | Render the generated `.kiro/steering/*.md` discovery adapters. |
| `generate_makefile_roster.py` | Render `make/generated-roster.mk`'s `ALL_SKILLS` from the registry. |
| `generic_package.py` | Build a host-neutral skill package archive. |
| `graph.py` | Cycle detection for the composition and dependency graphs. |
| `host_adapter.py` | Host capability support lookup and host-adapter interface/identity validation. |
| `host_portability.py` | Validate that every skill declares a workable path on every supported host. |
| `host_registry.py` | Typed parsing and fail-closed validation for agent-hosts.yaml. |
| `id_diff.py` | Shared "found ids vs registered ids" two-way diff, used by the doc sync validators (routing_sync.py) so the dangling vs. |
| `install_resolver.py` | One module answering "where does `install.sh --agent X` write, and under what host label". |
| `load.py` | Load skill descriptions, deprecation markers, and the parsed registry. |
| `machine_summary.py` | Pure validators for the common artifact-v2 machine summary. |
| `makefile_graph.py` | Read the root Makefile plus its literal includes as one text blob. |
| `manifest.py` | Build the normalized runtime manifest from the canonical skills.yaml. |
| `manifest_merge.py` | Merge per-skill authoring fragments into the generated root skills.yaml. |
| `models.py` | Typed registry records: `SkillEntry`, `InstallSpec`, `CapabilitiesSpec`, and friends. |
| `p1_validation.py` | Validate the P1 contract layer: result/handoff/execution envelope fields, host matrices, permissions. |
| `result_envelope.py` | One builder for the runtime result envelope every assessment skill returns. |
| `routing_sync.py` | Cross-check skill-id mentions in shared framework docs against the registry. |
| `escalation_sync.py` | Cross-check cross-skill-escalation.md's matrix against the registry's escalation edges. |
| `generate_issue_templates.py` | Regenerate the skill dropdowns in .github/ISSUE_TEMPLATE/*.yml from the registry. |
| `schema.py` | Parse and cache skills.yaml, resolving `profiles:`/`extends:` before any consumer sees it. |
| `semantic_document.py` | Fail-closed identity binding for machine summaries and semantic documents. |
| `shadow_detector.py` | Discovery-precedence shadow detection for install.sh (Candidate 8 of docs/superpowers/specs/2026-08-31-universal-agent-compatibility-design.md). |
| `skill_contract_adoption_sync.py` | Every skill must reference the shared result/authorization/completion contracts. |
| `skill_frontmatter_schema.py` | SKILL.md YAML frontmatter schema (v1). |
| `skill_result.py` | The execution-status half of the shared runtime result envelope. |
| `validation_primitives.py` | Shared primitives for the repo's `validate_X(data) -> list[str]` validators. |

<!-- scripts-index:end -->

`scripts/tests/` holds the shared pytest suite (`make lint-framework-tests`). `scripts/registry/*.yaml`
are the registry's data files rather than modules, and `skills.yaml`'s per-skill authoring fragments
live under `scripts/registry/skills.d/`.

## Quality gate

Staged changes to `scripts/*.sh` are linted by the pre-commit hook (`make setup-hooks`) and by
`make lint` (shellcheck locally or via Docker).

See [docs/REPOSITORY.md](../docs/REPOSITORY.md) for full repo documentation.
