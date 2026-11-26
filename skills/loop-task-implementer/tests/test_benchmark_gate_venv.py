"""Tests for the C4c-2c pieces of `benchmark_gate.py`: `snapshot_venv`, `check_venv` and the `snapshot-venv` CLI.

Fake venvs only (a directory with `pyvenv.cfg`, `bin/` and `lib/python3.12/site-packages`), as the design asks: no real venvs in unit tests.
The `.pth` lines are the ones the real editable backends write (setuptools finder, hatchling/pdm path lines, flit/poetry path lines,
pytest-cov's `a1_coverage.pth`). Design: docs/superpowers/specs/2026-10-02-c4-performance-review-executor-handoff-design.md.

The `snapshot-venv` CLI also prints `snapshot_sha256: <hex>` (the written file's bytes) and `interpreter_sha256: <hex>` (the interpreter pin),
both computed before any install; they are what `compare` takes in `Side`. The interpreter pin itself (`interpreter_pin`) is tested in
test_benchmark_gate_compare.py (C4d-3).
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import stat
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, module)
    spec.loader.exec_module(module)
    return module


bg = _load(_SCRIPTS / "benchmark_gate.py", "benchmark_gate")
Err = bg.BenchmarkGateError


@pytest.fixture
def world(tmp_path):
    """`(venv_root, bin_dir, site, export_root, snapshot_path)`; the venv lies OUTSIDE the export, as in the design."""
    export = tmp_path / "export"
    export.mkdir()
    (export / "src").mkdir()
    venv = tmp_path / "venv"
    site = venv / "lib" / "python3.12" / "site-packages"
    site.mkdir(parents=True)
    (venv / "bin").mkdir()
    (venv / "pyvenv.cfg").write_text("home = /usr/bin\ninclude-system-site-packages = false\nversion = 3.12.1\n")
    return venv, venv / "bin", site, export, tmp_path / "snap.json"


def snapshot(w):
    bg.snapshot_venv(str(w[1]), str(w[4]))


def check(w, other_roots=()):
    return bg.check_venv(str(w[1]), str(w[4]), str(w[3]), other_roots)


def rejected(w, code="VENV_HOOK_REJECTED"):
    with pytest.raises(Err) as info:
        check(w)
    assert info.value.code == code
    return info.value


# --- accepted installs: what the real backends write -------------------------------------------------------------------------------

@pytest.mark.parametrize("name, content", [
    ("__editable__.pkg-1.0.pth", "import __editable___pkg_1_0_finder; __editable___pkg_1_0_finder.install()\n"),   # setuptools
    ("_editable_impl_pkg.pth", "{export}/src\n"),                                                                       # hatchling, pdm-backend
    ("pkg.pth", "{export}\n"),                                                                                          # flit, poetry-core
    ("pkg.pth", "# a comment\n\n{export}/src\n"),
    ("_pkg.pth", "import _editable_impl_pkg\n"),
    ("pkg.pth", "../../../../export/src\n"),                                                                            # relative to site-packages
    ("pkg.pth", "{export}/does-not-exist-yet\n"),
    ("pkg.pth", "﻿{export}\r\n"),                                                                                  # BOM, CRLF
])
def test_what_the_real_editable_backends_write_is_accepted(world, name, content):
    snapshot(world)
    (world[2] / name).write_text(content.format(export=world[3]), encoding="utf-8")
    check(world)


def test_a_venv_with_no_new_hook_passes_and_an_unchanged_prior_pth_is_not_judged(world):
    (world[2] / "distutils-precedence.pth").write_text("import os; var = 'x'\n")  # present BEFORE the install: the venv's own
    snapshot(world)
    check(world)


def test_a_removed_entry_is_ignored(world):
    (world[2] / "old.pth").write_text("import os\n")
    snapshot(world)
    (world[2] / "old.pth").unlink()
    check(world)


# --- refused installs -----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("content", [
    "import coverage; coverage.process_startup()\n",        # pytest-cov's a1_coverage.pth shape
    "import os\n",
    "import __editable___pkg_finder; __editable___other_finder.install()\n",
    "import __editable___pkg_finder; __editable___pkg_finder.install(); import os\n",
    "import __editable___pkg_finder;__editable___pkg_finder.install()\n",
    "import __editable___pkg_finder; __editable___pkg_finder.install() \n",
    "import\tos\n",
    "/usr/lib/python3\n",
    "{export}/../elsewhere\n",
    "{export}2\n",
    "/\n",
    "{export}\nimport os\n",
    "{export}\rimport os\n",                                  # a bare CR ends a line for Python
    "import _editable_impl_pkg; import os\n",
    "import _editable_impl_pkg.sub\n",
    "x\0\n",
])
def test_a_pth_line_that_is_not_a_path_in_the_export_or_an_editable_finder_is_refused(world, content):
    snapshot(world)
    (world[2] / "a1_coverage.pth").write_bytes(content.format(export=world[3]).encode())
    error = rejected(world)
    assert error.hits[0]["path"].endswith("a1_coverage.pth") and error.detail.startswith("venv hooks, 1, first 1: ")


@pytest.mark.parametrize("sep", ["\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"])
@pytest.mark.parametrize("before", ["# comment", "{export}"])
def test_every_line_separator_python_may_use_hides_nothing(world, sep, before):
    snapshot(world)
    body = before.format(export=world[3]) + sep + "import os; open('x', 'w')\n"
    (world[2] / "x.pth").write_text(body, encoding="utf-8")
    rejected(world)


def test_a_pth_symlink_into_the_export_is_refused(world):
    snapshot(world)
    (world[3] / "real.pth").write_text("import os\n")
    os.symlink(world[3] / "real.pth", world[2] / "x.pth")
    assert "not a regular file" in rejected(world).hits[0]["reason"]


def test_a_pth_that_is_a_directory_is_refused(world):
    snapshot(world)
    (world[2] / "x.pth").mkdir()
    assert "not a regular file" in rejected(world).hits[0]["reason"]


def test_a_pth_that_is_not_utf8_or_too_large_or_too_long_is_refused(world):
    snapshot(world)
    (world[2] / "a.pth").write_bytes(b"\xff\xfe\n")
    (world[2] / "b.pth").write_bytes(b"#" * (bg._PTH_MAX_BYTES + 1))
    (world[2] / "c.pth").write_bytes(b"#\n" * (bg._PTH_MAX_LINES + 1))
    assert {h["path"].rsplit("/", 1)[1] for h in rejected(world).hits} == {"a.pth", "b.pth", "c.pth"}


def test_a_changed_pth_is_judged_again(world):
    (world[2] / "pkg.pth").write_text(f"{world[3]}\n")
    snapshot(world)
    (world[2] / "pkg.pth").write_text("import os\n")
    rejected(world)


@pytest.mark.parametrize("name", ["PKG.PTH", ".hidden.pth", "pkg.pth ", "pkg.pth."])
def test_pth_names_python_or_a_filesystem_may_still_read_are_judged(world, name):
    snapshot(world)
    (world[2] / name).write_text("import os\n")
    rejected(world)


@pytest.mark.parametrize("name, is_dir", [
    ("sitecustomize.py", False), ("usercustomize.py", False), ("SiteCustomize.py", False), ("sitecustomize.cpython-312-darwin.so", False),
    ("usercustomize.abi3.so", False), ("sitecustomize.pyc", False), ("usercustomize.cpython-312.pyc", False), ("sitecustomize.pyd", False), ("sitecustomize", True), ("usercustomize", True),
])
def test_a_new_startup_module_in_any_form_is_refused(world, name, is_dir):
    snapshot(world)
    if is_dir:
        (world[2] / name).mkdir()
    else:
        (world[2] / name).write_bytes(b"x")
    assert rejected(world).hits[0]["reason"] == "a new or changed startup module"


def test_a_changed_startup_module_is_refused(world):
    (world[2] / "sitecustomize.py").write_text("pass\n")
    snapshot(world)
    (world[2] / "sitecustomize.py").write_text("print(1)\n")
    rejected(world)


def test_near_miss_names_are_not_hooks(world):
    snapshot(world)
    for name in ("sitecustomizer.py", "my_usercustomize.py", "pth", "x.pth.bak", "sitecustomize.txt", "readme.md"):
        (world[2] / name).write_text("import os\n")
    check(world)


def test_hits_are_counted_and_listed_five_at_a_time(world):
    snapshot(world)
    for i in range(8):
        (world[2] / f"p{i}.pth").write_text("import os\n")
    error = rejected(world)
    assert error.detail.startswith("venv hooks, 8, first 5: ") and len(error.hits) == 8


# --- isolation of the venv itself ----------------------------------------------------------------------------------------------

def test_system_site_packages_make_the_venv_not_isolated(world):
    (world[0] / "pyvenv.cfg").write_text("include-system-site-packages = true\n")
    with pytest.raises(Err) as info:
        snapshot(world)
    assert info.value.code == "VENV_NOT_ISOLATED"


def test_a_missing_pyvenv_cfg_is_not_a_fresh_venv(world):
    (world[0] / "pyvenv.cfg").unlink()
    with pytest.raises(Err) as info:
        snapshot(world)
    assert info.value.code == "VENV_NOT_ISOLATED"


def test_a_pyvenv_cfg_symlink_is_not_followed(world, tmp_path):
    (world[0] / "pyvenv.cfg").unlink()
    (tmp_path / "cfg").write_text("home = /x\n")
    os.symlink(tmp_path / "cfg", world[0] / "pyvenv.cfg")
    with pytest.raises(Err) as info:
        snapshot(world)
    assert info.value.code == "VENV_NOT_ISOLATED"


@pytest.mark.parametrize("bad", [None, 3, "", "relative-name-not-bin", "x\0/bin", b"/tmp/bin", "/nonexistent-dir/bin"])
def test_a_bad_bin_argument_is_refused(world, bad):
    with pytest.raises(Err) as info:
        bg.snapshot_venv(bad, str(world[4]))
    assert info.value.code == "VENV_NOT_ISOLATED"


def test_check_venv_returns_the_real_root_of_the_venv_so_the_two_sides_can_be_told_apart(world):
    snapshot(world)
    assert check(world) == os.path.realpath(world[0])


def test_a_venv_without_site_packages_is_not_isolated(world):
    os.rmdir(world[2])
    with pytest.raises(Err) as info:
        snapshot(world)
    assert info.value.code == "VENV_NOT_ISOLATED"


def test_site_packages_that_resolves_outside_the_venv_is_refused(world, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    os.rmdir(world[2])
    os.symlink(outside, world[2])
    with pytest.raises(Err) as info:
        snapshot(world)
    assert info.value.code == "VENV_NOT_ISOLATED"


def test_bin_as_a_symlink_is_refused(world, tmp_path):
    real = tmp_path / "realbin"
    real.mkdir()
    os.rmdir(world[1])
    os.symlink(real, world[1])
    with pytest.raises(Err) as info:
        snapshot(world)
    assert info.value.code == "VENV_NOT_ISOLATED"


def test_lib64_pointing_at_lib_is_one_site_directory(world):
    os.symlink("lib", world[0] / "lib64")
    snapshot(world)
    (world[2] / "x.pth").write_text("import os\n")
    assert len(rejected(world).hits) == 1


def test_a_venv_inside_an_export_is_not_isolated(world, tmp_path):
    inner = world[3] / "venv"
    os.rename(world[0], inner)
    bg.snapshot_venv(str(inner / "bin"), str(world[4]))
    with pytest.raises(Err) as info:
        bg.check_venv(str(inner / "bin"), str(world[4]), str(world[3]), ())
    assert info.value.code == "VENV_NOT_ISOLATED"


def test_an_export_inside_the_venv_is_not_isolated(world):
    export = world[0] / "export"
    export.mkdir()
    snapshot(world)
    with pytest.raises(Err) as info:
        bg.check_venv(str(world[1]), str(world[4]), str(export), ())
    assert info.value.code == "VENV_NOT_ISOLATED"


def test_the_other_export_root_may_not_contain_the_venv(world, tmp_path):
    snapshot(world)
    with pytest.raises(Err) as info:
        check(world, other_roots=(str(tmp_path),))
    assert info.value.code == "VENV_NOT_ISOLATED"


# --- the snapshot file ----------------------------------------------------------------------------------------------------------

def test_an_existing_snapshot_path_is_refused_and_not_overwritten(world):
    world[4].write_text("keep")
    with pytest.raises(Err) as info:
        snapshot(world)
    assert info.value.code == "DEST_REJECTED" and world[4].read_text() == "keep"


def test_the_snapshot_records_hooks_with_hashes_and_nothing_else(world):
    (world[2] / "a.pth").write_text("x\n")
    (world[2] / "numpy").mkdir()
    snapshot(world)
    data = json.loads(world[4].read_text())
    assert data["kind"] == bg._VENV_SNAPSHOT_KIND and data["version"] == 1 and data["venv"] == str(world[0].resolve())
    assert list(data["entries"]) == ["lib/python3.12/site-packages/a.pth"]
    assert data["entries"]["lib/python3.12/site-packages/a.pth"]["kind"] == "file" and len(data["entries"]["lib/python3.12/site-packages/a.pth"]["sha256"]) == 64


@pytest.mark.parametrize("content", [
    b"", b"not json", b"[]", b"{}", b'{"kind": "x"}',
    json.dumps({"kind": "software-builder-bench-venv-snapshot", "version": 2, "venv": "v", "entries": {}}).encode(),
    json.dumps({"kind": "software-builder-bench-venv-snapshot", "version": 1, "venv": "v", "entries": []}).encode(),
    json.dumps({"kind": "software-builder-bench-venv-snapshot", "version": 1, "venv": "v", "entries": {"a": 1}}).encode(),
    json.dumps({"kind": "software-builder-bench-venv-snapshot", "version": 1, "venv": "v", "entries": {"a": {"kind": 1, "sha256": ""}}}).encode(),
    b"\xff\xfe",
])
def test_a_missing_or_malformed_snapshot_is_a_caller_error_not_a_verdict(world, content):
    world[4].write_bytes(content)
    with pytest.raises(Err) as info:
        check(world)
    assert info.value.code == "VENV_SNAPSHOT_INVALID"


def test_a_snapshot_of_another_venv_is_refused(world, tmp_path):
    other = tmp_path / "venv2"
    (other / "lib" / "python3.12" / "site-packages").mkdir(parents=True)
    (other / "bin").mkdir()
    (other / "pyvenv.cfg").write_text("home = /usr/bin\n")
    bg.snapshot_venv(str(other / "bin"), str(world[4]))
    with pytest.raises(Err) as info:
        check(world)
    assert info.value.code == "VENV_SNAPSHOT_INVALID"


def test_no_snapshot_file_is_a_caller_error(world):
    with pytest.raises(Err) as info:
        check(world)
    assert info.value.code == "VENV_SNAPSHOT_INVALID"


def test_a_snapshot_that_is_a_symlink_is_not_followed(world, tmp_path):
    snapshot(world)
    real = tmp_path / "real.json"
    os.rename(world[4], real)
    os.symlink(real, world[4])
    with pytest.raises(Err) as info:
        check(world)
    assert info.value.code == "VENV_SNAPSHOT_INVALID"


def test_a_missing_export_root_is_refused(world):
    snapshot(world)
    with pytest.raises(Err) as info:
        bg.check_venv(str(world[1]), str(world[4]), str(world[3] / "nope"), ())
    assert info.value.code == "DEST_REJECTED"


# --- CLI ------------------------------------------------------------------------------------------------------------------------

@pytest.fixture
def pinned_world(world, tmp_path, monkeypatch):
    """`world` plus what the interpreter pin needs: `bin/python` -> `bin/python3.12` -> a small fake prefix, and a `pyvenv.cfg` whose `home`
    is that prefix's `bin`. The start-up probe is stubbed (the fake interpreter is a shell stub); the real one has its own rows."""
    prefix = tmp_path / "interp"
    (prefix / "bin").mkdir(parents=True)
    exe = prefix / "bin" / "python3.12"
    exe.write_text("#!/bin/sh\nexit 0\n")
    exe.chmod(0o755)
    (prefix / "lib" / "python3.12").mkdir(parents=True)
    (prefix / "lib" / "python3.12" / "os.py").write_text("# fake stdlib\n")
    venv, bin_dir = world[0], world[1]
    (bin_dir / "python3.12").symlink_to(exe)
    (bin_dir / "python").symlink_to("python3.12")
    (venv / "pyvenv.cfg").write_text(f"home = {prefix / 'bin'}\ninclude-system-site-packages = false\nversion = 3.12.1\n")
    real = os.path.realpath(prefix)
    monkeypatch.setattr(bg, "_startup_probe", lambda python, env: "\n".join([real, os.path.join(real, "lib", "python3.12", "os.py"), real]) + "\n")
    return world


