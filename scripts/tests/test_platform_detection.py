"""Tests for scripts/registry/platform_detection.py (gap-backlog F2).

Each test here is a concrete regression case for one specific bug the design doc's 4 rounds of
adversarial review found and fixed -- see docs/superpowers/specs/2026-09-27-f2-platform-support-
design.md's Revision history for why each of these exists.
"""

from __future__ import annotations

from pathlib import Path

from scripts.registry.platform_detection import ALLOWED_PLATFORMS, derive_platforms

REAL_ROOT = Path(__file__).resolve().parents[2]


def _write_script(skill_dir: Path, name: str, source: str) -> Path:
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    path = scripts_dir / name
    path.write_text(source, encoding="utf-8")
    return path


def test_no_scripts_directory_defaults_permissive(tmp_path: Path) -> None:
    skill_dir = tmp_path / "no-scripts"
    skill_dir.mkdir()
    assert derive_platforms(skill_dir) == ["posix", "windows"]


def test_missing_skill_directory_defaults_permissive(tmp_path: Path) -> None:
    assert derive_platforms(tmp_path / "does-not-exist") == ["posix", "windows"]


def test_empty_scripts_directory_defaults_permissive(tmp_path: Path) -> None:
    skill_dir = tmp_path / "empty-scripts"
    (skill_dir / "scripts").mkdir(parents=True)
    assert derive_platforms(skill_dir) == ["posix", "windows"]


def test_cross_platform_stdlib_import_does_not_count(tmp_path: Path) -> None:
    skill_dir = tmp_path / "cross-platform"
    _write_script(skill_dir, "run.py", "import os\nimport sys\nimport json\n")
    assert derive_platforms(skill_dir) == ["posix", "windows"]


def test_bare_module_top_level_posix_only_import_counts_as_evidence(tmp_path: Path) -> None:
    skill_dir = tmp_path / "bare-fcntl"
    _write_script(skill_dir, "lock.py", "import fcntl\n")
    assert derive_platforms(skill_dir) == ["posix"]


def test_from_import_of_posix_only_module_counts_as_evidence(tmp_path: Path) -> None:
    skill_dir = tmp_path / "from-import"
    _write_script(skill_dir, "lock.py", "from fcntl import flock\n")
    assert derive_platforms(skill_dir) == ["posix"]


def test_try_except_import_error_counts_as_posix_only_regardless_of_handler_content(
    tmp_path: Path,
) -> None:
    """Round 2's committed, purely-syntactic reading: ANY try/except ImportError shape at module
    top level counts as POSIX-only evidence, even a real, working fallback like
    `except ImportError: import msvcrt as fcntl` -- a deliberate, disclosed, safe-direction
    trade-off (can over-restrict, never under-restrict). This is the regression test for the
    ambiguity round 2 found and closed; it must NOT be "fixed" to read handler content."""
    skill_dir = tmp_path / "try-except-working-fallback"
    _write_script(
        skill_dir,
        "lock.py",
        "try:\n    import fcntl\nexcept ImportError:\n    import msvcrt as fcntl\n",
    )
    assert derive_platforms(skill_dir) == ["posix"]


def test_try_except_import_error_with_none_fallback_still_counts_as_evidence(
    tmp_path: Path,
) -> None:
    skill_dir = tmp_path / "try-except-none-fallback"
    _write_script(
        skill_dir,
        "lock.py",
        "try:\n    import fcntl\nexcept ImportError:\n    fcntl = None\n",
    )
    assert derive_platforms(skill_dir) == ["posix"]


def test_sys_platform_if_else_is_a_functional_fallback_and_does_not_count(tmp_path: Path) -> None:
    """The one exemption: an explicit `if sys.platform == ...: ... else: ...` branch -- neither
    branch's imports count as evidence, regardless of which stdlib module either names."""
    skill_dir = tmp_path / "if-else-fallback"
    _write_script(
        skill_dir,
        "lock.py",
        "import sys\n"
        "if sys.platform == 'win32':\n"
        "    import msvcrt as fcntl\n"
        "else:\n"
        "    import fcntl\n",
    )
    assert derive_platforms(skill_dir) == ["posix", "windows"]


def test_sys_platform_if_without_else_is_not_exempt(tmp_path: Path) -> None:
    """No else/elif branch: this isn't the functional-fallback shape (round 2's committed rule
    requires an else), so it's just a plain top-level `if` -- the import inside it is nested,
    produces no evidence either way (out of scope), same as any other conditional body."""
    skill_dir = tmp_path / "if-no-else"
    _write_script(
        skill_dir,
        "lock.py",
        "import sys\nif sys.platform == 'win32':\n    import fcntl\n",
    )
    assert derive_platforms(skill_dir) == ["posix", "windows"]


def test_import_nested_in_function_body_produces_no_evidence(tmp_path: Path) -> None:
    """Module-top-level-only scope: an import guarded at any other nesting level (function,
    class, conditional body) produces no evidence either way -- this detector never walks into
    nested scopes."""
    skill_dir = tmp_path / "nested-in-function"
    _write_script(
        skill_dir,
        "lock.py",
        "def maybe_lock():\n    import fcntl\n    return fcntl\n",
    )
    assert derive_platforms(skill_dir) == ["posix", "windows"]


def test_import_nested_in_class_body_produces_no_evidence(tmp_path: Path) -> None:
    skill_dir = tmp_path / "nested-in-class"
    _write_script(
        skill_dir,
        "lock.py",
        "class Locker:\n    import fcntl\n",
    )
    assert derive_platforms(skill_dir) == ["posix", "windows"]


