# Host Adapter Contract

**Normative.** Core skills depend on capabilities, not product or provider names. Host adapters translate those capabilities into the active environment.

## Required adapter surface

A host profile declares support for these capability families:

```yaml
host:
  discover_files: full|degraded|unsupported
  read_repo: full|degraded|unsupported
  write_repo: full|degraded|unsupported
  git: full|degraded|unsupported
  scm: full|degraded|unsupported
  subagents: full|degraded|unsupported
  task_isolation: full|degraded|unsupported
  terminal: full|degraded|unsupported
  browser: full|degraded|unsupported
  connectors: full|degraded|unsupported
```

The machine-readable source is `scripts/registry/host_contracts.yaml`. Runtime/tooling code must resolve support through `scripts.registry.host_adapter.capability_support(...)`; unknown hosts, unknown capability families, and undeclared support values fail closed rather than inventing behavior.

A skill must resolve its declared capabilities against the profile before execution. Missing optional capabilities trigger documented degraded modes; missing required capability paths produce `BLOCKED` rather than invented substitutes.

## Core/runtime boundary

Core skill logic must not branch on host brand names such as Cursor, Claude, Codex, ChatGPT, or Kiro. Brand-specific discovery, paths, invocation syntax, and packaging belong in generated or explicit host adapters.

Provider names such as Datadog, GitHub, GitLab, Kubernetes, Jira, and Slack may appear as examples or adapter implementations, but routing decisions should be expressed as capability requirements.

## Packaging validation

The repository validates these surfaces:

- **Claude:** `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` are valid and point at the canonical skill tree.
- **Codex / ChatGPT:** `.codex-plugin/plugin.json` is valid and exposes the canonical skill tree. ChatGPT uses the same portable skill package contract; no ChatGPT-only prompt copy is maintained.
- **Cursor:** `.cursor/rules/*.mdc` are generated from the registry, cover exactly the registered skills, reference canonical `SKILL.md` files, and are checked for drift.
- **Kiro:** `.kiro/steering/*.md` are generated from the registry, cover exactly the registered skills, reference canonical `SKILL.md` files, and are checked for drift.
- **Generic agents:** build the deterministic portable bundle with `python3 -m scripts.registry package-generic --output dist/software-builder-skills.tar.gz`. The archive is seeded from the runtime files in every registered skill tree, the shared framework, `skills.yaml`, and the license, then follows the transitive set of reachable relative Markdown references. Per-skill `CHANGELOG.md` history, test/verification fixtures, VCS/CI/cache/build-output content, symlinks, and common credential/private-key files are excluded or rejected. Changelog links in packaged Markdown are rendered as plain labels rather than dangling links. Archive metadata is normalized and all remaining packaged relative Markdown references and anchors must remain valid after extraction.

`evals/host-parity/expected.yaml` captures semantic host-surface expectations; it is validated against the canonical registry and host contract instead of snapshotting exact prompt prose.

## Degraded operation

A host profile may be `degraded` for a capability family. The skill must state which outcome is unavailable and continue only when its own capability contract permits that mode. Host limitations never grant additional write or merge authority.
