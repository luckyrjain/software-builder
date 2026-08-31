# Agent Compatibility Expansion Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish executable legacy-install evidence, Agent Skills conformance validation, and a validated declarative host registry without changing installer behavior.

**Architecture:** Keep `skills.yaml` as the skill-owned registry and add an independent `agent-hosts.yaml` for host-owned facts. Build small Python validators with typed models and deterministic errors; later installer and doctor work will consume these validators. Freeze current Bash installer behavior with subprocess golden tests before migrating any destination logic.

**Tech Stack:** Bash 3.2-compatible installer, Python 3.12, dataclasses, PyYAML/ruamel YAML safety helpers, pytest, existing `scripts.registry` package.

**Spec:** `docs/superpowers/specs/2026-08-31-agent-compatibility-approved.md`

## Global Constraints

- `SKILL.md` remains the canonical workflow definition.
- `skills.yaml` remains the canonical source of skill capability requirements.
- `agent-hosts.yaml` is the canonical source of host discovery and capability information.
- Existing Cursor and Claude installer command meanings remain unchanged.
- `--agent all` semantics do not change in this phase.
- Unknown capabilities do not satisfy required capabilities.
- Canonical skills do not receive host-specific permission fields.
- Supported installer platforms remain macOS, Linux, and WSL; Bash 3.2 syntax remains valid.
- Registry schema version 1 rejects unknown fields and unsafe path templates.
- Every new security validation rule has a negative test.

---

### Task 1: Freeze legacy installer behavior

**Files:**
- Create: `scripts/tests/test_install_legacy_golden.py`
- Modify: `scripts/tests/test_install_integration.sh` only if a shared fixture helper is needed

**Interfaces:**
- Consumes: current `scripts/install.sh` CLI output and exit-code behavior.
- Produces: subprocess tests that later installer-resolver work must keep green.

- [ ] **Step 1: Write golden tests for current dry-run selectors.**

  Add tests that run `bash scripts/install.sh` from the repository root with a
  temporary `HOME`, capture stdout/stderr separately, and assert exit code 0.
  Cover these exact invocations and destination/host text:

  ```text
  --agent cursor --dry-run pr-review
  --agent cursor-project --target-dir <tmp>/project --dry-run pr-review
  --agent claude-user --dry-run pr-review
  --agent claude-project --target-dir <tmp>/project --dry-run pr-review
  --agent all --target-dir <tmp>/project --dry-run pr-review
  ```

  Assert the cursor paths end in `.cursor/skills/pr-review`, Claude paths end
  in `.claude/skills/pr-review`, project paths use the exact temporary project
  root, and `all` emits exactly one Cursor and one Claude destination. Assert
  that no dry-run invocation writes a destination.

- [ ] **Step 2: Add golden tests for legacy list, verify, and invalid selector behavior.**

  Assert `bash scripts/install.sh --list` returns the sorted IDs emitted by
  `scripts.install_support.registry_skill_ids`, `--verify <missing>` returns
  non-zero and contains `not a directory`, and an unknown agent returns
  non-zero with `unknown --agent` in stderr. Keep the test independent of the
  current user's home directory.

- [ ] **Step 3: Run the focused baseline tests.**

  Run:

  ```bash
  PYTHONPATH=. .venv/bin/python -m pytest -p no:cacheprovider scripts/tests/test_install_legacy_golden.py scripts/tests/test_install_safety.py -q
  ```

  Expected result: all tests pass against the unchanged installer.

- [ ] **Step 4: Commit the baseline freeze.**

  ```bash
  git add scripts/tests/test_install_legacy_golden.py scripts/tests/test_install_integration.sh
  git commit -m "test: freeze legacy installer behavior"
  ```

### Task 2: Add Agent Skills conformance validation

**Files:**
- Create: `scripts/registry/agent_skills.py`
- Create: `scripts/tests/test_agent_skills.py`
- Modify: `scripts/registry/__main__.py`
- Modify: `scripts/registry/cli.py`
- Modify: `make/core.mk`

**Interfaces:**
- Consumes: `scripts.registry.frontmatter.load_skill_frontmatter` and the
  repository's canonical skill directories.
- Produces: `validate_agent_skills(root: Path) -> list[str]`,
  `validate_skill(skill_dir: Path) -> list[str]`, and registry CLI command
  `python3 -m scripts.registry validate-agent-skills`.

- [ ] **Step 1: Write failing validator tests.**

  In `scripts/tests/test_agent_skills.py`, add tests for: missing `SKILL.md`,
  missing frontmatter, invalid YAML frontmatter, missing `name`, missing or
  empty `description`, uppercase name, underscore name, leading/trailing
  hyphen, consecutive hyphens, name longer than 64 characters, name that does
  not match the directory, description longer than 1024 characters, and a
  valid minimal skill. Add one repository-wide test that validates the current
  canonical skill set and asserts an empty error list.

- [ ] **Step 2: Run the validator tests to verify the expected failures.**

  Run:

  ```bash
  PYTHONPATH=. .venv/bin/python -m pytest -p no:cacheprovider scripts/tests/test_agent_skills.py -q
  ```

  Expected result: collection succeeds and the new behavior tests fail because
  `scripts.registry.agent_skills` and its CLI command do not yet exist.

