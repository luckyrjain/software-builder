#!/usr/bin/env python3
"""Validation, lint and statistics core of the performance-review -> loop-task-implementer benchmark gate (Epic C).

**This module is not wired into anything yet.** It is delivered by a series of six PRs for gap-backlog ticket
C4 (C4a core, C4b lint, C4c exports, C4d harness, C4e classifier/docs, C4f wiring); no workflow file,
lifecycle validator or other script calls it until C4f. So far it holds the pure, string-level and arithmetic
pieces (``validate``, ``lint``) and the filesystem/git pieces of C4c (``export``, ``snapshot-venv``,
``cleanup`` and the library functions ``compare`` will call); C4d adds measurement, the trace, ``compare`` and
``run-once``, C4e the classifier and docs, C4f the workflow wiring. Specification (revision 5, the converged result of four review
rounds): ``docs/superpowers/specs/2026-10-02-c4-performance-review-executor-handoff-design.md`` (APIs table,
Data model, Capacity, Threat model). This docstring states each function's own contract and the reason each
rule exists; it does not re-derive the design.

Threat model, in one paragraph: the gate resists accidental, lazy and moderately clever gaming and makes
honest wins measurable. It does not make a measurement trustworthy against a Builder whose code executes
under the harness; for that class the control is a human reading the fix and the benchmark. Everything here
fails closed: any malformed input yields a rejection code or ``INCONCLUSIVE``, never a pass.

Standard library only. The skill is packaged with ``scripts/`` shipped wholesale and cannot import
repo-root packages, and nothing platform-specific happens at import time (Windows-safe). The C4c filesystem
helpers need POSIX (``fchmod``, ``O_NOFOLLOW``, ``os.kill``): the harness is POSIX-only (Windows is out of
scope, ``compare`` reports ``UNSUPPORTED_PLATFORM``), but importing the module works everywhere.
"""

from __future__ import annotations

import argparse
import ast
import codecs
import dis
import hashlib
import importlib.util
import io
import json
import keyword
import math
import os
import posixpath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import tokenize
import types
import unicodedata
import warnings
from fractions import Fraction
from pathlib import Path
from typing import Literal

# ---------------------------------------------------------------------------
# benchmark_symbol_from_location
# ---------------------------------------------------------------------------

