#!/usr/bin/env python3
"""Validation, lint and statistics core of the performance-review -> loop-task-implementer benchmark gate (Epic C).

**This module is not wired into anything yet.** It is delivered by a series of six PRs for gap-backlog ticket
C4 (C4a core, C4b lint, C4c exports, C4d harness, C4e classifier/docs, C4f wiring); no workflow file,
lifecycle validator or other script calls it until C4f, and the ``lint`` subcommand added by C4b is called by
nothing until C4d/C4e/C4f. So far it holds only the pure, string-level and arithmetic pieces plus the
``validate`` and ``lint`` CLIs. Specification (revision 5, the converged result of four review
rounds): ``docs/superpowers/specs/2026-10-02-c4-performance-review-executor-handoff-design.md`` (APIs table,
Data model, Capacity, Threat model). This docstring states each function's own contract and the reason each
rule exists; it does not re-derive the design.

Threat model, in one paragraph: the gate resists accidental, lazy and moderately clever gaming and makes
honest wins measurable. It does not make a measurement trustworthy against a Builder whose code executes
under the harness; for that class the control is a human reading the fix and the benchmark. Everything here
fails closed: any malformed input yields a rejection code or ``INCONCLUSIVE``, never a pass.

Standard library only. The skill is packaged with ``scripts/`` shipped wholesale and cannot import
repo-root packages, and nothing platform-specific happens at import time (Windows-safe).
"""

from __future__ import annotations

import argparse
import ast
import codecs
import hashlib
import io
import json
import math
import os
import posixpath
import re
import stat
import sys
import tokenize
from fractions import Fraction
from pathlib import Path

# ---------------------------------------------------------------------------
# benchmark_symbol_from_location
# ---------------------------------------------------------------------------

# ``re.ASCII``: without it ``\d`` also matches Arabic-Indic and other Unicode digits, so such a tail would strip.
_LINE_TAIL_RE = re.compile(r"(?::\d+(?::\d+)?|#L\d+| L\d+)\Z", re.ASCII)
_SYMBOL_RE = re.compile(r"[A-Za-z_]\w*", re.ASCII)
_SYMBOL_DENYLIST = frozenset(
    {"print", "hashlib", "sha256", "main", "data", "sort", "load", "list", "item", "time", "test", "bench", "run", "get", "set"}
)
_SYMBOL_BAD_NAMES = frozenset({"__init__", "__main__"})
# A bare ``a.b`` with no ``/`` is ambiguous between a dotted symbol (``OrderService.list_orders``) and a file
# (``orders.js``); only these extensions are treated as files in that ambiguous case. With a ``/`` any
# extension means a file.
_KNOWN_FILE_EXTENSIONS = frozenset(
    {"js", "jsx", "ts", "tsx", "pyi", "pyc", "pyw", "pyx", "pxd", "go", "rs", "java", "kt", "rb", "php", "c", "h",
     "cc", "cpp", "cs", "scala", "swift", "lua", "dart", "sql", "sh", "md", "json", "yaml", "yml", "toml", "txt",
     "html", "css"}
)


def _valid_symbol(name: object) -> bool:
    """True iff ``name`` is an ASCII identifier of 3 to 64 characters that the lint's own required elements
    or trivial builtins could not satisfy by accident. ``fullmatch`` (not ``$``) so a trailing newline fails.
    Replaces revision 3's 4-character rule, which excluded real symbols (``fib``, ``api``) yet admitted ``main``."""
    return (
        isinstance(name, str)
        and _SYMBOL_RE.fullmatch(name) is not None
        and 3 <= len(name) <= 64
        and name not in _SYMBOL_BAD_NAMES
        and name not in _SYMBOL_DENYLIST
    )


def benchmark_symbol_from_location(location: object) -> str | None:
    """Derive the symbol the benchmark must reference from a finding's ``Location``, or ``None``.

    Steps (design APIs table): strip one surrounding backtick pair; strip one trailing ``:N``, ``:N:M``,
    ``#LN`` or `` LN``; strip a trailing ``()``; if ``::`` is present take the part after the last ``::`` and
    then its last dotted component (``app/orders.py::OrderService.list_orders`` -> ``list_orders``); else a
    ``.py`` Location is file-level and yields the module stem; else the last dotted component. A Location
    naming any other file extension (``.ts``, ``.js``, ``.pyi``, ``.PY``) is ``None``: the gate is
    Python-only and this is where that is enforced. The result must pass ``_valid_symbol``.

    Known limit, by design: a bare ``name.ext`` with no ``/`` and no ``::`` is indistinguishable from a dotted
    symbol (``OrderService.list_orders``), so only the extensions in ``_KNOWN_FILE_EXTENSIONS`` make it a file
    (``None``); any other bare ``name.ext`` (``orders.rake``) is read as a dotted symbol and yields ``ext``.
    With a ``/`` or ``::`` every non-``.py`` extension is a file.

    No ``.strip()`` anywhere, and the tail regex ends in ``\\Z`` (``$`` would match before a trailing
    newline): a trailing newline must make the result fail, not be silently repaired.
    """
    if not isinstance(location, str):
        return None
    text = location
    if len(text) >= 2 and text[0] == "`" and text[-1] == "`":
        text = text[1:-1]
    text = _LINE_TAIL_RE.sub("", text, count=1)
    if text.endswith("()"):
        text = text[:-2]

    if "::" in text:
        head, _, tail = text.rpartition("::")
        head_base = head.rsplit("/", 1)[-1]
        if "." in head_base and head_base.rpartition(".")[2] != "py":
            return None
        name = tail.rsplit(".", 1)[-1]
    else:
        base = text.rsplit("/", 1)[-1]
        if text.endswith(".py"):
            name = base[:-3]
        elif "." in base and ("/" in text or base.rpartition(".")[2].casefold() in _KNOWN_FILE_EXTENSIONS):
            return None
        else:
            name = base.rsplit(".", 1)[-1]
    return name if _valid_symbol(name) else None


