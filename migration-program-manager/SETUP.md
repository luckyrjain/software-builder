# migration-program-manager — Setup


## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-08-09 |
| **Review cadence** | Quarterly — or when pinned MCP package versions change |
| **External services** | None (reads MIGRATION_STATUS.yaml + SQUAD_MAP.md on disk) |

See [setup-freshness.md](../docs/skill-framework/shared/setup-freshness.md) for the shared contract.
## Ambient discovery is intended

This skill deliberately does **not** set `disable-model-invocation` — the agent can auto-apply it when
you ask for an org-wide migration status rollup, as well as an explicit invocation. No gate-policy
concerns apply — see [SKILL.md](SKILL.md) § "Why no gate policy, and no live wrapped-skill invocation at
all": this skill never invokes mysql-to-postgres-sql or squad-map live, only reads their existing files.

## Install

```bash
cd software-builder
make install-migration-program-manager
```

This chains `make install-mysql-to-postgres-sql install-squad-map` first — this skill has no
migration/ownership logic of its own and its output is meaningless without at least one workspace having
run both. Restart Cursor so all three skills reload.

### Claude Code

`make install-migration-program-manager` above already installs this skill for Claude Code too (default
installs to both editors). For Claude Code **only**:

```bash
cd software-builder
make install-claude-migration-program-manager
```

No restart needed. See [claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).

### Kiro / in-repo discovery

Working directly in this repo? `.cursor/rules/migration-program-manager.mdc` and
`.kiro/steering/migration-program-manager.md` point Cursor/Kiro at
`migration-program-manager/SKILL.md` without an install step.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python 3 | For `scripts/aggregate_migration_status.py` |
| PyYAML | `python3 -m pip install pyyaml` — parses `MIGRATION_STATUS.yaml` |
| pytest (dev only) | `python3 -m pip install pytest` — runs `tests/`, required by `make lint-migration-program-manager` |
| mysql-to-postgres-sql installed and configured | Its own prerequisites apply — see [mysql-to-postgres-sql/SETUP.md](../mysql-to-postgres-sql/SETUP.md) |
| squad-map installed and configured | Optional per-workspace — a workspace without it still aggregates, joined as `squad: UNKNOWN` — see [squad-map/SETUP.md](../squad-map/SETUP.md) |

No MCP of its own — this skill never queries GitLab, Datadog, or any other MCP server directly.

## Config

No config file of its own. `program_manifest` and `staleness_threshold_days` are passed at invocation
time. `state_path` defaults alongside the report output; point it at a stable, version-controlled or
persistent location if you want staleness tracking to survive across sessions/machines — an ephemeral
`state_path` (e.g. a scratch directory wiped between runs) means every run looks like a first run
(staleness always 0), which silently defeats the escalation this skill exists to provide.

## Framework links

- [skill-framework README](../docs/skill-framework/README.md)
- [confidence-bands](../docs/skill-framework/shared/confidence-bands.md)
- [cross-skill-escalation](../docs/skill-framework/shared/cross-skill-escalation.md)

## Smoke test

After install, run the invocation in [reference/smoke-test.md](reference/smoke-test.md), and separately
verify the script's own test suite: `python3 -m pytest migration-program-manager/tests/ -v`.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Every service shows staleness 0 every run | `state_path` isn't persisting between runs — check it points at a stable location, not a scratch/ephemeral path |
| A workspace's services are all missing from the report | Check `MIGRATION_STATUS.yaml` actually exists at that `workspace_root` — see the Workspace gaps section of the report |
| A service always joins as `squad: UNKNOWN` despite a real `SQUAD_MAP.md` | Check the service's `path` (preferred) or `name` in `MIGRATION_STATUS.yaml` matches `SQUAD_MAP.md`'s `Repo` column exactly — **this skill's own adapter** (`join_squad` in [scripts/aggregate_migration_status.py](scripts/aggregate_migration_status.py)) is exact-match only, no fuzzy matching or alias fallback. That's a property of this adapter, not the shared [org-rollup-schema.md](../docs/skill-framework/shared/org-rollup-schema.md) itself — its `k8s_waste` adapter (used by cost-optimization-sprint-planner) does fall back to squad-map's `ownership.datadog.service_aliases` config when a verbatim match fails (schema § 3). Fix the mismatch here by correcting the `Repo` cell or the service's `path`/`name`, not by expecting an alias to be consulted. |
| `ModuleNotFoundError: No module named 'yaml'` | `python3 -m pip install pyyaml` |