# ``re.ASCII``: without it ``\d`` also matches Arabic-Indic and other Unicode digits, so such a tail would strip.
_LINE_TAIL_RE = re.compile(r"(?::\d+(?::\d+)?|#L\d+| L\d+)\Z", re.ASCII)
_SYMBOL_RE = re.compile(r"[A-Za-z_]\w*", re.ASCII)
_SYMBOL_DENYLIST = frozenset(
    {"print", "hashlib", "sha256", "main", "data", "sort", "load", "list", "item", "time", "test", "bench", "run", "get", "set"}
)
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
    Replaces revision 3's 4-character rule, which excluded real symbols (``fib``, ``api``) yet admitted ``main``.

    Beyond the design's 15 denied names, EVERY dunder is rejected (the design named only ``__init__`` and
    ``__main__``): the lint rejects a dunder as a ``Name``, ``Attribute`` or alias, so a benchmark could never
    reference ``Order.__eq__`` and the task would loop on an unfixable lint rejection. A Python keyword is
    rejected for the same reason (no benchmark can bind or attribute-access ``class``). ``type(name) is str``,
    not ``isinstance``: a ``str`` subclass with a hostile ``__eq__`` would otherwise make every name "match"."""
    return (
        type(name) is str
        and not keyword.iskeyword(name)
        and _SYMBOL_RE.fullmatch(name) is not None
        and 3 <= len(name) <= 64
        and not _is_dunder(name)
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

    Design deviation (stricter, fail closed): a symbol derived from a ``::``, dotted-method or bare-name form
    (``app/db.py::Database.open``, ``input()``) is ``None`` when it is one of the lint's ``_BANNED_NAMES``, as is
    any dunder: no benchmark could reference it without the lint rejecting it. The file-level module-stem branch
    is exempt (``app/open.py`` -> ``open``; a module path is accepted). The design lists exactly 15 denied names.

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

    module_stem = False
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
            module_stem = True
        elif "." in base and ("/" in text or base.rpartition(".")[2].casefold() in _KNOWN_FILE_EXTENSIONS):
            return None
        else:
            name = base.rsplit(".", 1)[-1]
    if name in _BANNED_NAMES and not module_stem:
        return None
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
    "ANALYSIS_FAILED",            # bad ``repo_top_levels`` argument, or an unexpected internal error
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
    "BANNED_NAME",                # a banned name as ``Name``, ``Attribute``, bound import name, ``match``, type parameter
    "DUNDER_NAME",                # any dunder in those places or a module path, plus function and parameter names
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


_NAME_BINDING_OPS = frozenset({"STORE_NAME", "DELETE_NAME", "STORE_GLOBAL", "DELETE_GLOBAL"})  # a nested walrus makes the name global
_COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
# CPython's compiler crashes (SIGSEGV on 3.12 and 3.14) on about 23 nested comprehensions, 20 if async: deeper
# nesting is rejected without compiling it.
_MAX_COMPREHENSION_DEPTH = 12


def _comprehension_depth(tree: ast.AST) -> int:
    """Maximum nesting depth of list/set/dict comprehensions and generator expressions. Iterative."""
    deepest = 0
    stack = [(tree, 0)]
    while stack:
        node, depth = stack.pop()
        depth += isinstance(node, _COMPREHENSIONS)
        deepest = max(deepest, depth)
        stack.extend((child, depth) for child in ast.iter_child_nodes(node))
    return deepest


def _module_level_names(code: types.CodeType) -> list[str]:
    """Every name the compiled module binds or deletes in module scope, one entry per bytecode occurrence.

    The COMPILER decides what binds a module-level name, not a hand-written AST walk (which needed a new patch
    each review round). In the module's own code object that is ``STORE_NAME``/``DELETE_NAME`` (or the ``*_GLOBAL``
    forms, when a nested walrus makes the name global); in every nested code object only ``STORE_GLOBAL`` counts (how a walrus in a generator expression binds the module's name). Names bound only in a function or class body, or as a comprehension's own variable, do not
    appear; a redefinition counts twice. Iterative (nested code via ``co_consts``); nothing is executed.
    """
    names: list[str] = []
    pending = [(code, True)]
    while pending:
        current, is_module = pending.pop()
        wanted = _NAME_BINDING_OPS if is_module else {"STORE_GLOBAL"}
        names.extend(ins.argval for ins in dis.get_instructions(current) if ins.opname in wanted)
        pending.extend((const, False) for const in current.co_consts if isinstance(const, types.CodeType))
    return names


def _content_violations(source: object, symbol: object, repo_top_levels: frozenset[str]) -> set[str]:
    # Exactly a set or frozenset of str: a str would make ``in`` a substring test and a custom container could
    # answer True to everything, so anything else is rejected outright rather than failing open.
    if type(repo_top_levels) not in (set, frozenset) or any(type(name) is not str for name in repo_top_levels):
        return {"ANALYSIS_FAILED"}
    if type(source) is not bytes:
        return {"SOURCE_NOT_BYTES"}
    early: set[str] = set()
    if len(source) > _MAX_BENCHMARK_BYTES:
        early.add("FILE_TOO_LARGE")
    else:
        try:
            # ``detect_encoding`` splits on ``\n`` only, the C tokenizer also at a bare ``\r``: normalize, or
            # ``b"\r# coding: hz\r..."`` hides a cookie the parser honours.
            normalized = source.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            encoding, _ = tokenize.detect_encoding(io.BytesIO(normalized).readline)
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
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # a SyntaxWarning (invalid escape) must neither print nor change the verdict
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
        """A name that is only a string in the AST (import aliases, ``match`` captures and class-pattern attributes,
        type parameters) is as dangerous as a ``Name`` node (``from json import __builtins__ as bb``).
        ``banned=False`` checks dunders only, for a module-path component that is never bound or fetched."""
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
                    # ``import a.b`` binds only ``a``, and ``import a.b as c`` binds only ``c`` (checked below)
                    flag(part, banned=index == 0 and alias.asname is None)
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

    if found:
        return found  # already rejected: do not spend (or risk) a compile on it; its code set is a subset
    if _comprehension_depth(tree) > _MAX_COMPREHENSION_DEPTH:
        return {"PARSE_FAILED"}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            code = compile(source, "<benchmark>", "exec", dont_inherit=True)  # compiles, never executes
        names = _module_level_names(code)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        # ``compile`` is stricter than ``ast.parse`` (a 3.14 walrus in an annotation, a walrus in a comprehension
        # iterable), and ``dis`` cannot render a huge integer constant (ValueError): the count cannot be trusted.
        return {"PARSE_FAILED"}
    tests = [name for name in names if name.startswith("test")]
    top_level_tests = [s for s in tree.body if isinstance(s, ast.FunctionDef) and s.name.startswith("test")]
    # pytest also collects ``Test*`` names and acts on ``pytest_*`` hooks and ``pytestmark``.
    if len(tests) != 1 or any(name.startswith(("pytest", "Test")) for name in names):
        found.add("TEST_NAME_COUNT")
    elif len(top_level_tests) != 1 or tests != [top_level_tests[0].name]:
        # Defense in depth: the counted name must BE the one top-level def. ``test_a = print`` followed by an
        # unreachable ``def test_bench`` compiles to ``test_a`` alone (the dead def vanishes), so counts alone pass.
        found.add("TEST_NOT_FUNCTION")
    else:
        args = top_level_tests[0].args
        if args.posonlyargs or args.args or args.vararg or args.kwonlyargs or args.kwarg:
            found.add("TEST_HAS_PARAMETERS")
    return found


def validate_benchmark_content(source: bytes, symbol: str, repo_top_levels: frozenset[str]) -> list[str]:
    """Lint one benchmark file; return violation codes (``VIOLATION_CODES``), empty meaning accepted.

    NEVER raises. A parser failure is ``PARSE_FAILED``; ``ANALYSIS_FAILED`` is a ``repo_top_levels`` that is not
    exactly a ``set``/``frozenset`` of ``str`` (checked first, so nothing fails open) or an unexpected internal
    error. The result is de-duplicated in the canonical ``VIOLATION_CODES`` order. A file failing a byte-level rule
    (``FILE_TOO_LARGE``, ``NON_ASCII_SOURCE``, ``ENCODING_REJECTED``) is not parsed.

    Operates on BYTES: ``ast.parse(bytes)`` honours a PEP 263 coding cookie, so an ASCII file declaring another
    codec would be read differently from a text-mode lint. ``tokenize.detect_encoding`` (fed newline-normalized
    bytes: it splits on ``\\n`` only while the C tokenizer also ends a line at a bare ``\\r``) must say utf-8,
    and every byte must be ASCII.

    Rules (design APIs table). No ``ClassDef``, async construct (``async def``/``with``/``for``, ``await``, async
    comprehension: ``ast.parse`` accepts them outside an ``async def``), ``Lambda``, ``Try``/``TryStar``, ``With``,
    ``Global``, ``Nonlocal``, no decorator. Imports: a stdlib module must be in ``_STDLIB_IMPORT_ALLOWLIST``
    (``pytest`` is rejected even if ``repo_top_levels`` names it), any other top-level name must be in
    ``repo_top_levels``; relative imports and ``from X import *`` are rejected. ``_BANNED_NAMES`` and every dunder
    are rejected as ``Name``/``Attribute`` and wherever a name is only a string in the AST: import aliases, ``match``
    captures and class-pattern attributes, type parameters. Module-PATH components bind nothing (``import a.b``
    binds ``a``, ``from a.b import c`` binds ``c``), so a banned name there is fine (``from app.open import go``)
    and only a dunder is rejected; the ``__future__`` module itself is exempt. Required: a ``print(...)`` call, the
    literal ``BENCH_RESULT_DIGEST: `` in a string constant, a ``hashlib.sha256(...)`` call (or a call of the name
    from ``from hashlib import sha256``), and a reference to ``symbol`` as ``Name.id``, ``Attribute.attr``, an
    import ``alias.name``/``asname`` or a dotted component of an import's module.

    The one-test rule is counted from the COMPILED module (``_module_level_names``), not an AST walk: exactly one
    module-level name beginning ``test`` (a redefinition, ``del`` and a walrus anywhere count), none beginning
    ``pytest`` (``pytest_*`` hooks, ``pytestmark``) or ``Test`` (collected classes; ``TEST_SIZE`` is fine), and the
    one name must be a ``def`` with no parameters. ``compile`` runs ONLY when no other rule fired, so a rejected
    source gets only AST codes (its code set is a subset, and not stable across Python versions). It is stricter
    than ``ast.parse`` and ``dis`` cannot render a huge integer constant: both are ``PARSE_FAILED``, as is
    comprehension nesting beyond ``_MAX_COMPREHENSION_DEPTH`` (CPython's compiler crashes on about 23 nested
    comprehensions, so such a source is never compiled). Residual: ``compile`` runs in-process on input that passed
    the AST rules, so a compiler crash class beyond that guarded family would end the process, which callers
    (``compare``, the CLI) treat as fail-closed (exit 2 / no JSON). ``sys.stdlib_module_names`` differs between
    Python versions, so ``compare`` must lint with the harness's own Python. Warnings are silenced during parsing.

    Beyond the table (stricter): a dunder function or parameter name, a star import, and an invalid ``symbol``
    (``SYMBOL_INVALID``) are rejected; so is comprehension nesting deeper than 12 (``PARSE_FAILED``), and the
    one-test rule also rejects module-level names beginning ``test`` as a prefix match (``tester`` counts, ``tes``
    does not) and the widened ``pytest``/``Test`` prefixes (``pytest_*``, ``pytestmark``, ``TestX``).

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
# C4c: exports, tree hash and seal, overlay, protected paths, token tripwire, venv snapshot, cleanup
#
# Everything here runs on attacker-influenced input (a Builder's commit, a venv a build hook wrote into): argv lists
# only, a scrubbed environment, every subprocess bounded in time and output, every path validated before use, no
# symlink ever followed out of a root. POSIX only (see the module docstring).
# ---------------------------------------------------------------------------

# Stable ASCII codes. A refusal of hostile tree content is a verdict (CLI: stdout, exit 1); the rest are failures (exit 2).
EXPORT_REFUSAL_CODES = (
    "EXPORT_PATH_REJECTED",     # a `.`/`..`/empty component or a `.git` lookalike
    "EXPORT_PATH_COLLISION",    # two paths equal after NFC + casefold, or a file/directory clash that way
    "EXPORT_ENTRY_MODE",        # not a regular file, symlink or gitlink
    "EXPORT_TOO_LARGE",         # over 100,000 entries or 1 GiB of blobs
    "EXPORT_SYMLINK_ESCAPES",   # a symlink whose real target is outside the export
    "EXPORT_VERIFY_FAILED",     # the written tree differs from the commit's listing
)
ERROR_CODES = (
    "COMMIT_INVALID", "COMMIT_NOT_FOUND", "REPO_UNREADABLE", "DEST_REJECTED", "GIT_FAILED", "GIT_TIMEOUT",
    "GIT_OUTPUT_TOO_LARGE", "TREE_UNREADABLE", "TREE_TOO_LARGE", "SEAL_FAILED", "SNAPSHOT_FAILED", "TRIPWIRE_LIMIT",
    "PROTECTED_DIFF_FAILED", "MARKER_MISSING", "MARKER_INVALID", "OVERLAY_REJECTED", "BENCHMARK_MODIFIED",
)
CLEANUP_CODES = (
    "REMOVED", "ABSENT",        # success (exit 0); the rest are refusals (exit 1)
    "NOT_UNDER_FIXED_PARENT", "NOT_A_DIRECTORY", "NOT_OWNED", "MARKER_MISSING", "MARKER_INVALID", "OWNER_ALIVE",
    "REMOVE_FAILED",
)
BENCHMARK_AWARE_CODE = "BENCHMARK_AWARE_CODE"  # the `compare` result code a token-tripwire hit maps to

_COMMIT_RE = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}", re.ASCII)
_EMPTY_TREE = {  # git knows the empty tree without it being in the object store
    40: "4b825dc642cb6eb9a060e54bf8d69288fbee4904",
    64: "6ef19b41225c5369f1c104d45d8d85efa9b057b53b14b4b9b939dd74decc5321",
}
_ROOT_PARENT_NAME = "software-builder-bench"
_MARKER_NAME = ".bench-root.json"
_MARKER_KIND = "software-builder-bench-root"
_ROOT_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{7,63}")
_LEAF_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
_MAX_TREE_ENTRIES = 100_000
_MAX_EXPORT_BYTES = 1 << 30
_GIT_TIMEOUT_SECONDS = 300
_GIT_OUTPUT_CAP = 64 << 20
_LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1\n"


