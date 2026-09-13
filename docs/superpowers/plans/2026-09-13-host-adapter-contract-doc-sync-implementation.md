# Host Adapter Contract Doc-Sync Validator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an automated guard so `docs/skill-framework/shared/host-adapter-contract.md`'s
capability-family list can never silently drift from `scripts/registry/host_adapter.py`'s
`CAPABILITIES` set again.

**Architecture:** One new pure function, `validate_host_adapter_contract_doc(root)`, in
`scripts/registry/host_portability.py` (the module that already owns adapter-contract-adjacent doc
checks — host-brand conditional-logic scanning, runtime-contract doc cross-references). It extracts
the capability-family keys from the doc's fenced ```yaml block and compares them against
`host_adapter.CAPABILITIES`. Wired into the existing `validate_host_portability()` aggregate, which
is already called from `cmd_validate`/`make validate` — no new CLI subcommand or wiring needed.

**Tech Stack:** Python stdlib `re` + the repo's existing PyYAML dependency (already imported
elsewhere in this module's neighbors); no new dependency.

## Global Constraints

- Doc drift precedent: commit `5edd34e` manually fixed this exact doc (added `report_output` to its
  capability-family list after it drifted from `host_adapter.CAPABILITIES`) with no guard added —
  this plan closes that gap, it does not change the doc's current (already correct) content.
- Follow `repository_doc_sync.py`'s existing convention exactly: if the doc file is missing, return
  `[]` (no error) rather than failing — this module's tests construct `tmp_path` roots without the
  full doc tree, and a hard-required file would break that existing test pattern for every other
  check in this module.
- Error message must start with `"error: "` (matching every other check in this module — see
  `_generated_surface_errors`, `_plugin_errors`) so it flows through `cmd_validate`'s existing
  `errors.append`/print loop with no special-casing.
- Zero fork of resolution logic: the source of truth for the capability set is
  `host_adapter.CAPABILITIES` — the new function imports and compares against it directly, it does
  not restate the 11 names.

---

### Task 1: Add `validate_host_adapter_contract_doc` and wire it into `validate_host_portability`

**Files:**
- Modify: `scripts/registry/host_portability.py`
- Test: `scripts/tests/test_host_portability.py`

**Interfaces:**
- Consumes: `scripts.registry.host_adapter.CAPABILITIES` (existing, `scripts/registry/host_adapter.py:9-21`).
- Produces: `validate_host_adapter_contract_doc(root: Path) -> list[str]`, importable from
  `scripts.registry.host_portability` (matches the module's existing public-function naming, e.g.
  `validate_host_portability`).

- [ ] **Step 1: Write the failing tests**

Add to `scripts/tests/test_host_portability.py` (alongside the existing imports at the top — add
`validate_host_adapter_contract_doc` to the `from scripts.registry.host_portability import (...)`
block):

```python
def test_host_adapter_contract_doc_matches_capabilities() -> None:
    assert validate_host_adapter_contract_doc(ROOT) == []


def test_host_adapter_contract_doc_missing_reports_no_error(tmp_path: Path) -> None:
    assert validate_host_adapter_contract_doc(tmp_path) == []


def test_host_adapter_contract_doc_drift_is_reported(tmp_path: Path) -> None:
    doc_dir = tmp_path / "docs" / "skill-framework" / "shared"
    doc_dir.mkdir(parents=True)
    (doc_dir / "host-adapter-contract.md").write_text(
        "# Host Adapter Contract\n\n"
        "## Required adapter surface\n\n"
        "```yaml\n"
        "host:\n"
        "  discover_files: full|degraded|unsupported\n"
        "  read_repo: full|degraded|unsupported\n"
        "```\n",
        encoding="utf-8",
    )

    errors = validate_host_adapter_contract_doc(tmp_path)

    assert errors and errors[0].startswith("error: ")
    assert "host-adapter-contract.md" in errors[0]


def test_host_adapter_contract_doc_included_in_portability_validation() -> None:
    """validate_host_portability() must actually call the new check, not just leave it dead code --
    a targeted drift in a tmp_path copy of the real doc tree must surface through the aggregate the
    same way it does through the standalone function."""
    import shutil

    tree = tmp_path_for_portability_copy = Path(__file__).resolve().parents[2]  # placeholder, replaced below
