# Universal Agent Compatibility — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the concrete, code-level gaps identified in the 2026-09-12 global-deployability audit of `d5ddcbd`, starting with the foundational per-surface capability model that every other gap (installers, CLI, distribution) depends on.

**Architecture:** Extend the existing declarative registries (`agent-hosts.yaml` + `scripts/registry/host_registry.py` + `scripts/registry/compatibility_resolver.py`) rather than replacing them — the codebase already names this exact next step as "Candidate 2" in its own docstrings and has a `doctor.py --surface` flag stubbed out and waiting for it. Two follow-on cleanups (a capability-family conflation and a version-drift gap) are bundled first because they're small, independent, and already flagged in the audit.

**Tech Stack:** Python 3, pytest, PyYAML (via `scripts/yaml_safety`), Make.

## Global Constraints

- Every new/changed validator must be wired into `make lint-static` (see `make/core.mk`) so it runs in CI, not just locally.
- Match existing code style exactly: frozen dataclasses, `errors: list[str]` accumulation (never raise mid-parse), `_unknown_fields` rejection of undeclared YAML keys, module docstrings that explain *why*, not *what*.
- No new dependencies. No schema break for existing `agent-hosts.yaml` entries — every change below is additive and backward-compatible (existing YAML with no `surfaces[].capabilities` block must parse identically to today).
- Do not collapse `agent-hosts.yaml` and `host_contracts.yaml` into one file. Re-read `agent-hosts.yaml:1-15` before touching either — the split is a deliberate, documented design (evidence-gated host identity vs. generated-adapter capability matrix), not the bug the audit's phrasing implies. Confirm this with the user before any future task proposes merging them.

---

## Important scope note (read before executing)

The audit's own "Recommended implementation order" spans 7 phases — a real CLI, signed multi-channel releases, provider profiles, enterprise rollout, and more. Those are legitimate program-level workstreams, but they involve API/UX decisions (CLI verb surface, signing infra, org policy shape) that need the maintainer's sign-off on the *shape* before any TDD task can be written without guessing. Writing speculative bite-sized code for them now would be exactly the kind of premature, unrequested design this repo's own CLAUDE.md warns against.

