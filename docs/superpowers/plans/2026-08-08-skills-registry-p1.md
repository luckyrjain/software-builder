# Skills Registry (Milestone C) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce `skills.yaml` as the canonical platform registry and generate thin Cursor/Kiro adapters plus derived README/REPOSITORY inventories, with CI drift detection.

**Architecture:** `scripts/registry/` loads `skills.yaml` and merges each skill's `SKILL.md` frontmatter, validates split-ownership rules, and writes generated files. `make lint` runs `validate` before existing checks; `make generate --check` fails CI when committed outputs drift.

**Tech Stack:** Python 3.12, PyYAML (already in `requirements.lock`), pytest, Makefile.

## Global Constraints

- Keep imports at top of module (no inline imports).
- Do not implement registry-driven per-skill `make lint-*` recipes in this plan.
- Do not rewrite `scripts/install.sh` from registry data in this plan.
- Generated adapters must be thin (≤10 body lines); no duplicated routing/policy prose.
- Registry owns platform facts; `SKILL.md` owns `name`, `description`, `skill_version`, `disable-model-invocation`.
- `invocation: automation-only` ↔ `disable-model-invocation: true`.
- Exit codes: `0` ok, `1` validation/drift failure, `2` tooling error.
- Error format: `error: <skill-id>: <message>` on stderr; collect all errors per category.

**Spec:** `docs/superpowers/specs/2026-08-08-skills-registry-design.md`

---

## File map

| File | Responsibility |
|------|----------------|
| `skills.yaml` | Platform facts for all 22 skills |
| `scripts/__init__.py` | Enable `python3 -m scripts.registry` from repo root |
| `scripts/registry/__init__.py` | Package marker |
| `scripts/registry/__main__.py` | Delegates to `cli.main()` |
| `scripts/registry/models.py` | `SkillEntry`, `Registry` dataclasses |
| `scripts/registry/schema.py` | Parse/validate `skills.yaml` structure |
| `scripts/registry/frontmatter.py` | Parse `SKILL.md` YAML frontmatter |
| `scripts/registry/load.py` | Merge registry + frontmatter into `LoadedSkill` |
| `scripts/registry/crosscheck.py` | Split-ownership + graph validation |
| `scripts/registry/generate_cursor.py` | `.cursor/rules/<id>.mdc` |
| `scripts/registry/generate_kiro.py` | `.kiro/steering/<id>.md` |
| `scripts/registry/generate_docs.py` | README badge, REPOSITORY table, Mermaid |
| `scripts/registry/cli.py` | `validate`, `generate`, `generate --check` |
| `scripts/tests/test_registry.py` | Unit + golden tests |
| `generated/catalogue/install-deps.mmd` | Mermaid install graph |
| `Makefile` | `validate-registry`, `generate`, wire into `lint` |
| `CHANGELOG.md` | Platform section entry |

---

### Task 1: Registry schema and models

**Files:**
- Create: `scripts/__init__.py`
- Create: `scripts/registry/__init__.py`
- Create: `scripts/registry/models.py`
- Create: `scripts/registry/schema.py`
- Test: `scripts/tests/test_registry.py`

**Interfaces:**
- Produces: `parse_registry(path: Path) -> Registry`, `Registry.skills: dict[str, SkillEntry]`

- [ ] **Step 1: Write the failing test**

```python
# scripts/tests/test_registry.py
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.registry.schema import parse_registry  # noqa: E402


def test_parse_minimal_registry(tmp_path: Path) -> None:
    registry_file = tmp_path / "skills.yaml"
    registry_file.write_text(
        """
schema_version: 1
skills:
  squad-map:
    path: squad-map
    category: architecture
    invocation: ambient
    hosts:
      cursor: {discovery: rule}
      claude: {install: true}
      kiro: {discovery: manual}
    install:
      requires: []
    lint:
      skill_md_max_lines: 180
      target: squad-map
""",
        encoding="utf-8",
    )
    registry = parse_registry(registry_file)
    assert registry.schema_version == 1
    assert "squad-map" in registry.skills
    assert registry.skills["squad-map"].install.requires == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest scripts/tests/test_registry.py::test_parse_minimal_registry -q`  
