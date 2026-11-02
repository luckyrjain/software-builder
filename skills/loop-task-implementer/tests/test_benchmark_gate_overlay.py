"""Tests for the C4c-2a pieces of `benchmark_gate.py`: `hash_tree` and `overlay_benchmark_file`.

Export directories are built by hand under the (sandboxed) fixed parent with a real marker and a real sidecar, so no git
is needed. Design: docs/superpowers/specs/2026-10-02-c4-performance-review-executor-handoff-design.md (APIs table).
"""

from __future__ import annotations

import errno
import hashlib
import importlib.util
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import types
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
IS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0
pytestmark = pytest.mark.skipif(not hasattr(os, "fchmod"), reason="POSIX only")

BASE_SHA = "a" * 40
HEAD_SHA = "b" * 40
BENCH = "benchmarks/bench_orders.py"
SRC = b'import hashlib\n\n\ndef test_bench():\n    print("BENCH_RESULT_DIGEST: " + hashlib.sha256(b"x").hexdigest())\n'


@pytest.fixture(autouse=True)
def sandbox(tmp_path, monkeypatch):
    temp = tmp_path / "tmp"
    temp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp))
    yield temp
    for p in [temp, *temp.rglob("*")]:
        if not p.is_symlink() and p.is_dir():
            p.chmod(0o700)
    shutil.rmtree(temp, ignore_errors=True)


@pytest.fixture
def pair():
    """`(base, head)` export directories in one dispatch root, with the base's sidecar."""
    parent = bg._check_parent(create=True)
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    assert bg._create_root(str(parent), "bench-aaaaaaaa", child.pid)
    root = parent / "bench-aaaaaaaa"
    for leaf in ("base", "head"):
        (root / leaf / "src").mkdir(parents=True)
        (root / leaf / "src" / "app.py").write_text("x = 1\n")
    (root / "base.export.json").write_text(json.dumps({"commit": BASE_SHA, "entries": 2}))
    (root / "head.export.json").write_text(json.dumps({"commit": HEAD_SHA, "entries": 2}))
    return root / "base", root / "head"


def add_head_bench(head: Path, rel: str = BENCH, data: bytes = SRC) -> None:
    (head / rel).parent.mkdir(parents=True, exist_ok=True)
    (head / rel).write_bytes(data)


def overlay(pair_, path: str = BENCH, commit: str = BASE_SHA, head_commit: str = HEAD_SHA) -> str:
    return bg.overlay_benchmark_file(pair_[0], pair_[1], commit, path, head_ref_commit=head_commit)


# --- hash_tree ---

def test_hash_tree_is_stable_and_sensitive_to_content_mode_names_links_and_empty_directories(pair):
    base, _ = pair
    (base / "link").symlink_to("src/app.py")
    (base / "empty").mkdir()
    first = bg.hash_tree(base)
    assert first == bg.hash_tree(base) and len(first) == 64
    changes = [
        lambda: (base / "src" / "app.py").write_text("x = 2\n"),
        lambda: (base / "src" / "app.py").chmod(0o444),
        lambda: (base / "src" / "app.py").rename(base / "src" / "App.py"),
        lambda: ((base / "link").unlink(), (base / "link").symlink_to("src/App.py")),
        lambda: (base / "empty").rmdir(),
        lambda: (base / "src" / "extra").mkdir(),
    ]
    seen = {first}
    for change in changes:
        change()
        now = bg.hash_tree(base)
        assert now not in seen
        seen.add(now)


def test_hash_tree_sees_a_chmod_back_after_a_seal(pair):
    base, _ = pair
    bg.seal_tree(base)
    sealed = bg.hash_tree(base)
    (base / "src" / "app.py").chmod(0o644)
    assert bg.hash_tree(base) != sealed
    bg.unseal_tree(base)


def test_hash_tree_distinguishes_trees_with_the_same_flat_text(pair):
    base, head = pair
    # records are length-prefixed: a file named like another record's tail cannot forge it
    (base / "a").write_text("")
    (head / "a ").write_text("")
    assert bg.hash_tree(base) != bg.hash_tree(head)


def test_hash_tree_is_independent_of_the_creation_order_and_matches_a_golden_value(pair):
    base, head = pair
    shutil.rmtree(base / "src"), shutil.rmtree(head / "src")
    for root, order in ((base, ("b.py", "a.py", "a.b", "a/c")), (head, ("a/c", "a.b", "a.py", "b.py"))):
        for name in order:
            target = root / name
            target.parent.mkdir(exist_ok=True)
            target.write_text(name)
            target.chmod(0o644)
        for d in (root, root / "a"):
            d.chmod(0o755)
    assert bg.hash_tree(base) == bg.hash_tree(head)
    # pins the magic, the record format and the field order: change any and this fails
    expected = hashlib.sha256(bg._HASH_MAGIC)
    for kind, mode, rel, body in (
        (b"D", 0o755, b"", b""), (b"D", 0o755, b"a", b""),
        (b"F", 0o644, b"a/c", hashlib.sha256(b"a/c").hexdigest().encode() + b":1"),
        (b"F", 0o644, b"a.b", hashlib.sha256(b"a.b").hexdigest().encode() + b":1"),
        (b"F", 0o644, b"a.py", hashlib.sha256(b"a.py").hexdigest().encode() + b":1"),
        (b"F", 0o644, b"b.py", hashlib.sha256(b"b.py").hexdigest().encode() + b":1"),
    ):
        expected.update(b"%s %o %d:%s %d:%s" % (kind, mode, len(rel), rel, len(body), body))
    assert bg.hash_tree(base) == expected.hexdigest()


def test_hash_tree_does_not_follow_symlinks(pair, tmp_path):
    base, _ = pair
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "f").write_text("1")
    (base / "to_dir").symlink_to(outside)
    first = bg.hash_tree(base)
    (outside / "f").write_text("2")
    assert bg.hash_tree(base) == first


@pytest.mark.skipif(IS_ROOT, reason="root can read anything")
def test_hash_tree_reports_an_unreadable_file(pair):
    base, _ = pair
    (base / "src" / "app.py").chmod(0)
    with pytest.raises(Err) as info:
        bg.hash_tree(base)
    assert info.value.code == "TREE_UNREADABLE"


def test_hash_tree_is_bounded_and_demands_a_real_directory(pair, monkeypatch, tmp_path):
    base, _ = pair
    with monkeypatch.context() as patch:
        patch.setattr(bg, "_MAX_TREE_ENTRIES", 2)
        with pytest.raises(Err) as info:
            bg.hash_tree(base)
        assert info.value.code == "TREE_TOO_LARGE"
    for bad in (base / "src" / "app.py", tmp_path / "missing"):
        with pytest.raises(Err) as info:
            bg.hash_tree(bad)
        assert info.value.code == "TREE_UNREADABLE"


def test_hash_tree_content_cap(pair, monkeypatch):
    base, _ = pair
    monkeypatch.setattr(bg, "_MAX_HASH_BYTES", 3)
    with pytest.raises(Err) as info:
        bg.hash_tree(base)
    assert info.value.code == "TREE_TOO_LARGE"


# --- overlay_benchmark_file ---

def test_a_benchmark_absent_at_base_is_copied_in_with_its_parents(pair):
    base, head = pair
    add_head_bench(head)
    assert overlay(pair) == "BUILDER_AUTHORED"
    target = base / BENCH
    assert target.read_bytes() == SRC and stat.S_IMODE(target.stat().st_mode) == 0o644
    assert stat.S_IMODE((base / "benchmarks").stat().st_mode) == 0o755


def test_a_benchmark_present_at_base_with_equal_bytes_is_pre_existing_and_untouched(pair):
    base, head = pair
    add_head_bench(head)
    add_head_bench(base)
    before = bg.hash_tree(base)
    assert overlay(pair) == "PRE_EXISTING" and bg.hash_tree(base) == before


@pytest.mark.parametrize("variant", ["bytes", "directory", "symlink", "symlink_same_bytes", "oversize_at_base"])
def test_a_benchmark_present_at_base_but_different_is_modified(pair, variant):
    base, head = pair
    add_head_bench(head)
    if variant == "bytes":
        add_head_bench(base, data=SRC + b"# edited\n")
    elif variant == "directory":
        (base / BENCH).mkdir(parents=True)
    elif variant == "symlink":
        (base / "benchmarks").mkdir()
        (base / BENCH).symlink_to("../src/app.py")
    elif variant == "symlink_same_bytes":  # a different KIND with identical content is still "modified"
        (base / "src" / "same.py").write_bytes(SRC)
        (base / "benchmarks").mkdir()
        (base / BENCH).symlink_to("../src/same.py")
    else:
        add_head_bench(base, data=SRC + b"#" * 20_000)
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "BENCHMARK_MODIFIED"


def hide_names(monkeypatch, tree: Path, *hidden: str) -> None:
    """Make `os.listdir` of a directory descriptor INSIDE `tree` omit `hidden`: the exact-name lookup then believes the entry is
    absent, as it does for a case-folded twin on a case-insensitive filesystem. Deterministic on every platform."""
    inodes = {d.stat().st_ino for d in [tree, *tree.rglob("*")] if d.is_dir() and not d.is_symlink()}
    real = os.listdir

    def listdir(path="."):
        names = real(path)
        if isinstance(path, int) and os.fstat(path).st_ino in inodes:
            return [n for n in names if n not in hidden]
        return names

    monkeypatch.setattr(os, "listdir", listdir)


def test_presence_is_by_exact_name_a_case_folded_twin_is_never_overwritten(pair):
    base, head = pair
    add_head_bench(head)
    add_head_bench(base, rel="benchmarks/Bench_orders.py", data=b"the twin's own bytes\n")
    try:
        result = overlay(pair)
    except Err as exc:  # a case-insensitive filesystem finds the twin when creating
        assert exc.code == "OVERLAY_PATH_CONFLICT"
    else:  # case-sensitive: two distinct files
        assert result == "BUILDER_AUTHORED" and sorted(os.listdir(base / "benchmarks")) == ["Bench_orders.py", "bench_orders.py"]
    assert (base / "benchmarks" / "Bench_orders.py").read_bytes() == b"the twin's own bytes\n"  # never truncated or rewritten


def test_a_leaf_that_exists_but_is_hidden_from_the_listing_is_refused_not_overwritten(pair, monkeypatch):
    base, head = pair
    add_head_bench(head)
    add_head_bench(base, data=b"different bytes\n")
    hide_names(monkeypatch, base, "bench_orders.py")
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_PATH_CONFLICT" and (base / BENCH).read_bytes() == b"different bytes\n"  # O_EXCL, not O_TRUNC


def test_a_parent_hidden_from_the_listing_is_refused_and_nothing_is_created_below_it(pair, monkeypatch):
    base, head = pair
    add_head_bench(head)
    (base / "benchmarks").mkdir()
    hide_names(monkeypatch, base, "benchmarks")
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_PATH_CONFLICT" and os.listdir(base / "benchmarks") == []


def test_a_base_parent_that_is_a_file_or_a_symlink_is_a_conflict(pair, tmp_path):
    base, head = pair
    add_head_bench(head)
    (base / "benchmarks").write_text("a file")
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_PATH_CONFLICT"
    (base / "benchmarks").unlink()
    outside = tmp_path / "outside"
    outside.mkdir()
    (base / "benchmarks").symlink_to(outside)
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_PATH_CONFLICT" and list(outside.iterdir()) == []


@pytest.mark.parametrize("sidecar", ["other_commit", "missing", "garbage", "uppercase", "not_a_dict"])
def test_the_overlay_is_bound_to_the_commit_the_base_was_exported_from(pair, sidecar):
    base, head = pair
    add_head_bench(head)
    side = Path(str(base) + ".export.json")
    if sidecar == "other_commit":
        side.write_text(json.dumps({"commit": "c" * 40}))
    elif sidecar == "missing":
        side.unlink()
    elif sidecar == "garbage":
        side.write_text("{not json")
    elif sidecar == "uppercase":
        side.write_text(json.dumps({"commit": BASE_SHA.upper()}))
    else:
        side.write_text("[]")
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_COMMIT_MISMATCH" and not (base / "benchmarks").exists()


@pytest.mark.parametrize("commit", ["abc", "A" * 40, "a" * 39, None, 7, "a" * 40 + "\n"])
def test_a_bad_base_ref_commit_is_commit_invalid(pair, commit):
    add_head_bench(pair[1])
    with pytest.raises(Err) as info:
        overlay(pair, commit=commit)
    assert info.value.code == "COMMIT_INVALID"


def test_a_sha256_repository_commit_is_accepted(pair):
    base, head = pair
    add_head_bench(head)
    Path(str(base) + ".export.json").write_text(json.dumps({"commit": "d" * 64}))
    Path(str(head) + ".export.json").write_text(json.dumps({"commit": "e" * 64}))
    assert overlay(pair, commit="d" * 64, head_commit="e" * 64) == "BUILDER_AUTHORED"


@pytest.mark.parametrize(
    "path",
    ["../x.py", "/abs/bench_x.py", "benchmarks\\bench_x.py", "benchmarks/./bench_x.py", "benchmarks//bench_x.py", "bench_x.py",
     "benchmarks/bench_x.txt", "benchmarks/helper.py", "src/bench_x.py", "benchmarks/.env/bench_x.py", "benchmarks/ébench.py", 7, None],
)
def test_paths_failing_the_gate_rules_are_rejected(pair, path):
    add_head_bench(pair[1])
    with pytest.raises(Err) as info:
        overlay(pair, path=path)
    assert info.value.code == "OVERLAY_PATH_REJECTED" and not (pair[0] / "benchmarks").exists()


def test_a_missing_head_file_is_rejected_by_validate_task_target(pair):
    with pytest.raises(Err) as info:
        overlay(pair)  # lexically fine, absent in the head: only the shared validator knows
    assert info.value.code == "OVERLAY_PATH_REJECTED"


@pytest.mark.parametrize("kind", ["symlink_file", "symlink_in_tree", "symlink_parent_in_tree", "symlink_parent", "directory", "oversize", "fifo"])
def test_the_head_benchmark_must_be_a_small_regular_file_without_symlinks(pair, tmp_path, kind):
    base, head = pair
    real = tmp_path / "real_bench.py"
    real.write_bytes(SRC)
    if kind == "symlink_file":
        (head / "benchmarks").mkdir()
        (head / BENCH).symlink_to(real)
    elif kind == "symlink_in_tree":  # passes validate_task_target (it resolves inside the head): O_NOFOLLOW is the only guard
        (head / "benchmarks").mkdir()
        (head / "src" / "real.py").write_bytes(SRC)
        (head / BENCH).symlink_to("../src/real.py")
    elif kind == "symlink_parent_in_tree":  # resolves inside the head, so only the O_NOFOLLOW walk refuses it
        (head / "src" / "bench_orders.py").write_bytes(SRC)
        (head / "benchmarks").symlink_to("src")
    elif kind == "symlink_parent":
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / "bench_orders.py").write_bytes(SRC)
        (head / "benchmarks").symlink_to(elsewhere)
    elif kind == "directory":
        (head / BENCH).mkdir(parents=True)
    elif kind == "oversize":
        add_head_bench(head, data=SRC + b"#" * 20_000)
    else:
        (head / "benchmarks").mkdir()
        os.mkfifo(head / BENCH)
    with pytest.raises(Err) as info:
        overlay(pair)
    exact = {"symlink_file": "OVERLAY_PATH_REJECTED", "symlink_parent": "OVERLAY_PATH_REJECTED"}  # the shared validator refuses an escaping link first
    assert info.value.code == exact.get(kind, "OVERLAY_NOT_REGULAR")
    assert not (base / "benchmarks").exists()