class BenchmarkGateError(Exception):
    """A refusal or failure of a C4c helper: `code` is one of the stable codes above, `detail` untrusted free text."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


# --- the fixed parent, the dispatch-unique root and its marker ----------------------------------------------------

def fixed_parent() -> Path:
    """The only directory `export` creates roots in and `cleanup` removes them from: `<tempdir>/software-builder-bench`.
    Fixed (not caller-supplied) so containment is a `realpath` comparison, and never a name pattern (a pattern delete
    could hit another live task's root; `task_lease` allows concurrent Orchestrators on one host). Derived from
    `tempfile.gettempdir()` at call time: a process with a different `TMPDIR` finds nothing and refuses."""
    return Path(tempfile.gettempdir()) / _ROOT_PARENT_NAME


def _foreign(st: os.stat_result) -> bool:
    return hasattr(os, "getuid") and st.st_uid != os.getuid()


def _ensure_fixed_parent() -> Path:
    parent = fixed_parent()
    try:
        os.mkdir(parent, 0o700)
    except FileExistsError:
        pass
    st = os.lstat(parent)  # lstat: a symlink planted at the fixed parent is not a directory
    if not stat.S_ISDIR(st.st_mode) or st.st_mode & 0o022 or _foreign(st):
        raise BenchmarkGateError("DEST_REJECTED", "fixed parent is not a private directory owned by this user")
    return parent


def _write_json_atomic(path: str, payload: dict) -> None:
    tmp = f"{path}.{os.getpid()}.tmp"  # O_EXCL + O_NOFOLLOW, then rename: a reader sees all of it or none
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(json.dumps(payload, sort_keys=True).encode("ascii"))
        os.replace(tmp, path)
    except BaseException:
        if os.path.lexists(tmp):
            os.unlink(tmp)
        raise


def _write_marker(root: str, owner_pid: int) -> None:
    _write_json_atomic(os.path.join(root, _MARKER_NAME), {
        "kind": _MARKER_KIND, "version": 1, "pid": owner_pid, "created": time.time(), "root": os.path.basename(root),
    })


def _read_marker(root: str) -> dict:
    """The validated marker: kind, version, positive `int` pid, finite non-future `created`, and `root` equal to the
    directory's own name (a copied marker proves nothing). Else `MARKER_MISSING` / `MARKER_INVALID`."""
    try:
        raw = _read_bounded(os.path.join(root, _MARKER_NAME), 4096, nofollow=True)
    except OSError as exc:
        raise BenchmarkGateError("MARKER_MISSING", str(exc)) from exc
    except ValueError as exc:
        raise BenchmarkGateError("MARKER_INVALID", "not a regular file") from exc
    try:
        marker = json.loads(raw.decode("ascii")) if len(raw) <= 4096 else None
    except (ValueError, RecursionError):
        marker = None
    pid, created = (marker.get("pid"), marker.get("created")) if isinstance(marker, dict) else (None, None)
    if not (
        isinstance(marker, dict) and marker.get("kind") == _MARKER_KIND and marker.get("version") == 1
        and marker.get("root") == os.path.basename(root) and type(pid) is int and 0 < pid < 1 << 31
        and type(created) in (int, float) and math.isfinite(created) and 0 < created <= time.time() + 300
    ):
        raise BenchmarkGateError("MARKER_INVALID", "marker fields are wrong")
    return marker


def _pid_alive(pid: int) -> bool:
    """`os.kill(pid, 0)`: no error is alive, ESRCH dead, EPERM alive, anything else alive (fail closed). Off POSIX the
    answer is "alive" (Windows `os.kill` would terminate the process). Residual: a recycled pid keeps a dead owner's
    root undeletable (the safe direction); portable process start times need a third-party package."""
    if os.name != "posix":
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except (OSError, OverflowError, ValueError):
        return True
    return True


def _checked_root(root: str | os.PathLike) -> str:
    """The root's path when it is a real directory of ours directly under the fixed parent, else `BenchmarkGateError`."""
    path = os.path.abspath(os.fspath(root))
    parent = os.path.realpath(os.path.dirname(path))
    if not _ROOT_NAME_RE.fullmatch(os.path.basename(path)) or parent != os.path.realpath(fixed_parent()):
        raise BenchmarkGateError("NOT_UNDER_FIXED_PARENT", "root is not directly under the fixed parent")
    path = os.path.join(parent, os.path.basename(path))  # operate on the resolved path, never on the argument
    try:
        st = os.lstat(path)
    except FileNotFoundError as exc:
        raise BenchmarkGateError("ABSENT") from exc
    if not stat.S_ISDIR(st.st_mode):
        raise BenchmarkGateError("NOT_A_DIRECTORY", "root is a symlink or not a directory")
    if _foreign(st):
        raise BenchmarkGateError("NOT_OWNED", "root belongs to another user")
    return path


def claim_root(root: str | os.PathLike, pid: int | None = None) -> None:
    """Re-point a root's marker at `pid` (default: this process) so `cleanup` refuses while it lives (`compare`, C4d)."""
    path = _checked_root(root)
    _read_marker(path)
    _write_marker(path, os.getpid() if pid is None else pid)


# --- tree walking, hashing, sealing ------------------------------------------------------------------------------

def _walk_tree(root: str, before_dir=None):
    """Yield `(relpath, abspath, lstat)` for `root` ("" first) and everything below: depth first, names sorted, symlinks
    reported and never followed, at most `_MAX_TREE_ENTRIES`. `before_dir(path, st)` runs before a directory is listed.
    Any `OSError` is `TREE_UNREADABLE`: a tree that cannot be read completely is never hashed or sealed partially."""
    try:
        stack = [("", root, os.lstat(root))]
        count = 0
        while stack:
            rel, path, st = stack.pop()
            count += 1
            if count > _MAX_TREE_ENTRIES:
                raise BenchmarkGateError("TREE_TOO_LARGE", f"more than {_MAX_TREE_ENTRIES} entries")
            if rel == "" and not stat.S_ISDIR(st.st_mode):
                raise BenchmarkGateError("TREE_UNREADABLE", "root is not a real directory")
            if before_dir is not None and stat.S_ISDIR(st.st_mode):
                before_dir(path, st)
            yield rel, path, st
            if stat.S_ISDIR(st.st_mode):
                with os.scandir(path) as listing:
                    names = sorted(entry.name for entry in listing)
                for name in reversed(names):
                    child = os.path.join(path, name)
                    stack.append((f"{rel}/{name}" if rel else name, child, os.lstat(child)))
    except OSError as exc:
        raise BenchmarkGateError("TREE_UNREADABLE", str(exc)) from exc


def _open_same(path: str, st: os.stat_result, flags: int) -> int:
    """Open without following a symlink and confirm it is the object `lstat` described (not swapped since)."""
    fd = os.open(path, flags | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    after = os.fstat(fd)
    if (after.st_dev, after.st_ino) != (st.st_dev, st.st_ino):
        os.close(fd)
        raise OSError("entry changed while it was being read")
    return fd


def _file_digest(path: str, st: os.stat_result, keep: int = 0) -> tuple[bytes, bytes]:
    """`(sha256 digest, first keep bytes)` of a regular file, streamed; a FIFO or device is refused, never blocked on."""
    with os.fdopen(_open_same(path, st, os.O_RDONLY), "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise OSError("not a regular file")
        digest, head = hashlib.sha256(), b""
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
            head += chunk[: max(keep - len(head), 0)]
    return digest.digest(), head


def hash_tree(root: str | os.PathLike) -> str:
    """Deterministic sha256 of a tree, taken by `compare` at the seal and again after measurement.

    Hashed, depth first in sorted order with length-prefixed fields: entry type, relative path, permission bits, and
    the file's content digest or the symlink's target. Nothing is excluded (`.pyc`, `.egg-info`, caches included:
    pytest runs with `PYTHONPYCACHEPREFIX` outside the tree and `-p no:cacheprovider`, so a write into it is the
    signal). Not hashed: timestamps, owner, xattrs, ACLs, link counts. Special files are hashed by type and mode and
    never opened. An unreadable entry is `TREE_UNREADABLE`. Residual: the walk lists by path, so a live attacker swapping
    a directory for a symlink mid-walk is caught only by the second hash differing."""
    digest = hashlib.sha256()

    def field(data: bytes) -> None:
        digest.update(b"%d:" % len(data) + data)

    for rel, path, st in _walk_tree(os.fspath(root)):
        mode = st.st_mode
        kind = b"D" if stat.S_ISDIR(mode) else b"L" if stat.S_ISLNK(mode) else b"F" if stat.S_ISREG(mode) else b"O"
        field(kind)
        field(os.fsencode(rel))
        field(b"%o" % stat.S_IMODE(mode))
        try:
            if kind == b"L":
                field(os.fsencode(os.readlink(path)))
            elif kind == b"F":
                field(_file_digest(path, st)[0])
        except OSError as exc:
            raise BenchmarkGateError("TREE_UNREADABLE", str(exc)) from exc
    return digest.hexdigest()


def _chmod_entry(path: str, st: os.stat_result, clear: int, add: int, fallback: bool = False) -> None:
    """`fchmod` through a descriptor opened without following symlinks; symlinks and special files are skipped.
    `fallback` (unseal) chmods by path when a directory is not even openable (mode 0)."""
    mode = st.st_mode
    if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
        return
    if stat.S_ISREG(mode) and st.st_nlink > 1:  # the inode is shared with a path outside the tree: never change it
        raise OSError("hard-linked file")
    new_mode = (stat.S_IMODE(mode) & ~clear) | add
    try:
        fd = _open_same(path, st, os.O_RDONLY | (getattr(os, "O_DIRECTORY", 0) if stat.S_ISDIR(mode) else 0))
    except PermissionError:
        if not fallback:
            raise
        os.chmod(path, new_mode)
        return
    try:
        os.fchmod(fd, new_mode)
    finally:
        os.close(fd)


def seal_tree(root: str | os.PathLike) -> None:
    """Remove every write bit under `root` (children before parents, symlinks untouched). `compare` seals AFTER the
    project install and the overlay: sealing before breaks `pip install -e` (verified), and sealing after then running
    pytest leaves the tree hash unchanged. Fails closed (`SEAL_FAILED`), including on a hard-linked file. A same-user
    process can `chmod` back; the hash recheck then reports it."""
    try:
        for _, path, st in reversed(list(_walk_tree(os.fspath(root)))):
            _chmod_entry(path, st, clear=0o222, add=0)
    except OSError as exc:
        raise BenchmarkGateError("SEAL_FAILED", str(exc)) from exc


def unseal_tree(root: str | os.PathLike) -> None:
    """Inverse of `seal_tree` for `cleanup`: directories `u+rwx` top-down (each listable before it is read), files `u+w`."""
    try:
        for _, path, st in _walk_tree(os.fspath(root), before_dir=lambda p, s: _chmod_entry(p, s, 0, 0o700, fallback=True)):
            if stat.S_ISREG(st.st_mode):
                try:
                    _chmod_entry(path, st, clear=0, add=0o200)
                except OSError:
                    pass  # deleting a file needs write on its directory only
    except OSError as exc:
        raise BenchmarkGateError("TREE_UNREADABLE", str(exc)) from exc


def cleanup_root(root: str | os.PathLike) -> str:
    """Remove a dispatch-unique root; return `REMOVED` / `ABSENT` or a refusal code (`CLEANUP_CODES`).

    Only if the path is a directory directly under `fixed_parent()` (so not a symlink, not elsewhere), owned by this
    user, carries a valid marker, and the marker's pid is not alive. Then `unseal_tree` (a sealed tree otherwise raises
    `PermissionError`) and `shutil.rmtree`, which on POSIX works through directory descriptors and refuses a symlink root.
    Never a name pattern. Residual: a same-user process swapping a directory for a symlink between unseal and removal."""
    try:
        path = _checked_root(root)
        marker = _read_marker(path)
    except BenchmarkGateError as exc:
        return exc.code
    if _pid_alive(marker["pid"]):
        return "OWNER_ALIVE"
    try:
        unseal_tree(path)
        shutil.rmtree(path)
    except Exception:  # noqa: BLE001 -- RecursionError on absurd nesting, OSError, BenchmarkGateError: all "not removed"
        return "REMOVE_FAILED"
    return "REMOVED"


# --- git: a private repository over the real object store ---------------------------------------------------------

def _git_env(home: str) -> dict[str, str]:
    """An environment built from nothing: no inherited `GIT_*`, no user or system config, no prompts, replace refs,
    lazy fetch or pager."""
    return {
        "PATH": "/usr/bin:/bin", "HOME": home, "XDG_CONFIG_HOME": home, "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0", "GIT_ATTR_NOSYSTEM": "1", "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_NO_LAZY_FETCH": "1", "GIT_OPTIONAL_LOCKS": "0", "GIT_LITERAL_PATHSPECS": "1", "GIT_PAGER": "cat",
    }


def _objects_dir(repo: str | os.PathLike) -> str:
    """The object directory of `repo` (work tree, bare, or linked worktree with a `gitdir:` file), found by reading
    files, not by running git in the hostile repository."""
    try:
        base = os.path.abspath(os.fspath(repo))
        gitdir, dot_git = base, os.path.join(base, ".git")
        if os.path.isdir(dot_git):
            gitdir = dot_git
        elif os.path.isfile(dot_git):
            line = _read_bounded(dot_git, 4096, nofollow=True).decode("utf-8", "surrogateescape").strip()
            if not line.startswith("gitdir:"):
                raise ValueError("unrecognised .git file")
            gitdir = os.path.normpath(os.path.join(base, line[len("gitdir:"):].strip()))
            common = os.path.join(gitdir, "commondir")
            if os.path.isfile(common):
                gitdir = os.path.normpath(os.path.join(gitdir, _read_bounded(common, 4096).decode("utf-8", "surrogateescape").strip()))
        objects = os.path.join(gitdir, "objects")
        if ":" in objects or "\n" in objects or not os.path.isdir(objects):  # the alternates variable is colon-separated
            raise ValueError("no usable git object directory")
        return objects
    except (OSError, ValueError, TypeError) as exc:
        raise BenchmarkGateError("REPO_UNREADABLE", escape_diagnostic(str(exc), 120)) from exc


def _fsize_limiter(cap: int):
    """A `preexec_fn` capping every file the child writes at `cap + 1` bytes (`resource` is POSIX-only: lazy import)."""
    def apply() -> None:
        import resource

        resource.setrlimit(resource.RLIMIT_FSIZE, (cap + 1, cap + 1))
    return apply


class _PrivateGit:
    """A throw-away bare repository with NO config, hooks, attributes, remotes or refs, whose object store is the real
    repository's, read through `GIT_ALTERNATE_OBJECT_DIRECTORIES`. Every git command run on attacker-controlled objects
    runs here, so nothing in the repository's own `.git/config` (a `filter.*` smudge, `core.fsmonitor`, a diff driver,
    `core.hooksPath`, a promisor remote) can execute, and nothing is written to the real object store. SHA-1 and
    SHA-256 repositories are told apart by the commit length."""

    def __init__(self, repo: str | os.PathLike, commit_length: int) -> None:
        self._objects = _objects_dir(repo)
        self._length = commit_length

    def __enter__(self) -> "_PrivateGit":
        self._dir = tempfile.mkdtemp(prefix="bench-git-")
        try:
            home = os.path.join(self._dir, "home")
            os.mkdir(home)
            self.gitdir = os.path.join(self._dir, "git")
            fmt = "sha1" if self._length == 40 else "sha256"
            self._run_raw(["init", "-q", "--bare", "--template=", f"--object-format={fmt}", self.gitdir], _git_env(home), self._dir)
            self.env = dict(
                _git_env(home), GIT_DIR=self.gitdir, GIT_OBJECT_DIRECTORY=os.path.join(self.gitdir, "objects"),
                GIT_ALTERNATE_OBJECT_DIRECTORIES=self._objects, GIT_INDEX_FILE=os.path.join(self._dir, "index"),
                GIT_ATTR_SOURCE=_EMPTY_TREE[self._length],  # ignore the tree's own .gitattributes (eol, ident, encodings)
            )
        except BaseException:
            shutil.rmtree(self._dir, ignore_errors=True)
            raise
        return self

    def __exit__(self, *exc_info) -> None:
        shutil.rmtree(self._dir, ignore_errors=True)

    @staticmethod
    def _run_raw(args: list, env: dict, cwd: str, cap: int | None = None) -> tuple[int, bytes]:
        # Fixed system directories, never the inherited PATH (it may hold "." or a hostile checkout).
        git = shutil.which("git", path="/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin")
        if git is None:
            raise BenchmarkGateError("GIT_FAILED", "git is not installed")
        argv = [git, "-c", "core.protectNTFS=true", "-c", "core.protectHFS=true", "-c", "core.fsmonitor=false", *args]
        kwargs = {"preexec_fn": _fsize_limiter(cap)} if cap is not None and os.name == "posix" else {}
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            try:
                proc = subprocess.run(argv, env=env, cwd=cwd, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                      timeout=_GIT_TIMEOUT_SECONDS, check=False, close_fds=True, **kwargs)
            except subprocess.TimeoutExpired as exc:
                raise BenchmarkGateError("GIT_TIMEOUT", f"git {args[0]} exceeded {_GIT_TIMEOUT_SECONDS} s") from exc
            except OSError as exc:
                raise BenchmarkGateError("GIT_FAILED", str(exc)) from exc
            out.seek(0)
            data = out.read((cap if cap is not None else _GIT_OUTPUT_CAP) + 1)
            if cap is not None and len(data) > cap:
                raise BenchmarkGateError("GIT_OUTPUT_TOO_LARGE", f"git {args[0]} wrote more than {cap} bytes")
            err.seek(0)
            return (0, data) if proc.returncode == 0 else (proc.returncode, err.read(2048))

    def run(self, *args: str | bytes, work_tree: str | None = None, cap: int | None = _GIT_OUTPUT_CAP) -> bytes:
        env = dict(self.env, GIT_WORK_TREE=work_tree) if work_tree is not None else self.env
        code, data = self._run_raw(list(args), env, self._dir, cap)
        if code != 0:
            raise BenchmarkGateError("GIT_FAILED", f"git {os.fsdecode(args[0])} exit {code}: {data.decode('utf-8', 'replace')}")
        return data

    def require_commit(self, commit: str) -> None:
        code, data = self._run_raw(["cat-file", "-t", commit], self.env, self._dir, 64)
        if code != 0 or data.strip() != b"commit":
            raise BenchmarkGateError("COMMIT_NOT_FOUND", "no such commit in the repository")


def _check_commits(*commits: object) -> int:
    """All arguments lowercase hex of ONE length (40 or 64); returns it."""
    if any(type(c) is not str or _COMMIT_RE.fullmatch(c) is None for c in commits) or len({len(c) for c in commits}) != 1:
        raise BenchmarkGateError("COMMIT_INVALID", "a commit must be 40 or 64 lowercase hex characters")
    return len(commits[0])


# --- export_tree --------------------------------------------------------------------------------------------------

def _fold_component(part: str) -> str:
    """NFC, casefolded, format characters dropped (HFS+ ignores zero-width joiners), trailing dots and spaces stripped (NTFS)."""
    folded = unicodedata.normalize("NFC", part).casefold()
    return "".join(c for c in folded if unicodedata.category(c) != "Cf").rstrip(" .")


def _parse_listing(raw: bytes) -> dict[str, tuple[str, int, bool]]:
    """`git ls-tree -r -l -z` -> `{relpath: (kind, size, executable)}`, kind `F` file / `L` symlink / `G` gitlink.
    Refuses (`EXPORT_*`) a bad path, a case or normalization collision, an unknown mode, or an oversize tree."""
    entries: dict[str, tuple[str, int, bool]] = {}
    keys: set[str] = set()
    ancestors: set[str] = set()
    total = 0
    records = raw.split(b"\0")
    if records.pop() != b"":
        raise BenchmarkGateError("GIT_FAILED", "unterminated ls-tree output")
    for record in records:
        meta, tab, raw_path = record.partition(b"\t")
        try:
            mode, otype, _object, size = meta.decode("ascii").split()
            size_value = 0 if size == "-" else int(size)
        except ValueError as exc:
            raise BenchmarkGateError("GIT_FAILED", "unparseable ls-tree record") from exc
        rel = os.fsdecode(raw_path)
        parts = rel.split("/")
        if not tab or any(p in ("", ".", "..") or _fold_component(p) in (".git", "git~1") for p in parts):
            raise BenchmarkGateError("EXPORT_PATH_REJECTED", escape_diagnostic(rel, 120))
        kind = {("100644", "blob"): "F", ("100664", "blob"): "F", ("100755", "blob"): "F", ("120000", "blob"): "L",
                ("160000", "commit"): "G"}.get((mode, otype))
        if kind is None:
            raise BenchmarkGateError("EXPORT_ENTRY_MODE", f"mode {escape_diagnostic(mode, 8)}: {escape_diagnostic(rel, 120)}")
        key = "/".join(_fold_component(p) for p in parts)
        if key in keys:
            raise BenchmarkGateError("EXPORT_PATH_COLLISION", escape_diagnostic(rel, 120))
        keys.add(key)
        ancestors.update("/".join(key.split("/")[:i]) for i in range(1, len(parts)))
        total += size_value
        entries[rel] = (kind, size_value, mode == "100755")
        if len(entries) > _MAX_TREE_ENTRIES or total > _MAX_EXPORT_BYTES:
            raise BenchmarkGateError("EXPORT_TOO_LARGE", f"over {_MAX_TREE_ENTRIES} entries or {_MAX_EXPORT_BYTES} bytes")
    if keys & ancestors:
        raise BenchmarkGateError("EXPORT_PATH_COLLISION", "a file and a directory share a name")
    return entries


def _verify_export(dest: str, entries: dict[str, tuple[str, int, bool]]) -> list[str]:
    """Walk the written tree and demand it equal the commit's listing: nothing extra or missing, every size and
    executable bit equal (this also catches a conversion that slipped past `GIT_ATTR_SOURCE` on a git too old to honour
    it), no symlink whose real target leaves `dest`. Returns the LFS-pointer paths."""
    expected_dirs = {"/".join(rel.split("/")[:i]) for rel in entries for i in range(1, rel.count("/") + 1)}
    expected_dirs |= {rel for rel, (kind, _, _) in entries.items() if kind == "G"}
    real_dest = os.path.realpath(dest)
    seen: set[str] = set()
    lfs: list[str] = []
    for rel, path, st in _walk_tree(dest):
        if rel == "":
            continue
        want = entries.get(rel)
        if stat.S_ISDIR(st.st_mode):
            if rel not in expected_dirs:
                raise BenchmarkGateError("EXPORT_VERIFY_FAILED", f"unexpected directory {escape_diagnostic(rel, 120)}")
            continue
        seen.add(rel)
        is_link = stat.S_ISLNK(st.st_mode)
        if (
            want is None or want[0] == "G" or not (is_link or stat.S_ISREG(st.st_mode)) or is_link != (want[0] == "L")
            or st.st_size != want[1] or (not is_link and bool(st.st_mode & 0o100) != want[2])
        ):
            raise BenchmarkGateError("EXPORT_VERIFY_FAILED", escape_diagnostic(rel, 120))
        if is_link:
            real = os.path.realpath(path)
            if real != real_dest and not real.startswith(real_dest + os.sep):
                raise BenchmarkGateError("EXPORT_SYMLINK_ESCAPES", escape_diagnostic(rel, 120))
        elif want[1] <= 200 and _read_bounded(path, 64, nofollow=True).startswith(_LFS_POINTER_PREFIX):
            lfs.append(rel)
    if seen != {rel for rel, (kind, _, _) in entries.items() if kind != "G"}:
        raise BenchmarkGateError("EXPORT_VERIFY_FAILED", "an entry of the commit is missing from the export")
    return lfs


def _export(repo, commit, dest, owner_pid: int | None) -> tuple[Path, dict[str, list[str]]]:
    length = _check_commits(commit)
    try:
        leaf_path = Path(os.path.abspath(os.fspath(dest)))
    except (TypeError, ValueError) as exc:
        raise BenchmarkGateError("DEST_REJECTED", "dest is not a path") from exc
    root_name, leaf = leaf_path.parent.name, leaf_path.name
    if not _ROOT_NAME_RE.fullmatch(root_name) or not _LEAF_NAME_RE.fullmatch(leaf):
        raise BenchmarkGateError("DEST_REJECTED", "dest must be <fixed parent>/<root name>/<leaf name>")
    parent = _ensure_fixed_parent()
    if os.path.realpath(leaf_path.parent.parent) != os.path.realpath(parent):
        raise BenchmarkGateError("DEST_REJECTED", f"dest must be under {parent}")
    root = os.path.join(os.path.realpath(parent), root_name)
    export_dir = os.path.join(root, leaf)
    owner = os.getpid() if owner_pid is None else owner_pid
    if type(owner) is not int or not 0 < owner < 1 << 31:
        raise BenchmarkGateError("DEST_REJECTED", "owner pid must be a positive int")

    with _PrivateGit(repo, length) as git:  # the repository is validated before anything is created
        git.require_commit(commit)
        entries = _parse_listing(git.run("ls-tree", "-r", "-l", "-z", "--full-tree", commit))
        created_root = False
        try:
            os.mkdir(root, 0o700)
            created_root = True
        except FileExistsError:
            st = os.lstat(root)
            if not stat.S_ISDIR(st.st_mode) or _foreign(st):
                raise BenchmarkGateError("DEST_REJECTED", "root exists and is not a directory of this user") from None
            _read_marker(root)  # an existing root must be one of ours
        try:
            if created_root:
                _write_marker(root, owner)
            try:
                os.mkdir(export_dir, 0o755)
            except FileExistsError:
                raise BenchmarkGateError("DEST_REJECTED", "dest already exists") from None
            git.run("read-tree", commit)
            git.run("checkout-index", "-a", "-f", work_tree=export_dir, cap=None)
            lfs = _verify_export(export_dir, entries)
            _write_json_atomic(export_dir + ".export.json", {"commit": commit, "entries": len(entries)})
        except BaseException:
            shutil.rmtree(export_dir, ignore_errors=True)
            if created_root:
                shutil.rmtree(root, ignore_errors=True)
            raise
    return Path(export_dir), {"gitlinks": sorted(r for r, e in entries.items() if e[0] == "G"), "lfs_pointers": lfs}


def export_tree(repo: str | os.PathLike, commit: str, dest: str | os.PathLike, *, owner_pid: int | None = None) -> Path:
    """Export the tree of `commit` into `dest` and return `dest`. Raises `BenchmarkGateError`.

    `commit` is 40 or 64 lowercase hex. `dest` is `<fixed_parent()>/<root>/<leaf>` and must not exist; the root
    (`[A-Za-z0-9][A-Za-z0-9_-]{7,63}`, caller-chosen, dispatch-unique) is created mode 0700 with a marker holding
    `owner_pid` (default: this process) and a timestamp, or reused after its marker validates (the second export of a
    dispatch). `dest` is left WRITABLE: the install and the overlay still run; `compare` seals and hashes afterwards.

    Built by `git read-tree` into a private index plus `git checkout-index` inside a `_PrivateGit` (never `git archive`,
    which honours `export-ignore`/`export-subst`): no `.git`, no hooks, no filters, no LFS, no network. A plain
    checkout-index applied the tree's own `.gitattributes` (`eol=crlf` rewrote every line ending, `ident` rewrote
    `$Id$`), so `GIT_ATTR_SOURCE` points at the empty tree and `_verify_export` rechecks every size. A submodule becomes
    an EMPTY directory and an LFS pointer stays pointer text (both named by the CLI on stderr). A symlink is written as a
    symlink and the export is REFUSED if any resolves outside `dest` (stricter than "never follow": a legitimate absolute
    symlink fails closed); unsafe or colliding paths and oversize trees are refused too. A sidecar `<leaf>.export.json`
    beside `dest` records the commit so `overlay_benchmark_file` can bind `base_ref_commit` to it. On failure `dest`
    (and a root this call created) is removed."""
    return _export(repo, commit, dest, owner_pid)[0]


# --- overlay_benchmark_file ---------------------------------------------------------------------------------------

_validate_task_target_module = None


def _load_validate_task_target():
    """Load the sibling `validate_task_target.py` by path (scripts/ ships wholesale but is not a package)."""
    global _validate_task_target_module
    if _validate_task_target_module is None:
        name = "_bg_validate_task_target"
        spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name("validate_task_target.py"))
        try:
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        except Exception as exc:
            sys.modules.pop(name, None)
            raise BenchmarkGateError("OVERLAY_REJECTED", "cannot load validate_task_target") from exc
        _validate_task_target_module = module
    return _validate_task_target_module


def _exact_entry(root: str, rel: str) -> os.stat_result | None:
    """`lstat` of `root/rel`, found by listing each directory and comparing names EXACTLY (a case-folding filesystem
    must not report `Bench_X.py` present when only `bench_x.py` is); `None` when absent; a non-directory parent raises."""
    current = root
    parts = rel.split("/")
    for index, part in enumerate(parts):
        if part not in os.listdir(current):
            return None
        current = os.path.join(current, part)
        st = os.lstat(current)
        if index < len(parts) - 1 and not stat.S_ISDIR(st.st_mode):
            raise BenchmarkGateError("OVERLAY_REJECTED", "a parent of the benchmark is a symlink or not a directory")
    return st


def overlay_benchmark_file(
    base_root: str | os.PathLike, head_root: str | os.PathLike, base_ref_commit: str, path: str
) -> Literal["PRE_EXISTING", "BUILDER_AUTHORED"]:
    """Make the head's benchmark exist in the base export and say where it came from.

    `path` must pass `_benchmark_path_ok` and the merged `validate_task_target(head_root, path)`; the head file must be a
    regular non-symlink file of at most 16 KiB with no symlinked parent. Pre-existence is decided from the BASE EXPORT's
    own listing (exact names), as the design row says; `base_ref_commit` is bound to that export through the sidecar
    `export_tree` wrote (a mismatch is `OVERLAY_REJECTED`), so the listing is provably that commit's. Present: bytes must
    equal head's else `BENCHMARK_MODIFIED`, origin `PRE_EXISTING`. Absent: parents are created inside `base_root` only, the
    file is written `O_EXCL`/`O_NOFOLLOW` mode 0644, origin `BUILDER_AUTHORED`. Residual: a build hook that ran during the
    base install could have created the file and reads as `PRE_EXISTING`; the Orchestrator re-derives the origin with
    `git cat-file -e <base>:<path>`. Raises `BenchmarkGateError` (`OVERLAY_REJECTED`, `BENCHMARK_MODIFIED`, `COMMIT_INVALID`)."""
    _check_commits(base_ref_commit)

    def reject(why: str) -> BenchmarkGateError:
        return BenchmarkGateError("OVERLAY_REJECTED", why)

    if type(path) is not str or not _benchmark_path_ok(path):
        raise reject("path is not an acceptable benchmark path")
    try:
        base, head = os.path.realpath(os.fspath(base_root)), os.path.realpath(os.fspath(head_root))
        if (base == head or not os.path.isdir(base) or not os.path.isdir(head)
                or head.startswith(base + os.sep) or base.startswith(head + os.sep)):
            raise reject("the two roots must be distinct, separate directories")
        try:
            sidecar = json.loads(_read_bounded(base + ".export.json", 4096, nofollow=True).decode("ascii"))
        except (OSError, ValueError):
            sidecar = None
        if not isinstance(sidecar, dict) or sidecar.get("commit") != base_ref_commit:
            raise reject("base_root is not an export of base_ref_commit")
        if _load_validate_task_target().validate_task_target(head, path) is None:
            raise reject("validate_task_target rejected the path")
        head_stat = _exact_entry(head, path)
        if head_stat is None or not stat.S_ISREG(head_stat.st_mode) or head_stat.st_size > _MAX_BENCHMARK_BYTES:
            raise reject("head benchmark is missing, not a regular file, or over 16 KiB")
        content = _read_bounded(os.path.join(head, path), _MAX_BENCHMARK_BYTES, nofollow=True)
        base_stat = _exact_entry(base, path)
        if base_stat is not None:
            if not stat.S_ISREG(base_stat.st_mode):
                raise reject("the base entry is not a regular file")
            if _read_bounded(os.path.join(base, path), _MAX_BENCHMARK_BYTES, nofollow=True) != content:
                raise BenchmarkGateError("BENCHMARK_MODIFIED", "the benchmark exists at base with different bytes")
            return "PRE_EXISTING"
        directory = base
        for part in path.split("/")[:-1]:
            directory = os.path.join(directory, part)
            if not os.path.lexists(directory):
                os.mkdir(directory, 0o755)
            elif not stat.S_ISDIR(os.lstat(directory).st_mode):
                raise reject("a parent of the benchmark is a symlink or not a directory")
        target = os.path.join(base, path)
        if os.path.realpath(target) != target:
            raise reject("the target resolves outside base_root")
        with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644), "wb") as handle:
            handle.write(content)
            os.fchmod(handle.fileno(), 0o644)
        return "BUILDER_AUTHORED"
    except (OSError, ValueError) as exc:
        raise reject(escape_diagnostic(str(exc), 120)) from exc