def test_cli_snapshot_venv_writes_the_file(pinned_world, capsys):
    world = pinned_world
    assert bg.main(["snapshot-venv", "--bin", str(world[1]), "--out", str(world[4])]) == 0
    assert json.loads(world[4].read_text())["kind"] == bg._VENV_SNAPSHOT_KIND


def test_snapshot_venv_prints_both_pins(pinned_world, capsys):
    import hashlib
    world = pinned_world
    assert bg.main(["snapshot-venv", "--bin", str(world[1]), "--out", str(world[4])]) == 0
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 2 and out[0].startswith("snapshot_sha256: ") and out[1].startswith("interpreter_sha256: ")
    assert re.fullmatch(r"snapshot_sha256: [0-9a-f]{64}", out[0]) and re.fullmatch(r"interpreter_sha256: [0-9a-f]{64}", out[1])
    assert out[0].split(": ")[1] == hashlib.sha256(world[4].read_bytes()).hexdigest()
    assert out[1].split(": ")[1] == bg.interpreter_pin(str(world[1])).sha256


def test_snapshot_venv_missing_or_oversized_stdlib_exits_2_with_the_code_on_stderr(pinned_world, capsys, monkeypatch):
    world = pinned_world
    prefix = Path(os.path.realpath(world[1] / "python")).parent.parent
    os.rename(prefix / "lib" / "python3.12", prefix / "lib" / "gone")
    assert bg.main(["snapshot-venv", "--bin", str(world[1]), "--out", str(world[4])]) == 2
    cap = capsys.readouterr()
    assert "DEST_REJECTED" in cap.err and cap.out == "" and not world[4].exists()
    os.rename(prefix / "lib" / "gone", prefix / "lib" / "python3.12")
    limit = bg._INTERPRETER_LIMIT
    monkeypatch.setattr(bg, "_INTERPRETER_LIMIT", 1)
    assert bg.main(["snapshot-venv", "--bin", str(world[1]), "--out", str(world[4])]) == 2
    cap = capsys.readouterr()
    assert "TREE_TOO_LARGE" in cap.err and cap.out == "" and not world[4].exists()
    monkeypatch.setattr(bg, "_INTERPRETER_LIMIT", limit)
    assert bg.main(["snapshot-venv", "--bin", str(world[1]), "--out", str(world[4])]) == 0  # a retry is not blocked by a leftover file


