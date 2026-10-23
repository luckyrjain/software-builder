"""Tests for the C4c-2a pieces of `benchmark_gate.py`: `hash_tree` and `overlay_benchmark_file`.

Export directories are built by hand under the (sandboxed) fixed parent with a real marker and a real sidecar, so no git
is needed. Design: docs/superpowers/specs/2026-10-02-c4-performance-review-executor-handoff-design.md (APIs table).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
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
    return root / "base", root / "head"


def add_head_bench(head: Path, rel: str = BENCH, data: bytes = SRC) -> None:
    (head / rel).parent.mkdir(parents=True, exist_ok=True)
    (head / rel).write_bytes(data)


def overlay(pair_, path: str = BENCH, commit: str = BASE_SHA) -> str:
    return bg.overlay_benchmark_file(pair_[0], pair_[1], commit, path)


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


def hide_names(monkeypatch, *hidden: str) -> None:
    """Make `os.listdir` of a directory descriptor omit `hidden`: the exact-name lookup then believes the entry is absent, as it
    does for a case-folded twin on a case-insensitive filesystem. Deterministic on every platform."""
    real = os.listdir

    def listdir(path="."):
        names = real(path)
        return [n for n in names if n not in hidden] if isinstance(path, int) else names

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
    hide_names(monkeypatch, "bench_orders.py")
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_PATH_CONFLICT" and (base / BENCH).read_bytes() == b"different bytes\n"  # O_EXCL, not O_TRUNC


def test_a_parent_hidden_from_the_listing_is_refused_and_nothing_is_created_below_it(pair, monkeypatch):
    base, head = pair
    add_head_bench(head)
    (base / "benchmarks").mkdir()
    hide_names(monkeypatch, "benchmarks")
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
    assert overlay(pair, commit="d" * 64) == "BUILDER_AUTHORED"


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
    exact = {"symlink_in_tree": "OVERLAY_NOT_REGULAR", "symlink_parent_in_tree": "OVERLAY_NOT_REGULAR"}
    assert info.value.code == exact.get(kind, info.value.code) and info.value.code in ("OVERLAY_PATH_REJECTED", "OVERLAY_NOT_REGULAR")
    assert not (base / "benchmarks").exists() or kind == "symlink_parent_in_tree"


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
            bg.overlay_benchmark_file(roots[0], roots[1], BASE_SHA, BENCH)
        assert info.value.code == "DEST_REJECTED"
    link = base.parent / "linked"
    link.symlink_to(head)
    with pytest.raises(Err) as info:
        bg.overlay_benchmark_file(base, link, BASE_SHA, BENCH)
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


@pytest.mark.skipif(IS_ROOT, reason="root can write anywhere")
def test_an_unwritable_base_is_overlay_failed(pair):
    base, head = pair
    add_head_bench(head)
    bg.seal_tree(base)
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_FAILED"
    bg.unseal_tree(base)


def test_the_overlay_validator_is_the_shared_one_and_a_missing_file_fails_closed(pair, monkeypatch):
    add_head_bench(pair[1])
    monkeypatch.setattr(bg, "_task_target_module", None)
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
    return len(os.listdir("/dev/fd"))


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
            bg.overlay_benchmark_file(*args)
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
        monkeypatch.setattr(bg, "_task_target_module", None)
        monkeypatch.setattr(bg, "_task_target_path", lambda: bad)
        with pytest.raises(Err) as info:
            overlay(pair)
        assert info.value.code == "OVERLAY_FAILED"
    bad.unlink()
    monkeypatch.setattr(bg, "_task_target_module", None)
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "OVERLAY_FAILED"
    if not IS_ROOT:
        bad.write_text("def validate_task_target(a, b):\n    return b\n")
        bad.chmod(0)
        monkeypatch.setattr(bg, "_task_target_module", None)
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
    monkeypatch.setattr(bg, "_task_target_module", None)
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
        bg.overlay_benchmark_file(roots[0], roots[1], BASE_SHA, path)
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