# --- protected-path diff and token tripwire -----------------------------------------------------------------------

_PROTECTED_BASENAMES = frozenset({
    "conftest.py", "pytest.ini", "pyproject.toml", "setup.cfg", "setup.py", "tox.ini", "noxfile.py", "manifest.in",
    "environment.yml", "poetry.lock", "uv.lock", "pdm.lock", "pylock.toml",
})
_STARTUP_STEMS = ("sitecustomize", "usercustomize")
_MAX_DIFF_ENTRIES = 50_000
_MAX_TRIPWIRE_FILES = 500
_TRIPWIRE_FILE_CAP = 4 << 20
_TRIPWIRE_TOTAL_CAP = 32 << 20
_TRIPWIRE_TOKENS = (b"PYTEST_CURRENT_TEST", b"BENCH_RESULT_DIGEST", b"BENCH_TRACE_LINES", b"os._exit", b"sys.argv")


def _is_protected(rel: str, benchmark_path: str, stdlib_names: frozenset[str]) -> bool:
    """One changed path against the design's protected list, compared NFC-casefolded (a case-insensitive filesystem
    makes `Conftest.PY` and `JSON.py` the same files)."""
    folded = unicodedata.normalize("NFC", rel).casefold()
    parts = folded.split("/")
    base = parts[-1]
    if (
        base in _PROTECTED_BASENAMES
        or base.endswith((".pth", ".pyc", ".in"))
        or (base.startswith(("requirements", "constraints")) and base.endswith(".txt"))
        or (len(parts) > 1 and parts[-2] == "requirements" and base.endswith(".txt"))
        or base.startswith("pipfile")
        or (base.startswith("pylock.") and base.endswith(".toml"))  # PEP 751 `pylock.<name>.toml` (beyond the list)
        or "__pycache__" in parts
        or any(part.startswith(_STARTUP_STEMS) and (i < len(parts) - 1 or part.endswith((".py", ".pyi", ".so", ".pyd")))
               for i, part in enumerate(parts))
    ):
        return True
    # Could shadow a standard-library module once installed: a module or package at the root or directly under `src/`
    # (an editable install puts `src` on `sys.path`); `.so`/`.pyd` shadow too. `test` and `types` are stdlib names, so a
    # top-level `test/` directory has every change under it protected, per the design.
    importable = [(parts[0], len(parts) == 1)] + ([(parts[1], len(parts) == 2)] if parts[0] == "src" and len(parts) > 1 else [])
    for name, is_file in importable:
        stem, _, extension = name.partition(".")
        if (is_file and extension.rpartition(".")[2] in ("py", "so", "pyd") and stem in stdlib_names) or (
            not is_file and name in stdlib_names
        ):
            return True
    return rel != benchmark_path and folded.startswith(posixpath.dirname(benchmark_path).casefold() + "/")


