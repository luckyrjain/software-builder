# Versioned Plugin Bundle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `package-plugin` CLI command building a versioned, checksummed archive (generic
bundle + `.claude-plugin/`/`.codex-plugin/`) that CI uploads to every tagged release, so a user can
pin a Claude Code / Codex plugin install to a specific version instead of only tracking `main` live.

**Architecture:** Extend `scripts/registry/generic_package.py` additively (new
`_plugin_package_files`/`build_plugin_package_bytes`/`build_plugin_package`, sharing the existing
tar-writing logic via one small extracted helper), wire a new `package-plugin` subcommand into
`scripts/registry/cli.py` mirroring the existing `package-generic` wiring exactly, add one CI step to
`.github/workflows/release.yml` mirroring PR #260's "Build and upload sb wheel" step, and document
the new artifact in `docs/RELEASE.md`.

**Tech Stack:** Pure Python stdlib (`tarfile`, `gzip`) — no new dependency; reuses this repo's
existing `git ls-files`-based tracked-file collection.

## Global Constraints

- Additive only: `scripts/package_release.py`'s existing tarball, its `.claude-plugin`/`.codex-plugin`
  exclusion, and its own tests are untouched — this plan does not touch that file at all.
- No new `make` target — `package-generic` has none today (CLI/CI-invoked only); `package-plugin`
  follows the same convention.