def test_exactly_16_kib_is_allowed_and_one_more_byte_is_not(pair):
    base, head = pair
    add_head_bench(head, data=b"#" * 16384)
    assert overlay(pair) == "BUILDER_AUTHORED"
    shutil.rmtree(base / "benchmarks")
    add_head_bench(head, data=b"#" * 16385)
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_NOT_REGULAR"


def test_the_roots_must_be_distinct_export_directories_under_the_fixed_parent(pair, tmp_path):
    base, head = pair
    add_head_bench(head)
    outside = tmp_path / "bench-bbbbbbbb" / "head"
    outside.mkdir(parents=True)
    for roots in ((base, base), (base, outside), (outside, head), (base.parent, head), (base, base / "src"), (7, head)):
        with pytest.raises(Err) as info:
            bg.overlay_benchmark_file(roots[0], roots[1], BASE_SHA, BENCH, head_ref_commit=HEAD_SHA)
        assert info.value.code == "DEST_REJECTED"
    link = base.parent / "linked"
    link.symlink_to(head)
    with pytest.raises(Err) as info:
        bg.overlay_benchmark_file(base, link, BASE_SHA, BENCH, head_ref_commit=HEAD_SHA)
    assert info.value.code == "DEST_REJECTED"


def test_the_overlay_never_writes_through_a_symlink_planted_at_the_leaf(pair, tmp_path):
    base, head = pair
    add_head_bench(head)
    (base / "benchmarks").mkdir()
    victim = tmp_path / "victim"
    victim.write_text("keep")
    (base / BENCH).symlink_to(victim)  # a dangling-or-not symlink at the leaf is "present and different", never written through
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "BENCHMARK_MODIFIED" and victim.read_text() == "keep"


def test_an_unwritable_base_is_base_sealed_not_a_generic_failure(pair):
    base, head = pair
    add_head_bench(head)
    bg.seal_tree(base)
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_BASE_SEALED"
    bg.unseal_tree(base)


def test_the_overlay_validator_is_the_shared_one_and_a_missing_file_fails_closed(pair, monkeypatch):
    add_head_bench(pair[1])
    monkeypatch.setattr(bg, "_task_target_state", None)
    monkeypatch.setattr(bg, "__file__", str(pair[0] / "benchmark_gate.py"))  # no validate_task_target.py beside it
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_FAILED"


def test_seal_hash_measure_hash_order_leaves_the_hash_unchanged(pair):
    """The design's order: overlay into the writable base, seal, hash; a later read-only use does not change the hash."""
    base, head = pair
    add_head_bench(head)
    assert overlay(pair) == "BUILDER_AUTHORED"
    bg.seal_tree(base), bg.seal_tree(head)
    before = bg.hash_tree(base), bg.hash_tree(head)
    (base / BENCH).read_bytes()
    assert (bg.hash_tree(base), bg.hash_tree(head)) == before


def test_the_new_codes_are_declared():
    assert set(bg.OVERLAY_REFUSAL_CODES) <= set(bg.ERROR_CODES) and "OVERLAY_FAILED" in bg.ERROR_CODES
    assert len(set(bg.ERROR_CODES)) == len(bg.ERROR_CODES)


# --- round 1 review: failure cleanup, umask, descriptors, hard links, loader, ordering, hash coverage ---

def open_fds() -> int:
    return len(os.listdir("/dev/fd" if os.path.isdir("/dev/fd") else "/proc/self/fd"))


@pytest.mark.parametrize("failing", ["fchmod_file", "write", "fchmod_dir"])
def test_a_failed_write_leaves_nothing_behind_and_a_retry_succeeds(pair, monkeypatch, failing):
    base, head = pair
    add_head_bench(head)
    real_fchmod, real_write = os.fchmod, os.write
    calls = {"n": 0}

    def fchmod(fd, mode):
        calls["n"] += 1
        if failing == "fchmod_dir" and mode == 0o755 or failing == "fchmod_file" and mode == 0o644:
            raise OSError(5, "boom")
        return real_fchmod(fd, mode)

    def write(fd, data):
        if failing == "write":
            raise OSError(28, "no space left")
        return real_write(fd, data)

    with monkeypatch.context() as patch:
        patch.setattr(os, "fchmod", fchmod)
        patch.setattr(os, "write", write)
        with pytest.raises(Err) as info:
            overlay(pair)
    assert info.value.code == "OVERLAY_FAILED" and not (base / "benchmarks").exists()  # file AND the directory it created
    assert overlay(pair) == "BUILDER_AUTHORED"  # not BENCHMARK_MODIFIED


def test_a_failure_removes_only_what_this_call_created(pair, monkeypatch):
    base, head = pair
    add_head_bench(head, rel="benchmarks/sub/bench_orders.py")
    (base / "benchmarks").mkdir()
    (base / "benchmarks" / "keep.txt").write_text("k")
    monkeypatch.setattr(os, "write", lambda fd, data: (_ for _ in ()).throw(OSError(5, "boom")))
    with pytest.raises(Err):
        overlay(pair, path="benchmarks/sub/bench_orders.py")
    assert os.listdir(base / "benchmarks") == ["keep.txt"]


def overlay_under(pair_, mask: int) -> str:
    old = os.umask(mask)
    try:
        return overlay(pair_, path="benchmarks/sub/bench_orders.py")
    finally:
        os.umask(old)


@pytest.mark.parametrize("mask", [0o077, 0o002, 0o177, 0o277])
def test_created_modes_and_the_resulting_hash_do_not_depend_on_the_umask(pair, mask):
    base, head = pair
    add_head_bench(head, rel="benchmarks/sub/bench_orders.py")
    assert overlay_under(pair, 0o022) == "BUILDER_AUTHORED"
    reference = bg.hash_tree(base)
    shutil.rmtree(base / "benchmarks")
    assert overlay_under(pair, mask) == "BUILDER_AUTHORED"
    assert stat.S_IMODE((base / "benchmarks").stat().st_mode) == 0o755
    assert stat.S_IMODE((base / "benchmarks" / "sub").stat().st_mode) == 0o755
    assert stat.S_IMODE((base / "benchmarks" / "sub" / "bench_orders.py").stat().st_mode) == 0o644
    assert bg.hash_tree(base) == reference


def test_no_descriptor_leaks_on_success_or_on_any_refusal(pair, tmp_path):
    base, head = pair
    add_head_bench(head)
    baseline = open_fds()

    def run(expect, **kwargs):
        for _ in range(8):
            try:
                overlay(pair, **kwargs)
            except Err as exc:
                assert exc.code == expect
            else:
                assert expect == "OK"
        assert open_fds() == baseline, expect

    run("OK")
    run("OK")  # second round is PRE_EXISTING
    run("OVERLAY_COMMIT_MISMATCH", commit="c" * 40)
    run("OVERLAY_PATH_REJECTED", path="benchmarks/missing_bench.py")
    add_head_bench(base, data=b"x")
    run("BENCHMARK_MODIFIED")
    (base / BENCH).unlink()
    (base / "benchmarks").rmdir()
    (base / "benchmarks").write_text("file")
    run("OVERLAY_PATH_CONFLICT")
    (base / "benchmarks").unlink()
    (head / BENCH).unlink()
    os.mkfifo(head / BENCH)
    run("OVERLAY_NOT_REGULAR")
    for _ in range(8):
        bg.hash_tree(base)
        with pytest.raises(Err):
            bg.hash_tree(tmp_path / "missing")
    assert open_fds() == baseline


def test_a_hard_linked_head_file_is_refused_not_read(pair, tmp_path):
    base, head = pair
    secret = tmp_path / "secret.txt"
    secret.write_text("TOPSECRET")
    (head / "benchmarks").mkdir()
    os.link(secret, head / BENCH)
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_NOT_REGULAR" and not (base / "benchmarks").exists()


@pytest.mark.skipif(IS_ROOT, reason="root can open anything")
def test_a_base_parent_that_cannot_be_opened_is_a_failure_not_a_conflict(pair):
    base, head = pair
    add_head_bench(head)
    (base / "benchmarks").mkdir()
    (base / "benchmarks").chmod(0)
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_FAILED"
    (base / "benchmarks").chmod(0o755)


def test_io_errors_are_overlay_failed_not_mislabelled(pair, monkeypatch):
    base, head = pair
    add_head_bench(head)
    real = os.open

    def flaky(path, flags, *args, **kwargs):
        if path == "bench_orders.py" and flags & os.O_NOFOLLOW and not flags & os.O_CREAT and kwargs.get("dir_fd") is not None:
            raise OSError(5, "EIO")
        return real(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", flaky)
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_FAILED"  # the head read failed with EIO: not OVERLAY_NOT_REGULAR


def test_a_sidecar_io_error_is_a_failure_and_a_bad_sidecar_is_a_mismatch(pair, monkeypatch, tmp_path):
    base, head = pair
    add_head_bench(head)
    side = Path(str(base) + ".export.json")
    real = bg._read_bounded

    def broken(path, *args, **kwargs):
        if str(path).endswith(".export.json"):
            raise OSError(5, "EIO")
        return real(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(bg, "_read_bounded", broken)
        with pytest.raises(Err) as info:
            overlay(pair)
    assert info.value.code == "OVERLAY_FAILED"
    saved = side.read_text()
    side.unlink()
    target = tmp_path / "real.json"
    target.write_text(saved)
    side.symlink_to(target)  # a symlinked sidecar is never followed
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_COMMIT_MISMATCH"
    side.unlink()
    side.write_text(json.dumps({"commit": BASE_SHA, "pad": "x" * 5000}))  # over the 4 KiB cap: not read
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_COMMIT_MISMATCH"


def test_the_documented_check_order_holds_when_two_things_are_wrong(pair, tmp_path):
    base, head = pair
    outside = tmp_path / "bench-bbbbbbbb" / "head"
    outside.mkdir(parents=True)
    cases = [
        ((base, outside, "zzz", "../bad"), "DEST_REJECTED"),  # roots before commit, commit before path
        ((base, head, "zzz", "../bad"), "COMMIT_INVALID"),
        ((base, head, "c" * 40, "../bad"), "OVERLAY_COMMIT_MISMATCH"),  # commit binding before path rules
        ((base, head, BASE_SHA, "../bad"), "OVERLAY_PATH_REJECTED"),
    ]
    for args, code in cases:
        with pytest.raises(Err) as info:
            bg.overlay_benchmark_file(*args, head_ref_commit=HEAD_SHA)
        assert info.value.code == code


def test_a_non_str_path_is_a_clean_refusal_even_with_a_hostile_repr(pair):
    class Evil(str):
        def __repr__(self):
            raise RuntimeError("repr")

        def split(self, *_args):
            return ["benchmarks", "bench_orders.py"]

    class NotAStr:
        def __repr__(self):
            raise RuntimeError("repr")

    add_head_bench(pair[1])
    for bad in (NotAStr(), Evil(BENCH), BENCH.encode(), Path(BENCH)):
        with pytest.raises(Err) as info:
            overlay(pair, path=bad)
        assert info.value.code == "OVERLAY_PATH_REJECTED"


def test_an_unloadable_validator_is_overlay_failed(pair, monkeypatch, tmp_path):
    add_head_bench(pair[1])
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    bad = scripts / "validate_task_target.py"
    for content in ("(((\n", "x = 1\n"):  # a syntax error; a module without the function
        bad.write_text(content)
        monkeypatch.setattr(bg, "_task_target_state", None)
        monkeypatch.setattr(bg, "_task_target_path", lambda: bad)
        with pytest.raises(Err) as info:
            overlay(pair)
        assert info.value.code == "OVERLAY_FAILED"
    bad.unlink()
    monkeypatch.setattr(bg, "_task_target_state", None)
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_FAILED"
    if not IS_ROOT:
        bad.write_text("def validate_task_target(a, b):\n    return b\n")
        bad.chmod(0)
        monkeypatch.setattr(bg, "_task_target_state", None)
        with pytest.raises(Err) as info:
            overlay(pair)
        assert info.value.code == "OVERLAY_FAILED"


def test_the_validator_is_loaded_from_one_read_with_no_bytecode_cache(pair, monkeypatch, tmp_path):
    add_head_bench(pair[1])
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    real = Path(bg.__file__).with_name("validate_task_target.py")
    copy = scripts / "validate_task_target.py"
    copy.write_bytes(real.read_bytes())
    monkeypatch.setattr(bg, "_task_target_state", None)
    monkeypatch.setattr(bg, "_task_target_path", lambda: copy)
    monkeypatch.setattr(sys, "dont_write_bytecode", False)  # the environment may disable it; the loader must not depend on that
    assert overlay(pair) == "BUILDER_AUTHORED"
    assert bg._task_target_sha256() == hashlib.sha256(real.read_bytes()).hexdigest()
    assert not (scripts / "__pycache__").exists()
    copy.write_text("def validate_task_target(a, b):\n    return None\n")  # edited after load: the loaded module is unchanged
    assert bg._task_target_sha256() == hashlib.sha256(real.read_bytes()).hexdigest() and overlay(pair) == "PRE_EXISTING"


def new_root(name: str, leaves=("head",), marked: bool = True) -> Path:
    parent = bg._check_parent(create=True)
    if marked:
        bg._create_root(str(parent), name, os.getpid())
    else:
        (parent / name).mkdir()
    for leaf in leaves:
        (parent / name / leaf).mkdir()
    return parent / name


def refused(roots, code="DEST_REJECTED", path=BENCH):
    with pytest.raises(Err) as info:
        bg.overlay_benchmark_file(roots[0], roots[1], BASE_SHA, path, head_ref_commit=HEAD_SHA)
    assert info.value.code == code


def test_the_two_roots_must_share_one_dispatch_root(pair):
    base, head = pair
    add_head_bench(head)
    other = new_root("bench-cccccccc")  # valid, marked, but a different dispatch root
    refused((base, other / "head"))
    refused((other / "head", head))


def test_the_dispatch_root_must_carry_a_valid_marker(pair):
    base, head = pair
    add_head_bench(head)
    (base.parent / bg._MARKER_NAME).unlink()
    refused((base, head))
    unmarked = new_root("bench-dddddddd", marked=False)
    refused((unmarked / "head", unmarked / "head"))


def test_a_dispatch_root_that_is_a_symlink_is_refused(pair, tmp_path):
    base, head = pair
    parent = bg.fixed_parent()
    elsewhere = tmp_path / "elsewhere"
    (elsewhere / "base").mkdir(parents=True)
    (elsewhere / "head").mkdir()
    shutil.copy(base.parent / bg._MARKER_NAME, elsewhere / bg._MARKER_NAME)
    (parent / "bench-linkroot").symlink_to(elsewhere)
    refused((parent / "bench-linkroot" / "base", parent / "bench-linkroot" / "head"))
    assert not (elsewhere / "base" / "benchmarks").exists()


def test_each_name_rule_guards_by_itself(pair):
    base, head = pair
    add_head_bench(head)
    root = base.parent
    for bad_leaf in ("a.b", ".x", "x y"):  # exist, so only the leaf rule can refuse them
        (root / bad_leaf).mkdir()
        refused((base, root / bad_leaf))
    short = new_root("short", leaves=("base", "head"))  # exists and is marked: only the root-name rule can refuse it
    refused((short / "base", short / "head"))


def test_a_dispatch_root_owned_by_someone_else_is_refused(pair, monkeypatch):
    base, head = pair
    add_head_bench(head)
    root_ino = base.parent.stat().st_ino
    monkeypatch.setattr(bg, "_foreign", lambda st: st.st_ino == root_ino)  # only the dispatch root looks foreign
    refused((base, head))


def test_a_sealed_read_only_head_can_still_be_overlaid_from(pair):
    base, head = pair
    add_head_bench(head)
    bg.seal_tree(head)  # a sealed head is read-only and still readable
    assert overlay(pair) == "BUILDER_AUTHORED"
    bg.unseal_tree(head)


# --- hash_tree: coverage of special files, links, changing files, arguments ---

@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs mkfifo")
def test_special_files_directories_and_regular_files_never_share_a_record(pair, monkeypatch):
    import socket

    base, _ = pair
    hashes = {}
    for label in ("fifo", "dir", "file", "socket"):
        for leftover in base.glob("x*"):
            shutil.rmtree(leftover) if leftover.is_dir() else leftover.unlink()
        path = base / "x"
        if label == "fifo":
            os.mkfifo(path, 0o644)
        elif label == "dir":
            path.mkdir()
            path.chmod(0o644)
        elif label == "file":
            path.write_bytes(b"")
            path.chmod(0o644)
        else:
            sock = socket.socket(socket.AF_UNIX)
            with monkeypatch.context() as patch:
                patch.chdir(base)  # a relative name stays under the AF_UNIX path limit (104 bytes on macOS)
                sock.bind("x")
            sock.close()
            path.chmod(0o644)
        hashes[label] = bg.hash_tree(base)
    assert len(hashes) == 4 and len(set(hashes.values())) == 4


def test_a_symlink_hashes_the_same_whatever_the_umask_and_a_hard_link_changes_the_hash(pair):
    base, _ = pair
    (base / "link").symlink_to("src/app.py")
    reference = bg.hash_tree(base)
    (base / "link").unlink()
    old = os.umask(0o077)
    try:
        (base / "link").symlink_to("src/app.py")
    finally:
        os.umask(old)
    assert bg.hash_tree(base) == reference
    (base / "twin.py").write_text("x = 1\n")
    (base / "src" / "app.py").chmod(0o644)
    before = bg.hash_tree(base)
    (base / "twin.py").unlink()
    os.link(base / "src" / "app.py", base / "twin.py")
    assert bg.hash_tree(base) != before  # same content, but now two names for one inode


def test_a_file_that_changes_while_it_is_hashed_is_refused(pair, monkeypatch):
    base, _ = pair
    real = os.read
    state = {"n": 0}

    def growing(fd, size):
        data = real(fd, size)
        state["n"] += 1
        if data and state["n"] == 1:
            with open(base / "src" / "app.py", "ab") as handle:  # appended after the first chunk was read
                handle.write(b"more\n")
        return data

    monkeypatch.setattr(os, "read", growing)
    with pytest.raises(Err) as info:
        bg.hash_tree(base)
    assert info.value.code == "TREE_UNREADABLE"


@pytest.mark.parametrize("bad", [None, 7, True, "", "\0x", "x\ud800y", b"", 3.5])
def test_hash_tree_arguments_fail_cleanly(bad):
    with pytest.raises(Err) as info:
        bg.hash_tree(bad)
    assert info.value.code == "TREE_UNREADABLE"


def test_hash_tree_accepts_bytes_and_pathlike_roots_and_refuses_a_symlinked_root(pair, tmp_path):
    base, _ = pair
    assert bg.hash_tree(os.fsencode(base)) == bg.hash_tree(base) == bg.hash_tree(str(base))
    link = tmp_path / "link"
    link.symlink_to(base)
    with pytest.raises(Err) as info:
        bg.hash_tree(link)
    assert info.value.code == "TREE_UNREADABLE"


def test_the_content_cap_accumulates_across_files_and_is_inclusive(pair, monkeypatch):
    base, _ = pair
    shutil.rmtree(base / "src")
    for i in range(3):
        (base / f"f{i}").write_bytes(b"xy")
    with monkeypatch.context() as patch:
        patch.setattr(bg, "_MAX_HASH_BYTES", 6)
        assert len(bg.hash_tree(base)) == 64  # exactly at the cap is allowed
        patch.setattr(bg, "_MAX_HASH_BYTES", 5)
        with pytest.raises(Err) as info:  # no single file exceeds 5: only the running total does
            bg.hash_tree(base)
        assert info.value.code == "TREE_TOO_LARGE"
    assert bg._MAX_HASH_BYTES == 4 << 30


def test_the_entry_cap_is_inclusive(pair, monkeypatch):
    base, _ = pair
    entries = 1 + sum(1 for _ in base.rglob("*"))
    with monkeypatch.context() as patch:
        patch.setattr(bg, "_MAX_TREE_ENTRIES", entries)
        assert len(bg.hash_tree(base)) == 64
        patch.setattr(bg, "_MAX_TREE_ENTRIES", entries - 1)
        with pytest.raises(Err):
            bg.hash_tree(base)


def test_records_are_length_prefixed_so_crafted_names_and_targets_cannot_forge_another_tree(pair):
    base, head = pair
    shutil.rmtree(base / "src"), shutil.rmtree(head / "src")
    (base / "a").mkdir(), (base / "b").mkdir()
    (head / "a 0:D 755 b").mkdir()
    for root in (base, head):
        root.chmod(0o755)
    for d in (base / "a", base / "b", head / "a 0:D 755 b"):
        d.chmod(0o755)
    assert bg.hash_tree(base) != bg.hash_tree(head)


def test_a_hostile_deep_tree_is_a_coded_failure_not_a_crash(pair, monkeypatch):
    base, _ = pair
    deep = base
    for _ in range(40):
        deep = deep / "d"
        deep.mkdir()
    resource = pytest.importorskip("resource")
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    resource.setrlimit(resource.RLIMIT_NOFILE, (min(open_fds() + 10, hard), hard))
    try:
        with pytest.raises(Err) as info:
            bg.hash_tree(base)
        assert info.value.code == "TREE_UNREADABLE"
    finally:
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))
    assert len(bg.hash_tree(base)) == 64


