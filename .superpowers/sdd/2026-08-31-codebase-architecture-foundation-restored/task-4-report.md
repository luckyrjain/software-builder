# Task 4 — Canonical registration report

## Scope completed

- Added authoritative registry fragments for `module-design` and `codebase-architecture-review` under `scripts/registry/skills.d/`, then regenerated the explicitly requested canonical `skills.yaml` skill mapping.
- Registered both skills as inherited `read-only-leaf-review` contracts: `leaf`, `ambient`, read-only, six-host, no dependencies, and required capabilities exactly `[host.report.write, host.repository.read]`.
- Declared explicit `invokes: []`. `module-design` can escalate only to `system-design` and `architecture-review`; `codebase-architecture-review` can escalate only to `module-design` and `domain-comprehension`.
- Added durable v1 proposed-state artifacts, payload type maps, composition producer contracts, and canonical single-owner ownership with no delegates:
  - `module_design_spec` owned by `module-design`.
  - `codebase_architecture_report` owned by `codebase-architecture-review`.
- Added matching capability-catalog and setup-freshness entries.
- Added a foundation assertion covering registration shape, six-host inheritance, permissions, required capabilities, no invokes/consumes, exact artifact fields, v1/proposed-state metadata, payload types, and ownership.

## Artifact schemas

`module_design_spec` required fields:

`title`, `module_scope`, `responsibility`, `callers`, `contract_surface`, `invariants`, `dependency_direction`, `seams`, `adapters`, `errors`, `state_model`, `concurrency_expectations`, `performance_sensitive_behavior`, `test_surface`, `migration_plan`, `alternatives_rejected`, `unresolved_questions`.

`codebase_architecture_report` required fields:

`title`, `scope`, `analysis_budget`, `evidence_summary`, `candidates`, `top_recommendation`, `limitations`.

## Focused verification outputs

Command:

```text
python3 -m pytest -q scripts/tests/test_codebase_architecture_foundation.py -k canonical_read_only_artifact_contracts
```

Output:

```text
.                                                                        [100%]
1 passed, 7 deselected in 0.45s
```

Command:

```text
python3 -m pytest -q scripts/tests/test_artifact_contracts.py scripts/tests/test_composition_contracts.py scripts/tests/test_validate_setup_freshness.py
```

Output:

```text
...........................................................              [100%]
59 passed in 1.70s
```

Command:

```text
python3 -m scripts.registry backfill-capabilities --check
```

Output:

```text
ok: all skills already have capabilities blocks
```

Command:

```text
git diff --check
python3 - <<'PY'
from pathlib import Path
from scripts.registry.artifact_contracts import validate_artifact_contracts
from scripts.registry.canonical_manifest import validate_canonical_manifest
from scripts.registry.capability_sync import validate_capability_catalog_sync
from scripts.validate_setup_freshness import ensure_setup_freshness
root = Path('.')
assert validate_canonical_manifest(root) == []
assert validate_artifact_contracts(root) == []
assert validate_capability_catalog_sync(root) == []
assert ensure_setup_freshness(root, write=False) == []
print('ok: canonical registry, artifacts, capability catalog, and setup freshness validate')
PY
```

Output:

```text
ok: canonical registry, artifacts, capability catalog, and setup freshness validate
```

## Known out-of-scope failures (not changed)

The full foundation dispatch module has four failures because `scripts/registry/routing_rules.yaml` does not yet declare the two new registered skills. The first error is:

```text
ValueError: routing rules must cover exactly all registered skills; missing=['codebase-architecture-review', 'module-design'], extra=[]
```

This task explicitly excludes central routing, so no routing entry was added.

The legacy `scripts/registry/composition_contracts.yaml` projection remains intentionally untouched. Its tests therefore report the new artifact ownership entries as unknown when that legacy file is supplied directly. The canonical manifest validation and canonical artifact-contract validation above both pass.

`scripts/tests/test_registry.py::test_bootstrap_registry_validates_on_real_repo` also remains out of scope: it requires central routing, Make install targets, and Task 2–3 framework-link text. No change was made to those areas.