def test_mixed_file_same_skill_aggregation(tmp_path: Path) -> None:
    """The concrete regression test for round 3's aggregation-semantics fix: one file has real
    unconditional POSIX-only evidence, a sibling file in the same skill has a syntax error --
    the skill must still classify ["posix"], not fall back to the permissive default. A
    skill-wide try/except around the whole per-skill file loop (the previously-ambiguous, unsafe
    reading) would incorrectly discard the first file's real evidence."""
    skill_dir = tmp_path / "mixed-skill"
    _write_script(skill_dir, "good.py", "import fcntl\n")
    _write_script(skill_dir, "broken.py", "def broken(:\n    pass\n")
    assert derive_platforms(skill_dir) == ["posix"]


def test_mixed_file_aggregation_is_order_independent(tmp_path: Path) -> None:
    skill_dir = tmp_path / "mixed-skill-reverse-order"
    _write_script(skill_dir, "aaa_broken.py", "def broken(:\n    pass\n")
    _write_script(skill_dir, "zzz_good.py", "import fcntl\n")
    assert derive_platforms(skill_dir) == ["posix"]


def test_all_files_fail_to_parse_defaults_permissive(tmp_path: Path) -> None:
    skill_dir = tmp_path / "all-broken"
    _write_script(skill_dir, "broken1.py", "def broken(:\n    pass\n")
    _write_script(skill_dir, "broken2.py", "def also_broken(:\n    pass\n")
    assert derive_platforms(skill_dir) == ["posix", "windows"]


def test_cross_skill_isolation_malformed_file_does_not_affect_sibling_skill(tmp_path: Path) -> None:
    """The concrete regression test for the repo-wide-crash bug this design's own review process
    found and fixed: one skill's malformed .py file must never crash, or leak into, another
    skill's classification -- each skill's directory is scanned in total isolation."""
    broken_skill = tmp_path / "broken-skill"
    _write_script(broken_skill, "broken.py", "def broken(:\n    pass\n")

    clean_skill = tmp_path / "clean-skill"
    _write_script(clean_skill, "clean.py", "import fcntl\n")

    # Neither call raises, and neither skill's result is contaminated by the other's content.
    assert derive_platforms(broken_skill) == ["posix", "windows"]
    assert derive_platforms(clean_skill) == ["posix"]


def test_nul_byte_fixture_raises_value_error_internally_but_is_caught(tmp_path: Path) -> None:
    """CPython's ast.parse()/compile() raises ValueError (not SyntaxError) for source text
    containing an embedded NUL byte -- a real, confirmed quirk round 3 found missing from the
    exception set. Must be caught, contribute no evidence, and never crash the scan of the
    skill's other files."""
    skill_dir = tmp_path / "nul-byte-skill"
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "nul.py").write_bytes(b"import os\n\x00\n")
    (scripts_dir / "good.py").write_text("import fcntl\n", encoding="utf-8")

    # The NUL-byte file contributes no evidence, but the sibling file's real evidence survives.
    assert derive_platforms(skill_dir) == ["posix"]


def test_nul_byte_only_file_defaults_permissive(tmp_path: Path) -> None:
    skill_dir = tmp_path / "nul-byte-only"
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "nul.py").write_bytes(b"import os\n\x00\n")
    assert derive_platforms(skill_dir) == ["posix", "windows"]


def test_unreadable_encoding_is_caught_and_contributes_no_evidence(tmp_path: Path) -> None:
    skill_dir = tmp_path / "bad-encoding"
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    # Invalid UTF-8 byte sequence -- read_text(encoding="utf-8") raises UnicodeDecodeError.
    (scripts_dir / "bad.py").write_bytes(b"import os\n\xff\xfe\n")
    assert derive_platforms(skill_dir) == ["posix", "windows"]


def test_scans_scripts_subdirectory_recursively(tmp_path: Path) -> None:
    skill_dir = tmp_path / "nested-scripts-dir"
    nested = skill_dir / "scripts" / "helpers"
    nested.mkdir(parents=True)
    (nested / "lock.py").write_text("import fcntl\n", encoding="utf-8")
    assert derive_platforms(skill_dir) == ["posix"]


def test_files_outside_scripts_directory_are_not_scanned(tmp_path: Path) -> None:
    """Scope is the skill's scripts/ tree specifically (matching the design's own Capacity
    section: 27 .py files across ~50 skills today, exactly the scripts/ subdirectory count) --
    not its whole directory, so test/template/reference .py files are out of scope."""
    skill_dir = tmp_path / "outside-scripts"
    (skill_dir / "tests").mkdir(parents=True)
    (skill_dir / "tests" / "test_something.py").write_text("import fcntl\n", encoding="utf-8")
    assert derive_platforms(skill_dir) == ["posix", "windows"]


def test_allowed_platforms_is_exactly_posix_and_windows() -> None:
    assert ALLOWED_PLATFORMS == {"posix", "windows"}


# --- Real-repo regression: the two skills this ticket names must classify correctly from the
# auto-detector alone, independent of their hand-authored `platforms:` overrides (design doc's
# Phase 0 gating requirement -- the override is defense-in-depth, not load-bearing correctness).


def test_pr_gatekeeper_derives_posix_only_from_the_real_repo() -> None:
    assert derive_platforms(REAL_ROOT / "skills" / "pr-gatekeeper") == ["posix"]


def test_migration_program_manager_derives_posix_only_from_the_real_repo() -> None:
    assert derive_platforms(REAL_ROOT / "skills" / "migration-program-manager") == ["posix"]