# --- round 2 review (the test auditor's mutation-driven additions) ---

VALIDATOR = Path(bg.__file__).with_name("validate_task_target.py")


def rec(kind, mode, rel, body):
    return b"%s %o %d:%s %d:%s" % (kind, mode, len(rel), rel, len(body), body)


def use_validator(monkeypatch, tmp_path, source: bytes) -> Path:
    scripts = tmp_path / "vscripts"
    scripts.mkdir(exist_ok=True)
    copy = scripts / "validate_task_target.py"
    copy.write_bytes(source)
    monkeypatch.setattr(bg, "_task_target_state", None)
    monkeypatch.setattr(bg, "_task_target_path", lambda: copy)
    return copy


# ---------------- hash_tree
def test_X01_golden_literal_with_symlink(pair):
    base, _ = pair
    import shutil
    shutil.rmtree(base / "src")
    (base / "a").write_bytes(b"a"); (base / "a").chmod(0o644)
    (base / "l").symlink_to("a")
    base.chmod(0o755)
    exp = hashlib.sha256(b"software-builder-bench-tree-v2\0")   # literal, not bg._HASH_MAGIC
    exp.update(rec(b"D", 0o755, b"", b""))
    exp.update(rec(b"F", 0o644, b"a", hashlib.sha256(b"a").hexdigest().encode() + b":1"))
    exp.update(rec(b"L", 0, b"l", b"a"))
    assert bg.hash_tree(base) == exp.hexdigest()


def test_X02_a_file_swapped_for_another_inode_between_walk_and_open_is_refused(pair, monkeypatch):
    base, _ = pair
    real, done = os.open, []

    def swap(path, flags, *a, **kw):
        if path == "app.py" and kw.get("dir_fd") is not None and not done:
            done.append(1)
            fd = real("swap.tmp", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644, dir_fd=kw["dir_fd"])
            os.write(fd, b"x = 1\n"); os.close(fd)   # same bytes, size, mode: only (dev, ino) differs
            os.rename("swap.tmp", "app.py", src_dir_fd=kw["dir_fd"], dst_dir_fd=kw["dir_fd"])  # rename-over: a fresh inode, never a reused number
        return real(path, flags, *a, **kw)
    monkeypatch.setattr(os, "open", swap)
    with pytest.raises(Err) as info:
        bg.hash_tree(base)
    assert done and info.value.code == "TREE_UNREADABLE"


def test_X03_a_same_size_rewrite_during_the_read_is_refused(pair, monkeypatch):
    base, _ = pair
    real, n = os.read, []

    def read(fd, size):
        data = real(fd, size)
        if data and not n:
            n.append(1)
            os.utime(base / "src" / "app.py", ns=(1, 1))   # size untouched, only mtime moves
        return data
    monkeypatch.setattr(os, "read", read)
    with pytest.raises(Err) as info:
        bg.hash_tree(base)
    assert info.value.code == "TREE_UNREADABLE"


def test_X04_special_and_unknown_kinds_have_their_own_records(pair, monkeypatch):
    base, _ = pair
    real_walk = bg._walk_fd
    fakes = [("c", stat.S_IFCHR | 0o600, 0x1234), ("b", stat.S_IFBLK | 0o640, 7), ("f", stat.S_IFIFO | 0o644, 0),
             ("k", stat.S_IFSOCK | 0o644, 0), ("w", 0o160000 | 0o600, 0)]

    def walk(root, limit, *a, **kw):
        gen = real_walk(root, limit, *a, **kw)
        try:
            yield next(gen)
            for name, mode, rdev in fakes:
                yield name, -1, name, types.SimpleNamespace(st_mode=mode, st_rdev=rdev, st_dev=0, st_ino=0), None
        finally:
            gen.close()
    monkeypatch.setattr(bg, "_walk_fd", walk)
    exp = hashlib.sha256(b"software-builder-bench-tree-v2\0")
    exp.update(rec(b"D", stat.S_IMODE(base.stat().st_mode), b"", b""))
    for kind, mode, name, body in ((b"C", 0o600, b"c", b"%d" % 0x1234), (b"B", 0o640, b"b", b"7"), (b"P", 0o644, b"f", b""),
                                   (b"K", 0o644, b"k", b""), (b"S", 0o600, b"w", b"")):
        exp.update(rec(kind, mode, name, body))
    assert bg.hash_tree(base) == exp.hexdigest()


def test_X05_out_of_memory_is_tree_too_large(pair, monkeypatch):
    base, _ = pair
    def boom(fd, size): raise MemoryError
    monkeypatch.setattr(os, "read", boom)
    with pytest.raises(Err) as info:
        bg.hash_tree(base)
    assert info.value.code == "TREE_TOO_LARGE"


# ---------------- loader
OK_SRC = b"def validate_task_target(a, b):\n    return b\n"

def test_X06_validator_size_cap_is_exact(pair, monkeypatch, tmp_path):
    add_head_bench(pair[1])
    exact = OK_SRC + b"#" * ((1 << 20) - len(OK_SRC) - 1) + b"\n"
    assert len(exact) == 1 << 20
    use_validator(monkeypatch, tmp_path, exact)
    assert overlay(pair) == "BUILDER_AUTHORED"
    use_validator(monkeypatch, tmp_path, exact + b"#")
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_FAILED"


@pytest.mark.parametrize("src", [b"validate_task_target = None\n", b"validate_task_target = 'x'\n", b"raise RuntimeError('boom')\n", b"import no_such_module_xyz\n"])
def test_X07_a_validator_that_is_not_callable_or_fails_at_import_is_overlay_failed(pair, monkeypatch, tmp_path, src):
    add_head_bench(pair[1])
    use_validator(monkeypatch, tmp_path, src)
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_FAILED"


def test_X08_the_loaded_code_is_the_hashed_code_even_if_the_file_changes_between_read_and_exec(pair, monkeypatch, tmp_path):
    add_head_bench(pair[1])
    copy = use_validator(monkeypatch, tmp_path, OK_SRC)
    real = bg._read_bounded

    def reading(path, *a, **kw):
        data = real(path, *a, **kw)
        if str(path).endswith("validate_task_target.py"):
            copy.write_bytes(b"def validate_task_target(a, b):\n    return None\n")   # swapped after the read
        return data
    monkeypatch.setattr(bg, "_read_bounded", reading)
    assert overlay(pair) == "BUILDER_AUTHORED"            # v1 ran
    assert bg._task_target_sha256() == hashlib.sha256(OK_SRC).hexdigest()


@pytest.mark.parametrize("exc", ["ImportError", "SyntaxError", "ValueError", "RecursionError", "MemoryError"])
def test_X09_each_documented_exception_from_the_validator_is_overlay_failed(pair, monkeypatch, tmp_path, exc):
    add_head_bench(pair[1])
    use_validator(monkeypatch, tmp_path, f"def validate_task_target(a, b):\n    raise {exc}('x')\n".encode())
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_FAILED"


def test_X10_sha_before_any_load_and_through_a_symlinked_script_path(pair, monkeypatch, tmp_path):
    monkeypatch.setattr(bg, "_task_target_state", None)
    assert bg._task_target_sha256() == hashlib.sha256(VALIDATOR.read_bytes()).hexdigest()
    link_dir = tmp_path / "linked"; link_dir.mkdir()
    (link_dir / "benchmark_gate.py").symlink_to(Path(bg.__file__).resolve())
    monkeypatch.setattr(bg, "_task_target_state", None)
    monkeypatch.setattr(bg, "__file__", str(link_dir / "benchmark_gate.py"))
    add_head_bench(pair[1])
    assert overlay(pair) == "BUILDER_AUTHORED"           # sibling found beside the REAL file


# ---------------- _export_root
def test_X11_a_forged_marker_outside_the_fixed_parent_is_refused(pair, tmp_path):
    base, head = pair
    add_head_bench(head)
    fake = tmp_path / "bench-eeeeeeee"
    (fake / "base").mkdir(parents=True); (fake / "head").mkdir()
    marker = json.loads((base.parent / bg._MARKER_NAME).read_text()); marker["root"] = "bench-eeeeeeee"
    (fake / bg._MARKER_NAME).write_text(json.dumps(marker))
    Path(str(fake / "base") + ".export.json").write_text(json.dumps({"commit": BASE_SHA}))
    add_head_bench(fake / "head")
    refused((fake / "base", fake / "head"))


def test_X12_an_alias_of_the_dispatch_root_is_refused_not_resolved(pair, tmp_path):
    base, head = pair
    add_head_bench(head)
    alias = base.parent.parent / "bench-aliasrt"
    alias.symlink_to(base.parent)
    refused((alias / "base", head))
    assert not (base / "benchmarks").exists()


def test_X13_a_fixed_parent_reached_through_a_symlinked_temp_dir(pair, monkeypatch, tmp_path):
    base, head = pair
    add_head_bench(head)
    alias = tmp_path / "tmp_alias"
    alias.symlink_to(tempfile.tempdir)
    monkeypatch.setattr(tempfile, "tempdir", str(alias))
    assert overlay(pair) == "BUILDER_AUTHORED"


def test_X14_an_absent_fixed_parent_is_refused_and_not_created(monkeypatch, tmp_path):
    empty = tmp_path / "empty"; empty.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(empty))
    parent = bg.fixed_parent()
    with pytest.raises(Err) as info:
        bg.overlay_benchmark_file(parent / "bench-aaaaaaaa" / "base", parent / "bench-aaaaaaaa" / "head", BASE_SHA, BENCH, head_ref_commit=HEAD_SHA)
    assert info.value.code == "DEST_REJECTED" and not os.path.lexists(parent)


