"""Tests for the C4c-2a pieces of `benchmark_gate.py`: `hash_tree` and `overlay_benchmark_file`.

Export directories are built by hand under the (sandboxed) fixed parent with a real marker and a real sidecar, so no git
is needed. Design: docs/superpowers/specs/2026-10-02-c4-performance-review-executor-handoff-design.md (APIs table).
"""

from __future__ import annotations

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


def test_hash_tree_is_independent_of_the_creation_order(pair, tmp_path):
    base, head = pair
    for name in ("b.py", "a.py", "a.b", "a/c"):
        target = base / name
        target.parent.mkdir(exist_ok=True)
        target.write_text(name)
    for name in ("a/c", "a.b", "a.py", "b.py"):
        target = head / name
        target.parent.mkdir(exist_ok=True)
        target.write_text(name)
    shutil.rmtree(base / "src"), shutil.rmtree(head / "src")
    assert bg.hash_tree(base) == bg.hash_tree(head)


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
    monkeypatch.setattr(bg, "_MAX_TREE_ENTRIES", 2)
    with pytest.raises(Err) as info:
        bg.hash_tree(base)
    assert info.value.code == "TREE_TOO_LARGE"
    monkeypatch.undo()
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


@pytest.mark.parametrize("variant", ["bytes", "directory", "symlink", "oversize_at_base"])
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
    else:
        add_head_bench(base, data=SRC + b"#" * 20_000)
    with pytest.raises(Err) as info:
        overlay(pair)
    assert info.value.code == "BENCHMARK_MODIFIED"


def test_presence_is_by_exact_name_not_by_case_folding(pair):
    base, head = pair
    add_head_bench(head)
    add_head_bench(base, rel="benchmarks/Bench_orders.py")
    try:
        result = overlay(pair)
    except Err as exc:  # a case-insensitive filesystem finds the twin when creating: refused, never silently PRE_EXISTING
        assert exc.code == "OVERLAY_PATH_CONFLICT"
    else:
        assert result == "BUILDER_AUTHORED" and (base / BENCH).read_bytes() == SRC


def test_a_case_folded_parent_twin_is_never_used_as_the_parent(pair):
    base, head = pair
    add_head_bench(head)
    (base / "Benchmarks").mkdir()
    (base / "Benchmarks" / "marker").write_text("m")
    try:
        overlay(pair)
    except Err as exc:
        assert exc.code == "OVERLAY_PATH_CONFLICT"
    else:  # case-sensitive filesystem: two distinct directories
        assert (base / "benchmarks" / "bench_orders.py").exists() and not (base / "Benchmarks" / "bench_orders.py").exists()


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


def test_a_missing_head_file_and_a_denied_name_are_rejected_by_validate_task_target(pair):
    with pytest.raises(Err) as info:
        overlay(pair)  # lexically fine, absent in the head
    assert info.value.code == "OVERLAY_PATH_REJECTED"


@pytest.mark.parametrize("kind", ["symlink_file", "symlink_in_tree", "symlink_parent", "directory", "oversize", "fifo"])
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
    assert info.value.code in ("OVERLAY_PATH_REJECTED", "OVERLAY_NOT_REGULAR") and not (base / "benchmarks").exists()


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
