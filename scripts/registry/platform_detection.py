"""Purely syntactic, AST-based detector for a skill's platform support (gap-backlog F2).

See docs/superpowers/specs/2026-09-27-f2-platform-support-design.md (revision 4, all 4 review
rounds) for the full history of why this detector is shaped exactly this way. The short version:

- **Purely syntactic, not behavioral.** A module-top-level `import fcntl` (bare, or inside a
  `try`/`except` of any shape) counts as POSIX-only evidence. The only exemption is an explicit
  `if sys.platform == ...: import X else: import Y` branch, which counts as a genuine functional
  fallback and suppresses POSIX-only classification for the import(s) it guards -- regardless of
  what the `try`/`except` handler actually does (round 2 rejected a "content-sensitive" reading:
  a real, working `except ImportError: import msvcrt as fcntl` fallback is still classified
  POSIX-only, a deliberate, disclosed, safe-direction trade-off that can over-restrict but never
  under-restrict).
- **Module-top-level only.** Both the if/else exemption and the try/except non-exemption apply
  only to an import statement sitting directly in the module's top-level statement list (or
  directly inside a top-level `try`'s own body). An import nested inside a function, class, or
  any other conditional produces no evidence either way -- this detector never walks into nested
  scopes.
- **Per-file failure isolation, not skill-wide abort.** `derive_platforms` parses every `.py` file
  under a skill's `scripts/` tree independently. A file that fails to parse (a mid-edit syntax
  error, a bad encoding, an embedded NUL byte -- CPython raises `ValueError`, not `SyntaxError`,
  for the last one) contributes zero evidence for that one file only; it never aborts the scan of
  the skill's other files, and it never affects another skill's resolution at all (each skill's
  directory is scanned in total isolation). The permissive default (`["posix", "windows"]`) is
  used only if literally no file in the skill contributed any evidence.
- **Scope: the skill's `scripts/` tree, not its whole directory.** Matches the design's own
  Capacity section (27 `.py` files across all ~50 skills today, confirmed by direct count --
  exactly the `scripts/` subdirectory count, not the much larger whole-skill-tree count that
  would include tests/templates/reference material). Test/template/reference `.py` files are not
  what actually runs at install/execution time and are deliberately out of scope.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# The list of "platforms" values this repository recognizes -- shared with schema.py's
# schema-validation for an explicit `platforms:` override (same enum-checked-list precedent as
# ALLOWED_RISK_CLASSES/_parse_risk_class).
ALLOWED_PLATFORMS = frozenset({"posix", "windows"})

# The failure-closed default: used when a skill's scripts/ tree contributes no evidence at all
# (no scripts/ directory, an empty one, or every file in it failed to parse) -- never when only
# SOME files failed to parse but others still contributed real evidence (see module docstring).
PERMISSIVE_DEFAULT: tuple[str, ...] = ("posix", "windows")
POSIX_ONLY: tuple[str, ...] = ("posix",)

# Stdlib modules that only exist / only function on POSIX. Deliberately narrow and stdlib-only
# (matching the change-impact report's "no new PyPI dependency" line) -- a POSIX-only third-party
# package is out of scope for this purely syntactic detector, same disclosed limitation as any
# other known-module-list heuristic (see design doc's Failure strategy table).
_POSIX_ONLY_MODULES = frozenset(
    {
        "fcntl",
        "termios",
        "tty",
        "pty",
        "pwd",
        "grp",
        "posix",
        "resource",
        "syslog",
        "crypt",
        "nis",
        "spwd",
    }
)


def _module_root(name: str) -> str:
    """The top-level package name of a dotted import target (`"fcntl.foo"` -> `"fcntl"`)."""
    return name.split(".", 1)[0]


def _names_from_import(node: ast.Import) -> set[str]:
    return {_module_root(alias.name) for alias in node.names}


def _names_from_import_from(node: ast.ImportFrom) -> set[str]:
    # `node.level > 0` (`from . import x`) or `node.module is None` is a relative import -- never
    # a stdlib module by construction, so it never contributes evidence either way.
    if node.level or node.module is None:
        return set()
    return {_module_root(node.module)}


def _is_sys_platform_attr(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "platform"
        and isinstance(node.value, ast.Name)
        and node.value.id == "sys"
    )


def _is_sys_platform_if_else(node: ast.If) -> bool:
    """True for `if sys.platform == <something>: ... else: ...` (an `elif` counts as an `else`
    for this purpose -- it still appears in `node.orelse`). Purely syntactic: only the test's
    *shape* is checked (a single `==` comparison naming `sys.platform` on either side), and an
    else/elif branch must be present -- nothing about either branch's content is inspected.
    """
    if not node.orelse:
        return False
    test = node.test
    if not (isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq)):
        return False
    operands = [test.left, *test.comparators]
    return any(_is_sys_platform_attr(operand) for operand in operands)


def _posix_only_names(stmt: ast.stmt) -> set[str]:
    if isinstance(stmt, ast.Import):
        return _names_from_import(stmt) & _POSIX_ONLY_MODULES
    if isinstance(stmt, ast.ImportFrom):
        return _names_from_import_from(stmt) & _POSIX_ONLY_MODULES
    return set()


def _module_has_posix_only_evidence(tree: ast.Module) -> bool:
    """Scan exactly one module's top-level statement list (see module docstring: this never
    recurses into a function/class/conditional body other than the two special-cased shapes
    below, both of which are themselves module-top-level constructs)."""
    for stmt in tree.body:
        if _posix_only_names(stmt):
            return True
        if isinstance(stmt, ast.Try):
            # ANY try/except shape at module top level still counts as POSIX-only evidence for
            # whatever its `try:` body imports, regardless of what the handler(s) do -- the
            # purely-syntactic rule round 2 committed to. Only the try body's own direct
            # statements are scanned; a nested if/try inside it is out of scope, same as anywhere
            # else below module top level.
            for inner in stmt.body:
                if _posix_only_names(inner):
                    return True
        elif isinstance(stmt, ast.If) and _is_sys_platform_if_else(stmt):
            # The one exemption: a genuine sys.platform-guarded if/else. Neither branch's
            # imports contribute evidence, regardless of which stdlib module either names.
            continue
        # Every other top-level shape (a plain `if` unrelated to sys.platform, a function/class
        # definition, ...) is left alone -- an import nested inside it is guarded at a nesting
        # level other than module-top-level and produces no evidence either way.
    return False


def _iter_script_files(skill_path: Path) -> list[Path]:
    scripts_dir = skill_path / "scripts"
    if not scripts_dir.is_dir():
        return []
    return sorted(scripts_dir.rglob("*.py"))


def derive_platforms(skill_path: Path) -> list[str]:
    """Derive one skill's `platforms` value from its `scripts/` tree's actual import shape.

    Each `.py` file under `skill_path / "scripts"` is parsed and scanned *independently* --
    a parse failure in one file (`SyntaxError`, `UnicodeDecodeError`, `OSError`, or `ValueError`
    -- the last for CPython's embedded-NUL-byte quirk in `ast.parse()`/`compile()`) contributes
    zero evidence for that one file only, with a loud warning on stderr, and never aborts the
    scan of the skill's other files. A parse failure in one skill's files never affects another
    skill's resolution at all -- this function only ever looks at `skill_path`'s own tree.

    Returns `["posix"]` if any file contributed POSIX-only evidence; `["posix", "windows"]`
    (the permissive default) only if literally no file in the skill's `scripts/` tree contributed
    any evidence at all (no such directory, an empty one, or every file failed to parse).
    """
    found_posix_only_evidence = False
    for path in _iter_script_files(skill_path):
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (SyntaxError, UnicodeDecodeError, OSError, ValueError) as exc:
            print(
                f"warning: platform_detection: could not parse {path}: {exc} "
                "-- this file contributes no platform evidence (its skill's other files are "
                "still scanned normally)",
                file=sys.stderr,
            )
            continue
        if _module_has_posix_only_evidence(tree):
            found_posix_only_evidence = True
    return list(POSIX_ONLY) if found_posix_only_evidence else list(PERMISSIVE_DEFAULT)
