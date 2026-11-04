"""Tests for the C4c-2c pieces of `benchmark_gate.py`: `snapshot_venv`, `check_venv` and the `snapshot-venv` CLI.

Fake venvs only (a directory with `pyvenv.cfg`, `bin/` and `lib/python3.12/site-packages`), as the design asks: no real venvs in unit tests.
The `.pth` lines are the ones the real editable backends write (setuptools finder, hatchling/pdm path lines, flit/poetry path lines,
pytest-cov's `a1_coverage.pth`). Design: docs/superpowers/specs/2026-10-02-c4-performance-review-executor-handoff-design.md.
"""

from __future__ import annotations

import importlib.util
import json
import os
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


def check(w, **kwargs):
    bg.check_venv(str(w[1]), str(w[4]), str(w[3]), **kwargs)


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
    ("usercustomize.abi3.so", False), ("sitecustomize.pyd", False), ("sitecustomize", True), ("usercustomize", True),
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


@pytest.mark.parametrize("bad", [None, 3, "", "relative-name-not-bin", "x\0/bin", b"/tmp/bin"])
def test_a_bad_bin_argument_is_refused(world, bad):
    with pytest.raises(Err) as info:
        bg.snapshot_venv(bad, str(world[4]))
    assert info.value.code in ("VENV_NOT_ISOLATED", "TREE_UNREADABLE")


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
    with pytest.raises(Err) as info:
        bg.snapshot_venv(str(inner / "bin"), str(world[4]))
        bg.check_venv(str(inner / "bin"), str(world[4]), str(world[3]))
    assert info.value.code == "VENV_NOT_ISOLATED"


def test_an_export_inside_the_venv_is_not_isolated(world):
    export = world[0] / "export"
    export.mkdir()
    snapshot(world)
    with pytest.raises(Err) as info:
        bg.check_venv(str(world[1]), str(world[4]), str(export))
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
        bg.check_venv(str(world[1]), str(world[4]), str(world[3] / "nope"))
    assert info.value.code == "VENV_NOT_ISOLATED"


# --- CLI ------------------------------------------------------------------------------------------------------------------------

def test_cli_snapshot_venv_writes_the_file(world, capsys):
    assert bg.main(["snapshot-venv", "--bin", str(world[1]), "--out", str(world[4])]) == 0
    assert json.loads(world[4].read_text())["kind"] == bg._VENV_SNAPSHOT_KIND


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