def test_snapshot_venv_cli_fails_instead_of_hashing_a_truncated_read(pinned_world, capsys, monkeypatch):
    """One limit for every reader: a snapshot bigger than `_VENV_MAX_SNAPSHOT_BYTES` could never be loaded by `compare`, so the command that mints its
    pin must refuse it (the bounded read returns limit + 1 bytes: hashing those would pin a file that is not the file)."""
    world = pinned_world
    monkeypatch.setattr(bg, "_VENV_MAX_SNAPSHOT_BYTES", 10)
    assert bg.main(["snapshot-venv", "--bin", str(world[1]), "--out", str(world[4])]) == 2
    cap = capsys.readouterr()
    assert cap.out == "" and "VENV_SNAPSHOT_INVALID" in cap.err
    assert not world[4].exists()  # the oversize file is removed: a retry on the same --out is not blocked
    monkeypatch.setattr(bg, "_VENV_MAX_SNAPSHOT_BYTES", 4 << 20)
    assert bg.main(["snapshot-venv", "--bin", str(world[1]), "--out", str(world[4])]) == 0


def test_compare_and_the_loader_use_the_one_snapshot_limit(tmp_path, monkeypatch):
    import hashlib
    path = tmp_path / "snap.json"
    path.write_bytes(b"x" * 100)
    side = bg.Side(str(tmp_path), "c" * 40, str(tmp_path / "bin"), str(path), hashlib.sha256(path.read_bytes()).hexdigest(), "0" * 64)
    bg._check_snapshots(side, side, "pre_overlay")  # within the limit, and the hash matches
    monkeypatch.setattr(bg, "_VENV_MAX_SNAPSHOT_BYTES", 99)
    with pytest.raises(bg._Verdict) as caught:
        bg._check_snapshots(side, side, "pre_overlay")
    assert caught.value.detail == "SNAPSHOT_CHANGED"
    assert not hasattr(bg, "_SNAPSHOT_LIMIT") and bg._VENV_MAX_SNAPSHOT_BYTES == 99  # no second constant


def test_cli_snapshot_venv_failures_are_exit_2_with_the_code_on_stderr(world, capsys):
    (world[0] / "pyvenv.cfg").unlink()
    assert bg.main(["snapshot-venv", "--bin", str(world[1]), "--out", str(world[4])]) == 2
    assert "VENV_NOT_ISOLATED" in capsys.readouterr().err and not world[4].exists()


def test_cli_snapshot_venv_requires_both_arguments(world):
    assert bg.main(["snapshot-venv", "--bin", str(world[1])]) == 2


def test_an_unreadable_site_directory_is_tree_unreadable(world):
    if os.geteuid() == 0:
        pytest.skip("root reads everything")
    os.chmod(world[2], 0)
    try:
        with pytest.raises(Err) as info:
            snapshot(world)
        assert info.value.code == "TREE_UNREADABLE"
    finally:
        os.chmod(world[2], 0o700)




# --- additional tests from the mutation audit ------------------------------------------------------------------------------------

def _good_snapshot(w):
    snapshot(w)
    return json.loads(w[4].read_text())


def _invalid_snapshot(w, data):
    w[4].write_text(json.dumps(data))
    with pytest.raises(Err) as info:
        check(w)
    assert info.value.code == "VENV_SNAPSHOT_INVALID"