def _changed_paths(git: "_PrivateGit", base_commit: str, head_commit: str) -> list[tuple[str, bytes]]:
    git.require_commit(base_commit)
    git.require_commit(head_commit)
    raw = git.run("diff", "--name-status", "-z", "--no-renames", "--no-ext-diff", "--no-textconv", base_commit, head_commit, "--",
                  cap=16 << 20)
    fields = raw.split(b"\0")
    if fields.pop() != b"" or len(fields) % 2 or len(fields) // 2 > _MAX_DIFF_ENTRIES:
        raise BenchmarkGateError("PROTECTED_DIFF_FAILED", "unparseable or oversize diff output")
    return [(fields[i].decode("ascii", "replace"), fields[i + 1]) for i in range(0, len(fields), 2)]


def protected_path_changes(repo, base_commit: str, head_commit: str, benchmark_path: str) -> list[str]:
    """Protected paths that differ between the two commits (the `compare` row's list); empty means none.

    `git diff --name-status -z --no-renames` in a `_PrivateGit`: rename detection is OFF (moving `conftest.py` is a delete
    plus an add), `-z` keeps spaces, newlines and non-ASCII intact, no external diff or textconv runs. Protected: any
    `conftest.py`; any path component starting `sitecustomize`/`usercustomize`; `*.pth`, `*.pyc`, `*.in`, `__pycache__`;
    `pytest.ini`, `pyproject.toml`, `setup.cfg`, `setup.py`, `tox.ini`, `noxfile.py`, `MANIFEST.in`, `requirements*.txt`,
    `requirements/*.txt`, `constraints*.txt`, `environment.yml`, `Pipfile*`, `poetry.lock`, `uv.lock`, `pdm.lock`,
    `pylock.toml`; a root-level or `src/`-level module or package named like a standard-library one; and any path under the
    benchmark's directory other than the benchmark (descendants too, a deliberate widening: `from benchmarks.sub import x`
    passes the lint). A path ADDED, MODIFIED, mode- or type-changed or DELETED counts (deleting a base `conftest.py` changes
    what is collected; the design says "added or changed"). `benchmark_path` is a fourth argument the design's
    three-argument signature lacks, needed for the directory rule. Returns unique paths sorted by bytes. Known false
    positive, per the design: `test` and `types` are standard-library names, so a repository with a top-level `test/`
    directory has every change under it protected."""
    length = _check_commits(base_commit, head_commit)
    if type(benchmark_path) is not str or not _benchmark_path_ok(benchmark_path):
        raise BenchmarkGateError("PROTECTED_DIFF_FAILED", "benchmark_path is not an acceptable benchmark path")
    stdlib = frozenset(name.casefold() for name in sys.stdlib_module_names)
    with _PrivateGit(repo, length) as git:
        changed = _changed_paths(git, base_commit, head_commit)
    paths = (os.fsdecode(raw) for _, raw in sorted(changed, key=lambda item: item[1]))
    return [path for path in paths if _is_protected(path, benchmark_path, stdlib)]


