#!/usr/bin/env python3
"""Validation, lint and statistics core of the performance-review -> loop-task-implementer benchmark gate (Epic C).

**This module is not wired into anything yet.** It is delivered by a series of PRs for gap-backlog ticket C4 (C4a core, C4b lint,
C4c-1a export, C4c-1b seal/cleanup, C4c-1c claim recovery, C4c-2 overlay/diff/venv check, C4d harness, C4e classifier/docs, C4f wiring); no
workflow file, lifecycle validator or other script calls it until C4f. C4d is delivered in three parts: C4d-1 the measurement harness
(``run_order``, ``side_env``, ``pytest_argv``, ``measure_paired``), C4d-2 the trace (``TRACE_PLUGIN_SOURCE``, ``trace_env``,
``trace_paired``) and C4d-3 ``compare`` (the pipeline of ``_compare_impl``: integrity checks, paired trace and measurement, post-run
check, verdict), ``run_benchmark_once`` and the CLI commands ``compare`` and ``run-once``. C4e is the classifier and docs, C4f the workflow
wiring.

Sections, in file order: the gate's string-level validation (``benchmark_symbol_from_location``, ``validate_benchmark_command``,
``validate_benchmark_gate``, ``benchmark_target``); ``evaluate_paired_samples``; ``escape_diagnostic``; the AST lint
(``validate_benchmark_content``); C4c-1 export, seal and cleanup (``export_tree``, ``seal_tree``, ``unseal_tree``, ``cleanup_root``,
``BenchmarkGateError`` and the error codes); C4c-2a tree hash and overlay (``hash_tree``, ``harness_sha256``, ``export_commit``,
``read_benchmark``, ``seal_export``, ``hash_export``, ``fingerprint_tree``, ``repo_top_levels``, ``overlay_benchmark_file``); C4c-2b the
diff checks (``protected_path_diff``, ``token_tripwire``, ``diff_checks``, ``is_ancestor``); C4c-2c the venv hook check
(``snapshot_venv``, ``interpreter_pin``, ``check_venv``); C4d-3 ``dependency_parity`` and ``verify_export_against_commit``; C4d-1 and C4d-2
the measurement harness and the trace (``measure_paired``, ``trace_paired``); ``run_benchmark_once``; C4d-3 ``compare`` (vocabularies,
``Side``, result assembly and writing, steps 1 to 13); the CLI.

Calling order. The Orchestrator provisions HEAD FIRST (spec 2.5): for each side it creates the venv, runs ``snapshot-venv`` (which prints
``snapshot_sha256`` and ``interpreter_sha256``) BEFORE that side's install, then installs; it creates the base export and venv only after the
head install has finished. Each export comes from ``export_tree`` (the dispatch root's marker pid defaults to the exporting process, so pass
``--owner-pid`` when ``cleanup`` will run from another process). It then calls ``compare`` once per fresh pair of exports; a second call on the SAME exports only for the
``COMPARE_RETRYABLE_AUTOMATIC`` triple and, after a human sets the flag, the ``COMPARE_RETRYABLE_WITH_HUMAN_FLAG`` triple (see "Reading the
outcome"); every other outcome needs fresh exports. ``compare`` runs
``is_ancestor``, then the isolation checks of both sides (roots, interpreter pin, snapshots, ``check_venv``, ``dependency_parity``,
``verify_export_against_commit``), ``diff_checks`` and the host-load check, all before any export is modified; then ``repo_top_levels`` of the
base export (after the install, so ``build/`` and ``dist/`` can join the lint allowlist: harmless, disclosed) and ``overlay_benchmark_file``;
``seal_export`` x2, ``read_benchmark`` on BOTH roots (required equal), the lint and ``hash_export`` x2; the integrity checks once more
immediately before the first child; ``trace_paired``; ``measure_paired``; a post-run check of every hash, fingerprint, snapshot and pin
after any path that started a child; and the verdict, written to ``out_path``. ``harness_sha256`` is computed at step 2 (both parts are fixed
at import and at the first load of the validator, whose module body it therefore runs).

Provisioning contract (spec 2.2 and 2.5; the Orchestrator's side, not enforced beyond what ``compare`` checks): each venv is created fresh
and ``snapshot-venv`` runs BEFORE that side's install: it mints the snapshot and interpreter pins, and a pin is never re-minted after an
install. The install uses ``--no-compile`` and runs with ``PYTHONDONTWRITEBYTECODE=1``, a fresh ``HOME`` and ``TMPDIR``, ``PIP_CONFIG_FILE=/dev/null``
and ``PIP_NO_CACHE_DIR=1``, from pinned requirements (or a wheelhouse), ideally with no network, and installs the project EDITABLE ONLY (``dependency_parity`` fails closed on a non-editable project install). AFTER the install and before
``compare``, every ``__pycache__`` and ``.pyc`` under the venv's site-packages is removed (``dependency_parity`` rejects bytecode there; the
dependencies then compile on every run on both sides; the interpreter pin does not cover site-packages, so the removal leaves the pins valid).
An interpreter that is not writable by the build user is preferred (a writable one needs ``--allow-writable-interpreter``, a human's signal, and
shows in the ``RESULT:`` line). A stray-process census around the installs is recommended and not enforced here: it is the Orchestrator-side check for the
accepted ``setsid`` residual [R1]. The harness's euid must not be 0: a euid-0 Orchestrator (e.g. Docker as root) gets ``INTERPRETER_WRITABLE`` on EVERY
compare (root owns, and can write, every interpreter file, so the interpreter is never "non-writable") and every symlink alias is refused, so root is
effectively unsupported unless a human passes ``--allow-writable-interpreter`` and the paths have no symlink hop; C4e must run the Orchestrator non-root
(an alias or venv-hook refusal is an ENVIRONMENT fault, not a Builder fault). After ``compare`` the Orchestrator reads the result file ONCE into bytes, hashes
those bytes and compares the hash to the line's ``sha256=``, parses the SAME bytes, reads ``stage`` and ``detail`` only from those bytes (the
``RESULT:`` line carries neither; ``INTERPRETER_WRITABLE`` needs its detail from the file) and checks the line's result and reason against them (the CLI
prints the line from the in-memory result and the hash of the bytes it wrote, never from a re-read of the file; a file rewritten afterwards no
longer matches its line and must be ignored). It also pins the EXPECTED ``harness_sha256`` and requires each project venv to be CPython >= 3.12
([R2] and [R3] below). ``harness_sha256`` is a domain-separated, length-prefixed digest that ``sha256sum`` cannot reproduce: the
``harness-sha256`` subcommand prints it, and the expected value must be taken from a TRUSTED copy of the harness (the pinned release, or a run of
``harness-sha256`` in a clean checkout), NEVER from a previous ``compare`` result (that would be circular: a tampered harness vouches for itself).

Reading the outcome (the contract of ``_cmd_compare``): exit 0 is ``IMPROVED`` ONLY together with a valid ``RESULT: IMPROVED ...`` line whose
``sha256=`` matches the bytes of the result file; a bare exit 0 (``compare --help`` exits 0 and prints no ``RESULT:`` line) is NOT an ``IMPROVED``.
Exit 1 is any other result, but an exit 1 WITHOUT a valid ``RESULT:`` line counts as exit 2; exit 2 (usage error, a raised ``BenchmarkGateError``,
a crash) means any file at ``--out`` is to be IGNORED (the file can exist: ``compare`` writes it before the CLI validates the in-memory result).
Option abbreviations are refused (``allow_abbrev=False``: ``--allow-writable-i`` is a usage error, exit 2, not the human flag). Retry on the same
exports is keyed on (reason, stage, detail), not on the reason alone, and two constants are the complete list: ``COMPARE_RETRYABLE_AUTOMATIC``
(``HOST_BUSY_START``, retried by the Orchestrator itself) and ``COMPARE_RETRYABLE_WITH_HUMAN_FLAG`` (``INTERPRETER_WRITABLE``, detail of
``ISOLATION_REJECTED``, retried ONLY after a human sets ``--allow-writable-interpreter``: it must NEVER be auto-retried with the flag). Every other ``ISOLATION_REJECTED`` at ``pre_overlay`` (``INTERPRETER_CHANGED``, ``INTERPRETER_DIFFERS``,
``SNAPSHOT_CHANGED``, ``DEPENDENCY_PARITY``, ``TRACKED_FILE_DIFFERS``, ...) is NOT: the pins precede the install, so it needs fresh provisioning
(the other rows are in spec 2.3). Tamper signals: ``ISOLATION_REJECTED``/``EXPORT_CHANGED`` at stage ``ran`` is also what the spawn guard gives when a directory was replaced before a spawn (no measured fields): a human matter, never retried.

The Orchestrator's wait is a provisioning-side budget and is NOT enforced by any deadline inside ``compare``: at least the gate cap (1800 s of
child time) plus the hashing plus 300 s x the git invocations ``compare`` opens plus up to ~20 s per interpreter probe (``python -I -S``, a
child that runs before any benchmark child: steps 4, 9 and 12; spec 2.2 and 9.12 say the same). ``_GIT_TIMEOUT_SECONDS`` (300 s) bounds EACH git invocation, and ``compare``
opens at least nine git contexts (``is_ancestor``, ``diff_checks``, ``_benchmark_origin`` at step 7, and ``verify_export_against_commit`` per
side at steps 4, 9 and 12), several invocations each; a slow repository can therefore exceed any fixed allowance.

Known residuals of ``compare``: THIS list is the single source; spec 2.5 ("Disclosed residuals") carries the same stable labels ``[R1]`` to ``[R12]`` and
a test pins that the labels match (numbers and short labels, not prose).
[R1:setsid] Escaped ``setsid`` daemon: a head child can leave the process-group kill behind with fork + ``setsid``: a stray same-user daemon survives the run.
Nothing detects it (there is no process census; page-cache effects included).
[R2:harness-file] Harness file writable: it is writable by the same user, so C4e must pin the EXPECTED ``harness_sha256`` and compare it with the result's; and it
should prefer a non-writable interpreter: bytecode written into a writable interpreter prefix between the pin and ``compare`` changes the pin's hash and
gives ``INTERPRETER_CHANGED`` (``INTERPRETER_DIFFERS`` is a different fault: two sides on different interpreters, an interpreter inside a venv or an
export, or a start-up probe that disagrees). Both are ``ISOLATION_REJECTED`` and NOT retryable on the same exports (see "Reading the outcome");
the stage is ``pre_overlay`` at step 4, but a change noticed at step 9 ends at ``overlaid`` and one noticed at step 12 at ``ran``. At step 12 an
over-budget ``_check_parity`` ends as ``NOT_PROVISIONED`` at stage ``ran``.
[R3:py312] Python older than 3.12: the trace needs ``sys.monitoring``, so a project venv older than CPython 3.12 yields ``no_monitoring``, hence
``INCONCLUSIVE``/``TRACE_UNAVAILABLE``, and can never reach ``IMPROVED``.
[R4:path-chain] Interpreter path chain: the interpreter's own path chain (the ``home`` of ``pyvenv.cfg``, symlink hops to the real prefix and the parent of the prefix are pinned by content, not guarded
by directory identity: a user-writable hop in front of a prefix that is not user-owned could be repointed by a head child between runs (a writable prefix
is already refused as ``INTERPRETER_WRITABLE``, so this needs that unusual layout); the human acceptance of every ``IMPROVED`` remains the control.
[R5:outside-state] State outside the fingerprints: they detect changes to the exports, venvs and dispatch root between the baseline and the end, not writes elsewhere
(absolute ``/tmp`` or ``/dev/shm`` state a head run leaves for a later run).
[R6:ctime-tick] Coarse ctime tick: a change undone inside one ctime tick on a coarse filesystem is not seen.
[R7:writable-interpreter] Writable interpreter: the pin covers the files listed and is exact only for a non-writable interpreter; a bytecode or file planted into a writable
interpreter by a child during a run is caught only by the end-of-run pin, not if restored.
[R8:sigkill] SIGKILL leaves child: a SIGKILLed ``compare`` leaves a running child until its own timeout.
[R9:third-party] Third-party content: content that is identical and RECORD-consistent on both sides is not judged.
[R10:prefix-ancestors-libs] Ancestors and shared libraries: the ancestors of ``<prefix>`` (the interpreter's real prefix) are not checked for writability, and shared
libraries outside ``<prefix>`` (``libssl``, ``libffi`` linked by ``_ssl``, ``_hashlib`` under a user-owned Homebrew) are not pinned.
[R11:finder-and-bin] Finder code and ``bin/``: the editable finder's own code is trusted by name once its mapping is checked, and the venv ``bin/`` directory (``PATH`` puts it
first) is not verified (the benchmark lint allows no subprocess module; only the library under test could spawn a tool).
[R12:non-code-inputs] Non-code untracked inputs (``.env``, ``*.json``, ``*.cfg``) are not covered by ``verify_export_against_commit``.

Limits of the trace: it is a narrow tripwire, not a proof of equal work. For the typical benchmark, which makes one library call and prints a
digest, the executed-line count is a small constant on both sides, so equality proves nothing; the trace discriminates only when the test body
loops or branches on library behaviour. Blind spots: helpers and callbacks, generator expressions, lambdas, ``map``, ``exec``/``eval``,
``asyncio.run(main())``, a same-named decoy, and branches inside one line. In-process tampering by code running in the child, and detection of
the trace run itself, are not detected. The trace run also differs from a timed run in the contents of its per-side work directory (extra
``plugin-`` and ``out-`` entries), in its environment (``PYTHONPATH`` and the three ``BENCH_TRACE_*`` keys), in ``config.invocation_params`` and
``getoption('plugins')`` (not tokenised), and in compiling the plugin on every run (no bytecode is written: ``PYTHONDONTWRITEBYTECODE``). A
suppressed or missing result is fail-closed; only a forged, matching result is a bypass. C4d-3 specification:
``docs/superpowers/specs/2026-11-06-c4d3-compare-and-run-once-design.md``. Parent Specification (revision 5, the converged result of four review
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
import contextlib
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
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import tokenize
import types
import unicodedata
import warnings
from fractions import Fraction
from pathlib import Path
from typing import Callable, Literal, NamedTuple

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
    ``(warmup_runs + repeats + 3) * 2 * per_run_timeout_seconds <= 1800`` budgets the CHILD time of one ``compare`` only; the
    ``+3`` is the untimed trace run, allowed 3x a timed run, per side. It does not keep a dispatch inside its wait: the git work and the hashing
    sit outside it, so the Orchestrator's wait must be longer than the cap (a budget it keeps; nothing enforces it: see "Provisioning
    contract" in the module docstring). Defaults use 1600 s; at
    ``repeats`` 8 the timeout may be at most 75 with ``warmup_runs`` 1 and 69 with 2 (``warmup_runs`` 0 is
    ``BOUNDS_REJECTED``: ``measure_paired`` needs at least one warm-up).
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
        1 <= values["warmup_runs"] <= 2
        and values["repeats"] in _REPEATS_ALLOWED
        and 10 <= values["per_run_timeout_seconds"] <= 300
        and Fraction("0.05") <= fractions["min_improvement"] <= Fraction("0.90")
        and Fraction("0.02") <= fractions["max_noise"] <= Fraction("0.30")
    ):
        return None, "BOUNDS_REJECTED"
    if (values["warmup_runs"] + values["repeats"] + _TRACE_TIMEOUT_FACTOR) * 2 * values["per_run_timeout_seconds"] > _BUDGET_CAP_SECONDS:
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


def benchmark_target(normalized_gate: dict) -> str:
    """The pytest target (path or ``path::symbol``) of a validated gate command: its one non-option token."""
    tokens = normalized_gate["command"].split(" ")
    if tokens[:3] == ["python3", "-m", "pytest"]:
        tokens = tokens[3:]
    elif tokens[:1] == ["pytest"]:
        tokens = tokens[1:]
    targets = [token for token in tokens if token and not token.startswith("-")]
    if len(targets) != 1:
        raise ValueError("gate command has no single target")  # unreachable for a validated gate
    return targets[0]


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


def _ratio_stats(base, head) -> tuple[list[Fraction], Fraction, Fraction]:
    """Exact ``(ratios, median, mad)`` of head/base per pair, in input order; does not validate (``_evaluate`` does)."""
    ratios = [Fraction(h, b) for b, h in zip(base, head)]
    median = _median(ratios)
    mad = _median([abs(r - median) for r in ratios])
    return ratios, median, mad


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

    ratios, median, mad = _ratio_stats(base, head)
    # (1) Clear win: at least `need` ratios <= 1 - min_improvement. The noise gate is skipped here (the median
    # clause of revision 3 was redundant). need = 7 at n=8 is the stricter setting: need 6 gave 11.9% false
    # IMPROVED in the period-4 lock-in regime (revision 5).
    if sum(1 for r in ratios if r <= 1 - threshold) >= _NEED_CLEAR[repeats]:
        return "IMPROVED", "IMPROVED_CLEAR"
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
# C4c-1: export (1a), seal and cleanup (1b), claim recovery (1c)
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
# ERROR_CODES: the codes a `BenchmarkGateError.code` can carry (built up in stages below). The reasons of a `compare` RESULT that exist only
# there (`HOST_BUSY_START`, `HOST_BUSY_END`, `IMPROVED_CLEAR`, `NOISY`, `BORDERLINE`, `GATE_REJECTED`, `ISOLATION_REJECTED`, `LINT_REJECTED`,
# `HEAD_OUTPUT_TOO_LARGE`, ... see `COMPARE_REASONS`) are not exceptions and are not listed here. Many names are both, because `compare` reports a
# library refusal under its own name as a reason (the measure and trace refusals, the diff refusals, `BENCHMARK_MODIFIED`,
# `UNSUPPORTED_PLATFORM`): the overlap is exactly `set(ERROR_CODES) & set(COMPARE_REASONS)` (14 names when this was written; a test pins it).
GIT_TREE_SEAL_CODES = (  # the git, tree and seal refusals and failures; `COMPARE_REASONS` takes its detail tokens from here
    "COMMIT_INVALID", "COMMIT_NOT_FOUND", "REPO_UNREADABLE", "DEST_REJECTED", "GIT_FAILED", "GIT_TOO_OLD", "GIT_TIMEOUT",
    "GIT_OUTPUT_TOO_LARGE", "TREE_UNREADABLE", "TREE_TOO_LARGE", "SEAL_FAILED",
)
ERROR_CODES = GIT_TREE_SEAL_CODES + (  # MARKER_MISSING / MARKER_INVALID also appear in CLEANUP_CODES: the same condition seen by `cleanup`
    "MARKER_MISSING", "MARKER_INVALID",
)
# C4c-2a: refusals of the overlay: library results that `compare` (C4d) maps to a verdict. No CLI prints them (`_fail` is for
# `export`); a failure that is not one of these is OVERLAY_FAILED (an I/O error or a broken validator: a crash, not a verdict), and
# OVERLAY_BASE_SEALED is a caller-order error (the overlay ran after `seal_tree`).
OVERLAY_REFUSAL_CODES = (
    "OVERLAY_PATH_REJECTED",    # the path fails the gate's lexical rules (also for the C4c-2b diff checks) or `validate_task_target`, or no entry of that exact name
    "OVERLAY_NOT_REGULAR",      # the head file is a symlink, hard-linked, special, unreadable or over 16 KiB, or behind a symlinked parent
    "OVERLAY_PATH_CONFLICT",    # a base component that should be a directory is not one, or a case-folded twin exists there
    "BENCHMARK_MODIFIED",       # present at base, and the head's bytes, kind or link count differ
)
# NOT verdicts about the PR: a wrong or missing export (OVERLAY_COMMIT_MISMATCH: a stale directory, a swapped root, a tampered or absent
# sidecar), a sealed base (a caller-order error), an unreadable harness file, an I/O error. `compare` must not blame the Builder for them.
ERROR_CODES += OVERLAY_REFUSAL_CODES + ("OVERLAY_COMMIT_MISMATCH", "OVERLAY_FAILED", "OVERLAY_BASE_SEALED", "HARNESS_UNREADABLE")
# C4c-2b: refusals of the two diff checks (library results that `compare` maps per the design: PROTECTED_PATH_CHANGED -> PROPOSED_BLOCKING, BENCHMARK_AWARE_CODE -> REJECTED with NEEDS_EVIDENCE). A failure to RUN the
# check (a missing commit, an unreadable repository, git failing) is one of the git codes above: a crash, not a verdict.
DIFF_REFUSAL_CODES = (
    "PROTECTED_PATH_CHANGED",   # a protected path (a startup hook, config, shadowing module, ...) was added, changed or removed between the commits
    "BENCHMARK_AWARE_CODE",     # a line added outside the benchmark file mentions a token a benchmark-aware fix would need
)
ERROR_CODES += DIFF_REFUSAL_CODES
CLEANUP_CODES = (
    "REMOVED", "ABSENT",        # success (exit 0); the rest are refusals (exit 1)
    "NOT_UNDER_FIXED_PARENT", "NOT_A_DIRECTORY", "NOT_OWNED", "MARKER_MISSING", "MARKER_INVALID", "OWNER_ALIVE",
    "ROOT_CHANGED",             # the root or the fixed parent was replaced between the checks and the removal
    "REMOVE_FAILED",
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
        self.side: str | None = None  # measure_paired and trace_paired: which side failed ("base" or "head"), None if neither or both
        self.phase: str | None = None  # measure_paired: "warmup" or "timed"; trace_paired: "trace" (None for an argument error)
        self.partial: dict | None = None  # measure_paired only: {"order", "base_ns", "head_ns"} of the completed rounds when phase == "timed" (None for trace_paired)
        # why a run failed. trace_paired: one of TRACE_FAILURE_KINDS on every error after validation; measure_paired: the `_execute` kind (spawn,
        # oversize, timeout, nonzero) of a failed run only (None for a digest error, WORKLOAD_TOO_SHORT, MEASURE_FAILED or a bad argument);
        # run_benchmark_once: the same `_execute` kind of a failed run, None for DIGEST_MISSING; `compare` maps by kind. None for every other error.
        self.kind: str | None = None
        # trace_paired only (`compare` shows it in its result), and only for an error raised AFTER both sides produced a result (the kinds unavailable_one_side,
        # unavailable_tokens_differ, unavailable_interpreters_differ, interpreters_differ, counts_differ, unavailable): {"base": {"kind":
        # "lines"|"unavailable", "value": int count | str token, "interpreter": "<ver> <impl>"}, "head": {...}, "argv": {"base": [...],
        # "head": [...]}, "body_has_control_flow": bool}. None for an error raised during a side's run and for every other error.
        self.trace: dict | None = None
        self.hits: list[dict] = []  # the diff checks put what they found here (already escaped), for the evidence a human is shown

    def __str__(self) -> str:  # a traceback or log line shows the reason, not only the code
        return f"{self.code}: {self.detail}" if self.detail else self.code


class _IdentityChanged(Exception):
    """Raised by the spawn guard of ``_execute`` (spec 2.5, "Directory identity"): a directory a child is about to run in or from is no
    longer the one step 9 recorded (or a recorded path no longer resolves to itself). Deliberately NOT a ``BenchmarkGateError``: no generic
    ``except BenchmarkGateError`` (a verdict mapper, a CLI wrapper, ``measure_paired``'s own harness-fault handler) can swallow it or turn it
    into a ``MEASURE_FAILED``; only ``compare`` handles it, and it ends with ``ISOLATION_REJECTED``/``EXPORT_CHANGED`` (stage ``ran``) with
    nothing measured. It carries ``code`` (``MEASURE_FAILED``, for a library caller that logs it), ``detail`` and the same attributes as the
    errors of ``measure_paired`` and ``trace_paired``: ``side`` (the side about to be spawned), ``phase`` (``trace``; ``warmup`` or
    ``timed``), ``kind`` (``harness``), ``partial`` (the completed timed rounds when ``phase`` is ``timed``, else ``None``) and ``trace``
    (``None``). The guard sets ``side``; the function that called ``_execute`` fills the rest. A guard that finds nothing returns silently."""

    code = "MEASURE_FAILED"

    def __init__(self, detail: str, side: str | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.side: str | None = side
        self.phase: str | None = None
        self.kind: str | None = "harness"
        self.partial: dict | None = None
        self.trace: dict | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


# --- the fixed parent, the dispatch-unique root and its marker ----------------------------------------------------

def fixed_parent() -> Path:
    """The only directory `export` creates roots in and `cleanup` removes them from:
    `<tempfile.gettempdir()>/software-builder-bench-<uid>` (plain name without a uid), fixed so containment is a `realpath`
    comparison, never a name pattern (a pattern delete could hit another live task's root; `task_lease` allows concurrent
    Orchestrators on one host). The per-user name does NOT stop another user who already owns that name from making `export`
    and `cleanup` refuse (`DEST_REJECTED` / `NOT_UNDER_FIXED_PARENT`): a safe refusal, not a takeover. Absolute even for a
    relative `TMPDIR`. `tempfile.gettempdir()` caches its answer, so the path is fixed for the life of a process; separate
    CLI invocations must share one `TMPDIR`. CLI: `fixed-parent`. Residual: the parent is validated
    BY PATH above the dispatch root; a same-uid process can redirect it between check and use. For `export`/`cleanup` that gains
    nothing it did not have (it can already write, chmod and delete those directories); for `compare` it is NOT harmless in general: a
    head child could repoint a user-owned link in a path the later children are spawned through, which is why `compare` records and
    re-checks the RESOLVED directories before every spawn (`_spawn_guard`) and the venv checks refuse a `.pth` or finder path that goes
    through a link the user owns. Everything below a root is handled by descriptor."""
    suffix = f"-{os.getuid()}" if hasattr(os, "getuid") else ""
    return Path(os.path.abspath(tempfile.gettempdir())) / (_ROOT_PARENT_NAME + suffix)


def _foreign(st: os.stat_result) -> bool:
    return hasattr(os, "getuid") and st.st_uid != os.getuid()


def _check_parent(create: bool) -> Path:
    """The fixed parent, which must be a real directory of ours that others cannot write (created 0700 if `create`).
    `ABSENT` when it does not exist and `create` is false; `DEST_REJECTED` for anything else wrong with it."""
    parent = fixed_parent()
    if create:
        try:
            os.mkdir(parent, 0o700)
            os.chmod(parent, 0o700)  # umask-proof: umask 0277 would leave 0500 and poison every later export
        except FileExistsError:
            pass
        except OSError as exc:
            raise BenchmarkGateError("DEST_REJECTED", f"cannot create the fixed parent: {exc}") from exc
    try:
        st = os.lstat(parent)  # lstat: a symlink planted at the fixed parent is not a directory
    except OSError as exc:
        absent = isinstance(exc, FileNotFoundError) and not create  # `ABSENT` is a cleanup verdict, never an export error
        raise BenchmarkGateError("ABSENT" if absent else "DEST_REJECTED", f"fixed parent: {exc}") from exc
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
        os.fchmod(fd, 0o600)  # umask-proof: umask 0577 would leave a mode-0 file that reads back as MARKER_MISSING
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


def _read_marker(root: str, *, dir_fd: int | None = None, expect: str | None = None) -> dict:
    """The validated marker (kind, version, positive `int` pid, finite non-future `created`, `root` equal to the directory's own
    name, or to `expect` when the directory is read through `dir_fd` under another name: a copied marker proves nothing), else
    `MARKER_MISSING` / `MARKER_INVALID`."""
    try:
        raw = _read_bounded(_MARKER_NAME if dir_fd is not None else os.path.join(root, _MARKER_NAME), 4096, nofollow=True, dir_fd=dir_fd)
    except OSError as exc:
        if exc.errno not in (errno.ENOENT, errno.ENOTDIR, errno.ELOOP, errno.EACCES, errno.EPERM):
            raise  # EMFILE, EIO ...: the environment failed, which says nothing about whose directory this is
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
        and marker.get("root") == (expect or os.path.basename(root)) and type(pid) is int and 0 < pid < 1 << 31
        and type(created) in (int, float) and math.isfinite(created) and 0 < created <= time.time() + 300
    ):
        raise BenchmarkGateError("MARKER_INVALID", "marker fields are wrong")
    return marker


def _pid_alive(pid: int) -> bool:
    """`os.kill(pid, 0)`: ESRCH is dead, anything else alive (fail closed); off POSIX always alive (Windows `os.kill` would
    terminate the process). Residual: a recycled pid keeps a dead owner's root undeletable (the safe direction)."""
    if os.name != "posix":
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except (OSError, OverflowError, ValueError):
        return True
    return True


def _identity(path: str) -> tuple[int, int]:
    st = os.lstat(path)
    return st.st_dev, st.st_ino


def _checked_root(root: str | os.PathLike) -> tuple[str, tuple[tuple[int, int], tuple[int, int]]]:
    """`(resolved path, (parent identity, root identity))` when the root is a real directory of ours directly under a private
    fixed parent, else a `BenchmarkGateError` whose code is a `CLEANUP_CODES` entry. The identities let the caller notice a
    swap before it removes anything."""
    path = os.path.abspath(os.fspath(root))
    try:
        parent = os.path.realpath(os.path.dirname(path))
        same_parent = parent == os.path.realpath(fixed_parent())
    except (OSError, ValueError) as exc:  # EINVAL on a symlink loop being swapped under realpath, seen on Linux
        raise BenchmarkGateError("NOT_UNDER_FIXED_PARENT", f"cannot resolve the path: {exc}") from exc
    if not _ROOT_NAME_RE.fullmatch(os.path.basename(path)) or not same_parent:
        raise BenchmarkGateError("NOT_UNDER_FIXED_PARENT", "root is not directly under the fixed parent")
    try:
        _check_parent(create=False)
    except BenchmarkGateError as exc:
        raise BenchmarkGateError("ABSENT" if exc.code == "ABSENT" else "NOT_UNDER_FIXED_PARENT", exc.detail) from exc
    path = os.path.join(parent, os.path.basename(path))  # operate on the resolved path, never on the argument
    try:
        st = os.lstat(path)
    except OSError as exc:
        raise BenchmarkGateError("ABSENT" if isinstance(exc, FileNotFoundError) else "NOT_A_DIRECTORY", str(exc)) from exc
    if not stat.S_ISDIR(st.st_mode):
        raise BenchmarkGateError("NOT_A_DIRECTORY", "root is a symlink or not a directory")
    if _foreign(st):
        raise BenchmarkGateError("NOT_OWNED", "root belongs to another user")
    try:
        return path, (_identity(parent), (st.st_dev, st.st_ino))
    except OSError as exc:
        raise BenchmarkGateError("NOT_UNDER_FIXED_PARENT", str(exc)) from exc


# --- tree walking, sealing, cleanup ------------------------------------------------------------------------------

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


class _EntryChanged(OSError):
    """An entry is no longer the object that was verified (swapped while it was being read or repaired)."""


def _chmod_dir_nofollow(parent_fd: int, name: str, st: os.stat_result) -> bool:
    """`chmod 0700` on directory `name` of `parent_fd` (a directory that cannot be opened: mode 0), only if it is still the
    object `st` described. Linux: an `O_PATH` descriptor pins the inode (a symlink is refused by `O_DIRECTORY`), its
    identity is checked, then it is chmodded through `/proc/self/fd`: race-free. Where Python has `fchmodat(AT_SYMLINK_NOFOLLOW)`
    (macOS): `name` is re-`stat`ed immediately before it, which narrows but cannot close the window. False where neither exists."""
    def check(now: os.stat_result) -> None:
        if (now.st_dev, now.st_ino) != (st.st_dev, st.st_ino):
            raise _EntryChanged("entry changed while it was being repaired")

    if os.chmod in os.supports_follow_symlinks:
        check(os.stat(name, dir_fd=parent_fd, follow_symlinks=False))
        os.chmod(name, 0o700, dir_fd=parent_fd, follow_symlinks=False)
        return True
    if hasattr(os, "O_PATH") and os.path.isdir("/proc/self/fd"):
        fd = os.open(name, os.O_PATH | os.O_NOFOLLOW | os.O_DIRECTORY, dir_fd=parent_fd)
        try:
            check(os.fstat(fd))
            os.chmod(f"/proc/self/fd/{fd}", 0o700)
            return True
        finally:
            os.close(fd)
    return False


def _open_dir(parent_fd: int, name: str, st: os.stat_result, repair: bool) -> int:
    """Open directory `name` under `parent_fd`, never through a symlink, and confirm it is the object `st` described.
    `repair` (unseal, cleanup) first makes an unopenable directory openable, then gives it `u+rwx`."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        fd = os.open(name, flags, dir_fd=parent_fd)
    except PermissionError:
        if not (repair and _chmod_dir_nofollow(parent_fd, name, st)):
            raise
        fd = os.open(name, flags, dir_fd=parent_fd)
    try:
        after = os.fstat(fd)
        if (after.st_dev, after.st_ino) != (st.st_dev, st.st_ino):
            raise _EntryChanged("entry changed while it was being read")
        if repair:
            os.fchmod(fd, stat.S_IMODE(after.st_mode) | 0o700)
    except BaseException:
        os.close(fd)
        raise
    return fd


def _listing(fd: int) -> list[str]:
    """Names in `fd`, reversed (the walker pops from the end); closes `fd` if the listing fails, so no descriptor leaks."""
    try:
        return sorted(os.listdir(fd), reverse=True)
    except BaseException:
        os.close(fd)
        raise


def _walk_fd(root: str, limit: int | None, repair: bool = False, at: tuple[int, str, tuple[int, int]] | None = None,
             max_depth: int | None = None):
    """Yield `(rel, parent_fd, name, lstat, dir_fd)` for `root` ("" first) and everything below, depth first, names sorted,
    using ONLY descriptors: each child is `stat`ed and opened relative to its parent's descriptor with `O_NOFOLLOW` and checked
    against the `stat` result, so a directory swapped for a symlink mid-walk is refused, never followed; no path-based chmod.
    `dir_fd` is a directory's own descriptor (closed by the walker), else None. `limit` bounds the entries (None: unbounded,
    for removal). `repair` also tolerates an entry vanishing (a concurrent cleanup). `at=(parent_fd, name, (dev, ino))` walks that
    directory of the caller's open `parent_fd` instead of `root`, refusing it unless it still has that identity. `max_depth` refuses
    (`TREE_TOO_LARGE`) a directory more than that many levels below `root`, BEFORE its descriptor is opened. Raises `OSError` / `BenchmarkGateError`.
    Cost: one open descriptor per directory level (`RLIMIT_NOFILE` bounds the depth) and every entry of a large tree is stat'ed."""
    want = None
    if at is None:
        parent, name = os.path.split(os.path.abspath(root))
        pfd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
    else:
        pfd, name, identity = at
        want = types.SimpleNamespace(st_dev=identity[0], st_ino=identity[1])
    frames: list[tuple[str, int, list[str]]] = []
    try:
        st = os.stat(name, dir_fd=pfd, follow_symlinks=False)
        if not stat.S_ISDIR(st.st_mode):
            raise BenchmarkGateError("TREE_UNREADABLE", "root is not a real directory")
        fd = _open_dir(pfd, name, want or st, repair)
        frames.append(("", fd, _listing(fd)))
        count = 1
        yield "", pfd, name, st, fd
        while frames:
            rel, dfd, names = frames[-1]
            if not names:
                frames.pop()
                os.close(dfd)
                continue
            child = names.pop()
            try:
                cst = os.stat(child, dir_fd=dfd, follow_symlinks=False)
                if max_depth is not None and len(frames) > max_depth and stat.S_ISDIR(cst.st_mode):
                    raise BenchmarkGateError("TREE_TOO_LARGE", f"more than {max_depth} levels")
                cfd = _open_dir(dfd, child, cst, repair) if stat.S_ISDIR(cst.st_mode) else None
                if cfd is not None:
                    frames.append((f"{rel}/{child}" if rel else child, cfd, _listing(cfd)))
            except FileNotFoundError:
                if repair:
                    continue
                raise
            count += 1
            if limit is not None and count > limit:
                raise BenchmarkGateError("TREE_TOO_LARGE", f"more than {limit} entries")
            yield (f"{rel}/{child}" if rel else child), dfd, child, cst, cfd
    finally:
        for _, open_fd, _ in frames:
            try:
                os.close(open_fd)
            except OSError:  # one failing close must not leak the rest
                pass
        if at is None:
            try:
                os.close(pfd)
            except OSError:
                pass


def _fchmod_file(parent_fd: int, name: str, st: os.stat_result, clear: int, add: int) -> None:
    """`fchmod` a regular file through a descriptor opened relative to `parent_fd` without following a symlink, checked
    against `st`; refuses a hard-linked file (its inode is shared with a path outside the tree)."""
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0), dir_fd=parent_fd)
    try:
        after = os.fstat(fd)
        if not stat.S_ISREG(after.st_mode) or (after.st_dev, after.st_ino) != (st.st_dev, st.st_ino):
            raise _EntryChanged("entry changed while it was being read")
        if after.st_nlink > 1:
            raise OSError("hard-linked file")
        os.fchmod(fd, (stat.S_IMODE(after.st_mode) & ~clear) | add)
    finally:
        os.close(fd)


def _root_path(root: object, code: str) -> str | bytes:
    """`root` as a non-empty `str` or `bytes` path, else a coded refusal. An empty string would mean the working directory (it is
    what `os.path.abspath("")` returns), and a `str` subclass could lie about its contents."""
    try:
        path = os.fspath(root)  # type: ignore[arg-type]  # a hostile __fspath__ may raise anything, even SystemExit
        if type(path) not in (str, bytes) or not path:
            raise ValueError("root must be a non-empty str or bytes path (an empty one would mean the working directory)")
        if os.fsencode(path).count(b"\0"):  # also proves a str is encodable (a lone HIGH surrogate is not; \udc80-\udcff are undecodable bytes)
            raise ValueError("root contains a NUL byte")
    except (Exception, SystemExit) as exc:
        raise BenchmarkGateError(code, f"root is not a usable path: {_describe(exc)}") from exc
    return path


def seal_tree(root: str | os.PathLike) -> None:
    """Remove every write bit under `root` (symlinks and special files untouched), by descriptor only. `compare` seals AFTER
    the install and the overlay (sealing before breaks `pip install -e`, verified). Fails closed (`SEAL_FAILED`), including
    on a hard-linked file. Raises `BenchmarkGateError`: `SEAL_FAILED` (an `OSError`, including a swapped entry),
    `TREE_TOO_LARGE`, `TREE_UNREADABLE` (root not a real directory). NOT protected: a writer already holding a descriptor from
    before the seal; root ignores mode bits; a same-user process can `chmod` back (a later tree hash would show it); the
    dispatch root itself (marker, venvs). `root` must be a non-empty `str` or `bytes` path (`TREE_UNREADABLE` otherwise: an empty one
    would mean the working directory). Call it only on roots `export_tree` returned."""
    root_path = _root_path(root, "TREE_UNREADABLE")
    try:
        if not stat.S_ISDIR(os.lstat(root_path).st_mode):
            raise BenchmarkGateError("TREE_UNREADABLE", "root is not a real directory")
    except OSError as exc:  # the root itself cannot be looked at: not a sealing failure
        raise BenchmarkGateError("TREE_UNREADABLE", str(exc)) from exc
    try:
        for _, pfd, name, st, dfd in _walk_fd(root_path, _MAX_TREE_ENTRIES):
            if dfd is not None:
                os.fchmod(dfd, stat.S_IMODE(st.st_mode) & ~0o222)
            elif stat.S_ISREG(st.st_mode):
                _fchmod_file(pfd, name, st, 0o222, 0)
    except OSError as exc:
        if not os.path.lexists(root_path):  # the root itself vanished between the check above and the walk
            raise BenchmarkGateError("TREE_UNREADABLE", str(exc)) from exc
        raise BenchmarkGateError("SEAL_FAILED", str(exc)) from exc


def unseal_tree(root: str | os.PathLike, *, bounded: bool = True, _at: tuple[int, str, tuple[int, int]] | None = None) -> None:
    """Inverse of `seal_tree`, by descriptor only: directories `u+rwx` (an unopenable one via `_chmod_dir_nofollow`; where that is
    unavailable it stays), regular files `u+w` (hard-linked or unopenable ones are skipped: deleting a file needs write on its
    directory only). `bounded=False` lifts the entry bound; `_at` is `_walk_fd`'s `at` (`cleanup` walks the directory it claimed and
    holds open, never a path; `root` is then ignored, so callers outside `cleanup` pass a path and no `_at`). Raises
    `BenchmarkGateError`: `TREE_UNREADABLE` (an `OSError`, a non-directory root, or a root that is not a non-empty `str`/`bytes`
    path without NUL), `TREE_TOO_LARGE`."""
    root_path = _root_path(root, "TREE_UNREADABLE") if _at is None else ""  # `cleanup` holds the directory open: no path is used
    try:
        for _, pfd, name, st, dfd in _walk_fd(root_path, _MAX_TREE_ENTRIES if bounded else None, repair=True, at=_at):
            if dfd is None and stat.S_ISREG(st.st_mode):
                try:
                    _fchmod_file(pfd, name, st, 0, 0o200)
                except OSError:
                    pass
    except OSError as exc:
        raise BenchmarkGateError("TREE_UNREADABLE", str(exc)) from exc


_failure = ""  # why the last `cleanup_root` said REMOVE_FAILED, for the CLI (one call at a time per process)
_CLAIM_TAIL = re.compile(r"[0-9a-f]{16}")
_LOCK_WAIT_SECONDS = 5.0  # a loser of an N-way race waits this long for the winner's lock; a removal slower than that is a retryable refusal
_REMOVE_PASSES = 3  # a late writer may add entries; the marker goes only when a pass leaves nothing else


def _failed(reason: str) -> str:
    global _failure
    _failure = escape_diagnostic(reason, 200)
    return "REMOVE_FAILED"


_NO_FLOCK = tuple(getattr(errno, name) for name in ("ENOLCK", "EOPNOTSUPP", "ENOTSUP", "ENOSYS", "EINVAL") if hasattr(errno, name))


def _lock(fd: int) -> bool | None:
    """Exclusive non-blocking `flock`: True (held), False (another process or thread holds it), None (this platform or filesystem has
    no `flock`: `ImportError`, or an errno that means "unsupported", `_NO_FLOCK`; the caller proceeds on the rename claim alone and
    never moves another cleanup's directory). Any other `OSError` (EIO, EBADF, EMFILE ...) is raised: it is not "unsupported", so the
    caller refuses. The kernel drops the lock when its holder dies, even by SIGKILL. `ENOLCK` also means "out of locks" under kernel
    pressure and then fails open too: accepted, it is the same errno network filesystems use for "no locking here"."""
    try:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return False
    except ImportError:
        return None
    except OSError as exc:
        if exc.errno in _NO_FLOCK:
            return None
        raise
    return True


def _claim_state(dir_fd: int, held: str, want: tuple[int, int]) -> str | None:
    """None while `held` is still the directory `want`; `RETRY` when the name is gone (finished or put back by whoever held the
    lock: look again, never answer `ABSENT`); `ROOT_CHANGED` when it is another object."""
    try:
        return None if _id_at(dir_fd, held) == want else "ROOT_CHANGED"
    except FileNotFoundError:
        return "RETRY"


def _id_at(dir_fd: int, name: str) -> tuple[int, int]:
    st = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
    return st.st_dev, st.st_ino


def _open_locked(pfd: int, name: str, want: tuple[int, int], vanished: str) -> tuple[int | None, bool | str]:
    """THE ownership rule: lock first, rename second, put back only under the lock you hold. Open the directory `name` of `pfd`
    (identity `want`, mode repaired to `u+rwx`) and take its exclusive `flock`, waiting up to `_LOCK_WAIT_SECONDS`. Returns
    `(fd, real_lock)` with the lock held (`real_lock` False when there is no `flock` here), or `(None, code)`: `vanished` when the name
    is not there to open, `RETRY` when it vanished while waiting (finished, or put back by the holder), `ROOT_CHANGED`, or
    `REMOVE_FAILED` (still locked after the wait, or the lock failed). Nothing is renamed on any of these paths."""
    try:
        fd = _open_dir(pfd, name, types.SimpleNamespace(st_dev=want[0], st_ino=want[1]), repair=True)
    except FileNotFoundError:
        return None, vanished
    except OSError as exc:
        return None, "ROOT_CHANGED" if isinstance(exc, _EntryChanged) or exc.errno in (errno.ELOOP, errno.ENOTDIR) else _failed(f"cannot open the claimed root: {exc}")
    held = False
    try:
        deadline = time.monotonic() + _LOCK_WAIT_SECONDS
        while (real := _lock(fd)) is False:  # another process holds it: a cleanup finishing this very directory, or a stray
            state = _claim_state(pfd, name, want)
            if state:
                return None, state
            if time.monotonic() > deadline:
                return None, _failed("claimed root is locked by another process")
            time.sleep(0.05)
        state = _claim_state(pfd, name, want)  # the holder may have finished it or put it back just before we got the lock
        held = not state
        return (fd, real is True) if held else (None, state)
    except OSError as exc:
        return None, _failed(f"cannot lock the claimed root: {exc}")
    finally:
        if not held:
            os.close(fd)


def _remove_contents(cfd: int) -> str:
    """Delete everything in the directory open as `cfd` EXCEPT its marker, relative to that descriptor only (never a path),
    recording failures and carrying on. Returns "" or why something is left; the caller deletes the marker LAST, so a stubborn
    entry leaves a directory that still carries its marker (a retry finds it)."""
    failures, first = 0, ""

    def record(_func, _path, exc: BaseException) -> None:
        nonlocal failures
        failures += not isinstance(exc, FileNotFoundError)

    try:
        names = sorted(name for name in os.listdir(cfd) if name != _MARKER_NAME)
    except OSError as exc:
        return f"cannot list the claimed root: {exc}"
    for name in names:
        before = failures
        try:
            if stat.S_ISDIR(os.stat(name, dir_fd=cfd, follow_symlinks=False).st_mode):
                shutil.rmtree(name, dir_fd=cfd, onexc=record)
            else:
                os.unlink(name, dir_fd=cfd)
        except FileNotFoundError:
            pass
        except Exception:  # noqa: BLE001 -- OSError, RecursionError on absurd nesting: counted, never fatal
            failures += 1
        first = first or (name if failures > before else "")
    return f"{failures} entries could not be removed (first: {first})" if failures else ""


def _put_back(pfd: int, held: str, root: str, want: tuple[int, int], cfd: int, code: str | None, marker: dict | None = None) -> str | None:
    """Best effort, for a caller that HOLDS THE LOCK on `cfd` (or made the claim itself where there is no `flock`): rename the claimed
    `held` back to `root` if something is left in it (an empty one stays: nothing to retry), `cfd` is the claimed directory,
    `held` still names it and `root` is free; a `marker` already deleted is written back first, so the retry finds it
    (and an interrupt or a failing `rmdir` after that deletion loses nothing). Returns `code`."""
    try:
        if (os.fstat(cfd).st_dev, os.fstat(cfd).st_ino) != want:  # `cfd` is not the claimed directory: nothing here is ours to move
            return code
        if marker is not None or os.listdir(cfd):
            if marker is not None and _MARKER_NAME not in os.listdir(cfd):
                fd = os.open(_MARKER_NAME, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=cfd)
                with os.fdopen(fd, "wb") as handle:
                    os.fchmod(fd, 0o600)
                    handle.write(json.dumps(marker, sort_keys=True).encode("ascii"))
            if _id_at(pfd, held) == want:
                try:
                    os.stat(root, dir_fd=pfd, follow_symlinks=False)  # `root` taken: a rename would replace an empty directory
                except FileNotFoundError:
                    os.rename(held, root, src_dir_fd=pfd, dst_dir_fd=pfd)
    except OSError:
        pass
    return code


def _finish(pfd: int, held: str, want: tuple[int, int], root: str, cfd: int, claimed_now: bool, real_lock: bool) -> str:
    """Remove the directory `held` of `pfd` (identity `want`, marker naming `root`) through `cfd`, the descriptor the caller opened
    and LOCKED (`_open_locked`; the caller closes it): the root this call just claimed, or an abandoned claim. The tree is put back
    (on a refusal or any `BaseException`) only by a call that holds a real lock or made the claim itself; a recoverer without a real
    lock (no `flock` here) leaves the claim alone. `RETRY`: the name vanished at the end (finished, or put back): look again."""
    may_move, gone = claimed_now or real_lock, None  # `gone`: the marker, once it has been deleted

    def back(code: str | None, marker: dict | None = None) -> str | None:
        return _put_back(pfd, held, root, want, cfd, code, marker) if may_move else code

    try:
        try:
            marker = _read_marker("", dir_fd=cfd, expect=root)
        except BenchmarkGateError as exc:  # an EMPTY directory without its marker has nothing left to protect
            if exc.code != "MARKER_MISSING" or os.listdir(cfd):  # an unproven leftover stays where it is; a claimed root goes back
                return back(exc.code) if claimed_now else exc.code
        else:
            if _pid_alive(marker["pid"]):  # re-pointed (`claim_root`) after the pre-claim check
                return back("OWNER_ALIVE")
            try:
                unseal_tree("", bounded=False, _at=(pfd, held, want))
            except BenchmarkGateError:
                pass  # best effort; the removal below decides
            for _ in range(_REMOVE_PASSES):
                why = _remove_contents(cfd)
                if why or not set(os.listdir(cfd)) - {_MARKER_NAME}:
                    break
            else:
                why = "entries keep appearing in the claimed root"
            if why:
                return back(_failed(why))
            gone = marker  # before the unlink: an interrupt right after it must still find the marker to restore
            try:
                os.unlink(_MARKER_NAME, dir_fd=cfd)
            except FileNotFoundError:
                gone = None
        if _id_at(pfd, held) != want:  # swapped aside meanwhile: its contents are gone, but that name is not ours to remove
            return "ROOT_CHANGED"
        os.rmdir(held, dir_fd=pfd)
        return "REMOVED"
    except FileNotFoundError:  # the name vanished under us (finished or put back by someone else, without a lock to stop it): look again
        return "RETRY"
    except OSError as exc:
        return back(_failed(str(exc)), gone)
    except BaseException:
        back(None, gone)
        raise


def _recover(root: str | os.PathLike) -> str:
    """Finish the claims `.gone-<root>-<random>` of earlier cleanups of this root that died before they were done, so `ABSENT`
    means nothing is left that no live cleanup is working on. Selected by a VALIDATED MARKER (naming `root`, owner dead, a
    directory of ours, not a link; the name only narrows the search), and only under its `flock` (`_open_locked`). A marker-less
    empty one is just removed. Returns `REMOVED` / `ABSENT` / the refusal of any that was left; `RETRY` (which dominates) when any
    claim vanished or was put back meanwhile, and when `root` itself exists again after an empty scan."""
    path = os.path.abspath(os.fspath(root))
    name = os.path.basename(path)
    try:
        pfd = os.open(os.path.realpath(os.path.dirname(path)), os.O_RDONLY | os.O_DIRECTORY)
    except FileNotFoundError:
        return "ABSENT"
    except OSError as exc:
        return _failed(f"cannot scan for abandoned claims: {exc}")
    result = "ABSENT"
    try:
        prefix = f".gone-{name}-"
        for entry in sorted(os.listdir(pfd)):
            if not (entry.startswith(prefix) and _CLAIM_TAIL.fullmatch(entry[len(prefix):])):
                continue
            try:
                st = os.stat(entry, dir_fd=pfd, follow_symlinks=False)
            except FileNotFoundError:
                continue
            if stat.S_ISDIR(st.st_mode) and not _foreign(st):
                cfd, real = _open_locked(pfd, entry, (st.st_dev, st.st_ino), "RETRY")
                if cfd is None:
                    code = real
                else:
                    try:
                        code = _finish(pfd, entry, (st.st_dev, st.st_ino), name, cfd, False, real)
                    finally:
                        os.close(cfd)
                if code == "RETRY" or result == "RETRY":
                    result = "RETRY"
                elif code != "ABSENT" and result in ("ABSENT", "REMOVED"):
                    result = code
        if result == "ABSENT" and os.path.lexists(os.path.join(os.path.dirname(path), name)):
            return "RETRY"  # the holder of a claim put the tree back at the root name between the first look and this scan
    except OSError as exc:
        return _failed(f"cannot scan for abandoned claims: {exc}")
    finally:
        os.close(pfd)
    return result


def _more_descriptors():
    """Raise the soft `RLIMIT_NOFILE` to `min(hard, 4096)` (a walk holds one descriptor per level; macOS defaults to 256). Returns
    the old limits to give back, or None (not raised, or no `resource`)."""
    try:
        import resource
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        want = 4096 if hard == resource.RLIM_INFINITY else min(hard, 4096)
        if soft >= want:
            return None
        resource.setrlimit(resource.RLIMIT_NOFILE, (want, hard))
        return soft, hard
    except (ImportError, ValueError, OSError):
        return None


def cleanup_root(root: str | os.PathLike) -> str:
    """Remove a dispatch-unique root; return `REMOVED` / `ABSENT` or a refusal code (`CLEANUP_CODES`).

    Only if the path is a directory directly under the private `fixed_parent()` (not a symlink), owned by this user, with a
    valid marker whose pid is not alive. The root is opened by descriptor, checked against the identity recorded at validation
    and given `u+rwx` (a mode-0 root with a valid marker is cleanable), then CLAIMED by an atomic rename to a private
    `.gone-<root>-<64 random bits>` name: of overlapping cleanups exactly one claims it, the rest find it gone and then wait for its lock (below). The
    claimed directory is the one descriptor opened (and locked) before the rename, checked against the validated identity, and its marker read again (a pid re-pointed meanwhile
    is `OWNER_ALIVE`); unseal (no export entry bound: a legal root holds two exports and venvs), removal (marker LAST) and the
    final `rmdir` use that descriptor, never a path, so a same-user process that renames the claimed directory aside and plants
    a symlink cannot steer a delete (the contents still go, the verdict is `ROOT_CHANGED`). Anything left: renamed back,
    `REMOVE_FAILED`, and a retry finds the marker. `ROOT_CHANGED` only for a root that EXISTS with another identity. Never a name pattern.

    SIGINT, SIGTERM and SIGHUP (the CLI makes them `KeyboardInterrupt`, SIGINT even when it was inherited as ignored: on purpose) put the
    tree back, marker included even when the interrupt lands after the marker was deleted: the next call is `REMOVED`. The
    interrupted CLI exits 1 with EMPTY stdout ("exit 1 and no code" means retry). A cleanup killed by SIGKILL or power loss
    after the claim leaves `.gone-<root>-<hex>` (maybe half removed or sealed), as does a refusal below. **Ownership rule: lock
    first, rename second, put back only under the lock you hold.** The root is opened (mode repaired to `u+rwx`) and its exclusive
    `flock` taken BEFORE the claiming rename, and that one descriptor, with its identity, carries the whole call: a cleanup renames,
    restores a marker, removes or puts a tree back only through a descriptor on which it holds the lock, so one that merely waits (or
    was interrupted while waiting) never moves another cleanup's directory, and a recoverer can lock a claim only after its owner has
    released it or died (the kernel drops the lock then, even for SIGKILL). A lock that stays held for `_LOCK_WAIT_SECONDS` (5.0 s,
    long enough for a normal removal; tests set it small) is `REMOVE_FAILED` ("claimed root is locked by another process") with
    NOTHING renamed. **Callers (C4f): exit 1 with `REMOVE_FAILED` and that stderr text means retry later; so does "no code".** The next
    `cleanup_root(<root>)` finishes each leftover (`_recover`) whose VALIDATED MARKER names the root (owner dead; a directory of
    ours, not a link; the name only narrows the search; an empty marker-less one is just removed) and answers `REMOVED`, or the
    refusal for one it could not finish. A non-empty marker-less `.gone-<root>-<16 hex>` (e.g. a SIGKILL during the marker restore) is
    `MARKER_MISSING` until a human removes it or writes the marker back. `RETRY` (internal) is any claim that vanished or was put
    back while this call waited, and the root name existing again after an empty scan: `cleanup_root` looks again (up to 3 times,
    then `REMOVE_FAILED`) and never turns it into `ABSENT`. So `ABSENT` means: the path is gone AND no leftover of this root that
    this call could examine remains; an error while scanning is `REMOVE_FAILED`. The losers of an N-way race answer `ABSENT` only
    when the winner finishes within the wait. `flock` failing with an errno that means "unsupported" (`ENOLCK`, `EOPNOTSUPP`,
    `ENOSYS`, `EINVAL`, or no `fcntl`) leaves the rename claim alone: two cleaners may then both finish one claim (both may report
    `REMOVED`), and only the call that made a claim ever puts it back; any other `flock` error (`EIO`, `EBADF`, `EMFILE`) is a
    refusal. A leftover of an earlier incarnation of `<root>` is not touched while `<root>` exists (the next call finishes it).
    Killed before the claim, nothing changed but modes. The soft `RLIMIT_NOFILE` is raised to `min(hard, 4096)` for the call:
    process-wide, so other threads see it (the CLI is unaffected). POSIX only. Depth bound: one descriptor per level, so a chain
    deeper than ~4,090 levels is not removable under a soft `RLIMIT_NOFILE` of 256 (macOS; Linux's usual 1M is not reached):
    hostile-only, no safety impact. Residual: a rename back onto an EMPTY directory at the root name replaces it.

    The root's mode is repaired BEFORE the marker is read (a mode-0 root hides its marker), so a refused cleanup (bad marker,
    live owner) can leave a 0500 root at 0700. Residual: the fixed parent and the root are validated BY PATH and re-checked
    just before the claiming rename, which narrows but cannot close the window; a same-uid process can redirect it, gaining no
    capability (it can already write, chmod and delete those directories)."""
    old = _more_descriptors()
    try:
        for _ in range(3):  # `RETRY`: the claim vanished under a waiting call (finished, or put back): look at the state again
            code = _cleanup(root)
            code = _recover(root) if code == "ABSENT" else code
            if code != "RETRY":
                return code
        return _failed("the root kept changing while it was being cleaned up")
    finally:
        if old is not None:
            import resource
            try:
                resource.setrlimit(resource.RLIMIT_NOFILE, old)
            except (ValueError, OSError):
                pass


def _cleanup(root: str | os.PathLike) -> str:
    try:
        path, identities = _checked_root(root)
    except BenchmarkGateError as exc:
        return exc.code
    parent, name = os.path.split(path)
    pfd = cfd = -1
    try:
        pfd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        if (os.fstat(pfd).st_dev, os.fstat(pfd).st_ino) != identities[0]:
            return "ROOT_CHANGED"
        opened, real = _open_locked(pfd, name, identities[1], "ABSENT")  # LOCK FIRST (RECORDED identity): nothing below renames without it
        if opened is None:
            return real
        cfd = opened
        marker = _read_marker(path)
        if _pid_alive(marker["pid"]):
            return "OWNER_ALIVE"
        claimed = f".gone-{name}-{os.urandom(8).hex()}"
        if (_identity(parent), _identity(path)) != identities:
            return "ROOT_CHANGED"
        try:
            os.rename(name, claimed, src_dir_fd=pfd, dst_dir_fd=pfd)
            if _id_at(pfd, claimed) != identities[1]:  # raced the rename: what was moved is not what was validated; undo OUR rename
                os.rename(claimed, name, src_dir_fd=pfd, dst_dir_fd=pfd)
                return "ROOT_CHANGED"
            return _finish(pfd, claimed, identities[1], name, cfd, True, real)
        except BaseException:  # an interrupt anywhere from the rename on: put the claim back, through the locked descriptor
            _put_back(pfd, claimed, name, identities[1], cfd, None)
            raise
    except BenchmarkGateError as exc:
        return "ABSENT" if exc.code == "MARKER_MISSING" and not os.path.lexists(path) else exc.code
    except FileNotFoundError:  # a concurrent cleanup claimed it first
        return "ABSENT"
    except OSError as exc:
        return "ROOT_CHANGED" if exc.errno in (errno.ELOOP, errno.ENOTDIR) else _failed(str(exc))
    finally:
        for fd in (cfd, pfd):
            if fd >= 0:
                os.close(fd)


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


def _child_setup(cap: int | None):
    """A `preexec_fn` for every git child: a fixed `umask 022` (so an export's modes do not depend on the caller's umask) and,
    when `cap` is given, every file the child writes capped at `cap + 1` bytes, clamped to the hard limit it inherited (a lower
    hard limit would make `setrlimit` raise). `resource` is POSIX-only: lazy import."""
    def apply() -> None:
        import resource

        os.umask(0o022)
        if cap is not None:
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
            os.chmod(self._dir, 0o700)  # umask-proof
            home = os.path.join(self._dir, "home")
            os.mkdir(home, 0o700)
            os.chmod(home, 0o700)
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
        kwargs = {"preexec_fn": _child_setup(cap)} if os.name == "posix" else {}
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


def _parse_listing_oids(raw: bytes) -> dict[str, str]:
    """`git ls-tree -r -z [-l]` -> `{relpath: object id}` (40 or 64 lowercase hex). A sibling of `_parse_listing`, which keeps its tuple
    shape: `verify_export_against_commit` parses the same bytes with both. A record that does not parse, or an id that is not hex of a
    git hash width, is `GIT_FAILED`; path policy (`EXPORT_*`) stays `_parse_listing`'s."""
    oids: dict[str, str] = {}
    records = raw.split(b"\0")
    if records.pop() != b"":
        raise BenchmarkGateError("GIT_FAILED", "unterminated ls-tree output")
    for record in records:
        meta, tab, raw_path = record.partition(b"\t")
        try:
            fields = meta.decode("ascii").split()
        except UnicodeDecodeError as exc:
            raise BenchmarkGateError("GIT_FAILED", "unparseable ls-tree record") from exc
        if not tab or len(fields) not in (3, 4) or _COMMIT_RE.fullmatch(fields[2]) is None:
            raise BenchmarkGateError("GIT_FAILED", "unparseable ls-tree record")
        oids[os.fsdecode(raw_path)] = fields[2]
    return oids


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
    never sees a root without a marker). True if this call created it; False if it existed (an existing directory, even an
    empty marker-less one, is never replaced), which the caller validates."""
    root = os.path.join(parent, name)
    if os.path.lexists(root):
        return False
    try:
        tmp = tempfile.mkdtemp(dir=parent, prefix=".new-")
    except OSError as exc:
        raise BenchmarkGateError("DEST_REJECTED", f"cannot create a root: {exc}") from exc
    try:
        os.chmod(tmp, 0o700)  # umask-proof
        _write_marker(tmp, owner, name)
        os.rename(tmp, root)
        return True
    except OSError as exc:
        if exc.errno not in (errno.ENOTEMPTY, errno.EEXIST, errno.ENOTDIR):
            raise BenchmarkGateError("DEST_REJECTED", f"cannot create the root: {exc}") from exc
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
    for taken in (sidecar, f"{sidecar}.{os.getpid()}.tmp"):  # never replace or trip over something that is already there
        if os.path.lexists(taken):
            raise BenchmarkGateError("DEST_REJECTED", "a sidecar path is already taken")

    with _PrivateGit(repo, length) as git:  # nothing is created in the root until the commit and its listing are validated
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
                os.chmod(export_dir, 0o755)  # umask-proof: the checkout must be able to write into it
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
    default the short-lived exporting process, so `cleanup` is allowed right after export unless `--owner-pid` names a
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
    write, chmod and delete those directories). A SIGTERM mid-export leaves a `bench-git-*` directory (index-sized) in the temp
    directory; `cleanup` cannot reach it."""
    return _export(repo, commit, dest, owner_pid)[0]


# ---------------------------------------------------------------------------
# C4c-2a: tree hash and benchmark overlay
#
# `compare` (C4d) calls these as library functions: overlay the benchmark into the base export, seal both trees, hash them,
# measure, hash again. Both work on descriptors (`_walk_fd`), never follow a symlink, and fail closed.
# ---------------------------------------------------------------------------

_HASH_MAGIC = b"software-builder-bench-tree-v2\0"
_MAX_HASH_BYTES = 4 << 30
_MAX_HASH_DEPTH = 128  # a deeper tree is refused: the walk holds one descriptor per level and its cost grows faster than linearly
_MAX_BENCHMARK_FILE_BYTES = _MAX_BENCHMARK_BYTES  # one limit: the lint and the copy must agree
_MAX_VALIDATOR_BYTES = 1 << 20
_NOFOLLOW_DIR = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
_NOT_A_DIRECTORY_ERRNOS = frozenset({errno.ELOOP, errno.ENOTDIR, errno.EMLINK})  # what `O_NOFOLLOW | O_DIRECTORY` says of a symlink or file
_BAD_PATH_ERRNOS = frozenset({errno.ENOENT, errno.ENOTDIR, errno.ELOOP, errno.EACCES, errno.EPERM, errno.ENAMETOOLONG})
_SPECIAL_KINDS = {stat.S_IFIFO: b"P", stat.S_IFSOCK: b"K", stat.S_IFCHR: b"C", stat.S_IFBLK: b"B"}


def _describe(exc: BaseException) -> str:
    """`Type: message` for a detail string, safe against an exception whose `__str__` or `__repr__` itself raises, cut to 400
    characters (the message is still built before it is cut)."""
    try:
        if isinstance(exc, BenchmarkGateError):
            return f"{exc.code}: {exc.detail}"[:400]
        return f"{type(exc).__name__}: {str(exc)[:400]}"
    except BaseException:  # noqa: BLE001 - this runs inside handlers; it must never raise
        return type(exc).__name__


def hash_tree(root: str | os.PathLike) -> str:
    """sha256 (hex) of the tree under `root`, a real directory, walked by descriptor with no symlink followed. Take it AFTER
    `seal_tree` (and after the install and the overlay): it covers permission bits, so it differs before and after a seal, and a
    `chmod` back changes it. One record per entry, in the walk's canonical order (names sorted at every level, depth first, so
    the order is a function of the tree alone): kind (`D` directory, `F` file, `L` symlink, `P` FIFO, `K` socket, `C` / `B`
    character / block device, `S` other), permission bits (0 for a symlink, whose mode follows the umask on macOS), the path,
    and a body: a file's sha256 and LINK COUNT, a symlink's target, a device's `st_rdev`. Directories and empty directories
    (a gitlink) appear; timestamps, extended attributes and flags do not. Length-prefixed fields make the record stream
    injective. The link count is deliberate: `seal_tree` refuses a multiply linked file, so a count that rises afterwards
    means someone made an alias, a second write path into a sealed inode. The result is a bare digest: it says THAT the tree changed,
    not why.
    Memory is constant in the tree size (records stream into the digest).

    NOT an atomic snapshot: each directory is listed once, when the walk reaches it, so an entry added to a directory already
    listed is missed by this pass (one removed fails the pass). A file whose inode, link count, size, mtime or ctime moves while it
    is read (compared with a fresh `stat` of its NAME after the read, so a rename-over is seen too) is an `_EntryChanged` failure,
    but a writer that restores them, or one that acts inside the filesystem's timestamp granularity (about 4 ms of ctime and mtime on
    Linux), is not caught. The guarantee comes from `compare` taking two full passes (before and after measurement) of a SEALED
    tree and comparing them.

    Raises `BenchmarkGateError`: `TREE_UNREADABLE` (any `OSError`, a root that is not a non-empty `str` or `bytes` path, a swapped
    or changing entry, an unreadable file), `TREE_TOO_LARGE` (over 100,000 entries, 128 levels or 4 GiB of file content, or out of
    memory)."""
    root_path = _root_path(root, "TREE_UNREADABLE")
    out = hashlib.sha256(_HASH_MAGIC)
    total = 0
    try:
        for rel, pfd, name, st, dfd in _walk_fd(root_path, _MAX_TREE_ENTRIES, max_depth=_MAX_HASH_DEPTH):
            if rel.count("/") >= _MAX_HASH_DEPTH:
                raise BenchmarkGateError("TREE_TOO_LARGE", f"more than {_MAX_HASH_DEPTH} levels")
            mode = stat.S_IMODE(st.st_mode)
            if dfd is not None:
                kind, body = b"D", b""
            elif stat.S_ISLNK(st.st_mode):
                kind, mode, body = b"L", 0, os.fsencode(os.readlink(name, dir_fd=pfd))
            elif stat.S_ISREG(st.st_mode):
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0), dir_fd=pfd)
                try:
                    before = os.fstat(fd)
                    if not stat.S_ISREG(before.st_mode) or (before.st_dev, before.st_ino) != (st.st_dev, st.st_ino):
                        raise _EntryChanged("entry changed while it was being read")
                    digest, size = hashlib.sha256(), 0
                    while chunk := os.read(fd, 1 << 20):
                        size += len(chunk)
                        total += len(chunk)
                        if total > _MAX_HASH_BYTES:
                            raise BenchmarkGateError("TREE_TOO_LARGE", f"more than {_MAX_HASH_BYTES} bytes of content")
                        digest.update(chunk)
                    after = os.stat(name, dir_fd=pfd, follow_symlinks=False)  # by NAME: a rename-over shows as another inode
                    fields = ("st_dev", "st_ino", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
                    if size != before.st_size or any(getattr(after, f) != getattr(before, f) for f in fields):
                        raise _EntryChanged("a file changed while it was being hashed")
                finally:
                    os.close(fd)
                kind, body = b"F", b"%s:%d" % (digest.hexdigest().encode("ascii"), before.st_nlink)
            else:
                kind = _SPECIAL_KINDS.get(stat.S_IFMT(st.st_mode), b"S")
                body = b"%d" % st.st_rdev if kind in (b"C", b"B") else b""
            path = os.fsencode(rel)
            out.update(b"%s %o %d:%s %d:%s" % (kind, mode, len(path), path, len(body), body))
    except (OSError, ValueError) as exc:  # ValueError: an embedded NUL in the root
        raise BenchmarkGateError("TREE_UNREADABLE", str(exc)) from exc
    except MemoryError as exc:
        raise BenchmarkGateError("TREE_TOO_LARGE", "out of memory while hashing") from exc
    return out.hexdigest()


_task_target_lock = threading.RLock()
_task_target_state: tuple | None = None  # (module, sha256 hex of the exact source that was executed), replaced as one unit
_task_target_loading = False  # True while the validator's module code runs: a re-entrant load is refused, not deadlocked
_LOAD_LOCK_SECONDS = 30


def _task_target_path() -> Path:
    """`validate_task_target.py` beside this file: the one place both the loader and `harness_sha256` look."""
    return Path(__file__).resolve().with_name("validate_task_target.py")


def _reset_task_target_cache() -> None:
    """Forget the loaded validator (tests; also a way to pick up a changed file in a long-lived process)."""
    global _task_target_state
    with _task_target_lock:
        _task_target_state = None
        sys.modules.pop("_benchmark_gate_validate_task_target", None)


def _load_task_target() -> tuple:
    """`(module, sha256)` of the sibling `validate_task_target.py`, loaded once. The source is read ONCE and the module is built from
    those bytes by a loader with no bytecode cache, so what runs is exactly what the digest reports (no stale `.pyc`, no swap
    between a hash and the load). The module is registered under a private name and has `__file__`, so a later edit using
    dataclasses, enums or typing helpers keeps working. Any `Exception`, including a re-entrant load from the module's own code, is `OVERLAY_FAILED`; a `SystemExit`
    or `KeyboardInterrupt` passes through (see `_call_validator`)."""
    global _task_target_state, _task_target_loading
    if not _task_target_lock.acquire(timeout=_LOAD_LOCK_SECONDS):  # another thread is stuck loading (e.g. the module body joins a thread of ours)
        raise BenchmarkGateError("OVERLAY_FAILED", "timed out waiting for the validator load")
    try:
        if _task_target_state is not None:
            return _task_target_state
        if _task_target_loading:
            raise BenchmarkGateError("OVERLAY_FAILED", "the validator's own code re-entered its load")
        import importlib.abc
        import importlib.util

        name = "_benchmark_gate_validate_task_target"
        _task_target_loading = True
        try:
            path = _task_target_path()
            source = _read_bounded(os.fspath(path), _MAX_VALIDATOR_BYTES)
            if len(source) > _MAX_VALIDATOR_BYTES:
                raise ValueError("over 1 MiB")

            class _SourceOnly(importlib.abc.SourceLoader):  # no `path_stats` / `set_data`: nothing is cached or written
                def get_filename(self, fullname):
                    return os.fspath(path)

                def get_data(self, data_path):
                    return source

            loader = _SourceOnly()
            spec = importlib.util.spec_from_loader(name, loader, origin=os.fspath(path))
            module = importlib.util.module_from_spec(spec)
            module.__file__ = os.fspath(path)
            sys.modules[name] = module
            try:
                loader.exec_module(module)
            except BaseException:  # SystemExit/KeyboardInterrupt included: it passes through, the half-loaded module does not stay
                sys.modules.pop(name, None)
                raise
            if not callable(getattr(module, "validate_task_target", None)):
                sys.modules.pop(name, None)
                raise AttributeError("no callable validate_task_target")
        except Exception as exc:  # unreadable, a syntax error, an import-time failure: one coded refusal
            raise BenchmarkGateError("OVERLAY_FAILED", f"cannot load validate_task_target.py: {_describe(exc)}") from exc
        finally:
            _task_target_loading = False
        _task_target_state = (module, hashlib.sha256(source).hexdigest())
        return _task_target_state
    finally:
        _task_target_lock.release()


def _call_validator(root: str, target: str) -> object:
    """`validate_task_target(root, target)` of the loaded validator. Any `Exception` it raises is `OVERLAY_FAILED`. A `SystemExit`
    or `KeyboardInterrupt` is NOT converted: it cannot be told from a shutdown request of our own process delivered while this
    frame is running (a signal handler runs in whatever frame is current), and the validator is this repository's own file."""
    function = _load_task_target()[0].validate_task_target
    try:
        return function(root, target)
    except Exception as exc:
        raise BenchmarkGateError("OVERLAY_FAILED", f"validate_task_target raised {_describe(exc)}") from exc


def _task_target_sha256() -> str:
    """sha256 of the exact bytes of `validate_task_target.py` that were loaded."""
    return _load_task_target()[1]


def _digest_own_file() -> str:
    """sha256 (hex) of this file's SOURCE bytes as they are on disk when the module is imported, or "" if they cannot be read (then
    `harness_sha256` is `HARNESS_UNREADABLE`, never a digest of something else). It is the source, not the code object that runs: a
    stale `.pyc` that matches the source's size and mtime would not be noticed (needs a same-user writer; the accepted residual)."""
    try:
        with open(os.fspath(Path(__file__).resolve()), "rb") as handle:
            data = handle.read(4 << 20 | 1)
        return hashlib.sha256(data).hexdigest() if len(data) <= 4 << 20 else ""
    except Exception:  # noqa: BLE001 - a missing __file__ (embedded loaders), an unreadable file, a symlink loop
        return ""


_SELF_DIGEST = _digest_own_file()  # at import: the file the importer used, not whatever is on disk at the first call


def harness_sha256() -> str:
    """The `harness_sha256` of the `compare` result: sha256 over the digest of this file's source as on disk at IMPORT and the digest of
    the loaded `validate_task_target.py` (length-prefixed, domain `software-builder-bench-harness-v1`). Both name the code this
    process has been using (up to the stale-`.pyc` residual of `_digest_own_file`): this file is digested when it is imported, the
    validator when it is loaded (and cached until
    `_reset_task_target_cache()`). The trace plugin is a constant inside this file, so the own-file digest covers it; the domain string stays ``-v1``.
    `HARNESS_UNREADABLE` if either part cannot be read. It is not a file hash (`sha256sum` cannot reproduce it): the CLI command ``harness-sha256``
    prints it, and the EXPECTED value must be taken from a TRUSTED copy of the harness (the pinned release, or ``harness-sha256`` run in a clean
    checkout), never from a previous `compare` result (circular: a tampered harness would vouch for itself)."""
    try:
        if not _SELF_DIGEST:
            raise ValueError("this file could not be read when it was imported")
        own_digest = _SELF_DIGEST.encode("ascii")
        validator = _task_target_sha256().encode("ascii")
    except BenchmarkGateError as exc:
        raise BenchmarkGateError("HARNESS_UNREADABLE", exc.detail or exc.code) from exc
    except Exception as exc:
        raise BenchmarkGateError("HARNESS_UNREADABLE", _describe(exc)) from exc
    return hashlib.sha256(b"software-builder-bench-harness-v1\0%d:%s%d:%s" % (len(own_digest), own_digest, len(validator), validator)).hexdigest()


def _export_root(path: object, label: str) -> str:
    """The same shape `export` produces: `<fixed parent>/<root name>/<leaf name>`, resolved, with the dispatch root a real directory
    (not a symlink) of ours directly under the private fixed parent and carrying a valid marker, and the leaf a real directory of
    ours. `path` must be a `str` or a `PathLike` returning a `str`. `DEST_REJECTED` for anything wrong with the path or the ownership;
    an environmental failure (EIO, EMFILE) is an `OSError` for the caller to classify as `OVERLAY_FAILED`."""
    try:
        raw = os.fspath(path)  # type: ignore[arg-type]  # a hostile __fspath__ may raise anything, even SystemExit
        if type(raw) is not str or not raw:
            raise TypeError("not a non-empty str path")
    except (Exception, SystemExit) as exc:
        raise BenchmarkGateError("DEST_REJECTED", f"{label} is not a usable path: {_describe(exc)}") from exc
    try:
        leaf_path = Path(os.path.abspath(raw))
        if not (_ROOT_NAME_RE.fullmatch(leaf_path.parent.name) and _LEAF_NAME_RE.fullmatch(leaf_path.name)):
            raise BenchmarkGateError("DEST_REJECTED", f"{label} must be <fixed parent>/<root name>/<leaf name>")
        unresolved_root = os.lstat(leaf_path.parent)
        if not stat.S_ISDIR(unresolved_root.st_mode):  # a symlinked dispatch root is not "directly under" the fixed parent
            raise BenchmarkGateError("DEST_REJECTED", f"{label}'s dispatch root is a symlink or not a directory")
        fixed = os.path.realpath(_check_parent(create=False))
        root_dir = os.path.realpath(leaf_path.parent)
        if root_dir != os.path.join(fixed, leaf_path.parent.name):  # the resolved name must be the requested name (a swap after the lstat)
            raise BenchmarkGateError("DEST_REJECTED", f"{label} must be under {fixed_parent()}")
        root_st = os.lstat(root_dir)
        if not stat.S_ISDIR(root_st.st_mode) or _foreign(root_st):
            raise BenchmarkGateError("DEST_REJECTED", f"{label}'s dispatch root is not a real directory of this user")
        _read_marker(root_dir)
        resolved = os.path.join(root_dir, leaf_path.name)
        st = os.lstat(resolved)
    except BenchmarkGateError as exc:
        raise BenchmarkGateError("DEST_REJECTED", exc.detail or exc.code) from exc
    except OSError as exc:
        if exc.errno in _BAD_PATH_ERRNOS:
            raise BenchmarkGateError("DEST_REJECTED", f"{label} is not an export directory: {_describe(exc)}") from exc
        raise
    except Exception as exc:  # a NUL, a surrogate: the argument is bad, nothing more (a real SystemExit is not ours to swallow)
        raise BenchmarkGateError("DEST_REJECTED", f"{label} is not a usable path: {_describe(exc)}") from exc
    if not stat.S_ISDIR(st.st_mode) or _foreign(st):
        raise BenchmarkGateError("DEST_REJECTED", f"{label} must be a real <fixed parent>/<root>/<leaf> directory of this user")
    return resolved


def export_commit(root: str | os.PathLike) -> str:
    """The commit recorded in an export's sidecar `<root>.export.json` (the file `export_tree` writes beside the export directory) as 40
    or 64 hex, for `compare` to check each export against the commit it was asked for. `root` must be a `str` (or `PathLike`
    returning one) without NUL (a trailing separator is ignored), else `DEST_REJECTED`. `OVERLAY_COMMIT_MISMATCH` when the sidecar is absent, not
    a plain small file, or not valid; an I/O failure (EIO, EMFILE) propagates as `OSError`. The sidecar sits in the dispatch root, which
    the same user can write: this guards against slips and stale directories, not against a same-user attacker."""
    try:
        raw = os.fspath(root)
        if type(raw) is str:
            raw = os.path.abspath(raw) if raw.strip("/" + os.sep) and raw.strip("/" + os.sep + ".") else ""  # same normalisation as `_export_root`
        if type(raw) is not str or not raw or "\0" in raw:
            raise TypeError("not a non-empty str path without NUL")
    except (Exception, SystemExit) as exc:
        raise BenchmarkGateError("DEST_REJECTED", f"root is not a usable path: {_describe(exc)}") from exc
    try:
        data = _read_bounded(raw + ".export.json", 4096, nofollow=True)
    except OSError as exc:
        if exc.errno in (errno.ENOENT, errno.ENOTDIR, errno.ELOOP, errno.EMLINK):
            raise BenchmarkGateError("OVERLAY_COMMIT_MISMATCH", "the export has no readable sidecar") from exc
        raise
    except ValueError as exc:
        raise BenchmarkGateError("OVERLAY_COMMIT_MISMATCH", "the export's sidecar is not a regular file") from exc
    try:
        record = json.loads(data.decode("ascii")) if len(data) <= 4096 else None
    except (ValueError, RecursionError):
        record = None
    commit = record.get("commit") if isinstance(record, dict) else None
    if not (isinstance(commit, str) and _COMMIT_RE.fullmatch(commit)):
        raise BenchmarkGateError("OVERLAY_COMMIT_MISMATCH", "the export's sidecar has no valid commit")
    return commit


def _read_small_file_once(parent_fd: int, name: str, *, permission_is_refusal: bool) -> bytes:
    """The bytes of regular file `name` of directory `parent_fd`: looked at by name first (a socket cannot be opened), then opened
    with `O_NOFOLLOW | O_NONBLOCK`, and the open descriptor must be the very file that was looked at (`fstat`), regular, with ONE
    link (a hard link would read a file outside the export), and still be what the name points to after the read (a by-name
    `stat`); at most 16 KiB. `_FileRefused` for a symlink, special file, hard link or oversize, and (when
    `permission_is_refusal`, true for the Builder's head tree) a permission error; `_FileUnstable` for a swap or a change while
    reading; any other `OSError` (EIO, EMFILE, a vanished entry, and a permission error in OUR base tree) propagates."""
    try:
        before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink > 1:
            raise _FileRefused("not a regular file with a single link")
        leaf = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0), dir_fd=parent_fd)
    except PermissionError as exc:
        if permission_is_refusal:
            raise _FileRefused(f"permission denied: {exc}") from exc
        raise
    except OSError as exc:
        if exc.errno in _NOT_A_DIRECTORY_ERRNOS:
            raise _FileRefused(f"not a regular file: {exc}") from exc
        raise
    try:
        st = os.fstat(leaf)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink > 1 or (st.st_dev, st.st_ino) != (before.st_dev, before.st_ino):
            raise _FileUnstable("the file changed while it was being opened")
        chunks, size = [], 0
        while size <= _MAX_BENCHMARK_FILE_BYTES and (chunk := os.read(leaf, _MAX_BENCHMARK_FILE_BYTES + 1 - size)):
            chunks.append(chunk)
            size += len(chunk)
        done = os.fstat(leaf)
        moved = any(getattr(done, f) != getattr(st, f) for f in ("st_dev", "st_ino", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns"))
        if moved or (st.st_size <= _MAX_BENCHMARK_FILE_BYTES and size != st.st_size):
            raise _FileUnstable("the file was being written while it was read")  # torn bytes: a writer rewrote it in place
        after = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if (after.st_dev, after.st_ino, after.st_nlink) != (st.st_dev, st.st_ino, st.st_nlink):
            raise _FileUnstable("the name no longer points to the file that was read")
    except PermissionError as exc:
        if permission_is_refusal:
            raise _FileRefused(f"permission denied: {exc}") from exc
        raise
    finally:
        os.close(leaf)
    if size > _MAX_BENCHMARK_FILE_BYTES:
        raise _FileRefused("the benchmark file is over 16 KiB")
    return b"".join(chunks)


class _FileRefused(Exception):
    """The file is not an acceptable benchmark (kind, links, size, permissions): a refusal, not an environmental failure."""


class _FileUnstable(Exception):
    """The file kept changing while it was read (a writer, a swap, a background attribute change). Not a verdict about the file's
    kind: it surfaces as `OVERLAY_FAILED` (a crash for `compare`, not a refusal blamed on the Builder) after `_READ_ATTEMPTS` tries."""


_READ_ATTEMPTS = 3


def _read_small_file(parent_fd: int, name: str, *, permission_is_refusal: bool = True) -> bytes:
    """`_read_small_file_once`, retried a few times when the file is seen changing mid-read (a macOS background xattr write, an NFS
    attribute refresh and similar disturb ctime for an instant). `_FileUnstable` if it never settles; `_FileRefused` at once."""
    for attempt in range(_READ_ATTEMPTS):
        try:
            return _read_small_file_once(parent_fd, name, permission_is_refusal=permission_is_refusal)
        except _FileUnstable:
            if attempt == _READ_ATTEMPTS - 1:
                raise
    raise AssertionError("unreachable")  # pragma: no cover


def _head_bytes(head_root: str, parts: list[str]) -> bytes:
    """The benchmark's bytes from an export: every component looked up by EXACT name in a directory listing (a case-insensitive
    filesystem cannot make `Benchmarks/` stand in for `benchmarks/`) and opened with `O_NOFOLLOW` relative to its parent (no
    symlinked parent), the leaf read by `_read_small_file`. A missing exact name is `OVERLAY_PATH_REJECTED`; a symlink, a
    non-directory or unreadable parent, a special file (FIFO, socket, device), a hard link, an unreadable or oversize file is
    `OVERLAY_NOT_REGULAR`; any other `OSError` (EIO, EMFILE, a vanished or swapped entry) propagates."""
    def refuse(detail: str) -> BenchmarkGateError:
        return BenchmarkGateError("OVERLAY_NOT_REGULAR", f"benchmark: {detail}")

    fd = os.open(head_root, _NOFOLLOW_DIR)
    try:
        for index, part in enumerate(parts):
            try:
                present = part in os.listdir(fd)
            except PermissionError as exc:
                raise refuse(f"a parent cannot be listed: {exc}") from exc
            if not present:
                raise BenchmarkGateError("OVERLAY_PATH_REJECTED", "no entry of that exact name (case differs, or it is absent)")
            if index == len(parts) - 1:
                break
            try:
                child = os.open(part, _NOFOLLOW_DIR, dir_fd=fd)
            except OSError as exc:
                if exc.errno in _NOT_A_DIRECTORY_ERRNOS or isinstance(exc, PermissionError):
                    raise refuse(f"a parent is not an openable directory: {exc}") from exc
                raise
            old, fd = fd, child  # detach first: if closing the parent raises, the `finally` below owns the child, not the stale parent
            os.close(old)
        try:
            return _read_small_file(fd, parts[-1])
        except _FileRefused as exc:
            raise refuse(str(exc)) from exc
    finally:
        os.close(fd)


def read_benchmark(export_root: str | os.PathLike, path: str) -> bytes:
    """The benchmark file's bytes inside an export, read under the same rules as the overlay's head read (exact names, no symlink,
    one link, regular, at most 16 KiB). For `benchmark_sha256` and the lint source, call it AFTER `seal_tree` on BOTH the base and the
    head and require the two to be equal: before the seal the head is still writable by whatever the install step started, so only a
    post-seal read names the bytes that are measured. Refusals: `DEST_REJECTED`, `OVERLAY_PATH_REJECTED` (not a `str`, or the gate's lexical
    rules, or no such exact name), `OVERLAY_NOT_REGULAR`; other failures are `OVERLAY_FAILED`."""
    try:
        root = _export_root(export_root, "export_root")
        if type(path) is not str or not _benchmark_path_ok(path):
            raise BenchmarkGateError("OVERLAY_PATH_REJECTED", "path fails the gate's lexical rules")
        return _head_bytes(root, path.split("/"))
    except BenchmarkGateError:
        raise
    except Exception as exc:
        raise BenchmarkGateError("OVERLAY_FAILED", _describe(exc)) from exc


def _top_level_names(dir_fd: int, names: set[str]) -> None:
    """Add the importable top-level names of directory `dir_fd` to `names`: real directories (a namespace package is importable too)
    and real `*.py` files, never a symlink, ASCII identifiers only, at most `_MAX_TREE_ENTRIES` entries read."""
    count = 0
    for name in os.listdir(dir_fd):
        count += 1
        if count > _MAX_TREE_ENTRIES:
            raise BenchmarkGateError("TREE_TOO_LARGE", f"more than {_MAX_TREE_ENTRIES} entries in a top-level directory")
        st = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
        stem = name[:-3] if name.endswith(".py") and stat.S_ISREG(st.st_mode) else name if stat.S_ISDIR(st.st_mode) else ""
        if stem.isascii() and stem.isidentifier():
            names.add(stem)


def seal_export(export_root: str | os.PathLike) -> None:
    """`seal_tree` for an EXPORT: the root must pass the same shape check as the overlay (`<fixed parent>/<root>/<leaf>`, a real directory
    of ours with a valid marker), so a wrong path argument cannot silently seal some other tree. `DEST_REJECTED` for a bad root,
    `OVERLAY_FAILED` for an environmental error; otherwise the errors of `seal_tree`. `compare` should use this, not `seal_tree`."""
    try:
        root = _export_root(export_root, "export_root")
    except BenchmarkGateError:
        raise
    except Exception as exc:
        raise BenchmarkGateError("OVERLAY_FAILED", _describe(exc)) from exc
    seal_tree(root)


def hash_export(export_root: str | os.PathLike) -> str:
    """`hash_tree` for an EXPORT, with the root checked like `seal_export` (same errors)."""
    try:
        root = _export_root(export_root, "export_root")
    except BenchmarkGateError:
        raise
    except Exception as exc:
        raise BenchmarkGateError("OVERLAY_FAILED", _describe(exc)) from exc
    return hash_tree(root)


_VENV_FINGERPRINT_LIMIT = 200_000


def fingerprint_tree(root: str | os.PathLike, *, limit: int) -> str:
    """sha256 over every entry of `root` (no link followed) as `(relpath, dev, ino, mode, nlink, size, mtime_ns, ctime_ns)`, sorted by
    path, plus the root's `(dev, ino, ctime_ns)`. `ctime` cannot be set by a user, so a tamper-and-restore of content or `mtime` still
    moves it. A tree over `limit` entries or deeper than `_MAX_HASH_DEPTH` levels is `TREE_TOO_LARGE`, any `OSError` (an unreadable
    directory, a vanished entry, a root that is not a real directory) is `TREE_UNREADABLE`: a limit or a fault is never a skip."""
    root_path = os.fsdecode(_root_path(root, "TREE_UNREADABLE"))
    records: list[tuple[bytes, bytes]] = []
    try:
        root_st = os.lstat(root_path)
        if not stat.S_ISDIR(root_st.st_mode):
            raise BenchmarkGateError("TREE_UNREADABLE", "root is not a real directory")
        pending = [("", 0)]
        while pending:
            rel, depth = pending.pop()
            with os.scandir(os.path.join(root_path, rel) if rel else root_path) as it:
                names = [entry.name for entry in it]
            for name in names:
                child = os.path.join(rel, name) if rel else name
                st = os.lstat(os.path.join(root_path, child))
                if len(records) >= limit:
                    raise BenchmarkGateError("TREE_TOO_LARGE", f"more than {limit} entries")
                key = os.fsencode(child)
                records.append((key, key + b"\0" + b" ".join(str(n).encode() for n in (
                    st.st_dev, st.st_ino, st.st_mode, st.st_nlink, st.st_size, st.st_mtime_ns, st.st_ctime_ns)) + b"\n"))
                if stat.S_ISDIR(st.st_mode):
                    if depth + 1 > _MAX_HASH_DEPTH:
                        raise BenchmarkGateError("TREE_TOO_LARGE", f"more than {_MAX_HASH_DEPTH} levels")
                    pending.append((child, depth + 1))
    except BenchmarkGateError:
        raise
    except OSError as exc:
        raise BenchmarkGateError("TREE_UNREADABLE", _describe(exc)) from exc
    digest = hashlib.sha256(b"software-builder-bench-fingerprint-v1\0")
    digest.update(f"{root_st.st_dev} {root_st.st_ino} {root_st.st_ctime_ns}\n".encode())
    for _, record in sorted(records):
        digest.update(record)
    return digest.hexdigest()


def repo_top_levels(export_root: str | os.PathLike) -> frozenset[str]:
    """The top-level package and module names of an export (its root and `src/`), the `repo_top_levels` argument of
    `validate_benchmark_content`. Walked by descriptor with no symlink followed (a symlink named like a package, or a symlinked
    `src`, contributes nothing). Compute it from the BASE export BEFORE `overlay_benchmark_file`. `compare` calls it at step 7, AFTER
    the project install, so a build step that created `build/` or `dist/` in the base export has already added those names to the
    allowlist: harmless, and disclosed. A caller that wants the strict list computes it before any install. `DEST_REJECTED`
    for a bad root, `TREE_TOO_LARGE`, `OVERLAY_FAILED` for an I/O failure."""
    try:
        root = _export_root(export_root, "export_root")
        names: set[str] = set()
        fd = os.open(root, _NOFOLLOW_DIR)
        try:
            _top_level_names(fd, names)
            try:
                src_st = os.stat("src", dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                src_st = None
            if src_st is not None and stat.S_ISDIR(src_st.st_mode):
                src = os.open("src", _NOFOLLOW_DIR, dir_fd=fd)
                try:
                    _top_level_names(src, names)
                finally:
                    os.close(src)
        finally:
            os.close(fd)
        return frozenset(names)
    except BenchmarkGateError:
        raise
    except Exception as exc:
        raise BenchmarkGateError("OVERLAY_FAILED", _describe(exc)) from exc


def _same_dir(a: str, b: str) -> bool:
    x, y = os.lstat(a), os.lstat(b)
    return (x.st_dev, x.st_ino) == (y.st_dev, y.st_ino)


def _run_cleanup(steps) -> tuple[BaseException | None, BaseException | None]:
    """Run every cleanup step even if one fails. Returns `(first ordinary failure, first fatal)`; "fatal" is anything that is not an
    `Exception` (a `KeyboardInterrupt`, `SystemExit`), kept apart so an earlier ordinary failure cannot hide it. A vanished entry
    (`FileNotFoundError`: someone else already removed it) is not a failure."""
    failure = fatal = None
    for step in steps:
        try:
            step()
        except FileNotFoundError:
            pass
        except BaseException as exc:  # noqa: BLE001 - cleanup must complete; the caller reports what is left
            if isinstance(exc, Exception):
                failure = failure or exc
            else:
                fatal = fatal or exc
    return failure, fatal


def _overlay_into_base(base_root: str, parts: list[str], data: bytes) -> str:
    """Look `parts` up in the base export by EXACT name (a listing, never the filesystem's case folding) and either confirm the
    bytes equal `data` (`PRE_EXISTING`) or create the file (`BUILDER_AUTHORED`), creating missing parent directories (mode 0755,
    set explicitly: `mkdir` is masked by the umask) only below `base_root`. Every step is relative to an `O_NOFOLLOW` directory
    descriptor. On ANY failure this call tries to remove what it created (the file, then the directories), each only if it is still
    the very inode this call made: the created file's descriptor and every created directory's stay OPEN until the cleanup has run,
    so an inode number cannot be reused under the check (and an identity that could not be read at creation is read again from the
    open descriptor; if that fails too the file is left and reported). Best effort and sound against a quiescent base (single
    writer): POSIX has no unlink-with-identity, so a rename over the name between the check and the removal is not prevented. A
    cleanup that cannot finish is reported (`OVERLAY_FAILED`, "cleanup incomplete"), never silent. A `KeyboardInterrupt` or
    `SystemExit` (whether it was the original failure or struck during cleanup) is re-raised as itself, after the cleanup ran."""
    fds = [os.open(base_root, _NOFOLLOW_DIR)]
    made: list[list] = []  # [index into fds of the parent, name, (dev, ino) or None] of directories this call created
    leaf_made: list = []  # [name, identity or None] once the O_EXCL create has returned
    out = -1
    try:
        for part in parts[:-1]:
            parent = fds[-1]
            if part in os.listdir(parent):
                try:
                    fds.append(os.open(part, _NOFOLLOW_DIR, dir_fd=parent))
                except OSError as exc:
                    if exc.errno in _NOT_A_DIRECTORY_ERRNOS:
                        raise BenchmarkGateError("OVERLAY_PATH_CONFLICT", f"base component is not a directory: {exc}") from exc
                    raise
                continue
            try:
                os.mkdir(part, 0o755, dir_fd=parent)  # a case-folded twin ("Benchmarks" for "benchmarks") raises FileExistsError
            except PermissionError as exc:  # a sub-directory of the base is read-only: sealed below its root
                raise BenchmarkGateError("OVERLAY_BASE_SEALED", f"cannot create {part!r}: {_describe(exc)}") from exc
            except FileExistsError as exc:
                raise BenchmarkGateError("OVERLAY_PATH_CONFLICT", "a parent appeared concurrently or has a case-folded twin in the base") from exc
            made.append([len(fds) - 1, part, None])  # at once, before anything else can fail: the identity is filled in next
            created = os.stat(part, dir_fd=parent, follow_symlinks=False)
            made[-1][2] = (created.st_dev, created.st_ino)
            fds.append(os.open(part, _NOFOLLOW_DIR, dir_fd=parent))
            opened = os.fstat(fds[-1])
            if (opened.st_dev, opened.st_ino) != (created.st_dev, created.st_ino):
                raise BenchmarkGateError("OVERLAY_PATH_CONFLICT", "a parent was replaced while it was being created")
            os.fchmod(fds[-1], 0o755)
        parent, leaf = fds[-1], parts[-1]
        if leaf in os.listdir(parent):
            try:
                same = _read_small_file(parent, leaf, permission_is_refusal=False) == data
            except _FileRefused:
                same = False  # a symlink, directory, special file or hard link where the head has a regular file
            if not same:
                raise BenchmarkGateError("BENCHMARK_MODIFIED", "the benchmark exists at the base and differs (bytes, kind or link count)")
            return "PRE_EXISTING"
        try:
            out = os.open(leaf, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=parent)
        except PermissionError as exc:
            raise BenchmarkGateError("OVERLAY_BASE_SEALED", f"cannot create the benchmark: {_describe(exc)}") from exc
        except FileExistsError as exc:
            raise BenchmarkGateError("OVERLAY_PATH_CONFLICT", "the benchmark appeared concurrently or has a case-folded twin in the base") from exc
        leaf_made.append([leaf, None])  # the name is ours from here on (O_EXCL); the identity is filled in next
        made_st = os.fstat(out)
        leaf_made[0][1] = (made_st.st_dev, made_st.st_ino)
        os.fchmod(out, 0o644)
        view = memoryview(data)
        while view:
            view = view[os.write(out, view):]
        closing, out = out, -1  # detach first: a close that raises must not be repeated on a number another thread may now hold
        os.close(closing)
        return "BUILDER_AUTHORED"
    except BaseException as original:
        def remove_leaf():
            name, ident = leaf_made[0]
            if ident is None:
                if out < 0:
                    raise OSError("the created file could not be identified")
                got = os.fstat(out)  # still open: the identity can be read again
                ident = (got.st_dev, got.st_ino)
            now = os.stat(name, dir_fd=fds[-1], follow_symlinks=False)
            if (now.st_dev, now.st_ino) == ident:
                os.unlink(name, dir_fd=fds[-1])

        def remove_dir(index, name, ident):
            now = os.stat(name, dir_fd=fds[index], follow_symlinks=False)
            if (ident is None and stat.S_ISDIR(now.st_mode)) or (now.st_dev, now.st_ino) == ident:
                os.rmdir(name, dir_fd=fds[index])  # only an empty directory goes

        steps = ([remove_leaf] if leaf_made else []) + [(lambda i=i, n=n, d=d: remove_dir(i, n, d)) for i, n, d in reversed(made)]
        failure, fatal = _run_cleanup(steps)  # the descriptors are still open here, so the inode numbers cannot have been reused
        if not isinstance(original, Exception):
            if failure is not None:  # the interrupt stays an interrupt, but a leftover must not be silent
                original.add_note(f"overlay cleanup incomplete: {_describe(failure)}")
            if fatal is not None:  # a second shutdown request struck during the cleanup: it is recorded, not dropped
                original.add_note(f"overlay cleanup was also interrupted by {_describe(fatal)}; entries may remain")
            raise  # Ctrl-C or SystemExit stays what it is, however the cleanup went
        if fatal is not None:
            fatal.add_note("overlay cleanup was interrupted: entries this call created may remain in the base"
                           + (f" (earlier cleanup failure: {_describe(failure)})" if failure is not None else ""))
            raise fatal
        if failure is not None:
            raise BenchmarkGateError(
                "OVERLAY_FAILED", f"{_describe(original)[:90]}; cleanup incomplete: {_describe(failure)[:90]}") from original
        raise
    finally:
        closing_fds, out_fd = list(fds), out
        out = -1
        for fd in ([out_fd] if out_fd >= 0 else []) + closing_fds:
            try:
                os.close(fd)
            except OSError:
                pass


def overlay_benchmark_file(
    base_root: str | os.PathLike, head_root: str | os.PathLike, base_ref_commit: str, path: str, *, head_ref_commit: str
) -> Literal["PRE_EXISTING", "BUILDER_AUTHORED"]:
    """Make the benchmark file exist in the BASE export exactly as the head has it. Returns `PRE_EXISTING` (present at base with the
    same bytes, a regular file with one link) or `BUILDER_AUTHORED` (absent at base: copied in, mode 0644, parents created only inside
    `base_root`, mode 0755). `compare` calls this ONCE per pair of fresh exports, after the installs and before `seal_tree`: the base
    must still be writable (a sealed base is refused with `OVERLAY_BASE_SEALED`), and a second call on the same base answers
    `PRE_EXISTING` for the file the first call created, so a retry must start from fresh exports. The return value is NOT authoritative
    for the file's origin: presence is read from the base export AFTER the project install, so a build step that wrote that path would
    make a Builder-authored file look `PRE_EXISTING`. The Orchestrator re-derives the origin itself (`git cat-file -e <base>:<path>`),
    never from this value or the JSON. `read_benchmark` gives back the bytes for the hash and the lint; `repo_top_levels` (taken
    BEFORE the overlay, but by `compare` after the install: `build/` and `dist/` can join the allowlist, harmless and disclosed)
    gives the lint its argument. One writer per base.

    Both commits are REQUIRED and each must equal the commit in its export's sidecar (`export_commit`), so neither export can come from
    another commit than the one it is named for.

    Refusals (`BenchmarkGateError`; the verdict-like ones are `OVERLAY_REFUSAL_CODES`), in this order: `DEST_REJECTED` (either root
    is not an export directory under a private fixed parent with a valid marker, the two are the same directory, or they are not in
    the same dispatch root), `COMMIT_INVALID` (a commit is not 40 or 64 hex, or the two differ in length), `OVERLAY_COMMIT_MISMATCH` (a
    commit is not the one in that export's sidecar, which `export_tree` writes; a missing or malformed sidecar is a mismatch; the
    sidecar is writable by the same user, so this guards against slips and stale directories, not against a same-user attacker),
    `OVERLAY_PATH_REJECTED` (not a `str`, the gate's lexical path rules, `validate_task_target(head_root, path)`: containment, symlinks,
    deny list, existence, or no entry of that exact name), `OVERLAY_BASE_SEALED`, `OVERLAY_NOT_REGULAR` (the head file is a symlink,
    behind a symlinked parent, a special file, hard-linked, or over 16 KiB), `OVERLAY_PATH_CONFLICT`, `BENCHMARK_MODIFIED`. Every
    other failure (an I/O error, the validator unloadable or misbehaving, a cleanup that could not finish) is `OVERLAY_FAILED`, a
    crash rather than a verdict. A failure leaves no file or directory this call created, or says so; `compare` should treat an
    overlay failure as terminal. Presence is decided from the base export's own listing by exact name, so a case-insensitive
    filesystem cannot make `Benchmarks/` stand in for `benchmarks/`; on such a filesystem the create step finds the twin and refuses."""
    try:
        base, head = _export_root(base_root, "base_root"), _export_root(head_root, "head_root")
        if _same_dir(base, head) or not _same_dir(os.path.dirname(base), os.path.dirname(head)):
            raise BenchmarkGateError("DEST_REJECTED", "base_root and head_root must be two exports in one dispatch root")
        _check_commits(base_ref_commit, head_ref_commit)
        if export_commit(base) != base_ref_commit:
            raise BenchmarkGateError("OVERLAY_COMMIT_MISMATCH", "base_ref_commit is not the commit the base export was made from")
        if export_commit(head) != head_ref_commit:
            raise BenchmarkGateError("OVERLAY_COMMIT_MISMATCH", "head_ref_commit is not the commit the head export was made from")
        if type(path) is not str:
            raise BenchmarkGateError("OVERLAY_PATH_REJECTED", f"path is a {type(path).__name__}, not a str")
        if not _benchmark_path_ok(path) or _call_validator(head, path) != path:
            raise BenchmarkGateError("OVERLAY_PATH_REJECTED", escape_diagnostic(path, 120))
        if not os.lstat(base).st_mode & 0o200:
            raise BenchmarkGateError("OVERLAY_BASE_SEALED", "the base export is sealed: overlay before seal_tree")
        parts = path.split("/")
        return _overlay_into_base(base, parts, _head_bytes(head, parts))
    except BenchmarkGateError:
        raise
    except Exception as exc:  # an I/O error or anything unexpected: one coded failure (a real SystemExit/KeyboardInterrupt passes through)
        raise BenchmarkGateError("OVERLAY_FAILED", _describe(exc)) from exc


# ---------------------------------------------------------------------------
# C4c-2b: protected-path diff and token tripwire
#
# Both compare two commits of the real repository through the same private git as `export_tree` (no config, hooks, diff drivers,
# textconv or attributes of the repository can run) and raise `BenchmarkGateError` with a code of `DIFF_REFUSAL_CODES` when they
# find something. They look at git's own record of the two commits, not at the exports, so they can run at any point of
# `compare`. Neither is a security boundary: they raise the cost of the obvious ways to make a benchmark measure something other
# than the fix (a hook that runs at interpreter start, a changed pytest or dependency configuration, a module shadowing the
# standard library, a fix that detects the benchmark), and are disclosed as such. A determined author who controls executed
# code is out of scope for any in-process control; the controls that do not depend on a list are the trace, the exports and the
# human acceptance of the benchmark and the fix.
# ---------------------------------------------------------------------------

_DIFF_NAME_LIMIT = 5
_PROTECTED_BASENAMES = frozenset({  # compared casefolded: a macOS filesystem is case-insensitive
    "conftest.py", "pytest.ini", ".pytest.ini", "pytest.toml", ".pytest.toml", ".coveragerc", "pyproject.toml", "setup.cfg", "setup.py", "tox.ini", "noxfile.py", "manifest.in",
    "environment.yml", "environment.yaml", "poetry.lock", "uv.lock", "pdm.lock", "pylock.toml",
})
_PROTECTED_PREFIXES_SUFFIXES = (  # (prefix, suffix) of the casefolded basename
    ("sitecustomize", ".py"), ("usercustomize", ".py"), ("", ".pth"), ("requirements", ".txt"), ("constraints", ".txt"),
    ("", ".in"), ("pipfile", ""),
)
_STARTUP_MODULES = frozenset({"sitecustomize", "usercustomize"})
_STDLIB_FOLDED = frozenset(name.casefold() for name in sys.stdlib_module_names)
_TRIPWIRE_TOKENS = (b"PYTEST_CURRENT_TEST", b"BENCH_RESULT_DIGEST", b"BENCH_TRACE_LINES", b"os._exit", b"sys.argv",
                    b"BENCH_TRACE_", b"bench_trace_plugin", b"sys.monitoring", b"import monitoring", b"orig_argv",
                    b"/proc/self/cmdline", b"/proc/self/environ")  # + the benchmark's path; textual only (no bare `/proc/self` or `monitoring`); orig_argv and cmdline because the trace run's argv differs from a timed run's
_MODULE_FILE_RE = re.compile(r"([^.]+)(?:\.[^.]+)?\.(?:py|pyc|so|pyd)")  # `json.py`, a sourceless `json.pyc` (imported straight from the directory), `json.so`, `json.cpython-312-darwin.so`, `json.abi3.so`
_GIT_ESCAPES = {b"a": b"\a", b"b": b"\b", b"t": b"\t", b"n": b"\n", b"v": b"\v", b"f": b"\f", b"r": b"\r", b'"': b'"', b"\\": b"\\"}
_HUNK_RE = re.compile(rb"@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _diff_arguments(commits: tuple[object, object], benchmark_path: object) -> int:
    length = _check_commits(*commits)
    if type(benchmark_path) is not str or not _benchmark_path_ok(benchmark_path):
        raise BenchmarkGateError("OVERLAY_PATH_REJECTED", "path fails the gate's lexical rules")
    return length


def _protected_reason(path: str, benchmark_path: str, linked: bool = False) -> str | None:
    """Why `path` (repo-relative, `/`-separated) may not differ between the two commits, or None."""
    parts = path.split("/")
    folded = [_fold_component(part) for part in parts]
    name = folded[-1]
    if name in _PROTECTED_BASENAMES or any(
        name.startswith(prefix) and name.endswith(suffix) and len(name) >= len(prefix) + len(suffix)
        for prefix, suffix in _PROTECTED_PREFIXES_SUFFIXES
    ):
        return "configuration, startup or dependency file"
    startup = _MODULE_FILE_RE.fullmatch(name)  # the interpreter imports these from any sys.path entry, in any form
    if _STARTUP_MODULES.intersection(folded[:-1]) or (startup and startup[1] in _STARTUP_MODULES):
        return "configuration, startup or dependency file"
    if "requirements" in folded[:-1] and name.endswith(".txt"):
        return "dependency file"
    if "__pycache__" in folded or name.endswith((".pyc", ".pyo")):
        return "compiled bytecode"
    top = folded[1:] if folded[0] == "src" and len(folded) > 1 else folded  # the two directories `repo_top_levels` reads
    module = _MODULE_FILE_RE.fullmatch(top[0]) if len(top) == 1 else None  # a module file, source or compiled extension
    importable = module[1] if module else top[0] if len(top) > 1 else ""
    if importable in _STDLIB_FOLDED:
        return "module that shadows the standard library"
    if linked and len(top) == 1:  # a symlink or submodule at an import root is imported as whatever it points at, whatever its name
        return "symbolic link or submodule at an import root"
    if folded[:-1] == [_fold_component(part) for part in benchmark_path.split("/")[:-1]] and path != benchmark_path:
        return "file beside the benchmark (it is imported with the benchmark)"
    return None


def _changed_paths(git: "_PrivateGit", base_commit: str, head_commit: str) -> list[tuple[str, bool]]:
    """Every path whose entry differs between the two commits (added, changed, removed, type change), sorted, no rename detection."""
    raw = git.run("diff-tree", "-r", "-z", "--raw", "--no-renames", "--no-abbrev", base_commit, head_commit)
    records = raw.split(b"\0")
    if records.pop() != b"" or len(records) % 2:
        raise BenchmarkGateError("GIT_FAILED", "unparseable diff-tree output")
    paths = []
    for meta, raw_path in zip(records[0::2], records[1::2]):
        if not meta.startswith(b":") or not raw_path:
            raise BenchmarkGateError("GIT_FAILED", "unparseable diff-tree record")
        modes = meta[1:].split(b" ")[:2]
        paths.append((os.fsdecode(raw_path), any(mode in (b"120000", b"160000") for mode in modes)))
    if len(paths) > _MAX_TREE_ENTRIES:
        raise BenchmarkGateError("TREE_TOO_LARGE", f"more than {_MAX_TREE_ENTRIES} changed paths")
    return paths


def _shown(items: list[str]) -> str:
    """`N, first K: a, b, ...`: the count comes first because `BenchmarkGateError` cuts a detail at 200 characters, from the end."""
    shown = items[:_DIFF_NAME_LIMIT]
    return f"{len(items)}, first {len(shown)}: " + ", ".join(escape_diagnostic(item, 40) for item in shown)


def _diff_findings(repo, base_commit, head_commit, benchmark_path, *, protected: bool, aware: bool) -> tuple[list[dict], list[dict]]:
    """`(protected hits, benchmark-aware hits)` for the two commits, each hit a dict of escaped strings. One private git, one pass."""
    try:
        length = _diff_arguments((base_commit, head_commit), benchmark_path)
        tokens = _TRIPWIRE_TOKENS + (benchmark_path.encode("ascii"),)
        with _PrivateGit(repo, length) as git:
            git.require_commit(base_commit)
            git.require_commit(head_commit)
            paths = _changed_paths(git, base_commit, head_commit) if protected else []
            patch = (git.run("diff", "-U0", "--no-renames", "--no-textconv", "--no-ext-diff", "--no-color", "--text",
                             "--src-prefix=a/", "--dst-prefix=b/", base_commit, head_commit, cap=_GIT_OUTPUT_CAP) if aware else b"")
        protected_hits = [{"path": escape_diagnostic(path, 200), "reason": reason} for path, linked in paths if path != benchmark_path
                          for reason in [_protected_reason(path, benchmark_path, linked)] if reason]
        aware_hits: dict[tuple[str, bytes], dict] = {}
        for path, number, line in _added_lines(patch):
            if path != benchmark_path:
                for token in tokens:
                    if token in line and (path, token) not in aware_hits:
                        aware_hits[path, token] = {"path": escape_diagnostic(path, 200), "token": token.decode("ascii"),
                                                   "line_number": number, "line": escape_diagnostic(line.decode("utf-8", "replace"), 200)}
        return protected_hits, list(aware_hits.values())
    except BenchmarkGateError:
        raise
    except Exception as exc:  # noqa: BLE001 - an unexpected failure is a crash with a code, never a bare exception
        raise BenchmarkGateError("GIT_FAILED", _describe(exc)) from exc


def _refuse_protected(hits: list[dict]) -> BenchmarkGateError:
    error = BenchmarkGateError("PROTECTED_PATH_CHANGED", f"protected paths differ, {_shown([hit['path'] for hit in hits])}")
    error.hits = hits
    return error


def _refuse_aware(hits: list[dict]) -> BenchmarkGateError:
    error = BenchmarkGateError("BENCHMARK_AWARE_CODE", "benchmark-aware patterns added outside the benchmark, "
                               + _shown([f"{hit['token']} in {hit['path']}" for hit in hits]))
    error.hits = hits
    return error


def protected_path_diff(repo: str | os.PathLike, base_commit: str, head_commit: str, benchmark_path: str) -> None:
    """Raise `PROTECTED_PATH_CHANGED` if the head commit adds, changes or removes a protected path relative to `base_commit`. Protected,
    anywhere in the tree and compared casefolded: `conftest.py`; `sitecustomize*.py` and `usercustomize*.py` (run at interpreter
    start); `*.pth`; the pytest, packaging and dependency files (`pytest.ini`, `pyproject.toml`, `setup.cfg`, `setup.py`, `tox.ini`,
    `noxfile.py`, `MANIFEST.in`, `requirements*.txt` and any `.txt` under a `requirements/` directory, `constraints*.txt`, `*.in`,
    `environment.yml`, `Pipfile*` and the lock files); any `.pyc` or `__pycache__`; a module or package at the top level of the
    repository or of `src/` whose name is in `sys.stdlib_module_names` (it would shadow the standard library; `-P` does not make that
    safe for the second import path); and any file in the benchmark's own directory other than the benchmark (an `__init__.py`, a
    helper imported by it). A removal counts: a head that deletes a base `conftest.py` can make the base slower than the head. The
    benchmark file itself is not checked here (the overlay and the lint own it). `compare` checks that `base_commit` is an ancestor of
    `head_commit` (`is_ancestor`) and echoes both; this function only compares the two trees. `diff_checks` runs this and the tripwire together.

    Raises `BenchmarkGateError`: `PROTECTED_PATH_CHANGED` (the detail counts the paths and names the first five; `hits` has one `{path, reason}` per path, escaped); `COMMIT_INVALID`, `COMMIT_NOT_FOUND`,
    `REPO_UNREADABLE`, `GIT_FAILED`, `GIT_TIMEOUT`, `GIT_OUTPUT_TOO_LARGE`, `GIT_TOO_OLD`, `TREE_TOO_LARGE` (over 100,000 changed paths)
    for a check that could not run; `OVERLAY_PATH_REJECTED` for a `benchmark_path` that fails the gate's lexical rules."""
    hits, _ = _diff_findings(repo, base_commit, head_commit, benchmark_path, protected=True, aware=False)
    if hits:
        raise _refuse_protected(hits)


def _git_unquote(token: bytes) -> bytes:
    """A path as git writes it in a patch header: bare, or `"..."` with C escapes (`\\t`, `\\"`, octal bytes)."""
    if not token.startswith(b'"'):
        return token
    body = token[1:-1] if len(token) >= 2 and token.endswith(b'"') else None
    out, index = bytearray(), 0
    while body is not None and index < len(body):
        byte = body[index:index + 1]
        index += 1
        if byte != b"\\":
            out += byte
        elif body[index:index + 1] in _GIT_ESCAPES:
            out += _GIT_ESCAPES[body[index:index + 1]]
            index += 1
        elif re.fullmatch(rb"[0-3][0-7]{2}", body[index:index + 3]):
            out.append(int(body[index:index + 3], 8))
            index += 3
        else:
            body = None
    if body is None:
        raise BenchmarkGateError("GIT_FAILED", "unparseable path in a patch header")
    return bytes(out)


def _header_path(line: bytes) -> str:
    """The path of a `diff --git a/P b/P` header (no rename detection, so both sides name the same path)."""
    rest = line[len(b"diff --git "):]
    if rest.startswith(b'"'):  # quoted: the first token ends at the first unescaped quote after the opening one
        end, escaped = 1, False
        while end < len(rest) and (escaped or rest[end:end + 1] != b'"'):
            escaped = not escaped and rest[end:end + 1] == b"\\"
            end += 1
        first = _git_unquote(rest[:end + 1])
    else:
        half, remainder = divmod(len(rest) - 5, 2)  # `a/P b/P` is 2 * len(P) + 5 bytes
        if remainder or half < 1 or not rest.startswith(b"a/"):
            first = b""
        else:
            first = rest[:half + 2]
    if not first.startswith(b"a/") or len(first) <= 2:
        raise BenchmarkGateError("GIT_FAILED", "unparseable patch header")
    return os.fsdecode(first[2:])


def _added_lines(patch: bytes):
    """Yield `(path, line number in the new file, line)` for every line a `-U0` patch adds. The hunk header's counts say exactly how many lines follow, so a
    content line that looks like a header (`+++ x`, `diff --git ...`) is never mistaken for one."""
    lines = patch.split(b"\n")
    index, path = 0, ""
    while index < len(lines):
        line = lines[index]
        if line.startswith(b"diff --git "):
            path = _header_path(line)
            index += 1
            while index < len(lines) and not lines[index].startswith((b"@@ ", b"diff --git ")):
                index += 1
        elif line.startswith(b"@@ "):
            found = _HUNK_RE.match(line)
            if found is None:
                raise BenchmarkGateError("GIT_FAILED", "unparseable hunk header")
            removed = 1 if found[1] is None else int(found[1])
            added = 1 if found[3] is None else int(found[3])
            number = int(found[2])
            index += 1
            while removed or added or (index < len(lines) and lines[index].startswith(b"\\")):
                if index >= len(lines):
                    raise BenchmarkGateError("GIT_FAILED", "truncated hunk")
                body = lines[index]
                index += 1
                if body.startswith(b"\\"):  # "\ No newline at end of file"
                    continue
                if body.startswith(b"-") and removed:
                    removed -= 1
                elif body.startswith(b"+") and added:
                    added -= 1
                    yield path, number, body[1:]
                    number += 1
                else:
                    raise BenchmarkGateError("GIT_FAILED", "unparseable hunk body")
        else:
            index += 1


def token_tripwire(repo: str | os.PathLike, base_commit: str, head_commit: str, benchmark_path: str) -> None:
    """Raise `BENCHMARK_AWARE_CODE` if a line ADDED between the commits, in any file other than the benchmark, contains one of
    `PYTEST_CURRENT_TEST`, `BENCH_RESULT_DIGEST`, `BENCH_TRACE_LINES`, `os._exit`, `sys.argv`, `BENCH_TRACE_` (the trace
    plugin's environment prefix), `bench_trace_plugin`, `sys.monitoring`, `import monitoring`, `orig_argv`, `/proc/self/cmdline`,
    `/proc/self/environ` or the benchmark's full path (the tokens are textual only; a bare `/proc/self` and a bare `monitoring` are deliberately
    not tokens, and `sys.orig_argv` and `/proc/self/cmdline` are included because the trace run's argv differs from a timed run's):
    what a fix needs to behave differently when it is being measured, or to forge the harness's output. Added lines come from
    a zero-context patch of the two trees (binary files are read as text, no rename detection, no textconv or external diff). A TRIPWIRE: a
    token built at run time passes, and a line that moved is still an added line. The detail counts the `token in path` pairs and names the
    first five; `hits` has one `{path, token, line_number, line}` per (path, token), escaped, for the evidence a human is shown.

    Raises `BenchmarkGateError`: `BENCHMARK_AWARE_CODE`; the same failure codes as `protected_path_diff` otherwise (`GIT_OUTPUT_TOO_LARGE` when
    the patch is over 64 MiB)."""
    _, hits = _diff_findings(repo, base_commit, head_commit, benchmark_path, protected=False, aware=True)
    if hits:
        raise _refuse_aware(hits)


def diff_checks(repo: str | os.PathLike, base_commit: str, head_commit: str, benchmark_path: str) -> None:
    """`protected_path_diff` and `token_tripwire` in one pass over one private git. When both would fire, `BENCHMARK_AWARE_CODE` is raised
    (it needs a human; the Builder cannot fix it by touching fewer files, so it must not hide behind a fixable `PROTECTED_PATH_CHANGED`).
    Same arguments, failure codes and `hits` as the two functions."""
    protected_hits, aware_hits = _diff_findings(repo, base_commit, head_commit, benchmark_path, protected=True, aware=True)
    if aware_hits:
        raise _refuse_aware(aware_hits)
    if protected_hits:
        raise _refuse_protected(protected_hits)


def is_ancestor(repo: str | os.PathLike, base_commit: str, head_commit: str) -> bool:
    """True if `base_commit` is an ancestor of (or equal to) `head_commit`: `git merge-base --is-ancestor`, which `compare` requires of the
    review package's merge base. False means it is not (exit 1). The checks above only compare two trees and say nothing about ancestry.
    Raises `BenchmarkGateError` `COMMIT_INVALID`, `COMMIT_NOT_FOUND`, `REPO_UNREADABLE`, `GIT_FAILED` (any other git exit, for example a
    shallow repository that lacks the history), `GIT_TIMEOUT`, `GIT_TOO_OLD`."""
    try:
        length = _check_commits(base_commit, head_commit)
        with _PrivateGit(repo, length) as git:
            git.require_commit(base_commit)
            git.require_commit(head_commit)
            code, detail = _PrivateGit._run_raw(["merge-base", "--is-ancestor", base_commit, head_commit], git.env, git._dir, 2048)
    except BenchmarkGateError:
        raise
    except Exception as exc:  # noqa: BLE001 - see _diff_findings
        raise BenchmarkGateError("GIT_FAILED", _describe(exc)) from exc
    if code not in (0, 1):
        raise BenchmarkGateError("GIT_FAILED", f"git merge-base exit {code}: {detail.decode('utf-8', 'replace')}")
    return code == 0


# ---------------------------------------------------------------------------
# C4c-2c: the venv hook check (`snapshot-venv`)
#
# A virtualenv runs code at interpreter start: every `*.pth` line in `site-packages` that begins with `import`, and a `sitecustomize` /
# `usercustomize` module found there. The harness runs the measured code with `-P` under a fresh venv, so the one way to get a
# benchmark-aware hook in front of it is the project's own install. Order (design, APIs table): fresh venv -> `snapshot_venv` ->
# project install -> `check_venv`. The check is on CONTENT, not file names (hatchling and pdm write `_editable_impl_*.pth`, flit and
# poetry `<pkg>.pth`, pytest-cov `a1_coverage.pth`).
#
# A tripwire, not a boundary: the install runs the head's build backend, which can write anywhere, and the editable finder module a
# recognised `import` line names is trusted by name only. The control for that class is a human reading the fix; this refuses the
# accidental and the lazy hook. Verified against nothing live in unit tests (fake venvs only); the real backends are in the design's list.
# ---------------------------------------------------------------------------

VENV_REFUSAL_CODES = (
    "VENV_NOT_ISOLATED",        # not a fresh venv (no pyvenv.cfg, system site-packages on), or a root contains the venv
    "VENV_HOOK_REJECTED",       # a new or changed `.pth` line that is not a path inside the export or a recognised editable finder, or a new startup module
)
# VENV_SNAPSHOT_INVALID is a caller error (a missing, tampered or foreign snapshot), not a verdict: `compare` must not blame the Builder.
ERROR_CODES += VENV_REFUSAL_CODES + ("VENV_SNAPSHOT_INVALID",)

_VENV_SNAPSHOT_KIND = "software-builder-bench-venv-snapshot"
_VENV_MAX_ENTRIES = 10_000
_VENV_MAX_SNAPSHOT_BYTES = 4 << 20
_PTH_MAX_BYTES = 64 << 10
_PTH_MAX_LINES = 1000
_EDITABLE_LINE_RES = (  # setuptools' finder, and the `_editable_impl_<pkg>` import form
    re.compile(r"import (__editable___[A-Za-z0-9_]+_finder); \1\.install\(\)", re.ASCII),
    re.compile(r"import _editable_impl_[A-Za-z0-9_]+", re.ASCII),
)


def _fs(value: object) -> object:
    """`os.fspath` for a str or path-like; anything else is passed through, so the caller's own check refuses it with a coded error."""
    return os.fspath(value) if isinstance(value, (str, os.PathLike)) else value


def _venv_layout(bin_dir: object) -> tuple[str, list[str]]:
    """`(venv root, site-packages directories)` of a venv given its `bin` directory, refusing anything that is not a plain,
    fresh, isolated venv: `bin` a real directory named `bin`, `pyvenv.cfg` a regular file next to it that does not enable the
    system site-packages, and at least one `lib*/python3*/site-packages` that is a real directory inside the venv."""
    if type(bin_dir) is not str or not bin_dir or "\0" in bin_dir or os.path.basename(os.path.abspath(bin_dir)) != "bin":
        raise BenchmarkGateError("VENV_NOT_ISOLATED", "bin must be the path of a venv's `bin` directory")
    bin_path = os.path.abspath(bin_dir)
    try:
        is_dir = stat.S_ISDIR(os.lstat(bin_path).st_mode)
    except OSError as exc:
        raise BenchmarkGateError("VENV_NOT_ISOLATED", f"bin does not exist: {escape_diagnostic(str(exc), 120)}") from exc
    if not is_dir:
        raise BenchmarkGateError("VENV_NOT_ISOLATED", "bin is a symlink or not a directory")
    root = os.path.dirname(bin_path)
    if os.path.lexists(os.path.join(bin_path, "pyvenv.cfg")):  # `site.venv` reads the interpreter's own directory first: a wheel's scripts could drop one
        raise BenchmarkGateError("VENV_NOT_ISOLATED", "bin contains a pyvenv.cfg")
    cfg = os.path.join(root, "pyvenv.cfg")
    try:
        text = _read_bounded(cfg, 64 << 10, nofollow=True).decode("utf-8", "replace")
    except (OSError, ValueError) as exc:
        raise BenchmarkGateError("VENV_NOT_ISOLATED", f"no pyvenv.cfg next to bin: {escape_diagnostic(str(exc), 120)}") from exc
    for line in text.splitlines():
        key, _, value = line.partition("=")
        if key.strip().casefold() == "include-system-site-packages" and value.strip().casefold() != "false":
            raise BenchmarkGateError("VENV_NOT_ISOLATED", "the venv includes the system site-packages")
    real_root = os.path.realpath(root)
    sites: dict[str, str] = {}
    for lib in sorted(os.listdir(root)):
        if lib == "lib" or lib == "lib64":
            lib_path = os.path.join(root, lib)
            if not os.path.isdir(lib_path):
                raise BenchmarkGateError("VENV_NOT_ISOLATED", f"{lib} is not a directory")
            for py in sorted(os.listdir(lib_path)):
                site = os.path.join(lib_path, py, "site-packages")
                if py.startswith("python3") and os.path.isdir(site):
                    real = os.path.realpath(site)
                    if real != real_root and not real.startswith(real_root + os.sep):
                        raise BenchmarkGateError("VENV_NOT_ISOLATED", "site-packages resolves outside the venv")
                    sites.setdefault(real, site)
    if not sites:
        raise BenchmarkGateError("VENV_NOT_ISOLATED", "no lib/python3*/site-packages in the venv")
    return root, sorted(sites.values())


def _venv_entries(root: str, sites: list[str]) -> dict[str, dict]:
    """Every `*.pth` and every `sitecustomize` / `usercustomize` entry (module file in any form, or package directory) directly in a
    site-packages directory, keyed by its path relative to the venv root: `{"kind": file|dir|link|other, "sha256": ...}`
    (hashed over its first 1 MiB for a regular file only; a `.pth` over 64 KiB is `VENV_HOOK_REJECTED` where it is read, not here)."""
    entries: dict[str, dict] = {}
    for site in sites:
        with os.scandir(site) as scan:
            for item in scan:
                folded = _fold_component(item.name)
                module = _MODULE_FILE_RE.fullmatch(folded)
                if not (folded.endswith(".pth") or folded in _STARTUP_MODULES or (module and module[1] in _STARTUP_MODULES)):
                    continue
                if len(entries) >= _VENV_MAX_ENTRIES:
                    raise BenchmarkGateError("TREE_TOO_LARGE", f"more than {_VENV_MAX_ENTRIES} hook candidates in site-packages")
                mode = os.lstat(item.path).st_mode
                kind = "file" if stat.S_ISREG(mode) else "dir" if stat.S_ISDIR(mode) else "link" if stat.S_ISLNK(mode) else "other"
                digest = ""
                if kind == "file":
                    digest = hashlib.sha256(_read_bounded(item.path, _PTH_MAX_BYTES * 16, nofollow=True)).hexdigest()
                entries[os.path.relpath(item.path, root)] = {"kind": kind, "sha256": digest}
    return entries


def snapshot_venv(bin_dir: str | os.PathLike, out_path: str | os.PathLike) -> None:
    """Record the hook candidates of a FRESH venv (run after creating it and BEFORE installing the project) to `out_path`, JSON, written
    atomically; an existing `out_path` is refused (`DEST_REJECTED`). `VENV_NOT_ISOLATED` if the venv is not a plain isolated one;
    `TREE_UNREADABLE` for an I/O error. Anything already in the snapshot (the venv's own `distutils-precedence.pth`, say) is not judged later.
    The CLI `snapshot-venv` also prints the snapshot file's sha256 and the interpreter pin's (`snapshot_sha256`, `interpreter_sha256`): the
    Orchestrator passes both to `compare` in `Side`, and `compare` ends with `ISOLATION_REJECTED` (`SNAPSHOT_CHANGED`, `INTERPRETER_CHANGED`) when either no longer hashes to its pin. This
    function writes only the snapshot; the digest is computed from the file that was written."""
    try:
        root, sites = _venv_layout(_fs(bin_dir))
        out = _fs(out_path)
        if type(out) is not str or not out or os.path.lexists(out):
            raise BenchmarkGateError("DEST_REJECTED", "the snapshot path must be a new file")
        _write_json_atomic(out, {"kind": _VENV_SNAPSHOT_KIND, "version": 1, "venv": os.path.realpath(root),
                                 "entries": _venv_entries(root, sites)})
    except BenchmarkGateError:
        raise
    except (OSError, ValueError, TypeError) as exc:
        raise BenchmarkGateError("TREE_UNREADABLE", _describe(exc)) from exc


def _load_venv_snapshot(path: object, real_root: str) -> dict[str, dict]:
    try:
        raw = _read_bounded(os.fspath(path), _VENV_MAX_SNAPSHOT_BYTES, nofollow=True)  # type: ignore[arg-type]
        data = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        raise BenchmarkGateError("VENV_SNAPSHOT_INVALID", f"cannot read the snapshot: {escape_diagnostic(str(exc), 120)}") from exc
    entries = data.get("entries") if isinstance(data, dict) else None
    if (not isinstance(data, dict) or data.get("kind") != _VENV_SNAPSHOT_KIND or data.get("version") != 1
            or not isinstance(entries, dict) or len(raw) > _VENV_MAX_SNAPSHOT_BYTES
            or not all(type(k) is str and isinstance(v, dict) and type(v.get("kind")) is str and type(v.get("sha256")) is str
                       for k, v in entries.items())):
        raise BenchmarkGateError("VENV_SNAPSHOT_INVALID", "not a snapshot written by `snapshot-venv`")
    if data.get("venv") != real_root:
        raise BenchmarkGateError("VENV_SNAPSHOT_INVALID", "the snapshot belongs to another venv")
    return entries


_TRUSTED_LINK_UID = 0  # the uid whose symlinks a path string may go through (root: macOS `/var` -> `/private/var`); a test seam
# Codecs the compare path uses, loaded NOW: a first use (the `utf-8-sig` decode of a `.pth` file, an ascii decode) would import a module from the
# harness interpreter's stdlib, possibly after a child ran (the interpreter is pinned, but the import would then read it late).
for _codec in ("utf-8", "utf-8-sig", "ascii"):
    codecs.lookup(_codec)


def _euid_can_write(path: str) -> bool:
    """`os.access(path, W_OK)` by the EFFECTIVE uid where the platform supports it (`effective_ids`), else the plain call; an error is "writable"."""
    try:
        if os.access in os.supports_effective_ids:
            return os.access(path, os.W_OK, effective_ids=True)
        return os.access(path, os.W_OK)
    except OSError:
        return True


def _only_root_changes(path: str, info: os.stat_result) -> bool:
    """Whether the directory at `path` (stat `info`) is closed to the harness's euid and to group and other. Group or other write is accepted only
    for a sticky directory owned by ``_TRUSTED_LINK_UID`` (`/tmp`: a user can then remove only their own entries)."""
    if _euid_can_write(path):
        return False
    return info.st_mode & 0o022 == 0 or (info.st_mode & stat.S_ISVTX != 0 and info.st_uid == _TRUSTED_LINK_UID)


def _link_is_trusted(directory: str, info: os.stat_result) -> bool:
    """Whether the symlink with `lstat` `info`, held by `directory`, can be repointed only by root. Owner uid alone is not enough: whoever can
    rename or unlink a link in its directory replaces it, whatever the link's owner. So the link must be owned by ``_TRUSTED_LINK_UID`` with
    exactly one name (`st_nlink == 1`: a second hard link to a root-owned link lives wherever someone else can write); the holding directory must
    be owned by ``_TRUSTED_LINK_UID`` too (a directory the user owns can be chmodded by the user, whatever its mode now), and closed to the euid
    and to group and other (`_only_root_changes`); and so must EVERY ancestor of the holder (a writable ancestor lets the holder be renamed away
    and replaced), a sticky root-owned ancestor such as `/tmp` being acceptable. Fail closed on any error."""
    if info.st_uid != _TRUSTED_LINK_UID or info.st_nlink != 1:
        return False
    try:
        held_by = os.stat(directory)
        if held_by.st_uid != _TRUSTED_LINK_UID or not _only_root_changes(directory, held_by):
            return False
        ancestor = directory
        while True:
            parent = os.path.dirname(ancestor)
            if parent == ancestor:
                return True
            if not _only_root_changes(parent, os.stat(parent)):
                return False
            ancestor = parent
    except OSError:
        return False


def _only_trusted_aliases(path: str) -> bool:
    """True when every symlink met while resolving the absolute lexical `path` (each hop followed, nested ones too) is trusted
    (`_link_is_trusted`: owned by ``_TRUSTED_LINK_UID``, with one name, in a root-owned directory only root can change; its ancestors too), and only when the harness does not
    itself run as root: with an effective uid of 0 the head child is root too, so a root-owned link is not distinct from the attacker's and
    EVERY alias is refused (a root Orchestrator, e.g. Docker, must use paths without symlink hops; C4e must route that refusal, like a venv-hook
    refusal through an alias, as an ENVIRONMENT fault, not a Builder fault). A path string that goes through any other link is refused by the venv
    checks: a head child (same uid) could repoint or replace that link after the check and leave it there, and the spawn guard only re-checks
    resolved paths. A missing component ends the walk as accepted (nothing below it can be a link)."""
    todo = path.split("/")[:0:-1]  # components, last first (so `pop` yields them in order)
    current, hops = "/", 0
    while todo:
        part = todo.pop()
        if part in ("", "."):
            continue
        if part == "..":
            current = os.path.dirname(current)
            continue
        candidate = os.path.join(current, part)
        try:
            info = os.lstat(candidate)
        except FileNotFoundError:
            return True
        except OSError:
            return False
        if not stat.S_ISLNK(info.st_mode):
            current = candidate
            continue
        hops += 1
        if getattr(os, "geteuid", lambda: 1)() == 0 or hops > 40 or not _link_is_trusted(current, info):
            return False
        try:
            target = os.readlink(candidate)
        except OSError:
            return False
        if os.path.isabs(target):
            current = "/"
        todo.extend(target.split("/")[::-1])
    return True


def _alias_accepted(lexical: str) -> bool:
    """A lexical path that differs from its own realpath is accepted only through trusted (root-owned) links."""
    return lexical == os.path.realpath(lexical) or _only_trusted_aliases(lexical)


def _inside(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


_INTERPRETER_LIMIT = 20_000  # entries hashed into an interpreter pin (a stock CPython stdlib is a few thousand)
_INTERPRETER_BYTES = 1 << 30  # bytes hashed into an interpreter pin
_PROBE_MAX_OUTPUT = 4096
_PROBE_TIMEOUT = 20.0
_PROBE_CODE = "import os,sys;print(os.path.realpath(sys.base_prefix),os.path.realpath(os.__file__),os.path.realpath(sys.base_exec_prefix),sep='\\n')"
_CFG_KEYS = frozenset({"home", "version", "include-system-site-packages", "executable"})  # `version_info` folds into `version`


class InterpreterPin(NamedTuple):
    sha256: str
    writable: bool
    real_python: str


def _parse_pyvenv_cfg(data: bytes) -> dict[str, str]:
    """The five keys that matter from a `pyvenv.cfg` (`key = value` lines, UTF-8: a user home may be non-ASCII). `version` and
    `version_info` are one key; a duplicate of any of them is refused, because CPython and `site` would not agree on which wins. The
    `command` key and every other key are ignored."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BenchmarkGateError("VENV_NOT_ISOLATED", "pyvenv.cfg is not UTF-8") from exc
    found: dict[str, str] = {}
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        key, sep, value = line.partition("=")
        key = key.strip().casefold()
        key = "version" if key == "version_info" else key
        if not sep or key not in _CFG_KEYS:
            continue
        if key in found:
            raise BenchmarkGateError("VENV_NOT_ISOLATED", f"pyvenv.cfg repeats {escape_diagnostic(key, 40)}")
        found[key] = value.strip()
    return found


def _probe_env(bin_path: str) -> dict[str, str]:
    """The side's clean environment without a scratch directory: `side_env`'s allowlist minus `HOME` and `TMPDIR` (the probe needs neither)."""
    return {"PATH": f"{bin_path}:/usr/bin:/bin", "VIRTUAL_ENV": os.path.dirname(bin_path), "PYTHONNOUSERSITE": "1", "PYTHONHASHSEED": "0",
            "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "LANG": "C.UTF-8"}


def _startup_probe(python: str, env: dict[str, str]) -> str:
    """Run `python -I -S -c <_PROBE_CODE>` (no shell, no `.pth`, no `sitecustomize`, no user site: only the interpreter binary runs) and
    return its stdout. Output is read up to a cap, the run is killed after `_PROBE_TIMEOUT`; any failure is `VENV_NOT_ISOLATED`."""
    try:
        proc = subprocess.Popen([python, "-I", "-S", "-c", _PROBE_CODE], env=env, cwd="/", stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, close_fds=True, shell=False)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise BenchmarkGateError("VENV_NOT_ISOLATED", f"the interpreter does not start: {escape_diagnostic(str(exc), 120)}") from exc
    timer = threading.Timer(_PROBE_TIMEOUT, proc.kill)
    timer.start()
    try:
        data = proc.stdout.read(_PROBE_MAX_OUTPUT + 1)  # type: ignore[union-attr]
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()  # closed its output and lingers: not a clean run
            proc.wait()
    finally:
        timer.cancel()
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        proc.stdout.close()  # type: ignore[union-attr]
    if len(data) > _PROBE_MAX_OUTPUT or proc.returncode != 0:  # a killed or timed-out child has a negative code
        raise BenchmarkGateError("VENV_NOT_ISOLATED", "the start-up probe failed, timed out or printed too much")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BenchmarkGateError("VENV_NOT_ISOLATED", "the start-up probe printed non-UTF-8") from exc


def _interpreter_digest(real: str, prefix: str, stdlib: str) -> tuple[str, bool]:
    """`(sha256, writable)` of the pinned interpreter files: the real binary; the stdlib tree without its top-level `site-packages` (so
    with `__pycache__` and `lib-dynload`); and the regular files directly under `prefix` and `prefix/lib` (the framework dylib,
    `libpython*`, a `python3XY.zip`). Content only, no timestamps. Entries and bytes are bounded; `writable` is decided in the same walk."""
    euid = getattr(os, "geteuid", lambda: -1)()
    entries = 0
    hashed = 0
    writable = False
    records: list[tuple[bytes, bytes]] = []

    def count() -> None:
        nonlocal entries
        entries += 1
        if entries > _INTERPRETER_LIMIT:
            raise BenchmarkGateError("TREE_TOO_LARGE", f"more than {_INTERPRETER_LIMIT} interpreter entries")

    def owned_or_writable(path: str, st: os.stat_result) -> None:
        nonlocal writable
        if st.st_uid == euid or (not stat.S_ISLNK(st.st_mode) and os.access(path, os.W_OK)):
            writable = True

    def content(path: str, st: os.stat_result) -> str:
        nonlocal hashed
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        try:
            opened = os.fstat(fd)
            if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (st.st_dev, st.st_ino):
                raise BenchmarkGateError("TREE_UNREADABLE", "an interpreter file changed while it was read")
            file_digest = hashlib.sha256()
            while True:
                chunk = os.read(fd, 1 << 20)
                if not chunk:
                    return file_digest.hexdigest()
                hashed += len(chunk)
                if hashed > _INTERPRETER_BYTES:
                    raise BenchmarkGateError("TREE_TOO_LARGE", f"more than {_INTERPRETER_BYTES} interpreter bytes")
                file_digest.update(chunk)
        finally:
            os.close(fd)

    def record(tag: bytes, rel: str, path: str, st: os.stat_result) -> None:
        count()
        owned_or_writable(path, st)
        key = tag + os.fsencode(rel)
        if stat.S_ISREG(st.st_mode):
            body = b"f" + content(path, st).encode()
        elif stat.S_ISDIR(st.st_mode):
            body = b"d"
        elif stat.S_ISLNK(st.st_mode):
            body = b"l" + os.fsencode(os.readlink(path))
        else:
            body = b"o"  # a fifo or device is never opened
        records.append((key, key + b"\0" + body + b"\n"))

    try:
        for directory in (os.path.dirname(real), prefix, os.path.join(prefix, "lib")):
            if os.path.isdir(directory):
                owned_or_writable(directory, os.stat(directory))
        record(b"B", os.path.basename(real), real, os.lstat(real))
        for tag, directory in ((b"P", prefix), (b"L", os.path.join(prefix, "lib"))):
            if not os.path.isdir(directory):
                continue
            with os.scandir(directory) as scan:
                names = sorted(item.name for item in scan)
            for name in names:
                path = os.path.join(directory, name)
                st = os.lstat(path)
                if stat.S_ISREG(st.st_mode):
                    record(tag, name, path, st)
        owned_or_writable(stdlib, os.stat(stdlib))
        pending = [("", 0)]
        while pending:
            rel, depth = pending.pop()
            where = os.path.join(stdlib, rel) if rel else stdlib
            with os.scandir(where) as scan:
                names = sorted(item.name for item in scan)
            for name in names:
                if not rel and name == "site-packages":
                    continue
                child = os.path.join(rel, name) if rel else name
                path = os.path.join(stdlib, child)
                st = os.lstat(path)
                record(b"S", child, path, st)
                if stat.S_ISDIR(st.st_mode):
                    if depth + 1 > _MAX_HASH_DEPTH:
                        raise BenchmarkGateError("TREE_TOO_LARGE", f"more than {_MAX_HASH_DEPTH} levels")
                    pending.append((child, depth + 1))
    except BenchmarkGateError:
        raise
    except OSError as exc:
        raise BenchmarkGateError("TREE_UNREADABLE", _describe(exc)) from exc
    digest = hashlib.sha256(b"software-builder-bench-interpreter-v1\0")
    for _, line in sorted(records):
        digest.update(line)
    return digest.hexdigest(), writable


def interpreter_pin(bin_dir: str | os.PathLike, *, outside: tuple[str, ...] | list[str] = (),
                    probe: Callable[[str, dict[str, str]], str] | None = None) -> InterpreterPin:
    """Identify and hash the interpreter behind a venv's `bin/python`. `pyvenv.cfg` is parsed (`include-system-site-packages` must be
    `false`, no duplicate keys, `version`/`version_info` agrees with a `python3.X` basename), `home` is checked BY FILE
    (`realpath(home/<first symlink hop's name>) == realpath(bin/python)`: Homebrew, uv and Xcode CLT layouts all satisfy that and a
    `dirname(realpath)` comparison would not), the real interpreter must lie outside the venv and every `outside` root (the sibling exports;
    a `--copies` venv is therefore refused), and a start-up probe (`probe(python, env) -> stdout`, default `_startup_probe`) must report a
    `base_prefix` equal to `prefix = dirname(dirname(realpath))` and an `os.__file__` under the stdlib, which catches a `home` redirected
    to a decoy prefix. The cross-side check (both sides one interpreter) is `compare`'s. `VENV_NOT_ISOLATED` (cfg, layout, probe),
    `TREE_TOO_LARGE`, `DEST_REJECTED` (no stdlib directory) and `TREE_UNREADABLE`."""
    bin_path = _fs(bin_dir)
    venv_root, _ = _venv_layout(bin_path)
    bin_path = os.path.abspath(bin_path)
    python = os.path.join(bin_path, "python")
    try:
        cfg = _parse_pyvenv_cfg(_read_bounded(os.path.join(venv_root, "pyvenv.cfg"), 64 << 10, nofollow=True))
        real = os.path.realpath(python)
        if not stat.S_ISREG(os.stat(real).st_mode):
            raise OSError("not a regular file")
    except (OSError, ValueError) as exc:
        raise BenchmarkGateError("VENV_NOT_ISOLATED", f"bin/python or pyvenv.cfg unusable: {escape_diagnostic(str(exc), 120)}") from exc
    forbidden = [os.path.realpath(venv_root)] + [os.path.realpath(_fs(root)) for root in outside]
    if any(_inside(real, root) for root in forbidden):
        raise BenchmarkGateError("VENV_NOT_ISOLATED", "the interpreter lies inside the venv or an export (a --copies venv?)")
    if cfg.get("include-system-site-packages", "false").casefold() != "false":
        raise BenchmarkGateError("VENV_NOT_ISOLATED", "the venv includes the system site-packages")
    home = cfg.get("home", "")
    first_hop = os.path.basename(os.readlink(python)) if os.path.islink(python) else "python"
    if not os.path.isabs(home) or "\0" in home or os.path.realpath(os.path.join(home, first_hop)) != real:
        raise BenchmarkGateError("VENV_NOT_ISOLATED", "pyvenv.cfg `home` does not lead to the venv's python")
    version = re.fullmatch(r"(\d+)\.(\d+)(?:\..*)?", cfg.get("version", ""))
    if not version:
        raise BenchmarkGateError("VENV_NOT_ISOLATED", "pyvenv.cfg has no usable version")
    named = re.fullmatch(r"python(\d+)\.(\d+)", os.path.basename(real))
    if named and named.groups() != version.groups():
        raise BenchmarkGateError("VENV_NOT_ISOLATED", "pyvenv.cfg version does not match the interpreter's name")
    xy = f"python{version[1]}.{version[2]}"
    prefix = os.path.dirname(os.path.dirname(real))
    stdlib = next((path for path in (os.path.join(prefix, "lib", xy), os.path.join(prefix, "lib64", xy)) if os.path.isdir(path)), None)
    if stdlib is None:
        raise BenchmarkGateError("DEST_REJECTED", f"no {xy} standard library under the interpreter prefix")
    try:
        out = (probe or _startup_probe)(python, _probe_env(bin_path))
        lines = out.rstrip("\n").split("\n")
        if len(lines) != 3:
            raise ValueError("unexpected probe output")
        base_prefix, os_file = os.path.realpath(lines[0]), os.path.realpath(lines[1])
    except BenchmarkGateError:
        raise
    except Exception as exc:  # noqa: BLE001 - a stub or a odd output is a failed probe, whatever it raised
        raise BenchmarkGateError("VENV_NOT_ISOLATED", f"the start-up probe is unusable: {escape_diagnostic(_describe(exc), 120)}") from exc
    real_stdlib = os.path.realpath(stdlib)  # `site-packages` is not in the pin, so an `os` loaded from there is not the pinned one
    if base_prefix != prefix or not _inside(os_file, real_stdlib) or _inside(os_file, os.path.join(real_stdlib, "site-packages")):
        raise BenchmarkGateError("VENV_NOT_ISOLATED", "the start-up probe loads another prefix than the pinned one (`home` redirected?)")
    sha256, writable = _interpreter_digest(real, prefix, stdlib)
    return InterpreterPin(sha256, writable, real)


def _pth_problem(site: str, data: bytes, export_root: str, export_aliases: tuple[str, ...] = ()) -> str | None:
    """Why a `.pth` file's content may not run, or None. Mirrors `site.addpackage`: a line starting with `#` is a comment, one
    starting with `import ` or `import<TAB>` is executed, anything else is a path joined to the site directory. Allowed: comments,
    blank lines, a path that resolves INSIDE the export, and exactly the recognised editable-finder `import` lines."""
    if len(data) > _PTH_MAX_BYTES:
        return "a .pth file over 64 KiB"
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return "a .pth file that is not UTF-8"
    if "\0" in text:
        return "a .pth file with a NUL"
    lines = text.splitlines()  # a SUPERSET of every Python's split (3.12 text-mode `\r`/`\n`, newer `str.splitlines()`: also VT, FF, FS, GS, RS, NEL, LS, PS)
    if len(lines) > _PTH_MAX_LINES:
        return "a .pth file over 1000 lines"
    for line in lines:
        if line.startswith("#") or not line.strip():  # a blank line names the site directory itself, already on the path
            continue
        if line.startswith(("import ", "import\t")):
            if not any(pattern.fullmatch(line) for pattern in _EDITABLE_LINE_RES):
                return f"import line: {escape_diagnostic(line, 60)}"
            continue
        joined = os.path.join(site, line.rstrip())
        # BOTH: CPython puts the lexical `abspath` (`..` collapsed without resolving symlinks) on `sys.path`, and the directory it
        # names may itself reach elsewhere through a link; a symlink inside the export plus `..` makes the two differ
        lexical = os.path.abspath(joined)  # compared with the root as given too: the venv path (so `site`) may go through a symlink (macOS /var -> /private/var)
        if not (any(_inside(lexical, root) for root in (export_root, *export_aliases)) and _inside(os.path.realpath(joined), export_root)
                and _alias_accepted(lexical)):
            return f"path outside the export: {escape_diagnostic(line, 60)}"
    return None


def check_venv(bin_dir: str | os.PathLike, snapshot_path: str | os.PathLike, export_root: str | os.PathLike,
               other_roots: tuple[str, ...]) -> str:
    """After the project's install: refuse a venv that gained a hook. Raises `VENV_NOT_ISOLATED` (not a fresh isolated venv, or the venv
    lies inside `export_root` or any of `other_roots`, or a root lies inside the venv), `VENV_HOOK_REJECTED` (every NEW or CHANGED
    `.pth` or startup entry is judged: a `.pth` must be a regular file whose lines are comments, blank, a path resolving inside
    `export_root`, or exactly `import __editable___<pkg>_finder; __editable___<pkg>_finder.install()` / `import _editable_impl_<pkg>`;
    a new `sitecustomize` / `usercustomize` in any form is refused; a pytest-cov `a1_coverage.pth` is refused), `VENV_SNAPSHOT_INVALID`
    (missing, tampered or another venv's snapshot: a caller error), `DEST_REJECTED` (`export_root` is not a directory: a caller error) or `TREE_UNREADABLE`. Returns the venv's real root, so `compare` can require the two sides' venvs to be DISTINCT (not decidable from one side) and `other_roots` is required (omit nothing: the OTHER side's export must be passed). Not enforced here: that the venv was created after the exports (only `pyvenv.cfg` one level up is checked). The error carries `hits`
    (`{"path": <relative to the venv>, "reason": ...}`). Entries only removed since the snapshot are ignored."""
    try:
        root, sites = _venv_layout(_fs(bin_dir))
        real_root = os.path.realpath(root)
        if not isinstance(other_roots, (tuple, list)):
            raise BenchmarkGateError("DEST_REJECTED", "other_roots must be a tuple or list of paths")
        if any(type(_fs(r)) is not str or not _fs(r) or "\0" in _fs(r) for r in (export_root, *other_roots)):
            raise BenchmarkGateError("DEST_REJECTED", "export_root and other_roots must be paths")
        export = os.path.realpath(_fs(export_root))
        if not os.path.isdir(export):
            raise BenchmarkGateError("DEST_REJECTED", "export_root is not a directory")  # a caller error, not a verdict on the venv
        for other in (export, *(os.path.realpath(_fs(r)) for r in other_roots)):
            if _inside(real_root, other) or _inside(other, real_root):
                raise BenchmarkGateError("VENV_NOT_ISOLATED", "the venv and an export root contain each other")
        before = _load_venv_snapshot(snapshot_path, real_root)
        hits: list[dict] = []
        for rel, entry in sorted(_venv_entries(root, sites).items()):
            if before.get(rel) == entry:
                continue
            name = _fold_component(os.path.basename(rel))
            module = _MODULE_FILE_RE.fullmatch(name)
            if not name.endswith(".pth") or name in _STARTUP_MODULES or (module and module[1] in _STARTUP_MODULES):
                reason = "a new or changed startup module"
            elif entry["kind"] != "file":
                reason = "a .pth that is not a regular file"
            else:
                reason = _pth_problem(os.path.dirname(os.path.join(root, rel)),
                                      _read_bounded(os.path.join(root, rel), _PTH_MAX_BYTES + 1, nofollow=True), export,
                                      (os.path.abspath(_fs(export_root)),))
            if reason:
                hits.append({"path": escape_diagnostic(rel, 200), "reason": reason})
        if hits:
            error = BenchmarkGateError("VENV_HOOK_REJECTED", "venv hooks, " + _shown([h["path"] + " (" + h["reason"] + ")" for h in hits]))
            error.hits = hits
            raise error
        return real_root
    except BenchmarkGateError:
        raise
    except (OSError, ValueError, TypeError) as exc:
        raise BenchmarkGateError("TREE_UNREADABLE", _describe(exc)) from exc


# ---------------------------------------------------------------------------
# C4d-3 dependency parity: an inventory of each venv's site-packages (spec 2.5), not a comparison of RECORD files
# ---------------------------------------------------------------------------

_VENV_HASH_BYTES = 1 << 30  # bytes hashed per venv; more is NOT_PROVISIONED
_RECORD_MAX_BYTES = 16 << 20
_PARITY_FINDINGS_MAX = 50
_PARITY_NAMES_SHOWN = 8
_DIST_INFO_FREE = frozenset({"INSTALLER", "REQUESTED", "RECORD", "direct_url.json"})
_EDITABLE_OWNED_PREFIXES = ("__editable__", "_editable_impl_")
_FINDER_RE = re.compile(r"__editable___[A-Za-z0-9_]+_finder\.py", re.ASCII)


class _ParityOverBudget(Exception):
    pass


def _parity_hash(path: str, st: os.stat_result, spent: list[int]) -> str:
    """sha256 of a regular file by descriptor (no link followed), charged against the venv's byte budget."""
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (st.st_dev, st.st_ino):
            raise OSError("entry changed while hashing")
        digest = hashlib.sha256()
        while True:
            chunk = os.read(fd, 1 << 20)
            if not chunk:
                return digest.hexdigest()
            spent[0] += len(chunk)
            if spent[0] > _VENV_HASH_BYTES:
                raise _ParityOverBudget()
            digest.update(chunk)
    finally:
        os.close(fd)


def _parity_walk(site: str, spent: list[int], add: Callable[[str], None]) -> dict[str, str]:
    """`{relpath: sha256}` of every regular file under `site`, by `lstat` with no link followed. A symlink, device, socket, fifo, `.pyc`
    or `__pycache__` is a finding and is not descended into; a limit or an I/O fault is an error, never a skip."""
    files: dict[str, str] = {}
    count = 0
    pending = [("", 0)]
    while pending:
        rel, depth = pending.pop()
        with os.scandir(os.path.join(site, rel) if rel else site) as it:
            names = sorted(entry.name for entry in it)
        for name in names:
            count += 1
            if count > _VENV_FINGERPRINT_LIMIT:
                raise BenchmarkGateError("TREE_TOO_LARGE", f"more than {_VENV_FINGERPRINT_LIMIT} entries in site-packages")
            child = f"{rel}/{name}" if rel else name
            full = os.path.join(site, child)
            st = os.lstat(full)
            if stat.S_ISLNK(st.st_mode):
                add(f"symlink {escape_diagnostic(child, 100)}")
            elif stat.S_ISDIR(st.st_mode):
                if name.casefold() == "__pycache__":
                    add(f"bytecode directory {escape_diagnostic(child, 100)}")
                    continue
                if depth + 1 > _MAX_HASH_DEPTH:
                    raise BenchmarkGateError("TREE_TOO_LARGE", f"more than {_MAX_HASH_DEPTH} levels in site-packages")
                pending.append((child, depth + 1))
            elif not stat.S_ISREG(st.st_mode):
                add(f"device, socket or fifo {escape_diagnostic(child, 100)}")
            elif name.casefold().endswith((".pyc", ".pyo")):
                add(f"bytecode {escape_diagnostic(child, 100)}")
            else:
                files[child] = _parity_hash(full, st, spent)
    return files


def _record_path(raw: str) -> str | None:
    """A RECORD row's path as a clean relative path, `None` for a console-script row (a leading `../` run: out of site-packages, dropped);
    `ValueError` for anything else that is not a plain relative path. An absolute path is refused here and never joined."""
    if not raw or "\0" in raw or "\\" in raw or raw.startswith("/"):
        raise ValueError("not a plain relative path")
    parts = raw.split("/")
    lead = 0
    while lead < len(parts) and parts[lead] == "..":
        lead += 1
    rest = parts[lead:]
    if not rest or any(part in ("", ".", "..") for part in rest):
        raise ValueError("empty, dot or dot-dot component")
    return None if lead else "/".join(rest)


def _file_url_inside(url: object, export_real: str) -> bool | None:
    """`None` if `url` is not a local `file://` URL, else whether it resolves inside `export_real`."""
    import urllib.parse
    if type(url) is not str:
        return None
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "file":
        return None
    path = urllib.parse.unquote(parts.path)
    if parts.netloc not in ("", "localhost") or "\0" in path or not os.path.isabs(path):
        return False
    return _inside(os.path.realpath(path), export_real)


def _finder_problem(source: bytes, export_real: str) -> str | None:
    """`MAPPING` and `NAMESPACES` of a setuptools editable finder, parsed as literals only; every target must resolve inside the export."""
    try:
        tree = ast.parse(source.decode("utf-8"))
    except (UnicodeDecodeError, SyntaxError, ValueError, RecursionError, MemoryError):
        return "the editable finder does not parse"
    found: dict[str, object] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name, value = node.targets[0].id, node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            name, value = node.target.id, node.value
        else:
            continue
        if name in ("MAPPING", "NAMESPACES"):
            if name in found:
                return f"{name} is assigned twice"
            try:
                found[name] = ast.literal_eval(value)
            except (ValueError, TypeError, SyntaxError, RecursionError, MemoryError):
                return f"{name} is not a literal"
    mapping, namespaces = found.get("MAPPING"), found.get("NAMESPACES")
    if not isinstance(mapping, dict) or not isinstance(namespaces, dict):
        return "MAPPING or NAMESPACES missing or not a dict"
    targets = list(mapping.values())
    for value in namespaces.values():
        if not isinstance(value, (list, tuple)):
            return "a NAMESPACES value is not a list"
        targets.extend(value)
    for target in targets:
        if type(target) is not str or not target or "\0" in target or not os.path.isabs(target):
            return "a finder target is not an absolute path"
        # the kernel (and the finder's `Path(target, ...)`) resolves the RAW string: `..` after a user-owned link would otherwise be collapsed by
        # `abspath` into a path that never meets the link. A target that is not already normal (`..`, `.`, `//`, a trailing `/`) is refused
        if posixpath.normpath(target) != target or not _inside(os.path.realpath(target), export_real) or not _alias_accepted(target):
            return "a finder target resolves outside the export"
    return None


def _side_inventory(bin_dir: object, export_root: object, label: str, add: Callable[[str, str], None]) -> tuple[dict[str, str], set[str]] | None:
    """`(inventory, exempt keys)` of one venv, findings through `add(detail, text)`; `None` when the byte budget ran out."""
    import base64
    import csv
    root, sites = _venv_layout(_fs(bin_dir))
    export_real = os.path.realpath(_fs(export_root))

    def bad(text: str) -> None:
        add("DEPENDENCY_PARITY", f"{label}: {text}")

    inventory: dict[str, str] = {}
    exempt: set[str] = set()
    editable_dists: list[str] = []
    spent = [0]
    try:
        for site in sites:
            prefix = os.path.relpath(site, root)
            files = _parity_walk(site, spent, bad)
            inventory.update({f"{prefix}/{rel}": digest for rel, digest in files.items()})
            dists = sorted({rel.split("/", 1)[0] for rel in files if "/" in rel and rel.split("/", 1)[0].endswith(".dist-info")})
            claimed: set[str] = set()
            for dist in dists:
                exempt_dist = False
                owned_all: list[str] = []
                record_key = f"{dist}/RECORD"
                url_key = f"{dist}/direct_url.json"
                if url_key in files:
                    try:
                        meta = json.loads(_read_bounded(os.path.join(site, url_key), _PTH_MAX_BYTES, nofollow=True).decode("utf-8"))
                        if not isinstance(meta, dict):
                            raise ValueError("not an object")
                        info = meta.get("dir_info")
                        editable = isinstance(info, dict) and info.get("editable") is True
                        inside = _file_url_inside(meta.get("url"), export_real)
                    except (OSError, ValueError, RecursionError) as exc:
                        bad(f"{escape_diagnostic(dist, 80)} has an unreadable direct_url.json ({escape_diagnostic(str(exc), 60)})")
                        editable, inside = False, None
                    if editable and inside:
                        exempt_dist = True
                        editable_dists.append(dist)
                    elif editable:
                        bad(f"{escape_diagnostic(dist, 80)} is editable but not from this side's export")
                    elif inside:
                        bad(f"{escape_diagnostic(dist, 80)} is a non-editable install of the project")
                if record_key not in files:
                    bad(f"{escape_diagnostic(dist, 80)} has no RECORD")
                    continue
                try:
                    data = _read_bounded(os.path.join(site, record_key), _RECORD_MAX_BYTES, nofollow=True)
                    if len(data) > _RECORD_MAX_BYTES:
                        raise ValueError("RECORD too large")
                    if hashlib.sha256(data).hexdigest() != files[record_key]:
                        raise ValueError("RECORD changed while checking")
                    rows = [row for row in csv.reader(io.StringIO(data.decode("utf-8"), newline="")) if row]
                except (OSError, ValueError, csv.Error) as exc:
                    bad(f"{escape_diagnostic(dist, 80)} RECORD unusable ({escape_diagnostic(str(exc), 60)})")
                    continue
                for row in rows:
                    try:
                        rel = _record_path(row[0])
                    except ValueError:
                        bad(f"{escape_diagnostic(dist, 80)} RECORD row path refused: {escape_diagnostic(row[0], 80)}")
                        continue
                    if rel is None:
                        continue
                    owned_all.append(rel)
                    digest = row[1] if len(row) > 1 else ""
                    if not digest:
                        continue  # an unhashed row (the RECORD itself, a bytecode row) verifies and owns nothing
                    if not digest.startswith("sha256="):
                        bad(f"{escape_diagnostic(dist, 80)} RECORD row {escape_diagnostic(rel, 80)} is not sha256")
                        continue
                    claimed.add(rel)
                    disk = files.get(rel)
                    if disk is None:
                        bad(f"{escape_diagnostic(dist, 80)} RECORD names a missing file {escape_diagnostic(rel, 80)}")
                    elif base64.urlsafe_b64encode(bytes.fromhex(disk)).rstrip(b"=").decode() != digest[7:].rstrip("="):
                        bad(f"hash on disk differs from RECORD: {escape_diagnostic(rel, 100)}")
                if exempt_dist:
                    own_prefix = dist + "/"
                    for rel in owned_all:
                        top = rel.split("/", 1)[0]
                        if not (rel.startswith(own_prefix) or (rel.endswith(".pth") and "/" not in rel) or top.startswith(_EDITABLE_OWNED_PREFIXES)):
                            bad(f"the editable dist {escape_diagnostic(dist, 80)} owns {escape_diagnostic(rel, 80)}")
                        elif _FINDER_RE.fullmatch(rel) and rel in files:
                            try:
                                problem = _finder_problem(_read_bounded(os.path.join(site, rel), 1 << 20, nofollow=True), export_real)
                            except (OSError, ValueError) as exc:
                                problem = f"finder unreadable ({escape_diagnostic(str(exc), 60)})"
                            if problem:
                                bad(f"{escape_diagnostic(rel, 80)}: {problem}")
                    exempt.update(f"{prefix}/{rel}" for rel in owned_all if rel in files)
                    exempt.update(f"{prefix}/{rel}" for rel in files if rel.startswith(own_prefix))
            for rel in files:
                name = rel.rsplit("/", 1)[-1]
                parent = rel.rsplit("/", 1)[0] if "/" in rel else ""
                if (rel in claimed or (parent in dists and name in _DIST_INFO_FREE)
                        or (not parent and (name == "distutils-precedence.pth" or name.startswith("_virtualenv.")))):
                    continue
                bad(f"file not owned by a verified RECORD row: {escape_diagnostic(rel, 100)}")
    except _ParityOverBudget:
        add("NOT_PROVISIONED", f"{label}: more than {_VENV_HASH_BYTES} bytes in site-packages")
        return None
    except OSError as exc:
        raise BenchmarkGateError("TREE_UNREADABLE", f"{label}: {_describe(exc)}") from exc
    if len(editable_dists) > 1:
        bad("more than one editable dist: " + ", ".join(escape_diagnostic(d, 60) for d in editable_dists[:4]))
        exempt.clear()
    return inventory, exempt


def dependency_parity(base_bin: str | os.PathLike, head_bin: str | os.PathLike,
                      base_root: str | os.PathLike, head_root: str | os.PathLike) -> list[tuple[str, str]]:
    """Findings `(detail, text)` for the two venvs' site-packages; an empty list is a pass. `detail` is `DEPENDENCY_PARITY`, or
    `NOT_PROVISIONED` when a venv holds more than `_VENV_HASH_BYTES`. Each venv is inventoried `{relpath: sha256 on disk}` with no link
    followed; every regular file must be a hash-verified RECORD row or one of the few allowed names; the two inventories must be equal
    except for the one exempt editable dist per side. `text` is escaped. `VENV_NOT_ISOLATED`, `TREE_TOO_LARGE` and `TREE_UNREADABLE`
    are raised (a venv that cannot be inspected is not a finding about the dependencies)."""
    findings: list[tuple[str, str]] = []
    over_budget: list[tuple[str, str]] = []  # NOT_PROVISIONED lives outside the capped list: a full list must not lose it

    def add(detail: str, text: str) -> None:
        if detail == "NOT_PROVISIONED":
            over_budget.append((detail, escape_diagnostic(text, 300)))  # at most one per venv
        elif len(findings) < _PARITY_FINDINGS_MAX:
            findings.append((detail, escape_diagnostic(text, 300)))

    base = _side_inventory(base_bin, base_root, "base", add)
    head = _side_inventory(head_bin, head_root, "head", add)
    if over_budget:
        return over_budget
    if base is None or head is None:  # `_side_inventory` gives None only after reporting the budget: an invariant, not an input
        raise BenchmarkGateError("MEASURE_FAILED", "internal invariant: a venv inventory is missing")
    skip = base[1] | head[1]
    # A RECORD is excluded from the comparison: its console-script rows embed the venv's own path. Every row of it was verified against
    # the disk above and what it does not list is refused as unowned, so its text decides nothing the file inventory does not.
    def comparable(inv: dict[str, str]) -> dict[str, str]:
        return {k: v for k, v in inv.items() if k not in skip and not (k.endswith(".dist-info/RECORD"))}

    left, right = comparable(base[0]), comparable(head[0])
    for label, names in (("only in base", sorted(left.keys() - right.keys())), ("only in head", sorted(right.keys() - left.keys())),
                         ("content differs", sorted(k for k in left.keys() & right.keys() if left[k] != right[k]))):
        if names:
            add("DEPENDENCY_PARITY", f"{label} ({len(names)}): " + ", ".join(escape_diagnostic(n, 60) for n in names[:_PARITY_NAMES_SHOWN]))
    return findings


_EXPORT_FINDINGS_MAX = 50
_UNTRACKED_MODULE_SUFFIXES = (".py", ".pyc", ".pyd", ".so", ".pth", ".zip", ".egg", ".whl")
_EXEMPT_TOP_DIRS = frozenset({"build", "dist", ".eggs"})  # an honest `pip install -e` / build leaves these at the root


def _is_untracked_python_name(name: str) -> bool:
    """A file name the interpreter or an installer would treat as code or a path hook: a module/archive suffix, a startup module name
    (`sitecustomize*`, `usercustomize*`, any suffix). Casefolded, so `HASHLIB.PY` counts on a case-insensitive filesystem."""
    folded = name.casefold()
    module = _MODULE_FILE_RE.fullmatch(folded)
    return (folded.endswith(_UNTRACKED_MODULE_SUFFIXES) or folded.startswith(tuple(_STARTUP_MODULES))
            or (module is not None and module[1] in _STARTUP_MODULES))


def _blob_id(length: int, size: int, chunks) -> str:
    """The git blob id of `chunks` (an iterable of bytes totalling `size`; `blob <n>\\0` framing, NO filters), sha1 for a 40-hex commit
    and sha256 for 64. A total other than `size` yields an id nothing matches."""
    digest = hashlib.sha1(usedforsecurity=False) if length == 40 else hashlib.sha256()
    digest.update(b"blob %d\0" % size)
    seen = 0
    for chunk in chunks:
        seen += len(chunk)
        if seen > size:
            return ""
        digest.update(chunk)
    return digest.hexdigest() if seen == size else ""


def _read_chunks(fd: int):
    while chunk := os.read(fd, 1 << 20):
        yield chunk


def verify_export_against_commit(repo: str | os.PathLike, commit: str, export_root: str | os.PathLike, *,
                                 allow: dict[str, str] | None = None) -> list[tuple[str, str]]:
    """Findings `(detail, relpath)` for the export at `export_root` against `commit`'s tree; an empty list is a pass. `detail` is
    `TRACKED_FILE_DIFFERS` (a tracked file, symlink or gitlink that is not what the commit lists: git blob id of the bytes, no filters,
    and the executable bit; a symlink's `readlink` bytes and a target staying inside the export; a gitlink an empty directory; missing
    entries) or `UNTRACKED_PYTHON_FILE` (an untracked symlink, socket, device or fifo; an untracked file with a module, archive or startup
    name, or a `__pycache__` directory, except under the root-level `build/`, `dist/`, `.eggs/` and `<root>/*.egg-info`, and except the
    `allow` entries `{relpath: sha256 of the bytes}`, which must be that exact regular file). The walk follows no link. Untracked inputs
    that are not code (`.env`, `*.json`) are not covered. `relpath` is escaped. Raises, never returns, for `EXPORT_*` (a hostile
    listing), `GIT_*` and `COMMIT_*` errors including `GIT_OUTPUT_TOO_LARGE`, `TREE_TOO_LARGE` (entries or depth) and `TREE_UNREADABLE`
    (an I/O fault: a tree that cannot be read is not a finding)."""
    length = _check_commits(commit)
    root = _export_root(export_root, "export_root")
    allowed = dict(allow or {})
    with _PrivateGit(repo, length) as git:
        git.require_commit(commit)
        raw = git.run("ls-tree", "-r", "-l", "-z", "--full-tree", commit)  # one byte string, two parsers (shape and ids)
    entries = _parse_listing(raw)
    oids = _parse_listing_oids(raw)
    if oids.keys() != entries.keys():
        raise BenchmarkGateError("GIT_FAILED", "ls-tree listing parsed inconsistently")
    tracked_dirs = {"/".join(rel.split("/")[:i]) for rel in entries for i in range(1, rel.count("/") + 1)}
    findings: list[tuple[str, str]] = []

    def add(detail: str, rel: str) -> None:
        if len(findings) < _EXPORT_FINDINGS_MAX:
            findings.append((detail, escape_diagnostic(rel, 300)))

    seen: set[str] = set()
    count = 0
    pending: list[tuple[str, int, bool]] = [("", 0, False)]  # (relpath of a directory, depth, inside an exempt untracked directory)
    try:
        while pending:
            rel_dir, depth, exempt_dir = pending.pop()
            with os.scandir(os.path.join(root, rel_dir) if rel_dir else root) as it:
                names = sorted(entry.name for entry in it)
            for name in names:
                count += 1
                if count > _MAX_TREE_ENTRIES:
                    raise BenchmarkGateError("TREE_TOO_LARGE", f"more than {_MAX_TREE_ENTRIES} entries")
                rel = f"{rel_dir}/{name}" if rel_dir else name
                path = os.path.join(root, rel)
                st = os.lstat(path)
                want = entries.get(rel)
                is_dir = stat.S_ISDIR(st.st_mode)
                if want is not None:
                    seen.add(rel)
                    kind = want[0]
                    if kind == "G":
                        if not is_dir or os.listdir(path):
                            add("TRACKED_FILE_DIFFERS", rel)
                    elif kind == "L":
                        if not stat.S_ISLNK(st.st_mode):
                            add("TRACKED_FILE_DIFFERS", rel)
                        else:
                            target = os.fsencode(os.readlink(path))
                            real_root = os.path.realpath(root)
                            real = os.path.realpath(path)
                            inside = real == real_root or real.startswith(real_root + os.sep)
                            if _blob_id(length, len(target), [target]) != oids[rel] or not inside:
                                add("TRACKED_FILE_DIFFERS", rel)
                    else:
                        ok = stat.S_ISREG(st.st_mode) and st.st_size == want[1] and bool(st.st_mode & 0o100) == want[2]
                        if ok:
                            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0))
                            try:
                                fst = os.fstat(fd)
                                ok = (stat.S_ISREG(fst.st_mode) and (fst.st_dev, fst.st_ino) == (st.st_dev, st.st_ino)
                                      and _blob_id(length, want[1], _read_chunks(fd)) == oids[rel])
                            finally:
                                os.close(fd)
                        if not ok:
                            add("TRACKED_FILE_DIFFERS", rel)
                    continue  # a directory where a file or link is tracked is reported above and not walked
                if is_dir:
                    if rel in tracked_dirs:  # an ancestor of tracked entries
                        pending.append((rel, depth + 1, False))
                        if depth + 1 > _MAX_HASH_DEPTH:
                            raise BenchmarkGateError("TREE_TOO_LARGE", f"more than {_MAX_HASH_DEPTH} levels")
                        continue
                    exempt = exempt_dir or (rel_dir == "" and (name in _EXEMPT_TOP_DIRS or name.endswith(".egg-info")))
                    if name == "__pycache__" and not exempt and rel not in allowed:
                        add("UNTRACKED_PYTHON_FILE", rel)
                    if depth + 1 > _MAX_HASH_DEPTH:
                        raise BenchmarkGateError("TREE_TOO_LARGE", f"more than {_MAX_HASH_DEPTH} levels")
                    pending.append((rel, depth + 1, exempt))
                elif not stat.S_ISREG(st.st_mode):  # untracked symlink, socket, device, fifo
                    add("UNTRACKED_PYTHON_FILE", rel)
                elif rel in allowed:
                    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0))
                    try:
                        fst = os.fstat(fd)
                        digest, total = hashlib.sha256(), 0
                        ok = stat.S_ISREG(fst.st_mode) and (fst.st_dev, fst.st_ino) == (st.st_dev, st.st_ino)
                        while ok and (chunk := os.read(fd, 1 << 20)):
                            total += len(chunk)
                            if total > _MAX_BENCHMARK_FILE_BYTES:
                                ok = False
                            digest.update(chunk)
                    finally:
                        os.close(fd)
                    if not ok or digest.hexdigest() != allowed[rel]:
                        add("UNTRACKED_PYTHON_FILE", rel)
                elif not exempt_dir and _is_untracked_python_name(name):
                    add("UNTRACKED_PYTHON_FILE", rel)
    except BenchmarkGateError:
        raise
    except OSError as exc:
        raise BenchmarkGateError("TREE_UNREADABLE", _describe(exc)) from exc
    for rel in sorted(entries.keys() - seen):
        add("TRACKED_FILE_DIFFERS", rel)  # missing
    return findings


# ---------------------------------------------------------------------------
# C4d-1 the measurement harness (`measure_paired`); the block also holds the C4d-2 trace (`TRACE_PLUGIN_SOURCE`, `trace_env`, `trace_paired`)
#
# Runs the benchmark as a child process of each side, alternating sides in a seeded balanced order, and returns raw wall times.
# It decides nothing: the verdict is `evaluate_paired_samples` over the lists, called by `compare` (C4d-3). POSIX only.
# ---------------------------------------------------------------------------

# Library results that `compare` maps to a verdict (design: code -> result table). Nothing here blames the Builder for a harness fault:
# BASE_NONZERO_EXIT is a provisioning problem (a flat-layout project that was not installed fails closed that way), MEASURE_ARGS_INVALID a
# caller error.
MEASURE_REFUSAL_CODES = (
    "UNSUPPORTED_PLATFORM",     # not POSIX: no process groups, no rlimits
    "BASE_NONZERO_EXIT",        # the benchmark exited non-zero (or was killed) on the base side
    "HEAD_NONZERO_EXIT",        # ... on the head side
    "BASE_TIMEOUT",             # a base run exceeded the per-run timeout (compare: INCONCLUSIVE)
    "HEAD_TIMEOUT",             # a head run exceeded it (compare: NOT_IMPROVED, the Builder can fix it)
    "OUTPUT_TOO_LARGE",         # a run wrote 1 MiB to stdout or stderr (RLIMIT_FSIZE reached)
    "DIGEST_MISSING",           # NEITHER side printed a `BENCH_RESULT_DIGEST: <64 hex>` line in the first warmup round
    "DIGEST_UNSTABLE",          # one side printed different digests in different runs (or stopped printing one)
    "DIGEST_MISMATCH",          # the sides disagree, or only ONE side printed a digest
    "WORKLOAD_TOO_SHORT",       # the base median is under the minimum: timing noise would dominate
)
# MEASURE_ARGS_INVALID: a caller error. MEASURE_FAILED: a harness fault (no disk space, no thread, a failed temp file, a bad plugin file): not the
# Builder's; `measure_paired` and `trace_paired` both raise it (the trace with phase "trace").
ERROR_CODES += MEASURE_REFUSAL_CODES + ("MEASURE_ARGS_INVALID", "MEASURE_FAILED")
# C4d-2: the paired trace run's refusals. TRACE_MISMATCH: the sides' executed-line traces disagree (or a side's trace is not as the plugin must
# have produced it); TRACE_UNAVAILABLE: no trustworthy trace could be taken (a harness limit, not the Builder's fault). Both are raised by
# `trace_paired` only, with phase "trace"; a harness fault there is `MEASURE_FAILED`, not one of these.
TRACE_REFUSAL_CODES = ("TRACE_MISMATCH", "TRACE_UNAVAILABLE")
ERROR_CODES += TRACE_REFUSAL_CODES
# C4d-3: `compare` raises this when the base commit is not an ancestor of the head commit (a caller error: the pair is not a PR's
# before and after). It is never a result reason or detail.
ERROR_CODES += ("BASE_NOT_ANCESTOR",)
# The closed vocabulary of ``BenchmarkGateError.kind`` that ``trace_paired`` sets on EVERY error it raises after validation: the four ``_execute``
# kinds, then plugin_failed ("plugin reported failure"), no_result ("no trace result"), the four post-result unavailable/interpreter
# kinds, counts_differ (TRACE_MISMATCH), unavailable (TRACE_UNAVAILABLE) and harness (MEASURE_FAILED).
TRACE_FAILURE_KINDS = ("spawn", "oversize", "timeout", "nonzero", "plugin_failed", "no_result", "unavailable_one_side",
                       "unavailable_tokens_differ", "unavailable_interpreters_differ", "interpreters_differ", "counts_differ", "unavailable",
                       "harness")

_RUN_FSIZE_LIMIT = 1 << 20
_STDERR_TAIL = 2048
_MIN_BASE_NS = 2_000_000_000
_DIGEST_RE = re.compile(rb"BENCH_RESULT_DIGEST: ([0-9a-f]{64})(?![0-9a-f])")
_EMPTY_INI = "[pytest]\n"
_TRACE_MODULE = "bench_trace_plugin"  # the one pytest plugin the gate may load (C4d-2): `-p bench_trace_plugin`, found through PYTHONPATH
_TRACE_TIMEOUT_FACTOR = 3  # the traced run may take this many times the per-run timeout; per_run_timeout_seconds must leave room for a traced run (about 7x the benchmark time for a tight loop); the gate budget cap uses this factor

# The trace plugin, written fresh into a harness-owned directory per side (spec D1, D2). It must stay ASCII, annotation-free and importable
# on CPython 3.8: it runs inside the side's own venv, whose interpreter may be older than this one. Raw string: no escape is interpreted.
# Importable is not usable: it counts lines with ``sys.monitoring`` (3.12+), so on an older interpreter the plugin reports ``no_monitoring``,
# `trace_paired` raises ``TRACE_UNAVAILABLE`` and `compare` ends INCONCLUSIVE/``TRACE_UNAVAILABLE``: a project venv older than 3.12 never
# reaches ``IMPROVED``.
TRACE_PLUGIN_SOURCE = r"""import os
import sys
import threading

import pytest


class _State(object):
    def __init__(self):
        self.traced_ids = set()  # id() of the code objects to count; membership is by identity, code objects compare by value
        self.keep = []  # holds those code objects alive so an id is never reused
        self.thread = None
        self.count = 0
        self.failed = False
        self.unavailable = None
        self.claimed = False
        self.out = None
        self.nonce = None
        self.root_real = None
        self.target_real = None


STATE = _State()


def _claim_tool(sys_module):
    # None when tool id 4 is ours; otherwise a token. Never raises: the import of this module must not fail.
    try:
        monitoring = getattr(sys_module, "monitoring", None)
        if monitoring is None:
            return "no_monitoring"
        monitoring.use_tool_id(4, "bench_trace_plugin")
    except ValueError:
        return "tool_in_use"
    except Exception:
        return "error"
    return None


def _release_tool(sys_module):
    # 3.12 has no clear_tool_id and a callback survives free_tool_id there, so unregister both events by hand first.
    monitoring = sys_module.monitoring
    if hasattr(monitoring, "clear_tool_id"):
        monitoring.clear_tool_id(4)
    else:
        monitoring.register_callback(4, monitoring.events.LINE, None)
        monitoring.register_callback(4, monitoring.events.JUMP, None)
    monitoring.free_tool_id(4)


def on_event(code, arg1, arg2=None):
    # LINE calls (code, line), JUMP calls (code, instruction_offset, destination_offset).
    try:
        if id(code) not in STATE.traced_ids:
            return sys.monitoring.DISABLE
        if threading.get_ident() == STATE.thread:
            STATE.count += 1
    except BaseException:
        STATE.failed = True
    return None


def _traced_set(obj, originalname):
    # The code objects to count, or None. obj plus at most 8 __wrapped__ hops; a cycle, a longer chain, a link without __code__, or an
    # innermost code that is not in the target file under the test's own name -> None. Never calls os.getcwd().
    codes = []
    seen = set()
    link = obj
    hops = 0
    while True:
        if id(link) in seen:
            return None
        seen.add(id(link))
        code = getattr(link, "__code__", None)
        if code is None:
            return None
        codes.append(code)
        following = getattr(link, "__wrapped__", None)
        if following is None:
            break
        hops += 1
        if hops > 8:
            return None
        link = following
    innermost = codes[-1]
    if innermost.co_name != originalname or os.path.realpath(innermost.co_filename) != STATE.target_real:
        return None
    return tuple(c for c in codes if os.path.realpath(c.co_filename) == STATE.target_real)


def pytest_collection_modifyitems(session, config, items):
    if len(items) != 1:
        STATE.failed = True


@pytest.hookimpl(hookwrapper=True)
def pytest_pyfunc_call(pyfuncitem):
    enabled = False
    if STATE.claimed and not STATE.failed:
        try:
            traced = _traced_set(pyfuncitem.obj, pyfuncitem.originalname)
            if traced is None:
                STATE.failed = True
            else:
                STATE.traced_ids = set(id(c) for c in traced)
                STATE.keep = list(traced)
                STATE.thread = threading.get_ident()
                monitoring = sys.monitoring
                monitoring.register_callback(4, monitoring.events.LINE, on_event)
                monitoring.register_callback(4, monitoring.events.JUMP, on_event)
                enabled = True
                monitoring.set_events(4, monitoring.events.LINE | monitoring.events.JUMP)
        except BaseException:
            STATE.failed = True
    try:
        yield
    finally:
        if enabled:
            try:
                sys.monitoring.set_events(4, 0)
            except BaseException:
                STATE.failed = True


def _write_marker(path, content):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        data = content.encode("ascii")
        while data:
            written = os.write(fd, data)
            data = data[written:]
    finally:
        os.close(fd)


# Precedence of the one terminal marker: failed first, then unavailable, then a zero count (a failure), then the success line. It also runs when
# the tool was not claimed (STATE.unavailable is then set, so the marker is UNAVAILABLE, or STATE.failed is, so it is the failed marker).
def _write_terminal_marker():
    if STATE.out is None:
        pytest.exit("trace out path missing", returncode=3)
    version = "%d.%d.%d" % sys.version_info[:3]
    failed_path = STATE.out + ".failed"
    if STATE.failed or (STATE.unavailable is None and STATE.count == 0):
        primary = None
    elif STATE.unavailable is not None:
        primary = "BENCH_TRACE_UNAVAILABLE: %s %s %s %s\n" % (STATE.unavailable, version, sys.implementation.name, STATE.nonce)
    else:
        primary = "BENCH_TRACE_LINES: %d %s %s %s\n" % (STATE.count, version, sys.implementation.name, STATE.nonce)
    if primary is not None:
        try:
            _write_marker(STATE.out, primary)
            return
        except Exception:
            pass
    try:
        _write_marker(failed_path, "failed\n")
    except Exception:
        pytest.exit("trace marker not writable", returncode=3)


def pytest_sessionfinish(session, exitstatus):
    try:
        if STATE.claimed:
            sys.monitoring.set_events(4, 0)
            if sys.monitoring.get_tool(4) != "bench_trace_plugin":
                STATE.failed = True
            _release_tool(sys)
    except BaseException:
        STATE.failed = True
    finally:
        _write_terminal_marker()


def _init(environ, sys_module):
    # Pop with defaults so a missing variable cannot leave the others behind.
    target = environ.pop("BENCH_TRACE_FILE", None)
    STATE.out = environ.pop("BENCH_TRACE_OUT", None)
    STATE.nonce = environ.pop("BENCH_TRACE_NONCE", None)
    if target is None or STATE.out is None or STATE.nonce is None:
        STATE.failed = True
    else:
        # Captured once, so a benchmark that later chdirs (even to /) cannot move them.
        try:
            STATE.root_real = os.path.realpath(os.getcwd())
            STATE.target_real = os.path.realpath(os.path.join(STATE.root_real, target))
            if not os.path.isfile(STATE.target_real) or not STATE.target_real.startswith(STATE.root_real.rstrip(os.sep) + os.sep):
                STATE.failed = True
        except Exception:
            STATE.failed = True
    # Hygiene, not an integrity control: sys.modules still holds this module.
    own_dir = os.path.dirname(__file__)
    while own_dir in sys.path:
        sys.path.remove(own_dir)
    if "PYTHONPATH" in environ:
        kept = [p for p in environ["PYTHONPATH"].split(os.pathsep) if p != own_dir]
        if kept:
            environ["PYTHONPATH"] = os.pathsep.join(kept)
        else:
            del environ["PYTHONPATH"]
    if not STATE.failed:
        token = _claim_tool(sys_module)
        if token is None:
            STATE.claimed = True
        elif token == "error":
            STATE.failed = True
        else:
            STATE.unavailable = token


_init(os.environ, sys)
"""


def _write_plugin(plugin_dir: str) -> str:
    """Write ``TRACE_PLUGIN_SOURCE`` as the one read-only file ``<plugin_dir>/bench_trace_plugin.py`` (O_EXCL, no symlink follow); return its path."""
    if os.pathsep in plugin_dir:
        raise BenchmarkGateError("MEASURE_FAILED", "plugin directory path contains the path separator")
    path = os.path.join(plugin_dir, _TRACE_MODULE + ".py")
    data = TRACE_PLUGIN_SOURCE.encode("ascii")
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o400)
        try:
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view):]
        finally:
            os.close(fd)
    except OSError as exc:
        raise BenchmarkGateError("MEASURE_FAILED", f"plugin write failed: {type(exc).__name__}: {exc}") from exc
    return path


def _verify_plugin(path: str) -> None:
    """Raise ``MEASURE_FAILED`` unless the file at ``path`` still holds exactly ``TRACE_PLUGIN_SOURCE``."""
    want = hashlib.sha256(TRACE_PLUGIN_SOURCE.encode("ascii")).digest()
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            chunks = []
            while True:
                chunk = os.read(fd, 1 << 16)
                if not chunk:
                    break
                chunks.append(chunk)
        finally:
            os.close(fd)
        got = hashlib.sha256(b"".join(chunks)).digest()
    except OSError:
        got = b""
    if got != want:
        raise BenchmarkGateError("MEASURE_FAILED", "plugin file hash mismatch")


def run_order(base_commit: str, head_commit: str, benchmark_sha256: str, attempt: int, repeats: int, *, salt: str | None = None) -> list[str]:
    """The round order: exactly ``repeats / 2`` rounds are ``"head_first"``, the rest ``"base_first"``, shuffled by a PRNG seeded from
    ``sha256(base_commit || head_commit || benchmark_sha256 || attempt [|| salt])`` (fields joined by ``\\0``). Strict alternation phase-locks onto a period-4 disturbance
    (about 25% false IMPROVED); a seeded balanced permutation does not, and a human can reproduce it. ``attempt`` makes the one allowed
    re-measure use a different order. ``salt`` (``None`` means unsalted: today's seed bytes, unchanged) is lowercase hex of 1 to 64
    characters and is appended as a fifth ``\\0``-joined seed field, so a run's order is reproducible from the recorded salt but not
    predictable from the public inputs. ``measure_paired`` passes its ``order_salt`` straight through (so ``None`` is unsalted there);
    ``compare`` generates a random salt when it is given none and records it as ``order_salt`` in its result, so the order of any
    result can be recomputed. Raises ``MEASURE_ARGS_INVALID`` for a bad argument."""
    import random

    if not all(isinstance(c, str) and _COMMIT_RE.fullmatch(c) for c in (base_commit, head_commit)):
        raise BenchmarkGateError("MEASURE_ARGS_INVALID", "commits must be 40 or 64 lowercase hex")
    if not isinstance(benchmark_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", benchmark_sha256, re.ASCII):
        raise BenchmarkGateError("MEASURE_ARGS_INVALID", "benchmark_sha256 must be 64 lowercase hex")
    if not _is_real_int(attempt) or not 1 <= attempt <= 2:
        raise BenchmarkGateError("MEASURE_ARGS_INVALID", "attempt must be 1 or 2")
    if not _is_real_int(repeats) or repeats not in _NEED_CLEAR:
        raise BenchmarkGateError("MEASURE_ARGS_INVALID", "repeats must be 4, 6 or 8")
    if salt is not None and not (isinstance(salt, str) and re.fullmatch(r"[0-9a-f]{1,64}", salt, re.ASCII)):
        raise BenchmarkGateError("MEASURE_ARGS_INVALID", "order_salt must be 1 to 64 lowercase hex characters")
    fields = (base_commit, head_commit, benchmark_sha256, str(attempt)) + (() if salt is None else (salt,))
    seed = hashlib.sha256("\0".join(fields).encode("ascii")).digest()
    order = ["head_first"] * (repeats // 2) + ["base_first"] * (repeats - repeats // 2)
    random.Random(int.from_bytes(seed, "big")).shuffle(order)
    return order


def side_env(bin_dir: str, scratch: str) -> dict[str, str]:
    """The child's environment, exactly nine keys: an allowlist, not a sandbox. The side's venv ``bin`` first on ``PATH`` (and ``VIRTUAL_ENV``),
    no user site, a fixed hash seed, ``PYTHONDONTWRITEBYTECODE=1``, fresh ``HOME`` and ``TMPDIR`` under ``scratch`` (it makes both
    directories), ``LANG``, pytest plugin autoload off. No ``PYTHONPYCACHEPREFIX``: a prefix
    would make CPython ignore every existing ``__pycache__`` and recompile the interpreter, pytest and the benchmark's imports on every
    run, pushing ratios toward 1 and letting compile time satisfy the workload floor; existing bytecode is read, none is written. No
    ``PYTHONPATH``, no SCM, cloud or API token. The trace's environment is ``trace_env``, which adds ``PYTHONPATH`` and the three ``BENCH_TRACE_*``
    keys (file, out, nonce) for the trace run only."""
    home = os.path.join(scratch, "home")
    tmp = os.path.join(scratch, "tmp")
    for directory in (home, tmp):
        os.makedirs(directory, exist_ok=True)
    return {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "VIRTUAL_ENV": os.path.dirname(bin_dir),
        "PYTHONNOUSERSITE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "LANG": "C.UTF-8",
        "HOME": home,
        "TMPDIR": tmp,
    }


def trace_env(env: dict[str, str], plugin_dir: str, benchmark_file: str, out_path: str, nonce: str) -> dict[str, str]:
    """A COPY of ``env`` plus the four keys the trace plugin reads: ``PYTHONPATH`` (``plugin_dir``), ``BENCH_TRACE_FILE``,
    ``BENCH_TRACE_OUT`` and ``BENCH_TRACE_NONCE``. ``env`` is not changed."""
    return {**env, "PYTHONPATH": plugin_dir, "BENCH_TRACE_FILE": benchmark_file, "BENCH_TRACE_OUT": out_path, "BENCH_TRACE_NONCE": nonce}


def pytest_argv(bin_dir: str, root: str, target: str, ini: str, *, plugins: tuple[str, ...] | list[str] = ()) -> list[str]:
    """The harness argv, built from the gate and never from the command string. ``-P`` drops the cwd entry from ``sys.path`` so a head-added
    ``pytest.py``, ``hashlib.py`` or ``statistics.py`` cannot shadow (the code under test must therefore be INSTALLED into the side's venv);
    ``-s`` lets the digest through; an empty harness-owned ini and ``--noconftest`` keep the tree's configuration out.
    ``plugins`` (keyword-only) is a tuple or list whose every element is exactly the trace module; each becomes ``-p <name>`` after
    ``-p no:cacheprovider`` and before the target. Anything else (a string, another name) is a ``ValueError``."""
    if not isinstance(plugins, (tuple, list)) or any(not isinstance(p, str) or p != _TRACE_MODULE for p in plugins):
        raise ValueError("plugins must be a tuple or list of the trace module name only")
    return [
        os.path.join(bin_dir, "python"), "-P", "-m", "pytest", "-q", "--no-header", "-s", "--noconftest",
        "--import-mode=importlib", "-c", ini, "--rootdir", root, "-p", "no:cacheprovider",
        *(arg for name in plugins for arg in ("-p", name)), target,
    ]


def _kill_group(pgid: int) -> None:
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):  # already gone, or a reused pgid we may not signal
        pass


def _guarded_signals() -> tuple:
    """The signals the harness guards: SIGTERM, SIGHUP and SIGINT where the platform has them (no SIGHUP on Windows). Built on each call, so
    importing this module never needs a POSIX-only name (``compare`` then reports ``UNSUPPORTED_PLATFORM`` instead of the import failing)."""
    return tuple(getattr(signal, name) for name in ("SIGTERM", "SIGHUP", "SIGINT") if hasattr(signal, name))



@contextlib.contextmanager
def _with_signal_handlers():
    """For CLI commands (main thread only; every CLI command installs it: ``compare``, ``run-once`` and ``cleanup``; the library functions
    ``compare`` and ``_run_once`` do not): SIGTERM, SIGHUP and SIGINT raise
    ``KeyboardInterrupt``, and the first one sets ``SIG_IGN`` for all three so a second cannot interrupt the cleanup. The previous
    handlers are restored in a ``finally``. A library caller on another thread must not use this (``signal.signal`` works only on the
    main thread), so it raises ``RuntimeError`` before changing anything."""
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError("signal handlers can be installed only from the main thread")

    guarded = _guarded_signals()

    def interrupt(_signum, _frame):
        for number in guarded:
            signal.signal(number, signal.SIG_IGN)
        raise KeyboardInterrupt

    old: list = []
    try:
        for number in guarded:
            old.append((number, signal.signal(number, interrupt)))
        yield
    finally:
        for number, handler in old:
            signal.signal(number, handler or signal.SIG_DFL)  # None: a handler Python did not install


def _run_once(argv: list[str], cwd: str, env: dict[str, str], timeout: float) -> tuple[int | None, int, bytes, bytes, bool]:
    """One child run: ``(exit code or None if killed by the watchdog, wall nanoseconds, stdout, stderr tail, output hit the size limit)``.
    A blocking ``wait`` with a watchdog ``Timer`` (cancelled and joined after the wait, so a late fire cannot ``killpg`` a reused pgid),
    and a group kill after EVERY run. ``RLIMIT_FSIZE`` kills nothing in Python (CPython ignores SIGXFSZ), so oversize is detected by a
    file whose size equals the limit. The child starts in its own session with default dispositions for the guarded signals and an empty
    signal mask (the parent has handlers for them, or ignores them, and blocks them around the spawn), no stdin, and ``env`` exactly as given. ``Popen`` failing
    raises ``_SpawnFailed`` (with the errno), which ``_execute`` splits into a provisioning fault of the side and a host fault. Used by
    ``measure_paired``, ``trace_paired`` and ``run_benchmark_once`` through ``_execute`` only."""
    import resource  # imported here, in the parent, not between fork and exec

    guarded = _guarded_signals()  # in the parent: the child touches nothing but `signal` and `resource`

    def child_setup() -> None:  # runs in the child between fork and exec
        for number in guarded:
            signal.signal(number, signal.SIG_DFL)  # an ignored signal would be inherited across exec
        signal.pthread_sigmask(signal.SIG_SETMASK, ())  # the parent's mask (below) would be inherited across exec too
        resource.setrlimit(resource.RLIMIT_FSIZE, (_RUN_FSIZE_LIMIT, _RUN_FSIZE_LIMIT))

    timed_out = threading.Event()
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        started = time.perf_counter_ns()
        # SIGTERM, SIGHUP and SIGINT are blocked from before the fork until the `try` below is entered, so a signal cannot arrive
        # after the child exists but before its group is guarded; the pending signal is delivered at the unmask, inside the `try`.
        # The mask is per thread: this window is safe only while the process is SINGLE-THREADED (a contract of this function, not
        # asserted; `preexec_fn` is thread-unsafe for the same reason).
        old_mask = signal.pthread_sigmask(signal.SIG_BLOCK, guarded)
        try:
            proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err, close_fds=True,
                                    start_new_session=True, preexec_fn=child_setup)
        except BaseException as exc:
            signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
            if isinstance(exc, (OSError, subprocess.SubprocessError)):
                raise _SpawnFailed(str(exc), exc.errno if isinstance(exc, OSError) else None) from exc  # a SubprocessError has no errno
            raise

        def fire() -> None:
            timed_out.set()
            _kill_group(proc.pid)

        watchdog = threading.Timer(timeout, fire)
        try:  # from here on the child exists: whatever goes wrong (even a failed thread start or Ctrl-C), its group dies
            signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)  # a pending signal is delivered here, inside the try
            watchdog.start()
            code = proc.wait()
            elapsed = time.perf_counter_ns() - started
        finally:
            try:  # the kill has its own `finally`: a KeyboardInterrupt while the watchdog is cancelled or joined cannot skip it
                watchdog.cancel()
                if watchdog.is_alive():
                    watchdog.join()
            finally:
                _kill_group(proc.pid)
        out_size = os.fstat(out.fileno()).st_size
        err_size = os.fstat(err.fileno()).st_size
        out.seek(0)
        stdout = out.read(_RUN_FSIZE_LIMIT)
        err.seek(max(0, err_size - _STDERR_TAIL))
        tail = err.read(_STDERR_TAIL)
    oversize = out_size >= _RUN_FSIZE_LIMIT or err_size >= _RUN_FSIZE_LIMIT
    return (None if timed_out.is_set() else code), elapsed, stdout, tail, oversize


class _SpawnFailed(Exception):
    """``Popen`` could not start the child. ``errno`` (``None`` for a ``SubprocessError``) tells a provisioning fault of that side (no
    ``<bin>/python``, not executable) from a host fault (no processes or memory left); ``_execute`` splits on it. The default keeps
    callers that build one from a message alone meaning the provisioning case."""

    def __init__(self, message: str, errno: int | None = errno.ENOENT) -> None:  # the default is bound here, before the parameter shadows the module
        super().__init__(message)
        self.errno = errno


_SPAWN_PROVISIONING_ERRNOS = frozenset({errno.ENOENT, errno.EACCES, errno.ENOEXEC, errno.ENOTDIR})  # a missing cwd is ENOENT too


# The ONE table of `_execute` failure kinds: kind -> the suffix of the reason and the error code (``<SIDE>_<suffix>``). A spawn failure (a venv
# that was not provisioned) is a nonzero exit. `_run_error_code`, the trace rows of the `compare` mapping (T4), `_RUN_FAILURE_KINDS` and the
# `run-once` reasons (`_RUN_ONCE_REASONS`) all derive from it, so a new kind cannot be handled in one place and forgotten in another.
_KIND_SUFFIX = {"nonzero": "NONZERO_EXIT", "timeout": "TIMEOUT", "oversize": "OUTPUT_TOO_LARGE", "spawn": "NONZERO_EXIT"}
_UNSIDED_KINDS = frozenset({"oversize"})  # their ERROR CODE has no side prefix (`OUTPUT_TOO_LARGE`; the `compare` reason has one)


def _run_error_code(side: str, kind: str) -> str:
    """The ``measure_paired`` error code of an ``_execute`` failure kind; an unknown kind is a bug in this file, not an input."""
    if kind not in _KIND_SUFFIX:
        raise AssertionError(f"unknown _execute failure kind {kind!r}")
    return _KIND_SUFFIX[kind] if kind in _UNSIDED_KINDS else f"{side.upper()}_{_KIND_SUFFIX[kind]}"


def _digest_of(stdout: bytes) -> str | None:
    """The LAST ``BENCH_RESULT_DIGEST: <64 hex>`` in the output, unanchored (pytest's progress dot shares the line)."""
    found = _DIGEST_RE.findall(stdout)
    return found[-1].decode("ascii") if found else None


def _tail_detail(tail: bytes) -> str:
    """The END of the child's stderr (a traceback's useful line is last), for the exception detail, which keeps the first 200 characters."""
    return tail.decode("ascii", "replace")[-150:]


def _prepare_run(side: str, bin_dir: str, work: str, ini_path: str | None = None) -> tuple[str, dict, str]:
    """Make the run's scratch directory (``tempfile.mkdtemp`` inside ``work``, so an unpredictable name and a planted name cannot fail the run)
    and build its environment (``side_env`` makes the home and tmp directories). Returns ``(scratch, env, ini)``: ``ini`` is ``ini_path``
    when given, else a fresh ``empty.ini`` written inside the scratch, so a child that rewrites its ini changes nothing for the next run
    (no mutable harness state crosses a child). Shared by ``measure_paired``, ``trace_paired`` and ``run_benchmark_once``; the caller owns
    ``work`` (a temporary directory it removes), and ``_execute`` removes the scratch."""
    scratch = tempfile.mkdtemp(dir=work)
    env = side_env(bin_dir, scratch)
    ini = ini_path
    if ini is None:
        ini = os.path.join(scratch, "empty.ini")
        with open(ini, "w", encoding="ascii") as handle:
            handle.write(_EMPTY_INI)
    return scratch, env, ini


def _execute(side: str, argv: list[str], root: str, scratch: str, env: dict[str, str], timeout_seconds: float,
             fail: Callable[[str, str], BenchmarkGateError], guard: Callable[[str, str], None] | None = None) -> tuple[int, bytes]:
    """Run once, always remove ``scratch``, and raise ``fail(kind, detail)`` for a spawn failure, oversize output, timeout or nonzero exit
    (kinds ``spawn``, ``oversize``, ``timeout``, ``nonzero``, checked in that order; ``spawn`` only for a provisioning errno of the side,
    ``_SPAWN_PROVISIONING_ERRNOS``). A host spawn fault (``EAGAIN``, ``ENOMEM``, a failed ``preexec_fn``) raises ``RuntimeError``, which the
    callers turn into ``MEASURE_FAILED``. Returns ``(elapsed_ns, stdout)``; the exit code and stderr are not returned (only a failure's
    detail shows the stderr tail). ``fail`` is the caller's error factory: ``measure_paired`` and ``run_benchmark_once`` map the kind to
    a code and keep it in ``error.kind``; ``trace_paired`` makes every kind a ``TRACE_MISMATCH``. ``guard(side, root)``, when given, runs
    immediately before the spawn (the scratch is still removed if it raises): ``compare`` uses it to check that the directories the child
    runs in are still the ones step 9 recorded."""
    try:
        if guard is not None:
            guard(side, root)
        code, elapsed, stdout, tail, oversize = _run_once(argv, root, env, float(timeout_seconds))
    except _SpawnFailed as exc:
        if exc.errno in _SPAWN_PROVISIONING_ERRNOS:  # no <bin>/python, not executable, a missing cwd: the side was not provisioned
            raise fail("spawn", f"could not start the run: {exc}") from exc
        raise RuntimeError("host spawn fault") from exc  # EAGAIN, ENOMEM, a failed preexec_fn: the host, not the side (callers turn it into MEASURE_FAILED)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    if oversize:
        raise fail("oversize", f"{side} run wrote {_RUN_FSIZE_LIMIT} bytes")
    if code is None:
        raise fail("timeout", f"run exceeded {timeout_seconds} s")
    if code != 0:
        raise fail("nonzero", f"exit {code}: {_tail_detail(tail)}")
    return elapsed, stdout


_TARGET_MESSAGE = "target must be a .py path under the root, without '..' or a leading '-'"


def _benchmark_file_of(target: object) -> str:
    """The file part of a pytest target (before the first ``::``), checked: the target is ASCII with no NUL; the file part is a relative
    ``.py`` path with no empty, ``.`` or ``..`` component, no control character (below 0x20 or 0x7f), no backslash and no leading ``-``.
    The id part after ``::`` may hold a backslash (a parametrize id such as ``t[a\\b]``)."""
    if not isinstance(target, str) or not target.isascii() or "\0" in target:
        raise BenchmarkGateError("MEASURE_ARGS_INVALID", _TARGET_MESSAGE)
    file_part = target.split("::", 1)[0]
    if (not file_part or "\\" in file_part or any(ord(c) < 0x20 or ord(c) == 0x7F for c in file_part)
            or file_part.startswith(("/", "-")) or not file_part.endswith(".py") or any(part in ("", ".", "..") for part in file_part.split("/"))):
        raise BenchmarkGateError("MEASURE_ARGS_INVALID", _TARGET_MESSAGE)
    return file_part


def _check_timeout(timeout_seconds: object) -> None:
    """Raise ``MEASURE_ARGS_INVALID`` unless ``timeout_seconds`` is a real number (not a bool, not NaN) in (0, 3600]."""
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not 0 < timeout_seconds <= 3600 \
            or timeout_seconds != timeout_seconds:
        raise BenchmarkGateError("MEASURE_ARGS_INVALID", "timeout_seconds must be a number in (0, 3600]")


def _real_dirs(name: str, root: object, bin_dir: object) -> tuple[str, str]:
    """``(realpath root, realpath bin)`` of one side, each an existing absolute directory, else ``MEASURE_ARGS_INVALID``."""
    for label, path in (("root", root), ("bin", bin_dir)):
        if not isinstance(path, str) or not path or "\0" in path or not os.path.isabs(path) or not os.path.isdir(path):
            raise BenchmarkGateError("MEASURE_ARGS_INVALID", f"{name} {label} must be an existing absolute directory")
    return os.path.realpath(root), os.path.realpath(bin_dir)


def _check_ini(ini_path: object) -> None:
    if ini_path is not None and (not isinstance(ini_path, str) or not os.path.isabs(ini_path) or not os.path.isfile(ini_path)):
        raise BenchmarkGateError("MEASURE_ARGS_INVALID", "ini_path must be an existing absolute file")


def _check_one_side(root: object, bin_dir: object, target: object, ini_path: object) -> tuple[str, str, str]:
    """Validate one side for ``run_benchmark_once``; returns ``(realpath root, realpath bin, benchmark_file)``. The root and bin are existing
    absolute directories, ``bin`` passes ``_venv_layout`` (a plain isolated venv), and the target's file is a regular, non-symlink file
    that stays under the root once resolved (an intermediate symlink out of the root is refused). ``root`` need not be an export:
    nothing here seals, hashes or writes. The timeout is the caller's (``_check_timeout``)."""
    real_root, real_bin = _real_dirs("side", root, bin_dir)
    try:
        _venv_layout(bin_dir)
    except BenchmarkGateError as exc:  # the layout's own codes are the compare pipeline's; here every bad argument is one code
        raise BenchmarkGateError("MEASURE_ARGS_INVALID", f"bin is not an isolated venv bin: {exc.code}") from exc
    benchmark_file = _benchmark_file_of(target)
    path = os.path.join(root, benchmark_file)
    try:
        regular = stat.S_ISREG(os.lstat(path).st_mode)  # lstat: a symlink target is refused, not followed
    except OSError:
        regular = False
    if not regular or not _inside(os.path.realpath(path), real_root):
        raise BenchmarkGateError("MEASURE_ARGS_INVALID", "target must be a regular file (not a symlink) under the root")
    _check_ini(ini_path)
    return real_root, real_bin, benchmark_file


def _check_sides(base_root: object, head_root: object, base_bin: object, head_bin: object, target: object,
                 ini_path: object) -> tuple[dict, str]:
    """Validate the two sides, the target and the ini; returns ``({name: (realpath root, realpath bin)}, benchmark_file)``."""
    sides = {}
    for name, root, bin_dir in (("base", base_root, base_bin), ("head", head_root, head_bin)):
        sides[name] = _real_dirs(name, root, bin_dir)
    for index in (0, 1):  # root, bin: the same directory under two names (a symlink, or a case-folding file system) is one directory
        if os.path.samefile(sides["base"][index], sides["head"][index]):
            raise BenchmarkGateError("MEASURE_ARGS_INVALID", "the two sides must not share a root or a bin directory")
    if _inside(sides["base"][0], sides["head"][0]) or _inside(sides["head"][0], sides["base"][0]):
        raise BenchmarkGateError("MEASURE_ARGS_INVALID", "neither root may contain the other")
    benchmark_file = _benchmark_file_of(target)
    _check_ini(ini_path)
    return sides, benchmark_file


def measure_paired(base_root: str, head_root: str, base_bin: str, head_bin: str, target: str, *, repeats: int, timeout_seconds: float,
                   base_commit: str, head_commit: str, benchmark_sha256: str, attempt: int = 1, warmup: int = 1,
                   min_base_ns: int = _MIN_BASE_NS, argv_builder=None, ini_path: str | None = None, order_salt: str | None = None,
                   spawn_guard: Callable[[str, str], None] | None = None) -> dict:
    """Run ``warmup`` untimed rounds, then ``repeats`` timed rounds; every round runs both sides once, base first in warmup and in the
    order ``run_order`` gives afterwards. Returns ``{"order", "base_ns", "head_ns", "digest", "argv"}``: ``base_ns[i]`` and ``head_ns[i]``
    are the wall nanoseconds of timed round ``i`` (positive ints, ready for ``evaluate_paired_samples``), ``digest`` the one digest every
    run of both sides printed, ``argv`` the ``{"base": ..., "head": ...}`` command lines (so a human can rerun them; with the default
    builder the ini is ``ini_path`` when given, else a temporary file that is gone when this returns).

    Raises ``BenchmarkGateError`` with a ``MEASURE_REFUSAL_CODES`` code, or ``MEASURE_ARGS_INVALID`` (a caller error) or ``MEASURE_FAILED`` (a harness fault: no disk space, no thread; not the Builder's). The exception
    carries (always, ``None`` when not applicable) ``side`` (``"base"``, ``"head"`` or ``None``), ``phase`` (``"warmup"``, ``"timed"`` or ``None``) and, for a failure after
    timing began (``phase == "timed"``), ``partial`` (``{"order", "base_ns", "head_ns"}`` of the completed rounds). A spawn failure (no ``<bin>/python``: a venv that was not
    provisioned) is ``<SIDE>_NONZERO_EXIT``. ``kind`` is the ``_execute`` kind (``spawn``, ``oversize``, ``timeout``, ``nonzero``) of a failed run and ``None`` for every
    other error (a digest error, ``WORKLOAD_TOO_SHORT``, ``MEASURE_FAILED``, a bad argument): ``compare`` needs it because a spawn and a nonzero exit share a code. Digest rules: after the FIRST warmup round both sides have run, so a digest printed by
    neither is ``DIGEST_MISSING``, by one is ``DIGEST_MISMATCH``, by both but different is ``DIGEST_MISMATCH`` (a benchmark that is
    nondeterministic on both sides is therefore reported as a mismatch there); from then on a run without a digest or with another one is
    ``DIGEST_UNSTABLE``; the digests of ALL runs (warmup included) must be one value at the end. ``WORKLOAD_TOO_SHORT`` needs the timed
    rounds and names the measured median. ``argv_builder(side, bin_dir, root, target) -> argv`` is the test seam; the default is
    ``pytest_argv``. ``order_salt`` is ``run_order``'s ``salt`` (``None``: unsalted; ``compare`` always passes one). ``phase`` here is only ``"warmup"`` or ``"timed"``; the paired trace run is ``trace_paired``, a separate function.

    ``spawn_guard(side, root)`` (``None``: no guard; ``compare`` always passes one) is called immediately before EVERY spawn (warmup and timed), with the side and the root the child will run in and
    returns silently or raises ``_IdentityChanged``. That exception is NOT a ``BenchmarkGateError`` (so no handler of one can swallow it) and
    is propagated unchanged after the scratch and work directories are removed; no further child is started. It carries ``side`` (the side
    about to be spawned), ``phase`` (``"warmup"`` or ``"timed"``), ``kind`` ``"harness"`` and ``partial`` (the completed timed rounds once
    ``phase == "timed"``, else ``None``), the same semantics as an error of this function."""
    if os.name != "posix":
        raise BenchmarkGateError("UNSUPPORTED_PLATFORM", "the harness needs POSIX process groups")
    order = run_order(base_commit, head_commit, benchmark_sha256, attempt, repeats, salt=order_salt)
    if not _is_real_int(warmup) or not 1 <= warmup <= 3:
        raise BenchmarkGateError("MEASURE_ARGS_INVALID", "warmup must be 1 to 3")
    _check_timeout(timeout_seconds)
    if not _is_real_int(min_base_ns) or min_base_ns < 0:
        raise BenchmarkGateError("MEASURE_ARGS_INVALID", "min_base_ns must be a non-negative int")
    sides, _ = _check_sides(base_root, head_root, base_bin, head_bin, target, ini_path)

    base_ns: list[int] = []
    head_ns: list[int] = []
    phase_now: list[str | None] = [None]

    def fail(code: str, detail: str, side: str | None, phase: str | None) -> BenchmarkGateError:
        error = BenchmarkGateError(code, detail)
        error.side, error.phase = side, phase
        error.partial = {"order": order, "base_ns": list(base_ns), "head_ns": list(head_ns)} if phase == "timed" else None
        return error

    try:
        with tempfile.TemporaryDirectory(prefix="bench-run-") as work:
            work_stat = os.lstat(work)
            work_identity = (work_stat.st_dev, work_stat.st_ino)
            digests: dict[str, set[str]] = {"base": set(), "head": set()}
            argvs: dict[str, list[str]] = {}

            def run(side: str, phase: str) -> tuple[int, str | None]:
                phase_now[0] = phase
                now = os.lstat(work)  # a child that replaced the work directory is a denial, not a measurement
                if (now.st_dev, now.st_ino) != work_identity:
                    raise fail("MEASURE_FAILED", "the work directory was replaced during the measurement", None, phase)
                root, bin_dir = sides[side]
                scratch, env, ini = _prepare_run(side, bin_dir, work, ini_path)
                argv = argv_builder(side, bin_dir, root, target) if argv_builder else pytest_argv(bin_dir, root, target, ini)
                argvs.setdefault(side, argv)

                def adapt(kind: str, detail: str) -> BenchmarkGateError:
                    error = fail(_run_error_code(side, kind), detail, side, phase)
                    error.kind = kind  # compare's verdict mapping needs the kind, not only the code (a spawn and a nonzero exit share a code)
                    return error

                try:
                    elapsed, stdout = _execute(side, argv, root, scratch, env, timeout_seconds, adapt, guard=spawn_guard)
                except _IdentityChanged as changed:  # not a BenchmarkGateError: it passes the handler below; give it the attributes of the others
                    changed.side, changed.phase, changed.kind = side, phase, "harness"
                    changed.partial = {"order": order, "base_ns": list(base_ns), "head_ns": list(head_ns)} if phase == "timed" else None
                    raise
                return elapsed, _digest_of(stdout)

            def record(side: str, phase: str, digest: str | None, first_round: bool) -> None:
                if digest is None:
                    if not first_round:
                        raise fail("DIGEST_UNSTABLE", f"{side} printed no digest after the first round", side, phase)
                    return
                digests[side].add(digest)
                if len(digests[side]) > 1:
                    raise fail("DIGEST_UNSTABLE", f"{side} printed {len(digests[side])} different digests", side, phase)

            for index in range(warmup):
                for side in ("base", "head"):
                    record(side, "warmup", run(side, "warmup")[1], index == 0)
                if index == 0:
                    if not digests["base"] and not digests["head"]:
                        raise fail("DIGEST_MISSING", "neither side printed a digest in the first warmup round", None, "warmup")
                    if digests["base"] != digests["head"]:
                        raise fail("DIGEST_MISMATCH", "the sides printed different digests (or only one printed one) in the first warmup round",
                                   None, "warmup")
            for position in order:
                pair = ("head", "base") if position == "head_first" else ("base", "head")
                took = {}
                for side in pair:
                    took[side], digest = run(side, "timed")
                    record(side, "timed", digest, False)
                base_ns.append(max(took["base"], 1))
                head_ns.append(max(took["head"], 1))
            median = _median([Fraction(v) for v in base_ns])
            if median < min_base_ns:
                raise fail("WORKLOAD_TOO_SHORT", f"base median {int(median)} ns is under {min_base_ns} ns", "base", "timed")
            return {"order": order, "base_ns": base_ns, "head_ns": head_ns, "digest": next(iter(digests["base"])), "argv": argvs}
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:  # no disk space, no thread, a failed temp file: a harness fault
        error = BenchmarkGateError("MEASURE_FAILED", f"{type(exc).__name__}: {exc}")
        error.phase = phase_now[0]
        error.partial = {"order": order, "base_ns": list(base_ns), "head_ns": list(head_ns)} if phase_now[0] == "timed" else None
        raise error from exc


_TRACE_LINES_RE = re.compile(r"\ABENCH_TRACE_LINES: ([0-9]{1,18}) ([0-9]+\.[0-9]+\.[0-9]+) ([a-z]+) ([0-9a-f]{32})\n\Z")
_TRACE_UNAVAILABLE_RE = re.compile(
    r"\ABENCH_TRACE_UNAVAILABLE: (no_monitoring|tool_in_use) ([0-9]+\.[0-9]+\.[0-9]+) ([a-z]+) ([0-9a-f]{32})\n\Z")
_TRACE_RESULT_MAX = 256  # a result line is about 60 bytes
_BODY_SOURCE_MAX = 16 * 1024
_CONTROL_FLOW_NODES = (ast.For, ast.AsyncFor, ast.While, ast.If, ast.IfExp, ast.Try, ast.TryStar, ast.Match, ast.BoolOp, ast.ListComp,
                       ast.SetComp, ast.DictComp)
_NOT_ENTERED_NODES = (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef, ast.GeneratorExp)  # the trace cannot see into these


def _read_regular_file(path: str, limit: int, owner_only: bool) -> bytes | None:
    """At most ``limit`` bytes of the regular file at ``path`` (never followed through a symlink, never blocking on a FIFO), or ``None``
    when it is absent, not a regular file, longer than ``limit`` or unreadable. ``owner_only`` also needs a single link and our uid.
    The checks are made on the open descriptor, so a swap after the ``open`` cannot change what was checked."""
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    if owner_only:
        flags |= os.O_NOCTTY | os.O_CLOEXEC
    try:
        fd = os.open(path, flags)
    except OSError:
        return None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit or (owner_only and (info.st_nlink != 1 or info.st_uid != os.getuid())):
            return None
        chunks: list[bytes] = []
        total = 0
        while total <= limit:
            chunk = os.read(fd, limit + 1 - total)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        data = b"".join(chunks)
        return data if len(data) <= limit else None
    except OSError:
        return None
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


def _body_has_control_flow(root: str, benchmark_file: str, target: str) -> bool:
    """Advisory: does the benchmark's test body loop or branch (what the trace can discriminate)? Reads the base root's benchmark file,
    picks the module-level function the target names (the LAST one when a name is defined twice: Python runs the last), else the first
    module-level ``test*`` function, and walks it without entering nested lambdas, functions or generator expressions. A class-method or
    parametrized target (``file::Class::method``) names no module-level function, so it falls back to the first module-level test function
    (advisory only). Every failure to read or parse is ``False``."""
    try:
        data = _read_regular_file(os.path.join(root, benchmark_file), _BODY_SOURCE_MAX, False)
        if data is None:
            return False
        functions = [node for node in ast.parse(data).body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        parts = target.split("::")
        named = [f for f in functions if len(parts) == 2 and f.name == parts[1]]
        chosen = named[-1] if named else next((f for f in functions if f.name.startswith("test")), None)
        if chosen is None:
            return False
        stack: list[ast.AST] = list(chosen.body)
        while stack:
            node = stack.pop()
            if isinstance(node, _NOT_ENTERED_NODES):
                continue
            if isinstance(node, _CONTROL_FLOW_NODES):
                return True
            stack.extend(ast.iter_child_nodes(node))
        return False
    except Exception:  # noqa: BLE001 - SyntaxError, ValueError, RecursionError, MemoryError, OSError: advisory only
        return False


class _TraceResult(NamedTuple):
    kind: str  # "lines" or "unavailable"
    value: int | str  # the executed-line count, or the unavailability token
    interpreter: str  # "<version> <impl>"


def _trace_result(raw: bytes | None, nonce: str) -> _TraceResult | None:
    """A ``_TraceResult`` for a well-formed result of THIS run (``kind`` ``lines`` with the int count, or ``unavailable`` with the token),
    else ``None``."""
    if raw is None:
        return None
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        return None
    found = _TRACE_LINES_RE.match(text)
    if found:
        if int(found.group(1)) == 0 or found.group(4) != nonce:
            return None
        return _TraceResult("lines", int(found.group(1)), f"{found.group(2)} {found.group(3)}")
    found = _TRACE_UNAVAILABLE_RE.match(text)
    if found and found.group(4) == nonce:
        return _TraceResult("unavailable", found.group(1), f"{found.group(2)} {found.group(3)}")
    return None


def trace_paired(base_root: str, head_root: str, base_bin: str, head_bin: str, target: str, *, timeout_seconds: float,
                 argv_builder=None, ini_path: str | None = None, spawn_guard: Callable[[str, str], None] | None = None) -> dict:
    """One untimed, traced run per side (base, then head) and a comparison of what the harness-owned plugin counted in the test body.
    Returns ``{"base": int, "head": int, "interpreter": "<version> <impl>", "argv": {"base": [...], "head": [...]},
    "body_has_control_flow": bool}`` (the last is advisory: computed from the base root's benchmark file before the first run).

    Validation is C4d-1's (``UNSUPPORTED_PLATFORM``, then the timeout, then the sides, target and ini: ``MEASURE_ARGS_INVALID``), with
    ``phase`` ``None``. After it every error has ``phase == "trace"`` and ``partial`` ``None``. One rule: a fault of the harness's own
    machinery (a temp directory, the plugin file, its hash, a path separator in the directory) is ``MEASURE_FAILED`` (``side`` ``None``);
    what the child did (a failed run, a missing or malformed result, ``.failed``, differing counts or interpreters) is
    ``TRACE_MISMATCH``, or ``TRACE_UNAVAILABLE`` when both sides report the same unavailability. A hard failure on either side raises at
    once. Every error raised after the validation carries ``kind``, one of ``TRACE_FAILURE_KINDS`` (the ``_execute`` kinds are the first four;
    the validation errors have ``kind`` ``None``, and ``measure_paired`` and ``run_benchmark_once`` also set ``kind``, to an ``_execute`` kind, on a failed run). An error raised after
    BOTH sides produced a result (the kinds ``unavailable_one_side``, ``unavailable_tokens_differ``, ``unavailable_interpreters_differ``,
    ``interpreters_differ``, ``counts_differ``, ``unavailable``) also carries ``trace``: ``{"base": {"kind": "lines"|"unavailable", "value":
    int count | str token, "interpreter": "<ver> <impl>"}, "head": {...}, "argv": {"base": [...], "head": [...]}, "body_has_control_flow":
    bool}``; ``trace`` is ``None`` for an error raised during a side's run. The run's timeout is ``_TRACE_TIMEOUT_FACTOR * timeout_seconds``. The digest is not checked and stdout is not parsed.
    ``argv_builder(side, bin_dir, root, target) -> argv`` is the test seam.

    ``spawn_guard(side, root)`` (``None``: no guard; ``compare`` always passes one) is called immediately before EVERY spawn (with the side and the root the child will run in) and returns silently or
    raises ``_IdentityChanged``: not a ``BenchmarkGateError``, propagated unchanged after the side's work directory is removed, with ``side``
    (the side about to be spawned), ``phase`` ``"trace"``, ``kind`` ``"harness"``, ``partial`` ``None`` and ``trace`` ``None``."""
    if os.name != "posix":
        raise BenchmarkGateError("UNSUPPORTED_PLATFORM", "the harness needs POSIX process groups")
    _check_timeout(timeout_seconds)
    sides, benchmark_file = _check_sides(base_root, head_root, base_bin, head_bin, target, ini_path)

    def fail(code: str, detail: str, kind: str, side: str | None = None, trace: dict | None = None) -> BenchmarkGateError:
        error = BenchmarkGateError(code, detail)
        error.side, error.phase, error.partial, error.kind, error.trace = side, "trace", None, kind, trace
        return error

    def run_side(side: str) -> tuple[_TraceResult, list[str]]:
        root, bin_dir = sides[side]
        with tempfile.TemporaryDirectory(prefix="bench-run-") as work:
            scratch, env, ini = _prepare_run(side, bin_dir, work, ini_path)
            plugin_dir = tempfile.mkdtemp(dir=work, prefix="plugin-")
            out_dir = tempfile.mkdtemp(dir=work, prefix="out-")  # a sibling of scratch: _execute removes scratch before the result is read
            out_path = os.path.join(out_dir, "trace.out")
            nonce = os.urandom(16).hex()
            plugin_path = _write_plugin(plugin_dir)
            argv = argv_builder(side, bin_dir, root, target) if argv_builder else pytest_argv(bin_dir, root, target, ini, plugins=(_TRACE_MODULE,))
            env = trace_env(env, plugin_dir, benchmark_file, out_path, nonce)
            _verify_plugin(plugin_path)  # last, right before the child starts: nothing the argv builder did can slip past it

            def adapt(kind: str, detail: str) -> BenchmarkGateError:
                if kind == "timeout":
                    detail += f" ({_TRACE_TIMEOUT_FACTOR}x the per-run timeout)"
                return fail("TRACE_MISMATCH", f"{kind}: {detail}", kind, side)

            try:
                _execute(side, argv, root, scratch, env, _TRACE_TIMEOUT_FACTOR * timeout_seconds, adapt, guard=spawn_guard)
            except _IdentityChanged as changed:
                changed.side, changed.phase, changed.kind, changed.partial = side, "trace", "harness", None
                raise
            if os.path.lexists(out_path + ".failed"):
                raise fail("TRACE_MISMATCH", "plugin reported failure", "plugin_failed", side)
            result = _trace_result(_read_regular_file(out_path, _TRACE_RESULT_MAX, True), nonce)
            if result is None:
                raise fail("TRACE_MISMATCH", "no trace result", "no_result", side)
            return result, argv

    has_control_flow = _body_has_control_flow(sides["base"][0], benchmark_file, target)
    results: dict[str, _TraceResult] = {}
    argvs: dict[str, list[str]] = {}
    try:
        for side in ("base", "head"):
            results[side], argvs[side] = run_side(side)
    except BenchmarkGateError as exc:  # raised by _write_plugin / _verify_plugin, or by `fail`
        if exc.phase is None:
            exc.side, exc.phase, exc.partial, exc.kind = None, "trace", None, "harness"
        raise
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:  # the harness's own machinery, outside the child
        raise fail("MEASURE_FAILED", f"{type(exc).__name__}: {exc}", "harness") from exc

    base, head = results["base"], results["head"]
    seen = {"base": base._asdict(), "head": head._asdict(), "argv": dict(argvs), "body_has_control_flow": has_control_flow}

    def after(code: str, detail: str, kind: str, side: str | None = None) -> BenchmarkGateError:
        return fail(code, detail, kind, side, seen)

    if (base.kind == "unavailable") != (head.kind == "unavailable"):
        raise after("TRACE_MISMATCH", "unavailable on one side only", "unavailable_one_side", "base" if base.kind == "unavailable" else "head")
    if base.kind == "unavailable":
        if base.value != head.value:
            raise after("TRACE_MISMATCH", f"unavailable for different reasons: base {base.value}, head {head.value}", "unavailable_tokens_differ")
        if base.interpreter != head.interpreter:
            raise after("TRACE_MISMATCH", f"{base.value} on different interpreters: base {base.interpreter}, head {head.interpreter}",
                        "unavailable_interpreters_differ")
        raise after("TRACE_UNAVAILABLE", f"{base.value} ({base.interpreter})", "unavailable")
    if base.interpreter != head.interpreter:
        raise after("TRACE_MISMATCH", f"different interpreters: base {base.interpreter}, head {head.interpreter}", "interpreters_differ")
    if base.value != head.value:
        raise after("TRACE_MISMATCH", f"line counts differ: base {base.value}, head {head.value}", "counts_differ")
    return {"base": base.value, "head": head.value, "interpreter": base.interpreter, "argv": argvs, "body_has_control_flow": has_control_flow}


def run_benchmark_once(root: str, bin_dir: str, target: str, *, timeout_seconds: float, side: str = "head", argv_builder=None,
                       ini_path: str | None = None) -> dict:
    """One untimed run of the benchmark in ``root`` with ``bin_dir``'s interpreter, through the same ``_prepare_run``/``_execute`` chain as
    ``measure_paired`` (own scratch and ini, removed afterwards). Returns ``{"digest", "argv"}``; the digest is what the child printed and
    is NOT evidence. Nothing in ``root`` is sealed, hashed or written by this function. Raises ``BenchmarkGateError``: ``MEASURE_ARGS_INVALID``,
    ``UNSUPPORTED_PLATFORM``, ``<SIDE>_NONZERO_EXIT`` (also a spawn failure), ``<SIDE>_TIMEOUT``, ``OUTPUT_TOO_LARGE``, ``DIGEST_MISSING``
    (each with ``side`` set; ``kind`` is the ``_execute`` kind, ``None`` for ``DIGEST_MISSING``) or ``MEASURE_FAILED`` (a harness fault)."""
    if os.name != "posix":
        raise BenchmarkGateError("UNSUPPORTED_PLATFORM", "the harness needs POSIX process groups")
    if side not in ("base", "head"):
        raise BenchmarkGateError("MEASURE_ARGS_INVALID", "side must be 'base' or 'head'")
    _check_timeout(timeout_seconds)
    real_root, real_bin, _ = _check_one_side(root, bin_dir, target, ini_path)

    def fail(code: str, detail: str, kind: str | None) -> BenchmarkGateError:
        error = BenchmarkGateError(code, detail)
        error.side, error.phase, error.partial, error.kind = side, None, None, kind
        return error

    try:
        with tempfile.TemporaryDirectory(prefix="bench-run-") as work:
            scratch, env, ini = _prepare_run(side, real_bin, work, ini_path)
            argv = argv_builder(side, real_bin, real_root, target) if argv_builder else pytest_argv(real_bin, real_root, target, ini)
            _, stdout = _execute(side, argv, real_root, scratch, env, timeout_seconds,
                                 lambda kind, detail: fail(_run_error_code(side, kind), detail, kind))
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:  # no disk space, no thread, a host spawn fault: a harness fault
        error = BenchmarkGateError("MEASURE_FAILED", f"{type(exc).__name__}: {exc}")
        error.side, error.phase, error.partial = side, None, None
        raise error from exc
    digest = _digest_of(stdout)
    if digest is None:
        raise fail("DIGEST_MISSING", "the run printed no digest", None)
    return {"digest": digest, "argv": argv}


# ---------------------------------------------------------------------------
# C4d-3 compare: vocabularies, `Side`, the internal verdict, result assembly and the result writer
# ---------------------------------------------------------------------------

class Side(NamedTuple):
    """One side of a comparison: its export root and commit, its venv's ``bin`` directory, and the snapshot of that venv with the
    sha256 pins the Orchestrator minted (``snapshot-venv``) before any install."""
    root: str
    commit: str
    bin_dir: str
    snapshot: str
    snapshot_sha256: str
    interpreter_sha256: str


COMPARE_RESULTS = frozenset({"IMPROVED", "NOT_IMPROVED", "INCONCLUSIVE", "REJECTED"})
COMPARE_STAGES = ("pre_overlay", "overlaid", "ran")
# The `detail` of an ISOLATION_REJECTED result.
ISOLATION_DETAILS = (
    "ROOT_HAS_GIT", "BIN_NOT_ISOLATED", "NOT_PROVISIONED", "INTERPRETER_DIFFERS", "INTERPRETER_WRITABLE", "HARNESS_FILE_UNDER_ROOT",
    "TRACKED_FILE_DIFFERS", "UNTRACKED_PYTHON_FILE", "DEPENDENCY_PARITY", "BENCHMARK_BYTES_DIFFER", "VENV_NOT_ISOLATED", "VENV_HOOK_REJECTED",
    "SNAPSHOT_CHANGED", "INTERPRETER_CHANGED", "EXPORT_CHANGED", "VENV_CHANGED", "HASH_UNREADABLE", "FINGERPRINT_FAILED",
)
# The closed set of a result's `detail`'s first word is derived below from the one table of reasons.
_HOSTILE_TREE_CODES = ("SEAL_FAILED", "TREE_UNREADABLE", "TREE_TOO_LARGE", "GIT_OUTPUT_TOO_LARGE")  # codes a hostile export tree can raise (spec 2.1)
_READ_BENCHMARK_CODES = ("OVERLAY_PATH_REJECTED", "OVERLAY_NOT_REGULAR")  # `read_benchmark` refusals of a hostile export: EXPORT_REJECTED too (steps 7 and 8)
_GATE_REJECTION_CODES = ("GATE_MISSING", "KEY_MISSING", "KEY_UNKNOWN", "TYPE_REJECTED", "PATH_REJECTED", "SYMBOL_REJECTED", "COMMAND_REJECTED",
                         "BOUNDS_REJECTED", "BUDGET_REJECTED")  # the codes of `validate_benchmark_gate`
_NO_DETAIL = ("",)
_PRE, _OVERLAID, _RAN = COMPARE_STAGES
_TRACE_MISMATCH_KINDS = tuple(kind for kind in TRACE_FAILURE_KINDS if kind not in _KIND_SUFFIX and kind not in ("unavailable", "harness"))

# THE table of what a `compare` result can say: reason -> (result, the stages it can end at, the details it can carry; `""` is "no detail").
# `COMPARE_RESULT_OF_REASON` and `COMPARE_DETAIL_TOKENS` are derived from it and `_result_dict` validates every verdict against it. A detail
# is exactly one of these tokens (nothing produces a detail with numbers). Pinned by an exact-contents test and by the test that every step-ending row agrees with it.
COMPARE_REASONS = {
    "GATE_REJECTED": ("REJECTED", (_PRE,), _GATE_REJECTION_CODES),
    "ISOLATION_REJECTED": ("REJECTED", COMPARE_STAGES, ISOLATION_DETAILS),
    "PROTECTED_PATH_CHANGED": ("REJECTED", (_PRE,), ("PROTECTED_PATH_CHANGED",)),
    "BENCHMARK_AWARE_CODE": ("REJECTED", (_PRE,), ("BENCHMARK_AWARE_CODE",)),
    "DIFF_UNCHECKABLE": ("REJECTED", (_PRE,), ("GIT_OUTPUT_TOO_LARGE", "TREE_TOO_LARGE")),
    "EXPORT_REJECTED": ("REJECTED", COMPARE_STAGES, EXPORT_REFUSAL_CODES + _HOSTILE_TREE_CODES + _READ_BENCHMARK_CODES),
    "OVERLAY_REJECTED": ("REJECTED", (_PRE,), tuple(code for code in OVERLAY_REFUSAL_CODES if code != "BENCHMARK_MODIFIED")),
    "BENCHMARK_MODIFIED": ("REJECTED", (_PRE,), ("BENCHMARK_MODIFIED",)),
    "LINT_REJECTED": ("REJECTED", (_OVERLAID,), VIOLATION_CODES),
    "TRACE_MISMATCH": ("REJECTED", (_RAN,), _TRACE_MISMATCH_KINDS),
    "BASE_NONZERO_EXIT": ("REJECTED", (_RAN,), ("nonzero",)),
    "DIGEST_MISSING": ("REJECTED", (_RAN,), _NO_DETAIL),
    "DIGEST_UNSTABLE": ("REJECTED", (_RAN,), _NO_DETAIL),
    "WORKLOAD_TOO_SHORT": ("REJECTED", (_RAN,), _NO_DETAIL),
    "HEAD_NONZERO_EXIT": ("NOT_IMPROVED", (_RAN,), ("nonzero",)),
    "HEAD_TIMEOUT": ("NOT_IMPROVED", (_RAN,), ("timeout",)),
    "HEAD_OUTPUT_TOO_LARGE": ("NOT_IMPROVED", (_RAN,), ("oversize",)),
    "DIGEST_MISMATCH": ("NOT_IMPROVED", (_RAN,), _NO_DETAIL),
    "BELOW_HALF_THRESHOLD": ("NOT_IMPROVED", (_RAN,), _NO_DETAIL),
    "UNSUPPORTED_PLATFORM": ("INCONCLUSIVE", (_PRE,), _NO_DETAIL),
    "HOST_BUSY_START": ("INCONCLUSIVE", (_PRE,), _NO_DETAIL),
    "HOST_BUSY_END": ("INCONCLUSIVE", (_RAN,), _NO_DETAIL),
    "TRACE_UNAVAILABLE": ("INCONCLUSIVE", (_RAN,), ("unavailable",)),
    "BASE_TIMEOUT": ("INCONCLUSIVE", (_RAN,), ("timeout",)),
    "BASE_OUTPUT_TOO_LARGE": ("INCONCLUSIVE", (_RAN,), ("oversize",)),
    "NOISY": ("INCONCLUSIVE", (_RAN,), _NO_DETAIL),
    "INCONSISTENT": ("INCONCLUSIVE", (_RAN,), _NO_DETAIL),
    "BORDERLINE": ("INCONCLUSIVE", (_RAN,), _NO_DETAIL),
    "INVALID_INPUT": ("INCONCLUSIVE", (_RAN,), _NO_DETAIL),
    "IMPROVED_CLEAR": ("IMPROVED", (_RAN,), _NO_DETAIL),
}
# Every reason a `compare` result can carry, and the result it belongs to.
COMPARE_RESULT_OF_REASON = {reason: row[0] for reason, row in COMPARE_REASONS.items()}
# The tokens a result's `detail` can start with: only what really is a detail (not every reason or refusal name). A published vocabulary for the
# Orchestrator and C4e (tests and the spec pin it); no production code reads it back.
COMPARE_DETAIL_TOKENS = tuple(dict.fromkeys(token for _, _, details in COMPARE_REASONS.values() for token in details if token))

# THE retry rule, machine-readable (spec 2.3, "Retry on the same exports"): the `(reason, stage, detail)` triples of a `compare` result for
# which a second `compare` on the SAME exports (always with a new `out_path`) can give another outcome. There are two sets because they are
# retried by different actors: a busy host is waited out AUTOMATICALLY; a writable interpreter is retried ONLY after a human has set
# `--allow-writable-interpreter` (never automatically). Nothing else is retryable on the same exports: every other outcome is a function of the
# exports, the venvs and their pins (all minted once, before the install), so only fresh provisioning can change it.
COMPARE_RETRYABLE_AUTOMATIC = frozenset({
    ("HOST_BUSY_START", _PRE, ""),
})
COMPARE_RETRYABLE_WITH_HUMAN_FLAG = frozenset({
    ("ISOLATION_REJECTED", _PRE, "INTERPRETER_WRITABLE"),
})


def _detail_allowed(detail: object, allowed: tuple[str, ...]) -> bool:
    """``detail`` is ``""`` (when the reason allows no detail) or exactly one token of ``allowed``. No producer builds a detail with numbers
    after the token (the kinds and codes are bare words), so none is accepted: a detail that carries text can only be a harness bug."""
    return isinstance(detail, str) and detail in allowed


COMPARE_SCHEMA = "software-builder-bench-compare-v1"
COMPARE_RESULT_KEYS = (
    "schema", "result", "reason", "detail", "kind", "stage", "trace_mismatch_seen", "trace_fault", "untrusted_text", "benchmark_origin",
    "improvement", "ratios", "mad_over_median", "n", "repeats", "min_improvement", "max_noise", "base_median_ns", "head_median_ns", "base_ns",
    "head_ns", "order", "order_salt", "digest", "base_commit", "head_commit", "benchmark_sha256", "gate_sha256", "harness_sha256", "argv",
    "trace", "python", "interpreter_home", "interpreter_writable", "loadavg", "cpu_count", "host_check", "attempt", "side", "phase", "partial",
)
_VERDICT_OWNED_KEYS = frozenset({"schema", "result", "reason", "detail", "kind", "stage"})
# Defence in depth: the closed value sets of the short string fields (`detail` has its own table). None is allowed for each.
_ENUM_FIELDS = {
    "kind": frozenset(TRACE_FAILURE_KINDS),
    "trace_fault": frozenset({"base", "head"}),
    "side": frozenset({"base", "head"}),
    "phase": frozenset({"warmup", "timed", "trace"}),
    "host_check": frozenset({"skipped_probe_failed", "start_only", "checked", "end_skipped_few_cpus"}),
    "benchmark_origin": frozenset({"PRE_EXISTING", "BUILDER_AUTHORED"}),
}
_UNTRUSTED_TEXT_MAX_ENTRIES = 20
_UNTRUSTED_TEXT_MAX_CHARS = 200


class _WrittenResult(dict):
    """The result dict `_compare_impl` returns (equal to the plain dict, JSON-serialisable as is), carrying ``written_sha256``: what
    ``_write_result`` returned for the bytes it wrote. The CLI prints the RESULT line from this object and never re-reads the file (a
    same-user process could rewrite the file in place after the write: spec 2.9). ``None`` until a write happened: the CLI treats anything
    but 64 lowercase hex characters as a failure (exit 2)."""
    written_sha256: str | None = None


class _Verdict(Exception):
    """The internal end of a `compare` step: a result, not an error. Raised through the pipeline and caught by ``_compare_impl``, which adds
    the common fields. Subclasses ``Exception`` only, so a ``BaseException`` (a signal) is never mistaken for a verdict. ``extra`` carries
    result keys the step knows (``untrusted_text``, ``benchmark_origin``, ``ratios``, ...)."""

    def __init__(self, result: str, reason: str, detail: str = "", *, kind: str | None = None, stage: str,
                 extra: dict | None = None) -> None:
        super().__init__(reason)
        self.result, self.reason, self.detail, self.kind, self.stage = result, reason, detail, kind, stage
        self.extra = dict(extra) if extra else {}


def _jsonable(value):
    """Plain JSON data for a result value: Fractions become floats, tuples lists; anything else unexpected is a harness bug."""
    if isinstance(value, Fraction):
        return float(value)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        return {key: _jsonable(item) for key, item in value.items()}
    raise ValueError(f"not a JSON value: {type(value).__name__}")


def _result_dict(verdict: _Verdict, common: dict) -> dict:
    """The 2.8 result: every key present, ``None`` for not applicable. ``common`` holds the fields every result has (commits, hashes,
    attempt, ...); the verdict's ``extra`` overrides it. Attacker-influenced strings are escaped HERE, once: ``untrusted_text`` entries
    (at most 20, each capped), ``detail``, ``python`` and ``interpreter_home``. Raises ``ValueError`` for an inconsistent verdict or an
    unknown key (a harness bug, never PR content)."""
    row = COMPARE_REASONS.get(verdict.reason)
    if row is None or row[0] != verdict.result:
        raise ValueError("verdict result does not belong to its reason")
    if verdict.stage not in row[1]:
        raise ValueError("verdict stage is not one its reason can end at")
    if not _detail_allowed(verdict.detail, row[2]):
        raise ValueError("verdict detail is not in the closed set of its reason")
    fields: dict = {}
    for source in (common, verdict.extra):
        if any(key not in COMPARE_RESULT_KEYS or key in _VERDICT_OWNED_KEYS for key in source):
            raise ValueError("unknown or verdict-owned result key")
        fields.update(source)
    texts = fields.pop("untrusted_text", None) or []
    result = dict.fromkeys(COMPARE_RESULT_KEYS)
    result.update(fields)
    result.update(kind=verdict.kind)
    for key, allowed in _ENUM_FIELDS.items():
        if result[key] is not None and not (type(result[key]) is str and result[key] in allowed):
            raise ValueError(f"{key} is not in its closed set")
    result.update(schema=COMPARE_SCHEMA, result=verdict.result, reason=verdict.reason, kind=verdict.kind, stage=verdict.stage,
                  detail=escape_diagnostic(verdict.detail, _UNTRUSTED_TEXT_MAX_CHARS))
    result["untrusted_text"] = [escape_diagnostic(text, _UNTRUSTED_TEXT_MAX_CHARS) for text in list(texts)[:_UNTRUSTED_TEXT_MAX_ENTRIES]]
    for key in ("python", "interpreter_home"):
        if result[key] is not None:
            result[key] = escape_diagnostic(result[key], 200)
    return _jsonable(result)


def _result_bytes(result: dict) -> bytes:
    """The bytes of the result file: ASCII JSON (``ensure_ascii``), no NaN/Infinity, one trailing newline."""
    return (json.dumps(result, ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


_OUT_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", re.ASCII)


def _validate_out_path(out_path: object, forbidden: object) -> tuple[tuple[int, int], str]:
    """Step 1: ``out_path`` is an absolute, normalized path with a plain file name, in an existing real directory owned by this user and not
    group/other writable; nothing exists at it (``lexists``); and it is not under (by ``realpath``) any ``forbidden`` path (roots, bins,
    venvs, snapshots, the dispatch root). Returns ``((st_dev, st_ino) of the directory, file name)``. ``MEASURE_ARGS_INVALID`` otherwise."""
    def bad(why: str) -> BenchmarkGateError:
        return BenchmarkGateError("MEASURE_ARGS_INVALID", f"out_path: {why}")

    if not isinstance(out_path, str) or not out_path or "\0" in out_path or not os.path.isabs(out_path):
        raise bad("not an absolute path")
    if posixpath.normpath(out_path) != out_path:
        raise bad("not normalized")
    directory, name = os.path.split(out_path)
    if _OUT_NAME_RE.fullmatch(name) is None or name in (".", ".."):
        raise bad("not a plain file name")
    try:
        info = os.lstat(directory)  # lstat: a symlinked directory is refused (the writer opens it with O_NOFOLLOW)
        real_directory = os.path.realpath(directory)
        exists = os.path.lexists(out_path)
        real_forbidden = [os.path.realpath(path) for path in forbidden]
    except (OSError, ValueError, TypeError) as exc:
        raise bad(f"{type(exc).__name__}") from exc
    if not stat.S_ISDIR(info.st_mode):
        raise bad("directory missing or a symlink")
    if info.st_uid != os.getuid() or info.st_mode & 0o022:
        raise bad("directory not owned by the user or writable by others")
    if exists:
        raise bad("already exists")
    target = os.path.join(real_directory, name)
    if any(_inside(target, path) for path in real_forbidden):
        raise bad("under a harness-owned path")
    return (info.st_dev, info.st_ino), name


# follow_symlinks=False: linkat without AT_SYMLINK_FOLLOW (a symlink planted as the temp name is never followed); supported on Linux and macOS
_LINK_NO_FOLLOW = {"follow_symlinks": False} if os.link in os.supports_follow_symlinks else {}


def _write_result(out_path: str, dir_ident: tuple[int, int], name: str, data: bytes) -> str:
    """Write ``data`` to ``out_path`` exclusively and return its sha256. The directory is opened ``O_DIRECTORY|O_NOFOLLOW`` and must be the
    one recorded at validation; a random-named temp is written through that descriptor and hard-linked to ``name`` (``link`` fails if the
    name exists, ``replace`` would not); the temp is unlinked in a ``finally``; the final ``lstat`` of ``out_path`` must be the written
    inode. A child that plants the name or swaps the directory turns the verdict into an error (``MEASURE_FAILED``), never into a
    different file."""
    def fault(why: str) -> BenchmarkGateError:
        return BenchmarkGateError("MEASURE_FAILED", f"result write: {why}")

    directory = os.path.dirname(out_path)
    temp = ".bench-result-" + os.urandom(8).hex() + ".tmp"
    dir_fd = -1
    temp_made = False
    try:
        dir_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        info = os.fstat(dir_fd)
        if (info.st_dev, info.st_ino) != tuple(dir_ident):
            raise fault("the directory was replaced")
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dir_fd)
        temp_made = True
        try:
            written = os.fstat(fd)
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.link(temp, name, src_dir_fd=dir_fd, dst_dir_fd=dir_fd, **_LINK_NO_FOLLOW)
        final = os.stat(out_path, follow_symlinks=False)
        if (final.st_dev, final.st_ino) != (written.st_dev, written.st_ino):
            raise fault("the file is not the one written")
    except BenchmarkGateError:
        raise
    except OSError as exc:
        raise fault(f"{type(exc).__name__}: {exc}") from exc
    finally:
        if temp_made:
            try:
                os.unlink(temp, dir_fd=dir_fd)
            except OSError:
                pass
        if dir_fd >= 0:
            os.close(dir_fd)
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# C4d-3 compare: steps 1 to 6 (arguments, gate, ancestry, isolation, diff checks, host load) and the `compare` entry points
# ---------------------------------------------------------------------------

_SHA256_RE = re.compile(r"[0-9a-f]{64}", re.ASCII)
_SALT_RE = re.compile(r"[0-9a-f]{1,64}", re.ASCII)

class _Run:
    """The bookkeeping of one `compare` call, shared by its step functions: ``common`` holds the result fields known so far (each step adds
    what it learned, so a verdict raised later carries it) and ``out`` the validated ``(directory identity, file name)`` of ``out_path``."""

    def __init__(self) -> None:
        self.common: dict = {}
        self.out: tuple[tuple[int, int], str] | None = None


class _Checked(NamedTuple):
    """What steps 1 to 6 learned and the later steps use."""
    gate: dict          # the normalized gate
    target: str
    order_salt: str
    attempt: int
    base_pin: InterpreterPin
    head_pin: InterpreterPin
    load: tuple | None  # the start `(load1, cpu_count)`, None when the probe failed
    roots: tuple[str, str]  # the resolved base and head export roots (`_export_root`), computed once at step 4


def _default_load_probe() -> tuple[float, int]:
    """`(1-minute load average, usable CPU count)` of this host."""
    load1 = os.getloadavg()[0]
    try:
        cpus = len(os.sched_getaffinity(0))  # type: ignore[attr-defined]  # Linux only
    except AttributeError:
        cpus = os.cpu_count() or 1
    return load1, cpus


def _arg_error(why: str) -> BenchmarkGateError:
    return BenchmarkGateError("MEASURE_ARGS_INVALID", why)


def _check_side_argument(side: object, label: str) -> None:
    """A `Side` of the right type whose strings have the right shape; nothing is looked at on disk."""
    if type(side) is not Side:
        raise _arg_error(f"{label} must be a Side")
    for name in ("root", "bin_dir", "snapshot"):
        value = getattr(side, name)
        if type(value) is not str or not value or "\0" in value or not os.path.isabs(value):
            raise _arg_error(f"{label}.{name} must be an absolute path")
    if type(side.commit) is not str:
        raise _arg_error(f"{label}.commit must be a string")
    for name in ("snapshot_sha256", "interpreter_sha256"):
        value = getattr(side, name)
        if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
            raise _arg_error(f"{label}.{name} must be 64 lowercase hex characters")


def _interpreter_seam(interpreter_of: Callable[[str], InterpreterPin] | None, roots: tuple[str, str]) -> Callable[[str], InterpreterPin]:
    """The function that pins one side's interpreter: the test seam when given, else `interpreter_pin` told to stay outside the two exports."""
    return interpreter_of or (lambda bin_dir: interpreter_pin(bin_dir, outside=roots))


# The three interpreter/venv error maps differ on purpose, so they are NOT one function: `_pin_error` (steps 4 and 9) classifies why a pin could
# not be MADE (`INTERPRETER_DIFFERS` vs `NOT_PROVISIONED`); `_check_venvs`/`_check_parity` map their own codes and read the stage (an over-budget tree
# is `NOT_PROVISIONED` at step 4 but `VENV_CHANGED` later); step 12 maps every failure of an interpreter that pinned fine at step 9 to
# `INTERPRETER_CHANGED` (it changed), and `VENV_NOT_ISOLATED` to `VENV_CHANGED`.
def _pin_error(exc: BenchmarkGateError, which: str, stage: str = _PRE) -> _Verdict:
    """The interpreter helper's errors as an ISOLATION_REJECTED verdict (spec 2.1: `VENV_NOT_ISOLATED` is `INTERPRETER_DIFFERS`, the size, stdlib
    and I/O errors are `NOT_PROVISIONED`); any other code is re-raised."""
    if exc.code == "VENV_NOT_ISOLATED":
        detail = "INTERPRETER_DIFFERS"
    elif exc.code in ("TREE_TOO_LARGE", "DEST_REJECTED", "TREE_UNREADABLE"):
        detail = "NOT_PROVISIONED"
    else:
        raise exc
    return _Verdict("REJECTED", "ISOLATION_REJECTED", detail, stage=stage, extra={"untrusted_text": [f"{which}: {exc.detail or exc.code}"]})


def _isolation(detail: str, texts: list | tuple = (), stage: str = _PRE) -> _Verdict:
    return _Verdict("REJECTED", "ISOLATION_REJECTED", detail, stage=stage, extra={"untrusted_text": [str(t) for t in texts]})


def _host_load(load_probe: Callable[[], tuple]) -> tuple | None:
    """The start probe's `(load1, cpu_count)`, or None when it raised or returned anything but a finite non-negative real and a positive int."""
    try:
        load1, cpus = load_probe()
    except Exception:  # noqa: BLE001 - a failing probe skips the host checks, whatever it raised
        return None
    if isinstance(load1, bool) or not isinstance(load1, (int, float, Fraction)) or not math.isfinite(load1) or load1 < 0:
        return None
    if type(cpus) is not int or cpus <= 0:
        return None
    return load1, cpus


def _check_snapshots(base: Side, head: Side, stage: str) -> None:
    """Each side's snapshot file must hash to its pin (`SNAPSHOT_CHANGED`); steps 4 and 9 (and 12) share this."""
    for label, side in (("base", base), ("head", head)):
        try:
            data = _read_bounded(side.snapshot, _VENV_MAX_SNAPSHOT_BYTES, nofollow=True)
        except (OSError, ValueError) as exc:
            raise BenchmarkGateError("VENV_SNAPSHOT_INVALID", f"{label} snapshot unreadable: {_describe(exc)}") from exc
        if len(data) > _VENV_MAX_SNAPSHOT_BYTES or hashlib.sha256(data).hexdigest() != side.snapshot_sha256:
            raise _isolation("SNAPSHOT_CHANGED", [label], stage)


def _check_venvs(base: Side, head: Side, roots: tuple[str, str], stage: str) -> list:
    """`check_venv` per side (its errors mapped) and the two venv roots distinct; returns the real venv roots. A size error
    (`TREE_TOO_LARGE`) is `NOT_PROVISIONED` at step 4 (the same word as the interpreter helper's and `dependency_parity`'s over-budget) and
    `VENV_CHANGED` at steps 9 and 12 (the venv was within the limit before)."""
    real_venvs = []
    for label, side, root, other in (("base", base, roots[0], roots[1]), ("head", head, roots[1], roots[0])):
        try:
            real_venvs.append(check_venv(side.bin_dir, side.snapshot, root, (other,)))
        except BenchmarkGateError as exc:
            if exc.code in ("VENV_NOT_ISOLATED", "VENV_HOOK_REJECTED"):
                detail = exc.code
            elif exc.code in ("TREE_UNREADABLE", "DEST_REJECTED"):
                detail = "VENV_NOT_ISOLATED"
            elif exc.code == "TREE_TOO_LARGE":  # more hook candidates than the limit (spec 2.1): a verdict about the venv, never a raise
                detail = "NOT_PROVISIONED" if stage == _PRE else "VENV_CHANGED"  # step 4: over budget from the start; later: it grew since step 4
            else:
                raise
            hits = [f"{label}: {h.get('path')} ({h.get('reason')})" for h in exc.hits] or [f"{label}: {exc.detail or exc.code}"]
            raise _isolation(detail, hits, stage) from exc
    if real_venvs[0] == real_venvs[1]:
        raise _isolation("VENV_NOT_ISOLATED", ["the two sides share one venv"], stage)
    return real_venvs


def _check_parity(base: Side, head: Side, roots: tuple[str, str], stage: str) -> None:
    """`dependency_parity` with its errors and findings mapped."""
    try:
        findings = dependency_parity(base.bin_dir, head.bin_dir, roots[0], roots[1])
    except BenchmarkGateError as exc:
        if exc.code == "TREE_TOO_LARGE":
            raise _isolation("NOT_PROVISIONED", [exc.detail or exc.code], stage) from exc
        if exc.code in ("VENV_NOT_ISOLATED", "TREE_UNREADABLE"):
            raise _isolation("VENV_NOT_ISOLATED", [exc.detail or exc.code], stage) from exc
        raise
    if findings:
        raise _isolation(findings[0][0], [text for _, text in findings], stage)


def _check_exports(repo: object, sides: tuple[Side, Side], roots: tuple[str, str], allows: tuple[dict, dict], stage: str) -> None:
    """`verify_export_against_commit` per side (base first) with that side's allowance; hostile-tree errors are `EXPORT_REJECTED`."""
    for label, side, root, allow in zip(("base", "head"), sides, roots, allows):
        try:
            found = verify_export_against_commit(repo, side.commit, root, allow=allow) if allow else verify_export_against_commit(repo, side.commit, root)
        except BenchmarkGateError as exc:
            if exc.code.startswith("EXPORT_") or exc.code in _HOSTILE_TREE_CODES:
                raise _Verdict("REJECTED", "EXPORT_REJECTED", exc.code, stage=stage,
                               extra={"untrusted_text": [f"{label}: {exc.detail or exc.code}"]}) from exc
            raise
        if found:
            raise _isolation(found[0][0], [f"{label}: {rel}" for _, rel in found], stage)


def _compare_checks(gate: object, repo: object, base: Side, head: Side, *, attempt: object, out_path: object, allow_writable_interpreter: bool,
                    load_probe: Callable[[], tuple] | None, order_salt: object, interpreter_of: Callable[[str], InterpreterPin] | None,
                    run: _Run) -> _Checked:
    """Steps 1 to 6 of the pipeline. Returns what they learned, raises `_Verdict` for a result and `BenchmarkGateError` for a caller or
    harness fault. Nothing here starts a BENCHMARK child, seals an export or writes inside one. It does run the interpreter probe (``python -I -S``,
    `_startup_probe`, up to ~20 s each) which IS a child (steps 4, 9 and 12), before the sealed runs; the wait floor counts it."""
    # 1: every argument is validated before anything is touched
    _check_side_argument(base, "base")
    _check_side_argument(head, "head")
    if type(attempt) is not int or attempt not in (1, 2):
        raise _arg_error("attempt must be 1 or 2")
    if type(allow_writable_interpreter) is not bool:
        raise _arg_error("allow_writable_interpreter must be a bool")
    if order_salt is not None and (type(order_salt) is not str or _SALT_RE.fullmatch(order_salt) is None):
        raise _arg_error("order_salt must be 1 to 64 lowercase hex characters")
    _check_commits(base.commit, head.commit)
    dispatch = os.path.dirname(os.path.abspath(base.root))
    run.out = _validate_out_path(out_path, [base.root, head.root, dispatch, *(
        path for side in (base, head) for path in (side.bin_dir, os.path.dirname(os.path.abspath(side.bin_dir)), side.snapshot))])
    salt = os.urandom(8).hex() if order_salt is None else order_salt
    common = run.common
    common.update(base_commit=base.commit, head_commit=head.commit, attempt=attempt, order_salt=salt)
    if os.name != "posix":
        raise _Verdict("INCONCLUSIVE", "UNSUPPORTED_PLATFORM", stage=_PRE)
    # 2: the gate (the harness hash is taken now: every later result names the code that produced it)
    common["harness_sha256"] = harness_sha256()
    normalized, code = validate_benchmark_gate(gate)
    if normalized is None:
        raise _Verdict("REJECTED", "GATE_REJECTED", code, stage=_PRE)
    target = benchmark_target(normalized)
    common.update(gate_sha256=gate_sha256(normalized), repeats=normalized["repeats"], min_improvement=normalized["min_improvement"],
                  max_noise=normalized["max_noise"])
    # 3: ancestry is a caller error, not a verdict
    if not is_ancestor(repo, base.commit, head.commit):
        raise BenchmarkGateError("BASE_NOT_ANCESTOR", "the base commit is not an ancestor of the head commit")
    # 4: isolation, no child yet, in the order of the spec
    roots = (_export_root(base.root, "base root"), _export_root(head.root, "head root"))
    if roots[0] == roots[1] or os.path.dirname(roots[0]) != os.path.dirname(roots[1]):
        raise BenchmarkGateError("DEST_REJECTED", "the two roots must be distinct siblings of one dispatch root")
    for side, root in zip((base, head), roots):
        if export_commit(root) != side.commit:
            raise BenchmarkGateError("OVERLAY_COMMIT_MISMATCH", "an export is not at the commit it was given")
    for label, root in zip(("base", "head"), roots):
        if os.path.lexists(os.path.join(root, ".git")):
            raise _isolation("ROOT_HAS_GIT", [label])
    bins = [os.path.realpath(base.bin_dir), os.path.realpath(head.bin_dir)]
    if bins[0] == bins[1] or any(_inside(path, root) or _inside(root, path) for path in bins for root in map(os.path.realpath, roots)):
        raise _isolation("BIN_NOT_ISOLATED")
    seam = _interpreter_seam(interpreter_of, roots)
    pins = []
    for label, side in (("base", base), ("head", head)):
        if not os.path.exists(os.path.join(side.bin_dir, "python")):
            raise _isolation("NOT_PROVISIONED", [f"{label}: no bin/python"])
        try:
            pins.append(seam(side.bin_dir))
        except BenchmarkGateError as exc:
            raise _pin_error(exc, label) from exc
    if pins[0].real_python != pins[1].real_python:
        raise _isolation("INTERPRETER_DIFFERS", ["the sides resolve to different interpreters"])
    real_python = os.path.realpath(pins[0].real_python)
    venvs = [os.path.realpath(os.path.dirname(os.path.abspath(side.bin_dir))) for side in (base, head)]
    if any(_inside(real_python, path) for path in (*venvs, *map(os.path.realpath, roots))):
        raise _isolation("INTERPRETER_DIFFERS", ["the interpreter lies inside a venv or an export"])
    writable = bool(pins[0].writable or pins[1].writable)
    common.update(python=pins[0].real_python, interpreter_home=os.path.dirname(os.path.dirname(pins[0].real_python)), interpreter_writable=writable)
    for label, side, pin in (("base", base, pins[0]), ("head", head, pins[1])):
        if pin.sha256 != side.interpreter_sha256:
            raise _isolation("INTERPRETER_CHANGED", [label])
    if writable and not allow_writable_interpreter:
        raise _isolation("INTERPRETER_WRITABLE")
    here = os.path.realpath(__file__)
    if any(_inside(here, path) for path in map(os.path.realpath, roots)):
        raise _isolation("HARNESS_FILE_UNDER_ROOT")
    _check_snapshots(base, head, _PRE)
    _check_venvs(base, head, roots, _PRE)
    _check_parity(base, head, roots, _PRE)
    _check_exports(repo, (base, head), roots, ({}, {}), _PRE)
    # 5: the diff checks
    try:
        diff_checks(repo, base.commit, head.commit, normalized["benchmark_paths"][0])
    except BenchmarkGateError as exc:
        if exc.code in DIFF_REFUSAL_CODES:
            raise _Verdict("REJECTED", exc.code, exc.code, stage=_PRE,
                           extra={"untrusted_text": [" | ".join(str(v) for v in hit.values()) for hit in exc.hits]}) from exc
        if exc.code in COMPARE_REASONS["DIFF_UNCHECKABLE"][2]:
            raise _Verdict("REJECTED", "DIFF_UNCHECKABLE", exc.code, stage=_PRE) from exc
        raise
    # 6: the host must be quiet before anything is sealed (the end check is step 13's)
    load = _host_load(load_probe or _default_load_probe)
    if load is None:
        common.update(host_check="skipped_probe_failed", loadavg={"start": None, "end": None}, cpu_count={"start": None, "end": None})
    else:
        common.update(host_check="start_only", loadavg={"start": float(load[0]), "end": None}, cpu_count={"start": load[1], "end": None})
        if Fraction(str(load[0])) * 10 > 7 * load[1]:
            raise _Verdict("INCONCLUSIVE", "HOST_BUSY_START", stage=_PRE)
    return _Checked(normalized, target, salt, attempt, pins[0], pins[1], load, roots)


class _Baseline(NamedTuple):
    """The step-9 fingerprints (spec 2.5), taken immediately before the first child and compared by step 12. Index 0 is the base, 1 the head."""
    exports: tuple[str, str]               # `fingerprint_tree` of each export (`_MAX_TREE_ENTRIES`)
    venvs: tuple[str, str]                 # `fingerprint_tree` of each venv root (`_VENV_FINGERPRINT_LIMIT`)
    snapshots: tuple[tuple, tuple]         # a stat record of each snapshot file
    dispatch: tuple[tuple, tuple]          # (sorted names of the dispatch root, ((".", (dev, ino, ctime_ns)) for the root itself, then (name, (dev, ino, size, ctime_ns)) for every non-export entry))
    cfg_sha256: tuple[str, str]            # sha256 of each venv's `pyvenv.cfg`
    real_python: tuple[str, str]           # the interpreter each side resolved to at step 4
    bins: tuple[str, str]                  # the resolved `bin_dir` of each side (what the children run, passed on instead of resolving again)
    identities: tuple                      # `(resolved path, st_dev, st_ino, label, ctime_ns or None)` of the dispatch root, both exports, both bin dirs, both venv roots (ctime only for the roots the harness never modifies after sealing)


class _Prepared(NamedTuple):
    """What steps 7 to 9 learned and the run steps use."""
    gate: dict              # the normalized gate
    target: str
    benchmark: str          # the benchmark path (relative, as in the gate)
    origin: str             # `PRE_EXISTING` or `BUILDER_AUTHORED`, derived from the base commit, not from the overlay's return value
    benchmark_sha256: str
    h0: tuple[str, str]     # `hash_export` of the base and the head export just after the seal
    roots: tuple[str, str]
    baseline: _Baseline


def _benchmark_origin(repo: object, base_commit: str, path: str) -> str:
    """`PRE_EXISTING` when the base COMMIT lists `path`, else `BUILDER_AUTHORED`: read from git, never from the exports (the overlay's own
    return value reads the installed base export, which a build step could have written to)."""
    length = _check_commits(base_commit)
    with _PrivateGit(repo, length) as git:
        git.require_commit(base_commit)
        raw = git.run("ls-tree", "-z", "--full-tree", base_commit, "--", path)
    return "PRE_EXISTING" if any(record.partition(b"\t")[2] == path.encode() for record in raw.split(b"\0")) else "BUILDER_AUTHORED"


def _export_rejected(exc: BenchmarkGateError, label: str, stage: str) -> _Verdict:
    return _Verdict("REJECTED", "EXPORT_REJECTED", exc.code, stage=stage, extra={"untrusted_text": [f"{label}: {exc.detail or exc.code}"]})


def _compare_prepare(repo: object, base: Side, head: Side, checked: _Checked, *, interpreter_of: Callable[[str], InterpreterPin] | None,
                     run: _Run) -> _Prepared:
    """Steps 7 to 9. Raises `_Verdict` for a result and `BenchmarkGateError` for a caller or harness fault. Stage `pre_overlay` until the
    overlay has succeeded, `overlaid` after. Nothing here starts a child; at the end both exports are sealed and hashed."""
    common = run.common
    roots = checked.roots
    benchmark = checked.gate["benchmark_paths"][0]
    # 7: the lint's import allowlist is read BEFORE the overlay and after the install; then the overlay itself
    try:
        top = repo_top_levels(roots[0])
        overlay_benchmark_file(roots[0], roots[1], base.commit, benchmark, head_ref_commit=head.commit)
    except BenchmarkGateError as exc:
        if exc.code == "BENCHMARK_MODIFIED":
            raise _Verdict("REJECTED", "BENCHMARK_MODIFIED", exc.code, stage=_PRE) from exc
        if exc.code in COMPARE_REASONS["OVERLAY_REJECTED"][2]:  # every other `OVERLAY_REFUSAL_CODES` member (a new one must not raise here)
            raise _Verdict("REJECTED", "OVERLAY_REJECTED", exc.code, stage=_PRE, extra={"untrusted_text": [exc.detail or exc.code]}) from exc
        if exc.code in _HOSTILE_TREE_CODES:
            raise _export_rejected(exc, "base", _PRE) from exc
        raise
    # the file exists in the base from here: a retry needs fresh exports
    # the overlay's return value is not authoritative (a build step could have written the file); the base commit decides, and an
    # installed-but-untracked file is then allowed only by its sha256 at step 9
    origin = _benchmark_origin(repo, base.commit, benchmark)
    common["benchmark_origin"] = origin
    stage = _OVERLAID
    # 8: seal, read, compare, hash, lint, hash, re-read
    try:
        seal_export(roots[0])
        seal_export(roots[1])
        data = [read_benchmark(root, benchmark) for root in roots]
    except BenchmarkGateError as exc:
        if exc.code in _HOSTILE_TREE_CODES or exc.code in _READ_BENCHMARK_CODES:
            raise _export_rejected(exc, "export", stage) from exc
        raise
    if data[0] != data[1]:
        raise _isolation("BENCHMARK_BYTES_DIFFER", [benchmark], stage)
    benchmark_sha = hashlib.sha256(data[0]).hexdigest()
    common["benchmark_sha256"] = benchmark_sha
    violations = validate_benchmark_content(data[0], checked.gate["benchmark_symbol"], top)
    if violations:
        raise _Verdict("REJECTED", "LINT_REJECTED", violations[0], stage=stage, extra={"untrusted_text": list(violations)})
    try:
        h0 = (hash_export(roots[0]), hash_export(roots[1]))
        again = [hashlib.sha256(read_benchmark(root, benchmark)).hexdigest() for root in roots]
    except BenchmarkGateError as exc:
        if exc.code in _HOSTILE_TREE_CODES or exc.code in _READ_BENCHMARK_CODES:
            raise _export_rejected(exc, "export", stage) from exc
        raise
    if again != [benchmark_sha, benchmark_sha]:
        raise _isolation("EXPORT_CHANGED", [benchmark], stage)
    # 9: immediately before the first child, the step 4 checks again, with the overlay allowance on the base only
    _check_snapshots(base, head, stage)
    _check_venvs(base, head, roots, stage)
    seam = _interpreter_seam(interpreter_of, roots)
    for label, side, before in (("base", base, checked.base_pin), ("head", head, checked.head_pin)):
        try:
            pin = seam(side.bin_dir)
        except BenchmarkGateError as exc:
            raise _pin_error(exc, label, stage) from exc
        if pin.sha256 != side.interpreter_sha256 or pin.real_python != before.real_python:
            raise _isolation("INTERPRETER_CHANGED", [label], stage)
    _check_parity(base, head, roots, stage)
    _check_exports(repo, (base, head), roots, ({benchmark: benchmark_sha} if origin == "BUILDER_AUTHORED" else {}, {}), stage)
    baseline = _baseline_fingerprints(base, head, roots, (checked.base_pin.real_python, checked.head_pin.real_python), stage)
    return _Prepared(checked.gate, checked.target, benchmark, origin, benchmark_sha, h0, roots, baseline)


def _stat_record(path: str) -> tuple:
    """`lstat` of a file as the tuple the baseline compares (`ctime` cannot be set by a user, so a restore still shows)."""
    st = os.lstat(path)
    return (st.st_dev, st.st_ino, st.st_mode, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _fingerprint_or_verdict(path: str, limit: int, fallback: str, label: str, stage: str) -> str:
    """`fingerprint_tree` with its errors as `ISOLATION_REJECTED`: over the limit is `FINGERPRINT_FAILED` (the Builder cannot fix it), any
    other fault is `fallback`. The module-level limits are read by the caller at call time."""
    try:
        return fingerprint_tree(path, limit=limit)
    except BenchmarkGateError as exc:
        detail = "FINGERPRINT_FAILED" if exc.code == "TREE_TOO_LARGE" else fallback
        raise _isolation(detail, [f"{label}: {exc.detail or exc.code}"], stage) from exc


def _dispatch_state(roots: tuple[str, str], fallback: str, stage: str) -> tuple:
    """The dispatch root's sorted name list and every entry that is not one of the two exports as `(dev, ino, size, ctime_ns)` (and the
    root itself, as `"."`: `(dev, ino, ctime_ns)`), so a swapped sidecar, marker or sibling, or a renamed-and-restored dispatch root, shows (the exports are covered by their own fingerprint)."""
    dispatch = os.path.dirname(roots[0])
    export_names = {os.path.basename(root) for root in roots}
    try:
        names = []
        with os.scandir(dispatch) as listing:  # bounded: a hostile run could fill the dispatch root with entries
            for entry in listing:
                names.append(entry.name)
                if len(names) > _MAX_TREE_ENTRIES:
                    raise _isolation("FINGERPRINT_FAILED", ["dispatch root: too many entries"], stage)
        names.sort()
        own = os.lstat(dispatch)  # the dispatch root itself: a rename-and-restore of it moves its ctime
        entries = [(".", (own.st_dev, own.st_ino, own.st_ctime_ns))]
        for name in names:
            if name not in export_names:
                st = os.lstat(os.path.join(dispatch, name))
                entries.append((name, (st.st_dev, st.st_ino, st.st_size, st.st_ctime_ns)))
    except OSError as exc:
        raise _isolation(fallback, [f"dispatch root: {_describe(exc)}"], stage) from exc
    return tuple(names), tuple(entries)


def _cfg_sha256(side: Side, label: str, stage: str) -> str:
    cfg = os.path.join(os.path.dirname(os.path.abspath(side.bin_dir)), "pyvenv.cfg")
    try:
        return hashlib.sha256(_read_bounded(cfg, _MAX_INPUT_BYTES, nofollow=True)).hexdigest()
    except (OSError, ValueError) as exc:
        raise _isolation("VENV_CHANGED", [f"{label}: pyvenv.cfg unreadable: {_describe(exc)}"], stage) from exc


def _venv_roots(base: Side, head: Side) -> tuple[str, str]:
    return tuple(os.path.dirname(os.path.abspath(side.bin_dir)) for side in (base, head))  # type: ignore[return-value]


def _snapshot_records(base: Side, head: Side, stage: str) -> tuple[tuple, tuple]:
    try:
        return _stat_record(base.snapshot), _stat_record(head.snapshot)
    except OSError as exc:
        raise _isolation("SNAPSHOT_CHANGED", [_describe(exc)], stage) from exc


def _identity_of(path: str, label: str, stage: str, *, sealed: bool = False) -> tuple[str, int, int, str, int | None]:
    """`(resolved path, st_dev, st_ino, label, st_ctime_ns or None)` of a directory the children run in or from; it must be a real directory
    (not a symlink) whose own path is already resolved, else `ISOLATION_REJECTED`/`HASH_UNREADABLE` (nothing a child could have done yet:
    step 9). The ctime is kept only for `sealed` directories (the two export roots and the dispatch root): the harness never modifies
    those after sealing (their entries are only read), so a rename-and-restore or an entry added or removed moves it. The bin and venv
    roots are NOT sealed: pip, `pyvenv.cfg` readers and the interpreter may legitimately touch them, so they stay `(dev, ino)`."""
    resolved = os.path.realpath(path)
    try:
        st = os.lstat(resolved)
    except OSError as exc:
        raise _isolation("HASH_UNREADABLE", [f"{label}: {_describe(exc)}"], stage) from exc
    if not stat.S_ISDIR(st.st_mode):
        raise _isolation("HASH_UNREADABLE", [f"{label}: not a directory"], stage)
    return resolved, st.st_dev, st.st_ino, label, (st.st_ctime_ns if sealed else None)


def _spawn_guard(identities: tuple) -> Callable[[str, str], None]:
    """The guard `_execute` calls before every child (arguments: the side about to be spawned and the root it will run in): the root must be
    the recorded one (so the path the harness resolved for the spawn is the step-9 path: fail closed), and each recorded directory must still resolve to
    itself (no symlink or renamed ancestor in its path), still be the same inode and, for a sealed directory, still have its recorded ctime.
    A dispatch root swapped for a planted copy (and put back later, inodes and all) shows here at the next spawn, or at step 12 (ctime).
    Raises `_IdentityChanged` (its text starts with the label, so a length cap cannot cut it); `compare` turns it into
    `ISOLATION_REJECTED`/`EXPORT_CHANGED`, stage `ran`."""
    roots = {label: path for path, _dev, _ino, label, _ctime in identities}

    def guard(side: str, root: str) -> None:
        recorded = roots.get(f"{side} root")
        if recorded is not None and root != recorded:
            raise _IdentityChanged(f"{side} root: the child would run in {root}, not the recorded {recorded}", side)
        for path, dev, ino, label, ctime in identities:
            try:
                now = os.lstat(path)
                same = (os.path.realpath(path) == path and (now.st_dev, now.st_ino) == (dev, ino)
                        and (ctime is None or now.st_ctime_ns == ctime))
            except OSError:
                same = False
            if not same:
                raise _IdentityChanged(f"{label}: directory replaced or modified before the {side} spawn: {path}", side)
    return guard


def _baseline_fingerprints(base: Side, head: Side, roots: tuple[str, str], real_python: tuple[str, str], stage: str) -> _Baseline:
    """The end of step 9: fingerprints of both exports, both venvs, both snapshot files, the dispatch root and each `pyvenv.cfg`. Errors are
    `ISOLATION_REJECTED` (`FINGERPRINT_FAILED` over a limit, else the side's own change token)."""
    labels = ("base", "head")
    bins = tuple(os.path.realpath(side.bin_dir) for side in (base, head))
    sealed_labels = ("dispatch root", "base root", "head root")
    identities = tuple(_identity_of(path, label, stage, sealed=label in sealed_labels) for path, label in (
        (os.path.dirname(roots[0]), "dispatch root"), (roots[0], "base root"), (roots[1], "head root"), (bins[0], "base bin"), (bins[1], "head bin"),
        *((root, f"{label} venv") for label, root in zip(labels, _venv_roots(base, head)))))
    exports = tuple(_fingerprint_or_verdict(root, _MAX_TREE_ENTRIES, "HASH_UNREADABLE", label, stage) for label, root in zip(labels, roots))
    venvs = tuple(_fingerprint_or_verdict(root, _VENV_FINGERPRINT_LIMIT, "VENV_CHANGED", label, stage)
                  for label, root in zip(labels, _venv_roots(base, head)))
    return _Baseline(exports, venvs, _snapshot_records(base, head, stage),  # type: ignore[arg-type]
                     _dispatch_state(roots, "HASH_UNREADABLE", stage),
                     tuple(_cfg_sha256(side, label, stage) for label, side in zip(labels, (base, head))), tuple(real_python),  # type: ignore[arg-type]
                     bins, identities)  # type: ignore[arg-type]


def _post_run_check(prepared: _Prepared, repo: object, base: Side, head: Side, *,
                    interpreter_of: Callable[[str], InterpreterPin] | None) -> _Verdict | None:
    """Step 12 (spec 2.5): everything step 9 fixed must still hold. In this order, and the first failure names the detail: snapshot pins
    (`SNAPSHOT_CHANGED`), interpreter pin (`INTERPRETER_CHANGED`), `hash_export` and the export fingerprints and dispatch root
    (`HASH_UNREADABLE`/`EXPORT_CHANGED`), `check_venv` and the venv fingerprints (`VENV_HOOK_REJECTED`/`VENV_CHANGED`), `dependency_parity`,
    `verify_export_against_commit` with the step-9 allowance. Returns the `ISOLATION_REJECTED` (or `EXPORT_REJECTED`, stage `ran`: it beats
    everything below too) verdict, or None. An
    integrity error is a verdict; a git or host fault (`GIT_TIMEOUT`, `GIT_FAILED`, `REPO_UNREADABLE`) raises, as everywhere else."""
    stage = _RAN
    roots, before = prepared.roots, prepared.baseline
    labels = ("base", "head")
    sides = (base, head)
    try:
        # 1: snapshot pins, then the files themselves (a rewritten-and-restored snapshot moves ctime)
        try:
            _check_snapshots(base, head, stage)
        except BenchmarkGateError as exc:
            if exc.code != "VENV_SNAPSHOT_INVALID":
                raise
            raise _isolation("SNAPSHOT_CHANGED", [exc.detail or exc.code], stage) from exc
        if _snapshot_records(base, head, stage) != before.snapshots:
            raise _isolation("SNAPSHOT_CHANGED", ["snapshot file replaced or touched"], stage)
        # 2: the interpreter
        seam = _interpreter_seam(interpreter_of, roots)
        for label, side, real in zip(labels, sides, before.real_python):
            try:
                pin = seam(side.bin_dir)
            except BenchmarkGateError as exc:  # any failure of an interpreter that pinned at step 9 is a change (see the note at `_pin_error`)
                raise _isolation("INTERPRETER_CHANGED", [f"{label}: {exc.detail or exc.code}"], stage) from exc
            if pin.sha256 != side.interpreter_sha256 or pin.real_python != real:
                raise _isolation("INTERPRETER_CHANGED", [label], stage)
        # 3: the exports (content hash, then ctime fingerprints, then the dispatch root)
        try:
            hashes = tuple(hash_export(root) for root in roots)
        except BenchmarkGateError as exc:  # DEST_REJECTED and OVERLAY_FAILED from the root check are integrity errors here
            raise _isolation("HASH_UNREADABLE", [exc.detail or exc.code], stage) from exc
        if hashes != prepared.h0:
            raise _isolation("EXPORT_CHANGED", [label for label, now, then in zip(labels, hashes, prepared.h0) if now != then], stage)
        prints = tuple(_fingerprint_or_verdict(root, _MAX_TREE_ENTRIES, "HASH_UNREADABLE", label, stage) for label, root in zip(labels, roots))
        if prints != before.exports:
            raise _isolation("EXPORT_CHANGED", [label for label, now, then in zip(labels, prints, before.exports) if now != then], stage)
        if _dispatch_state(roots, "HASH_UNREADABLE", stage) != before.dispatch:
            raise _isolation("EXPORT_CHANGED", ["dispatch root"], stage)
        # 4: the venvs (the hook check, then the fingerprints, then pyvenv.cfg)
        try:
            _check_venvs(base, head, roots, stage)
        except _Verdict as verdict:
            if verdict.detail == "VENV_NOT_ISOLATED":  # it was isolated at step 9: it changed
                verdict.detail = "VENV_CHANGED"
            raise
        except BenchmarkGateError as exc:
            if exc.code != "VENV_SNAPSHOT_INVALID":
                raise
            raise _isolation("SNAPSHOT_CHANGED", [exc.detail or exc.code], stage) from exc
        vprints = tuple(_fingerprint_or_verdict(root, _VENV_FINGERPRINT_LIMIT, "VENV_CHANGED", label, stage)
                        for label, root in zip(labels, _venv_roots(base, head)))
        if vprints != before.venvs:
            raise _isolation("VENV_CHANGED", [label for label, now, then in zip(labels, vprints, before.venvs) if now != then], stage)
        cfgs = tuple(_cfg_sha256(side, label, stage) for label, side in zip(labels, sides))
        if cfgs != before.cfg_sha256:
            raise _isolation("VENV_CHANGED", ["pyvenv.cfg"], stage)
        # 5: the dependency inventory, 6: the exports against their commits (the base keeps the step-9 overlay allowance)
        try:
            _check_parity(base, head, roots, stage)
        except _Verdict as verdict:
            if verdict.detail == "VENV_NOT_ISOLATED":  # it was isolated at step 9: it changed (the word `_check_venvs` uses here)
                verdict.detail = "VENV_CHANGED"
            raise
        except BenchmarkGateError as exc:
            if exc.code in _RAISING_CODES:  # a harness invariant or a caller fault is not the Builder's DEPENDENCY_PARITY
                raise
            raise _isolation("DEPENDENCY_PARITY", [exc.detail or exc.code], stage) from exc
        allow = {prepared.benchmark: prepared.benchmark_sha256} if prepared.origin == "BUILDER_AUTHORED" else {}
        _check_exports(repo, (base, head), roots, (allow, {}), stage)
    except _Verdict as verdict:
        return verdict
    return None


# --- steps 10 and 11: the paired runs and the 2.7 mapping -------------------------------------------------------------------------

_TRACE_ARGV_NOTE = "harness-only: temporary ini and plugin directory"
_RAISING_CODES = frozenset({"MEASURE_FAILED", "MEASURE_ARGS_INVALID"})  # T1 and M4: a harness or caller fault, never a verdict
_TRACE_AT_ONCE_KINDS = frozenset(COMPARE_REASONS["TRACE_MISMATCH"][2]) - {"counts_differ"}  # T6 (`counts_differ` is T5: pending)
_RUN_FAILURE_KINDS = frozenset(_KIND_SUFFIX) - {"spawn"}  # T4 (the `_execute` kinds that are not a spawn failure)
# M1, M2, M3: a measure refusal is a verdict under the reason of its own name, except these two (`UNSUPPORTED_PLATFORM`: step 1 handled it;
# `OUTPUT_TOO_LARGE`: split by side, see `_map_measure_error`)
_MEASURE_NOT_A_VERDICT = frozenset({"UNSUPPORTED_PLATFORM", "OUTPUT_TOO_LARGE"})


class _RunOutcome(NamedTuple):
    """What steps 10 and 11 leave for step 13 to merge, after step 12 found nothing."""
    trace: dict | None             # the normalised trace of 2.8, None when no trace result was seen
    pending: _Verdict | None       # the `counts_differ` TRACE_MISMATCH (T5), not yet raised
    measured: dict | None          # `measure_paired`'s return value when it succeeded
    measure_verdict: _Verdict | None  # the mapped INCONCLUSIVE (M3) of a measure refusal; REJECTED/NOT_IMPROVED never get here (item 3 raises)


def _normalise_trace(trace: dict | None) -> dict | None:
    """The 2.8 shape from a `trace_paired` error's ``trace`` (both sides' results) or its success dict; None when there is no result to show."""
    if trace is None:
        return None
    if "interpreter" in trace:  # the success dict: one count and one interpreter for both sides
        sides = {name: {"kind": "lines", "value": trace[name], "interpreter": trace["interpreter"]} for name in ("base", "head")}
    else:
        sides = {name: dict(trace[name]) for name in ("base", "head")}
    return {**sides, "body_has_control_flow": trace["body_has_control_flow"], "argv": trace["argv"], "argv_note": _TRACE_ARGV_NOTE}


def _error_extra(error: BenchmarkGateError) -> dict:
    """The result keys an error of `trace_paired`/`measure_paired` supplies (its text is child-derived: `untrusted_text`)."""
    return {"side": error.side, "phase": error.phase, "partial": error.partial, "untrusted_text": [error.detail or error.code]}


def _map_trace_error(error: BenchmarkGateError) -> _Verdict:
    """Rows T2 to T6 of 2.7 for an error of `trace_paired` (the order: the raising codes, `kind == "spawn"`, the code, the kind). Returns the
    verdict (the caller decides whether `counts_differ`, T5, is pending); anything not in the table, and every harness fault, is re-raised."""
    if error.code in _RAISING_CODES:  # T1
        raise error
    kind, extra = error.kind, _error_extra(error)
    if kind == "spawn":  # T3: the side could not be started (stage `ran` even though no child ran)
        return _Verdict("REJECTED", "ISOLATION_REJECTED", "NOT_PROVISIONED", kind=kind, stage=_RAN, extra=extra)
    if error.code == "TRACE_UNAVAILABLE":  # T2
        return _Verdict("INCONCLUSIVE", "TRACE_UNAVAILABLE", kind or "", kind=kind, stage=_RAN, extra=extra)
    if error.code != "TRACE_MISMATCH":
        raise error
    if kind in _RUN_FAILURE_KINDS and error.side in ("base", "head"):  # T4: by side, with the measure rows
        reason = f"{error.side.upper()}_{_KIND_SUFFIX[kind]}"
        return _Verdict(COMPARE_RESULT_OF_REASON[reason], reason, kind, kind=kind, stage=_RAN, extra={**extra, "trace_fault": error.side})
    if kind == "counts_differ" or kind in _TRACE_AT_ONCE_KINDS:  # T5 (pending, by the caller) and T6
        return _Verdict("REJECTED", "TRACE_MISMATCH", kind, kind=kind, stage=_RAN, extra=extra)
    raise error  # `harness` or a kind this table does not know: no verdict


def _map_measure_error(error: BenchmarkGateError) -> _Verdict:
    """Rows T3, M1 to M3 of 2.7 for an error of `measure_paired` (the raising codes first, then `kind == "spawn"`, then the code, then the side)."""
    if error.code in _RAISING_CODES:  # M4
        raise error
    kind, extra = error.kind, _error_extra(error)
    if kind == "spawn":  # T3
        return _Verdict("REJECTED", "ISOLATION_REJECTED", "NOT_PROVISIONED", kind=kind, stage=_RAN, extra=extra)
    if error.code == "OUTPUT_TOO_LARGE" and error.side in ("base", "head"):
        reason = f"{error.side.upper()}_OUTPUT_TOO_LARGE"
    elif error.code in MEASURE_REFUSAL_CODES and error.code not in _MEASURE_NOT_A_VERDICT and error.code in COMPARE_RESULT_OF_REASON:
        reason = error.code
    else:
        raise error  # UNSUPPORTED_PLATFORM (step 1 handled it) or a code this table does not know: no verdict
    return _Verdict(COMPARE_RESULT_OF_REASON[reason], reason, kind or "", kind=kind, stage=_RAN, extra=extra)


def _identity_ending(error: _IdentityChanged) -> _Verdict:
    """The outcome of a spawn guard that objected (``ISOLATION_REJECTED``/``EXPORT_CHANGED``, stage ``ran``): the result carries what the exception
    knows (``side`` the side about to be spawned, ``phase`` and ``partial`` the completed timed rounds, as the errors of ``measure_paired`` and
    ``trace_paired`` do), so an operator can see where the swap was caught."""
    verdict = _isolation("EXPORT_CHANGED", [error.detail], _RAN)
    verdict.extra.update({"side": error.side, "phase": error.phase, "partial": error.partial})
    return verdict


def _replaced_after_invalid(error: BenchmarkGateError, guard: Callable[[str, str], None], root: str) -> _Verdict | None:
    """A `MEASURE_ARGS_INVALID` out of `trace_paired`/`measure_paired` is a caller fault, unless a child replaced a directory the argument
    checks look at (it renamed its export root or venv bin, or symlinked one side to the other): the checks then fail BEFORE any spawn and
    so before the spawn guard. Run the guard again: if it objects, the outcome is `ISOLATION_REJECTED`/`EXPORT_CHANGED` (stage `ran`), the
    same as the guard's own; if it is silent the error stands (None) and the caller maps it as before (a raise, exit 2)."""
    if error.code != "MEASURE_ARGS_INVALID":
        return None
    try:
        guard("base", root)
    except _IdentityChanged as changed:
        return _identity_ending(changed)
    return None


def _compare_runs(prepared: _Prepared, repo: object, base: Side, head: Side, checked: _Checked, *, run: _Run, argv_builder=None,
                  min_base_ns: int = _MIN_BASE_NS, interpreter_of: Callable[[str], InterpreterPin] | None = None) -> _RunOutcome:
    """Steps 10 to 12 (step 13, `_merge_outcome`, merges what is returned). A `BenchmarkGateError` raised by a run (a raise of 2.7: T1, M4,
    any 2.1 raise) propagates and step 12 does not run, EXCEPT a `MEASURE_ARGS_INVALID` while a directory the children use was replaced
    (a child that renamed its export root or symlinked one side to the other makes the argument checks fail): the spawn guard is run again,
    and if it objects that is `_IdentityChanged`'s outcome, not a caller fault. An `_IdentityChanged` (the spawn guard, before a spawn)
    is caught here, ends the runs with `ISOLATION_REJECTED`/`EXPORT_CHANGED` (stage `ran`) and step 12 DOES run (it wins with its own finding).
    Every other path started a child (a T3 spawn too, even if none ran), so step 12 runs: its `ISOLATION_REJECTED` (or `EXPORT_REJECTED`, stage `ran`) beats everything. Then
    the at-once trace results (items 2) and a measure-raised REJECTED/NOT_IMPROVED (item 3) are raised as `_Verdict`; what is left for the
    precedence list (pending trace mismatch, measure INCONCLUSIVE, success: items 4 to 6) is returned."""
    gate, common = prepared.gate, run.common
    common["trace_mismatch_seen"] = False
    sides = (prepared.roots[0], prepared.roots[1], *prepared.baseline.bins)  # the step-9 resolved paths, not resolved again after a child ran
    guard = _spawn_guard(prepared.baseline.identities)
    if not set(sides) <= {path for path, *_ in prepared.baseline.identities}:  # local invariant: only recorded (step-9 resolved) paths are spawned
        raise BenchmarkGateError("MEASURE_FAILED", "internal invariant: a path to be spawned from was not recorded at step 9")
    ending: _Verdict | None = None
    pending: _Verdict | None = None
    trace: dict | None = None
    measured: dict | None = None
    measure_verdict: _Verdict | None = None
    # 10: the paired trace run
    try:
        guard("base", sides[0])  # nothing may have been replaced since step 9
        traced = trace_paired(*sides, prepared.target, timeout_seconds=gate["per_run_timeout_seconds"], argv_builder=argv_builder,
                              spawn_guard=guard)
        trace = _normalise_trace(traced)
    except _IdentityChanged as error:  # a directory was replaced between runs: nothing more is run or measured (step 12 still runs)
        ending = _identity_ending(error)
    except BenchmarkGateError as error:
        ending = _replaced_after_invalid(error, guard, sides[0])
        if ending is None:
            mapped = _map_trace_error(error)
            trace = _normalise_trace(error.trace)
            if mapped.kind == "counts_differ":
                pending = mapped  # T5: the measurement still runs
            else:
                ending = mapped
    common["trace"] = trace
    # 11: the paired measurement, unless the trace already ended it
    if ending is None:
        try:
            guard("base", sides[0])  # before measure_paired's own argument checks: a child of the trace run may have replaced a directory
            measured = measure_paired(*sides, prepared.target, repeats=gate["repeats"], timeout_seconds=gate["per_run_timeout_seconds"],
                                      base_commit=base.commit, head_commit=head.commit, benchmark_sha256=prepared.benchmark_sha256,
                                      attempt=checked.attempt, warmup=gate["warmup_runs"], min_base_ns=min_base_ns, argv_builder=argv_builder,
                                      order_salt=checked.order_salt, spawn_guard=guard)
        except _IdentityChanged as error:
            ending = _identity_ending(error)
        except BenchmarkGateError as error:
            replaced = _replaced_after_invalid(error, guard, sides[0])
            if replaced is not None:
                ending = replaced
            else:
                mapped = _map_measure_error(error)
                if mapped.result == "INCONCLUSIVE":  # M3: item 4 (a pending mismatch stands) or item 5; step 13 decides
                    measure_verdict = mapped
                else:  # item 3
                    ending = mapped
        if ending is not None and pending is not None:  # a trace mismatch still pending when the measurement ended it: say so (an ending before the measurement had none pending)
            ending.extra["trace_mismatch_seen"] = True
    # 12: beats everything but a raise. Note for C4e: when a step-12 finding beats a pending `counts_differ` (or an ending that carried
    # `trace_mismatch_seen`), the result is the finding's and `trace_mismatch_seen` STAYS False (spec 2.7 item 3 sets it only on a result that the
    # measure or a guard ended); the pending mismatch is still visible in `trace`.
    finding = _post_run_check(prepared, repo, base, head, interpreter_of=interpreter_of)
    if finding is not None:
        raise finding
    if ending is not None:
        raise ending
    return _RunOutcome(trace, pending, measured, measure_verdict)


# --- step 13: the one merge point of steps 10 to 12 (spec 2.6, 2.7) ---------------------------------------------------------------

_HOST_BUSY_MIN_CPUS = 3  # below this the gate's own one-process load is too large a share of the machine for the end check to mean anything


def _host_busy_end(checked: _Checked, load_probe: Callable[[], tuple] | None, common: dict) -> bool:
    """The end host check (2.6), probed once: `(load1 - 1) * 10 > 7 * cpu_count` in exact arithmetic (`Fraction(str(load1))`), the 1 being
    the gate's own load. Records `host_check`, `loadavg.end` and `cpu_count.end`. A failed start probe already skipped both checks (no end
    probe); a bad end probe or fewer than `_HOST_BUSY_MIN_CPUS` cpus skips this one."""
    if checked.load is None:
        return False
    load = _host_load(load_probe or _default_load_probe)
    if load is None:
        common["host_check"] = "skipped_probe_failed"
        return False
    common["loadavg"] = {**common["loadavg"], "end": float(load[0])}
    common["cpu_count"] = {**common["cpu_count"], "end": load[1]}
    if load[1] < _HOST_BUSY_MIN_CPUS:
        common["host_check"] = "end_skipped_few_cpus"
        return False
    common["host_check"] = "checked"
    return (Fraction(str(load[0])) - 1) * 10 > 7 * load[1]


def _measured_fields(measured: dict) -> dict:
    """The result keys a successful `measure_paired` fills (raw samples kept so a consumer can recompute): the ratios head/base per pair,
    `improvement = 1 - median(ratios)`, `mad_over_median`, the two median times. Fractions become floats in `_result_dict`."""
    base_ns, head_ns = measured["base_ns"], measured["head_ns"]
    ratios, median, mad = _ratio_stats(base_ns, head_ns)
    return {"order": measured["order"], "base_ns": base_ns, "head_ns": head_ns, "digest": measured["digest"], "argv": measured["argv"],
            "n": len(base_ns), "ratios": ratios, "improvement": 1 - median, "mad_over_median": mad / median,
            "base_median_ns": _median([Fraction(v) for v in base_ns]), "head_median_ns": _median([Fraction(v) for v in head_ns])}


def _merge_outcome(outcome: _RunOutcome, prepared: _Prepared, checked: _Checked, run: _Run, load_probe: Callable[[], tuple] | None) -> _Verdict:
    """Items 4 to 6 of the precedence list (2.7); items 0 to 3 already left `_compare_runs` as a raise or a `_Verdict`. 4: a pending
    `counts_differ` mismatch beats a measure-raised INCONCLUSIVE and the statistics; whatever was measured stays in the result and the end
    host check is not probed. 5: a measure-raised INCONCLUSIVE with nothing pending. 6: the statistics, then `HOST_BUSY_END` replaces an
    IMPROVED, NOT_IMPROVED or INCONCLUSIVE of `evaluate_paired_samples`, never `INVALID_INPUT`."""
    pending, refused, measured = outcome.pending, outcome.measure_verdict, outcome.measured
    if pending is not None:
        if measured is not None:
            pending.extra.update(_measured_fields(measured))
        elif refused is not None:
            pending.extra["partial"] = refused.extra.get("partial")
            pending.extra["untrusted_text"] = [*pending.extra.get("untrusted_text", []), *refused.extra.get("untrusted_text", [])]
        return pending
    if refused is not None:
        return refused
    if measured is None:  # no pending error and no refusal: the measurement succeeded (an invariant, not an input)
        raise BenchmarkGateError("MEASURE_FAILED", "internal invariant: no measurement and no verdict")
    fields = _measured_fields(measured)
    gate = prepared.gate
    result, reason = evaluate_paired_samples(measured["base_ns"], measured["head_ns"], repeats=gate["repeats"],
                                             min_improvement=gate["min_improvement"], max_noise=gate["max_noise"])
    if reason != "INVALID_INPUT" and _host_busy_end(checked, load_probe, run.common):
        result, reason = "INCONCLUSIVE", "HOST_BUSY_END"
    return _Verdict(result, reason, stage="ran", extra=fields)


def _compare_impl(gate: object, repo: object, base: Side, head: Side, *, attempt: object = 1, out_path: object,
                  allow_writable_interpreter: bool = False, argv_builder=None, load_probe=None, min_base_ns: int = _MIN_BASE_NS,
                  order_salt: object = None, interpreter_of=None) -> _WrittenResult:
    """The pipeline behind `compare`, with the test seams (`argv_builder`, `load_probe`, `min_base_ns`, `order_salt`, `interpreter_of`).
    A result (a `_Verdict`) is assembled, written to ``out_path`` after step 12 and returned; a caller or harness fault raises
    `BenchmarkGateError`."""
    run = _Run()
    try:
        checked = _compare_checks(gate, repo, base, head, attempt=attempt, out_path=out_path, allow_writable_interpreter=allow_writable_interpreter,
                                  load_probe=load_probe, order_salt=order_salt, interpreter_of=interpreter_of, run=run)
        prepared = _compare_prepare(repo, base, head, checked, interpreter_of=interpreter_of, run=run)
        outcome = _compare_runs(prepared, repo, base, head, checked, run=run, argv_builder=argv_builder, min_base_ns=min_base_ns,
                                interpreter_of=interpreter_of)
        verdict = _merge_outcome(outcome, prepared, checked, run, load_probe)
    except _Verdict as ended:
        verdict = ended
    result = _result_dict(verdict, run.common)
    if run.out is None:  # a verdict only exists after step 1 validated out_path (an invariant, not an input)
        raise BenchmarkGateError("MEASURE_FAILED", "internal invariant: a verdict before out_path was validated")
    written = _WrittenResult(result)
    written.written_sha256 = _write_result(str(out_path), run.out[0], run.out[1], _result_bytes(result))
    return written


def compare(gate: object, repo: object, base: Side, head: Side, *, attempt: object = 1, out_path: object,
            allow_writable_interpreter: bool = False) -> _WrittenResult:
    """Compare two exports of one benchmark (spec 2.2): a result dict (a ``_WrittenResult``) for every outcome that PR content, the children or the host can cause,
    `BenchmarkGateError` for a caller or harness fault. A thin wrapper over `_compare_impl` with the default seams.
    ``allow_writable_interpreter`` must be a ``bool`` (a ``BenchmarkGateError`` ``MEASURE_ARGS_INVALID`` otherwise); it is a human signal and
    must never be set by an automatic retry of ``INTERPRETER_WRITABLE``.
    Known residuals: the module docstring ("Known residuals of ``compare``", ``[R1]`` to ``[R9]``) is their single source; read them there. Retry on the
    same exports is keyed on (reason, stage, detail): ``COMPARE_RETRYABLE_AUTOMATIC`` (``HOST_BUSY_START``) and, only after a human sets the flag,
    ``COMPARE_RETRYABLE_WITH_HUMAN_FLAG`` (``INTERPRETER_WRITABLE``) are the complete list; every other
    ``ISOLATION_REJECTED`` at ``pre_overlay`` (``INTERPRETER_CHANGED``, ``INTERPRETER_DIFFERS``, ``SNAPSHOT_CHANGED``, ``DEPENDENCY_PARITY``,
    ``TRACKED_FILE_DIFFERS``, ...) is not (spec 2.3). The returned dict (a `_WrittenResult`: a ``dict`` subclass that also carries
    ``written_sha256``, the sha256 of the bytes written to ``out_path``) is the
    in-memory result; the file is not read back."""
    return _compare_impl(gate, repo, base, head, attempt=attempt, out_path=out_path, allow_writable_interpreter=allow_writable_interpreter)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_MAX_INPUT_BYTES = 1 << 20


def gate_sha256(normalized_gate: dict) -> str:
    """sha256 of the canonical JSON of a normalized gate (the Orchestrator recomputes it)."""
    canonical = json.dumps(normalized_gate, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _read_bounded(path: str, limit: int, nofollow: bool = False, dir_fd: int | None = None) -> bytes:
    """Read at most ``limit + 1`` bytes of a REGULAR file; the caller treats ``len > limit`` as too large.

    A bounded read rather than ``stat().st_size``: a size taken before the read is not a cap, and a FIFO or a
    device (``/dev/zero``) reports no useful size. The file is opened ``O_NONBLOCK`` (where the platform has it)
    so opening a FIFO with no writer cannot hang, then ``fstat`` on the opened descriptor must say regular file.
    ``nofollow`` refuses a symlink as the final component (``O_NOFOLLOW``), for files inside a tree under test; ``dir_fd``
    makes ``path`` relative to that directory descriptor.
    Raises ``OSError`` or ``ValueError``; both are usage errors to the CLI.
    """
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | (getattr(os, "O_NOFOLLOW", 0) if nofollow else 0), dir_fd=dir_fd)
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
    """Record a fresh venv's `.pth` and startup files before the project install, then print the two pins `compare` takes:
    ``snapshot_sha256: <hex>`` (the written file's bytes) and ``interpreter_sha256: <hex>`` (`interpreter_pin`). Exit 0; 2 on any failure,
    with the code on stderr and nothing on stdout. The interpreter pin is computed BEFORE the file is written: `snapshot_venv` refuses an
    existing path, so a pin failure after the write would leave a file that blocks the retry. A snapshot larger than ``_VENV_MAX_SNAPSHOT_BYTES`` (the
    one limit every reader uses) is a failure, never the hash of a truncated read: no later step could load it; the file this call wrote is then removed (best effort), so a
    retry on the same ``--out`` is possible."""
    written = False
    try:
        pin = interpreter_pin(args.bin)
        snapshot_venv(args.bin, args.out)
        written = True
        data = _read_bounded(args.out, _VENV_MAX_SNAPSHOT_BYTES, nofollow=True)
        if len(data) > _VENV_MAX_SNAPSHOT_BYTES:
            raise BenchmarkGateError("VENV_SNAPSHOT_INVALID", "the snapshot is larger than the limit every later step reads")
    except (BenchmarkGateError, OSError, ValueError) as exc:
        if written:  # the file this call just created (O_EXCL) is unusable: remove that exact path, or the retry would be blocked by it
            with contextlib.suppress(OSError):
                os.unlink(args.out)
        return _fail(exc if isinstance(exc, BenchmarkGateError) else BenchmarkGateError("TREE_UNREADABLE", escape_diagnostic(str(exc), 120)))
    print(f"snapshot_sha256: {hashlib.sha256(data).hexdigest()}")
    print(f"interpreter_sha256: {pin.sha256}")
    return 0


def _cmd_harness_sha256(_args: argparse.Namespace) -> int:
    """Print ``harness_sha256: <hex>`` (`harness_sha256()`), exit 0; 2 with the code on stderr when the harness cannot be digested. Run it in a
    TRUSTED copy of the harness (the pinned release or a clean checkout) to get the EXPECTED value C4e compares with a `compare` result's; the value
    of a previous `compare` result is never a source for it (circular)."""
    try:
        digest = harness_sha256()
    except BenchmarkGateError as exc:
        return _fail(exc)
    print(f"harness_sha256: {digest}")
    return 0


def _cmd_fixed_parent(_args: argparse.Namespace) -> int:
    """Print `fixed_parent()`: C4f builds `export --dest` and `cleanup --root` paths from it."""
    print(fixed_parent())
    return 0


def _cmd_cleanup(args: argparse.Namespace) -> int:
    """Remove one dispatch-unique root; print the result code: exit 0 for ``REMOVED``/``ABSENT``, 1 for a refusal (``REMOVE_FAILED``
    adds the escaped reason on stderr; its ``first: <name>`` is the first TOP-LEVEL entry; "claimed root is locked by another
    process" means retry later). SIGINT, SIGTERM and SIGHUP become
    ``KeyboardInterrupt`` (the first also ignores the others, so a second Ctrl-C cannot interrupt the put-back): the claimed tree is
    put back, exit 1; other fatal signals leave ``.gone-<root>-<hex>`` (see ``cleanup_root``)."""
    try:
        with _with_signal_handlers():
            code = cleanup_root(args.root)
    except KeyboardInterrupt:
        print("cleanup interrupted; run it again to finish", file=sys.stderr)
        return 1
    print(code)
    if code == "REMOVE_FAILED":
        print(f"REMOVE_FAILED: {_failure or 'no detail'}", file=sys.stderr)
    return 0 if code in ("REMOVED", "ABSENT") else 1


def _crash_message(exc: BaseException) -> str:
    """The crash contract's one stderr line (spec 2.9): ``usage error: <CODE or INTERNAL>: <type>``. Never the exception's text: it may carry
    attacker bytes. ``CODE`` is a ``BenchmarkGateError`` code from the closed ``ERROR_CODES``; anything else is ``INTERNAL``."""
    code = exc.code if isinstance(exc, BenchmarkGateError) and exc.code in ERROR_CODES else "INTERNAL"
    return f"usage error: {code}: {escape_diagnostic(type(exc).__name__, 64)}"


# What `run-once` reports as a reason (exit 1): every code `_run_error_code` can give for either side, plus the missing digest. Derived from
# `_KIND_SUFFIX`: a new `_execute` kind cannot turn `run-once` into exit 2.
_RUN_ONCE_REASONS = frozenset(_run_error_code(side, kind) for side in ("base", "head") for kind in _KIND_SUFFIX) | {"DIGEST_MISSING"}


def _read_gate_file(path: str) -> object:
    """The raw ``benchmark_gate`` JSON of ``--gate`` (a bounded read; not the whole specialist inputs). ``OSError`` or ``ValueError`` otherwise."""
    data = _read_bounded(path, _MAX_INPUT_BYTES)
    if len(data) > _MAX_INPUT_BYTES:
        raise ValueError("gate file too large")
    return json.loads(data.decode("utf-8"))


def _cmd_compare(args: argparse.Namespace) -> int:
    """Compare two exports (spec 2.9). This function returns 0 only for an ``IMPROVED`` result, 1 for any other result, 2 for usage, a raised
    ``BenchmarkGateError`` or a crash. Reading contract: exit 0 means ``IMPROVED`` ONLY together with a valid ``RESULT: IMPROVED ...`` line whose
    ``sha256=`` matches the bytes of the file; a bare exit 0 (``compare --help``, which argparse ends with exit 0 and no ``RESULT:`` line) is NOT an
    ``IMPROVED``. Abbreviated options are refused (``allow_abbrev=False``, exit 2). An exit 1 WITHOUT a valid ``RESULT:`` line counts as exit 2, and on exit 2 a file at
    ``--out`` is to be IGNORED. The file can exist on exit 2: ``compare`` writes it (step 13) and only then does this function validate the
    in-memory result (a failure there raises ``ValueError``, exit 2, with the file already on disk); a crash BEFORE ``compare`` returns, or
    inside it before the write, leaves none. The crash handler itself writes nothing. ``INTERPRETER_WRITABLE`` must never be auto-retried
    with ``--allow-writable-interpreter`` (a human signal; see ``COMPARE_RETRYABLE_WITH_HUMAN_FLAG``).
    The ``RESULT: <result> <reason> interpreter_writable=<0|1|n/a> sha256=<hex>`` line is printed AFTER the
    result file exists, from the in-memory result and the sha256 ``_write_result`` returned for the bytes it wrote (the file is NOT read back:
    a same-user process can rewrite it in place, and the exit code must not follow such a rewrite; the Orchestrator's check of the line
    against the bytes it reads from the file, once, is what catches one). A crash catches ``BenchmarkGateError``, ``OSError``, ``ValueError``, ``RecursionError``,
    ``Exception`` and ``KeyboardInterrupt`` (a SIGTERM, SIGHUP or SIGINT) and prints ``usage error: <CODE or INTERNAL>: <type>`` on stderr
    (never attacker text) and exits 2; sealed exports stay sealed (``cleanup`` restores them)."""
    try:
        with _with_signal_handlers():
            gate = _read_gate_file(args.gate)
            base = Side(args.base_root, args.base_commit, args.base_bin, args.base_snapshot, args.base_snapshot_sha256, args.base_interpreter_sha256)
            head = Side(args.head_root, args.head_commit, args.head_bin, args.head_snapshot, args.head_snapshot_sha256, args.head_interpreter_sha256)
            outcome = compare(gate, args.repo, base, head, attempt=args.attempt, out_path=args.out,
                              allow_writable_interpreter=args.allow_writable_interpreter)
            # everything below comes from the in-memory result and the hash `_write_result` returned for the bytes it wrote: the file on
            # disk is not read back (a same-user process could have rewritten it in place since, with the same inode)
            result, reason = outcome["result"], outcome["reason"]
            digest = getattr(outcome, "written_sha256", None)
            if (type(digest) is not str or result not in COMPARE_RESULTS or COMPARE_RESULT_OF_REASON.get(reason) != result or outcome["interpreter_writable"] not in (True, False, None)
                    or _SHA256_RE.fullmatch(digest) is None):
                raise ValueError("compare returned an unknown result or reason, or no hash of what it wrote")
            writable = {True: "1", False: "0", None: "n/a"}[outcome["interpreter_writable"]]
            print(f"RESULT: {result} {reason} interpreter_writable={writable} sha256={digest}")
    except (BenchmarkGateError, OSError, ValueError, RecursionError, Exception, KeyboardInterrupt) as exc:
        print(_crash_message(exc), file=sys.stderr)
        return 2
    return 0 if result == "IMPROVED" else 1


def _cmd_run_once(args: argparse.Namespace) -> int:
    """One untimed run of the benchmark (spec 2.9). Exit 0 prints ``digest: <64 hex>`` (what the child printed: NOT evidence); 1 prints the
    reason on stdout (``<SIDE>_NONZERO_EXIT``, ``<SIDE>_TIMEOUT``, ``OUTPUT_TOO_LARGE``, ``DIGEST_MISSING`` or ``REJECT:<gate code>``) and the
    escaped detail on stderr (child text: untrusted); 2 for usage or a crash (the crash contract of ``_cmd_compare``)."""
    try:
        with _with_signal_handlers():
            normalized, code = validate_benchmark_gate(_read_gate_file(args.gate))
            if normalized is None:
                print(f"REJECT:{code}")
                return 1
            outcome = run_benchmark_once(args.root, args.bin, benchmark_target(normalized), timeout_seconds=normalized["per_run_timeout_seconds"], side=args.side)
            print(f"digest: {outcome['digest']}")
            return 0
    except BenchmarkGateError as exc:
        if exc.code in _RUN_ONCE_REASONS:
            print(exc.code)
            print(f"detail: {escape_diagnostic(exc.detail, 200)}", file=sys.stderr)
            return 1
        print(_crash_message(exc), file=sys.stderr)
        return 2
    except (OSError, ValueError, RecursionError, Exception, KeyboardInterrupt) as exc:
        print(_crash_message(exc), file=sys.stderr)
        return 2


_RESULT_LINE_RE = re.compile(r"RESULT: ([A-Z_]+) ([A-Z_]+) interpreter_writable=(0|1|n/a) sha256=([0-9a-f]{64})")


def parse_compare_outcome(returncode: int, stdout: str, file_bytes: bytes | None) -> tuple[int, dict | None]:
    """The REFERENCE READER of one ``compare`` run for C4e (spec 2.9; stdlib only): `(exit_code, parsed)`, the exit code the Orchestrator may act
    on and the parsed result file. `returncode` and `stdout` are the process's; `file_bytes` is the result file read ONCE into bytes (``None``
    when it does not exist). An exit 0 or 1 counts only with exactly ONE valid ``RESULT:`` line whose ``sha256=`` is the hash of `file_bytes` and
    whose result and reason equal those of the parsed file (and are a pair of ``COMPARE_RESULT_OF_REASON``), and the exit agrees with the result: 0 only for
    ``IMPROVED`` (a bare exit 0, such as ``compare --help``, is NOT an ``IMPROVED``), 1 only for any other result. Anything else, including Python's own
    exit 1 for an uncaught exception, is `(2, None)`: "ignore the file". `stage` and `detail` are to be read from `parsed`, never from the line."""
    ignore: tuple[int, dict | None] = (2, None)
    if returncode not in (0, 1) or file_bytes is None:
        return ignore
    lines = [m for m in map(_RESULT_LINE_RE.fullmatch, stdout.splitlines()) if m]
    if len(lines) != 1 or lines[0].group(4) != hashlib.sha256(file_bytes).hexdigest():
        return ignore
    try:
        parsed = json.loads(file_bytes)
    except ValueError:
        return ignore
    if not isinstance(parsed, dict) or (parsed.get("result"), parsed.get("reason")) != (lines[0].group(1), lines[0].group(2)) \
            or COMPARE_RESULT_OF_REASON.get(parsed["reason"]) != parsed["result"]:
        return ignore
    improved = parsed["result"] == "IMPROVED"
    return (returncode, parsed) if (returncode == 0) == improved else ignore


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``validate`` (C4a), ``lint`` (C4b), ``export``, ``fixed-parent`` (C4c-1a), ``cleanup`` (C4c-1b, C4c-1c), ``snapshot-venv``
    (C4c-2c), and ``compare`` and ``run-once`` (C4d-3). Every other subcommand lets an unexpected exception escape (Python exits 1); ``compare`` and
    ``run-once`` own the crash contract: every error, ``KeyboardInterrupt`` included, becomes ``usage error: <CODE or INTERNAL>: <type>`` and
    exit 2 (see ``_cmd_compare``). An unexpected crash in ``harness-sha256``, ``snapshot-venv``, ``fixed-parent`` and the other non-compare
    subcommands is Python's uncaught exception and exits 1, so a caller must treat ANY non-zero exit of those as a failure. ``harness-sha256`` prints the harness digest. Reading contract for ``compare``: exit 0 is ``IMPROVED`` ONLY with a
    valid ``RESULT: IMPROVED ...`` line whose ``sha256=`` matches the file's bytes (``main`` returns an argparse ``SystemExit`` code unchanged, so
    ``compare --help`` is a bare exit 0 and NOT an ``IMPROVED``); exit 1 without a valid ``RESULT:`` line counts as 2, and exit 2 means
    any result file is to be IGNORED; ``INTERPRETER_WRITABLE`` must never be auto-retried with ``--allow-writable-interpreter``. Every parser has
    ``allow_abbrev=False``: an abbreviated option is a usage error (exit 2), never the human flag."""
    # `allow_abbrev=False` on the parser and on every subparser: an abbreviation such as `--allow-writable-i` must not set the human signal
    parser = argparse.ArgumentParser(prog="benchmark_gate.py", allow_abbrev=False,
                                     description="Benchmark gate: validate, lint, export, fixed-parent, cleanup, snapshot-venv, harness-sha256, compare, run-once.")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", allow_abbrev=False, help="validate specialist_inputs.benchmark_gate")
    validate.add_argument("--specialist-inputs", required=True, metavar="FILE")
    validate.set_defaults(func=_cmd_validate)
    lint = sub.add_parser("lint", allow_abbrev=False, help="lint one benchmark file (exit 0 clean, 1 violations, 2 usage)")
    lint.add_argument("--benchmark", required=True, metavar="FILE")
    lint.add_argument("--symbol", required=True, metavar="SYMBOL")
    lint.add_argument("--repo-root", metavar="DIR", help="derive the repo's top-level names from DIR and DIR/src")
    lint.add_argument("--top-level", action="append", default=[], metavar="NAME", help="add one top-level name")
    lint.set_defaults(func=_cmd_lint)
    export = sub.add_parser("export", allow_abbrev=False, help="export a commit's tree (exit 0, 1 refused, 2 usage); requires git >= 2.43")
    export.add_argument("--repo", required=True, metavar="DIR")
    export.add_argument("--commit", required=True, metavar="SHA")
    export.add_argument("--dest", required=True, metavar="DIR", help="<fixed parent>/<root>/<leaf>, root [A-Za-z0-9][A-Za-z0-9_-]{7,63}, leaf [A-Za-z0-9][A-Za-z0-9_-]{0,63}; must not exist; see fixed-parent")
    export.add_argument("--owner-pid", type=int, metavar="PID",
                        help="pid in a NEW root's marker, a positive int below 2**31 (default: this short-lived process, so cleanup is "
                             "allowed at once; ignored for an existing root)")
    export.set_defaults(func=_cmd_export)
    snapshot = sub.add_parser("snapshot-venv", allow_abbrev=False, help="record a fresh venv's .pth and startup files; run BEFORE installing the project; prints snapshot_sha256 and interpreter_sha256 (exit 0, 2 failure)")
    snapshot.add_argument("--bin", required=True, metavar="DIR", help="the venv's bin directory")
    snapshot.add_argument("--out", required=True, metavar="FILE", help="a new file")
    snapshot.set_defaults(func=_cmd_snapshot_venv)
    harness = sub.add_parser("harness-sha256", allow_abbrev=False, help="print harness_sha256 (take the EXPECTED value from a trusted copy of the harness, never from a compare result)")
    harness.set_defaults(func=_cmd_harness_sha256)
    fixed = sub.add_parser("fixed-parent", allow_abbrev=False, help="print the per-user directory that roots live in")
    fixed.set_defaults(func=_cmd_fixed_parent)
    cleanup = sub.add_parser("cleanup", allow_abbrev=False, help="remove a dispatch-unique root (exit 0 removed/absent, 1 refused or interrupted, no code on stdout = retry; "
                             "REMOVE_FAILED 'claimed root is locked by another process' = retry later)")
    cleanup.add_argument("--root", required=True, metavar="DIR")
    cleanup.set_defaults(func=_cmd_cleanup)
    compare_p = sub.add_parser("compare", allow_abbrev=False, help="compare two exports of one benchmark (exit 0 IMPROVED, 1 any other result, 2 usage or crash; prints a RESULT line)")
    for flag in ("gate", "repo", "base-root", "head-root", "base-commit", "head-commit", "base-bin", "head-bin", "base-snapshot", "base-snapshot-sha256",
                 "base-interpreter-sha256", "head-snapshot", "head-snapshot-sha256", "head-interpreter-sha256", "out"):
        compare_p.add_argument(f"--{flag}", required=True, metavar="FILE" if flag in ("gate", "out") or flag.endswith("snapshot") else "VALUE",
                               help="the raw benchmark_gate JSON (bounded read)" if flag == "gate" else "a new result file" if flag == "out" else None)
    compare_p.add_argument("--attempt", type=int, default=1, metavar="N")
    compare_p.add_argument("--allow-writable-interpreter", action="store_true")
    compare_p.set_defaults(func=_cmd_compare)
    run_once = sub.add_parser("run-once", allow_abbrev=False, help="one untimed run of the benchmark (exit 0 digest, 1 reason, 2 usage or crash)")
    run_once.add_argument("--gate", required=True, metavar="FILE", help="the raw benchmark_gate JSON")
    run_once.add_argument("--root", required=True, metavar="DIR")
    run_once.add_argument("--bin", required=True, metavar="DIR", help="the venv's bin directory")
    run_once.add_argument("--side", choices=("base", "head"), default="head")
    run_once.set_defaults(func=_cmd_run_once)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse exits 2 on usage errors (and 0 on --help)
        return exc.code if isinstance(exc.code, int) else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