@pytest.mark.parametrize("cfg", [
    "Include-System-Site-Packages = True\n",
    "include-system-site-packages = TRUE\n",
    "include-system-site-packages = yes\n",
    "include-system-site-packages =\n",
    "home = /x\rinclude-system-site-packages = true\r",             # a bare CR ends a line for Python
    "include-system-site-packages = false\ninclude-system-site-packages = true\n",
])
def test_every_spelling_that_may_enable_system_site_packages_is_refused(world, cfg):
    (world[0] / "pyvenv.cfg").write_text(cfg)
    with pytest.raises(Err) as info:
        snapshot(world)
    assert info.value.code == "VENV_NOT_ISOLATED"


def test_a_cfg_spelling_false_in_any_case_is_isolated(world):
    (world[0] / "pyvenv.cfg").write_text("home = /x\n Include-System-Site-Packages = False \n")
    snapshot(world)


def test_bin_must_be_a_directory_named_bin(world):
    (world[0] / "scripts").mkdir()
    with pytest.raises(Err) as info:
        bg.snapshot_venv(str(world[0] / "scripts"), str(world[4]))
    assert info.value.code == "VENV_NOT_ISOLATED"


def test_a_nul_or_empty_bin_is_not_isolated_exactly(world, monkeypatch):
    with pytest.raises(Err) as info:
        bg.snapshot_venv(f"{world[0]}\0/bin", str(world[4]))
    assert info.value.code == "VENV_NOT_ISOLATED"
    monkeypatch.chdir(world[1])  # "" is the current directory, which here is named `bin`
    with pytest.raises(Err) as info:
        bg.snapshot_venv("", str(world[4]))
    assert info.value.code == "VENV_NOT_ISOLATED"


def test_a_venv_reached_through_a_symlinked_path_is_one_venv(world, tmp_path):
    link = tmp_path / "link"
    os.symlink(world[0], link)
    bg.snapshot_venv(str(link / "bin"), str(world[4]))
    assert json.loads(world[4].read_text())["venv"] == str(world[0].resolve())
    (world[2] / "pkg.pth").write_text(f"{world[3]}\n")
    bg.check_venv(str(link / "bin"), str(world[4]), str(world[3]), ())
    bg.check_venv(str(world[1]), str(world[4]), str(world[3]), ())


def test_roots_are_compared_after_resolving_symlinks(world, tmp_path):
    snapshot(world)
    (world[2] / "pkg.pth").write_text(f"{world[3]}/src\n")
    export_link = tmp_path / "export-link"
    os.symlink(world[3], export_link)
    bg.check_venv(str(world[1]), str(world[4]), str(export_link), ())  # a symlinked export root still matches its real path lines
    inner = world[0] / "inner"
    inner.mkdir()
    inner_link = tmp_path / "inner-link"
    os.symlink(inner, inner_link)
    with pytest.raises(Err) as info:  # an export root that is a symlink into the venv
        bg.check_venv(str(world[1]), str(world[4]), str(inner_link), ())
    assert info.value.code == "VENV_NOT_ISOLATED"
    parent_link = tmp_path / "parent-link"
    os.symlink(tmp_path, parent_link)
    with pytest.raises(Err) as info:  # an other root that is a symlink to a directory containing the venv
        check(world, other_roots=(str(parent_link),))
    assert info.value.code == "VENV_NOT_ISOLATED"


def test_the_filesystem_root_contains_the_venv(world):
    snapshot(world)
    with pytest.raises(Err) as info:
        check(world, other_roots=("/",))
    assert info.value.code == "VENV_NOT_ISOLATED"


def test_site_packages_symlinked_to_a_sibling_sharing_the_venv_name_prefix_is_outside(world, tmp_path):
    sibling = tmp_path / "venv2" / "sp"
    sibling.mkdir(parents=True)
    os.rmdir(world[2])
    os.symlink(sibling, world[2])
    with pytest.raises(Err) as info:
        snapshot(world)
    assert info.value.code == "VENV_NOT_ISOLATED"


def test_a_real_lib64_directory_is_scanned_as_well_as_lib(world):
    site64 = world[0] / "lib64" / "python3.12" / "site-packages"
    site64.mkdir(parents=True)
    snapshot(world)
    (world[2] / "a.pth").write_text("import os\n")
    (site64 / "b.pth").write_text("import os\n")
    assert [h["path"] for h in rejected(world).hits] == ["lib/python3.12/site-packages/a.pth", "lib64/python3.12/site-packages/b.pth"]


def test_entry_keys_name_the_lib_path_whichever_way_lib64_is_listed(world, monkeypatch):
    os.symlink("lib", world[0] / "lib64")
    (world[2] / "a.pth").write_text("# x\n")
    real = os.listdir
    monkeypatch.setattr(bg.os, "listdir", lambda p: sorted(real(p), reverse=True))
    assert list(_good_snapshot(world)["entries"]) == ["lib/python3.12/site-packages/a.pth"]


def test_a_site_packages_symlink_inside_the_venv_keeps_its_own_path_in_the_report(world):
    target = world[0] / "elsewhere"
    target.mkdir()
    os.rmdir(world[2])
    os.symlink(target, world[2])
    snapshot(world)
    (target / "x.pth").write_text("import os\n")
    assert rejected(world).hits[0]["path"] == "lib/python3.12/site-packages/x.pth"


def test_ten_thousand_hook_candidates_are_the_limit(world):
    for i in range(10_000):
        (world[2] / f"p{i}.pth").touch()
    snapshot(world)
    (world[2] / "one-more.pth").touch()
    error = rejected(world, "TREE_TOO_LARGE")
    assert "10000" in error.detail


def test_entry_kinds_are_recorded(world):
    (world[2] / "d.pth").mkdir()
    os.symlink(world[3], world[2] / "l.pth")
    os.mkfifo(world[2] / "f.pth")
    entries = _good_snapshot(world)["entries"]
    base = "lib/python3.12/site-packages/"
    assert {n: entries[base + n]["kind"] for n in ("d.pth", "l.pth", "f.pth")} == {"d.pth": "dir", "l.pth": "link", "f.pth": "other"}


def test_a_fifo_pth_is_refused_not_read(world):
    snapshot(world)
    os.mkfifo(world[2] / "f.pth")
    assert "not a regular file" in rejected(world).hits[0]["reason"]


def test_a_prior_pth_is_hashed_over_its_whole_content_up_to_the_cap(world):
    (world[2] / "a.pth").write_text("#" * 50 + "\n")
    (world[2] / "big.pth").write_text("#" * 70_000)
    snapshot(world)
    (world[2] / "a.pth").write_text("#" * 50 + "\nimport os\n")      # differs only after byte 11
    (world[2] / "big.pth").write_text("#" * 70_000 + "\nimport os\n")  # differs only after the 64 KiB mark
    assert {h["path"].rsplit("/", 1)[1] for h in rejected(world).hits} == {"a.pth", "big.pth"}


def test_every_read_inside_the_venv_refuses_symlinks(world, monkeypatch):
    calls = []
    real = bg._read_bounded

    def spy(path, limit, nofollow=False, dir_fd=None):
        calls.append((os.path.basename(path), nofollow))
        return real(path, limit, nofollow, dir_fd)

    monkeypatch.setattr(bg, "_read_bounded", spy)
    (world[2] / "a.pth").write_text("# x\n")
    snapshot(world)
    (world[2] / "b.pth").write_text(f"{world[3]}\n")
    check(world)
    assert {name for name, _ in calls} >= {"pyvenv.cfg", "a.pth", "b.pth", "snap.json"} and all(flag is True for _, flag in calls)