def benchmark_aware_tokens(repo, base_commit: str, head_commit: str, benchmark_path: str) -> list[str]:
    """Token tripwire: ADDED lines of every changed file other than the benchmark containing `PYTEST_CURRENT_TEST`,
    `BENCH_RESULT_DIGEST`, `BENCH_TRACE_LINES`, `os._exit`, `sys.argv` or the benchmark's own path; `compare` maps a
    non-empty result to `BENCHMARK_AWARE_CODE` (a match may be innocent, so the human sees the lines). Entries are
    `"<path>: <token>: <line>"`, escaped and truncated.

    One `git diff -a -U0` per changed file (`-a` forces a text diff of binary files, so they are scanned as bytes, not
    skipped; `GIT_LITERAL_PATHSPECS` plus `--` make a `-`-prefixed name safe). Bytes are never decoded. Bounded and failing
    closed: over 500 changed files, a diff over 4 MiB, or 32 MiB in total raises `TRIPWIRE_LIMIT`. Deleted files have no
    added lines. A token split across lines or built at run time passes (a tripwire, not a proof)."""
    length = _check_commits(base_commit, head_commit)
    if type(benchmark_path) is not str or not _benchmark_path_ok(benchmark_path):
        raise BenchmarkGateError("TRIPWIRE_LIMIT", "benchmark_path is not an acceptable benchmark path")
    tokens = (*_TRIPWIRE_TOKENS, benchmark_path.encode("ascii"))
    hits: list[str] = []
    total = 0
    with _PrivateGit(repo, length) as git:
        changed = [(s, p) for s, p in _changed_paths(git, base_commit, head_commit)
                   if not s.startswith("D") and os.fsdecode(p) != benchmark_path]
        if len(changed) > _MAX_TRIPWIRE_FILES:
            raise BenchmarkGateError("TRIPWIRE_LIMIT", f"more than {_MAX_TRIPWIRE_FILES} changed files")
        for _, raw_path in sorted(changed, key=lambda item: item[1]):
            try:
                out = git.run("diff", "-a", "-U0", "--no-renames", "--no-ext-diff", "--no-textconv", "--no-color",
                              base_commit, head_commit, "--", raw_path, cap=_TRIPWIRE_FILE_CAP)
            except BenchmarkGateError as exc:
                if exc.code != "GIT_OUTPUT_TOO_LARGE":
                    raise
                raise BenchmarkGateError("TRIPWIRE_LIMIT", "a file's diff is over 4 MiB") from exc
            total += len(out)
            if total > _TRIPWIRE_TOTAL_CAP:
                raise BenchmarkGateError("TRIPWIRE_LIMIT", "the diffs total over 32 MiB")
            in_hunk = False
            for line in out.split(b"\n"):
                if line.startswith(b"@@"):
                    in_hunk = True
                elif in_hunk and line.startswith(b"+"):
                    hits += [f"{escape_diagnostic(os.fsdecode(raw_path), 120)}: {token.decode('ascii')}: "
                             f"{escape_diagnostic(line[1:121].decode('ascii', 'replace'), 120)}" for token in tokens if token in line]
    return hits


