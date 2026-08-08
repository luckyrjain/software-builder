# Skills registry — `skills.yaml` and generated inventories

**Date:** 2026-08-08  
**Status:** Approved for P1 implementation (milestone C)  
**Source:** August 2026 repository review (`software-builder-latest-main-full-review-2026-08-07.md`) findings #3, #4, #10; GitHub issue #12

## Problem

The repository advertises 22 skills but encodes platform facts in at least five manually synchronized
surfaces:

- Root `Makefile` (~80 KB): install dependency edges, per-skill lint targets, required files, tests
- `README.md`: skill count badge and catalogue
- `docs/REPOSITORY.md`: install target inventory tables
- `.cursor/rules/*.mdc`: discovery + duplicated routing/policy prose
- `.kiro/steering/*.md`: same routing prose in Kiro format

Adding or changing a skill requires coordinated edits across these locations. Drift is already
demonstrated (historical 16-vs-22 skill loops). Host adapters are the worst offender: they repeat
policy that belongs only in `SKILL.md`.

## Goal

Introduce `skills.yaml` as the canonical source of **platform** facts. Generate host adapters and
derived documentation from registry + `SKILL.md` frontmatter. CI fails on registry drift.

## Non-goals (milestone C)

- Registry-driven per-skill `make lint-*` recipes (phase 2)
- Rewriting `scripts/install.sh` from registry data (phase 2, pairs with transactional installer #14)
- Capability/output schema fields in registry (P2 — #13, #19)
- Full `tools/software_builder/` package with `pyproject.toml` (defer until installer/doctor land)
- Behavioral evaluation harness (#16)

## Decisions

| Decision | Choice |
|----------|--------|
| Milestone scope | **C** — validate + generate adapters + derived docs + install graph (docs) |
| Metadata split | **Split ownership** — registry = platform; `SKILL.md` = agent |
| Implementation layout | **Approach 1** — `scripts/registry/` modules + Make wrappers |

## Split ownership model

### Registry owns (platform facts)

Stored in `skills.yaml`:

```yaml
schema_version: 1

skills:
  unit-test-creator:
    path: unit-test-creator
    category: testing
    invocation: ambient          # ambient | automation-only
    hosts:
      cursor: { discovery: rule }   # rule | manual | always
      claude: { install: true }
      kiro:   { discovery: manual }
    install:
      requires: []                  # install dependency edges
    lint:
      skill_md_max_lines: 180
      target: unit-test-creator     # make lint-<target> alias
```

### `SKILL.md` owns (agent facts)

YAML frontmatter remains authoritative for:

- `name` (must equal registry key and directory name)
- `description` (used in generated adapter `description` / steering text)
- `skill_version` (optional today; validated when present)
- `disable-model-invocation` (must agree with registry `invocation`)

### Cross-check rules (CI)

1. Registry keys ↔ directories containing `SKILL.md` (bidirectional, no orphans)
2. `name:` in frontmatter == registry key == directory name
3. `disable-model-invocation: true` ↔ `invocation: automation-only`
4. `install.requires` edges reference existing skills; no cycles (DFS)
5. `hosts.*.discovery` values are known enums
6. Makefile install dependency edges match registry (warning in v1, error once install.sh reads registry)

## Generated outputs

### Cursor rules — `.cursor/rules/<skill>.mdc`

Thin discovery wrapper only (≤10 lines of body). **No** routing policy, mocking rules, or workflow
detail.

```markdown
---
description: <first line of SKILL.md description>
alwaysApply: false
---

<!-- GENERATED from skills.yaml + SKILL.md — do not edit; run make generate -->

Invoke the <skill-id> skill. Read `<skill-id>/SKILL.md` and follow it.
```

`alwaysApply: true` only when `hosts.cursor.discovery: always` (none today).

### Kiro steering — `.kiro/steering/<skill>.md`

```markdown
---
inclusion: manual
---

<!-- GENERATED from skills.yaml + SKILL.md — do not edit; run make generate -->

For <skill-id>, read `<skill-id>/SKILL.md` and follow it.
```

`inclusion` derived from `hosts.kiro.discovery` (`manual` | `always`).

### README skill count

Replace hardcoded badge count via HTML comment markers:

```markdown
<!-- skills-count:start -->22<!-- skills-count:end -->
```

`make generate` updates the number between markers.

### `docs/REPOSITORY.md` skill inventory table

Generated markdown table between markers:

```markdown
<!-- registry-skills-table:start -->
...
<!-- registry-skills-table:end -->
```

Surrounding prose stays hand-written.

### Install dependency graph (documentation)

- `generated/catalogue/install-deps.mmd` — Mermaid diagram from `install.requires`
- Optional markdown edge list embedded in REPOSITORY table section

`scripts/install.sh` is **not** generated in milestone C.

## Module layout

```
scripts/
  registry/
    __init__.py
    __main__.py
    models.py           # typed registry entries
    schema.py             # schema_version + enum validation
    load.py               # parse skills.yaml + scan SKILL.md frontmatter
    crosscheck.py         # split-ownership consistency
    generate_cursor.py
    generate_kiro.py
    generate_docs.py      # README badge, REPOSITORY table, Mermaid
    cli.py                # validate | generate [--check]
  tests/
    test_registry.py
skills.yaml
generated/
  catalogue/
    install-deps.mmd
```

Makefile targets:

| Target | Behavior |
|--------|----------|
| `make validate-registry` | `python3 -m scripts.registry validate` |
| `make generate` | `python3 -m scripts.registry generate` |
| `make lint` | runs `validate-registry` before existing lint |

`generate --check`: write to temp dir or memory, diff against committed files; exit 1 on drift.

## CLI behavior

```bash
python3 -m scripts.registry validate
python3 -m scripts.registry generate
python3 -m scripts.registry generate --check
```

**Exit codes:** `0` success, `1` validation or drift failure, `2` tooling/parse error.

**Error format:** `error: <skill-id>: <message>` on stderr. Collect all errors per category before
exiting (not fail-fast on first skill).

**Warnings (v1):** missing `reference/phase-index.md`; unknown optional keys in `skills.yaml`.

## Migration (22 existing skills)

### Bootstrap PR

1. Author `skills.yaml` for all 22 skills — derive `install.requires` from current Makefile install targets
2. Run `make generate` — replace fat adapters with thin wrappers (largest diff)
3. Wire `validate-registry` into `make lint` and CI
4. Add `scripts/tests/test_registry.py` with golden adapter fixtures

### Backward compatibility

- `make install-<skill>` targets unchanged in v1
- Generated adapter files remain **committed** (not gitignored)
- `make setup` unchanged
- Installed skill packages unaffected (adapters are in-repo discovery only)

## Testing

| Test | Proves |
|------|--------|
| `test_schema_rejects_invalid_discovery` | Enum strictness |
| `test_crosscheck_name_mismatch` | Split-ownership |
| `test_install_cycle_detected` | Graph validator |
| `test_generate_cursor_golden` | Stable adapter output |
| `test_generate_check_fails_on_drift` | CI gate |
| `test_bootstrap_all_22_skills` | Full registry round-trip |

## Success criteria (milestone C complete)

1. Adding skill #23 requires: skill directory + one `skills.yaml` entry + `make generate` — no manual adapter or inventory edits
2. `make lint` fails on registry / frontmatter drift
3. `make generate --check` passes in CI
4. Cursor/Kiro adapters are thin (≤10 body lines, no duplicated policy)
5. README skill count and REPOSITORY inventory table are marker-generated
6. Install dependency Mermaid graph matches Makefile install edges

## Sequencing after milestone C

| Follow-up | Issue | Reads from registry |
|-----------|-------|---------------------|
| Registry-driven lint | — | `lint.*` fields |
| Transactional installer | #14 | `install.requires`, allowlist |
| Capability doctor | #18 | `capabilities` (new fields) |
| Cross-skill graph validator | #19 | composition edges |
| Release bundles | #17 | versions, checksums |

## Relation to completed P0 work

Distribution integrity (#29) solved installed-package reference resolution. The registry solves
**source-tree** drift between platform surfaces. Both are required for a dependable public skill
platform; they are independent and can ship in either order (registry does not change install
packaging).