def test_a_dangling_symlink_or_empty_or_bytes_snapshot_path_is_refused(world, tmp_path):
    os.symlink(tmp_path / "nowhere", world[4])
    with pytest.raises(Err) as info:
        snapshot(world)
    assert info.value.code == "DEST_REJECTED" and not (tmp_path / "nowhere").exists()
    for bad in ("", b"snap2.json"):
        with pytest.raises(Err) as info:
            bg.snapshot_venv(str(world[1]), bad)
        assert info.value.code == "DEST_REJECTED"


def test_a_deeply_nested_snapshot_is_invalid_not_a_crash(world):
    world[4].write_bytes(b"[" * 200_000 + b"]" * 200_000)
    with pytest.raises(Err) as info:
        check(world)
    assert info.value.code == "VENV_SNAPSHOT_INVALID"


def test_a_snapshot_of_this_venv_with_a_wrong_header_or_entry_is_invalid(world):
    data = _good_snapshot(world)
    for key, value in (("version", 2), ("kind", "other"), ("entries", [])):
        _invalid_snapshot(world, {**data, key: value})
    for entry in (1, {"kind": 1, "sha256": ""}, {"kind": "file", "sha256": 5}, {"kind": "file"}, {"sha256": ""}):
        _invalid_snapshot(world, {**data, "entries": {"lib/python3.12/site-packages/a.pth": entry}})
    w4 = world[4]
    w4.write_text(json.dumps(data))
    check(world)  # the untampered one is accepted


def test_the_snapshot_file_size_limit_is_exactly_4_mib(world):
    text = json.dumps(_good_snapshot(world))
    world[4].write_text(text + " " * ((4 << 20) - len(text)))
    check(world)
    world[4].write_text(text + " " * ((4 << 20) + 1 - len(text)))
    with pytest.raises(Err) as info:
        check(world)
    assert info.value.code == "VENV_SNAPSHOT_INVALID"


def test_pth_size_and_line_limits_are_exact(world):
    snapshot(world)
    (world[2] / "ok1.pth").write_bytes(b"#" * 65_536)
    (world[2] / "ok2.pth").write_bytes(b"#\n" * 1000)
    check(world)
    (world[2] / "big.pth").write_bytes(b"#" * 65_537)
    (world[2] / "long.pth").write_bytes(b"#\n" * 1001)
    assert {h["path"].rsplit("/", 1)[1]: h["reason"] for h in rejected(world).hits} == {
        "big.pth": "a .pth file over 64 KiB", "long.pth": "a .pth file over 1000 lines"}


def test_a_non_utf8_byte_in_an_otherwise_good_path_is_refused_for_that_reason(world):
    snapshot(world)
    (world[2] / "a.pth").write_bytes(f"{world[3]}/".encode() + b"\xff\n")
    assert rejected(world).hits[0]["reason"] == "a .pth file that is not UTF-8"


@pytest.mark.parametrize("content", ["# c\rimport os\n", "# c\r\nimport os\n"])
def test_a_bare_cr_starts_a_new_line(world, content):
    snapshot(world)
    (world[2] / "a.pth").write_bytes(content.encode())
    assert rejected(world).hits[0]["reason"].startswith("import line")


@pytest.mark.parametrize("content", [
    "  \t \n",                            # a whitespace-only line is the site directory itself
    "{export}  \t\n",                    # trailing whitespace is stripped from a path line
    "import/../../../../../export\n",  # "import" without the space is a path line
    " import /../../../../../export\n",  # so is an indented import
])
def test_lines_python_reads_as_paths_or_comments_are_accepted(world, content):
    snapshot(world)
    (world[2] / "a.pth").write_text(content.format(export=world[3]), encoding="utf-8")
    check(world)


@pytest.mark.parametrize("content, reason", [
    (" # not a comment\n", "path outside the export"),         # only a line STARTING with # is a comment
    (" {export}\n", "path outside the export"),                 # leading whitespace is part of the name
    ("import\t../../../../../../export\n", "import line"),     # `import<TAB>` is executed
    ("import _editable_impl_\n", "import line"),
    ("import __editable____finder; __editable____finder.install()\n", "import line"),
    ("import __editable__pkg_finder; __editable__pkg_finder.install()\n", "import line"),
])
def test_other_lines_are_refused_for_the_right_reason(world, content, reason):
    snapshot(world)
    (world[2] / "a.pth").write_text(content.format(export=world[3]))
    assert rejected(world).hits[0]["reason"].startswith(reason)