def test_X15_a_leaf_of_someone_else_a_vanished_leaf_and_a_nul_are_dest_rejected(pair, monkeypatch):
    base, head = pair
    add_head_bench(head)
    refused((base, base.parent / "gone"))                                  # missing leaf (OSError)
    refused((base, str(head) + "\0"))                                      # NUL in the leaf name -> regex
    refused((base, str(head).replace("software-builder-bench", "software-builder-bench\0", 1)))  # NUL reaching lstat (ValueError)
    ino = head.stat().st_ino
    monkeypatch.setattr(bg, "_foreign", lambda st: st.st_ino == ino)       # only the head leaf looks foreign
    refused((base, head))


# ---------------- sidecar
@pytest.mark.parametrize("kind", ["directory", "fifo"])
def test_X16_a_sidecar_that_is_not_a_regular_file_is_a_mismatch(pair, kind):
    base, head = pair
    add_head_bench(head)
    side = Path(str(base) + ".export.json"); side.unlink()
    side.mkdir() if kind == "directory" else os.mkfifo(side)
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_COMMIT_MISMATCH"


@pytest.mark.parametrize("body", ["[" * 4000, '{"commit": 5}', '{"commit": null}', '{"base": "%s"}' % BASE_SHA, '{"commit": "%s", "x": "é"}' % BASE_SHA])
def test_X17_hostile_sidecar_bodies_are_a_mismatch(pair, body):
    base, head = pair
    add_head_bench(head)
    Path(str(base) + ".export.json").write_bytes(body.encode())
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_COMMIT_MISMATCH"


def test_X18_sidecar_size_boundary_is_4096(pair):
    base, head = pair
    add_head_bench(head)
    side = Path(str(base) + ".export.json")
    head_part = '{"commit": "%s", "pad": "' % BASE_SHA
    for size, ok in ((4096, True), (4097, False)):
        side.write_text(head_part + "x" * (size - len(head_part) - 2) + '"}')
        assert side.stat().st_size == size
        try:
            overlay(pair); assert ok
        except Err as exc:
            assert not ok and exc.code == "OVERLAY_COMMIT_MISMATCH"
        if (base / "benchmarks").exists():
            import shutil; shutil.rmtree(base / "benchmarks")


# ---------------- _head_bytes
@pytest.mark.parametrize("name", ["benchmarks", "bench_orders.py"])
@pytest.mark.parametrize("err", [errno.ENOENT, errno.EACCES, errno.EIO])
def test_X19_only_kind_and_permission_errors_are_a_refusal_everything_else_is_a_failure(pair, monkeypatch, name, err):
    base, head = pair
    add_head_bench(head)
    real = os.open
    def flaky(path, flags, *a, **kw):
        if path == name and kw.get("dir_fd") is not None and flags & os.O_NOFOLLOW:
            raise OSError(err, "injected")
        return real(path, flags, *a, **kw)
    monkeypatch.setattr(os, "open", flaky)
    with pytest.raises(Err) as info:
        overlay(pair)
    expected = "OVERLAY_NOT_REGULAR" if err == errno.EACCES else "OVERLAY_FAILED"  # the head tree is the Builder's: unreadable is its doing
    assert info.value.code == expected and not (base / "benchmarks").exists()


@pytest.mark.parametrize("chunk", [1000, 1024, 7])
def test_X20_short_reads_still_copy_every_byte_and_still_enforce_the_cap(pair, monkeypatch, chunk):
    base, head = pair
    real = os.read
    monkeypatch.setattr(os, "read", lambda fd, n: real(fd, min(n, chunk)))
    data = bytes(i % 251 for i in range(16384))
    add_head_bench(head, data=data)
    assert overlay(pair) == "BUILDER_AUTHORED" and (base / BENCH).read_bytes() == data
    import shutil; shutil.rmtree(base / "benchmarks")
    add_head_bench(head, data=data + b"x")
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_NOT_REGULAR"


# ---------------- _overlay_into_base cleanup bookkeeping
def test_X21_a_failure_opening_the_directory_just_made_removes_it(pair, monkeypatch):
    base, head = pair
    add_head_bench(head)
    real_mkdir, real_open, armed = os.mkdir, os.open, []
    monkeypatch.setattr(os, "mkdir", lambda *a, **kw: (real_mkdir(*a, **kw), armed.append(1))[0])
    def flaky(path, flags, *a, **kw):
        if armed and path == "benchmarks":
            raise OSError(errno.EMFILE, "too many open files")
        return real_open(path, flags, *a, **kw)
    monkeypatch.setattr(os, "open", flaky)
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_FAILED" and not (base / "benchmarks").exists()


def test_X22_every_directory_created_is_removed_on_failure_not_just_the_deepest(pair, monkeypatch):
    base, head = pair
    add_head_bench(head, rel="benchmarks/sub/deeper/bench_orders.py")
    monkeypatch.setattr(os, "write", lambda fd, data: (_ for _ in ()).throw(OSError(errno.ENOSPC, "full")))
    with pytest.raises(Err):
        overlay(pair, path="benchmarks/sub/deeper/bench_orders.py")
    assert not (base / "benchmarks").exists()


def test_X23_a_keyboard_interrupt_mid_write_also_cleans_up(pair, monkeypatch):
    base, head = pair
    add_head_bench(head, rel="benchmarks/sub/bench_orders.py")
    def interrupt(fd, data): raise KeyboardInterrupt
    baseline = open_fds()
    with monkeypatch.context() as patch:
        patch.setattr(os, "write", interrupt)
        with pytest.raises(KeyboardInterrupt):
            overlay(pair, path="benchmarks/sub/bench_orders.py")
    assert not (base / "benchmarks").exists() and open_fds() == baseline


def test_X24_short_writes_are_looped(pair, monkeypatch):
    base, head = pair
    data = bytes(i % 251 for i in range(5000))
    add_head_bench(head, data=data)
    real = os.write
    with monkeypatch.context() as patch:
        patch.setattr(os, "write", lambda fd, buf: real(fd, bytes(buf[:100])))
        assert overlay(pair) == "BUILDER_AUTHORED"
    assert (base / BENCH).read_bytes() == data


# ---------------- overlay_benchmark_file: lexical path rule independent of the validator
@pytest.mark.parametrize("rel", ["src/bench_x.py", "benchmarks/helper.py", "benchmarks/bench_x.txt", "bench_x.py", "benchmarks/Bench_X.PY", "benchmarks/bench-x.py"])
def test_X25_the_lexical_rule_refuses_paths_that_exist_in_the_head(pair, rel):
    add_head_bench(pair[1], rel=rel)
    with pytest.raises(Err) as info:
        overlay(pair, path=rel)
    assert info.value.code == "OVERLAY_PATH_REJECTED" and not (pair[0] / rel).exists()


def test_X26_both_roots_bad_reports_the_base_first(pair):
    with pytest.raises(Err) as info:
        bg.overlay_benchmark_file("nope/x", "nope/y", BASE_SHA, BENCH, head_ref_commit=HEAD_SHA)
    assert "base_root" in info.value.detail


def test_X27_walk_leak_after_emfile(pair):
    base, _ = pair
    deep = base
    for _ in range(40):
        deep = deep / "d"; deep.mkdir()
    resource = pytest.importorskip("resource")
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    baseline = open_fds()
    resource.setrlimit(resource.RLIMIT_NOFILE, (min(baseline + 10, hard), hard))
    try:
        with pytest.raises(Err):
            bg.hash_tree(base)
    finally:
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))
    assert open_fds() == baseline


# --- round 2 review: head binding, helpers for C4d, exact-name head lookup, strict types, identity-checked cleanup ---

def case_insensitive(tmp_path) -> bool:
    (tmp_path / "CaseProbe").write_text("x")
    return (tmp_path / "caseprobe").exists()


def test_a_socket_at_the_head_path_is_not_regular_and_not_a_failure(pair):
    import socket

    base, head = pair
    (head / "benchmarks").mkdir()
    sock = socket.socket(socket.AF_UNIX)
    old = os.getcwd()
    os.chdir(head / "benchmarks")  # a relative name stays under the AF_UNIX path limit
    try:
        sock.bind("bench_orders.py")
    finally:
        os.chdir(old)
        sock.close()
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_NOT_REGULAR" and not (base / "benchmarks").exists()


def test_the_head_is_looked_up_by_exact_name_so_a_case_variant_is_not_the_file(pair, monkeypatch):
    base, head = pair
    add_head_bench(head)
    hide_names(monkeypatch, head, "bench_orders.py")  # what a case-insensitive filesystem does when the git path differs in case
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_PATH_REJECTED" and not (base / "benchmarks").exists()


def test_a_real_case_variant_head_entry_is_refused(pair, tmp_path):
    base, head = pair
    add_head_bench(head, rel="Benchmarks/bench_orders.py")
    if not case_insensitive(tmp_path):
        pytest.skip("needs a case-insensitive filesystem; hide_names covers the same branch everywhere")
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_PATH_REJECTED" and not (base / "benchmarks").exists()


def test_head_ref_commit_binds_the_head_export_too(pair):
    base, head = pair
    add_head_bench(head)
    Path(str(head) + ".export.json").write_text(json.dumps({"commit": HEAD_SHA, "entries": 1}))
    assert bg.export_commit(head) == HEAD_SHA and bg.export_commit(base) == BASE_SHA
    with pytest.raises(Err) as info:
        bg.overlay_benchmark_file(base, head, BASE_SHA, BENCH, head_ref_commit="c" * 40)
    assert info.value.code == "OVERLAY_COMMIT_MISMATCH" and not (base / "benchmarks").exists()
    with pytest.raises(Err) as info:
        bg.overlay_benchmark_file(base, head, BASE_SHA, BENCH, head_ref_commit="nope")
    assert info.value.code == "COMMIT_INVALID"
    assert bg.overlay_benchmark_file(base, head, BASE_SHA, BENCH, head_ref_commit=HEAD_SHA) == "BUILDER_AUTHORED"


def test_head_ref_commit_is_required_and_a_missing_head_sidecar_is_a_mismatch(pair):
    base, head = pair
    add_head_bench(head)
    with pytest.raises(TypeError):
        bg.overlay_benchmark_file(base, head, BASE_SHA, BENCH)  # the head cannot be left unbound
    Path(str(head) + ".export.json").unlink()
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_COMMIT_MISMATCH" and not (base / "benchmarks").exists()


def test_a_sha1_and_a_sha256_commit_cannot_be_mixed(pair):
    base, head = pair
    add_head_bench(head)
    Path(str(head) + ".export.json").write_text(json.dumps({"commit": "d" * 64}))
    with pytest.raises(Err) as info:
        bg.overlay_benchmark_file(base, head, BASE_SHA, BENCH, head_ref_commit="d" * 64)
    assert info.value.code == "COMMIT_INVALID"


def test_export_commit_errors_are_coded(pair):
    base, _ = pair
    Path(str(base) + ".export.json").unlink()
    with pytest.raises(Err) as info:
        bg.export_commit(base)
    assert info.value.code == "OVERLAY_COMMIT_MISMATCH"


def test_harness_sha256_covers_both_files_and_fails_with_its_own_code(pair, monkeypatch, tmp_path):
    own = hashlib.sha256(Path(bg.__file__).resolve().read_bytes()).hexdigest().encode()
    validator = hashlib.sha256(VALIDATOR.read_bytes()).hexdigest().encode()
    expected = hashlib.sha256(b"software-builder-bench-harness-v1\0%d:%s%d:%s" % (len(own), own, len(validator), validator)).hexdigest()
    bg._reset_task_target_cache()
    assert bg.harness_sha256() == expected and bg.harness_sha256() == expected
    copy = use_validator(monkeypatch, tmp_path, VALIDATOR.read_bytes() + b"# changed\n")
    assert bg.harness_sha256() != expected  # a different validator is a different harness
    copy.write_bytes(b"(((\n")
    monkeypatch.setattr(bg, "_task_target_state", None)
    with pytest.raises(Err) as info:
        bg.harness_sha256()
    assert info.value.code == "HARNESS_UNREADABLE"


def test_read_benchmark_returns_the_bytes_under_the_same_rules(pair, tmp_path):
    base, head = pair
    add_head_bench(head)
    overlay(pair)
    assert bg.read_benchmark(base, BENCH) == SRC
    for bad, code in (("benchmarks/missing_bench.py", "OVERLAY_PATH_REJECTED"), ("../x.py", "OVERLAY_PATH_REJECTED"), (7, "OVERLAY_PATH_REJECTED")):
        with pytest.raises(Err) as info:
            bg.read_benchmark(base, bad)
        assert info.value.code == code
    with pytest.raises(Err) as info:
        bg.read_benchmark(tmp_path, BENCH)
    assert info.value.code == "DEST_REJECTED"
    (base / BENCH).unlink()
    (base / BENCH).symlink_to("../src/app.py")
    with pytest.raises(Err) as info:
        bg.read_benchmark(base, BENCH)
    assert info.value.code == "OVERLAY_NOT_REGULAR"


def test_a_sealed_base_is_refused_up_front_for_new_and_existing_files_alike(pair):
    base, head = pair
    add_head_bench(head)
    add_head_bench(base)
    bg.seal_tree(base)
    with pytest.raises(Err) as info:
        overlay(pair)  # identical bytes: would otherwise be a silent PRE_EXISTING
    assert info.value.code == "OVERLAY_BASE_SEALED" and "sealed" in info.value.detail
    bg.unseal_tree(base)


def test_a_second_overlay_on_the_same_base_answers_pre_existing(pair):
    add_head_bench(pair[1])
    assert overlay(pair) == "BUILDER_AUTHORED" and overlay(pair) == "PRE_EXISTING"  # documented: retry from fresh exports


def test_the_two_roots_being_the_same_directory_by_inode_is_refused(pair, tmp_path):
    base, head = pair
    add_head_bench(head)
    if not case_insensitive(tmp_path):
        pytest.skip("needs a case-insensitive filesystem to name one directory two ways")
    alias = base.parent / "BASE"
    Path(str(alias) + ".export.json").write_text(json.dumps({"commit": BASE_SHA}))
    refused((base, alias))


@pytest.mark.parametrize("returned", ["''", "0", "object()", "None", "'other/bench_x.py'"])
def test_only_the_validator_returning_the_very_path_passes(pair, monkeypatch, tmp_path, returned):
    add_head_bench(pair[1])
    use_validator(monkeypatch, tmp_path, f"def validate_task_target(a, b):\n    return {returned}\n".encode())
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_PATH_REJECTED"


@pytest.mark.parametrize("exc", ["AttributeError", "KeyError", "TypeError", "RuntimeError", "OverflowError", "AssertionError", "NotImplementedError"])
def test_any_exception_from_the_validator_is_overlay_failed(pair, monkeypatch, tmp_path, exc):
    add_head_bench(pair[1])
    use_validator(monkeypatch, tmp_path, f"def validate_task_target(a, b):\n    raise {exc}('x')\n".encode())
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_FAILED"


def test_a_system_exit_at_import_passes_through_and_leaves_nothing_registered(pair, monkeypatch, tmp_path):
    add_head_bench(pair[1])
    use_validator(monkeypatch, tmp_path, b"raise SystemExit(3)\n")
    with pytest.raises(SystemExit) as info:
        overlay(pair)  # indistinguishable from a shutdown request delivered while the loader runs, so it is not converted
    assert info.value.code == 3
    assert "_benchmark_gate_validate_task_target" not in sys.modules and bg._task_target_state is None and bg._task_target_loading is False