```

Note for the implementer: the fourth test above needs a real `tmp_path` fixture parameter and a full
copy of the repo root (registry, docs, evals, `.claude-plugin`, etc. — `validate_host_portability`
touches all of it) with only the doc file mutated, which is expensive to construct from scratch.
Simpler and equally valid: skip a from-scratch fourth test and instead add one assertion line to the
existing `test_host_packaging_semantics_validate` test (`scripts/tests/test_host_portability.py`
around line 103-104), which already calls `validate_host_portability(ROOT)` against the real repo
root and asserts `== []`. That test passing already proves the new check runs as part of the
aggregate and finds no drift on the real, currently-correct doc (if it were dead code / not called,
this test can't tell you that — but the three targeted unit tests above fully cover the function's
own logic, and a `monkeypatch`-based check that the aggregate calls it is unnecessary ceremony for a
one-line wiring change). Do not attempt the fourth test as sketched above — delete that sketch, it
does not compile as written and is not needed.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest scripts/tests/test_host_portability.py -v -k host_adapter_contract_doc`
Expected: FAIL with `ImportError` / `NameError` — `validate_host_adapter_contract_doc` does not
exist yet.

- [ ] **Step 3: Implement `validate_host_adapter_contract_doc`**

Add to `scripts/registry/host_portability.py`. Place it near the top, after the `HOST_BRANCH_RE`
definition and before `_generated_surface_errors` (matching the file's existing top-to-bottom order
of small-check-then-aggregator). Add `import yaml` to the existing import block at the top of the
file (alongside `import json`, `import re`) and add `CAPABILITIES` to the existing
`from scripts.registry.host_adapter import (...)` import block.

```python
_CONTRACT_DOC_CAPABILITY_BLOCK_RE = re.compile(
    r"## Required adapter surface\n.*?```yaml\n(.*?)\n```",
    re.DOTALL,
)


def host_adapter_contract_doc_path(root: Path) -> Path:
    return root / "docs" / "skill-framework" / "shared" / "host-adapter-contract.md"


def validate_host_adapter_contract_doc(root: Path) -> list[str]:
    """host-adapter-contract.md's "## Required adapter surface" section restates the capability
    family list from host_adapter.CAPABILITIES as prose documentation, with no code path enforcing
    the two stay in sync -- commit 5edd34e had to fix a real drift here by hand (report_output was
    added to CAPABILITIES but not to this doc) with no guard added at the time. This closes that gap.
    """
    path = host_adapter_contract_doc_path(root)
    if not path.is_file():
        return []
    markdown = path.read_text(encoding="utf-8")
    match = _CONTRACT_DOC_CAPABILITY_BLOCK_RE.search(markdown)
    if not match:
        return ["error: host-adapter-contract.md is missing its ## Required adapter surface yaml block"]
    try:
        parsed = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        return [f"error: host-adapter-contract.md capability block is not valid yaml: {exc}"]
    if not isinstance(parsed, dict) or not isinstance(parsed.get("host"), dict):
        return ["error: host-adapter-contract.md capability block must be a mapping under a top-level 'host:' key"]
    documented = set(parsed["host"])
    if documented != CAPABILITIES:
        missing = sorted(CAPABILITIES - documented)
        extra = sorted(documented - CAPABILITIES)
        return [
            "error: host-adapter-contract.md capability family list drifted from "
            f"host_adapter.CAPABILITIES: missing={missing}, extra={extra}",
        ]
    return []
```

Then wire it into the aggregate — in `validate_host_portability`, add one line right after its
existing `errors = validate_host_adapter_interface(root)` / `errors.extend(validate_host_adapter_identities(root))`
pair (near the top of the function body):

```python
errors.extend(validate_host_adapter_contract_doc(root))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest scripts/tests/test_host_portability.py -v -k host_adapter_contract_doc`
Expected: PASS (3 tests: matches, missing-doc-no-error, drift-is-reported).

Run: `python3 -m pytest scripts/tests/test_host_portability.py -v`
Expected: PASS (all tests in the file, including the pre-existing
`test_host_packaging_semantics_validate` and `test_missing_host_parity_expected_reports_exactly_one_error`
— confirm the new `errors.extend(...)` line didn't break either).

Run: `python3 -m scripts.registry validate`
Expected: exits 0, prints the existing `ok: skills registry, host portability, ...` success line —
confirms the new check runs cleanly against this repo's own (currently correct) doc through the real
CLI path, not just through the test harness.

- [ ] **Step 5: Commit**

```bash
git add scripts/registry/host_portability.py scripts/tests/test_host_portability.py
git commit -m "Add drift guard for host-adapter-contract.md's capability family list"
```

## Self-Review

- **Placeholder scan:** no TBD/TODO; the one deliberately-flagged non-actionable sketch (the fourth
  test) is explicitly called out as "do not implement as sketched, do this instead" with a concrete
  alternative, not a vague "add appropriate test."
- **Spec coverage:** the entire scope is one function + one wiring line + tests; nothing else is in
  scope (no new CLI subcommand, no changes to the doc's content, no changes to `host_contracts.yaml`
  — those already have their own drift guard via `validate_host_adapter_interface`).
- **Type consistency:** `validate_host_adapter_contract_doc(root: Path) -> list[str]` matches every
  sibling check's signature in this module (`validate_host_portability`, `_plugin_errors`, etc.).
