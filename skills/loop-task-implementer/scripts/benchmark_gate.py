#!/usr/bin/env python3
"""Validation, lint and statistics core of the performance-review -> loop-task-implementer benchmark gate (Epic C).

**This module is not wired into anything yet.** It is delivered by a series of eight PRs for gap-backlog ticket
C4 (C4a core, C4b lint, C4c-1a export, C4c-1b seal/cleanup, C4c-2 overlay/diff/venv check, C4d harness, C4e classifier/docs, C4f wiring); no workflow file,
lifecycle validator or other script calls it until C4f. So far it holds the pure, string-level and arithmetic
pieces (``validate``, ``lint``) and the first part of C4c (C4c-1a): ``export``, ``fixed-parent`` and the library
function ``export_tree``. C4c-1b adds ``seal_tree``, ``unseal_tree`` and ``cleanup``; C4c-2 adds the tree hash, the
benchmark overlay, the protected-path diff, the token tripwire and the venv ``.pth`` check with ``snapshot-venv``; C4d adds measurement, the trace, ``compare`` and ``run-once``, C4e
the classifier and docs, C4f the workflow wiring. Specification (revision 5, the converged result of four review
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
import errno
import hashlib
import io
import json
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
    reference ``Order.__eq__`` and the task would loop on an unfixable lint rejection."""
    return (
        isinstance(name, str)
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
_DENIED_COMPONENTS = frozenset({".git", ".ssh", ".aws", ".kube", ".docker", ".gnupg"})
_DENIED_NAMES_EXACT = frozenset(
    {".netrc", ".npmrc", ".htpasswd", ".pgpass", ".pypirc", ".git-credentials"}
)
_DENIED_NAME_PREFIXES = (
    ".env", "credentials", "kubeconfig", "terraform.tfstate",
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
)
_DENIED_SUFFIXES = (
    ".pem", ".key", ".p12", ".pfx", ".p8", ".jks", ".keystore", ".tfvars", ".tfstate",
)


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
    elif len(top_level_tests) != 1:
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
    (``SYMBOL_INVALID``) are rejected.

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
# C4c-1a: export
#
# Runs on attacker-influenced input (a Builder's commit, a tree the code under test wrote into): argv lists only, a
# scrubbed environment, bounded subprocesses, validated paths, no symlink followed out of a root. POSIX only.
# ---------------------------------------------------------------------------

# Stable ASCII codes. A refusal of hostile tree content is a verdict (CLI: stdout, exit 1); the rest are failures (exit 2).
EXPORT_REFUSAL_CODES = (
    "EXPORT_PATH_REJECTED",     # a `.`/`..`/empty component or a `.git` lookalike
    "EXPORT_PATH_COLLISION",    # two paths equal after NFC + casefold, or a file/directory clash that way
    "EXPORT_ENTRY_MODE",        # not a regular file, symlink or gitlink
    "EXPORT_TOO_LARGE",         # over 100,000 entries (files and directories) or 1 GiB of blobs
    "EXPORT_SYMLINK_ESCAPES",   # a symlink whose real target is outside the export
    "EXPORT_VERIFY_FAILED",     # the written tree differs from the commit's listing
)
ERROR_CODES = (  # MARKER_MISSING / MARKER_INVALID are also `cleanup` codes (C4c-1b): the same condition seen by `cleanup`
    "COMMIT_INVALID", "COMMIT_NOT_FOUND", "REPO_UNREADABLE", "DEST_REJECTED", "GIT_FAILED", "GIT_TOO_OLD", "GIT_TIMEOUT",
    "GIT_OUTPUT_TOO_LARGE", "TREE_UNREADABLE", "TREE_TOO_LARGE", "MARKER_MISSING", "MARKER_INVALID",
)

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
_GIT_MINIMUM = (2, 43)  # GIT_ATTR_SOURCE; older git silently applies the tree's own .gitattributes
_git_version: tuple[int, int] | None = None
_LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1\n"


class BenchmarkGateError(Exception):
    """A refusal or failure of a C4c helper: `code` is one of the stable codes above. `detail` may carry attacker-influenced
    text (git stderr, an OSError message, a file name), so it is escaped HERE, once: printable ASCII, no backticks or newlines."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = escape_diagnostic(detail, 200)


# --- the fixed parent, the dispatch-unique root and its marker ----------------------------------------------------

def fixed_parent() -> Path:
    """The only directory `export` creates roots in and `cleanup` (C4c-1b) removes them from:
    `<tempfile.gettempdir()>/software-builder-bench-<uid>` (plain name without a uid), fixed so containment is a `realpath`
    comparison, never a name pattern (a pattern delete could hit another live task's root; `task_lease` allows concurrent
    Orchestrators on one host). The per-user name does NOT stop another user who already owns that name from making `export`
    and `cleanup` refuse (`DEST_REJECTED` / `NOT_UNDER_FIXED_PARENT`): a safe refusal, not a takeover. Derived from `TMPDIR` at
    call time: the cleaning process must use the exporter's `TMPDIR`. CLI: `fixed-parent`. Residual: the parent is validated
    BY PATH above the dispatch root; a same-uid process can redirect it between check and use, gaining no capability (it can
    already write, chmod and delete those directories). Everything below a root is handled by descriptor."""
    suffix = f"-{os.getuid()}" if hasattr(os, "getuid") else ""
    return Path(tempfile.gettempdir()) / (_ROOT_PARENT_NAME + suffix)


def _foreign(st: os.stat_result) -> bool:
    return hasattr(os, "getuid") and st.st_uid != os.getuid()


def _check_parent(create: bool) -> Path:
    """The fixed parent, which must be a real directory of ours that others cannot write (created 0700 if `create`).
    `ABSENT` when it does not exist and `create` is false; `DEST_REJECTED` for anything else wrong with it."""
    parent = fixed_parent()
    if create:
        try:
            os.mkdir(parent, 0o700)
        except FileExistsError:
            pass
        except OSError as exc:
            raise BenchmarkGateError("DEST_REJECTED", f"cannot create the fixed parent: {exc}") from exc
    try:
        st = os.lstat(parent)  # lstat: a symlink planted at the fixed parent is not a directory
    except OSError as exc:
        raise BenchmarkGateError("ABSENT" if isinstance(exc, FileNotFoundError) else "DEST_REJECTED", f"fixed parent: {exc}") from exc
    if not stat.S_ISDIR(st.st_mode) or st.st_mode & 0o022 or _foreign(st):
        raise BenchmarkGateError("DEST_REJECTED", "fixed parent is not a private directory owned by this user")
    return parent


def _check_pid(pid: object) -> int:
    if type(pid) is not int or not 0 < pid < 1 << 31:
        raise BenchmarkGateError("DEST_REJECTED", "owner pid must be a positive int below 2**31")
    return pid


def _write_json_atomic(path: str, payload: dict) -> None:
    tmp = f"{path}.{os.getpid()}.tmp"  # O_EXCL + O_NOFOLLOW, then rename: a reader sees all of it or none
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    except FileExistsError as exc:  # a stale file of ours from a crashed run: never overwritten, never removed here
        raise BenchmarkGateError("DEST_REJECTED", "a stale temp file blocks the write; remove it") from exc
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(json.dumps(payload, sort_keys=True).encode("ascii"))
        os.replace(tmp, path)
    except BaseException:
        if os.path.lexists(tmp):
            os.unlink(tmp)
        raise


def _write_marker(root: str, owner_pid: int, name: str | None = None) -> None:
    """Write the marker (validating the pid first, so a bad pid leaves any existing marker untouched)."""
    _write_json_atomic(os.path.join(root, _MARKER_NAME), {
        "kind": _MARKER_KIND, "version": 1, "pid": _check_pid(owner_pid), "created": time.time(),
        "root": name or os.path.basename(root),
    })


def _read_marker(root: str) -> dict:
    """The validated marker (kind, version, positive `int` pid, finite non-future `created`, `root` equal to the directory's own
    name: a copied marker proves nothing), else `MARKER_MISSING` / `MARKER_INVALID`."""
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


def _identity(path: str) -> tuple[int, int]:
    st = os.lstat(path)
    return st.st_dev, st.st_ino


# --- tree walk (read-only: verifies a fresh export) ------------------------------------------------------------------------------

def _walk_tree(root: str):
    """Yield `(relpath, abspath, lstat)` for `root` ("" first) and everything below: depth first, names sorted, symlinks
    reported and never followed, at most `_MAX_TREE_ENTRIES`. By PATH: used by `_verify_export`, which only reads, on
    a tree this process has just written. Any `OSError` is `TREE_UNREADABLE`."""
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
            yield rel, path, st
            if stat.S_ISDIR(st.st_mode):
                with os.scandir(path) as listing:
                    names = sorted(entry.name for entry in listing)
                for name in reversed(names):
                    child = os.path.join(path, name)
                    stack.append((f"{rel}/{name}" if rel else name, child, os.lstat(child)))
    except OSError as exc:
        raise BenchmarkGateError("TREE_UNREADABLE", str(exc)) from exc


# --- git: a private repository over the real object store ---------------------------------------------------------

def _git_env(home: str) -> dict[str, str]:
    """An environment built from nothing: no inherited `GIT_*`, no user/system config, prompts, replace refs, lazy fetch, pager."""
    return {
        "PATH": "/usr/bin:/bin", "HOME": home, "XDG_CONFIG_HOME": home, "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0", "GIT_ATTR_NOSYSTEM": "1", "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_NO_LAZY_FETCH": "1", "GIT_OPTIONAL_LOCKS": "0", "GIT_LITERAL_PATHSPECS": "1", "GIT_PAGER": "cat",
    }


def _objects_dir(repo: str | os.PathLike) -> str:
    """The object directory of `repo` (work tree, bare, or linked worktree), found by reading files, not by running git in it."""
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
    """A `preexec_fn` capping every file the child writes at `cap + 1` bytes, clamped to the hard limit it inherited (a lower
    hard limit would make `setrlimit` raise). `resource` is POSIX-only: lazy import."""
    def apply() -> None:
        import resource

        hard = resource.getrlimit(resource.RLIMIT_FSIZE)[1]
        resource.setrlimit(resource.RLIMIT_FSIZE, (cap + 1 if hard == resource.RLIM_INFINITY else min(cap + 1, hard), hard))
    return apply


def _require_modern_git() -> None:
    """`GIT_ATTR_SOURCE` (keeps the tree's own `.gitattributes` out of the checkout) needs git >= 2.43; an older git silently
    applies `eol=crlf`/`ident`, so honest repositories would fail verification as hostile. Say so up front as an environment
    error (`GIT_TOO_OLD`, exit 2). Checked once per process."""
    global _git_version
    if _git_version is None:
        code, out = _PrivateGit._run_raw(["--version"], _git_env(tempfile.gettempdir()), tempfile.gettempdir(), 256)
        found = re.match(rb"git version (\d+)\.(\d+)", out) if code == 0 else None
        if found is None:
            raise BenchmarkGateError("GIT_FAILED", "cannot determine the git version")
        _git_version = (int(found[1]), int(found[2]))
    if _git_version < _GIT_MINIMUM:
        raise BenchmarkGateError("GIT_TOO_OLD", "git >= %d.%d is required, found %d.%d" % (*_GIT_MINIMUM, *_git_version))


class _PrivateGit:
    """A throw-away bare repository with NO config, hooks, attributes, remotes or refs, reading the real repository's
    objects through `GIT_ALTERNATE_OBJECT_DIRECTORIES`: nothing in the real `.git/config` (filters, fsmonitor, diff
    drivers, hooksPath, a promisor remote) can execute and nothing is written to the real store. SHA-1 or SHA-256 by commit length."""

    def __init__(self, repo: str | os.PathLike, commit_length: int) -> None:
        self._objects = _objects_dir(repo)
        self._length = commit_length

    def __enter__(self) -> "_PrivateGit":
        _require_modern_git()
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
            except (OSError, subprocess.SubprocessError) as exc:  # SubprocessError: a failing preexec_fn
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
    """NFC, casefolded, zero-width characters dropped (HFS+), trailing dots and spaces stripped (NTFS)."""
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
        # Files + directories + root: the bound the verification walk uses, so an oversize tree is always EXPORT_TOO_LARGE.
        if len(entries) + len(ancestors) + 1 > _MAX_TREE_ENTRIES or total > _MAX_EXPORT_BYTES:
            raise BenchmarkGateError("EXPORT_TOO_LARGE", f"over {_MAX_TREE_ENTRIES} entries (files and directories) or {_MAX_EXPORT_BYTES} bytes")
    if keys & ancestors:
        raise BenchmarkGateError("EXPORT_PATH_COLLISION", "a file and a directory share a name")
    return entries


def _verify_export(dest: str, entries: dict[str, tuple[str, int, bool]]) -> list[str]:
    """Demand the written tree equal the commit's listing (nothing extra or missing, sizes and executable bits equal: this
    also catches a conversion that slipped past `GIT_ATTR_SOURCE`), no symlink resolving outside `dest`. Returns LFS pointers."""
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


def _create_root(parent: str, name: str, owner: int) -> bool:
    """Create the dispatch root WITH its marker, atomically (a temp directory renamed into place, so a concurrent exporter
    never sees a root without a marker). True if this call created it; False if it existed, which the caller validates."""
    root = os.path.join(parent, name)
    tmp = tempfile.mkdtemp(dir=parent, prefix=".new-")
    try:
        _write_marker(tmp, owner, name)
        os.rename(tmp, root)
        return True
    except OSError as exc:
        if exc.errno not in (errno.ENOTEMPTY, errno.EEXIST, errno.ENOTDIR):
            raise
        return False
    finally:
        if os.path.lexists(tmp):
            shutil.rmtree(tmp, ignore_errors=True)


def _export(repo, commit, dest, owner_pid: int | None) -> tuple[Path, dict[str, list[str]]]:
    length = _check_commits(commit)
    try:
        leaf_path = Path(os.path.abspath(os.fspath(dest)))
    except (TypeError, ValueError) as exc:
        raise BenchmarkGateError("DEST_REJECTED", "dest is not a path") from exc
    root_name, leaf = leaf_path.parent.name, leaf_path.name
    if not _ROOT_NAME_RE.fullmatch(root_name) or not _LEAF_NAME_RE.fullmatch(leaf):
        raise BenchmarkGateError("DEST_REJECTED", "dest must be <fixed parent>/<root name>/<leaf name>")
    owner = _check_pid(os.getpid() if owner_pid is None else owner_pid)
    if os.path.realpath(leaf_path.parent.parent) != os.path.realpath(fixed_parent()):  # before anything is created
        raise BenchmarkGateError("DEST_REJECTED", f"dest must be under {fixed_parent()}")
    parent = os.path.realpath(_check_parent(create=True))
    root = os.path.join(parent, root_name)
    export_dir = os.path.join(root, leaf)
    sidecar = export_dir + ".export.json"

    with _PrivateGit(repo, length) as git:  # the repository is validated before anything is created
        git.require_commit(commit)
        entries = _parse_listing(git.run("ls-tree", "-r", "-l", "-z", "--full-tree", commit))
        created_root = _create_root(parent, root_name, owner)
        st = os.lstat(root)
        if not stat.S_ISDIR(st.st_mode) or _foreign(st):
            raise BenchmarkGateError("DEST_REJECTED", "root exists and is not a directory of this user")
        if not created_root:
            _read_marker(root)  # an existing root must be one of ours
        root_id, created_dest, sidecar_written = (st.st_dev, st.st_ino), False, False
        try:
            try:
                os.mkdir(export_dir, 0o755)
            except FileExistsError:
                raise BenchmarkGateError("DEST_REJECTED", "dest already exists") from None
            created_dest = True  # from here on, and only from here, this call owns `export_dir`
            git.run("read-tree", commit)
            git.run("checkout-index", "-a", "-f", work_tree=export_dir, cap=None)
            lfs = _verify_export(export_dir, entries)
            if _identity(root) != root_id or os.path.realpath(export_dir) != export_dir:  # narrows a same-uid redirect
                raise BenchmarkGateError("DEST_REJECTED", "the dispatch root changed while exporting")
            _write_json_atomic(sidecar, {"commit": commit, "entries": len(entries)})
            sidecar_written = True
        except BaseException:
            # Remove only what this call created INSIDE the root. A new root keeps its marker even when empty (an empty
            # root with a marker is cleanable by `cleanup`, and a later export may reuse it); unlinking the marker in place
            # would race a concurrent exporter that already validated it.
            if created_dest:
                shutil.rmtree(export_dir, ignore_errors=True)
            if sidecar_written:
                try:
                    os.unlink(sidecar)
                except OSError:
                    pass
            raise
    return Path(export_dir), {"gitlinks": sorted(r for r, e in entries.items() if e[0] == "G"), "lfs_pointers": lfs}


def export_tree(repo: str | os.PathLike, commit: str, dest: str | os.PathLike, *, owner_pid: int | None = None) -> Path:
    """Export the tree of `commit` into `dest` and return the RESOLVED path of `dest`. Raises `BenchmarkGateError`. Needs
    git >= 2.43 (`GIT_TOO_OLD` otherwise).

    `commit` is 40 or 64 lowercase hex. `dest` is `<fixed_parent()>/<root>/<leaf>` and must not exist (an existing one is
    `DEST_REJECTED` and never touched); the root (`[A-Za-z0-9][A-Za-z0-9_-]{7,63}`, caller-chosen, dispatch-unique) is created
    mode 0700 together with its marker (pid, timestamp), atomically, or reused after its marker validates; concurrent exports
    into one new root are safe. The marker pid is `owner_pid` for the FIRST export of a root (later ones are ignored); by
    default the short-lived exporting process, so `cleanup` (C4c-1b) is allowed right after export unless `--owner-pid` names a
    longer-lived owner. Put venvs at `<root>/venv-*`. `dest` is left WRITABLE: the install and the overlay still run.

    Built by `git read-tree` into a private index plus `git checkout-index` inside a `_PrivateGit` (never `git archive`,
    which honours `export-ignore`/`export-subst`): no `.git`, no hooks, no filters, no LFS, no network. A plain
    checkout-index applied the tree's own `.gitattributes` (`eol=crlf` rewrote every line ending, `ident` rewrote
    `$Id$`), so `GIT_ATTR_SOURCE` points at the empty tree and `_verify_export` rechecks every size. A submodule becomes
    an EMPTY directory and an LFS pointer stays pointer text (both named by the CLI on stderr). A symlink is written as a
    symlink and the export is REFUSED if any resolves outside `dest` (stricter than "never follow": a legitimate absolute
    symlink fails closed); unsafe or colliding paths and trees over 100,000 entries are refused too. A sidecar
    `<leaf>.export.json` beside `dest` records the commit (the C4c-2 overlay binds `base_ref_commit` to it). On failure only
    what this call created inside the root is removed (a new root keeps its marker). No `.git`: an installer deriving its
    version from git (setuptools_scm, versioneer) fails in an export unless the caller sets a pretend version. Residual:
    the fixed parent and the root are validated BY PATH (git itself works by path), then the root's identity is re-checked
    before the sidecar is written; a same-uid process can still redirect the write, gaining no capability (it can already
    write, chmod and delete those directories)."""
    return _export(repo, commit, dest, owner_pid)[0]


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


def _cmd_fixed_parent(_args: argparse.Namespace) -> int:
    """Print `fixed_parent()`: C4f builds `export --dest` and `cleanup --root` paths from it."""
    print(fixed_parent())
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``validate`` (C4a), ``lint`` (C4b), ``export`` and ``fixed-parent`` (C4c-1a). Later
    PRs add ``cleanup`` (C4c-1b), ``snapshot-venv`` (C4c-2), ``compare`` and ``run-once`` (C4d) by adding a subparser with ``set_defaults(func=...)``. There is no catch-all
    here on purpose: C4d owns the exit-code contract for a crash."""
    parser = argparse.ArgumentParser(prog="benchmark_gate.py", description="Benchmark gate: validate, lint, export, fixed-parent.")
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
    export.add_argument("--dest", required=True, metavar="DIR", help="<fixed parent>/<root>/<leaf>; must not exist; see fixed-parent")
    export.add_argument("--owner-pid", type=int, metavar="PID",
                        help="pid in a NEW root's marker, a positive int below 2**31 (default: this short-lived process, so cleanup is "
                             "allowed at once; ignored for an existing root); requires git >= 2.43")
    export.set_defaults(func=_cmd_export)
    fixed = sub.add_parser("fixed-parent", help="print the per-user directory that roots live in")
    fixed.set_defaults(func=_cmd_fixed_parent)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse exits 2 on usage errors (and 0 on --help)
        return exc.code if isinstance(exc.code, int) else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