def test_a_path_through_a_symlink_that_leaves_the_export_is_refused(world, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(outside, world[3] / "lnk")
    snapshot(world)
    (world[2] / "a.pth").write_text(f"{world[3]}/lnk\n")
    assert rejected(world).hits[0]["reason"].startswith("path outside the export")


def test_hits_are_reported_in_path_order_with_their_reasons(world):
    snapshot(world)
    for name in ("p3", "p1", "p2"):
        (world[2] / f"{name}.pth").write_text("import os\n")
    error = rejected(world)
    assert [h["path"].rsplit("/", 1)[1] for h in error.hits] == ["p1.pth", "p2.pth", "p3.pth"]
    assert error.detail.index("p1.pth") < error.detail.index("p2.pth") < error.detail.index("p3.pth") and "p1.pth (" in error.detail


def test_a_hit_path_is_escaped(world):
    snapshot(world)
    (world[2] / "a\nb.pth").write_text("import os\n")
    assert "\n" not in rejected(world).hits[0]["path"]


def test_a_changed_kind_is_a_change_even_when_neither_kind_is_hashed(world, tmp_path):
    (world[2] / "sitecustomize").mkdir()
    (world[2] / "x.pth").mkdir()
    snapshot(world)
    os.rmdir(world[2] / "sitecustomize")
    os.rmdir(world[2] / "x.pth")
    os.symlink(world[3], world[2] / "sitecustomize")
    os.symlink(world[3], world[2] / "x.pth")
    assert {h["path"].rsplit("/", 1)[1] for h in rejected(world).hits} == {"sitecustomize", "x.pth"}


def test_upper_case_pth_names_are_judged_as_pth_files(world):
    snapshot(world)
    (world[2] / "PKG.PTH").write_text(f"{world[3]}\n")
    check(world)
    (world[2] / "OTHER.PTH").write_text("import os\n")
    assert rejected(world).hits[0]["reason"].startswith("import line")


def test_check_failures_other_than_hooks_are_tree_unreadable(world):
    snapshot(world)
    with pytest.raises(Err) as info:
        bg.check_venv(str(world[1]), str(world[4]), None, ())
    assert info.value.code == "DEST_REJECTED"
    if os.geteuid() != 0:
        os.chmod(world[2], 0)
        try:
            with pytest.raises(Err) as info:
                check(world)
            assert info.value.code == "TREE_UNREADABLE"
        finally:
            os.chmod(world[2], 0o700)


def test_reasons_name_the_nul_and_the_offending_line(world):
    snapshot(world)
    (world[2] / "a.pth").write_bytes(b"x\0\n")
    (world[2] / "b.pth").write_text("/usr/lib/python3\n")
    reasons = {h["path"].rsplit("/", 1)[1]: h["reason"] for h in rejected(world).hits}
    assert reasons == {"a.pth": "a .pth file with a NUL", "b.pth": "path outside the export: /usr/lib/python3"}


def test_a_path_line_that_is_inside_the_export_only_by_resolving_a_symlink_is_refused(world, tmp_path):
    """CPython puts the LEXICAL path on sys.path: `<export>/a/lnk/../../..` collapses to a directory outside the export."""
    snapshot(world)
    deep = world[3] / "b" / "c" / "d"
    deep.mkdir(parents=True)
    os.symlink(deep, world[3] / "lnk")
    rel = os.path.relpath(world[3] / "lnk", world[2]) + "/../../.."
    assert os.path.realpath(os.path.join(world[2], rel)).startswith(str(world[3].resolve()))   # inside by realpath ...
    assert not os.path.abspath(os.path.join(world[2], rel)).startswith(str(world[3]))            # ... outside lexically
    (world[2] / "x.pth").write_text(rel + "\n")
    assert "path outside the export" in rejected(world).hits[0]["reason"]


def test_a_pyvenv_cfg_in_bin_is_not_isolated(world):
    (world[1] / "pyvenv.cfg").write_text("include-system-site-packages = true\n")
    with pytest.raises(Err) as info:
        snapshot(world)
    assert info.value.code == "VENV_NOT_ISOLATED"


def test_a_pyvenv_cfg_dropped_into_bin_by_the_install_is_refused(world):
    snapshot(world)
    (world[1] / "pyvenv.cfg").write_text("include-system-site-packages = true\n")
    rejected(world, "VENV_NOT_ISOLATED")


@pytest.mark.parametrize("export, others", [(None, ()), ("", ()), ("a\0b", ()), ("OK", ("",)), ("OK", ("a\0b",)), (b"/x", ()), ("OK", (None,)), ("OK", (3,)), ("OK", "/some/root"), ("OK", None), ("OK", 5)])
def test_bad_root_arguments_are_caller_errors(world, export, others):
    snapshot(world)
    export = str(world[3]) if export == "OK" else export
    with pytest.raises(Err) as info:
        bg.check_venv(str(world[1]), str(world[4]), export, others)
    assert info.value.code == "DEST_REJECTED"



def _trust_own_links(monkeypatch):
    """Stand in for root's `/var` -> `/private/var` (a link owned by uid 0 in a directory only root can change): the links this test creates are
    owned by the current user, in directories the current user can write, so both facts are simulated (the uid seam, and `os.access` W_OK false)."""
    monkeypatch.setattr(bg, "_TRUSTED_LINK_UID", os.getuid())
    real_access = os.access
    monkeypatch.setattr(bg.os, "access", lambda path, mode, *a, **k: False if mode & os.W_OK else real_access(path, mode, *a, **k))
    real_stat = os.stat

    def owned_stat(path, *a, **k):  # every ancestor must be owned by the trusted uid as well: the directories on the way up to `/` are root's or ours
        st = real_stat(path, *a, **k)
        if not stat.S_ISDIR(st.st_mode):
            return st
        return os.stat_result((st.st_mode, st.st_ino, st.st_dev, st.st_nlink, os.getuid(), st.st_gid, st.st_size,
                               int(st.st_atime), int(st.st_mtime), int(st.st_ctime)))
    monkeypatch.setattr(bg.os, "stat", owned_stat)


@pytest.mark.parametrize("line", ["{alias}/export/src\n", "../../../../export/src\n", "{real}/export/src\n"])
def test_paths_through_a_symlinked_parent_are_judged_by_where_they_point(world, tmp_path, line, monkeypatch):
    """macOS: the temp directory is `/var/...` -> `/private/var/...`; a caller may hold the venv and the export by the alias. The alias is
    a link of the TRUSTED uid here (the test stands in for root's `/var`): a link the user owns is refused, see the test below."""
    snapshot(world)
    alias = tmp_path.parent / (tmp_path.name + "-alias")
    os.symlink(tmp_path, alias)
    _trust_own_links(monkeypatch)
    try:
        bin_alias, export_alias = str(alias / "venv" / "bin"), str(alias / "export")
        (world[2] / "x.pth").write_text(line.format(alias=alias, real=tmp_path))
        assert bg.check_venv(bin_alias, str(world[4]), export_alias, ()) == os.path.realpath(world[0])
    finally:
        os.unlink(alias)


@pytest.mark.parametrize("line", ["{alias}/export/src\n", "../../../../export/src\n"])
def test_a_pth_path_through_a_link_the_user_owns_is_refused(world, tmp_path, line):
    """A head child (same uid) could repoint such a link after the check and leave it; the spawn guard re-checks resolved paths only."""
    snapshot(world)
    alias = tmp_path.parent / (tmp_path.name + "-useralias")
    os.symlink(tmp_path, alias)
    try:
        (world[2] / "x.pth").write_text(line.format(alias=alias))
        with pytest.raises(Err) as info:
            bg.check_venv(str(alias / "venv" / "bin"), str(world[4]), str(alias / "export"), ())
        assert info.value.code == "VENV_HOOK_REJECTED"
    finally:
        os.unlink(alias)


def _finder(target):
    return f"MAPPING = {{'pkg': {target!r}}}\nNAMESPACES = {{}}\n".encode()


def test_a_finder_target_through_a_user_owned_link_is_refused_and_through_a_trusted_one_accepted(tmp_path, monkeypatch):
    real = Path(os.path.realpath(tmp_path)) / "real"
    (real / "export" / "src" / "pkg").mkdir(parents=True)
    alias = Path(os.path.realpath(tmp_path)) / "alias"
    os.symlink(real, alias)
    export = str(real / "export")
    through = str(alias / "export" / "src" / "pkg")
    assert bg._finder_problem(_finder(str(real / "export" / "src" / "pkg")), export) is None  # the resolved path: accepted
    assert bg._finder_problem(_finder(through), export) == "a finder target resolves outside the export"  # the user owns the link
    _trust_own_links(monkeypatch)  # a root-owned link (macOS `/var`), simulated
    assert bg._finder_problem(_finder(through), export) is None
    monkeypatch.undo()
    assert bg._finder_problem(_finder(through), export) is not None  # and back to refused


@pytest.mark.parametrize("trusted", [False, True], ids=["user-owned", "trusted-uid"])
def test_a_finder_target_with_dot_dot_after_a_link_is_refused_whoever_owns_the_link(tmp_path, monkeypatch, trusted):
    """The kernel resolves the RAW target: `ul/..` goes to the PARENT of what `ul` points at, while `abspath` collapses it lexically and never meets
    the link, so a check on the collapsed string passed a target that a repointed `ul` would send elsewhere."""
    base = Path(os.path.realpath(tmp_path))
    (base / "a" / "b").mkdir(parents=True)
    (base / "dispatch" / "head" / "src" / "pkg").mkdir(parents=True)
    os.symlink(base / "a" / "b", base / "ul")  # base/ul/../.. is base: the raw target names base/dispatch/head/src/pkg
    raw = f"{base}/ul/../../dispatch/head/src/pkg"
    assert os.path.realpath(raw) == str(base / "dispatch" / "head" / "src" / "pkg")
    if trusted:
        _trust_own_links(monkeypatch)
    assert bg._finder_problem(_finder(raw), str(base / "dispatch" / "head")) == "a finder target resolves outside the export"
    for odd in (f"{base}/dispatch/head/./src/pkg", f"{base}//dispatch/head/src/pkg", f"{base}/dispatch/head/src/pkg/"):
        assert bg._finder_problem(_finder(odd), str(base / "dispatch" / "head")) is not None  # not normal: refused
    assert bg._finder_problem(_finder(str(base / "dispatch" / "head" / "src" / "pkg")), str(base / "dispatch" / "head")) is None


def test_a_root_run_trusts_no_alias_at_all(tmp_path, monkeypatch):
    """With an effective uid of 0 the head child is root too: a root-owned link is no more trustworthy than a user-owned one."""
    base = Path(os.path.realpath(tmp_path))
    (base / "real" / "export" / "src" / "pkg").mkdir(parents=True)
    os.symlink(base / "real", base / "alias")
    through = str(base / "alias" / "export" / "src" / "pkg")
    _trust_own_links(monkeypatch)
    monkeypatch.setattr(os, "geteuid", lambda: os.getuid() + 1)  # not root: the (patched) trusted link is accepted
    assert bg._finder_problem(_finder(through), str(base / "real" / "export")) is None
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    assert bg._finder_problem(_finder(through), str(base / "real" / "export")) == "a finder target resolves outside the export"
    assert bg._alias_accepted(through) is False


def test_the_codecs_of_the_compare_path_are_loaded_at_import():
    """A first `utf-8-sig` decode (a `.pth` file) would import from the harness interpreter's stdlib, possibly after a child ran."""
    import subprocess
    code = ("import importlib.util, sys\n"
            "spec = importlib.util.spec_from_file_location('bgx', sys.argv[1]); m = importlib.util.module_from_spec(spec)\n"
            "sys.modules['bgx'] = m; before = 'encodings.utf_8_sig' in sys.modules; spec.loader.exec_module(m)\n"
            "assert 'encodings.utf_8_sig' in sys.modules and 'encodings.ascii' in sys.modules, 'not loaded at import'\n"
            "print('ok')\n")
    done = subprocess.run([sys.executable, "-I", "-c", code, str(_SCRIPTS / "benchmark_gate.py")], capture_output=True, text=True, timeout=120,
                          env={"PYTHONDONTWRITEBYTECODE": "1"})
    assert done.returncode == 0 and done.stdout.strip() == "ok", done.stderr


def test_a_nested_user_owned_link_behind_a_trusted_one_is_still_refused(tmp_path, monkeypatch):
    base = Path(os.path.realpath(tmp_path))
    (base / "real" / "export" / "src").mkdir(parents=True)
    os.symlink(base / "real", base / "user")           # user-owned, reached through the trusted one below
    os.symlink(base / "user", base / "trusted")        # "root-owned": the first hop only
    real_lstat = os.lstat

    def lstat(path, *a, **k):
        st = real_lstat(path, *a, **k)
        if os.fspath(path) != str(base / "trusted"):
            return st
        return os.stat_result((st.st_mode, st.st_ino, st.st_dev, st.st_nlink, 0, st.st_gid, st.st_size, int(st.st_atime), int(st.st_mtime),
                               int(st.st_ctime)))
    monkeypatch.setattr(bg.os, "lstat", lstat)
    _trust_own_links(monkeypatch)
    monkeypatch.setattr(bg, "_TRUSTED_LINK_UID", 0)  # the first hop (reported as uid 0) is trusted; the second is owned by the user
    assert bg._only_trusted_aliases(str(base / "trusted" / "export" / "src")) is False  # the second hop is the user's
    assert bg._only_trusted_aliases(str(base / "real" / "export" / "src")) is True      # no link at all
    assert bg._only_trusted_aliases(str(base / "real" / "missing" / "x")) is True       # a missing component ends the walk


def _one_link(tmp_path):
    base = Path(os.path.realpath(tmp_path))
    (base / "real" / "export").mkdir(parents=True)
    os.symlink(base / "real", base / "alias")
    return base, str(base / "alias" / "export")


def test_a_link_in_a_directory_the_user_can_write_is_refused_even_when_its_uid_is_trusted(tmp_path, monkeypatch):
    """The owner of a link is not who can replace it: whoever can rename or unlink in its directory can (the round-5 swap: pre-swap and post-swap
    `_alias_accepted` both said True)."""
    base, through = _one_link(tmp_path)
    monkeypatch.setattr(bg, "_TRUSTED_LINK_UID", os.getuid())  # the uid check alone passes; the directory is the user's
    assert os.access(base, os.W_OK)
    assert bg._only_trusted_aliases(through) is False and bg._alias_accepted(through) is False
    os.rename(base / "alias", base / "moved")  # the swap a head child could do: a different link under the same name
    os.symlink(base / "real", base / "alias")
    assert bg._alias_accepted(through) is False


def test_a_link_in_a_root_owned_directory_is_accepted_the_macos_var_style(tmp_path, monkeypatch):
    base, through = _one_link(tmp_path)
    _trust_own_links(monkeypatch)  # the uid seam and a directory the euid cannot write
    assert os.stat(base).st_mode & 0o022 == 0
    assert bg._only_trusted_aliases(through) is True and bg._alias_accepted(through) is True


@pytest.mark.parametrize("mode,owner_is_trusted,expected", [(0o777, True, False), (0o775, True, False), (0o757, True, False), (0o1777, False, False),
                                                            (0o1777, True, True), (0o755, True, True), (0o755, False, False), (0o555, False, False)])
def test_a_directory_is_trusted_only_when_trusted_owned_and_closed_to_group_and_other(tmp_path, monkeypatch, mode, owner_is_trusted, expected):
    """The holder must be owned by the trusted uid UNCONDITIONALLY (an owner-uid 0555 directory is one chmod away from writable); group or other write
    is accepted only for a sticky directory of the trusted uid."""
    base, through = _one_link(tmp_path)
    _trust_own_links(monkeypatch)
    real_stat = os.stat
    held = os.fspath(base)

    def fake_stat(path, *a, **k):
        st = real_stat(path, *a, **k)
        if os.fspath(path) != held:
            return st
        return os.stat_result((stat.S_IFDIR | mode, st.st_ino, st.st_dev, st.st_nlink, os.getuid() if owner_is_trusted else os.getuid() + 1, st.st_gid,
                               st.st_size, int(st.st_atime), int(st.st_mtime), int(st.st_ctime)))
    monkeypatch.setattr(bg.os, "stat", fake_stat)
    assert bg._only_trusted_aliases(through) is expected


def _root_link_in_user_directory(tmp_path, monkeypatch):
    """A link reported as root-owned (seam uid 0) whose real holder is the user's own directory `base`; returns `(base, through)`."""
    base, through = _one_link(tmp_path)
    real_lstat = os.lstat

    def lstat(path, *a, **k):
        st = real_lstat(path, *a, **k)
        if os.fspath(path) != str(base / "alias"):
            return st
        return os.stat_result((st.st_mode, st.st_ino, st.st_dev, st.st_nlink, 0, st.st_gid, st.st_size, int(st.st_atime), int(st.st_mtime), int(st.st_ctime)))
    monkeypatch.setattr(bg.os, "lstat", lstat)
    monkeypatch.setattr(bg, "_TRUSTED_LINK_UID", 0)
    return base, through


@pytest.mark.skipif(os.geteuid() == 0, reason="the holder must be owned by a non-root user")
def test_an_own_uid_owned_read_only_holder_is_refused_for_a_root_owned_link(tmp_path, monkeypatch):
    base, through = _root_link_in_user_directory(tmp_path, monkeypatch)
    real_access = os.access
    monkeypatch.setattr(bg.os, "access", lambda path, mode, *a, **k: False if mode & os.W_OK else real_access(path, mode, *a, **k))  # as if 0555
    assert os.stat(base).st_uid == os.getuid() != 0 and os.stat(base).st_mode & 0o022 == 0
    assert bg._only_trusted_aliases(through) is False  # closed (as 0555) and not writable by the euid, but not root's directory


def test_a_writable_ancestor_of_a_trusted_holder_is_refused(tmp_path, monkeypatch):
    """The holder is trusted-owned and closed; its parent is writable by the euid: the holder can be renamed away and replaced."""
    base, through = _one_link(tmp_path)
    monkeypatch.setattr(bg, "_TRUSTED_LINK_UID", os.getuid())
    real_access = os.access
    held = os.fspath(base)
    monkeypatch.setattr(bg.os, "access", lambda path, mode, *a, **k: False if (mode & os.W_OK and os.fspath(path) == held) else real_access(path, mode, *a, **k))
    assert os.access(base.parent, os.W_OK)
    assert bg._only_trusted_aliases(through) is False
    _trust_own_links(monkeypatch)  # every ancestor closed to the euid as well: accepted
    assert bg._only_trusted_aliases(through) is True


def test_a_group_or_other_writable_ancestor_is_refused_unless_sticky_and_trusted(tmp_path, monkeypatch):
    """A root-owned (uid seam) sticky 1777-like ancestor that the euid CAN write (`os.access` True) is accepted; one owned by another uid is refused."""
    base, through = _one_link(tmp_path)
    _trust_own_links(monkeypatch)
    real_stat = os.stat  # `_trust_own_links`'s: every directory reports the trusted uid
    parent = os.fspath(base.parent)
    modes = {"mode": 0o775, "uid": os.getuid()}

    def fake_stat(path, *a, **k):
        st = real_stat(path, *a, **k)
        if os.fspath(path) != parent:
            return st
        return os.stat_result((stat.S_IFDIR | modes["mode"], st.st_ino, st.st_dev, st.st_nlink, modes["uid"], st.st_gid, st.st_size,
                               int(st.st_atime), int(st.st_mtime), int(st.st_ctime)))
    monkeypatch.setattr(bg.os, "stat", fake_stat)
    closed_access = os.access
    monkeypatch.setattr(bg.os, "access", lambda path, mode, *a, **k: True if (mode & os.W_OK and os.fspath(path) == parent) else closed_access(path, mode, *a, **k))
    assert os.access(parent, os.W_OK)  # the euid can really write the ancestor
    assert bg._only_trusted_aliases(through) is False  # 0775, writable, not sticky
    modes["mode"] = 0o1777
    assert bg._only_trusted_aliases(through) is True   # sticky, owned by the trusted uid, writable by the euid: like /tmp on Linux
    modes["uid"] = os.getuid() + 1
    assert bg._only_trusted_aliases(through) is False  # not owned by the trusted uid (and sticky): refused
    modes["uid"] = os.getuid()
    modes["mode"] = 0o555
    monkeypatch.setattr(bg.os, "access", closed_access)
    assert bg._only_trusted_aliases(through) is True   # closed and trusted-owned
    modes["uid"] = os.getuid() + 1
    assert bg._only_trusted_aliases(through) is False  # closed (0555) but owned by another uid: that owner can chmod it


def test_only_root_changes_sticky_rule_needs_the_trusted_owner(tmp_path, monkeypatch):
    st = os.stat(tmp_path)

    def info(mode, uid):
        return os.stat_result((stat.S_IFDIR | mode, st.st_ino, st.st_dev, st.st_nlink, uid, st.st_gid, st.st_size, 0, 0, 0))
    monkeypatch.setattr(bg, "_TRUSTED_LINK_UID", 0)
    monkeypatch.setattr(bg.os, "access", lambda path, mode, *a, **k: True)  # the euid can write everywhere
    assert bg._only_root_changes("/x", info(0o1777, 0)) is True        # root-owned sticky, like /tmp on Linux
    assert bg._only_root_changes("/x", info(0o1777, os.getuid() or 1)) is False  # sticky, owned by the test user: refused
    assert bg._only_root_changes("/x", info(0o755, 0)) is False        # not sticky and writable by the euid
    monkeypatch.setattr(bg.os, "access", lambda path, mode, *a, **k: False)
    assert bg._only_root_changes("/x", info(0o755, 0)) is True and bg._only_root_changes("/x", info(0o775, 0)) is False


def test_an_own_uid_read_only_ancestor_is_refused(tmp_path, monkeypatch):
    """The reviewer's repro: a 0555 ancestor owned by the user passes `_only_root_changes` but its owner can chmod it."""
    base, through = _one_link(tmp_path)
    _trust_own_links(monkeypatch)
    assert bg._only_trusted_aliases(through) is True
    real_stat = os.stat
    parent = os.fspath(base.parent)

    def other_owner(path, *a, **k):
        st = real_stat(path, *a, **k)
        if os.fspath(path) != parent:
            return st
        return os.stat_result((st.st_mode, st.st_ino, st.st_dev, st.st_nlink, os.getuid() + 1, st.st_gid, st.st_size, 0, 0, 0))
    monkeypatch.setattr(bg.os, "stat", other_owner)
    assert bg._only_trusted_aliases(through) is False


def test_an_unstatable_ancestor_fails_closed(tmp_path, monkeypatch):
    base, through = _one_link(tmp_path)
    _trust_own_links(monkeypatch)
    real_stat = os.stat
    parent = os.fspath(base.parent)

    def fake_stat(path, *a, **k):
        if os.fspath(path) == parent:
            raise PermissionError(13, "denied")
        return real_stat(path, *a, **k)
    monkeypatch.setattr(bg.os, "stat", fake_stat)
    assert bg._only_trusted_aliases(through) is False


def test_the_effective_uid_form_of_access_is_used_where_supported(monkeypatch):
    calls = []
    monkeypatch.setattr(bg.os, "access", lambda path, mode, **k: calls.append(k) or False)
    monkeypatch.setattr(bg.os, "supports_effective_ids", {bg.os.access})
    assert bg._euid_can_write("/x") is False and calls == [{"effective_ids": True}]
    calls.clear()
    monkeypatch.setattr(bg.os, "supports_effective_ids", set())
    assert bg._euid_can_write("/x") is False and calls == [{}]


@pytest.mark.skipif(not os.path.islink("/var") or os.geteuid() == 0, reason="needs the macOS /var -> /private/var chain, not root")
def test_the_real_macos_var_chain_is_still_accepted():
    assert bg._only_trusted_aliases("/var/folders") is True


def test_a_hard_linked_symlink_is_refused(tmp_path, monkeypatch):
    base, through = _one_link(tmp_path)
    _trust_own_links(monkeypatch)
    assert bg._only_trusted_aliases(through) is True
    real_lstat = os.lstat

    def lstat(path, *a, **k):  # a second name for the link (a hard link to a symlink is not possible everywhere, so the count is simulated)
        st = real_lstat(path, *a, **k)
        if os.fspath(path) != str(base / "alias"):
            return st
        return os.stat_result((st.st_mode, st.st_ino, st.st_dev, 2, st.st_uid, st.st_gid, st.st_size, int(st.st_atime), int(st.st_mtime), int(st.st_ctime)))
    monkeypatch.setattr(bg.os, "lstat", lstat)
    assert bg._only_trusted_aliases(through) is False


@pytest.mark.parametrize("lib", ["lib", "lib64"])
def test_a_lib_that_is_a_file_is_not_isolated_not_unreadable(world, lib):
    (world[0] / "lib64").write_text("x") if lib == "lib64" else None
    if lib == "lib":
        import shutil
        shutil.rmtree(world[0] / "lib")
        (world[0] / "lib").write_text("x")
    with pytest.raises(Err) as info:
        snapshot(world)
    assert info.value.code == "VENV_NOT_ISOLATED"