Expected: FAIL (`ModuleNotFoundError` or `ImportError`)

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/registry/models.py
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class HostCursor:
    discovery: str  # rule | manual | always


@dataclass(frozen=True)
class HostClaude:
    install: bool = True


@dataclass(frozen=True)
class HostKiro:
    discovery: str  # manual | always


@dataclass(frozen=True)
class Hosts:
    cursor: HostCursor
    claude: HostClaude
    kiro: HostKiro


@dataclass(frozen=True)
class InstallSpec:
    requires: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LintSpec:
    skill_md_max_lines: int
    target: str


@dataclass(frozen=True)
class SkillEntry:
    path: str
    category: str
    invocation: str  # ambient | automation-only
    hosts: Hosts
    install: InstallSpec
    lint: LintSpec


@dataclass(frozen=True)
class Registry:
    schema_version: int
    skills: dict[str, SkillEntry]
```

```python
# scripts/registry/schema.py
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from scripts.registry.models import (
    HostClaude,
    HostCursor,
    HostKiro,
    Hosts,
    InstallSpec,
    LintSpec,
    Registry,
    SkillEntry,
)

ALLOWED_INVOCATION = {"ambient", "automation-only"}
ALLOWED_CURSOR_DISCOVERY = {"rule", "manual", "always"}
ALLOWED_KIRO_DISCOVERY = {"manual", "always"}