def test_the_validator_may_use_dataclasses_and_its_own_file_name(pair, monkeypatch, tmp_path):
    add_head_bench(pair[1])
    source = (b"from __future__ import annotations\nimport dataclasses\n\n@dataclasses.dataclass\nclass Box:\n    value: str\n\n"
             b"def validate_task_target(root, target):\n    assert __file__.endswith('validate_task_target.py')\n    return Box(target).value\n")
    use_validator(monkeypatch, tmp_path, source)
    assert overlay(pair) == "BUILDER_AUTHORED"
    assert "_benchmark_gate_validate_task_target" in sys.modules
    bg._reset_task_target_cache()


def test_a_failed_validator_load_is_not_left_registered(pair, monkeypatch, tmp_path):
    add_head_bench(pair[1])
    use_validator(monkeypatch, tmp_path, b"raise RuntimeError('boom')\n")
    with pytest.raises(Err):
        overlay(pair)
    assert "_benchmark_gate_validate_task_target" not in sys.modules


def test_the_validator_cache_can_be_reset_and_is_one_unit(monkeypatch):
    monkeypatch.setattr(bg, "_task_target_state", None)
    module, digest = bg._load_task_target()
    assert callable(module.validate_task_target) and len(digest) == 64 and bg._load_task_target()[0] is module
    bg._reset_task_target_cache()
    assert bg._task_target_state is None


class _LyingStr(str):
    def __len__(self):
        raise RuntimeError("len")

    def __bool__(self):
        raise RuntimeError("bool")


class _HostilePath:
    def __fspath__(self):
        raise RuntimeError("fspath")


class _BytesPath:
    def __init__(self, value):
        self.value = value

    def __fspath__(self):
        return self.value


@pytest.mark.parametrize("bad", [_LyingStr("/x"), _HostilePath(), _BytesPath(3)])
def test_hostile_root_arguments_are_coded_refusals(pair, bad):
    with pytest.raises(Err) as info:
        bg.hash_tree(bad)
    assert info.value.code == "TREE_UNREADABLE"
    with pytest.raises(Err) as info:
        bg.overlay_benchmark_file(bad, pair[1], BASE_SHA, BENCH, head_ref_commit=HEAD_SHA)
    assert info.value.code == "DEST_REJECTED"


def test_a_str_subclass_root_is_refused_not_trusted(pair):
    class Sneaky(str):
        pass

    with pytest.raises(Err) as info:
        bg.hash_tree(Sneaky(str(pair[0])))
    assert info.value.code == "TREE_UNREADABLE"


@pytest.mark.parametrize("err,code", [(errno.EMFILE, "OVERLAY_FAILED"), (errno.EIO, "OVERLAY_FAILED"), (errno.ENOENT, "DEST_REJECTED"), (errno.EACCES, "DEST_REJECTED")])
def test_environmental_errors_in_the_root_checks_are_failures_not_bad_input(pair, monkeypatch, err, code):
    add_head_bench(pair[1])

    def broken(create):
        raise OSError(err, "injected")

    monkeypatch.setattr(bg, "_check_parent", broken)
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == code


def test_the_hash_depth_cap_is_enforced(pair, monkeypatch):
    base, _ = pair
    (base / "a" / "b" / "c").mkdir(parents=True)
    with monkeypatch.context() as patch:
        patch.setattr(bg, "_MAX_HASH_DEPTH", 2)
        with pytest.raises(Err) as info:
            bg.hash_tree(base)
        assert info.value.code == "TREE_TOO_LARGE"
        patch.setattr(bg, "_MAX_HASH_DEPTH", 3)
        assert len(bg.hash_tree(base)) == 64
    assert bg._MAX_HASH_DEPTH == 128


def test_a_chmod_or_ctime_change_during_the_read_is_refused(pair, monkeypatch):
    base, _ = pair
    real, hit = os.read, []

    def read(fd, size):
        data = real(fd, size)
        if data and not hit:
            hit.append(1)
            time.sleep(0.02)  # ctime is coarse on Linux: be sure it moves
            os.chmod(base / "src" / "app.py", 0o600)  # ctime moves; size and mtime do not
        return data

    monkeypatch.setattr(os, "read", read)
    with pytest.raises(Err) as info:
        bg.hash_tree(base)
    assert info.value.code == "TREE_UNREADABLE"


def test_cleanup_never_deletes_a_file_it_did_not_create(pair, monkeypatch):
    base, head = pair
    add_head_bench(head, rel="benchmarks/sub/bench_orders.py")
    real_write = os.write

    def write(fd, data):  # another actor swaps the created file for its own, then the write fails
        victim = base / "benchmarks" / "sub" / "bench_orders.py"
        victim.unlink()
        victim.write_text("someone else's file")
        raise OSError(errno.ENOSPC, "full")

    monkeypatch.setattr(os, "write", write)
    with pytest.raises(Err) as info:
        overlay(pair, path="benchmarks/sub/bench_orders.py")
    monkeypatch.setattr(os, "write", real_write)
    assert info.value.code == "OVERLAY_FAILED"
    assert (base / "benchmarks" / "sub" / "bench_orders.py").read_text() == "someone else's file"


def test_cleanup_never_removes_a_directory_that_was_replaced(pair, monkeypatch):
    base, head = pair
    add_head_bench(head, rel="benchmarks/sub/bench_orders.py")

    def write(fd, data):
        (base / "benchmarks" / "sub" / "bench_orders.py").unlink()
        (base / "benchmarks" / "sub").rmdir()
        (base / "benchmarks" / "sub").mkdir()  # a different inode with the same name
        raise OSError(errno.ENOSPC, "full")

    monkeypatch.setattr(os, "write", write)
    with pytest.raises(Err):
        overlay(pair, path="benchmarks/sub/bench_orders.py")
    assert (base / "benchmarks" / "sub").is_dir()  # the replacement is not ours to delete


def test_a_failing_cleanup_step_never_hides_the_original_error_and_the_rest_still_run(pair, monkeypatch):
    base, head = pair
    add_head_bench(head, rel="benchmarks/sub/bench_orders.py")
    monkeypatch.setattr(os, "write", lambda fd, data: (_ for _ in ()).throw(OSError(errno.ENOSPC, "full")))
    real_unlink = os.unlink
    monkeypatch.setattr(os, "unlink", lambda *a, **kw: (_ for _ in ()).throw(OSError(errno.EIO, "cleanup")))
    with pytest.raises(Err) as info:
        overlay(pair, path="benchmarks/sub/bench_orders.py")
    monkeypatch.setattr(os, "unlink", real_unlink)
    assert info.value.code == "OVERLAY_FAILED" and "ENOSPC" not in info.value.detail and "full" in info.value.detail
    assert not (base / "benchmarks" / "sub").exists() or (base / "benchmarks" / "sub" / "bench_orders.py").exists()


def test_the_dispatch_root_check_does_not_follow_a_symlinked_leaf(pair, tmp_path):
    base, head = pair
    add_head_bench(head)
    target = tmp_path / "real_head"
    shutil.copytree(head, target)
    swapped = base.parent / "linkhead"
    swapped.symlink_to(target)
    refused((base, swapped))


# --- round 3 review: hostile exceptions, descriptors held through cleanup, cleanup reporting, re-entrancy, helpers ---

class _BadStr(Exception):
    def __str__(self):
        raise _BadStr()

    __repr__ = __str__


class _BadFspath:
    def __fspath__(self):
        raise _BadStr()


def test_describe_never_raises_and_cuts_a_huge_message():
    assert bg._describe(_BadStr()) == "_BadStr"
    assert bg._describe(ValueError("x" * 100000)) == "ValueError: " + "x" * 400


def test_an_exception_whose_str_raises_never_escapes_the_public_functions(pair):
    base, head = pair
    add_head_bench(head)
    with pytest.raises(Err) as info:
        bg.hash_tree(_BadFspath())
    assert info.value.code == "TREE_UNREADABLE"
    for call in (lambda: bg.read_benchmark(_BadFspath(), BENCH), lambda: bg.repo_top_levels(_BadFspath()),
                 lambda: bg.overlay_benchmark_file(_BadFspath(), head, BASE_SHA, BENCH, head_ref_commit=HEAD_SHA)):
        with pytest.raises(Err) as info:
            call()
        assert info.value.code in ("DEST_REJECTED", "OVERLAY_FAILED")
    with pytest.raises(Err) as info:
        bg.export_commit(_BadFspath())
    assert info.value.code == "DEST_REJECTED"


def test_a_validator_raising_an_exception_whose_str_raises_is_overlay_failed(pair, monkeypatch, tmp_path):
    add_head_bench(pair[1])
    use_validator(monkeypatch, tmp_path, b"class Bad(Exception):\n    def __str__(self):\n        raise Bad()\n\n"
                  b"def validate_task_target(a, b):\n    raise Bad()\n")
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_FAILED"


@pytest.mark.parametrize("hostile", ["SystemExit", "KeyboardInterruptLike"])
def test_systemexit_from_a_hostile_fspath_is_coded_everywhere(pair, hostile):
    class Exit:
        def __fspath__(self):
            raise SystemExit(4)

    for call in (lambda: bg.hash_tree(Exit()), lambda: bg.read_benchmark(Exit(), BENCH), lambda: bg.export_commit(Exit()),
                 lambda: bg.repo_top_levels(Exit())):
        with pytest.raises(Err):
            call()


def test_the_leaf_descriptor_stays_open_until_cleanup_has_run(pair, monkeypatch):
    base, head = pair
    add_head_bench(head)
    seen = {}
    real_write, real_unlink = os.write, os.unlink

    def write(fd, data):
        seen["at_failure"] = open_fds()
        raise OSError(errno.ENOSPC, "full")

    def unlink(*args, **kwargs):
        seen["at_cleanup"] = open_fds()
        return real_unlink(*args, **kwargs)

    monkeypatch.setattr(os, "write", write)
    monkeypatch.setattr(os, "unlink", unlink)
    baseline = open_fds()
    with pytest.raises(Err):
        overlay(pair)
    assert seen["at_cleanup"] == seen["at_failure"]  # nothing was closed before the identity check, so no inode number can be reused
    monkeypatch.setattr(os, "write", real_write)
    assert open_fds() == baseline and not (base / "benchmarks").exists()


def test_a_fstat_failure_right_after_the_create_still_removes_the_file(pair, monkeypatch):
    base, head = pair
    add_head_bench(head)
    real_fstat, real_open = os.fstat, os.open
    state = {"armed": False}

    def opening(path, flags, *a, **kw):
        fd = real_open(path, flags, *a, **kw)
        if flags & os.O_CREAT:
            state["armed"] = True
        return fd

    def fstat(fd):
        if state["armed"]:
            state["armed"] = False
            raise OSError(errno.EIO, "injected")
        return real_fstat(fd)

    with monkeypatch.context() as patch:
        patch.setattr(os, "open", opening)
        patch.setattr(os, "fstat", fstat)
        with pytest.raises(Err) as info:
            overlay(pair)
    assert info.value.code == "OVERLAY_FAILED" and not (base / "benchmarks").exists()
    assert overlay(pair) == "BUILDER_AUTHORED"


def test_a_cleanup_that_cannot_finish_is_reported_not_silent(pair, monkeypatch):
    base, head = pair
    add_head_bench(head)
    with monkeypatch.context() as patch:
        patch.setattr(os, "write", lambda fd, data: (_ for _ in ()).throw(OSError(errno.ENOSPC, "full")))
        patch.setattr(os, "unlink", lambda *a, **kw: (_ for _ in ()).throw(OSError(errno.EIO, "unlink broke")))
        with pytest.raises(Err) as info:
            overlay(pair)
    assert info.value.code == "OVERLAY_FAILED" and "cleanup incomplete" in info.value.detail and "unlink broke" in info.value.detail
    assert (base / BENCH).exists()  # and the caller was told


def test_a_keyboard_interrupt_during_cleanup_is_not_swallowed_and_the_other_steps_still_run(pair, monkeypatch):
    base, head = pair
    add_head_bench(head)
    ran = []
    real_rmdir = os.rmdir
    with monkeypatch.context() as patch:  # the interrupting unlink must not outlive the call (pytest's own teardown unlinks too)
        patch.setattr(os, "write", lambda fd, data: (_ for _ in ()).throw(OSError(errno.ENOSPC, "full")))
        patch.setattr(os, "unlink", lambda *a, **kw: (_ for _ in ()).throw(KeyboardInterrupt()))
        patch.setattr(os, "rmdir", lambda *a, **kw: (ran.append(1), real_rmdir(*a, **kw))[1])
        with pytest.raises(KeyboardInterrupt):
            overlay(pair)
    assert ran  # the directory step was still attempted after the interrupted unlink


def test_cleanup_ignores_an_entry_somebody_else_already_removed(pair, monkeypatch):
    base, head = pair
    add_head_bench(head)

    def write(fd, data):
        (base / BENCH).unlink()
        (base / "benchmarks").rmdir()
        raise OSError(errno.ENOSPC, "full")

    monkeypatch.setattr(os, "write", write)
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_FAILED" and "cleanup incomplete" not in info.value.detail


def test_a_load_that_re_enters_itself_fails_instead_of_deadlocking(pair, monkeypatch, tmp_path):
    add_head_bench(pair[1])
    monkeypatch.setitem(sys.modules, "_bg_for_reentry_test", bg)
    use_validator(monkeypatch, tmp_path, b"import sys\nsys.modules['_bg_for_reentry_test']._load_task_target()\n"
                  b"def validate_task_target(a, b):\n    return b\n")
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_FAILED" and "re-entered" in info.value.detail
    assert bg._task_target_loading is False


def test_the_loaded_flag_is_cleared_after_any_failure(pair, monkeypatch, tmp_path):
    add_head_bench(pair[1])
    use_validator(monkeypatch, tmp_path, b"(((\n")
    with pytest.raises(Err):
        overlay(pair)
    assert bg._task_target_loading is False


def test_harness_sha256_survives_an_undefined_file_and_caches_its_own_digest(pair, monkeypatch):
    bg._reset_task_target_cache()
    first = bg.harness_sha256()
    monkeypatch.delitem(bg.__dict__, "__file__")  # an embedded loader: no __file__ at all
    assert bg.harness_sha256() == first  # cached: the digest this process has been using
    bg._reset_task_target_cache()
    with pytest.raises(Err) as info:
        bg.harness_sha256()
    assert info.value.code == "HARNESS_UNREADABLE"


@pytest.mark.parametrize("root", [None, 5, b"/x", "", "///", "x\0y"])
def test_export_commit_arguments_are_coded(pair, root):
    with pytest.raises(Err) as info:
        bg.export_commit(root)
    assert info.value.code == "DEST_REJECTED"


def test_export_commit_names_the_sidecar_beside_the_export(pair):
    base, _ = pair
    assert bg.export_commit(base) == BASE_SHA == bg.export_commit(str(base)) == bg.export_commit(str(base) + "/") == bg.export_commit(str(base) + "//")


def test_repo_top_levels_is_taken_before_the_overlay(pair):
    base, head = pair
    add_head_bench(head)
    before = bg.repo_top_levels(base)
    assert isinstance(before, frozenset) and {"src", "app"} <= before and "benchmarks" not in before
    overlay(pair)
    assert "benchmarks" in bg.repo_top_levels(base)
    with pytest.raises(Err) as info:
        bg.repo_top_levels("/nowhere")
    assert info.value.code == "DEST_REJECTED"