- [ ] **Step 3: Implement the minimal conformance validator.**

  Parse frontmatter through the existing YAML-safe loader. Validate exactly the
  required portable fields and constraints in the Phase 1 spec. Return stable
  messages prefixed with the skill-relative path. Reject malformed input rather
  than guessing. Do not validate host-specific fields and do not mutate skill
  files.

- [ ] **Step 4: Wire the validator into the registry CLI and Make target.**

  Add `validate-agent-skills` to `scripts/registry/__main__.py`/`cli.py` and a
  `validate-agent-skills` Make target that exits non-zero for any error. Keep
  the existing `validate` command behavior unchanged.

- [ ] **Step 5: Run focused and repository-wide conformance tests.**

  Run:

  ```bash
  PYTHONPATH=. .venv/bin/python -m pytest -p no:cacheprovider scripts/tests/test_agent_skills.py scripts/tests/test_skill_frontmatter_schema.py -q
  PYTHONPATH=. .venv/bin/python -m scripts.registry validate-agent-skills
  ```

  Expected result: all tests pass and the repository command prints a success
  result with no validation errors.

- [ ] **Step 6: Commit conformance validation.**

  ```bash
  git add scripts/registry/agent_skills.py scripts/tests/test_agent_skills.py scripts/registry/__main__.py scripts/registry/cli.py make/core.mk
  git commit -m "feat: validate Agent Skills conformance"
  ```

### Task 3: Add the declarative host registry schema

**Files:**
- Create: `agent-hosts.yaml`
- Create: `scripts/registry/host_registry.py`
- Create: `scripts/tests/test_host_registry.py`
- Modify: `scripts/registry/__main__.py`
- Modify: `scripts/registry/cli.py`
- Modify: `make/core.mk`

**Interfaces:**
- Consumes: `scripts.yaml_safety.load_unique_yaml_file` and the Phase 1
  `agent-hosts.yaml` schema.
- Produces: `HostRegistry`, `HostSpec`, `TargetSpec`, `SurfaceSpec`,
  `parse_host_registry(path: Path) -> HostRegistry`, and registry CLI command
  `python3 -m scripts.registry validate-hosts`.

- [ ] **Step 1: Write failing host-registry schema tests.**

  Cover a valid fixture containing Cursor, Claude, and Kiro local surfaces;
  duplicate host IDs; duplicate target IDs; unknown target reference; alias
  cycle; unsupported surface; unsupported discovery mode; unsupported
  verification state; unknown capability value; unknown path variable;
  project target missing `{project_root}`; user target containing
  `{project_root}`; `..` traversal; malformed evidence; and unknown top-level
  field. Assert `parse_host_registry` raises a deterministic `ValueError`
  naming the invalid field.

- [ ] **Step 2: Run schema tests to verify they fail for missing implementation.**

  Run:

  ```bash
  PYTHONPATH=. .venv/bin/python -m pytest -p no:cacheprovider scripts/tests/test_host_registry.py -q
  ```

  Expected result: collection fails because the host-registry module and
  `agent-hosts.yaml` do not yet exist.

- [ ] **Step 3: Implement typed host-registry parsing and validation.**

  Define frozen dataclasses for registry, targets, hosts, surfaces, discovery
  bindings, capabilities, isolation, constraints, and evidence. Validate
  schema version 1, reject unknown fields, resolve aliases without cycles,
  allow only `{project_root}` and `~` path variables, enforce scope/path
  consistency, and preserve `UNKNOWN` values without treating them as
  available. Use the existing YAML safety loader and deterministic sorted
  error reporting.

- [ ] **Step 4: Add the initial conservative registry data.**

  Represent existing Cursor, Claude, and Kiro user/project targets and local
  surfaces. Set verification to `UNVERIFIED` unless this repository already
  contains qualifying runtime evidence. Do not add unverified additional hosts
  or alter installer behavior.

- [ ] **Step 5: Wire host validation into the registry CLI and Make target.**

  Add `validate-hosts` without changing existing command output or semantics.
  Run it against the checked-in `agent-hosts.yaml`.

- [ ] **Step 6: Run focused, registry, and lint checks.**

  Run:

  ```bash
  PYTHONPATH=. .venv/bin/python -m pytest -p no:cacheprovider scripts/tests/test_host_registry.py scripts/tests/test_registry.py -q
  PYTHONPATH=. .venv/bin/python -m scripts.registry validate-hosts
  PATH="$PWD/.venv/bin:$PATH" make lint-python
  ```

  Expected result: all selected tests and commands pass with no lint errors.

- [ ] **Step 7: Commit the host registry foundation.**

  ```bash
  git add agent-hosts.yaml scripts/registry/host_registry.py scripts/tests/test_host_registry.py scripts/registry/__main__.py scripts/registry/cli.py make/core.mk
  git commit -m "feat: add declarative agent host registry"
  ```

### Phase 1 completion verification

- [ ] Run the full supported Python script suite with `PYTHONPATH=.` and the
  repository virtualenv, recording any pre-existing collection limitations.
- [ ] Run `PATH="$PWD/.venv/bin:$PATH" make lint-python`.
- [ ] Run `bash scripts/tests/test_install_integration.sh` and
  `bash scripts/tests/test_install_all_skills.sh` with the virtualenv Python
  first on `PATH`.
- [ ] Confirm `git diff --check` is clean and `git status --short` contains
  only intentional plan, registry, validator, and test changes.