# ---------------------------------------------------------------------------
# validate_benchmark_command
# ---------------------------------------------------------------------------

# --- Layer 1: byte-identical COPY of B3's validate_repro_command -----------------------------------------------
# Source: skills/bug-diagnosis/tests/test_repro_command_validation.py (the only copy in the repo; nothing under
# scripts/ imports it and packaging ships no sibling skill). Do not edit: a parity test in
# tests/test_benchmark_gate_core.py asserts equal patterns, flags and behaviour, so drift fails CI. Any change
# belongs in B3 first, with a fresh adversarial review.
_REPRO_COMMAND_BASE = re.compile(
    r"^(pytest|python3 -m pytest|make [\w-]+|npm test|npm run [\w:-]+)((?: [\w./:=-]+)*)$"
)
_DANGEROUS_PATH_MARKER = re.compile(r"[\s=:-]/|\.\.")


def validate_repro_command(command: str | None) -> str | None:
    """Return the command if it matches a known, safe test-runner invocation shape with no
    absolute-path or traversal content anywhere; else None.

    Closes: shell metacharacters/chaining/substitution/redirection (round 1); absolute-path
    arguments and ".." traversal, closed via a single delimiter-agnostic substring search rather
    than delimiter-specific splitting (rounds 3-5 each found a distinct delimiter shape -- bare,
    "=", multi-"=", pytest-cov's "TYPE:DEST" colon syntax -- slip past a splitting-based check;
    this version doesn't split at all, so no delimiter syntax needs to be individually enumerated).

    "..": rejected as a literal substring anywhere in the command, not just as an isolated path
    segment -- deliberately broader than strictly necessary (a value like "1..2" would also be
    rejected) because the allowed character class is narrow enough (test-runner invocations only)
    that this is not expected to reject any legitimate repro command, and over-rejection fails
    safe into Condition 3's existing "not automatable" fallback, never into executing something
    dangerous.

    Does NOT and cannot close: a syntactically clean, dangerous-substring-free, relative-path-only
    command still executes whatever the test runner's own extensibility points define at the
    checked-out commit (conftest.py collection, a Makefile recipe body, npm lifecycle hooks). No
    command-shape validator can constrain what a test runner itself chooses to execute; only
    execution-environment sandboxing could, and this design does not add that (accepted residual
    risk, Open questions).
    """
    if command is None:
        return None
    if not _REPRO_COMMAND_BASE.fullmatch(command):
        return None
    if _DANGEROUS_PATH_MARKER.search(command):
        return None
    return command


# --- Layer 2: strictly narrower --------------------------------------------------------------------------------
_ALLOWED_OPTIONS = frozenset({"-q", "--no-header"})
_TEST_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def validate_benchmark_command(command: object, benchmark_path: object) -> tuple[str | None, str]:
    """Return ``(command, "OK")`` or ``(None, "COMMAND_REJECTED")``.

    Layer 1 is B3's validator (above). Layer 2 is narrower because B3 admits ``make``, ``npm`` and arbitrary
    options (``pytest -p x`` loads a plugin; ``pytest -q -rA/benchmarks/x.py`` hides a path inside an option
    argument). Layer 2 requires: first tokens ``pytest`` or ``python3 -m pytest``; every ``-``-prefixed token
    classified as an option BEFORE it is compared with the path, and only ``-q`` and ``--no-header`` allowed;
    exactly one positional, equal to ``benchmark_path`` or ``benchmark_path::<identifier>`` with the
    identifier ASCII (Layer 1's ``\\w`` is Unicode, so a Cyrillic homoglyph passes Layer 1 and is rejected
    here by literal ASCII equality); no ``=``. The command string is only the handoff record: the harness
    builds its own argv from the gate and never executes it as written.
    """
    if not isinstance(command, str) or not isinstance(benchmark_path, str):
        return None, "COMMAND_REJECTED"
    if not command.isascii() or not benchmark_path.isascii() or not benchmark_path:
        return None, "COMMAND_REJECTED"
    if validate_repro_command(command) is None:
        return None, "COMMAND_REJECTED"

    tokens = command.split(" ")
    if tokens[:3] == ["python3", "-m", "pytest"]:
        rest = tokens[3:]
    elif tokens[0] == "pytest":
        rest = tokens[1:]
    else:
        return None, "COMMAND_REJECTED"

    positionals = []
    for token in rest:
        if token.startswith("-"):
            if token not in _ALLOWED_OPTIONS:
                return None, "COMMAND_REJECTED"
        else:
            positionals.append(token)
    if len(positionals) != 1:
        return None, "COMMAND_REJECTED"
    target = positionals[0]
    if "=" in target:
        return None, "COMMAND_REJECTED"
    if target != benchmark_path:
        prefix = benchmark_path + "::"
        if not target.startswith(prefix) or _TEST_IDENTIFIER_RE.fullmatch(target[len(prefix):]) is None:
            return None, "COMMAND_REJECTED"
    return command, "OK"


# ---------------------------------------------------------------------------
# validate_benchmark_gate
# ---------------------------------------------------------------------------

_REQUIRED_KEYS = ("command", "benchmark_paths", "benchmark_symbol")
_DEFAULTS = {
    "warmup_runs": 1,
    "repeats": 6,
    "per_run_timeout_seconds": 80,
    "min_improvement": 0.10,
    "max_noise": 0.10,
}
_ALLOWED_KEYS = frozenset(_REQUIRED_KEYS) | frozenset(_DEFAULTS)
_REPEATS_ALLOWED = (4, 6, 8)
_BUDGET_CAP_SECONDS = 1800

_MAX_PATH_CHARS = 200
_PATH_COMPONENT_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*")
_BENCH_BASENAME_RE = re.compile(r"(test_)?[A-Za-z0-9_]*bench[A-Za-z0-9_]*\.py")
_BENCH_DIRECTORIES = frozenset({"benchmarks", "bench", "perf", "performance"})