# --- venv snapshot and the .pth / startup-file content check ------------------------------------------------------

VENV_VIOLATION_CODES = (  # canonical order
    "SNAPSHOT_INVALID",         # before or after is not a well-formed snapshot
    "PTH_IMPORT_LINE",          # a new `import ...` line that is not a recognised editable-finder form
    "PTH_PATH_OUTSIDE_EXPORT",  # a new path line that is relative, has `..`, or resolves outside the export
    "PTH_PATH_NOT_DIRECTORY",   # a new path line that is not an existing directory (this includes `<path>; code`)
    "PTH_BAD_ENCODING",         # a new .pth with a NUL byte or invalid UTF-8
    "PTH_UNREADABLE",           # a new .pth whose content was too large to snapshot
    "VENV_ENTRY_NOT_REGULAR",   # a new watched entry that is a symlink, directory or special file
    "STARTUP_FILE_ADDED",       # a new or changed `sitecustomize*` / `usercustomize*` entry
)
_SNAPSHOT_CONTENT_CAP = 4096
_MAX_SNAPSHOT_ENTRIES = 1000
_EDITABLE_FINDER_RE = re.compile(r"import (__editable___\w+_finder); \1\.install\(\)", re.ASCII)
_EDITABLE_IMPL_RE = re.compile(r"import _editable_impl_\w+", re.ASCII)


def snapshot_venv(bin_dir: str | os.PathLike) -> dict:
    """Snapshot the files of a venv that run code at interpreter start, executing nothing in it.

    `bin_dir` is the venv's `bin` directory with `pyvenv.cfg` one level up. Format: `{"format": 1, "files": {<path
    relative to the venv root>: <entry>}}`, an entry being `{"kind": "file", "size": n, "sha256": hex, "hex": <first 4096
    bytes as hex, or null if larger>}`, `{"kind": "symlink", "target": text}`, `{"kind": "dir"}` or `{"kind": "other"}`.
    Watched, in each `site-packages`: names ending `.pth` and names starting `sitecustomize` or `usercustomize`
    (case-insensitive). Each `site-packages` must resolve inside the venv (`lib64 -> lib` is deduplicated). An unreadable
    file or more than 1000 watched entries is `SNAPSHOT_FAILED` (fail closed)."""
    try:
        venv = os.path.realpath(os.path.dirname(os.path.abspath(os.fspath(bin_dir))))
        if not stat.S_ISREG(os.lstat(os.path.join(venv, "pyvenv.cfg")).st_mode):
            raise BenchmarkGateError("SNAPSHOT_FAILED", "pyvenv.cfg is not a regular file")
        sites: list[str] = []
        for lib in ("lib", "lib64", "Lib"):
            lib_path = os.path.join(venv, lib)
            if not os.path.isdir(lib_path):
                continue
            candidates = [os.path.join(lib_path, "site-packages")]
            candidates += [os.path.join(lib_path, n, "site-packages") for n in sorted(os.listdir(lib_path)) if n.startswith("python")]
            for candidate in filter(os.path.isdir, candidates):
                real = os.path.realpath(candidate)
                if not real.startswith(venv + os.sep):
                    raise BenchmarkGateError("SNAPSHOT_FAILED", "a site-packages directory resolves outside the venv")
                if not any(os.path.samefile(real, seen) for seen in sites):  # `lib64 -> lib`; `Lib` is `lib` on macOS
                    sites.append(real)
        files: dict[str, dict] = {}
        for site in sorted(sites):
            for name in sorted(os.listdir(site)):
                if not (name.casefold().endswith(".pth") or name.casefold().startswith(_STARTUP_STEMS)):
                    continue
                if len(files) >= _MAX_SNAPSHOT_ENTRIES:
                    raise BenchmarkGateError("SNAPSHOT_FAILED", "too many watched entries")
                path = os.path.join(site, name)
                st = os.lstat(path)
                if stat.S_ISREG(st.st_mode):
                    digest, head = _file_digest(path, st, _SNAPSHOT_CONTENT_CAP)
                    entry = {"kind": "file", "size": st.st_size, "sha256": digest.hex(),
                             "hex": head.hex() if st.st_size <= _SNAPSHOT_CONTENT_CAP else None}
                elif stat.S_ISLNK(st.st_mode):
                    entry = {"kind": "symlink", "target": os.readlink(path)}
                else:
                    entry = {"kind": "dir" if stat.S_ISDIR(st.st_mode) else "other"}
                files[os.path.relpath(path, venv).replace(os.sep, "/")] = entry
    except OSError as exc:
        raise BenchmarkGateError("SNAPSHOT_FAILED", str(exc)) from exc
    return {"format": 1, "files": files}