This plan therefore fully details only **Phase 0** (three small, independent, already-flagged fixes) and **Phase 1** (the per-surface capability model — Candidate 2 — which is the one piece everything else in the audit's Critical row depends on). Phases 2–7 are captured as a roadmap with concrete file pointers and open decisions, each meant to become its own plan once the maintainer picks a direction.

---

## Phase 0 — Independent quick wins

### Task 1: Plugin-version-sync validator

`.codex-plugin/plugin.json` is pinned at `"version": "0.1.0"` while `VERSION` (the repo's canonical distribution version, read by `scripts/release_info.read_distribution_version`) is `1.4.0`. Nothing catches this drift today.

**Files:**
- Create: `scripts/check_plugin_version_sync.py`
- Modify: `make/core.mk` (add target, add to `lint-static` prerequisite chain)
- Test: `scripts/tests/test_check_plugin_version_sync.py`

**Interfaces:**
- Consumes: `scripts.release_info.read_distribution_version(root: Path | None = None) -> str` (existing, `scripts/release_info.py:34`)
- Produces: `drifted_plugin_versions(repo_root: Path) -> list[str]` — human-readable mismatch messages, empty list means clean. `main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: Write the failing test**

```python
# scripts/tests/test_check_plugin_version_sync.py
"""Tests for scripts/check_plugin_version_sync.py."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.check_plugin_version_sync import drifted_plugin_versions, main


def _write_repo(tmp_path: Path, *, distribution_version: str, plugin_version: str) -> Path:
    (tmp_path / "VERSION").write_text(f"{distribution_version}\n", encoding="utf-8")
    plugin_dir = tmp_path / ".codex-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(
        json.dumps({"name": "software-builder", "version": plugin_version}),
        encoding="utf-8",
    )
    return tmp_path


def test_matching_versions_report_no_drift(tmp_path: Path) -> None:
    repo = _write_repo(tmp_path, distribution_version="1.4.0", plugin_version="1.4.0")
    assert drifted_plugin_versions(repo) == []


def test_mismatched_versions_are_reported(tmp_path: Path) -> None:
    repo = _write_repo(tmp_path, distribution_version="1.4.0", plugin_version="0.1.0")
    errors = drifted_plugin_versions(repo)
    assert len(errors) == 1
    assert ".codex-plugin/plugin.json" in errors[0]
    assert "0.1.0" in errors[0]
    assert "1.4.0" in errors[0]


def test_missing_plugin_manifest_is_ignored(tmp_path: Path) -> None:
    (tmp_path / "VERSION").write_text("1.4.0\n", encoding="utf-8")
    assert drifted_plugin_versions(tmp_path) == []


def test_main_exits_nonzero_on_drift(tmp_path: Path, capsys) -> None:
    repo = _write_repo(tmp_path, distribution_version="1.4.0", plugin_version="0.1.0")
    exit_code = main(["--repo-root", str(repo)])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "0.1.0" in captured.err


def test_main_exits_zero_when_clean(tmp_path: Path) -> None:
    repo = _write_repo(tmp_path, distribution_version="1.4.0", plugin_version="1.4.0")
    assert main(["--repo-root", str(repo)]) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest scripts/tests/test_check_plugin_version_sync.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.check_plugin_version_sync'`

- [ ] **Step 3: Write minimal implementation**

```python
#!/usr/bin/env python3
"""Fail when a native-plugin manifest's version has drifted from the repo's distribution VERSION.

`.codex-plugin/plugin.json` (and any future `.claude-plugin/plugin.json`) carries its own
`"version"` field, independent of the root `VERSION` file `scripts/release_info.py` treats as
canonical. Nothing enforced the two stay equal, so `.codex-plugin/plugin.json` drifted to
`0.1.0` while `VERSION` moved on to `1.4.0` — this script closes that gap the same way
`scripts/check_pinned_actions.py` closes its own drift risk: a hard-fail, not a silent gate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.release_info import read_distribution_version  # noqa: E402

# Every native-plugin manifest whose "version" field must track VERSION. Add a path here
# (not a second, hand-copied check) when a future plugin bundle (e.g. .claude-plugin) gains
# its own versioned manifest.
PLUGIN_MANIFESTS: tuple[str, ...] = (".codex-plugin/plugin.json",)


def drifted_plugin_versions(repo_root: Path) -> list[str]:
    """One message per plugin manifest whose version does not match VERSION.

    A manifest that does not exist yet is skipped, not an error -- this check guards drift in
    manifests that exist, it does not mandate that every listed path be present (that's
    scripts/check_platform_files.py's job for load-bearing files).
    """
    try:
        distribution_version = read_distribution_version(repo_root)
    except ValueError as exc:
        return [str(exc)]

    errors: list[str] = []
    for relpath in PLUGIN_MANIFESTS:
        manifest_path = repo_root / relpath
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{relpath}: invalid JSON ({exc})")
            continue
        plugin_version = manifest.get("version")
        if plugin_version != distribution_version:
            errors.append(
                f"{relpath}: version {plugin_version!r} does not match VERSION "
                f"{distribution_version!r} -- bump {relpath} to match on every release"
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check_plugin_version_sync")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    args = parser.parse_args(argv)

    errors = drifted_plugin_versions(args.repo_root)
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest scripts/tests/test_check_plugin_version_sync.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Wire into `make lint-static`**

In `make/core.mk`, add near `lint-actions-pinning`:

```makefile
lint-plugin-version-sync:
	@python3 scripts/check_plugin_version_sync.py
```

Add `lint-plugin-version-sync` to the `.PHONY:` line that already lists `lint-static lint-suites lint-framework-tests lint-scripts-shellcheck lint-platform-files`, and add it to the `lint-static:` prerequisite chain (the long line at `make/core.mk:215`).

- [ ] **Step 6: Fix the actual drift and verify the new check passes against the real repo**

Run: `python3 -c "import json,pathlib; p=pathlib.Path('.codex-plugin/plugin.json'); d=json.loads(p.read_text()); d['version']='1.4.0'; p.write_text(json.dumps(d, indent=2)+'\n')"`
Run: `make lint-plugin-version-sync`
Expected: no output, exit 0

- [ ] **Step 7: Commit**

```bash
git add scripts/check_plugin_version_sync.py scripts/tests/test_check_plugin_version_sync.py make/core.mk .codex-plugin/plugin.json
git commit -m "$(cat <<'EOF'
Add plugin-manifest version-sync validator

.codex-plugin/plugin.json had drifted to 0.1.0 while VERSION moved to
1.4.0 with nothing catching it. Add a lint-static check plus fix the
current drift.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Split `host.report.write` out of the `write_repo` capability family

`scripts/registry/host_adapter.py:52` maps the skill-facing capability `host.report.write` directly onto the adapter-generation family `write_repo`. A chat-output-only or artifact-output review skill that only ever declares `host.report.write` is therefore treated as needing full repository write access — on a host like `chatgpt` (`write_repo: degraded` in `host_contracts.yaml`) this can wrongly demote or block a skill that never touches the repository at all.

**Files:**
- Modify: `scripts/registry/host_adapter.py:38-55` (add a new family, repoint the mapping)
- Modify: `scripts/registry/capability_families.yaml` (add the new family so `capability_family_sync.py`'s cross-check stays green — inspect current schema before editing, see Step 1)
- Test: `scripts/tests/test_host_adapter.py` (existing file — extend it)

**Interfaces:**
- Consumes: existing `HOST_CAPABILITY_FAMILIES: dict[str, tuple[str, ...]]` in `scripts/registry/host_adapter.py`
- Produces: new family name `report_output` in that same dict, referenced by `host_contracts.yaml`'s per-host `support:` blocks (every host needs a `report_output:` entry once the family exists — see Step 3)

- [ ] **Step 1: Read the current cross-check before editing anything**

Run: `python3 -m pytest scripts/tests/test_host_adapter.py scripts/tests/test_compatibility_resolver.py -v` (confirm current green baseline)
Run: `sed -n '1,40p' scripts/registry/capability_family_sync.py` (confirm how `capability_families.yaml`'s list is cross-checked against `host_adapter.CAPABILITIES` / `HOST_CAPABILITY_FAMILIES` — this determines exactly which two files below must agree)

- [ ] **Step 2: Write the failing test**

```python
# add to scripts/tests/test_host_adapter.py
def test_report_write_capability_is_not_a_full_repo_write_family() -> None:
    from scripts.registry.host_adapter import CAPABILITIES, HOST_CAPABILITY_FAMILIES

    assert "report_output" in CAPABILITIES
    assert HOST_CAPABILITY_FAMILIES["host.report.write"] == ("report_output",)
    assert HOST_CAPABILITY_FAMILIES["host.repository.read_write"] == ("read_repo", "write_repo")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 -m pytest scripts/tests/test_host_adapter.py -k report_write -v`
Expected: FAIL — `KeyError` or `AssertionError` (current mapping is `("write_repo",)`)

- [ ] **Step 4: Add the family and repoint the mapping**

In `scripts/registry/host_adapter.py`, add `"report_output"` to the `CAPABILITIES` set (alongside `discover_files`, `read_repo`, etc.) and change:

```python
    "host.report.write": ("write_repo",),
```
to:
```python
    "host.report.write": ("report_output",),
```

In `scripts/registry/capability_families.yaml`, add `report_output` to the `capability_families:` list, then add a `report_output:` line to every host's `support:` block in `host_contracts.yaml` — set it to `full` for every host that can render/output a report today (all six hosts: `cursor`, `claude`, `codex`, `chatgpt`, `kiro`, `generic` can all produce chat/file output; none of this family's semantics require repository write), matching the file's existing `full`/`degraded`/`unsupported` vocabulary.

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest scripts/tests/test_host_adapter.py -k report_write -v`
Expected: PASS

- [ ] **Step 6: Run the full existing suite to catch any skill wrongly relying on the old conflation**

Run: `python3 -m pytest scripts/tests/ -k "host_adapter or compatibility_resolver or capability_family" -v`
Run: `python3 -m scripts.registry validate-agent-skills`
Expected: all green. If any skill's resolved status changes (a skill that declared `host.report.write` as required and was previously silently satisfied by `write_repo` on a host where only `report_output` is now `full`), that is the bug this task exists to surface — investigate that skill's `skills.yaml` entry rather than reverting the family split.

- [ ] **Step 7: Commit**

```bash
git add scripts/registry/host_adapter.py scripts/registry/capability_families.yaml scripts/registry/host_contracts.yaml scripts/tests/test_host_adapter.py
git commit -m "$(cat <<'EOF'
Split host.report.write into its own report_output capability family

host.report.write was mapped onto the write_repo family, so a
chat/artifact-output-only skill was evaluated as if it needed full
repository write access -- wrongly BLOCKED/DEGRADED on hosts where
write_repo is degraded but report output is fully supported.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Phase 1 — Per-surface capabilities (Candidate 2)

This is the audit's top Critical item, and the codebase already names it: `compatibility_resolver.py`'s own module docstring calls out "Candidate 2's schema" as the extension point, and `doctor.py --surface` (`scripts/doctor.py:234-239`) is already stubbed with a note that it "does not yet change which capabilities are considered available." This phase finishes exactly that, additively.

**Design decision (stated, not hidden):** `HostSpec.capabilities` (host-level) stays as the default/fallback. A surface may declare its own `capabilities:` block; where present, a capability name declared at the surface level overrides the host-level value for that name only — anything not mentioned at the surface level still falls back to the host-level declaration. This keeps every existing `agent-hosts.yaml` entry (none of which declare per-surface capabilities today) parsing to the exact same resolved capabilities as before.

### Task 3: Extend `agent-hosts.yaml` schema to accept per-surface capabilities

**Files:**
- Modify: `scripts/registry/host_registry.py`
- Test: `scripts/tests/test_host_registry.py`

**Interfaces:**
- Consumes: existing `CapabilitySpec`, `_parse_capabilities`, `_unknown_fields`
- Produces: `SurfaceSpec.capabilities: CapabilitySpec` (new field, defaults to `CapabilitySpec()` i.e. empty — meaning "no override, use host-level")

- [ ] **Step 1: Write the failing test**

```python
# add to scripts/tests/test_host_registry.py
def test_surface_level_capabilities_override_host_level() -> None:
    raw = {
        "schema_version": 1,
        "targets": [{"id": "claude-user", "scope": "user", "path": "~/.claude/skills"}],
        "hosts": [
            {
                "id": "claude",
                "surfaces": [
                    {
                        "kind": "LOCAL",
                        "discovery": [
                            {"target": "claude-user", "mode": "NATIVE", "precedence": 10}
                        ],
                        "capabilities": {
                            "host.repository.read_write": "AVAILABLE",
                        },
                    },
                    {
                        "kind": "CLOUD",
                        "discovery": [
                            {"target": "claude-user", "mode": "NATIVE", "precedence": 10}
                        ],
                        "capabilities": {
                            "host.repository.read_write": "UNAVAILABLE",
                        },
                    },
                ],
                "capabilities": {
                    "host.filesystem.read": "AVAILABLE",
                    "host.repository.read_write": "UNKNOWN",
                },
                "isolation": {"mode": "UNKNOWN"},
                "constraints": [],
                "verification": "UNVERIFIED",
                "evidence": [],
                "maintainer_support": "BEST_EFFORT",
            }
        ],
    }
    path = tmp_path_write_registry(raw)  # see existing helper in this test file; adapt name if different
    registry = parse_host_registry(path)
    host = registry.hosts["claude"]

    local_surface = next(s for s in host.surfaces if s.kind == "LOCAL")
    cloud_surface = next(s for s in host.surfaces if s.kind == "CLOUD")
    assert local_surface.capabilities.state_for("host.repository.read_write") == "AVAILABLE"
    assert cloud_surface.capabilities.state_for("host.repository.read_write") == "UNAVAILABLE"
    # host-level capabilities are untouched and still there for names no surface overrides
    assert host.capabilities.state_for("host.filesystem.read") == "AVAILABLE"


def test_surface_without_capabilities_block_parses_unchanged() -> None:
    # Uses this file's existing _valid_registry() helper, which declares no per-surface
    # capabilities anywhere -- this must keep parsing exactly as it does today.
    registry = parse_host_registry(_write_registry(_valid_registry()))  # adapt to existing write helper
    for host in registry.hosts.values():
        for surface in host.surfaces:
            assert surface.capabilities.values == ()
```

Note for the implementer: inspect `scripts/tests/test_host_registry.py`'s existing helpers (it already has a `_valid_registry()` builder and some way to materialize a temp YAML file for `parse_host_registry` — follow that exact existing pattern rather than the placeholder helper names above, which are illustrative only).

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest scripts/tests/test_host_registry.py -k surface_level_capabilities -v`
Expected: FAIL — `_unknown_fields` rejects the new `capabilities` key on a surface (`hosts.claude.surfaces[0].capabilities is unknown`)

- [ ] **Step 3: Add `capabilities` to `SurfaceSpec` and its parser**

In `scripts/registry/host_registry.py`:

1. Add the field to `SurfaceSpec` (around line 73-77):

```python
@dataclass(frozen=True)
class SurfaceSpec:
    kind: str
    discovery: tuple[DiscoveryBinding, ...] = field(default_factory=tuple)
    capabilities: CapabilitySpec = field(default_factory=CapabilitySpec)
```

2. Add the matching raw-parse field to `_RawSurface` (around line 153-156):

```python
@dataclass(frozen=True)
class _RawSurface:
    kind: str
    discovery: tuple[_RawDiscoveryBinding, ...]
    capabilities: CapabilitySpec
```

3. In `_parse_surfaces` (around line 350-373), allow and parse the new key:

```python
        _unknown_fields(item, frozenset({"capabilities", "discovery", "kind"}), label, errors)
        kind = _enum(item.get("kind"), ALLOWED_SURFACES, f"{label}.kind", errors)
        discovery = _parse_discovery(item.get("discovery"), label, errors)
        raw_capabilities = item.get("capabilities")
        capabilities = (
            _parse_capabilities(raw_capabilities, label, errors)
            if raw_capabilities is not None
            else CapabilitySpec()
        )
        if kind is None or capabilities is None:
            continue
        if kind in seen:
            errors.append(f"{label}.kind is duplicated: {kind!r}")
            continue
        seen.add(kind)
        surfaces.append(
            _RawSurface(kind=kind, discovery=tuple(discovery), capabilities=capabilities)
        )
```

4. In `parse_host_registry`'s surface-resolution loop (around line 629-646), pass `capabilities` through:

```python
        for surface in raw_host.surfaces:
            discovery: list[DiscoveryBinding] = []
            for binding in surface.discovery:
                target = targets.get(binding.target_id)
                if target is None:
                    errors.append(
                        f"{binding.label}.target references unknown target {binding.target_id!r}"
                    )
                    continue
                discovery.append(
                    DiscoveryBinding(
                        target=target,
                        mode=binding.mode,
                        precedence=binding.precedence,
                    )
                )
            surfaces.append(
                SurfaceSpec(
                    kind=surface.kind,
                    discovery=tuple(discovery),
                    capabilities=surface.capabilities,
                )
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest scripts/tests/test_host_registry.py -v`
Expected: PASS (all tests, including the two new ones)

- [ ] **Step 5: Run the full registry test suite to confirm no regression**

Run: `python3 -m pytest scripts/tests/ -k "host_registry or compatibility_resolver or doctor" -v`
Run: `python3 -m scripts.registry validate-hosts`
Expected: all green — this step is additive/backward-compatible by design, so nothing pre-existing should change.

- [ ] **Step 6: Commit**

```bash
git add scripts/registry/host_registry.py scripts/tests/test_host_registry.py
git commit -m "$(cat <<'EOF'
Allow agent-hosts.yaml surfaces to declare per-surface capabilities

Additive schema extension (Candidate 2): a surface may now declare a
capabilities block that overrides the host-level value for specific
capability names, falling back to host-level for everything else.
Existing entries with no per-surface capabilities parse unchanged.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Make `compatibility_resolver.py` surface-aware

**Files:**
- Modify: `scripts/registry/compatibility_resolver.py`
- Test: `scripts/tests/test_compatibility_resolver.py`

**Interfaces:**
- Consumes: `SurfaceSpec.capabilities` from Task 3
- Produces: `available_capabilities(host: HostSpec, surface_kind: str | None = None) -> frozenset[str]` (extends existing signature with a defaulted new parameter — every existing call site keeps working unchanged); `resolve(host_registry, registry, host_id, skill_id, surface_kind: str | None = None) -> CompatibilityResult` (same additive pattern); `CompatibilityResult.surface_kind: str | None` (new field, default `None`)

- [ ] **Step 1: Write the failing test**

```python
# add to scripts/tests/test_compatibility_resolver.py
def test_available_capabilities_prefers_surface_override() -> None:
    raw = _raw_registry(
        capabilities={"host.repository.read_write": "AVAILABLE"},
    )
    raw["hosts"][0]["surfaces"][0]["capabilities"] = {
        "host.repository.read_write": "UNAVAILABLE",
    }
    registry = parse_host_registry(_write(raw))  # adapt to this file's existing write helper
    host = registry.hosts["cursor"]

    assert "host.repository.read_write" not in available_capabilities(host, surface_kind="LOCAL")
    # No surface_kind given -- host-level behavior is unchanged (back-compat)
    assert "host.repository.read_write" in available_capabilities(host)


def test_available_capabilities_falls_back_to_host_level_for_unmentioned_names() -> None:
    raw = _raw_registry(
        capabilities={
            "host.repository.read_write": "AVAILABLE",
            "host.filesystem.read": "AVAILABLE",
        },
    )
    raw["hosts"][0]["surfaces"][0]["capabilities"] = {
        "host.repository.read_write": "UNAVAILABLE",
    }
    registry = parse_host_registry(_write(raw))
    host = registry.hosts["cursor"]

    available = available_capabilities(host, surface_kind="LOCAL")
    assert "host.repository.read_write" not in available  # surface override wins
    assert "host.filesystem.read" in available  # falls back to host-level
```

Note for implementer: follow `test_compatibility_resolver.py`'s existing `_raw_registry()` / temp-file-write helper conventions exactly (inspect the file first — the illustrative `_write` name above may not match).

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest scripts/tests/test_compatibility_resolver.py -k surface_override -v`
Expected: FAIL — `available_capabilities() got an unexpected keyword argument 'surface_kind'`

- [ ] **Step 3: Implement surface-aware resolution**

In `scripts/registry/compatibility_resolver.py`, replace `available_capabilities` (lines 92-99):

```python
def available_capabilities(host: HostSpec, surface_kind: str | None = None) -> frozenset[str]:
    """The capability names this host currently satisfies -- AVAILABLE only.

    With no `surface_kind`, this is host-level only (unchanged from before Candidate 2). When
    `surface_kind` names one of the host's surfaces and that surface declares any capabilities
    of its own, those entries override the host-level value for the same name; every other
    capability name still resolves from the host-level declaration. A `surface_kind` that does
    not match any of the host's surfaces, or a matching surface with no capabilities declared
    at all, falls back to host-level behavior unchanged.
    """
    if surface_kind is None:
        return host.capabilities.available
    surface = next((item for item in host.surfaces if item.kind == surface_kind), None)
    if surface is None or not surface.capabilities.values:
        return host.capabilities.available
    merged = dict(host.capabilities.values)
    merged.update(dict(surface.capabilities.values))
    return frozenset(name for name, state in merged.items() if state == "AVAILABLE")
```

Update `CompatibilityResult` (lines 54-64) to add the field:

```python
@dataclass(frozen=True)
class CompatibilityResult:
    host_id: str
    skill_id: str
    status: str
    capability_status: str
    host_verification: str
    missing_required: list[str] = field(default_factory=list)
    missing_optional: list[str] = field(default_factory=list)
    active_path: CapabilityPath | None = None
    discoverable: bool = False
    surface_kind: str | None = None
```

Update `resolve` (lines 128-155) to thread it through:

```python
def resolve(
    host_registry: HostRegistry,
    registry: Registry,
    host_id: str,
    skill_id: str,
    surface_kind: str | None = None,
) -> CompatibilityResult:
    """Compute one host x skill compatibility result, optionally scoped to one surface.

    `capability_status` is doctor.py's engine's own {UNSPECIFIED, BLOCKED, DEGRADED, READY} outcome
    (UNSPECIFIED never occurs here since `available` is always a concrete set, never None, when driven
    by a HostSpec). `status` is that outcome combined with the host's own verification state -- see
    `_combine_status`.
    """
    host = resolve_host(host_registry, host_id)
    entry = registry.skills.get(skill_id)
    if entry is None:
        raise UnknownSkillError(f"unknown skill {skill_id!r}")

    available = available_capabilities(host, surface_kind)
    capability_status, missing_required, missing_optional, active_path = resolve_capability(entry, available)
    status = _combine_status(capability_status, host.verification)

    return CompatibilityResult(
        host_id=host_id,
        skill_id=skill_id,
        status=status,
        capability_status=capability_status,
        host_verification=host.verification,
        missing_required=missing_required,
        missing_optional=missing_optional,
        active_path=active_path,
        discoverable=is_discoverable(host),
        surface_kind=surface_kind,
    )
```

Update the module docstring's "Scope of this first pass" bullet (lines 9-16) — replace the first bullet, since it is no longer accurate:

```python
- Capability availability can now be resolved per-surface: a surface in agent-hosts.yaml's
  HostSpec.surfaces may declare its own `capabilities` block that overrides the host-level value
  for specific names (Candidate 2). `available_capabilities`/`resolve` take an optional
  `surface_kind` for this; omitting it keeps the original host-level-only behavior. `resolve_matrix`
  below still resolves at host level only (one surface per host would need a decision about *which*
  surface to default to for a host with more than one -- left to whichever candidate adds
  multi-surface matrix output).
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest scripts/tests/test_compatibility_resolver.py -v`
Expected: PASS (all tests, including the two new ones)

- [ ] **Step 5: Commit**

```bash
git add scripts/registry/compatibility_resolver.py scripts/tests/test_compatibility_resolver.py
git commit -m "$(cat <<'EOF'
Resolve compatibility per-surface when a surface declares capabilities

available_capabilities() and resolve() take an optional surface_kind
now: a matching surface's own capabilities block overrides the
host-level value for those names, falling back to host-level for
everything else. Omitting surface_kind keeps prior host-level-only
behavior unchanged.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Wire `doctor.py --surface` to actually affect resolution

`scripts/doctor.py:234-239` already accepts `--surface` and prints a note that it's informational-only. Finish it.

**Files:**
- Modify: `scripts/doctor.py`
- Test: `scripts/tests/test_doctor.py` (existing file — extend it; inspect its current `--agent` tests first for the calling convention `cmd_doctor`/`main` use)

**Interfaces:**
- Consumes: `available_capabilities(host, surface_kind)` from Task 4
- Produces: no new public interface — `main()`'s existing `--surface` argument stops being a no-op

- [ ] **Step 1: Write the failing test**

```python
# add to scripts/tests/test_doctor.py
def test_surface_flag_changes_available_capabilities_for_agent(tmp_path, capsys) -> None:
    # Build a minimal repo fixture the same way this file's existing --agent tests do
    # (skills.yaml + agent-hosts.yaml under tmp_path), except this host declares a LOCAL
    # surface with host.repository.read_write AVAILABLE and a CLOUD surface with it
    # UNAVAILABLE, and one skill requires host.repository.read_write.
    ...  # follow this file's existing fixture-building helper exactly; do not invent a new one
    exit_code_local = main(["--repo-root", str(repo), "--agent", "claude", "--surface", "LOCAL"])
    exit_code_cloud = main(["--repo-root", str(repo), "--agent", "claude", "--surface", "CLOUD"])
    assert exit_code_local == 0
    assert exit_code_cloud == 1  # BLOCKED: host.repository.read_write unavailable on CLOUD
```

Note for implementer: `scripts/tests/test_doctor.py` already has fixtures for `--agent` (Candidate 10) — read those first and reuse the exact same fixture-building helper, only adding the surface-level capability difference described above, rather than writing a parallel fixture builder.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest scripts/tests/test_doctor.py -k surface_flag_changes -v`
Expected: FAIL — both invocations return the same exit code (surface is still ignored)

- [ ] **Step 3: Wire the flag through**

In `scripts/doctor.py`'s `main()` (around lines 234-273), replace the informational-only branch:

```python
        host_id = args.agent
        host_verification = host.verification
        available = set(available_capabilities(host, args.surface))
```

(This removes the `if args.surface is not None: print("note: ...")` block entirely — the note is no longer true.)

Also update `cmd_doctor`'s docstring/help text if it repeats the "informational only" caveat elsewhere in the file (grep for `"informational only"` in `scripts/doctor.py` before editing to catch every mention), and update the `--surface` argparse help string:

```python
    parser.add_argument(
        "--surface",
        help="surface kind (e.g. LOCAL, CLOUD) from agent-hosts.yaml; narrows available "
        "capabilities to that surface's overrides where the host declares any (Candidate 2)",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest scripts/tests/test_doctor.py -v`
Expected: PASS

- [ ] **Step 5: Full regression pass**

Run: `python3 -m pytest scripts/ -x -q`
Run: `make lint-static` (expect this to take a while; it runs the whole registered lint chain including the two new Phase 0 checks)
Expected: all green

- [ ] **Step 6: Commit**

```bash
git add scripts/doctor.py scripts/tests/test_doctor.py
git commit -m "$(cat <<'EOF'
Make doctor --surface actually narrow capability resolution

--surface was accepted but only printed a note that it had no effect.
Now it's threaded into available_capabilities() so a host with
per-surface capability overrides (Candidate 2) resolves differently
for --surface LOCAL vs --surface CLOUD.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Self-review

**Spec coverage against the audit:**
- "Compatibility is only host × skill, not host × surface × skill" (Critical) → Tasks 3–5, fully addressed for the resolution path; `resolve_matrix` (bulk matrix generation) intentionally still host-level, noted as a follow-up in Task 4's docstring update rather than silently left inconsistent.
- "`host.report.write` conflated with repository write" (Watch) → Task 2.
- "`.codex-plugin/plugin.json` version drift" (Watch) → Task 1.
- "Host compatibility split across two registries" (Critical) → deliberately **not** a task here; see "Global Constraints" and "Important scope note" — the split is existing documented intent, not a bug, and merging it needs a maintainer decision this plan does not make for them.
- "Installation not actually global" / "native plugin distribution incomplete" / "supply-chain trust incomplete" / CLI / policy profiles / provider profiles / enterprise ops / docs generation (all Critical/Watch) → captured in the roadmap below, not detailed here, per the scope note.

**Placeholder scan:** the two `...` fixture bodies in Task 5's test step are the one intentional exception — they explicitly instruct the implementer to reuse an existing fixture helper from `scripts/tests/test_doctor.py` rather than inventing one blind, because that file's exact fixture shape wasn't read line-by-line while writing this plan. Every other step has real, runnable code.

**Type consistency:** `available_capabilities(host, surface_kind=None)` signature is identical across Tasks 4 and 5; `CompatibilityResult.surface_kind` added once in Task 4 and not redefined elsewhere; `resolve()`'s new parameter name (`surface_kind`) matches `available_capabilities`'s parameter name throughout.

---

## Roadmap — Phases 2–7 (not detailed; each needs a maintainer decision before planning)

Captured here so nothing from the audit is dropped, with concrete file pointers for whoever scopes each one next.

### Phase 2: First-class installers beyond Cursor/Claude/generic
- **Touches:** `scripts/install.sh`, `scripts/registry/install_resolver.py`, `agent-hosts.yaml` `targets:`/`hosts:` entries for `codex`, `chatgpt`, `github-copilot` (already partially modeled), a real `--agent kiro` path (currently explicitly rejected — see `agent-hosts.yaml:47-60`'s comment on why).
- **Open decision:** does `kiro`'s "fixed repo-root artifact, not a per-user install" constraint change, or does Kiro just stay `make generate`-only forever? The audit assumes it should become installable; the codebase's own comment says that's a deliberate non-goal today. Needs the maintainer's call before writing tasks.

### Phase 3: Native plugin distribution bundles
- **Touches:** `docs/RELEASE.md` (currently excludes `.claude-plugin/`/`.codex-plugin/` from release bundles — read the exclusion rationale there first), `scripts/package_release.py`, `.claude-plugin/` (does not appear to exist yet — confirm), `.codex-plugin/`.
- **Open decision:** one release artifact per host, or one universal artifact with per-host subfolders? Affects `scripts/package_release.py`'s output shape.

### Phase 4: A real `sb` CLI
- **Touches:** new top-level package, likely `sb/` or `scripts/cli/`. Most of the logic already exists as library functions (`scripts/doctor.py`, `scripts/registry/cli.py`, `scripts/registry/compatibility_resolver.py`) — this is largely a UX/packaging layer over existing internals, not new logic.
- **Open decision:** ship as a PyPI package, a single-file script, or a `pipx`-installable entry point? Determines packaging metadata work.

### Phase 5: Signed releases / SBOM / provenance
- **Touches:** `.github/workflows/`, `scripts/package_release.py`, `scripts/verify_release_bundle.py`.
- **Open decision:** Sigstore keyless signing vs. a maintainer-held key; SLSA provenance level target. Security/ops decision, not an engineering-taste one — flag to the maintainer explicitly rather than picking for them.

### Phase 6: Policy profiles, provider profiles, permission-scoped plugin manifests
- **Touches:** `.codex-plugin/plugin.json`'s flat `["Read", "Write"]` capabilities list, `scripts/registry/capability_catalog.yaml`, `scripts/registry/host_adapter.py` (extends naturally from Task 2's family split above).
- **Open decision:** exact policy-profile taxonomy (`read-only` / `review-and-comment` / `repository-write` / `automation` / `merge-deploy-disabled`, per the audit) needs sign-off since it becomes a public contract skill authors write against.

### Phase 7: Enterprise rollout, host-neutral docs generation, smoke-test matrix
- **Touches:** every per-skill `SETUP.md`/`README.md` (currently hand-maintained, Cursor-first — audit's "Watch" item), `scripts/registry/generate_docs.py` (already generates some docs; extending it to generate host-neutral setup sections is additive), new CI smoke-test jobs per host.
- **Open decision:** which hosts get CI-automatable smoke tests (Claude Code, generic) vs. which stay manual/best-effort (Cursor, Copilot, Kiro — no headless CI harness for these today). Needs a maintainer-approved test matrix before task-level planning.