# Deny sets aligned with validate_task_target.py as of origin/main (hardened by #332 after the design was
# written); a test compares them with that module so they cannot drift silently.
_DENIED_COMPONENTS = frozenset({".git", ".ssh", ".aws"})
_DENIED_NAMES_EXACT = frozenset({".netrc", ".npmrc", ".htpasswd", ".pgpass"})
_DENIED_NAME_PREFIXES = (
    ".env", "credentials", "kubeconfig", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
)
_DENIED_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".p8", ".jks", ".tfvars")


def _benchmark_path_ok(path: str) -> bool:
    """Lexical path rules, no filesystem: repo-relative, ASCII, at most 200 characters, ends in ``.py``,
    equals its own ``posixpath.normpath``, no ``..``/backslash/NUL/absolute prefix, every component
    ``[A-Za-z0-9_][A-Za-z0-9_.-]*``, no casefolded component on the deny list (a macOS filesystem is
    case-insensitive), a basename that looks like a benchmark, and a benchmark-ish directory component."""
    if not path.isascii() or len(path) > _MAX_PATH_CHARS or not path.endswith(".py"):
        return False
    if path.startswith("/") or "\\" in path or "\0" in path:
        return False
    if posixpath.normpath(path) != path:
        return False
    parts = path.split("/")
    if ".." in parts or any(_PATH_COMPONENT_RE.fullmatch(part) is None for part in parts):
        return False
    for part in parts:
        folded = part.casefold()
        if (
            folded in _DENIED_COMPONENTS
            or folded in _DENIED_NAMES_EXACT
            or folded.startswith(_DENIED_NAME_PREFIXES)
            or folded.endswith(_DENIED_SUFFIXES)
        ):
            return False
    if _BENCH_BASENAME_RE.fullmatch(parts[-1]) is None:
        return False
    return any(directory in _BENCH_DIRECTORIES for directory in parts[:-1])


def _is_real_int(value: object) -> bool:
    """``bool`` is a subclass of ``int`` and ``True`` must not pass as ``1``; exact-type check also drops
    int subclasses."""
    return type(value) is int


def _real_number_fraction(value: object) -> Fraction | None:
    """``Fraction(str(x))`` for a finite real ``float``, ``Fraction(x)`` for an ``int``; else ``None``.

    ``bool``, ``str``, ``Decimal`` and ``Fraction`` are rejected EXPLICITLY (by exact type) because
    ``Fraction(str(x))`` would otherwise accept every one of them. ``str(float)`` is used rather than
    ``Fraction(0.10)``, which is the binary value and is greater than 1/10 (revision 3 prototype). An ``int``
    goes in directly: ``str(int)`` raises ``ValueError`` above 4300 digits, and a huge int must reach the bounds
    check (``BOUNDS_REJECTED`` / ``INVALID_INPUT``), not raise."""
    if type(value) is int:
        return Fraction(value)
    if type(value) is not float or not math.isfinite(value):
        return None
    return Fraction(str(value))


def validate_benchmark_gate(gate: object) -> tuple[dict | None, str]:
    """Lexical validation of ``specialist_inputs.benchmark_gate``; no filesystem.

    Returns ``(normalized, "OK")`` with every default filled in, or ``(None, <code>)``. Codes:
    ``GATE_MISSING`` (absent, ``None`` or not a dict), ``KEY_MISSING`` (checked first), ``KEY_UNKNOWN``,
    then ``TYPE_REJECTED`` for a wrong Python type in any field (including ``bool``/``str``/``Decimal``/
    ``Fraction`` where a number is required), ``PATH_REJECTED`` (also for a ``benchmark_paths`` list whose
    length is not exactly one), ``SYMBOL_REJECTED``, ``COMMAND_REJECTED``, ``BOUNDS_REJECTED`` (also for
    NaN and infinity) and ``BUDGET_REJECTED``. The budget cap
    ``(warmup_runs + repeats + 3) * 2 * per_run_timeout_seconds <= 1800`` keeps one Lens B dispatch inside its
    wait; the ``+3`` is the untimed trace run, allowed 3x a timed run, per side. Defaults use 1600 s; at
    ``repeats`` 8 the timeout may be at most 81 with ``warmup_runs`` 0, 75 with 1 and 69 with 2.
    """
    if not isinstance(gate, dict):
        return None, "GATE_MISSING"
    if any(key not in gate for key in _REQUIRED_KEYS):
        return None, "KEY_MISSING"
    if any(not isinstance(key, str) or key not in _ALLOWED_KEYS for key in gate):
        return None, "KEY_UNKNOWN"

    command, paths, symbol = gate["command"], gate["benchmark_paths"], gate["benchmark_symbol"]
    if not isinstance(command, str) or not isinstance(symbol, str):
        return None, "TYPE_REJECTED"
    if not isinstance(paths, list) or any(not isinstance(item, str) for item in paths):
        return None, "TYPE_REJECTED"

    values = {name: gate.get(name, default) for name, default in _DEFAULTS.items()}
    for name in ("warmup_runs", "repeats", "per_run_timeout_seconds"):
        if not _is_real_int(values[name]):
            return None, "TYPE_REJECTED"
    fractions = {}
    for name in ("min_improvement", "max_noise"):
        fraction = _real_number_fraction(values[name])
        if fraction is None:
            # Non-finite floats are numbers of the right type that fail the bounds, not a type error.
            if type(values[name]) is float:
                return None, "BOUNDS_REJECTED"
            return None, "TYPE_REJECTED"
        fractions[name] = fraction

    if len(paths) != 1 or not _benchmark_path_ok(paths[0]):
        return None, "PATH_REJECTED"
    if not _valid_symbol(symbol):
        return None, "SYMBOL_REJECTED"
    if validate_benchmark_command(command, paths[0])[0] is None:
        return None, "COMMAND_REJECTED"

    if not (
        0 <= values["warmup_runs"] <= 2
        and values["repeats"] in _REPEATS_ALLOWED
        and 10 <= values["per_run_timeout_seconds"] <= 300
        and Fraction("0.05") <= fractions["min_improvement"] <= Fraction("0.90")
        and Fraction("0.02") <= fractions["max_noise"] <= Fraction("0.30")
    ):
        return None, "BOUNDS_REJECTED"
    if (values["warmup_runs"] + values["repeats"] + 3) * 2 * values["per_run_timeout_seconds"] > _BUDGET_CAP_SECONDS:
        return None, "BUDGET_REJECTED"

    normalized = {
        "command": command,
        "benchmark_paths": [paths[0]],
        "benchmark_symbol": symbol,
        "warmup_runs": values["warmup_runs"],
        "repeats": values["repeats"],
        "per_run_timeout_seconds": values["per_run_timeout_seconds"],
        "min_improvement": float(values["min_improvement"]),
        "max_noise": float(values["max_noise"]),
    }
    return normalized, "OK"