def load_snapshot(path: str | os.PathLike) -> dict:
    """Read a `snapshot-venv` file (regular file, at most 16 MiB). `SNAPSHOT_FAILED` if unreadable, oversize or not JSON;
    structural validation is `venv_addition_violations`'s job."""
    try:
        raw = _read_bounded(os.fspath(path), 16 << 20)
        if len(raw) > 16 << 20:
            raise ValueError("snapshot too large")
        return json.loads(raw.decode("utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise BenchmarkGateError("SNAPSHOT_FAILED", escape_diagnostic(str(exc), 120)) from exc


def _pth_lines(entry: object) -> list[str] | None:
    """The lines of a snapshot `.pth` entry as `site.py` splits them, or `None` without usable text (NUL, bad UTF-8)."""
    try:
        text = bytes.fromhex(entry["hex"]).decode("utf-8-sig")  # site.py reads .pth files as utf-8-sig
    except (KeyError, TypeError, ValueError):
        return None
    return None if "\0" in text else re.split(r"\r\n|\r|\n", text)


def venv_addition_violations(before: object, after: object, export_root: str | os.PathLike) -> list[str]:
    """Judge what the project install added to a venv; return `VENV_VIOLATION_CODES` (empty means acceptable).

    `before` is the `snapshot_venv` taken after the venv was created and BEFORE the install, `after` one taken now,
    `export_root` this side's export. A new or changed watched entry is judged by CONTENT (revision 4's filename allowlist
    rejected hatchling, pdm, flit and poetry editable installs): `sitecustomize*`/`usercustomize*` is always a violation; a
    symlink, directory or special file is a violation; a `.pth` must be UTF-8 without NUL, and each NEW line (blank lines
    and `#` comments ignored, as `site.py` does) must be an ABSOLUTE path without `..` whose real path is an existing
    directory inside `export_root`, or an editable-finder line, `import __editable___<pkg>_finder;
    __editable___<pkg>_finder.install()` (setuptools) or `import _editable_impl_<pkg>`. Any other line `site.py` would execute
    (`import ` or `import<TAB>`; `a1_coverage.pth` from pytest-cov) is rejected, as is `<path>; code` (not a directory).
    Removed entries are ignored. Known over-rejection: setuptools' `distutils-precedence.pth` (an import line) fails if a
    dependency pulls setuptools in; the design lists no exemption. Residual: code reached by other means (a build backend's own
    hooks) is outside every in-process control."""
    def files(snapshot: object) -> dict | None:
        table = snapshot.get("files") if isinstance(snapshot, dict) and snapshot.get("format") == 1 else None
        ok = isinstance(table, dict) and all(
            isinstance(k, str) and isinstance(v, dict) and v.get("kind") in ("file", "symlink", "dir", "other") for k, v in table.items()
        )
        return table if ok else None

    old, new = files(before), files(after)
    if old is None or new is None:
        return ["SNAPSHOT_INVALID"]
    found: set[str] = set()
    export_real = os.path.realpath(os.fspath(export_root))
    for key, entry in new.items():
        if old.get(key) == entry:
            continue
        if key.rsplit("/", 1)[-1].casefold().startswith(_STARTUP_STEMS):
            found.add("STARTUP_FILE_ADDED")
        elif entry["kind"] != "file":
            found.add("VENV_ENTRY_NOT_REGULAR")
        elif not isinstance(entry.get("hex"), str):
            found.add("PTH_UNREADABLE")
        elif (lines := _pth_lines(entry)) is None:
            found.add("PTH_BAD_ENCODING")
        else:
            known = set(_pth_lines(old[key]) or []) if old.get(key, {}).get("kind") == "file" else set()
            for line in (raw.rstrip() for raw in lines):
                if not line or line.startswith("#") or line in known:
                    continue
                if line.startswith(("import ", "import\t")):
                    if _EDITABLE_FINDER_RE.fullmatch(line) is None and _EDITABLE_IMPL_RE.fullmatch(line) is None:
                        found.add("PTH_IMPORT_LINE")
                    continue
                try:
                    real = os.path.realpath(line)
                except (OSError, ValueError):
                    real = ""
                if not os.path.isabs(line) or ".." in line.replace("\\", "/").split("/") or not (
                    real == export_real or real.startswith(export_real + os.sep)
                ):
                    found.add("PTH_PATH_OUTSIDE_EXPORT")
                elif not os.path.isdir(real):
                    found.add("PTH_PATH_NOT_DIRECTORY")
    return sorted(found, key=VENV_VIOLATION_CODES.index)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_MAX_INPUT_BYTES = 1 << 20


def gate_sha256(normalized_gate: dict) -> str:
    """sha256 of the canonical JSON of a normalized gate (the Orchestrator recomputes it)."""
    canonical = json.dumps(normalized_gate, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _read_bounded(path: str, limit: int, nofollow: bool = False) -> bytes:
    """Read at most ``limit + 1`` bytes of a REGULAR file; the caller treats ``len > limit`` as too large.

    A bounded read rather than ``stat().st_size``: a size taken before the read is not a cap, and a FIFO or a
    device (``/dev/zero``) reports no useful size. The file is opened ``O_NONBLOCK`` (where the platform has it)
    so opening a FIFO with no writer cannot hang, then ``fstat`` on the opened descriptor must say regular file.
    ``nofollow`` refuses a symlink as the final component (``O_NOFOLLOW``), for files inside a tree under test.
    Raises ``OSError`` or ``ValueError``; both are usage errors to the CLI.
    """
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | (getattr(os, "O_NOFOLLOW", 0) if nofollow else 0))
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
    oversize, non-regular (a pipe or ``/dev/stdin`` is refused on purpose), non-UTF-8, malformed or too deeply
    nested input is a usage error with nothing on stdout.
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


def _fail(exc: BenchmarkGateError) -> int:
    """A refusal of hostile tree content is a verdict (code on stdout, exit 1); every other failure is exit 2."""
    if exc.code in EXPORT_REFUSAL_CODES:
        print(exc.code)
        print(f"detail: {escape_diagnostic(exc.detail, 200)}", file=sys.stderr)
        return 1
    print(f"usage error: {exc.code}: {escape_diagnostic(exc.detail, 200)}", file=sys.stderr)
    return 2


def _cmd_export(args: argparse.Namespace) -> int:
    """Export one commit. Exit 0 and the path on stdout; 1 and a code on stdout when the tree is refused
    (``EXPORT_REFUSAL_CODES``); 2 for a bad commit or destination, a missing commit, an unreadable repository or a
    git failure. Gitlinks (left as EMPTY directories) and LFS pointers (left unresolved) are named on stderr."""
    try:
        dest, notes = _export(args.repo, args.commit, args.dest, args.owner_pid)
    except BenchmarkGateError as exc:
        return _fail(exc)
    except (OSError, ValueError) as exc:
        print(f"usage error: cannot export: {escape_diagnostic(str(exc), 200)}", file=sys.stderr)
        return 2
    print(dest)
    for key, label in (("gitlinks", "submodule left as an empty directory"), ("lfs_pointers", "LFS pointer left unresolved")):
        if notes[key]:
            print(f"note: {label}: {escape_diagnostic(', '.join(notes[key][:5]), 200)} ({len(notes[key])} total)", file=sys.stderr)
    return 0


def _cmd_snapshot_venv(args: argparse.Namespace) -> int:
    """Write ``snapshot_venv(--bin)`` to ``--out`` (atomically). Exit 0, or 2 on any failure (fail closed)."""
    try:
        _write_json_atomic(args.out, snapshot_venv(args.bin))
    except BenchmarkGateError as exc:
        return _fail(exc)
    except (OSError, ValueError) as exc:
        print(f"usage error: cannot snapshot: {escape_diagnostic(str(exc), 200)}", file=sys.stderr)
        return 2
    return 0


def _cmd_cleanup(args: argparse.Namespace) -> int:
    """Remove one dispatch-unique root. The result code is printed on stdout: exit 0 for ``REMOVED``/``ABSENT``, 1
    for a refusal (``CLEANUP_CODES``)."""
    code = cleanup_root(args.root)
    print(code)
    return 0 if code in ("REMOVED", "ABSENT") else 1


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``validate`` (C4a), ``lint`` (C4b), ``export``, ``snapshot-venv`` and ``cleanup`` (C4c). Later
    PRs add ``compare`` and ``run-once`` by adding a subparser with ``set_defaults(func=...)``. There is no catch-all
    here on purpose: C4d owns the exit-code contract for a crash."""
    parser = argparse.ArgumentParser(prog="benchmark_gate.py", description="Benchmark gate (C4a-C4c).")
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
    export = sub.add_parser("export", help="export a commit's tree (exit 0, 1 refused, 2 usage)")
    export.add_argument("--repo", required=True, metavar="DIR")
    export.add_argument("--commit", required=True, metavar="SHA")
    export.add_argument("--dest", required=True, metavar="DIR", help="<fixed parent>/<root>/<leaf>; must not exist")
    export.add_argument("--owner-pid", type=int, metavar="PID", help="pid recorded in the root's marker (default: this process)")
    export.set_defaults(func=_cmd_export)
    snap = sub.add_parser("snapshot-venv", help="snapshot a venv's .pth and startup files (run BEFORE the project install)")
    snap.add_argument("--bin", required=True, metavar="DIR")
    snap.add_argument("--out", required=True, metavar="FILE")
    snap.set_defaults(func=_cmd_snapshot_venv)
    cleanup = sub.add_parser("cleanup", help="remove a dispatch-unique root (exit 0 removed/absent, 1 refused)")
    cleanup.add_argument("--root", required=True, metavar="DIR")
    cleanup.set_defaults(func=_cmd_cleanup)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse exits 2 on usage errors (and 0 on --help)
        return exc.code if isinstance(exc.code, int) else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
