# `sb` CLI — Read-Only Diagnostics Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a standalone, `pipx`-installable `sb` command running `doctor`/`list`/`explain`/`compatibility` against an installed skill with no software-builder checkout present.

**Architecture:** A new, independently-versioned package at `cli/` vendors a git-tracked snapshot of `scripts/`'s logic and the registry data (`skills.yaml`, `agent-hosts.yaml`, `VERSION`, `scripts/registry/*.yaml`, `skills/**`, `docs/skill-framework/**`), built by a new standalone script (`scripts/build_sb_snapshot.py`) before `python -m build` runs in `cli/`. `sb`'s subcommands call the vendored `scripts.doctor`/`scripts.registry.cli` functions directly, passing the bundled snapshot directory as their existing `root`/`repo_root` parameter — zero fork of resolution logic.

**Tech Stack:** Python 3.12+, argparse, hatchling (new build backend for `cli/` only), pytest.

## Global Constraints

- This branch is built against `main` as-is (confirmed with the user) — PR #256 (per-surface capability resolver) is still open. No `--surface` flag on `sb compatibility`; `sb doctor --surface` stays exactly as `main`'s current no-op (vendored unchanged).
- The root `pyproject.toml`'s "no build backend, checkout-only" decision is not reversed. `cli/` gets its own separate `pyproject.toml` with its own build backend.
- `scripts/package_release.py` is not touched. It builds a different, integrity-sensitive artifact (the checksummed skill-distribution tarball) with its own dev-tooling exclusion filter; entangling it with `cli/`'s vendoring would fight that design.
- Vendoring is git-tracked-files-only (via `git ls-files`, not a hand-maintained list) — same untracked-cruft-can't-leak reasoning as `package_release.py`, implemented independently (never import `package_release.py`'s private `_tracked_files`, which returns tar-specific metadata for a different artifact).
- Every file path, pathspec, and function signature below was verified by direct execution against this checkout during planning (not assumed) — see the design spec's empirical-verification notes at `docs/superpowers/specs/2026-09-12-sb-cli-diagnostics-design.md`.
- No flag or command in this slice writes to disk, installs, uninstalls, or mutates a manifest.

---

### Task 1: `compatibility` subcommand in `scripts/registry/cli.py`

**Files:**
- Modify: `scripts/registry/cli.py`
- Test: `scripts/tests/test_discovery_compatibility_cli.py` (existing file — extend it, reusing its `_run_cli` helper)

**Interfaces:**
- Consumes: `scripts.registry.compatibility_resolver.resolve(host_registry, registry, host_id, skill_id) -> CompatibilityResult`, `.resolve_host(host_registry, host_id) -> HostSpec`, `.UnknownHostError`; `scripts.registry.host_registry.parse_host_registry`/`HostRegistryParseError` (already imported in `cli.py`); `scripts.registry.load.load_registry` (already imported)
- Produces: `cmd_compatibility(root: Path, host_id: str, skill_id: str | None) -> int`, wired into `main()` as the `compatibility` subcommand

- [ ] **Step 1: Write the failing tests**

Append to `scripts/tests/test_discovery_compatibility_cli.py` (it already defines `_run_cli(*args) -> subprocess.CompletedProcess[str]` running `python -m scripts.registry` against the real repo at `cli.ROOT` — reuse it exactly, do not build a new fixture):