def _require_mapping(data: Any, label: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a mapping")
    return data


def parse_registry(path: Path) -> Registry:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    root = _require_mapping(raw, "skills.yaml root")
    schema_version = int(root.get("schema_version", 0))
    if schema_version != 1:
        raise ValueError(f"unsupported schema_version: {schema_version}")
    skills_raw = _require_mapping(root.get("skills"), "skills")
    skills: dict[str, SkillEntry] = {}
    for skill_id, entry_raw in skills_raw.items():
        entry = _require_mapping(entry_raw, f"skills.{skill_id}")
        invocation = str(entry.get("invocation", ""))
        if invocation not in ALLOWED_INVOCATION:
            raise ValueError(f"skills.{skill_id}.invocation invalid: {invocation!r}")
        hosts_raw = _require_mapping(entry.get("hosts"), f"skills.{skill_id}.hosts")
        cursor_raw = _require_mapping(hosts_raw.get("cursor"), f"skills.{skill_id}.hosts.cursor")
        kiro_raw = _require_mapping(hosts_raw.get("kiro"), f"skills.{skill_id}.hosts.kiro")
        claude_raw = hosts_raw.get("claude", {"install": True})
        claude_map = _require_mapping(claude_raw, f"skills.{skill_id}.hosts.claude")
        cursor_discovery = str(cursor_raw.get("discovery", ""))
        kiro_discovery = str(kiro_raw.get("discovery", ""))
        if cursor_discovery not in ALLOWED_CURSOR_DISCOVERY:
            raise ValueError(f"skills.{skill_id}.hosts.cursor.discovery invalid")
        if kiro_discovery not in ALLOWED_KIRO_DISCOVERY:
            raise ValueError(f"skills.{skill_id}.hosts.kiro.discovery invalid")
        install_raw = _require_mapping(entry.get("install"), f"skills.{skill_id}.install")
        requires = install_raw.get("requires", [])
        if not isinstance(requires, list):
            raise ValueError(f"skills.{skill_id}.install.requires must be a list")
        lint_raw = _require_mapping(entry.get("lint"), f"skills.{skill_id}.lint")
        skills[skill_id] = SkillEntry(
            path=str(entry.get("path", skill_id)),
            category=str(entry.get("category", "")),
            invocation=invocation,
            hosts=Hosts(
                cursor=HostCursor(discovery=cursor_discovery),
                claude=HostClaude(install=bool(claude_map.get("install", True))),
                kiro=HostKiro(discovery=kiro_discovery),
            ),
            install=InstallSpec(requires=[str(x) for x in requires]),
            lint=LintSpec(
                skill_md_max_lines=int(lint_raw.get("skill_md_max_lines", 180)),
                target=str(lint_raw.get("target", skill_id)),
            ),
        )
    return Registry(schema_version=schema_version, skills=skills)
```

Create empty `scripts/__init__.py` and `scripts/registry/__init__.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest scripts/tests/test_registry.py::test_parse_minimal_registry -q`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/__init__.py scripts/registry/ scripts/tests/test_registry.py
git commit -m "feat(registry): add skills.yaml schema parser and models"
```

---

### Task 2: Frontmatter loader and cross-check

**Files:**
- Create: `scripts/registry/frontmatter.py`
- Create: `scripts/registry/load.py`
- Create: `scripts/registry/crosscheck.py`
- Modify: `scripts/tests/test_registry.py`

**Interfaces:**
- Produces: `load_skill_frontmatter(path: Path) -> dict[str, str]`
- Produces: `load_all(root: Path) -> list[LoadedSkill]`
- Produces: `validate_registry(root: Path) -> list[str]` (error messages)

- [ ] **Step 1: Write failing tests**

```python
def test_crosscheck_rejects_name_mismatch(tmp_path: Path) -> None:
    skill_dir = tmp_path / "foo"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: not-foo\ndescription: test\n---\n",
        encoding="utf-8",
    )
    registry_file = tmp_path / "skills.yaml"
    registry_file.write_text(
        """
schema_version: 1
skills:
  foo:
    path: foo
    category: testing
    invocation: ambient
    hosts:
      cursor: {discovery: rule}
      claude: {install: true}
      kiro: {discovery: manual}
    install:
      requires: []
    lint:
      skill_md_max_lines: 180
      target: foo
""",
        encoding="utf-8",
    )
    from scripts.registry.crosscheck import validate_registry  # noqa: E402

    errors = validate_registry(tmp_path)
    assert any("name mismatch" in e for e in errors)


def test_crosscheck_detects_install_cycle(tmp_path: Path) -> None:
    for skill_id in ("a", "b"):
        d = tmp_path / skill_id
        d.mkdir()
        (d / "SKILL.md").write_text(
            f"---\nname: {skill_id}\ndescription: test\n---\n",
            encoding="utf-8",
        )
    (tmp_path / "skills.yaml").write_text(
        """
schema_version: 1
skills:
  a:
    path: a
    category: testing
    invocation: ambient
    hosts:
      cursor: {discovery: rule}
      claude: {install: true}
      kiro: {discovery: manual}
    install: {requires: [b]}
    lint: {skill_md_max_lines: 180, target: a}
  b:
    path: b
    category: testing
    invocation: ambient
    hosts:
      cursor: {discovery: rule}
      claude: {install: true}
      kiro: {discovery: manual}
    install: {requires: [a]}
    lint: {skill_md_max_lines: 180, target: b}
""",
        encoding="utf-8",
    )
    from scripts.registry.crosscheck import validate_registry  # noqa: E402

    errors = validate_registry(tmp_path)
    assert any("cycle" in e for e in errors)
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `python3 -m pytest scripts/tests/test_registry.py -q -k crosscheck`  
Expected: FAIL

- [ ] **Step 3: Implement frontmatter + crosscheck**

```python
# scripts/registry/frontmatter.py
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def load_skill_frontmatter(skill_md: Path) -> dict[str, Any]:
    text = skill_md.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError(f"missing YAML frontmatter: {skill_md}")
    data = yaml.safe_load(match.group(1))
    if not isinstance(data, dict):
        raise ValueError(f"frontmatter must be a mapping: {skill_md}")
    return data
```

```python
# scripts/registry/crosscheck.py
from __future__ import annotations

from pathlib import Path

from scripts.registry.frontmatter import load_skill_frontmatter
from scripts.registry.schema import parse_registry


def _detect_cycles(skills: dict[str, list[str]]) -> list[str]:
    errors: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def dfs(node: str, stack: list[str]) -> None:
        if node in visiting:
            errors.append(f"error: install graph: cycle detected: {' -> '.join(stack + [node])}")
            return
        if node in visited:
            return
        visiting.add(node)
        for dep in skills.get(node, []):
            dfs(dep, stack + [node])
        visiting.remove(node)
        visited.add(node)

    for skill_id in skills:
        dfs(skill_id, [])
    return errors


def validate_registry(root: Path) -> list[str]:
    errors: list[str] = []
    registry_path = root / "skills.yaml"
    registry = parse_registry(registry_path)

    skill_dirs = {
        p.parent.name
        for p in root.glob("*/SKILL.md")
        if p.parent.is_dir() and not p.parent.name.startswith(".")
    }
    registry_ids = set(registry.skills.keys())

    for orphan in sorted(skill_dirs - registry_ids):
        errors.append(f"error: {orphan}: directory has SKILL.md but no registry entry")
    for missing in sorted(registry_ids - skill_dirs):
        errors.append(f"error: {missing}: registry entry has no SKILL.md directory")

    install_graph: dict[str, list[str]] = {}
    for skill_id, entry in registry.skills.items():
        install_graph[skill_id] = list(entry.install.requires)
        for dep in entry.install.requires:
            if dep not in registry.skills:
                errors.append(f"error: {skill_id}: install.requires unknown skill {dep!r}")

    errors.extend(_detect_cycles(install_graph))

    for skill_id, entry in registry.skills.items():
        skill_md = root / entry.path / "SKILL.md"
        try:
            fm = load_skill_frontmatter(skill_md)
        except ValueError as exc:
            errors.append(f"error: {skill_id}: {exc}")
            continue
        fm_name = str(fm.get("name", ""))
        if fm_name != skill_id:
            errors.append(f"error: {skill_id}: name mismatch (SKILL.md name={fm_name!r})")
        if "description" not in fm:
            errors.append(f"error: {skill_id}: SKILL.md missing description")
        disable = fm.get("disable-model-invocation") is True
        auto_only = entry.invocation == "automation-only"
        if disable != auto_only:
            errors.append(
                f"error: {skill_id}: disable-model-invocation={disable} "
                f"but invocation={entry.invocation!r}",
            )
    return errors
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `python3 -m pytest scripts/tests/test_registry.py -q -k crosscheck`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(registry): add frontmatter loader and cross-check validation"
```

---

### Task 3: Bootstrap `skills.yaml` for all 22 skills

**Files:**
- Create: `skills.yaml`
- Test: extend `scripts/tests/test_registry.py`

**Interfaces:**
- Consumes: `validate_registry(root)` from Task 2

- [ ] **Step 1: Write failing integration test**

```python
def test_bootstrap_registry_validates_on_real_repo() -> None:
    from scripts.registry.crosscheck import validate_registry  # noqa: E402

    errors = validate_registry(ROOT)
    assert errors == [], "\n".join(errors)
```

- [ ] **Step 2: Run test — expect FAIL** (no `skills.yaml` yet)

- [ ] **Step 3: Create `skills.yaml`**

Create `skills.yaml` at repo root with all 22 skills. Use these `install.requires` edges (from current `Makefile`):

| Skill | requires |
|-------|----------|
| `pr-review` | `[]` |
| `pr-gatekeeper` | `[pr-review]` |
| `k8s-overprovisioning-datadog` | `[]` |
| `incident-rca` | `[]` |
| `incident-triage-agent` | `[incident-rca, squad-map]` |
| `domain-comprehension` | `[squad-map]` |
| `squad-map` | `[]` |
| `who-owns-x-bot` | `[squad-map]` |
| `new-hire-guide` | `[domain-comprehension, squad-map]` |
| `release-readiness-checker` | `[pr-review, k8s-overprovisioning-datadog, incident-rca]` |
| `migration-program-manager` | `[mysql-to-postgres-sql, squad-map]` |
| `cost-optimization-sprint-planner` | `[k8s-overprovisioning-datadog, squad-map]` |
| `mysql-to-postgres-sql` | `[]` |
| `loop-task-implementer` | `[]` |
| `backlog-runner` | `[loop-task-implementer]` |
| `weekly-squad-digest` | `[migration-program-manager, cost-optimization-sprint-planner]` |
| `unit-test-creator` | `[]` |
| `integration-test-creator` | `[]` |
| `contract-test-creator` | `[]` |
| `e2e-test-creator` | `[]` |
| `api-test-creator` | `[]` |
| `test-writer` | `[unit-test-creator, integration-test-creator, contract-test-creator, e2e-test-creator, api-test-creator]` |

Set `invocation: automation-only` for: `pr-gatekeeper`, `incident-triage-agent`, `who-owns-x-bot`, `backlog-runner`, `weekly-squad-digest`.

Set `lint.skill_md_max_lines: 150` and `lint.target: k8s-skill` only for `k8s-overprovisioning-datadog`.

Use categories: `review`, `incident`, `platform`, `architecture`, `release`, `migration`, `automation`, `testing` as appropriate.

Default hosts for every skill:

```yaml
hosts:
  cursor: {discovery: rule}
  claude: {install: true}
  kiro: {discovery: manual}
```

- [ ] **Step 4: Run test — expect PASS**

Run: `python3 -m pytest scripts/tests/test_registry.py::test_bootstrap_registry_validates_on_real_repo -q`

- [ ] **Step 5: Commit**

```bash
git add skills.yaml scripts/tests/test_registry.py
git commit -m "feat(registry): bootstrap skills.yaml for all 22 skills"
```

---

### Task 4: Cursor adapter generator

**Files:**
- Create: `scripts/registry/generate_cursor.py`
- Test: `scripts/tests/test_registry.py`

**Interfaces:**
- Produces: `render_cursor_rule(skill_id: str, description: str, discovery: str) -> str`
- Produces: `generate_cursor_rules(root: Path, registry: Registry, descriptions: dict[str, str]) -> dict[Path, str]`

- [ ] **Step 1: Write golden test**

```python
def test_render_cursor_rule_thin_wrapper() -> None:
    from scripts.registry.generate_cursor import render_cursor_rule  # noqa: E402

    text = render_cursor_rule("squad-map", "Map repos to squads.", "rule")
    assert "GENERATED from skills.yaml" in text
    assert "squad-map/SKILL.md" in text
    assert "mock" not in text.lower()
    assert text.count("\n") < 15
    assert "alwaysApply: false" in text
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement generator**

```python
# scripts/registry/generate_cursor.py
from __future__ import annotations

from pathlib import Path

from scripts.registry.models import Registry


def _first_line(description: str) -> str:
    return description.strip().splitlines()[0].strip()


def render_cursor_rule(skill_id: str, description: str, discovery: str) -> str:
    always_apply = "true" if discovery == "always" else "false"
    body_lines = [
        f"Invoke the {skill_id} skill. Read `{skill_id}/SKILL.md` and follow it.",
    ]
    phase_index = f"{skill_id}/reference/phase-index.md"
    body_lines.append(
        f"Phase index: `{phase_index}` when present under the skill directory.",
    )
    return (
        "---\n"
        f'description: {_first_line(description)}\n'
        f"alwaysApply: {always_apply}\n"
        "---\n\n"
        "<!-- GENERATED from skills.yaml + SKILL.md — do not edit; run make generate -->\n\n"
        + "\n".join(body_lines)
        + "\n"
    )


def generate_cursor_rules(
    root: Path,
    registry: Registry,
    descriptions: dict[str, str],
) -> dict[Path, str]:
    outputs: dict[Path, str] = {}
    for skill_id, entry in sorted(registry.skills.items()):
        out_path = root / ".cursor" / "rules" / f"{skill_id}.mdc"
        outputs[out_path] = render_cursor_rule(
            skill_id,
            descriptions[skill_id],
            entry.hosts.cursor.discovery,
        )
    return outputs
```

- [ ] **Step 4: Run test — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add scripts/registry/generate_cursor.py scripts/tests/test_registry.py
git commit -m "feat(registry): add Cursor adapter generator"
```

---

### Task 5: Kiro adapter generator

**Files:**
- Create: `scripts/registry/generate_kiro.py`
- Test: `scripts/tests/test_registry.py`

- [ ] **Step 1: Golden test**

```python
def test_render_kiro_steering_thin_wrapper() -> None:
    from scripts.registry.generate_kiro import render_kiro_steering  # noqa: E402

    text = render_kiro_steering("squad-map", "manual")
    assert "GENERATED from skills.yaml" in text
    assert "squad-map/SKILL.md" in text
    assert "inclusion: manual" in text
```

- [ ] **Step 2–4: Implement + pass**

```python
# scripts/registry/generate_kiro.py
from __future__ import annotations

from pathlib import Path

from scripts.registry.models import Registry


def render_kiro_steering(skill_id: str, discovery: str) -> str:
    inclusion = "always" if discovery == "always" else "manual"
    return (
        "---\n"
        f"inclusion: {inclusion}\n"
        "---\n\n"
        "<!-- GENERATED from skills.yaml + SKILL.md — do not edit; run make generate -->\n\n"
        f"For {skill_id}, read `{skill_id}/SKILL.md` and follow it.\n"
    )


def generate_kiro_steering(root: Path, registry: Registry) -> dict[Path, str]:
    return {
        root / ".kiro" / "steering" / f"{skill_id}.md": render_kiro_steering(
            skill_id,
            entry.hosts.kiro.discovery,
        )
        for skill_id, entry in sorted(registry.skills.items())
    }
```

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(registry): add Kiro steering generator"
```

---

### Task 6: Docs and Mermaid generators

**Files:**
- Create: `scripts/registry/generate_docs.py`
- Modify: `README.md` (add `<!-- skills-count:start -->22<!-- skills-count:end -->` markers)
- Modify: `docs/REPOSITORY.md` (add `<!-- registry-skills-table:start/end -->` markers)
- Create: `generated/catalogue/install-deps.mmd` (via generate)

**Interfaces:**
- Produces: `update_readme_badge(readme: str, count: int) -> str`
- Produces: `render_skills_table(registry: Registry) -> str`
- Produces: `render_install_mermaid(registry: Registry) -> str`

- [ ] **Step 1: Test table + mermaid rendering**

```python
def test_render_install_mermaid_includes_edge() -> None:
    from scripts.registry.generate_docs import render_install_mermaid  # noqa: E402
    from scripts.registry.models import (
        HostClaude, HostCursor, HostKiro, Hosts, InstallSpec, LintSpec, Registry, SkillEntry,
    )

    registry = Registry(
        schema_version=1,
        skills={
            "child": SkillEntry(
                path="child",
                category="testing",
                invocation="ambient",
                hosts=Hosts(
                    cursor=HostCursor("rule"),
                    claude=HostClaude(True),
                    kiro=HostKiro("manual"),
                ),
                install=InstallSpec(requires=["parent"]),
                lint=LintSpec(180, "child"),
            ),
            "parent": SkillEntry(
                path="parent",
                category="testing",
                invocation="ambient",
                hosts=Hosts(
                    cursor=HostCursor("rule"),
                    claude=HostClaude(True),
                    kiro=HostKiro("manual"),
                ),
                install=InstallSpec(requires=[]),
                lint=LintSpec(180, "parent"),
            ),
        },
    )
    mermaid = render_install_mermaid(registry)
    assert "child --> parent" in mermaid or "parent --> child" in mermaid
```

Implement `generate_docs.py` with marker replacement for README and REPOSITORY, and Mermaid `graph TD` with edges `parent --> child` for each `install.requires` entry.

- [ ] **Step 2: Add markers to README and REPOSITORY** (manual edit once)

README line 4:

```markdown
![Skills](https://img.shields.io/badge/skills-<!-- skills-count:start -->22<!-- skills-count:end -->-blue)
```

Add empty table markers in `docs/REPOSITORY.md` under Layout or a new `## Skill registry` subsection.

- [ ] **Step 3: Run tests — PASS**

- [ ] **Step 4: Commit**

```bash
git add scripts/registry/generate_docs.py README.md docs/REPOSITORY.md scripts/tests/test_registry.py
git commit -m "feat(registry): add README/REPOSITORY/Mermaid doc generators"
```

---

### Task 7: CLI (`validate`, `generate`, `--check`)

**Files:**
- Create: `scripts/registry/load.py`
- Create: `scripts/registry/cli.py`
- Create: `scripts/registry/__main__.py`

**Interfaces:**
- Produces: `main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Test generate --check drift detection**

```python
def test_generate_check_fails_when_readme_drift(tmp_path: Path, monkeypatch) -> None:
    # copy minimal fixture tree with skills.yaml + one skill + README markers
    # run cli generate --check before writing => fail
    # run cli generate => pass
    ...
```

(Fill fixture in implementation — use `tmp_path` copy of minimal 1-skill registry.)

- [ ] **Step 2: Implement CLI**

```python
# scripts/registry/cli.py (structure)
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scripts.registry")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    gen = sub.add_parser("generate")
    gen.add_argument("--check", action="store_true")
    ...
```

`validate`: run `validate_registry(ROOT)`; print errors; return 1 if any.

`generate`: load descriptions from all `SKILL.md`; build all output dicts; write files (or diff in `--check` mode using `filecmp` or unified diff).

`__main__.py`:

```python
from scripts.registry.cli import main
raise SystemExit(main())
```

- [ ] **Step 3: Run full validate on repo**

Run: `python3 -m scripts.registry validate`  
Expected: PASS (after skills.yaml from Task 3)

- [ ] **Step 4: Commit**

```bash
git commit -am "feat(registry): add validate/generate CLI with --check drift gate"
```

---

### Task 8: Run generators and wire Makefile

**Files:**
- Modify: `Makefile`
- Modify: all `.cursor/rules/*.mdc` (22 files)
- Modify: all `.kiro/steering/*.md` (22 files)
- Modify: `generated/catalogue/install-deps.mmd`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add Makefile targets**

```makefile
validate-registry:
	@python3 -m scripts.registry validate

generate:
	@python3 -m scripts.registry generate

generate-check:
	@python3 -m scripts.registry generate --check
```

Prepend `validate-registry` to the `lint:` prerequisite list (before `lint-framework`).

Add `generate-check` to `lint-framework` pytest section OR as separate lint step after validate-registry.

- [ ] **Step 2: Run generate**

```bash
make generate
```

- [ ] **Step 3: Verify thin adapters**

Spot-check: no generated `.mdc` file should exceed 15 lines total; no `mock`, `routing to`, or `never modifies` policy phrases copied from old adapters.

- [ ] **Step 4: Run full lint**

```bash
make lint
```

Expected: PASS

- [ ] **Step 5: Update CHANGELOG.md** (Platform section)

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(registry): generate thin adapters and wire validate-registry into lint"
```

---

### Task 9: Final verification and PR

- [ ] **Step 1: Run registry tests**

```bash
python3 -m pytest scripts/tests/test_registry.py -q
```

- [ ] **Step 2: Run generate --check**

```bash
make generate-check
```

Expected: PASS (no drift)

- [ ] **Step 3: Manual smoke — add skill #23 drill (optional local only)**

Confirm workflow: new dir + registry entry + `make generate` updates adapters without hand edits.

- [ ] **Step 4: Open PR**

Title: `feat(registry): skills.yaml with generated adapters and inventories (#12)`

Body: reference spec, list generated surfaces, note Makefile install targets unchanged in v1.

---

## Spec self-review

| Spec requirement | Task |
|------------------|------|
| `skills.yaml` platform registry | Task 3 |
| Split ownership cross-check | Task 2 |
| Thin Cursor adapters | Task 4, 8 |
| Thin Kiro steering | Task 5, 8 |
| README badge markers | Task 6, 8 |
| REPOSITORY table markers | Task 6, 8 |
| Install Mermaid graph | Task 6, 8 |
| `validate` / `generate --check` CLI | Task 7 |
| `make lint` integration | Task 8 |
| Tests per design | Tasks 1–7, 9 |
| Makefile install unchanged | Explicit non-goal |
| No capabilities fields | Explicit non-goal |

No TBD placeholders remain in task steps that lack implementation detail (Task 7 drift test uses abbreviated fixture note — implementer copies Task 1–6 patterns).

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-08-skills-registry-p1.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