- The plugin bundle = the exact existing generic bundle's file set, plus every git-tracked file under
  `.claude-plugin/` and `.codex-plugin/` in full — no per-host split, no minimal/reduced variant (see
  design spec's "Scope decisions from brainstorming").
- Reuse `_is_safe_file`/`_tracked_files` unchanged for the new directories — do not reimplement
  symlink/sensitive-file rejection; those already have dedicated coverage in
  `test_generic_package_security.py` that this plan does not duplicate.

---

### Task 1: Add `package-plugin` bundle building, CLI wiring, CI upload step, and docs

**Files:**
- Modify: `scripts/registry/generic_package.py`
- Modify: `scripts/registry/cli.py`
- Modify: `.github/workflows/release.yml`
- Modify: `docs/RELEASE.md`
- Create: `scripts/tests/test_plugin_package.py`

**Interfaces:**
- Consumes: `scripts.registry.generic_package._package_files` (existing, unchanged),
  `scripts.registry.generic_package._tracked_files`/`_is_safe_file` (existing, unchanged).
- Produces: `build_plugin_package_bytes(root: Path) -> bytes`, `build_plugin_package(root: Path,
  output: Path) -> None` (both mirroring the existing `build_generic_package_bytes`/
  `build_generic_package` pair exactly), a new `package-plugin` CLI subcommand.

- [ ] **Step 1: Write the failing tests**

Create `scripts/tests/test_plugin_package.py`:

```python
"""Plugin bundle build: the generic bundle's file set plus .claude-plugin/.codex-plugin.

Security/symlink/sensitive-file rejection is not re-tested here -- the plugin bundle reuses
_is_safe_file/_tracked_files unchanged, and that logic already has dedicated coverage in
test_generic_package_security.py.
"""

from __future__ import annotations

import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import pytest

from scripts.registry import cli as registry_cli
from scripts.registry.generic_package import build_generic_package, build_plugin_package

ROOT = Path(__file__).resolve().parents[2]


def test_registry_package_plugin_command(tmp_path: Path) -> None:
    output = tmp_path / "plugin.tar.gz"
    assert registry_cli.main(["package-plugin", "--output", str(output)]) == 0
    assert output.is_file()


@dataclass(frozen=True)
class _BuiltPluginPackage:
    member_names: frozenset[str]
    packaged_root: Path


@pytest.fixture(scope="module")
def plugin_package(tmp_path_factory: pytest.TempPathFactory) -> _BuiltPluginPackage:
    tmp_path = tmp_path_factory.mktemp("plugin-package")
    output = tmp_path / "plugin.tar.gz"
    build_plugin_package(ROOT, output)

    extract_root = tmp_path / "extract"
    with tarfile.open(output, "r:gz") as archive:
        names = frozenset(member.name for member in archive.getmembers())
        archive.extractall(extract_root, filter="data")

    return _BuiltPluginPackage(
        member_names=names,
        packaged_root=extract_root / "software-builder",
    )


def test_plugin_package_is_a_strict_superset_of_the_generic_package(
    tmp_path_factory: pytest.TempPathFactory,
    plugin_package: _BuiltPluginPackage,
) -> None:
    generic_tmp = tmp_path_factory.mktemp("generic-for-comparison")
    generic_output = generic_tmp / "generic.tar.gz"
    build_generic_package(ROOT, generic_output)
    with tarfile.open(generic_output, "r:gz") as archive:
        generic_names = frozenset(member.name for member in archive.getmembers())

    assert generic_names <= plugin_package.member_names


def test_plugin_package_carries_both_plugin_manifests(plugin_package: _BuiltPluginPackage) -> None:
    names = plugin_package.member_names
    assert "software-builder/.claude-plugin/plugin.json" in names
    assert "software-builder/.claude-plugin/marketplace.json" in names
    assert "software-builder/.codex-plugin/plugin.json" in names


def test_plugin_package_manifests_resolve_to_a_real_populated_skills_dir(
    plugin_package: _BuiltPluginPackage,
) -> None:
    import json

    claude_plugin = json.loads(
        (plugin_package.packaged_root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"),
    )
    codex_plugin = json.loads(
        (plugin_package.packaged_root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"),
    )
    assert claude_plugin["skills"] == "./skills"
    assert codex_plugin["skills"] == "./skills"

    skills_dir = plugin_package.packaged_root / "skills"
    assert skills_dir.is_dir()
    assert any(skills_dir.rglob("SKILL.md"))


def test_plugin_package_members_are_plain_relative_files(plugin_package: _BuiltPluginPackage) -> None:
    assert all(
        not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts
        for name in plugin_package.member_names
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest scripts/tests/test_plugin_package.py -v`
Expected: FAIL with `ImportError` — `build_plugin_package` does not exist yet, and `package-plugin`
is not a recognized `registry_cli.main` command.

- [ ] **Step 3: Extend `scripts/registry/generic_package.py`**

Extract the existing `build_generic_package_bytes` function's tar-writing loop into a shared helper,
then add the plugin-specific file collection and build functions. Replace the existing
`build_generic_package_bytes` function (currently):

```python
def build_generic_package_bytes(root: Path) -> bytes:
    root = root.resolve()
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for path in _package_files(root):
                rel = path.relative_to(root).as_posix()
                arcname = f"{PACKAGE_ROOT}/{rel}"
                data = _packaged_bytes(root, path)
                info = tarfile.TarInfo(arcname)
                info.size = len(data)
                info.mtime = 0
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                info.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
                archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()
```

with:

```python
def _build_package_bytes(root: Path, files: list[Path]) -> bytes:
    """Write `files` (already resolved, root-relative) into a deterministic tar.gz -- shared by
    the generic bundle and the plugin bundle so both go through one archive-writing code path."""
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for path in files:
                rel = path.relative_to(root).as_posix()
                arcname = f"{PACKAGE_ROOT}/{rel}"
                data = _packaged_bytes(root, path)
                info = tarfile.TarInfo(arcname)
                info.size = len(data)
                info.mtime = 0
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                info.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
                archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def build_generic_package_bytes(root: Path) -> bytes:
    root = root.resolve()
    return _build_package_bytes(root, _package_files(root))


def _plugin_package_files(root: Path) -> list[Path]:
    """The generic bundle's file set, plus every git-tracked file under .claude-plugin/ and
    .codex-plugin/ -- both hosts' plugin manifests, needed for the archive to work as a plugin
    marketplace source, not just a generic-host skill bundle."""
    root = root.resolve()
    candidates = set(_package_files(root))
    tracked = _tracked_files(root)
    for dirname in (".claude-plugin", ".codex-plugin"):
        plugin_dir = (root / dirname).resolve()
        if not plugin_dir.is_dir():
            raise ValueError(f"plugin package requires {dirname}")
        for path in tracked:
            try:
                path.relative_to(plugin_dir)
            except ValueError:
                continue
            if _is_safe_file(root, path):
                candidates.add(path.resolve())
    return sorted(candidates, key=lambda path: path.relative_to(root).as_posix())


def build_plugin_package_bytes(root: Path) -> bytes:
    root = root.resolve()
    return _build_package_bytes(root, _plugin_package_files(root))


def build_plugin_package(root: Path, output: Path) -> None:
    root = root.resolve()
    output = output.resolve()
    _validate_output_path(root, output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(build_plugin_package_bytes(root))
```

`_package_files` and `build_generic_package` (the existing public entry point) are otherwise
untouched — `build_generic_package` still calls `build_generic_package_bytes`, unchanged.

- [ ] **Step 4: Wire `package-plugin` into `scripts/registry/cli.py`**

Change the existing import (currently):

```python
from scripts.registry.generic_package import build_generic_package
```

to:

```python
from scripts.registry.generic_package import build_generic_package, build_plugin_package
```

Add a new command function directly after the existing `cmd_package_generic` (around line 304-307):

```python
def cmd_package_plugin(root: Path, output: Path) -> int:
    build_plugin_package(root, output)
    print(f"ok: wrote deterministic plugin package to {output}")
    return 0
```

Add a new subparser directly after the existing `package_parser` block (around line 469-476):

```python
    plugin_parser = subparsers.add_parser(
        "package-plugin",
        help="build the deterministic plugin bundle (generic bundle plus .claude-plugin/.codex-plugin)",
    )
    plugin_parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist/software-builder-plugin.tar.gz"),
        help="archive output path",
    )
```

Add dispatch directly after the existing `if args.command == "package-generic":` block (around
line 529-531):

```python
    if args.command == "package-plugin":
        output = args.output if args.output.is_absolute() else ROOT / args.output
        return _run_command(lambda: cmd_package_plugin(ROOT, output.resolve()))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest scripts/tests/test_plugin_package.py -v`
Expected: PASS (all 5 tests).

Run: `python3 -m pytest scripts/tests/test_generic_package.py scripts/tests/test_generic_package_security.py -v`
Expected: PASS — confirms the refactor (`_build_package_bytes` extraction) didn't change
`build_generic_package`'s behavior; `test_generic_package_build_is_byte_deterministic` in particular
must still pass unchanged.

- [ ] **Step 6: Add the CI upload step to `.github/workflows/release.yml`**

Add a new step directly after the existing "Build and upload sb wheel" step:

```yaml
      - name: Build and upload plugin bundle
        env:
          GH_TOKEN: ${{ github.token }}
          RELEASE_TAG: ${{ steps.tag.outputs.name }}
        run: |
          VERSION="${RELEASE_TAG#v}"
          python3 -m scripts.registry package-plugin --output "dist/software-builder-plugin-${VERSION}.tar.gz"
          sha256sum "dist/software-builder-plugin-${VERSION}.tar.gz" > "dist/software-builder-plugin-${VERSION}.tar.gz.sha256"
          gh release upload "$RELEASE_TAG" \
            "dist/software-builder-plugin-${VERSION}.tar.gz" \
            "dist/software-builder-plugin-${VERSION}.tar.gz.sha256" \
            --clobber
```

- [ ] **Step 7: Document the new artifact in `docs/RELEASE.md`**

Add a new section directly after the existing "## Installing a tagged release" section (after its
closing code fence, before "## Release contract"):

```markdown
## Installing a versioned plugin bundle

Every tagged release also publishes a plugin bundle for Claude Code / Codex, an alternative to
adding this repository as a live (`main`-tracking) plugin marketplace source:

```bash
curl -LO https://github.com/luckyrjain/software-builder/releases/download/v1.4.0/software-builder-plugin-1.4.0.tar.gz
curl -LO https://github.com/luckyrjain/software-builder/releases/download/v1.4.0/software-builder-plugin-1.4.0.tar.gz.sha256
shasum -c software-builder-plugin-1.4.0.tar.gz.sha256
tar -xzf software-builder-plugin-1.4.0.tar.gz
```

Then add the extracted `software-builder/` directory as a local plugin marketplace source in your
Claude Code / Codex client. The bundle is the same deterministic, git-tracked-only skill set
`python3 -m scripts.registry package-generic` produces, plus `.claude-plugin/` and `.codex-plugin/`
(built via `python3 -m scripts.registry package-plugin`) -- one archive works as a plugin source for
both hosts and as a generic bundle for any other.
```

(Adjust the example version/URL only if the plugin bundle's first real release has already happened
by the time this step runs — otherwise leave `v1.4.0` as the illustrative placeholder matching the
rest of this file's existing examples, which already use that same version throughout.)

- [ ] **Step 8: Verify the motivating use case end to end**

Run: `python3 -m scripts.registry package-plugin --output /tmp/plugin-test.tar.gz` (or any scratch
path) and confirm it exits 0 with `ok: wrote deterministic plugin package to ...`.

Extract it and confirm `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json` are both present
at the extracted root alongside a populated `skills/` directory — the exact real-world flow a user
follows after downloading a release asset.

- [ ] **Step 9: Run full validation**

Run: `python3 -m scripts.registry validate`
Expected: exit 0, same `ok: ...` success line as before (this task adds a new packaging path, not a
registry/schema change — nothing this task touches is read by `validate`).

Run: `python3 -m ruff check .`
Expected: `All checks passed!`

- [ ] **Step 10: Commit**

```bash
git add scripts/registry/generic_package.py scripts/registry/cli.py scripts/tests/test_plugin_package.py .github/workflows/release.yml docs/RELEASE.md
git commit -m "Add package-plugin: versioned plugin bundle for Claude Code/Codex releases"
```

## Self-Review

- **Placeholder scan:** no TBD/TODO; every function body, CLI wiring diff, and workflow step is
  complete, runnable code.
- **Spec coverage:** the design spec's entire scope (new archive function, CLI subcommand, CI upload
  step, docs) is covered by this single task.
- **Type consistency:** `build_plugin_package_bytes(root: Path) -> bytes` / `build_plugin_package(root:
  Path, output: Path) -> None` mirror `build_generic_package_bytes`/`build_generic_package`'s existing
  signatures exactly; `cmd_package_plugin(root: Path, output: Path) -> int` mirrors
  `cmd_package_generic`'s existing signature exactly.