```python
def test_compatibility_prints_status_for_known_host_and_skill() -> None:
    result = _run_cli("compatibility", "--host", "claude", "--skill", "pr-review")

    assert result.returncode == 0
    assert "claude pr-review:" in result.stdout


def test_compatibility_defaults_to_every_skill_when_skill_omitted() -> None:
    result = _run_cli("compatibility", "--host", "claude")

    assert result.returncode == 0
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) > 1
    assert any("pr-review" in line for line in lines)


def test_compatibility_rejects_unknown_host() -> None:
    result = _run_cli("compatibility", "--host", "does-not-exist")

    assert result.returncode == 2
    assert "unknown host" in result.stderr


def test_compatibility_rejects_unknown_skill() -> None:
    result = _run_cli("compatibility", "--host", "claude", "--skill", "does-not-exist")

    assert result.returncode == 1
    assert "unknown skill" in result.stderr
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest scripts/tests/test_discovery_compatibility_cli.py -k compatibility -v`
Expected: FAIL — `argument command: invalid choice: 'compatibility'` (subcommand doesn't exist yet)

- [ ] **Step 3: Add the import**

In `scripts/registry/cli.py`, insert this import block right after the existing `from scripts.registry.capability_family_sync import validate_capability_families` line (line 20):

```python
from scripts.registry.compatibility_resolver import UnknownHostError, resolve, resolve_host
```

- [ ] **Step 4: Add `cmd_compatibility`**

Insert this function right after `cmd_validate_hosts` (after line 200, before the `_STALE_ADAPTER_ERROR_PREFIX` line):

```python
def cmd_compatibility(root: Path, host_id: str, skill_id: str | None) -> int:
    try:
        host_registry = parse_host_registry(root / "agent-hosts.yaml")
    except HostRegistryParseError as exc:
        for error in exc.errors:
            print(f"error: {error}", file=sys.stderr)
        return 2

    try:
        resolve_host(host_registry, host_id)
    except UnknownHostError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    registry = load_registry(root)
    if skill_id is not None:
        if skill_id not in registry.skills:
            print(f"error: unknown skill {skill_id!r}", file=sys.stderr)
            return 1
        skill_ids = [skill_id]
    else:
        skill_ids = sorted(registry.skills)

    for sid in skill_ids:
        result = resolve(host_registry, registry, host_id, sid)
        line = f"{result.host_id} {result.skill_id}: {result.status}"
        if result.missing_required:
            line += f" (missing required: {', '.join(result.missing_required)})"
        elif result.missing_optional:
            line += f" (missing optional: {', '.join(result.missing_optional)})"
        print(line)
    return 0
```

- [ ] **Step 5: Wire the argparse subcommand and dispatch**

In `main()`, after the `validate-hosts` subparser block (after line 200, before `subparsers.add_parser("list", ...)`), add:

```python
    compatibility_parser = subparsers.add_parser(
        "compatibility",
        help="resolve host x skill capability compatibility (Candidate 4)",
    )
    compatibility_parser.add_argument("--host", required=True, help="host id or alias from agent-hosts.yaml")
    compatibility_parser.add_argument("--skill", help="limit to one skill id (default: every registered skill)")
```

After the `if args.command == "validate-hosts":` dispatch line (line 463), add:

```python
    if args.command == "compatibility":
        return _run_command(lambda: cmd_compatibility(ROOT, args.host, args.skill))
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python3 -m pytest scripts/tests/test_discovery_compatibility_cli.py -v`
Expected: PASS (all tests in the file, including the 4 new ones)

- [ ] **Step 7: Commit**

```bash
git add scripts/registry/cli.py scripts/tests/test_discovery_compatibility_cli.py
git commit -m "$(cat <<'EOF'
Add compatibility subcommand to scripts.registry CLI

python3 -m scripts.registry compatibility --host X [--skill Y]
resolves host x skill capability compatibility from the CLI --
compatibility_resolver.resolve/resolve_matrix existed but had no
command-line entry point. Reuses the resolver unchanged; this is
pure CLI plumbing.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Fix `doctor.py`'s default `--install-root` scan

**Files:**
- Modify: `scripts/doctor.py`
- Test: `scripts/tests/test_doctor.py` (existing file — extend it; inspect its existing `--agent` tests first for the exact fixture-building convention before writing the new one)

**Interfaces:**
- Consumes: `scripts.registry.host_registry.HostSpec`/`resolve_target_path` (already partially imported in `doctor.py` — add `HostSpec`, `resolve_target_path` to the existing import line)
- Produces: `_default_install_roots_for_host(host: HostSpec, *, home: Path) -> list[Path]`

- [ ] **Step 1: Write the failing test**

First, read `scripts/tests/test_doctor.py` in full to find its real `--agent` test fixture pattern (it builds a temp repo with `skills.yaml`/`agent-hosts.yaml` under `tmp_path` and calls `main()`). Using that exact pattern, add:

```python
def test_agent_default_install_root_scans_the_hosts_own_user_scope_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Build the same minimal skills.yaml + agent-hosts.yaml fixture this file's existing
    # --agent tests use, with a host "claude" whose LOCAL surface discovers "claude-user"
    # (path ~/.claude/skills, scope user) -- agent-hosts.yaml's real claude host shape.
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    # ... build repo fixture under tmp_path / "repo" here, following this file's existing
    # --agent test's exact fixture-construction helper ...

    installed_dir = fake_home / ".claude" / "skills" / "<fixture-skill-id>"
    installed_dir.mkdir(parents=True)
    (installed_dir / ".software-builder-manifest.json").write_text(
        '{"distribution_version": "<fixture-version>", "source_sha": "0" * 40, "files": {}}',
        encoding="utf-8",
    )

    exit_code = main(["--repo-root", str(tmp_path / "repo"), "--agent", "claude"])

    assert exit_code == 0
    assert "installed (" in capsys.readouterr().out
```

(This is a template for the implementer to fill in against the file's real fixture-building helper and real fixture skill id/version — do not invent a new fixture shape; the file's existing `--agent` tests already build exactly the repo structure needed, only the `fake_home`/manifest-placement parts above are new.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest scripts/tests/test_doctor.py -k default_install_root -v`
Expected: FAIL — status shows "not installed" (still defaults to `~/.cursor/skills`, ignoring the fixture's fake `~/.claude/skills`)

- [ ] **Step 3: Add `HostSpec`/`resolve_target_path` to the import and write the helper**

In `scripts/doctor.py`, change:

```python
from scripts.registry.host_registry import HostRegistryParseError, parse_host_registry
```

to:

```python
from scripts.registry.host_registry import (
    HostRegistryParseError,
    HostSpec,
    parse_host_registry,
    resolve_target_path,
)
```

Add this function after `_installed_manifest` (after line 46):

```python
def _default_install_roots_for_host(host: HostSpec, *, home: Path) -> list[Path]:
    """Every install destination this host's surfaces declare at user scope, resolved against
    `home`, in discovery order with duplicates removed.

    Project-scope targets need a --target-dir this command has no context for outside a specific
    project (unlike install.sh, doctor has no notion of "the current project"), so those are left
    for an explicit --install-root; this only widens the previous single hardcoded
    ~/.cursor/skills default to every user-scope target the resolved host actually declares,
    it does not attempt project discovery. A host with no user-scope surface (e.g. kiro, whose
    only discovery target is repo-root-fixed and project-scoped) correctly yields an empty list --
    reporting "not installed" for such a host by default is accurate, not a gap.
    """
    roots: list[Path] = []
    seen: set[Path] = set()
    for surface in host.surfaces:
        for binding in surface.discovery:
            if binding.target.scope != "user":
                continue
            resolved = resolve_target_path(binding.target, home=home, target_dir=None)
            if resolved not in seen:
                seen.add(resolved)
                roots.append(resolved)
    return roots
```

- [ ] **Step 4: Use the helper in `main()`**

Replace (around line 283-285):

```python
    install_roots = list(args.install_root)
    if not install_roots:
        install_roots = [Path.home() / ".cursor" / "skills"]
```

with:

```python
    install_roots = list(args.install_root)
    if not install_roots:
        if host_id is not None:
            install_roots = _default_install_roots_for_host(host, home=Path.home())
        else:
            install_roots = [Path.home() / ".cursor" / "skills"]
```

(`host` and `host_id` are the same local variables already assigned inside the `if args.agent is not None:` block earlier in `main()` — no new variable needed, just referenced after that block, guarded by the same `host_id is not None` condition the rest of `main()` already uses.)

Also update the `--install-root` help string (around line 244-249) to reflect the new default:

```python
    parser.add_argument(
        "--install-root",
        action="append",
        type=Path,
        default=[],
        help="installed skills directory (repeatable; with --agent, defaults to every "
        "user-scope target that host's surfaces declare; without --agent, defaults to "
        "~/.cursor/skills)",
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest scripts/tests/test_doctor.py -v`
Expected: PASS (all tests, including the new one)

- [ ] **Step 6: Run the broader suite to confirm no regression**

Run: `python3 -m pytest scripts/tests/ -k "doctor or host_registry" -v`
Expected: all green

- [ ] **Step 7: Commit**

```bash
git add scripts/doctor.py scripts/tests/test_doctor.py
git commit -m "$(cat <<'EOF'
Default doctor --install-root scan to the host's own surfaces

--agent's default install-root scan was hardcoded to ~/.cursor/skills
regardless of which host was named. Default to every user-scope
target the resolved HostSpec's own surfaces declare instead --
project-scope targets still need an explicit --install-root, since
doctor has no notion of "the current project" the way install.sh does.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Scaffold the `cli/` package

**Files:**
- Create: `cli/pyproject.toml`
- Create: `cli/sb/__init__.py`
- Create: `cli/sb/__main__.py`
- Create: `cli/tests/test_sb_version.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `sb.__main__.main(argv: list[str] | None = None) -> int` (skeleton only — `--version`, bare invocation prints help and exits 0, unknown command exits 2). Later tasks add real subcommands.

- [ ] **Step 1: Write the failing test**

```python
# cli/tests/test_sb_version.py
"""Tests for the sb package's argparse skeleton (before real subcommands land)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

CLI_ROOT = Path(__file__).resolve().parents[1]


def _run_sb(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sb", *args],
        cwd=CLI_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_bare_invocation_prints_help_and_exits_zero() -> None:
    result = _run_sb()

    assert result.returncode == 0
    assert "usage" in result.stdout.lower()


def test_version_flag_prints_a_version_string() -> None:
    result = _run_sb("--version")

    assert result.returncode == 0
    assert "sb" in result.stdout


def test_unknown_command_exits_two() -> None:
    result = _run_sb("bogus-command")

    assert result.returncode == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd cli && python3 -m pytest tests/test_sb_version.py -v`
Expected: FAIL — `No module named sb`

- [ ] **Step 3: Write `cli/pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "software-builder-cli"
version = "1.4.0"
description = "Standalone sb CLI: doctor/list/explain/compatibility for installed software-builder skills, no checkout required."
requires-python = ">=3.12"
license = "MIT"
dependencies = ["PyYAML>=6.0.3"]

[project.scripts]
sb = "sb.__main__:main"

[tool.hatch.build.targets.wheel]
packages = ["sb"]
# _vendored/ and _registry_snapshot/ are gitignored, build-time-populated directories (see
# scripts/build_sb_snapshot.py) -- hatchling's default wheel file selection follows VCS tracking,
# which would silently ship an EMPTY wheel for both if not force-included here. `artifacts`
# includes matching paths regardless of gitignore state, as long as they exist on disk at build
# time.
artifacts = ["sb/_vendored/**", "sb/_registry_snapshot/**"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

(Version `1.4.0` matches the root `VERSION` file as of this writing — Task 7 adds a validator that keeps the two in sync going forward, the same pattern already established for `.codex-plugin/plugin.json`.)

- [ ] **Step 4: Write `cli/sb/__init__.py`**

```python
"""sb: standalone diagnostics CLI for software-builder skills, no checkout required."""
```

- [ ] **Step 5: Write `cli/sb/__main__.py`**

```python
#!/usr/bin/env python3
"""Entry point for the `sb` console script."""

from __future__ import annotations

import argparse
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _installed_version


def _package_version() -> str:
    try:
        return _installed_version("software-builder-cli")
    except PackageNotFoundError:
        return "unknown (not installed)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sb")
    parser.add_argument(
        "--version", action="version", version=f"sb {_package_version()}"
    )
    subparsers = parser.add_subparsers(dest="command")
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    print(f"error: unknown command {args.command!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Add `.gitignore` entries**

Append to `.gitignore`:

```
# cli/ (the sb package): build-time-populated snapshot directories, never committed
cli/sb/_vendored/
cli/sb/_registry_snapshot/
cli/dist/
cli/build/
cli/*.egg-info/
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd cli && python3 -m pytest tests/test_sb_version.py -v`
Expected: PASS (all 3 tests)

- [ ] **Step 8: Commit**

```bash
git add cli/pyproject.toml cli/sb/__init__.py cli/sb/__main__.py cli/tests/test_sb_version.py .gitignore
git commit -m "$(cat <<'EOF'
Scaffold the cli/ package (sb CLI skeleton)

Separate, independently-versioned package with its own build backend
(hatchling) -- the root pyproject.toml's "no build backend, checkout-
only" decision stands unchanged. Skeleton only: --version, help on
bare invocation, exit 2 on an unknown command. Real subcommands land
in later tasks once the vendoring step (Task 4) exists.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: `scripts/build_sb_snapshot.py`

**Files:**
- Create: `scripts/build_sb_snapshot.py`
- Test: `scripts/tests/test_build_sb_snapshot.py`

**Interfaces:**
- Produces: `build_snapshot(repo_root: Path = ROOT) -> tuple[int, int]` (returns `(code file count, data file count)`); `main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Write the failing test**

```python
# scripts/tests/test_build_sb_snapshot.py
"""Tests for scripts/build_sb_snapshot.py -- the cli/ package's vendoring step."""

from __future__ import annotations

import sys
from pathlib import Path

from scripts.build_sb_snapshot import build_snapshot

ROOT = Path(__file__).resolve().parents[2]


def test_build_snapshot_populates_both_output_directories() -> None:
    code_count, data_count = build_snapshot(ROOT)

    vendored = ROOT / "cli" / "sb" / "_vendored"
    snapshot = ROOT / "cli" / "sb" / "_registry_snapshot"
    assert (vendored / "scripts" / "doctor.py").is_file()
    assert (vendored / "scripts" / "registry" / "cli.py").is_file()
    assert not (vendored / "scripts" / "tests").exists()
    assert (snapshot / "skills.yaml").is_file()
    assert (snapshot / "agent-hosts.yaml").is_file()
    assert (snapshot / "VERSION").is_file()
    assert (snapshot / "skills" / "pr-review" / "SKILL.md").is_file()
    assert code_count > 0
    assert data_count > 0


def test_vendored_code_and_snapshot_data_work_together_end_to_end(tmp_path: Path) -> None:
    """The real proof: import the VENDORED copy (not this checkout's own scripts package) and
    run cmd_list/cmd_explain/cmd_doctor/compatibility_resolver.resolve against the snapshot --
    if the glob missed a needed file, this fails with an ImportError or a missing-file error,
    not a silent gap."""
    build_snapshot(ROOT)
    vendored = ROOT / "cli" / "sb" / "_vendored"
    snapshot = ROOT / "cli" / "sb" / "_registry_snapshot"

    sys.path.insert(0, str(vendored))
    try:
        import importlib

        doctor = importlib.import_module("scripts.doctor")
        registry_cli = importlib.import_module("scripts.registry.cli")
        compatibility_resolver = importlib.import_module("scripts.registry.compatibility_resolver")
        host_registry_module = importlib.import_module("scripts.registry.host_registry")
        load_module = importlib.import_module("scripts.registry.load")

        assert registry_cli.cmd_list(snapshot) == 0
        assert registry_cli.cmd_explain(snapshot, "pr-review") == 0
        assert doctor.cmd_doctor(
            snapshot, skill_filter="pr-review", available=set(), install_roots=[]
        ) in (0, 1)

        host_registry = host_registry_module.parse_host_registry(snapshot / "agent-hosts.yaml")
        registry = load_module.load_registry(snapshot)
        result = compatibility_resolver.resolve(host_registry, registry, "claude", "pr-review")
        assert result.status in {"READY", "DEGRADED", "BLOCKED", "UNVERIFIED", "CONFLICTED"}
    finally:
        sys.path.remove(str(vendored))
        for name in list(sys.modules):
            if name == "scripts" or name.startswith("scripts."):
                del sys.modules[name]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest scripts/tests/test_build_sb_snapshot.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.build_sb_snapshot'`

- [ ] **Step 3: Write the implementation**

```python
#!/usr/bin/env python3
"""Populate cli/sb/_vendored/ (code) and cli/sb/_registry_snapshot/ (data) from this checkout's
git-tracked files, so the `sb` package can run doctor/list/explain/compatibility logic unforked
against an installed skill with no software-builder checkout present.

Git-tracked only (same reasoning as scripts/package_release.py: untracked local cruft -- caches,
build output, local secrets -- can never leak into what ships), and pathspec-driven rather than a
hand-maintained file list, so a new scripts/*.py module, a new registry YAML, or a new skill is
picked up automatically. Does NOT reuse scripts/package_release.py's private _tracked_files --
that function returns tar-specific metadata (mode, blob hash) for a different artifact (the
checksummed skill-distribution tarball, which deliberately EXCLUDES scripts/ dev tooling); this
script's bundle has the opposite inclusion (scripts/ IS what this bundle ships), so it uses its
own minimal `git ls-files` invocation instead.

The exact file set here was verified empirically during planning, not assumed: cmd_list,
cmd_explain, cmd_doctor, and compatibility_resolver.resolve were each run directly against a
directory containing only this set (and separately, against a vendored copy of only this code
set) and confirmed to succeed -- see
docs/superpowers/specs/2026-09-12-sb-cli-diagnostics-design.md.

Run before `python -m build` in cli/. The two output directories are gitignored build inputs,
rebuilt from scratch on every run, never committed.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI_ROOT = ROOT / "cli"
VENDORED_ROOT = CLI_ROOT / "sb" / "_vendored"
SNAPSHOT_ROOT = CLI_ROOT / "sb" / "_registry_snapshot"

# `git ls-files "scripts/*.py"` matches recursively in this repo's git pathspec behavior (`*`
# crosses `/`) -- verified directly, not assumed -- so this one pattern already covers
# scripts/registry/*.py and scripts/evals/*.py (both needed transitively) without listing them
# separately. scripts/tests/ is filtered out below in Python (simpler and more robust than a
# git exclude pathspec, and confirmed sufficient: nothing doctor.py/registry/cli.py imports
# lives under scripts/tests/).
_CODE_PATHSPEC = "scripts/*.py"
_CODE_EXCLUDE_PREFIX = "scripts/tests/"

# Every data file the four target commands read, verified empirically (see module docstring).
# scripts/registry/*.yaml also pulls in scripts/registry/skills.d/*.yaml's ~50 source fragments
# alongside the ~11 real config files -- harmless (small, unused by any of the four commands,
# which read the already-materialized skills.yaml instead) and not filtered out, since excluding
# them would need extra logic for no functional benefit.
_DATA_PATHSPECS = (
    "skills.yaml",
    "agent-hosts.yaml",
    "VERSION",
    "scripts/registry/*.yaml",
    "skills/**",
    "docs/skill-framework/**",
)


def _tracked_files(repo_root: Path, *pathspecs: str) -> list[str]:
    """Git-tracked file paths (relative to repo_root) matching any of pathspecs."""
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z", "--", *pathspecs],
        check=True,
        capture_output=True,
        text=True,
    )
    return [rel for rel in result.stdout.split("\0") if rel]


def _copy_files(repo_root: Path, rel_paths: list[str], dest_root: Path) -> None:
    for rel in rel_paths:
        src = repo_root / rel
        dest = dest_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def build_snapshot(repo_root: Path = ROOT) -> tuple[int, int]:
    """Rebuild both output directories from scratch. Returns (code file count, data file count)."""
    if VENDORED_ROOT.exists():
        shutil.rmtree(VENDORED_ROOT)
    if SNAPSHOT_ROOT.exists():
        shutil.rmtree(SNAPSHOT_ROOT)

    code_files = [
        rel
        for rel in _tracked_files(repo_root, _CODE_PATHSPEC)
        if not rel.startswith(_CODE_EXCLUDE_PREFIX)
    ]
    _copy_files(repo_root, code_files, VENDORED_ROOT)

    data_files = _tracked_files(repo_root, *_DATA_PATHSPECS)
    _copy_files(repo_root, data_files, SNAPSHOT_ROOT)

    return len(code_files), len(data_files)


def main(argv: list[str] | None = None) -> int:
    code_count, data_count = build_snapshot()
    print(f"ok: vendored {code_count} code files into {VENDORED_ROOT}")
    print(f"ok: snapshotted {data_count} data files into {SNAPSHOT_ROOT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest scripts/tests/test_build_sb_snapshot.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Confirm the populated directories look right, then leave them in place for Task 5**

Run: `find cli/sb/_vendored -name "*.py" | wc -l` (expect roughly 100-115, matching Task 4's verified count)
Run: `ls cli/sb/_registry_snapshot/skills | head -5` (expect real skill ids)

- [ ] **Step 6: Commit**

```bash
git add scripts/build_sb_snapshot.py scripts/tests/test_build_sb_snapshot.py
git commit -m "$(cat <<'EOF'
Add scripts/build_sb_snapshot.py, the cli/ package's vendoring step

Populates cli/sb/_vendored/ (a git-tracked copy of scripts/, minus
scripts/tests/) and cli/sb/_registry_snapshot/ (skills.yaml,
agent-hosts.yaml, VERSION, scripts/registry/*.yaml, skills/**,
docs/skill-framework/**) so the sb package can run doctor/list/
explain/compatibility unforked against an installed skill with no
checkout present. Both file sets verified empirically to be sufficient
and necessary during planning.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Wire `sb doctor` / `sb list` / `sb explain`

**Files:**
- Create: `cli/sb/_paths.py`
- Modify: `cli/sb/__main__.py`
- Create: `cli/tests/test_sb_doctor_parity.py`
- Create: `cli/tests/test_sb_list_explain_parity.py`

**Interfaces:**
- Consumes: `scripts.doctor.cmd_doctor`, `scripts.doctor.main` (for arg-parsing reuse — see Step 3); `scripts.registry.cli.cmd_list`, `cmd_explain`; `Task 4`'s `VENDORED_ROOT`/`SNAPSHOT_ROOT` layout (via `importlib.resources`, not the build-time constants directly, since at runtime this is an installed package, not a checkout)
- Produces: `sb doctor [--skill ID] [--agent HOST] [--surface KIND] [--install-root PATH ...]`, `sb list`, `sb explain <skill-id>` subcommands in `cli/sb/__main__.py`

- [ ] **Step 1: Write the failing tests**

```python
# cli/tests/test_sb_list_explain_parity.py
"""Parity tests: sb list/explain must produce the same output as the checkout's own
python3 -m scripts.registry list/explain, run against the vendored snapshot instead of a live
checkout."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

CLI_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = CLI_ROOT.parent


def _run_sb(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sb", *args],
        cwd=CLI_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _run_checkout_registry_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "scripts.registry", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_sb_list_matches_checkout_list() -> None:
    sb_result = _run_sb("list")
    checkout_result = _run_checkout_registry_cli("list")

    assert sb_result.returncode == checkout_result.returncode == 0
    assert sb_result.stdout == checkout_result.stdout


def test_sb_explain_matches_checkout_explain() -> None:
    sb_result = _run_sb("explain", "pr-review")
    checkout_result = _run_checkout_registry_cli("explain", "pr-review")

    assert sb_result.returncode == checkout_result.returncode == 0
    assert sb_result.stdout == checkout_result.stdout


def test_sb_explain_rejects_unknown_skill() -> None:
    result = _run_sb("explain", "does-not-exist")

    assert result.returncode == 1
    assert "unknown skill" in result.stderr
```

```python
# cli/tests/test_sb_doctor_parity.py
"""Parity test: sb doctor must produce the same output as python3 -m scripts.doctor, run
against the vendored snapshot instead of a live checkout, for a skill filter with no host/
--available context (both default to UNSPECIFIED capability resolution)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

CLI_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = CLI_ROOT.parent


def _run_sb(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sb", *args],
        cwd=CLI_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _run_checkout_doctor(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "scripts.doctor", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_sb_doctor_matches_checkout_doctor_for_one_skill() -> None:
    sb_result = _run_sb("doctor", "--skill", "pr-review")
    checkout_result = _run_checkout_doctor("--skill", "pr-review", "--install-root", "/nonexistent")

    assert sb_result.stdout.splitlines()[1:] == checkout_result.stdout.splitlines()[1:]
```

(The first line of `doctor`'s output embeds the distribution version banner, which is identical for both since both read the same `VERSION` — sliced from the comparison only in case a stray blank-line/whitespace difference around the banner line trips the test; if the implementer finds the banner line matches exactly too, comparing full output including line 0 is preferable and simpler — check this while implementing and drop the slice if unnecessary, noting it in the report either way.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd cli && python3 -m pytest tests/test_sb_list_explain_parity.py tests/test_sb_doctor_parity.py -v`
Expected: FAIL — `sb` has no `list`/`explain`/`doctor` subcommands yet (argparse "invalid choice" or similar)

- [ ] **Step 3: Write `cli/sb/_paths.py`**

```python
"""Locate this package's bundled snapshot directories at runtime."""

from __future__ import annotations

from importlib import resources
from pathlib import Path


def vendored_scripts_root() -> Path:
    """Directory containing the vendored scripts/ package -- add this to sys.path before
    importing anything under `scripts.*`."""
    return Path(str(resources.files("sb") / "_vendored"))


def registry_snapshot_root() -> Path:
    """Directory that stands in for a repository checkout root when calling the vendored
    scripts.doctor / scripts.registry.cli functions' `root`/`repo_root` parameter."""
    return Path(str(resources.files("sb") / "_registry_snapshot"))
```

- [ ] **Step 4: Rewrite `cli/sb/__main__.py`**

```python
#!/usr/bin/env python3
"""Entry point for the `sb` console script."""

from __future__ import annotations

import argparse
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _installed_version
from pathlib import Path

from sb._paths import registry_snapshot_root, vendored_scripts_root

sys.path.insert(0, str(vendored_scripts_root()))

from scripts.doctor import cmd_doctor  # noqa: E402
from scripts.registry.cli import cmd_explain, cmd_list  # noqa: E402
from scripts.registry.compatibility_resolver import (  # noqa: E402
    UnknownHostError,
    available_capabilities,
    resolve_host,
)
from scripts.registry.host_registry import (  # noqa: E402
    HostRegistryParseError,
    parse_host_registry,
)
from scripts.registry.host_registry import (  # noqa: E402
    HostSpec,
    resolve_target_path,
)


def _package_version() -> str:
    try:
        return _installed_version("software-builder-cli")
    except PackageNotFoundError:
        return "unknown (not installed)"


def _default_install_roots_for_host(host: HostSpec, *, home: Path) -> list[Path]:
    """Same logic as scripts/doctor.py's own helper of the same name -- duplicated here
    rather than imported, since sb's argparse layer is a thin shim over the vendored
    library functions and this one piece of arg-resolution logic (turning --agent into a
    default --install-root list) lives in doctor.py's own main(), not in cmd_doctor itself,
    so there is no library function to call. Keep in sync with scripts/doctor.py's version
    if it changes."""
    roots: list[Path] = []
    seen: set[Path] = set()
    for surface in host.surfaces:
        for binding in surface.discovery:
            if binding.target.scope != "user":
                continue
            resolved = resolve_target_path(binding.target, home=home, target_dir=None)
            if resolved not in seen:
                seen.add(resolved)
                roots.append(resolved)
    return roots


def _cmd_doctor(args: argparse.Namespace) -> int:
    root = registry_snapshot_root()
    host_id: str | None = None
    host_verification: str | None = None
    available: set[str] | None = None

    if args.agent is not None:
        try:
            host_registry = parse_host_registry(root / "agent-hosts.yaml")
        except HostRegistryParseError as exc:
            for error in exc.errors:
                print(f"error: {error}", file=sys.stderr)
            return 2
        try:
            host = resolve_host(host_registry, args.agent)
        except UnknownHostError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        host_id = args.agent
        host_verification = host.verification
        available = set(available_capabilities(host))
    elif args.available is not None:
        available = {item.strip() for item in args.available.split(",") if item.strip()}

    install_roots = list(args.install_root)
    if not install_roots:
        if host_id is not None:
            install_roots = _default_install_roots_for_host(host, home=Path.home())
        else:
            install_roots = [Path.home() / ".cursor" / "skills"]

    return cmd_doctor(
        root,
        skill_filter=args.skill,
        available=available,
        install_roots=install_roots,
        host_id=host_id,
        host_verification=host_verification,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sb")
    parser.add_argument(
        "--version", action="version", version=f"sb {_package_version()}"
    )
    subparsers = parser.add_subparsers(dest="command")

    doctor_parser = subparsers.add_parser("doctor", help="check skill capability/install status")
    doctor_parser.add_argument("--skill", help="limit output to one skill id")
    doctor_parser.add_argument("--available", help="comma-separated capability names")
    doctor_parser.add_argument("--agent", help="host id or alias from agent-hosts.yaml")
    doctor_parser.add_argument(
        "--install-root", action="append", type=Path, default=[],
        help="installed skills directory (repeatable)",
    )

    subparsers.add_parser("list", help="list registered skills and their canonical metadata")

    explain_parser = subparsers.add_parser("explain", help="explain one skill's canonical metadata")
    explain_parser.add_argument("skill_id", help="registered skill identifier")

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "doctor":
        return _cmd_doctor(args)
    if args.command == "list":
        return cmd_list(registry_snapshot_root())
    if args.command == "explain":
        return cmd_explain(registry_snapshot_root(), args.skill_id)

    print(f"error: unknown command {args.command!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
```

Note: this drops the `--surface` flag entirely from `sb doctor` for this task (rather than vendoring a dead no-op flag) — the checkout's `doctor.py --surface` is currently a no-op anyway (see Global Constraints), and `sb` reimplements its own thin `main()` here (not calling `scripts.doctor.main()` directly, since that parses `sys.argv`-shaped args tied to the checkout's own flag set) rather than vendoring a flag with no effect. If a future task wants `sb doctor --surface`, it lands together with the `--surface` fast-follow noted in the design spec.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd cli && python3 -m pytest tests/ -v`
Expected: PASS (all tests across `test_sb_version.py`, `test_sb_list_explain_parity.py`, `test_sb_doctor_parity.py`)

- [ ] **Step 6: Commit**

```bash
git add cli/sb/_paths.py cli/sb/__main__.py cli/tests/test_sb_doctor_parity.py cli/tests/test_sb_list_explain_parity.py
git commit -m "$(cat <<'EOF'
Wire sb doctor/list/explain to the vendored snapshot

Thin argparse shim calling the vendored scripts.doctor.cmd_doctor /
scripts.registry.cli.cmd_list/cmd_explain against
_paths.registry_snapshot_root() instead of a checkout path. Parity
tests confirm identical output to the checkout's own
python -m scripts.registry / python -m scripts.doctor for the same
registry snapshot.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Wire `sb compatibility`

**Files:**
- Modify: `cli/sb/__main__.py`
- Create: `cli/tests/test_sb_compatibility_parity.py`

**Interfaces:**
- Consumes: `scripts.registry.cli.cmd_compatibility` (Task 1, now present in the vendored copy)

- [ ] **Step 1: Write the failing test**

```python
# cli/tests/test_sb_compatibility_parity.py
"""Parity test: sb compatibility must match the checkout's python -m scripts.registry
compatibility for the same host/skill."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

CLI_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = CLI_ROOT.parent


def _run_sb(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sb", *args],
        cwd=CLI_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _run_checkout_registry_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "scripts.registry", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_sb_compatibility_matches_checkout_compatibility() -> None:
    sb_result = _run_sb("compatibility", "--host", "claude", "--skill", "pr-review")
    checkout_result = _run_checkout_registry_cli(
        "compatibility", "--host", "claude", "--skill", "pr-review"
    )

    assert sb_result.returncode == checkout_result.returncode == 0
    assert sb_result.stdout == checkout_result.stdout


def test_sb_compatibility_rejects_unknown_host() -> None:
    result = _run_sb("compatibility", "--host", "does-not-exist")

    assert result.returncode == 2
    assert "unknown host" in result.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd cli && python3 -m pytest tests/test_sb_compatibility_parity.py -v`
Expected: FAIL — `sb` has no `compatibility` subcommand

- [ ] **Step 3: Wire the subcommand**

In `cli/sb/__main__.py`, add to the imports (alongside the existing `from scripts.registry.cli import cmd_explain, cmd_list` line):

```python
from scripts.registry.cli import cmd_compatibility, cmd_explain, cmd_list  # noqa: E402
```

In `main()`, after the `explain_parser` block:

```python
    compatibility_parser = subparsers.add_parser(
        "compatibility", help="resolve host x skill capability compatibility"
    )
    compatibility_parser.add_argument("--host", required=True, help="host id or alias from agent-hosts.yaml")
    compatibility_parser.add_argument("--skill", help="limit to one skill id")
```

And after the `if args.command == "explain":` dispatch line:

```python
    if args.command == "compatibility":
        return cmd_compatibility(registry_snapshot_root(), args.host, args.skill)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd cli && python3 -m pytest tests/ -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add cli/sb/__main__.py cli/tests/test_sb_compatibility_parity.py
git commit -m "$(cat <<'EOF'
Wire sb compatibility to the vendored cmd_compatibility

Reuses Task 1's cmd_compatibility (already present in the vendored
scripts/ copy) against the registry snapshot. Parity test confirms
identical output to the checkout's own
python -m scripts.registry compatibility.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Keep `cli/pyproject.toml`'s version in sync

**Files:**
- Modify: `scripts/check_plugin_version_sync.py`
- Modify: `scripts/tests/test_check_plugin_version_sync.py` (existing file — extend it)

**Interfaces:**
- Consumes: `scripts.release_info.read_distribution_version` (unchanged)
- Produces: `drifted_plugin_versions` also checks `cli/pyproject.toml` (TOML, not JSON)

- [ ] **Step 1: Write the failing test**

Append to `scripts/tests/test_check_plugin_version_sync.py` (reuse its existing `_write_repo`-style helper conventions — read the file first, since it already builds a `VERSION` + `.codex-plugin/plugin.json` fixture and this needs the same shape for a second manifest kind):

```python
def _write_cli_pyproject(tmp_path: Path, *, version: str) -> None:
    cli_dir = tmp_path / "cli"
    cli_dir.mkdir(exist_ok=True)
    (cli_dir / "pyproject.toml").write_text(
        f'[project]\nname = "software-builder-cli"\nversion = "{version}"\n',
        encoding="utf-8",
    )


def test_cli_pyproject_version_drift_is_reported(tmp_path: Path) -> None:
    (tmp_path / "VERSION").write_text("1.4.0\n", encoding="utf-8")
    _write_cli_pyproject(tmp_path, version="1.3.0")

    errors = drifted_plugin_versions(tmp_path)

    assert any("cli/pyproject.toml" in error and "1.3.0" in error for error in errors)


def test_cli_pyproject_matching_version_reports_no_drift(tmp_path: Path) -> None:
    (tmp_path / "VERSION").write_text("1.4.0\n", encoding="utf-8")
    _write_cli_pyproject(tmp_path, version="1.4.0")

    assert drifted_plugin_versions(tmp_path) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest scripts/tests/test_check_plugin_version_sync.py -k cli_pyproject -v`
Expected: FAIL — `cli/pyproject.toml` isn't checked at all yet (both new tests fail: the drift one because nothing reports it, the matching one only passes vacuously — verify the drift test actually fails, that's the meaningful one)

- [ ] **Step 3: Extend the validator**

In `scripts/check_plugin_version_sync.py`, this needs a TOML reader — Python 3.11+ stdlib has `tomllib` (read-only), matching this repo's `requires-python = ">=3.12"` floor, so no new dependency. Add:

```python
import tomllib
```

to the imports (alongside `json`). Add a second manifest-kind constant and a small TOML-specific check function:

```python
# TOML manifests whose [project].version must track VERSION -- same rationale as
# PLUGIN_MANIFESTS, a different file format (tomllib.load needs a binary-mode file, not
# json.loads on decoded text) so it gets its own tuple and check function rather than a
# strained shared abstraction over two unrelated parsers.
TOML_MANIFESTS: tuple[str, ...] = ("cli/pyproject.toml",)


def _drifted_toml_versions(repo_root: Path, distribution_version: str) -> list[str]:
    errors: list[str] = []
    for relpath in TOML_MANIFESTS:
        manifest_path = repo_root / relpath
        if not manifest_path.is_file():
            continue
        try:
            with manifest_path.open("rb") as handle:
                manifest = tomllib.load(handle)
        except tomllib.TOMLDecodeError as exc:
            errors.append(f"{relpath}: invalid TOML ({exc})")
            continue
        project_version = manifest.get("project", {}).get("version")
        if project_version != distribution_version:
            errors.append(
                f"{relpath}: version {project_version!r} does not match VERSION "
                f"{distribution_version!r} -- bump {relpath} to match on every release"
            )
    return errors
```

In `drifted_plugin_versions`, after the existing `for relpath in PLUGIN_MANIFESTS:` loop completes (right before its `return errors`), add:

```python
    errors.extend(_drifted_toml_versions(repo_root, distribution_version))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest scripts/tests/test_check_plugin_version_sync.py -v`
Expected: PASS (all tests, including the 2 new ones)

- [ ] **Step 5: Confirm it passes against the real repo**

Run: `python3 scripts/check_plugin_version_sync.py`
Expected: exit 0, no output (Task 3 already set `cli/pyproject.toml`'s version to `1.4.0`, matching the real `VERSION`)

- [ ] **Step 6: Commit**

```bash
git add scripts/check_plugin_version_sync.py scripts/tests/test_check_plugin_version_sync.py
git commit -m "$(cat <<'EOF'
Extend plugin-version-sync validator to cover cli/pyproject.toml

cli/pyproject.toml's [project].version now tracks VERSION the same
way .codex-plugin/plugin.json's version field already does -- a
tomllib-based check (stdlib, matches this repo's >=3.12 floor, no new
dependency) alongside the existing JSON one.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: End-to-end build + install smoke test

**Files:**
- Create: `scripts/tests/test_sb_wheel_smoke.py`
- Modify: `requirements.txt` / `requirements.lock` (add `build` — the PEP 517 build frontend — as a dev dependency)

**Interfaces:**
- No new production interfaces — this task only proves the whole pipeline (`build_snapshot` → `python -m build` → `pip install` into a throwaway venv → run the real installed `sb`) actually works, since every prior task tested `sb` by running `python -m sb`/`python -m scripts.registry` from the source tree, never through an actual installed package.

- [ ] **Step 1: Add `build` to dev dependencies**

Add to `requirements.txt` (in its existing alphabetical-ish list):

```
build>=1.2.2
```

Regenerate the lock file per the repo's existing convention:

Run: `uv pip compile requirements.txt --generate-hashes --python-version 3.12 -o requirements.lock`

- [ ] **Step 2: Write the smoke test**

```python
# scripts/tests/test_sb_wheel_smoke.py
"""End-to-end proof that the sb package actually builds, installs, and runs as a real
installed command -- every other cli/ test runs `python -m sb` from the source tree, which
never exercises the wheel's file selection (hatchling's `artifacts` config, Task 3) or the
console_script entry point (Task 3's [project.scripts]). This is the one test that would catch
either being silently misconfigured.

Marked slow: builds a real wheel and creates a real venv. Not part of the default fast test
loop -- run explicitly via `python3 -m pytest scripts/tests/test_sb_wheel_smoke.py -v`.
"""

from __future__ import annotations

import subprocess
import sys
import venv
from pathlib import Path

import pytest

from scripts.build_sb_snapshot import build_snapshot

ROOT = Path(__file__).resolve().parents[2]
CLI_ROOT = ROOT / "cli"


@pytest.mark.slow
def test_sb_wheel_builds_installs_and_runs(tmp_path: Path) -> None:
    build_snapshot(ROOT)

    dist_dir = tmp_path / "dist"
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(dist_dir), str(CLI_ROOT)],
        check=True,
        capture_output=True,
        text=True,
    )
    wheels = list(dist_dir.glob("software_builder_cli-*.whl"))
    assert len(wheels) == 1, f"expected exactly one wheel, found {wheels}"

    venv_dir = tmp_path / "venv"
    venv.create(venv_dir, with_pip=True)
    venv_python = venv_dir / "bin" / "python3"

    subprocess.run(
        [str(venv_python), "-m", "pip", "install", "--quiet", str(wheels[0])],
        check=True,
        capture_output=True,
        text=True,
    )

    sb_executable = venv_dir / "bin" / "sb"
    assert sb_executable.is_file()

    result = subprocess.run(
        [str(sb_executable), "list"], check=False, capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "pr-review" in result.stdout

    result = subprocess.run(
        [str(sb_executable), "explain", "pr-review"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Skill: pr-review" in result.stdout
```

- [ ] **Step 3: Run the smoke test**

Run: `python3 -m pip install build>=1.2.2` (if not already present locally)
Run: `python3 -m pytest scripts/tests/test_sb_wheel_smoke.py -v`
Expected: PASS — this is the first test in the whole plan that runs the actually-installed `sb` executable, proving the wheel's `artifacts` config (Task 3) really ships `_vendored`/`_registry_snapshot`, and the `[project.scripts]` entry point really works.

If this fails with an empty or missing `_vendored`/`_registry_snapshot` inside the installed package (importable but `registry_snapshot_root()` empty), the most likely cause is hatchling's `artifacts` glob syntax needing adjustment for this hatchling version — check `pip show hatchling` version and its `artifacts` documentation for the installed version before assuming the plan's syntax is wrong.

- [ ] **Step 4: Register the `slow` marker** (avoid an "unknown marker" warning polluting test output)

Add to `cli/pyproject.toml`'s `[tool.pytest.ini_options]` section is not relevant here (`test_sb_wheel_smoke.py` lives under `scripts/tests/`, using the root `pyproject.toml`'s pytest config) — add to the root `pyproject.toml`'s `[tool.pytest.ini_options].markers` list (alongside the existing `mutates_repository_root` entry):

```toml
    "slow: builds a real wheel and installs it into a throwaway venv; not part of the default fast loop, run explicitly",
```

- [ ] **Step 5: Run the full existing suite to confirm no regression**

Run: `python3 -m pytest scripts/tests/ -q --deselect scripts/tests/test_sb_wheel_smoke.py::test_sb_wheel_builds_installs_and_runs`
Expected: same baseline as before this plan (no new failures introduced)

- [ ] **Step 6: Commit**

```bash
git add requirements.txt requirements.lock scripts/tests/test_sb_wheel_smoke.py pyproject.toml
git commit -m "$(cat <<'EOF'
Add end-to-end wheel build/install smoke test for the sb package

Every prior cli/ test ran `python -m sb` from the source tree, never
exercising the actual wheel's file selection (hatchling's artifacts
config) or the installed console_script entry point. This builds a
real wheel, installs it into a throwaway venv, and runs the real
installed `sb list`/`sb explain` -- the one test that would catch
either being silently misconfigured. Marked slow, not part of the
default fast loop.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Self-review

**Spec coverage:** every command in the design's "Commands (this slice)" section (`doctor`, `list`, `explain`, `compatibility`) has a task wiring it and a parity test proving it matches checkout behavior (Tasks 5-6). The design's "Why this is safe to build now" claim (zero fork of resolution logic) is upheld literally — no task duplicates `cmd_doctor`/`cmd_list`/`cmd_explain`/`cmd_compatibility`'s bodies, only `_default_install_roots_for_host` is duplicated (Task 2 and Task 5's `__main__.py`), and that duplication is explicitly named and justified in Task 5's code comment (it's arg-resolution logic living in `doctor.py`'s `main()`, not in a library function `sb` could call directly — a real, acknowledged trade-off, not an oversight). The design's version-sync requirement is covered by Task 7. The design's empirically-verified file set is covered by Task 4, using the exact pathspecs and counts confirmed during planning. The design's "no `--surface`" scope boundary is respected in Task 5 (flag omitted, not stubbed).

**Placeholder scan:** Task 2's test has one deliberately-marked template block (`# ... build repo fixture ... #`) with an explicit instruction to follow the existing file's real fixture helper rather than an invented one — same pattern used successfully in the prior universal-agent-compatibility plan's Task 5, called out explicitly rather than left implicit. Task 5's doctor-parity test carries one explicit "check this while implementing" note about a possible line-slice — also called out, not silently assumed. Every other step has complete, runnable code.

**Type consistency:** `cmd_compatibility(root: Path, host_id: str, skill_id: str | None) -> int` (Task 1) is called identically in Task 6's `sb compatibility` wiring. `_default_install_roots_for_host(host: HostSpec, *, home: Path) -> list[Path]` has the same signature in both its Task 2 (`doctor.py`) and Task 5 (`cli/sb/__main__.py`) copies. `registry_snapshot_root()`/`vendored_scripts_root()` (Task 5's `_paths.py`) are used consistently across Tasks 5-6's `__main__.py` changes.

**Scope check:** 8 tasks, each independently testable and reviewable; no task depends on functionality two tasks ahead. `--surface` support, `sb install`/`uninstall`/`verify`, and `sb update` are explicitly out of scope per the design spec and not smuggled in anywhere here.