# ---------------------------------------------------------------------------
# evaluate_paired_samples
# ---------------------------------------------------------------------------

_NEED_CLEAR = {4: 4, 6: 5, 8: 7}


def _median(values: list[Fraction]) -> Fraction:
    """Median of a non-empty list; an even count is the mean of the two middle values."""
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _evaluate(base, head, repeats, min_improvement, max_noise) -> tuple[str, str]:
    if not _is_real_int(repeats) or repeats not in _NEED_CLEAR:
        return "INCONCLUSIVE", "INVALID_INPUT"
    threshold = _real_number_fraction(min_improvement)
    noise_limit = _real_number_fraction(max_noise)
    if threshold is None or noise_limit is None:
        return "INCONCLUSIVE", "INVALID_INPUT"
    if not (Fraction("0.05") <= threshold <= Fraction("0.90") and Fraction("0.02") <= noise_limit <= Fraction("0.30")):
        return "INCONCLUSIVE", "INVALID_INPUT"
    for samples in (base, head):
        if not isinstance(samples, (list, tuple)) or len(samples) != repeats:
            return "INCONCLUSIVE", "INVALID_INPUT"
        if any(not _is_real_int(v) or v <= 0 for v in samples):
            return "INCONCLUSIVE", "INVALID_INPUT"

    ratios = [Fraction(h, b) for b, h in zip(base, head)]
    # (1) Clear win: at least `need` ratios <= 1 - min_improvement. The noise gate is skipped here (the median
    # clause of revision 3 was redundant). need = 7 at n=8 is the stricter setting: need 6 gave 11.9% false
    # IMPROVED in the period-4 lock-in regime (revision 5).
    if sum(1 for r in ratios if r <= 1 - threshold) >= _NEED_CLEAR[repeats]:
        return "IMPROVED", "IMPROVED_CLEAR"
    median = _median(ratios)
    mad = _median([abs(r - median) for r in ratios])
    if mad / median > noise_limit:
        return "INCONCLUSIVE", "NOISY"
    if 1 - median >= threshold:
        return "INCONCLUSIVE", "INCONSISTENT"
    if 1 - median < threshold / 2:
        return "NOT_IMPROVED", "BELOW_HALF_THRESHOLD"
    return "INCONCLUSIVE", "BORDERLINE"


def evaluate_paired_samples(base, head, *, repeats, min_improvement, max_noise) -> tuple[str, str]:
    """Pure verdict over paired wall-time samples; returns ``(result, reason)`` and NEVER raises.

    Everything is exact ``fractions.Fraction`` arithmetic (floats via ``Fraction(str(x))``), so the 10%
    boundary is exact: ratios of exactly 0.9 at ``min_improvement`` 0.10 are ``IMPROVED_CLEAR``, 9.99% is not.
    ``ratio_i = head_i / base_i``. Parameters and inputs are validated here (``repeats`` in {4, 6, 8}, the
    two thresholds in their gate bounds, each list exactly ``repeats`` positive ``int`` with ``bool``
    rejected) and anything else is ``("INCONCLUSIVE", "INVALID_INPUT")``. Order: (1) clear win, skipping the
    noise gate; (2) ``MAD / median > max_noise`` -> ``NOISY``; (3) median already past the threshold but too
    few clear runs -> ``INCONSISTENT`` (no tolerance at n=4); (4) ``1 - median < min_improvement / 2``,
    including any head slower -> ``NOT_IMPROVED``; (5) else ``BORDERLINE``. ``INCONCLUSIVE`` is deliberately
    never a pass.
    """
    try:
        return _evaluate(base, head, repeats, min_improvement, max_noise)
    except Exception:  # noqa: BLE001 -- the contract is "never raises"; any surprise is a fail-closed result
        return "INCONCLUSIVE", "INVALID_INPUT"


# ---------------------------------------------------------------------------
# escape_diagnostic
# ---------------------------------------------------------------------------

def escape_diagnostic(text: object, limit: int = 2048) -> str:
    """Make untrusted text safe to embed in a diagnostic line (design: inline escaper, no shared runtime).

    Printable ASCII only (everything else becomes ``?``), newlines/CR/tab become spaces, backticks become
    ``'``, ``|`` becomes ``/`` (table breaking), a leading ``#``, ``>``, ``-`` (also ``*``, ``+``) is
    neutralized with a ``'`` prefix, and the result is capped at ``limit`` characters. Used only for
    diagnostics, never on the verdict path.
    """
    source = text if isinstance(text, str) else repr(text)
    out = []
    for char in source:
        if char in "\n\r\t":
            out.append(" ")
        elif char == "`":
            out.append("'")
        elif char == "|":
            out.append("/")
        elif " " <= char <= "~":
            out.append(char)
        else:
            out.append("?")
    escaped = "".join(out).lstrip(" ")
    if escaped[:1] in ("#", ">", "-", "*", "+"):
        escaped = "'" + escaped
    return escaped[: max(limit, 0)]