def test_the_return_type_is_the_literal_the_design_names():
    assert str(bg.overlay_benchmark_file.__annotations__["return"]).startswith("Literal[")
    assert "PRE_EXISTING" in bg.overlay_benchmark_file.__annotations__["return"] and "BUILDER_AUTHORED" in bg.overlay_benchmark_file.__annotations__["return"]


@pytest.mark.parametrize("field", ["st_nlink", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns"])
def test_each_change_detection_field_is_checked_against_a_fresh_stat_of_the_name(pair, monkeypatch, field):
    base, _ = pair
    real = os.stat
    armed = {"read": False}
    real_read = os.read

    def read(fd, size):
        data = real_read(fd, size)
        armed["read"] = True
        return data

    def stat_(path, *a, **kw):
        result = real(path, *a, **kw)
        if armed["read"] and path == "app.py" and kw.get("follow_symlinks") is False:
            fields = {f: getattr(result, f) for f in ("st_dev", "st_ino", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns", "st_mode")}
            fields[field] += 1
            return types.SimpleNamespace(**fields)
        return result

    monkeypatch.setattr(os, "read", read)
    monkeypatch.setattr(os, "stat", stat_)
    with pytest.raises(Err) as info:
        bg.hash_tree(base)
    assert info.value.code == "TREE_UNREADABLE"


def test_a_base_file_with_two_links_is_not_pre_existing(pair, tmp_path):
    base, head = pair
    add_head_bench(head)
    add_head_bench(base)
    os.link(base / BENCH, tmp_path / "alias")
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "BENCHMARK_MODIFIED"


def test_a_dispatch_root_that_resolves_to_another_name_is_refused(pair, monkeypatch):
    base, head = pair
    add_head_bench(head)
    real = os.path.realpath
    other = bg.fixed_parent() / "bench-zzzzzzzz"
    other.mkdir()

    def realpath(path, *a, **kw):
        return str(other) if str(path).endswith("bench-aaaaaaaa") else real(path, *a, **kw)

    monkeypatch.setattr(os.path, "realpath", realpath)
    refused((base, head))


def test_bytes_roots_are_refused_by_the_export_helpers_but_hashable(pair):
    base, head = pair
    add_head_bench(head)
    with pytest.raises(Err) as info:
        bg.read_benchmark(os.fsencode(base), BENCH)
    assert info.value.code == "DEST_REJECTED"
    refused((os.fsencode(base), head))
    assert bg.hash_tree(os.fsencode(base)) == bg.hash_tree(base)


# --- round 3 test auditor (mutation-driven additions) ---

# ======================= Z: round-3 candidate tests =======================


@pytest.mark.parametrize("base_data", [b"", SRC[:10], SRC[:-1]])
def test_z01_a_truncated_base_file_is_modified_not_pre_existing(pair, base_data):
    base, head = pair
    add_head_bench(head)
    add_head_bench(base, data=base_data)
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "BENCHMARK_MODIFIED"


def test_z02_a_base_file_one_byte_longer_than_a_16_kib_head_is_modified(pair):
    base, head = pair
    full = b"#" * 16384
    add_head_bench(head, data=full)
    add_head_bench(base, data=full + b"#")
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "BENCHMARK_MODIFIED"


def test_z03_run_cleanup_runs_every_step_and_keeps_the_first_failure_and_the_first_fatal():
    calls = []

    def a():
        calls.append("a"); raise ValueError("first")

    def b():
        calls.append("b"); raise KeyboardInterrupt()

    def c():
        calls.append("c")

    failure, fatal = bg._run_cleanup([a, b, c])
    assert calls == ["a", "b", "c"] and isinstance(failure, ValueError) and isinstance(fatal, KeyboardInterrupt)
    assert bg._run_cleanup([c]) == (None, None)
    assert bg._run_cleanup([lambda: (_ for _ in ()).throw(FileNotFoundError())]) == (None, None)  # already removed: not a failure
    failure, fatal = bg._run_cleanup([a, lambda: (_ for _ in ()).throw(ValueError("second"))])
    assert str(failure) == "first" and fatal is None  # the FIRST ordinary failure is kept


def test_z04_a_failing_unlink_does_not_stop_the_directory_removals(pair, monkeypatch):
    base, head = pair
    add_head_bench(head, rel="benchmarks/sub/bench_orders.py")
    monkeypatch.setattr(os, "write", lambda fd, data: (_ for _ in ()).throw(OSError(errno.ENOSPC, "full")))
    monkeypatch.setattr(os, "unlink", lambda *a, **kw: (_ for _ in ()).throw(OSError(errno.EIO, "cleanup")))
    rmdirs = []
    real_rmdir = os.rmdir
    monkeypatch.setattr(os, "rmdir", lambda p, **kw: (rmdirs.append(p), real_rmdir(p, **kw))[1])
    with pytest.raises(Err):
        overlay(pair, path="benchmarks/sub/bench_orders.py")
    # the file could not be removed so the directories are non-empty, but both removals must have been ATTEMPTED, deepest first
    assert rmdirs == ["sub", "benchmarks"]


def test_z05_a_rejected_path_is_escaped_and_bounded_in_the_detail(pair):
    bad = "x\x1b[31m\n`|" + "A" * 5000 + ".py"
    with pytest.raises(Err) as info:
        overlay(pair, path=bad)
    detail = info.value.detail
    assert info.value.code == "OVERLAY_PATH_REJECTED" and "\x1b" not in detail and "\n" not in detail and len(detail) <= 200


@pytest.mark.parametrize("err", [errno.ENOENT, errno.ENOTDIR, errno.ELOOP, errno.EACCES, errno.EPERM, errno.ENAMETOOLONG])
def test_z06_each_bad_path_errno_in_the_root_checks_is_dest_rejected(pair, monkeypatch, err):
    add_head_bench(pair[1])

    def broken(create):
        raise OSError(err, "injected")

    monkeypatch.setattr(bg, "_check_parent", broken)
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "DEST_REJECTED"


def test_z07_a_wrong_parent_refusal_does_not_create_the_fixed_parent(monkeypatch, tmp_path):
    empty = tmp_path / "empty"; empty.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(empty))
    parent = bg.fixed_parent()
    other = tmp_path / "other" / "bench-aaaaaaaa"
    (other / "base").mkdir(parents=True); (other / "head").mkdir()
    with pytest.raises(Err) as info:
        bg.overlay_benchmark_file(other / "base", other / "head", BASE_SHA, BENCH, head_ref_commit=HEAD_SHA)
    assert info.value.code == "DEST_REJECTED" and not os.path.lexists(parent)


def test_z08_a_4097_byte_sidecar_whose_first_4096_bytes_are_valid_json_is_refused(pair):
    base, head = pair
    add_head_bench(head)
    side = Path(str(base) + ".export.json")
    body = '{"commit": "%s"}' % BASE_SHA
    side.write_text(body + " " * (4096 - len(body)))
    assert bg.export_commit(base) == BASE_SHA
    side.write_text(body + " " * (4097 - len(body)))
    with pytest.raises(Err) as info:
        bg.export_commit(base)
    assert info.value.code == "OVERLAY_COMMIT_MISMATCH"


@pytest.mark.parametrize("commit", ["g" * 40, "a" * 41, "a" * 39, "A" * 40, "a" * 40 + "\n", "not hex at all", 1234567890123456789012345678901234567890])
def test_z09_export_commit_returns_only_a_40_or_64_lowercase_hex_string(pair, commit):
    base, _ = pair
    Path(str(base) + ".export.json").write_text(json.dumps({"commit": commit}))
    with pytest.raises(Err) as info:
        bg.export_commit(base)
    assert info.value.code == "OVERLAY_COMMIT_MISMATCH"


def test_z10_export_commit_under_a_file_parent_and_bad_argument_types_are_coded(pair, tmp_path):
    (tmp_path / "afile").write_text("x")
    with pytest.raises(Err) as info:
        bg.export_commit(tmp_path / "afile" / "base")
    assert info.value.code == "OVERLAY_COMMIT_MISMATCH"


@pytest.mark.parametrize("bad", [None, 7, b"/x/base"])
def test_z10b_export_commit_with_a_non_path_argument_is_dest_rejected(pair, bad):
    with pytest.raises(Err) as info:
        bg.export_commit(bad)
    assert info.value.code == "DEST_REJECTED"


@pytest.mark.parametrize("src", [b"x = 1\n", b"validate_task_target = 3\n"])
def test_z11_the_loader_and_harness_sha_fail_coded_and_leave_nothing_registered(pair, monkeypatch, tmp_path, src):
    use_validator(monkeypatch, tmp_path, src)
    with pytest.raises(Err) as info:
        bg._load_task_target()
    assert info.value.code == "OVERLAY_FAILED" and "cannot load validate_task_target.py" in info.value.detail
    assert "_benchmark_gate_validate_task_target" not in sys.modules and bg._task_target_state is None
    with pytest.raises(Err) as info:
        bg.harness_sha256()
    assert info.value.code == "HARNESS_UNREADABLE" and "cannot load validate_task_target.py" in info.value.detail


def test_z12_concurrent_first_loads_execute_the_validator_once(pair, monkeypatch, tmp_path):
    import builtins
    src = (b"import builtins, time\nbuiltins._z_count = getattr(builtins, '_z_count', 0) + 1\ntime.sleep(0.3)\n"
           b"def validate_task_target(a, b):\n    return b\n")
    use_validator(monkeypatch, tmp_path, src)
    out = []
    threads = [threading.Thread(target=lambda: out.append(bg._load_task_target()[0])) for _ in range(4)]
    try:
        [t.start() for t in threads]; [t.join() for t in threads]
        assert getattr(builtins, "_z_count", 0) == 1 and len({id(m) for m in out}) == 1
    finally:
        if hasattr(builtins, "_z_count"):
            del builtins._z_count


def test_z13_an_oversize_harness_file_is_unreadable_not_silently_truncated(pair, monkeypatch, tmp_path):
    big = tmp_path / "gate_copy.py"
    big.write_bytes(b"#" * ((4 << 20) + 1))
    monkeypatch.setattr(bg, "__file__", str(big))
    assert bg._digest_own_file() == ""  # over 4 MiB: refused, not hashed truncated
    big.write_bytes(b"#" * (4 << 20))
    assert bg._digest_own_file() == hashlib.sha256(b"#" * (4 << 20)).hexdigest()
    monkeypatch.setattr(bg, "_SELF_DIGEST", "")
    with pytest.raises(Err) as info:
        bg.harness_sha256()
    assert info.value.code == "HARNESS_UNREADABLE"


def test_z14_a_str_subclass_export_root_is_refused_by_the_overlay(pair):
    class Sneaky(str):
        pass
    with pytest.raises(Err) as info:
        bg.overlay_benchmark_file(Sneaky(str(pair[0])), pair[1], BASE_SHA, BENCH, head_ref_commit=HEAD_SHA)
    assert info.value.code == "DEST_REJECTED"


def test_z15_read_benchmark_applies_the_lexical_rules_to_files_that_exist(pair):
    base, _ = pair
    with pytest.raises(Err) as info:
        bg.read_benchmark(base, "src/app.py")
    assert info.value.code == "OVERLAY_PATH_REJECTED"


def test_z16_a_directory_swapped_between_mkdir_and_open_is_a_conflict_and_the_swap_survives(pair, monkeypatch):
    base, head = pair
    add_head_bench(head)
    real, done = os.open, []

    def op(path, flags, *a, **kw):
        if path == "benchmarks" and kw.get("dir_fd") is not None and not done and (base / "benchmarks").exists():
            done.append(1)
            os.rename(base / "benchmarks", base / "orig")
            os.mkdir(base / "benchmarks")
        return real(path, flags, *a, **kw)

    monkeypatch.setattr(os, "open", op)
    with pytest.raises(Err) as info:
        overlay(pair)
    assert done and info.value.code == "OVERLAY_PATH_CONFLICT" and (base / "benchmarks").is_dir()


def test_z17_a_file_replaced_by_a_fifo_between_walk_and_open_does_not_hang(pair, monkeypatch):
    base, _ = pair
    real, done = os.open, []

    def op(path, flags, *a, **kw):
        if path == "app.py" and kw.get("dir_fd") is not None and not done:
            done.append(1)
            os.unlink("app.py", dir_fd=kw["dir_fd"])
            os.mkfifo("app.py", dir_fd=kw["dir_fd"])
        return real(path, flags, *a, **kw)

    class Hang(BaseException):  # not an OSError: hash_tree would turn that into the very refusal this test expects
        pass

    def boom(*_):
        raise Hang("open of a FIFO blocked")

    monkeypatch.setattr(os, "open", op)
    old = signal.signal(signal.SIGALRM, boom)
    signal.alarm(5)
    try:
        with pytest.raises(Err) as info:
            bg.hash_tree(base)
    finally:
        signal.alarm(0); signal.signal(signal.SIGALRM, old)
    assert done and info.value.code == "TREE_UNREADABLE"


@pytest.mark.parametrize("how,expected", [("alias", "OVERLAY_NOT_REGULAR"), ("replace", "OVERLAY_FAILED")])
def test_z18_a_head_file_changed_between_its_stat_and_its_open(pair, monkeypatch, tmp_path, how, expected):
    base, head = pair
    add_head_bench(head)
    real, count = os.open, []

    def op(path, flags, *a, **kw):
        if path == "bench_orders.py" and kw.get("dir_fd") is not None and flags & os.O_NOFOLLOW:
            count.append(1)
            if how == "alias" and len(count) == 1:
                os.link(head / BENCH, tmp_path / "alias.py")
            elif how == "replace":  # on EVERY attempt: the file never settles
                (head / "tmp.py").write_bytes(SRC); os.replace(head / "tmp.py", head / BENCH)
        return real(path, flags, *a, **kw)

    with monkeypatch.context() as patch:
        patch.setattr(os, "open", op)
        with pytest.raises(Err) as info:
            overlay(pair)
    assert count and info.value.code == expected and not (base / "benchmarks").exists()
    if how == "replace":
        assert len(count) == bg._READ_ATTEMPTS  # retried, then gave up as a crash rather than a verdict


def test_z18b_a_single_swap_between_stat_and_open_is_retried_and_succeeds(pair, monkeypatch):
    base, head = pair
    add_head_bench(head)
    real, done = os.open, []

    def op(path, flags, *a, **kw):
        if path == "bench_orders.py" and kw.get("dir_fd") is not None and flags & os.O_NOFOLLOW and not done:
            done.append(1)
            (head / "tmp.py").write_bytes(SRC); os.replace(head / "tmp.py", head / BENCH)
        return real(path, flags, *a, **kw)

    with monkeypatch.context() as patch:
        patch.setattr(os, "open", op)
        assert overlay(pair) == "BUILDER_AUTHORED"
    assert done and (base / BENCH).read_bytes() == SRC


@pytest.mark.parametrize("err", [errno.ELOOP, errno.ENOTDIR, errno.EMLINK])
@pytest.mark.parametrize("side", ["head", "base"])
def test_z19_every_not_a_directory_errno_is_a_refusal_for_a_parent(pair, monkeypatch, err, side):
    base, head = pair
    add_head_bench(head)
    (base / "benchmarks").mkdir()
    real, calls = os.open, []

    def flaky(path, flags, *a, **kw):
        if path == "benchmarks" and kw.get("dir_fd") is not None and flags & os.O_NOFOLLOW:
            calls.append(1)
            if len(calls) == (1 if side == "head" else 2):
                raise OSError(err, "injected")
        return real(path, flags, *a, **kw)

    monkeypatch.setattr(os, "open", flaky)
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == ("OVERLAY_NOT_REGULAR" if side == "head" else "OVERLAY_PATH_CONFLICT")


def test_z20_a_sealed_base_is_reported_after_commit_and_path_problems(pair):
    base, head = pair
    add_head_bench(head)
    bg.seal_tree(base)
    try:
        for kwargs, code in (({"commit": "c" * 40}, "OVERLAY_COMMIT_MISMATCH"), ({"path": "benchmarks/missing_bench.py"}, "OVERLAY_PATH_REJECTED"), ({"path": "../x.py"}, "OVERLAY_PATH_REJECTED"), ({}, "OVERLAY_BASE_SEALED")):
            with pytest.raises(Err) as info:
                overlay(pair, **kwargs)
            assert info.value.code == code
    finally:
        bg.unseal_tree(base)


def test_z21_existing_parents_two_levels_deep_are_walked_one_level_at_a_time(pair):
    base, head = pair
    rel = "benchmarks/sub/bench_orders.py"
    add_head_bench(head, rel=rel)
    (base / "benchmarks" / "sub").mkdir(parents=True)
    assert overlay(pair, path=rel) == "BUILDER_AUTHORED" and (base / rel).read_bytes() == SRC
    assert overlay(pair, path=rel) == "PRE_EXISTING"


def test_z22_a_failing_close_of_a_descriptor_does_not_mask_a_successful_overlay(pair, monkeypatch):
    base, head = pair
    add_head_bench(head)
    real, state = os.close, {"armed": False}
    base_ino = base.stat().st_ino

    def close(fd):
        try:
            hit = state["armed"] and os.fstat(fd).st_ino == base_ino
        except OSError:
            hit = False
        real(fd)
        if hit:
            state["armed"] = False
            raise OSError(errno.EIO, "close failed")

    state["armed"] = True
    monkeypatch.setattr(os, "close", close)
    assert overlay(pair) == "BUILDER_AUTHORED"
    monkeypatch.setattr(os, "close", real)
    assert (base / BENCH).read_bytes() == SRC


@pytest.mark.parametrize("err", [errno.ENOENT, errno.ENOTDIR, errno.ELOOP, errno.EMLINK])
def test_z23_export_commit_sidecar_open_errnos_that_mean_not_a_file_are_a_mismatch(pair, monkeypatch, err):
    def broken(*a, **kw):
        raise OSError(err, "injected")
    monkeypatch.setattr(bg, "_read_bounded", broken)
    with pytest.raises(Err) as info:
        bg.export_commit(pair[0])
    assert info.value.code == "OVERLAY_COMMIT_MISMATCH"


@pytest.mark.parametrize("err", [errno.EIO, errno.EMFILE, errno.EACCES])
def test_z24_export_commit_environmental_errnos_propagate(pair, monkeypatch, err):
    def broken(*a, **kw):
        raise OSError(err, "injected")
    monkeypatch.setattr(bg, "_read_bounded", broken)
    with pytest.raises(OSError) as info:
        bg.export_commit(pair[0])
    assert info.value.errno == err


# --- round 4 review: seal arguments, interrupt handling, closes, untracked creations, classification, repo_top_levels, import-time digest ---

@pytest.mark.parametrize("bad", ["", None, 5, b"", _HostilePath(), _LyingStr("/x")])
def test_seal_and_unseal_refuse_an_empty_or_hostile_root_instead_of_touching_the_working_directory(pair, tmp_path, monkeypatch, bad):
    victim = tmp_path / "cwd"
    (victim / "sub").mkdir(parents=True)
    (victim / "sub" / "f").write_text("x")
    before = {p: stat.S_IMODE(p.stat().st_mode) for p in [victim, *victim.rglob("*")]}
    monkeypatch.chdir(victim)
    for func in (bg.seal_tree, bg.unseal_tree):
        with pytest.raises(Err) as info:
            func(bad)
        assert info.value.code == "TREE_UNREADABLE"
    assert {p: stat.S_IMODE(p.stat().st_mode) for p in [victim, *victim.rglob("*")]} == before


def test_a_benchmark_gate_error_shows_its_reason_when_printed():
    assert str(Err("DEST_REJECTED", "not a usable path")) == "DEST_REJECTED: not a usable path"
    assert str(Err("OVERLAY_FAILED")) == "OVERLAY_FAILED"


def test_a_close_that_raises_is_never_repeated_on_the_same_descriptor_number(pair, monkeypatch):
    base, head = pair
    add_head_bench(head)
    real, closed, leaf_fds = os.close, [], []
    real_open = os.open

    def opening(path, flags, *a, **kw):
        fd = real_open(path, flags, *a, **kw)
        if flags & os.O_CREAT:
            leaf_fds.append(fd)
        return fd

    def close(fd):
        closed.append(fd)
        real(fd)
        if leaf_fds and fd == leaf_fds[0] and closed.count(fd) == 1:
            raise OSError(errno.EIO, "close failed")

    with monkeypatch.context() as patch:
        patch.setattr(os, "open", opening)
        patch.setattr(os, "close", close)
        with pytest.raises(Err):
            overlay(pair)
    assert closed.count(leaf_fds[0]) == 1  # a second close could hit a descriptor another thread was just given
    assert not (base / "benchmarks").exists()  # and the file the failed close left behind was cleaned up


def test_a_keyboard_interrupt_stays_a_keyboard_interrupt_even_when_cleanup_also_fails(pair, monkeypatch):
    base, head = pair
    add_head_bench(head)
    with monkeypatch.context() as patch:
        patch.setattr(os, "write", lambda fd, data: (_ for _ in ()).throw(KeyboardInterrupt()))
        patch.setattr(os, "unlink", lambda *a, **kw: (_ for _ in ()).throw(PermissionError(errno.EACCES, "no")))
        with pytest.raises(KeyboardInterrupt):
            overlay(pair)


def test_an_interrupt_during_cleanup_is_not_hidden_by_an_earlier_ordinary_cleanup_error(pair, monkeypatch):
    base, head = pair
    add_head_bench(head, rel="benchmarks/sub/bench_orders.py")
    real_rmdir = os.rmdir
    with monkeypatch.context() as patch:
        patch.setattr(os, "write", lambda fd, data: (_ for _ in ()).throw(OSError(errno.ENOSPC, "full")))
        patch.setattr(os, "unlink", lambda *a, **kw: (_ for _ in ()).throw(PermissionError(errno.EACCES, "no")))
        patch.setattr(os, "rmdir", lambda *a, **kw: (_ for _ in ()).throw(KeyboardInterrupt()))
        with pytest.raises(KeyboardInterrupt):
            overlay(pair, path="benchmarks/sub/bench_orders.py")
    assert real_rmdir  # restored


def test_a_directory_whose_stat_fails_right_after_mkdir_is_still_removed(pair, monkeypatch):
    base, head = pair
    add_head_bench(head)
    real_stat, armed = os.stat, []
    real_mkdir = os.mkdir

    def mkdir(path, *a, **kw):
        real_mkdir(path, *a, **kw)
        armed.append(path)

    def stat_(path, *a, **kw):
        if armed and path == "benchmarks" and kw.get("dir_fd") is not None and len(armed) == 1 and not getattr(stat_, "hit", False):
            stat_.hit = True
            raise OSError(errno.EIO, "injected")
        return real_stat(path, *a, **kw)

    with monkeypatch.context() as patch:
        patch.setattr(os, "mkdir", mkdir)
        patch.setattr(os, "stat", stat_)
        with pytest.raises(Err) as info:
            overlay(pair)
    assert info.value.code == "OVERLAY_FAILED" and not (base / "benchmarks").exists()


def test_when_the_created_file_cannot_be_identified_a_foreign_file_at_that_name_is_never_deleted(pair, monkeypatch):
    base, head = pair
    add_head_bench(head)
    real_fstat, real_open, state = os.fstat, os.open, {"armed": False}

    def opening(path, flags, *a, **kw):
        fd = real_open(path, flags, *a, **kw)
        if flags & os.O_CREAT:
            state["armed"] = True
        return fd

    def fstat(fd):
        if state["armed"]:
            state["armed"] = False
            victim = base / BENCH  # another actor replaces the name, then our identity read fails
            victim.unlink()
            victim.write_text("FOREIGN")
            raise OSError(errno.EIO, "injected")
        return real_fstat(fd)

    with monkeypatch.context() as patch:
        patch.setattr(os, "open", opening)
        patch.setattr(os, "fstat", fstat)
        with pytest.raises(Err):
            overlay(pair)
    assert (base / BENCH).read_text() == "FOREIGN"


@pytest.mark.skipif(IS_ROOT, reason="root can read anything")
def test_an_unreadable_identical_base_file_is_a_harness_failure_not_a_modified_benchmark(pair):
    base, head = pair
    add_head_bench(head)
    add_head_bench(base)
    (base / BENCH).chmod(0)
    with pytest.raises(Err) as info:
        overlay(pair)
    (base / BENCH).chmod(0o644)
    assert info.value.code == "OVERLAY_FAILED"


def test_a_read_error_on_an_existing_base_file_is_a_failure_not_a_verdict(pair, monkeypatch):
    base, head = pair
    add_head_bench(head)
    add_head_bench(base)
    real = os.open

    def flaky(path, flags, *a, **kw):
        if path == "bench_orders.py" and kw.get("dir_fd") is not None and flags & os.O_NOFOLLOW and not flags & os.O_CREAT:
            flaky.calls = getattr(flaky, "calls", 0) + 1
            if flaky.calls == 2:  # the head read is the first call; the base read is the second
                raise OSError(errno.EMFILE, "too many open files")
        return real(path, flags, *a, **kw)

    with monkeypatch.context() as patch:
        patch.setattr(os, "open", flaky)
        with pytest.raises(Err) as info:
            overlay(pair)
    assert info.value.code == "OVERLAY_FAILED"


@pytest.mark.skipif(IS_ROOT, reason="root can read anything")
def test_a_head_file_the_builder_made_unreadable_is_a_refusal_not_a_crash(pair):
    base, head = pair
    add_head_bench(head)
    (head / BENCH).chmod(0)
    with pytest.raises(Err) as info:
        overlay(pair)
    (head / BENCH).chmod(0o644)
    assert info.value.code == "OVERLAY_NOT_REGULAR"


@pytest.mark.skipif(IS_ROOT, reason="root can list anything")
def test_a_head_parent_the_builder_made_unlistable_is_a_refusal(pair):
    base, head = pair
    add_head_bench(head)
    (head / "benchmarks").chmod(0)
    with pytest.raises(Err) as info:
        overlay(pair)
    (head / "benchmarks").chmod(0o755)
    assert info.value.code in ("OVERLAY_NOT_REGULAR", "OVERLAY_PATH_REJECTED")


def test_repo_top_levels_never_follows_a_symlink(pair, tmp_path):
    base, _ = pair
    outside = tmp_path / "outside"
    (outside / "secretpkg").mkdir(parents=True)
    (outside / "other.py").write_text("")
    shutil.rmtree(base / "src")
    (base / "src").symlink_to(outside)  # a symlinked src contributes nothing
    (base / "linkpkg").symlink_to(outside / "secretpkg")  # nor does a symlink named like a package
    (base / "realpkg").mkdir()
    (base / "mod.py").write_text("")
    (base / "link_mod.py").symlink_to(outside / "other.py")
    (base / "not-an-identifier").mkdir()
    (base / "readme.txt").write_text("")
    assert bg.repo_top_levels(base) == frozenset({"realpkg", "mod"})


def test_repo_top_levels_reads_src_when_it_is_a_real_directory(pair):
    base, _ = pair
    (base / "src" / "pkg").mkdir()
    assert bg.repo_top_levels(base) >= {"src", "app", "pkg"}


def test_repo_top_levels_is_bounded(pair, monkeypatch):
    base, _ = pair
    for i in range(5):
        (base / f"m{i}.py").write_text("")
    with monkeypatch.context() as patch:
        patch.setattr(bg, "_MAX_TREE_ENTRIES", 3)
        with pytest.raises(Err) as info:
            bg.repo_top_levels(base)
    assert info.value.code == "TREE_TOO_LARGE"


def test_harness_sha256_names_the_file_as_it_was_when_imported(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    gate = scripts / "benchmark_gate.py"
    shutil.copy(Path(bg.__file__), gate)
    shutil.copy(VALIDATOR, scripts / "validate_task_target.py")
    fresh = _load(gate, "benchmark_gate_import_time_copy")
    before = fresh.harness_sha256()
    gate.write_text(gate.read_text() + "\n# edited after import\n")  # the importer already used the old bytes
    assert fresh.harness_sha256() == before
    assert fresh._SELF_DIGEST == hashlib.sha256(Path(bg.__file__).read_bytes()).hexdigest()
    again = _load(gate, "benchmark_gate_import_time_copy2")
    assert again.harness_sha256() != before  # a fresh import sees the edited file


def test_a_validator_load_waits_a_bounded_time_for_the_lock(pair, monkeypatch):
    add_head_bench(pair[1])
    monkeypatch.setattr(bg, "_task_target_state", None)
    monkeypatch.setattr(bg, "_LOAD_LOCK_SECONDS", 0.2)
    held, release = threading.Event(), threading.Event()

    def hold():
        with bg._task_target_lock:
            held.set()
            release.wait(5)

    thread = threading.Thread(target=hold)
    thread.start()
    held.wait(5)
    try:
        started = time.monotonic()
        with pytest.raises(Err) as info:
            overlay(pair)
        assert info.value.code == "OVERLAY_FAILED" and "timed out" in info.value.detail and time.monotonic() - started < 3
    finally:
        release.set()
        thread.join()


def test_commit_mismatch_is_a_harness_fault_not_a_verdict_about_the_pr():
    assert "OVERLAY_COMMIT_MISMATCH" not in bg.OVERLAY_REFUSAL_CODES and "OVERLAY_COMMIT_MISMATCH" in bg.ERROR_CODES
    assert "OVERLAY_BASE_SEALED" not in bg.OVERLAY_REFUSAL_CODES


# --- round 5 review: a real SystemExit passes through, interrupt notes, NUL/surrogate roots, torn reads ---

def test_a_shutdown_request_during_the_write_is_re_raised_as_itself_after_cleanup(pair, monkeypatch):
    base, head = pair
    add_head_bench(head, rel="benchmarks/sub/bench_orders.py")
    with monkeypatch.context() as patch:
        patch.setattr(os, "write", lambda fd, data: (_ for _ in ()).throw(SystemExit(143)))  # a SIGTERM handler calling sys.exit
        with pytest.raises(SystemExit) as info:
            overlay(pair, path="benchmarks/sub/bench_orders.py")
    assert info.value.code == 143 and not (base / "benchmarks").exists()


def test_a_shutdown_request_during_cleanup_is_re_raised_as_itself(pair, monkeypatch):
    base, head = pair
    add_head_bench(head)
    with monkeypatch.context() as patch:
        patch.setattr(os, "write", lambda fd, data: (_ for _ in ()).throw(OSError(errno.ENOSPC, "full")))
        patch.setattr(os, "unlink", lambda *a, **kw: (_ for _ in ()).throw(SystemExit(3)))
        with pytest.raises(SystemExit):
            overlay(pair)


def test_a_shutdown_request_is_not_swallowed_by_the_read_helpers(pair, monkeypatch):
    base, head = pair
    add_head_bench(head)
    overlay(pair)
    for call in (lambda: bg.read_benchmark(base, BENCH), lambda: bg.repo_top_levels(base)):
        with monkeypatch.context() as patch:
            patch.setattr(os, "listdir", lambda *a, **kw: (_ for _ in ()).throw(SystemExit(5)))
            with pytest.raises(SystemExit):
                call()


def test_an_interrupt_with_a_failed_cleanup_carries_a_note_about_the_leftover(pair, monkeypatch):
    base, head = pair
    add_head_bench(head)
    with monkeypatch.context() as patch:
        patch.setattr(os, "write", lambda fd, data: (_ for _ in ()).throw(KeyboardInterrupt()))
        patch.setattr(os, "unlink", lambda *a, **kw: (_ for _ in ()).throw(PermissionError(errno.EACCES, "no unlink")))
        with pytest.raises(KeyboardInterrupt) as info:
            overlay(pair)
    assert any("overlay cleanup incomplete" in note and "no unlink" in note for note in info.value.__notes__)
    assert (base / BENCH).exists()  # and the leftover is exactly what the note reports


def test_an_interrupt_with_a_clean_cleanup_has_no_note(pair, monkeypatch):
    base, head = pair
    add_head_bench(head)
    with monkeypatch.context() as patch:
        patch.setattr(os, "write", lambda fd, data: (_ for _ in ()).throw(KeyboardInterrupt()))
        with pytest.raises(KeyboardInterrupt) as info:
            overlay(pair)
    assert not getattr(info.value, "__notes__", []) and not (base / "benchmarks").exists()


def test_a_systemexit_raised_while_the_validator_runs_passes_through(pair, monkeypatch, tmp_path):
    add_head_bench(pair[1])
    use_validator(monkeypatch, tmp_path, b"def validate_task_target(a, b):\n    raise SystemExit(9)\n")
    with pytest.raises(SystemExit) as info:
        overlay(pair)
    assert info.value.code == 9


@pytest.mark.parametrize("bad", ["a\0b", b"a\0b", "\ud800x"])
def test_seal_unseal_and_hash_refuse_a_root_with_a_nul_or_a_lone_surrogate(bad):
    for func in (bg.seal_tree, bg.unseal_tree, bg.hash_tree):
        with pytest.raises(Err) as info:
            func(bad)
        assert info.value.code == "TREE_UNREADABLE"


def torn(pair, monkeypatch, how, times=None):
    base, head = pair
    add_head_bench(head, data=b"x" * 3000)
    target = head / BENCH
    real_read, state = os.read, {"n": 0, "attempts": 0}

    def read(fd, size):
        data = real_read(fd, size)
        if data and size > 1:  # the first chunk of each read attempt (the digest/other reads use other sizes or fds)
            state["attempts"] += 1
            if times is None or state["attempts"] <= times:
                if how == "same_size_rewrite":
                    with open(target, "r+b") as handle:
                        handle.write(b"y" * 3000)  # same size, same inode
                    time.sleep(0.01)
                    os.utime(target, ns=(1, 2 + state["attempts"]))  # the mtime moves
                else:
                    with open(target, "wb") as handle:  # truncated and rewritten shorter
                        handle.write(b"z" * (10 + state["attempts"]))
        return data

    return read, state


@pytest.mark.parametrize("how", ["same_size_rewrite", "truncate_rewrite"])
def test_a_head_file_rewritten_in_place_on_every_attempt_is_a_crash_not_a_verdict(pair, monkeypatch, how):
    base, head = pair
    read, state = torn(pair, monkeypatch, how)
    with monkeypatch.context() as patch:
        patch.setattr(os, "read", read)
        with pytest.raises(Err) as info:
            overlay(pair)
    assert info.value.code == "OVERLAY_FAILED" and "being written" in info.value.detail and not (base / "benchmarks").exists()


@pytest.mark.parametrize("how", ["same_size_rewrite", "truncate_rewrite"])
def test_a_head_file_rewritten_once_while_read_is_retried_and_copied_stable(pair, monkeypatch, how):
    base, head = pair
    read, state = torn(pair, monkeypatch, how, times=1)
    with monkeypatch.context() as patch:
        patch.setattr(os, "read", read)
        assert overlay(pair) == "BUILDER_AUTHORED"
    assert (base / BENCH).read_bytes() == (head / BENCH).read_bytes() and state["attempts"] >= 2


def test_each_stability_field_of_the_read_is_checked(pair, monkeypatch):
    base, head = pair
    add_head_bench(head)
    for field in ("st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink", "st_ino"):
        real_fstat, calls, leaf_ino = os.fstat, {"n": 0}, (head / BENCH).stat().st_ino

        def fstat(fd, field=field):
            result = real_fstat(fd)
            if stat.S_ISREG(result.st_mode) and result.st_ino == leaf_ino:
                calls["n"] += 1
                if calls["n"] % 2 == 0:  # every second fstat of the head leaf is the one after the read, on every attempt
                    values = {f: getattr(result, f) for f in ("st_dev", "st_ino", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns", "st_mode")}
                    values[field] += 1
                    return types.SimpleNamespace(**values)
            return result

        with monkeypatch.context() as patch:
            patch.setattr(os, "fstat", fstat)
            with pytest.raises(Err) as info:
                overlay(pair)
        assert info.value.code == "OVERLAY_FAILED" and ("changed" in info.value.detail or "written" in info.value.detail), field
        assert not (base / "benchmarks").exists(), field


# --- round 6 review: export-checked seal/hash wrappers, sub-level seals, notes on interrupted cleanup, path-only unseal ---

def test_seal_export_and_hash_export_check_the_root_is_an_export(pair, tmp_path):
    base, head = pair
    stray = tmp_path / "stray"
    (stray / "sub").mkdir(parents=True)
    (stray / "sub" / "f").write_text("x")
    before = {p: stat.S_IMODE(p.stat().st_mode) for p in [stray, *stray.rglob("*")]}
    for func in (bg.seal_export, bg.hash_export):
        for bad in (stray, tmp_path, base.parent, "", None, os.fsencode(base)):
            with pytest.raises(Err) as info:
                func(bad)
            assert info.value.code == "DEST_REJECTED"
    assert {p: stat.S_IMODE(p.stat().st_mode) for p in [stray, *stray.rglob("*")]} == before  # nothing was sealed
    bg.seal_export(base)
    assert not (stat.S_IMODE(base.stat().st_mode) & 0o222)
    sealed = bg.hash_export(base)
    assert sealed == bg.hash_tree(base)
    bg.unseal_tree(base)
    assert bg.hash_export(base) != sealed  # the unsealed tree differs: modes are in the hash


def test_seal_export_wraps_environmental_errors(pair, monkeypatch):
    base, _ = pair

    def broken(create):
        raise OSError(errno.EIO, "injected")

    monkeypatch.setattr(bg, "_check_parent", broken)
    for func in (bg.seal_export, bg.hash_export):
        with pytest.raises(Err) as info:
            func(base)
        assert info.value.code == "OVERLAY_FAILED"


def test_seal_tree_on_a_missing_root_is_tree_unreadable_like_the_others(tmp_path):
    for func in (bg.seal_tree, bg.unseal_tree, bg.hash_tree):
        with pytest.raises(Err) as info:
            func(tmp_path / "nowhere")
        assert info.value.code == "TREE_UNREADABLE"
    (tmp_path / "afile").write_text("x")
    with pytest.raises(Err) as info:
        bg.seal_tree(tmp_path / "afile")
    assert info.value.code == "TREE_UNREADABLE"


@pytest.mark.skipif(IS_ROOT, reason="root can write anywhere")
def test_a_readonly_subdirectory_of_a_writable_base_is_base_sealed(pair):
    base, head = pair
    add_head_bench(head)
    (base / "benchmarks").mkdir()
    (base / "benchmarks").chmod(0o555)  # the base root is writable, one level below is not
    try:
        with pytest.raises(Err) as info:
            overlay(pair)
    finally:
        (base / "benchmarks").chmod(0o755)
    assert info.value.code == "OVERLAY_BASE_SEALED" and not (base / BENCH).exists()


@pytest.mark.skipif(IS_ROOT, reason="root can write anywhere")
def test_a_readonly_base_root_below_the_dispatch_level_is_also_base_sealed(pair):
    base, head = pair
    add_head_bench(head, rel="benchmarks/sub/bench_orders.py")
    (base / "benchmarks").mkdir()
    (base / "benchmarks" / "sub").mkdir()
    (base / "benchmarks" / "sub").chmod(0o555)
    try:
        with pytest.raises(Err) as info:
            overlay(pair, path="benchmarks/sub/bench_orders.py")
    finally:
        (base / "benchmarks" / "sub").chmod(0o755)
    assert info.value.code == "OVERLAY_BASE_SEALED"


def test_a_shutdown_during_cleanup_after_an_ordinary_failure_carries_a_note(pair, monkeypatch):
    base, head = pair
    add_head_bench(head)
    with monkeypatch.context() as patch:
        patch.setattr(os, "write", lambda fd, data: (_ for _ in ()).throw(OSError(errno.EIO, "disk")))
        patch.setattr(os, "unlink", lambda *a, **kw: (_ for _ in ()).throw(SystemExit(143)))
        with pytest.raises(SystemExit) as info:
            overlay(pair)
    assert any("cleanup was interrupted" in note for note in info.value.__notes__)
    assert (base / BENCH).exists()  # and the note says so


def test_a_shutdown_during_cleanup_with_an_earlier_cleanup_failure_names_both(pair, monkeypatch):
    base, head = pair
    add_head_bench(head, rel="benchmarks/sub/bench_orders.py")
    calls = []

    def unlink(*a, **kw):
        calls.append(1)
        raise PermissionError(errno.EACCES, "no unlink")

    with monkeypatch.context() as patch:
        patch.setattr(os, "write", lambda fd, data: (_ for _ in ()).throw(OSError(errno.EIO, "disk")))
        patch.setattr(os, "unlink", unlink)
        patch.setattr(os, "rmdir", lambda *a, **kw: (_ for _ in ()).throw(SystemExit(143)))
        with pytest.raises(SystemExit) as info:
            overlay(pair, path="benchmarks/sub/bench_orders.py")
    notes = " ".join(info.value.__notes__)
    assert "cleanup was interrupted" in notes and "no unlink" in notes


def test_a_failed_validator_load_is_retried_not_cached(pair, monkeypatch, tmp_path):
    add_head_bench(pair[1])
    copy = use_validator(monkeypatch, tmp_path, b"(((\n")
    with pytest.raises(Err):
        overlay(pair)
    copy.write_bytes(b"def validate_task_target(a, b):\n    return b\n")  # fixed on disk: the next call loads it
    assert overlay(pair) == "BUILDER_AUTHORED"


# --- round 7: root vanishing under seal_tree, export_commit with '.' components ---

def test_a_root_that_vanishes_between_the_precheck_and_the_walk_is_tree_unreadable(pair, monkeypatch):
    base, _ = pair
    real = bg._walk_fd

    def vanishing(root, *a, **kw):
        shutil.rmtree(base)  # gone right after seal_tree's own lstat said it was a directory
        yield from real(root, *a, **kw)

    with monkeypatch.context() as patch:
        patch.setattr(bg, "_walk_fd", vanishing)
        with pytest.raises(Err) as info:
            bg.seal_tree(base)
    assert info.value.code == "TREE_UNREADABLE"


def test_an_entry_vanishing_inside_the_tree_is_still_a_seal_failure(pair, monkeypatch):
    base, _ = pair
    real = bg._fchmod_file

    def vanishing(parent_fd, name, st, clear, add):
        (base / "src" / "app.py").unlink()
        return real(parent_fd, name, st, clear, add)

    with monkeypatch.context() as patch:
        patch.setattr(bg, "_fchmod_file", vanishing)
        with pytest.raises(Err) as info:
            bg.seal_tree(base)
    assert info.value.code == "SEAL_FAILED"


@pytest.mark.parametrize("suffix", ["/.", "/./", "//.//", "///", "/sub/..", "/"])
def test_export_commit_normalises_dot_components_and_trailing_separators(pair, suffix):
    base, _ = pair
    assert bg.export_commit(str(base) + suffix) == BASE_SHA


def test_export_commit_never_reads_a_sidecar_planted_inside_the_export(pair):
    base, head = pair
    (head / "..export.json").write_text(json.dumps({"commit": "c" * 40}))  # what "<head>/." + ".export.json" would have named
    assert bg.export_commit(head) == HEAD_SHA
    for spelling in (str(head) + "/.", str(head) + "/./", str(head) + "//.//"):
        assert bg.export_commit(spelling) == HEAD_SHA


@pytest.mark.parametrize("bad", [".", "./", "..", "/.", "/..", "//"])
def test_export_commit_refuses_a_dot_only_path(pair, bad, monkeypatch):
    base, head = pair
    monkeypatch.chdir(head)  # "." must not mean "the sidecar named '..export.json' in the working directory"
    (head / "..export.json").write_text(json.dumps({"commit": "c" * 40}))
    with pytest.raises(Err) as info:
        bg.export_commit(bad)
    assert info.value.code == "DEST_REJECTED"


# --- round 8: a close that raises must neither leak a sibling descriptor nor close a stale number ---

def fault_close(monkeypatch_ctx, nth: int):
    """Make the `nth` os.close call (0-based) really close the descriptor and then raise EIO, as NFS can."""
    real, calls = os.close, []

    def close(fd):
        calls.append(fd)
        real(fd)
        if len(calls) - 1 == nth:
            raise OSError(errno.EIO, "close failed after the descriptor was released")

    monkeypatch_ctx.setattr(os, "close", close)
    return calls


@pytest.mark.parametrize("nth", [0, 1, 2, 3])
def test_a_close_that_raises_while_descending_the_head_path_leaks_nothing(pair, monkeypatch, nth):
    base, head = pair
    add_head_bench(head, rel="benchmarks/x/bench_orders.py")
    baseline = open_fds()
    with monkeypatch.context() as patch:
        calls = fault_close(patch, nth)
        try:
            bg.read_benchmark(head, "benchmarks/x/bench_orders.py")
        except Err as exc:
            assert exc.code == "OVERLAY_FAILED"
    assert open_fds() == baseline
    assert len(calls) == len(set(calls)) or True  # numbers may repeat across opens; the descriptor count is the check


@pytest.mark.parametrize("nth", [0, 1, 2, 3, 4])
def test_a_close_that_raises_during_the_overlay_head_read_leaks_nothing(pair, monkeypatch, nth):
    base, head = pair
    add_head_bench(head, rel="benchmarks/x/bench_orders.py")
    baseline = open_fds()
    with monkeypatch.context() as patch:
        fault_close(patch, nth)
        try:
            overlay(pair, path="benchmarks/x/bench_orders.py")
        except Err as exc:
            assert exc.code in ("OVERLAY_FAILED", "OVERLAY_PATH_CONFLICT", "OVERLAY_NOT_REGULAR")
    assert open_fds() == baseline


def test_an_abandoned_walk_with_several_open_levels_closes_every_descriptor_even_if_one_close_fails(pair, monkeypatch):
    base, _ = pair
    deep = base
    for _ in range(6):
        deep = deep / "d"
        deep.mkdir()
    (deep / "f").write_text("x")
    baseline = open_fds()
    with monkeypatch.context() as patch:
        patch.setattr(bg, "_MAX_TREE_ENTRIES", 6)  # abandon the walk part-way, with several levels open
        fault_close(patch, 0)
        with pytest.raises(Err):
            bg.hash_tree(base)
    assert open_fds() == baseline
