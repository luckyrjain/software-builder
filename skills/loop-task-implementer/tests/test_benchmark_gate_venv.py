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


@pytest.mark.parametrize("export, others", [(None, ()), (b"/x", ()), ("OK", (None,)), ("OK", (3,))])
def test_bad_root_arguments_are_caller_errors(world, export, others):
    snapshot(world)
    export = str(world[3]) if export == "OK" else export
    with pytest.raises(Err) as info:
        bg.check_venv(str(world[1]), str(world[4]), export, others)
    assert info.value.code == "DEST_REJECTED"