# ---------------------------------------------------------------------------
# validate_benchmark_content (the AST lint)
# ---------------------------------------------------------------------------

_MAX_BENCHMARK_BYTES = 16 * 1024
_DIGEST_LITERAL = "BENCH_RESULT_DIGEST: "

# The stable set of violation codes, in the canonical order ``validate_benchmark_content`` returns them in.
# Codes are fixed strings (never built from the source), so they are safe to print and to compare.
VIOLATION_CODES = (
    "SOURCE_NOT_BYTES",           # source is not a ``bytes`` object
    "FILE_TOO_LARGE",             # over 16 KiB
    "NON_ASCII_SOURCE",           # any byte >= 0x80 (this includes a BOM)
    "ENCODING_REJECTED",          # a PEP 263 cookie other than utf-8, or an invalid cookie
    "PARSE_FAILED",               # ``ast.parse`` raised anything (SyntaxError, null byte, RecursionError, ...)
    "ANALYSIS_FAILED",            # bad ``repo_top_levels`` argument, or an unexpected internal error (the AST walks
                                  # are iterative, so deep input is PARSE_FAILED, not this)
    "SYMBOL_INVALID",             # ``symbol`` fails ``_valid_symbol``, so no reference to it can be required
    "FORBIDDEN_CLASS",
    "FORBIDDEN_ASYNC_FUNCTION",
    "FORBIDDEN_LAMBDA",
    "FORBIDDEN_TRY",              # ``Try`` and ``TryStar`` (``except*``)
    "FORBIDDEN_WITH",
    "FORBIDDEN_GLOBAL",
    "FORBIDDEN_NONLOCAL",
    "FORBIDDEN_DECORATOR",        # a decorator on any function
    "RELATIVE_IMPORT",
    "STAR_IMPORT",                # ``from X import *`` hides which names (``open``, dunders) arrive
    "IMPORT_NOT_ALLOWED",
    "BANNED_NAME",                # a banned name anywhere a name is spelled: ``Name``, ``Attribute``, import
                                  # components and aliases, ``match`` captures and class-pattern attributes, type parameters
    "DUNDER_NAME",                # any dunder in those places, plus function and parameter names
    "TEST_NAME_COUNT",            # not exactly one module-level name beginning ``test``
    "TEST_NOT_FUNCTION",          # that one name is not a module-level ``def``
    "TEST_HAS_PARAMETERS",
    "MISSING_PRINT",
    "MISSING_DIGEST_LITERAL",
    "MISSING_SHA256",
    "MISSING_SYMBOL_REFERENCE",
)
_VIOLATION_ORDER = {code: index for index, code in enumerate(VIOLATION_CODES)}

# Stdlib modules a benchmark may import; ``pytest``, ``string``, ``time``, ``os``, ``sys`` and every other stdlib
# module are rejected. A stdlib name wins over ``repo_top_levels``: a repo-top-level ``hashlib.py`` must not be
# importable in place of the real one.
_STDLIB_IMPORT_ALLOWLIST = frozenset(
    {"__future__", "hashlib", "json", "math", "statistics", "itertools", "functools", "collections", "re", "decimal",
     "fractions", "heapq", "bisect", "copy", "random", "io", "enum", "sqlite3"}
)
# Rejected even when the repository itself ships them (benchmarking pytest's own code, for instance): the harness
# owns the runner and a benchmark must never touch it.
_IMPORT_ALWAYS_REJECTED = frozenset({"pytest", "_pytest"})
_BANNED_NAMES = frozenset(
    {"eval", "exec", "compile", "__import__", "getattr", "setattr", "hasattr", "delattr", "open", "globals", "locals",
     "vars", "dir", "breakpoint", "input"}
)
_FORBIDDEN_NODES = {
    ast.ClassDef: "FORBIDDEN_CLASS",
    ast.AsyncFunctionDef: "FORBIDDEN_ASYNC_FUNCTION",
    ast.Lambda: "FORBIDDEN_LAMBDA",
    ast.Try: "FORBIDDEN_TRY",
    ast.TryStar: "FORBIDDEN_TRY",
    ast.With: "FORBIDDEN_WITH",
    ast.Global: "FORBIDDEN_GLOBAL",
    ast.Nonlocal: "FORBIDDEN_NONLOCAL",
    # ``ast.parse`` accepts these outside an ``async def`` (they only fail at compile time), so banning
    # ``AsyncFunctionDef`` alone leaves them parseable; the same code covers every async construct.
    ast.AsyncWith: "FORBIDDEN_ASYNC_FUNCTION",
    ast.AsyncFor: "FORBIDDEN_ASYNC_FUNCTION",
    ast.Await: "FORBIDDEN_ASYNC_FUNCTION",
}


def _is_dunder(name: object) -> bool:
    return isinstance(name, str) and len(name) > 4 and name.startswith("__") and name.endswith("__")


def _module_level_bindings(tree: ast.Module) -> list[str]:
    """Every name bound in module scope, one entry per binding (so a redefinition counts twice).

    Counts ``def``/``class`` names, assignment and ``for``/``with``/walrus targets, ``import`` names and ``match``
    captures, including bindings nested in module-level ``if``/``for``/``while``. Function and lambda bodies,
    class bodies and comprehension iteration variables are their own scopes and do not count; a walrus inside a
    comprehension does bind in the enclosing scope and does count. Iterative on purpose: the tree can be deep.
    """
    names: list[str] = []
    stack: list[tuple[ast.AST, bool]] = [(stmt, False) for stmt in tree.body]  # (node, inside another scope)
    while stack:
        node, local = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not local:
                names.append(node.name)
            if isinstance(node, ast.ClassDef):
                stack.extend((child, True) for child in node.body)
                continue
            # Decorators, defaults and annotations are evaluated in the enclosing scope (annotations at def time
            # on 3.12 and 3.13, so ``def f(x: (test_b := g))`` binds ``test_b`` there); the body is not.
            args = node.args
            every_arg = [*args.posonlyargs, *args.args, *args.kwonlyargs, *(a for a in (args.vararg, args.kwarg) if a)]
            outer = [
                *node.decorator_list, *args.defaults, *(d for d in args.kw_defaults if d is not None),
                *(a.annotation for a in every_arg if a.annotation is not None),
            ]
            if node.returns is not None:
                outer.append(node.returns)
            stack.extend((child, local) for child in outer)
            stack.extend((child, True) for child in node.body)
        elif isinstance(node, ast.Lambda):
            stack.append((node.body, True))
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            for generator in node.generators:
                stack.append((generator.target, True))
                stack.append((generator.iter, local))
                stack.extend((cond, local) for cond in generator.ifs)
            stack.extend(
                (child, local) for child in ast.iter_child_nodes(node) if not isinstance(child, ast.comprehension)
            )
        else:
            if not local:
                if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):  # ``del x`` is a binding too
                    names.append(node.id)
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    names.extend(alias.asname or alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name is not None:
                    names.append(node.name)
                elif isinstance(node, ast.MatchMapping) and node.rest is not None:
                    names.append(node.rest)
            stack.extend((child, local) for child in ast.iter_child_nodes(node))
    return names


def _content_violations(source: object, symbol: object, repo_top_levels: frozenset[str]) -> set[str]:
    # Exactly a set or frozenset of str. A str would make ``top in repo_top_levels`` a substring test, and a custom
    # container could answer True to everything: neither may fail open, so anything else is rejected outright.
    if type(repo_top_levels) not in (set, frozenset) or any(type(name) is not str for name in repo_top_levels):
        return {"ANALYSIS_FAILED"}
    if type(source) is not bytes:
        return {"SOURCE_NOT_BYTES"}
    early: set[str] = set()
    if len(source) > _MAX_BENCHMARK_BYTES:
        early.add("FILE_TOO_LARGE")
    else:
        try:
            encoding, _ = tokenize.detect_encoding(io.BytesIO(source).readline)
        except (SyntaxError, ValueError, LookupError):
            early.add("ENCODING_REJECTED")
        else:
            # ``detect_encoding`` only normalizes some spellings (``utf8`` comes back as written); every alias of
            # the utf-8 codec decodes ASCII identically, so compare the codec, not the cookie text.
            if codecs.lookup(encoding).name != "utf-8":
                early.add("ENCODING_REJECTED")
    if not source.isascii():
        early.add("NON_ASCII_SOURCE")
    if early:
        return early  # nothing is parsed from a file that already failed a byte-level rule
    try:
        tree = ast.parse(source)
    except Exception:  # noqa: BLE001 -- SyntaxError, ValueError (null byte), RecursionError, MemoryError ...
        return {"PARSE_FAILED"}

    found: set[str] = set()
    symbol_ok = _valid_symbol(symbol)
    if not symbol_ok:
        found.add("SYMBOL_INVALID")
    sha256_names: set[str] = set()  # names bound by ``from hashlib import sha256 [as x]``
    called: list[ast.expr] = []
    symbol_seen = digest_seen = False

    def check_import(module: str) -> None:
        top = module.split(".")[0]
        allowed = top in _STDLIB_IMPORT_ALLOWLIST or (
            top not in sys.stdlib_module_names and top not in _IMPORT_ALWAYS_REJECTED and top in repo_top_levels
        )
        if not allowed:
            found.add("IMPORT_NOT_ALLOWED")

    def flag(name: str | None, banned: bool = True) -> None:
        """A name spelled as a plain string in the AST (import components and aliases, ``match`` captures and
        class-pattern attributes, type parameters) is as dangerous as a ``Name`` node: ``from json import
        __builtins__ as bb`` reaches ``eval`` with no ``Name`` or ``Attribute`` that says so. ``banned=False``
        checks dunders only, for a module-path component that is never bound or fetched as a name."""
        if banned and name in _BANNED_NAMES:
            found.add("BANNED_NAME")
        if _is_dunder(name):
            found.add("DUNDER_NAME")

    for node in ast.walk(tree):
        kind = type(node)
        if kind in _FORBIDDEN_NODES:
            found.add(_FORBIDDEN_NODES[kind])
        if kind is ast.FunctionDef:
            if node.decorator_list:
                found.add("FORBIDDEN_DECORATOR")
            if _is_dunder(node.name):
                found.add("DUNDER_NAME")
        elif kind is ast.AsyncFunctionDef:
            if node.decorator_list:
                found.add("FORBIDDEN_DECORATOR")
        elif kind is ast.arg:
            if _is_dunder(node.arg):
                found.add("DUNDER_NAME")
        elif kind is ast.Name or kind is ast.Attribute:
            name = node.id if kind is ast.Name else node.attr
            flag(name)
            symbol_seen = symbol_seen or name == symbol
        elif kind is ast.Import:
            for alias in node.names:
                check_import(alias.name)
                parts = alias.name.split(".")
                for index, part in enumerate(parts):
                    flag(part, banned=index == 0)  # ``import a.b`` binds only ``a``
                flag(alias.asname)
                symbol_seen = symbol_seen or symbol in (*parts, alias.asname)
        elif kind is ast.ImportFrom:
            module = node.module or ""
            if node.level > 0:
                found.add("RELATIVE_IMPORT")
            else:
                check_import(module)
                if module == "hashlib":
                    sha256_names.update(alias.asname or alias.name for alias in node.names if alias.name == "sha256")
            if module != "__future__":  # the one module whose own name is a dunder
                for part in module.split("."):
                    flag(part, banned=False)  # ``from a.b import c`` binds only ``c``
            symbol_seen = symbol_seen or symbol in module.split(".")
            for alias in node.names:
                if alias.name == "*":
                    found.add("STAR_IMPORT")
                flag(alias.name)
                flag(alias.asname)
                symbol_seen = symbol_seen or symbol in (alias.name, alias.asname)
        elif kind is ast.MatchClass:
            for attr in node.kwd_attrs:
                flag(attr)
        elif kind in (ast.MatchAs, ast.MatchStar, ast.TypeVar, ast.ParamSpec, ast.TypeVarTuple):
            flag(node.name)
        elif kind is ast.MatchMapping:
            flag(node.rest)
        elif kind is ast.comprehension:
            if node.is_async:
                found.add("FORBIDDEN_ASYNC_FUNCTION")
        elif kind is ast.Constant:
            digest_seen = digest_seen or (isinstance(node.value, str) and _DIGEST_LITERAL in node.value)
        elif kind is ast.Call:
            called.append(node.func)

    if not any(isinstance(func, ast.Name) and func.id == "print" for func in called):
        found.add("MISSING_PRINT")
    if not digest_seen:
        found.add("MISSING_DIGEST_LITERAL")
    if not any(
        (
            isinstance(func, ast.Attribute)
            and func.attr == "sha256"
            and isinstance(func.value, ast.Name)
            and func.value.id == "hashlib"
        )
        or (isinstance(func, ast.Name) and func.id in sha256_names)
        for func in called
    ):
        found.add("MISSING_SHA256")
    if symbol_ok and not symbol_seen:
        found.add("MISSING_SYMBOL_REFERENCE")

    bound = [name for name in _module_level_bindings(tree) if name.startswith("test")]
    top_level_tests = [s for s in tree.body if isinstance(s, ast.FunctionDef) and s.name.startswith("test")]
    if len(bound) != 1:
        found.add("TEST_NAME_COUNT")
    elif len(top_level_tests) != 1:
        found.add("TEST_NOT_FUNCTION")
    else:
        args = top_level_tests[0].args
        if args.posonlyargs or args.args or args.vararg or args.kwonlyargs or args.kwarg:
            found.add("TEST_HAS_PARAMETERS")
    return found


def validate_benchmark_content(source: bytes, symbol: str, repo_top_levels: frozenset[str]) -> list[str]:
    """Lint one benchmark file; return violation codes (``VIOLATION_CODES``), empty meaning accepted.

    NEVER raises: any failure of the parser becomes ``PARSE_FAILED`` (deep nesting, ``RecursionError``, a null
    byte), and ``ANALYSIS_FAILED`` is for a ``repo_top_levels`` that is not exactly a ``set``/``frozenset`` of
    ``str`` (checked first, so a stdlib-only source cannot get past a bad argument) or an unexpected error in the
    checks. The result is de-duplicated and in the canonical ``VIOLATION_CODES`` order, so equal
    inputs give equal output. A file that fails a byte-level rule (``FILE_TOO_LARGE``, ``NON_ASCII_SOURCE``,
    ``ENCODING_REJECTED``) is not parsed, so those codes are never mixed with AST codes.

    Operates on BYTES: ``ast.parse(bytes)`` honours a PEP 263 coding cookie, so a source that is ASCII but
    declares another codec would be parsed differently from what a text-mode lint saw. Hence
    ``tokenize.detect_encoding`` must report utf-8 (any other or invalid cookie is rejected) and every byte must
    be ASCII.

    AST rules (design APIs table): exactly ONE module-level name beginning ``test`` (a ``def``, an assignment, an
    import and a walrus all count, and so does a redefinition), which must be a ``def`` with no parameters; no
    ``ClassDef``, ``AsyncFunctionDef``, ``Lambda``, ``Try``/``TryStar``, ``With``, ``Global``, ``Nonlocal`` and no
    decorator on any function (module-level helper functions and constants are fine). Imports: a stdlib module
    must be in ``_STDLIB_IMPORT_ALLOWLIST`` (``pytest`` is rejected even if ``repo_top_levels`` names it), any other
    top-level name must be in ``repo_top_levels`` (the top-level packages and modules of the base export), and a
    relative import and ``from X import *`` are rejected. ``_BANNED_NAMES`` and every dunder are rejected as
    ``Name`` or ``Attribute`` and also wherever a name is only a string in the AST: every dotted component of an
    import's module and aliases (``from json import __builtins__ as bb``; the ``__future__`` module itself is
    exempt), ``match`` captures and class-pattern attributes, and type-parameter names. Every async construct
    (``async def``/``with``/``for``, ``await``, an async comprehension) is ``FORBIDDEN_ASYNC_FUNCTION``: the
    parser accepts the latter ones outside an ``async def``. ``del test_x`` counts as a binding of ``test_x``.
    Required: a ``print(...)`` call, the literal ``BENCH_RESULT_DIGEST: `` in a string constant, a
    ``hashlib.sha256(...)`` call (or a call of the name bound by ``from hashlib import sha256``), and a reference to
    ``symbol`` as ``Name.id``, ``Attribute.attr``, an import ``alias.name``/``asname``, or a dotted component of an
    import's module.

    Beyond the table (stricter, same spirit): a dunder FUNCTION or PARAMETER name is ``DUNDER_NAME`` too, and an
    invalid ``symbol`` is ``SYMBOL_INVALID`` rather than a silently satisfiable requirement.

    This is a TRIPWIRE, not a sandbox. Allowlists are better than denylists but are still evadable
    (``string.Formatter().get_field``, ``type()``-built context managers, objects reached through the code under
    test), a constant digest and a dead reference pass it, and the code under test is not linted at all. The
    controls that do not depend on enumerating names are the harness trace, the exports and human acceptance.
    """
    try:
        return sorted(_content_violations(source, symbol, repo_top_levels), key=_VIOLATION_ORDER.__getitem__)
    except Exception:  # noqa: BLE001 -- the contract is "never raises" (RecursionError and MemoryError included)
        return ["ANALYSIS_FAILED"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_MAX_INPUT_BYTES = 1 << 20


def gate_sha256(normalized_gate: dict) -> str:
    """sha256 of the canonical JSON of a normalized gate (the Orchestrator recomputes it)."""
    canonical = json.dumps(normalized_gate, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _read_bounded(path: str, limit: int) -> bytes:
    """Read at most ``limit + 1`` bytes of a REGULAR file; the caller treats ``len > limit`` as too large.

    A bounded read rather than ``stat().st_size``: a size taken before the read is not a cap, and a FIFO or a
    device (``/dev/zero``) reports no useful size. The file is opened ``O_NONBLOCK`` (where the platform has it)
    so opening a FIFO with no writer cannot hang, then ``fstat`` on the opened descriptor must say regular file.
    Raises ``OSError`` or ``ValueError``; both are usage errors to the CLI.
    """
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("not a regular file")
        handle = os.fdopen(fd, "rb")  # ``fdopen`` itself raises on a directory, so check before it, and close on failure
    except BaseException:
        os.close(fd)
        raise
    with handle:
        return handle.read(limit + 1)


def _repo_top_levels(root: Path) -> set[str]:
    """Top-level importable names under ``root`` and ``root/src``: every directory (a namespace package is
    importable too) and every ``*.py`` module stem whose name is an ASCII identifier. Raises ``OSError`` or
    ``ValueError`` when ``root`` is not a readable directory. ``root/src`` is optional."""
    if not root.is_dir():
        raise ValueError("repo root is not a directory")
    names: set[str] = set()
    for base in (root, root / "src"):
        if not base.is_dir():
            continue
        for entry in base.iterdir():
            name = entry.stem if entry.suffix == ".py" and entry.is_file() else entry.name if entry.is_dir() else ""
            if name.isascii() and name.isidentifier():
                names.add(name)
    return names


def _cmd_validate(args: argparse.Namespace) -> int:
    """Exit codes: 0 ``OK`` (then ``gate_sha256: <hex>``), 1 ``REJECT:<code>``, 3 ``NOT_GATED``, 2 usage.

    The origin flag is tested with ``is True`` so ``"true"``, ``1`` and ``false`` are not set. A key present
    with ANY value, including ``null``, is gated, so both mismatch directions are executable. Unreadable,
    oversize, non-regular, non-UTF-8, malformed or too deeply nested input is a usage error with nothing on stdout.
    """
    try:
        data = _read_bounded(args.specialist_inputs, _MAX_INPUT_BYTES)
        if len(data) > _MAX_INPUT_BYTES:
            raise ValueError("input too large")
        inputs = json.loads(data.decode("utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        print(f"usage error: cannot read specialist_inputs: {escape_diagnostic(str(exc), 200)}", file=sys.stderr)
        return 2
    if not isinstance(inputs, dict):
        print("usage error: specialist_inputs must be a JSON object", file=sys.stderr)
        return 2

    has_gate = "benchmark_gate" in inputs
    origin = inputs.get("performance_review_origin") is True
    if not has_gate and not origin:
        print("NOT_GATED")
        return 3
    if origin and inputs.get("benchmark_gate") is None:
        print("REJECT:GATE_MISSING")
        return 1
    if not origin:
        print("REJECT:GATE_WITHOUT_ORIGIN")
        return 1
    normalized, code = validate_benchmark_gate(inputs["benchmark_gate"])
    if normalized is None:
        print(f"REJECT:{code}")
        return 1
    print("OK")
    print(f"gate_sha256: {gate_sha256(normalized)}")
    return 0


def _cmd_lint(args: argparse.Namespace) -> int:
    """Lint one benchmark file. Exit codes: 0 clean (nothing printed), 1 violations (one code per line on stdout,
    in ``VIOLATION_CODES`` order), 2 usage (bad arguments, unreadable or non-regular file, bad ``--repo-root``).

    The repository's importable top-level names come from ``--repo-root DIR`` (its directories and ``*.py``
    stems, plus those under ``DIR/src``; point it at the BASE export so a head-added package cannot allow
    itself) and/or repeated ``--top-level NAME``; with neither, only stdlib-allowlist imports pass. An over-size
    file is not a usage error: at most 16 KiB + 1 byte is read and ``FILE_TOO_LARGE`` is a violation like any other.
    """
    try:
        source = _read_bounded(args.benchmark, _MAX_BENCHMARK_BYTES)
        top_levels = set(args.top_level)
        if args.repo_root is not None:
            top_levels |= _repo_top_levels(Path(args.repo_root))
    except (OSError, ValueError) as exc:
        print(f"usage error: cannot lint: {escape_diagnostic(str(exc), 200)}", file=sys.stderr)
        return 2
    violations = validate_benchmark_content(source, args.symbol, frozenset(top_levels))
    for code in violations:
        print(code)
    return 1 if violations else 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``validate`` (C4a) and ``lint`` (C4b). Later PRs add ``export``, ``compare`` and others
    by adding a subparser with ``set_defaults(func=...)``; nothing else here changes."""
    parser = argparse.ArgumentParser(prog="benchmark_gate.py", description="Benchmark gate validation core (C4a/C4b).")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="validate specialist_inputs.benchmark_gate")
    validate.add_argument("--specialist-inputs", required=True, metavar="FILE")
    validate.set_defaults(func=_cmd_validate)
    lint = sub.add_parser("lint", help="lint one benchmark file (exit 0 clean, 1 violations, 2 usage)")
    lint.add_argument("--benchmark", required=True, metavar="FILE")
    lint.add_argument("--symbol", required=True, metavar="SYMBOL")
    lint.add_argument("--repo-root", metavar="DIR", help="derive the repo's top-level names from DIR and DIR/src")
    lint.add_argument("--top-level", action="append", default=[], metavar="NAME", help="add one top-level name")
    lint.set_defaults(func=_cmd_lint)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse exits 2 on usage errors (and 0 on --help)
        return exc.code if isinstance(exc.code, int) else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
