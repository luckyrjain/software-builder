"""Tests for the C4b AST lint of `benchmark_gate.py`: `validate_benchmark_content` and the `lint` CLI.

Covers every rule in the design's `validate_benchmark_content` row and every lint case named in Rollout row 2
(`docs/superpowers/specs/2026-10-02-c4-performance-review-executor-handoff-design.md`). The lint is a tripwire;
these tests pin what it does reject and accept, not that it is exhaustive.
"""

from __future__ import annotations

import ast
import importlib.util
import os
import subprocess
import sys
import time
import warnings
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

SYMBOL = "build_report"
TOPS = frozenset({"app"})
DIGEST_PRINT = '    print("BENCH_RESULT_DIGEST: " + hashlib.sha256(build_report(1)).hexdigest())\n'

GOOD = b"""from __future__ import annotations
import hashlib
from app.orders import build_report


def _digest(value):
    return hashlib.sha256(repr(value).encode()).hexdigest()


def test_bench():
    result = [build_report(i) for i in range(3)]
    print("BENCH_RESULT_DIGEST: " + _digest(result))
"""


def lint(source, symbol=SYMBOL, tops=TOPS):
    return bg.validate_benchmark_content(source, symbol, tops)


def codes(source, **kwargs):
    return set(lint(source, **kwargs))


def swap(old: bytes, new: bytes, base: bytes = GOOD) -> bytes:
    """``base`` with ``old`` replaced by ``new``; ``old`` must be present exactly once."""
    assert base.count(old) == 1, old
    return base.replace(old, new)


def with_imports(*lines: str) -> bytes:
    return swap(b"import hashlib\n", b"import hashlib\n" + "".join(f"{line}\n" for line in lines).encode())


def with_top(text: str) -> bytes:
    """GOOD plus module-level code appended after the test function."""
    return GOOD + b"\n\n" + text.encode()


NO_FUTURE = GOOD.replace(b"from __future__ import annotations\n", b"")  # annotations are evaluated at def time


def with_body(body: str) -> bytes:
    """GOOD with the test function's body replaced (the body is 4-space indented text)."""
    return GOOD.split(b"def test_bench():\n")[0] + b"def test_bench():\n" + body.encode()


# --- Accepted sources ---

def test_helpers_constants_and_from_future_annotations_are_allowed():
    source = with_top("LIMIT = 3\n\n\ndef helper(x, y=2, *rest, **kw):\n    return x + y\n")
    assert lint(source) == []  # GOOD itself starts with `from __future__ import annotations`


@pytest.mark.parametrize(
    "module",
    ["hashlib", "json", "math", "statistics", "itertools", "functools", "collections", "re", "decimal",
     "fractions", "heapq", "bisect", "copy", "random", "io", "enum", "sqlite3", "collections.abc", "json.decoder"],
)
def test_allowlisted_stdlib_imports_pass(module):
    assert lint(with_imports(f"import {module}", f"from {module} import something")) == []


def test_locals_named_test_do_not_count_as_module_level_names():
    source = with_top(
        "def helper(test_x):\n    test_y = [test_z for test_z in range(test_x)]\n    return test_y\n\n\n"
        "Q = [test_q for test_q in range(2)]\nG = list(test_g for test_g in range(2))\n"
    )
    assert lint(source) == []


@pytest.mark.parametrize(
    "body",
    [
        '    print(f"BENCH_RESULT_DIGEST: {hashlib.sha256(build_report(1)).hexdigest()}")\n',
        '    digest = hashlib.sha256(build_report(1)).hexdigest()\n    print("BENCH_RESULT_DIGEST: %s" % digest)\n',
        '    print("x BENCH_RESULT_DIGEST: " + hashlib.sha256(build_report(1)).hexdigest())\n',  # "in", not "at the start of"
    ],
)
def test_digest_literal_inside_an_fstring_or_format(body):
    assert lint(with_body(body)) == []


# --- Byte-level rules: size, ASCII, encoding cookie, parse failures ---

def test_over_size_boundary_is_16_kib():
    at_limit = GOOD + b"#" * (16 * 1024 - len(GOOD))
    assert len(at_limit) == 16 * 1024 and lint(at_limit) == []
    assert lint(at_limit + b"#") == ["FILE_TOO_LARGE"]


@pytest.mark.parametrize(
    "tail, expected",
    [
        ("# caf\u00e9\n".encode("utf-8"), ["NON_ASCII_SOURCE"]),
        (b"# \xff\n", ["NON_ASCII_SOURCE"]),
        ("na\u00efve = 1\n".encode("utf-8"), ["NON_ASCII_SOURCE"]),
    ],
)
def test_non_ascii_bytes_are_rejected(tail, expected):
    assert lint(GOOD + tail) == expected


def test_a_bom_is_non_ascii_and_a_utf8_sig_cookie():  # a BOM makes detect_encoding say utf-8-sig
    assert lint(b"\xef\xbb\xbf" + GOOD) == ["NON_ASCII_SOURCE", "ENCODING_REJECTED"]


@pytest.mark.parametrize("cookie", ["latin-1", "cp037", "ascii", "utf-16", "iso-8859-15", "no-such-codec"])
def test_coding_cookie_other_than_utf8_is_rejected(cookie):
    # The bypass: an ASCII-only file declaring another codec is parsed by ast.parse(bytes) with that codec.
    assert lint(f"# -*- coding: {cookie} -*-\n".encode("ascii") + GOOD) == ["ENCODING_REJECTED"]
    assert lint(f"#!/usr/bin/env python3\n# coding: {cookie}\n".encode("ascii") + GOOD) == ["ENCODING_REJECTED"]  # line 2


@pytest.mark.parametrize("codec", ["latin-1", "utf-7", "hz", "unicode_escape"])
@pytest.mark.parametrize("newline", [b"\n", b"\r\n", b"\r"])
@pytest.mark.parametrize("blank_first_line", [False, True])
def test_cookie_is_seen_whatever_the_newline_style(codec, newline, blank_first_line):
    # `tokenize.detect_encoding` splits on \n only, the C tokenizer also on a bare \r: `\r# coding: hz\r...` hid
    # the cookie from the former (the `hz` program below compiled a non-ASCII constant) while the parser honoured it.
    cookie = b"# coding: " + codec.encode() + newline
    assert lint((newline if blank_first_line else b"") + cookie + GOOD.replace(b"\n", newline)) == ["ENCODING_REJECTED"]


@pytest.mark.parametrize("newline", [b"\n", b"\r\n", b"\r"])
@pytest.mark.parametrize("cookie", [None, "utf-8", "UTF-8", "utf8", "utf_8", "u8", "utf-8-sig"])  # utf-8 aliases
def test_utf8_cookie_spellings_and_newline_styles_are_accepted(cookie, newline):
    first = b"" if cookie is None else f"# coding: {cookie}".encode() + newline
    assert lint(first + GOOD.replace(b"\n", newline)) == []


@pytest.mark.parametrize(
    "source",
    [GOOD + b"\x00", swap(b"result = [", b"res\x00ult = ["), b"def (:\n", b"x = (\n",
     GOOD + b"x = " + b"(" * 300 + b"1" + b")" * 300 + b"\n"],  # 300-deep nesting
)
def test_parse_failures_become_a_code(source):
    assert lint(source) == ["PARSE_FAILED"]


class _Sneaky(bytes):  # a subclass could lie about isascii(); it is not trusted
    def isascii(self):
        return True


@pytest.mark.parametrize("source", [None, "def test_x(): pass", bytearray(GOOD), memoryview(GOOD), 5, [GOOD], _Sneaky(GOOD)])
def test_non_bytes_source_is_a_code(source):
    assert lint(source) == ["SOURCE_NOT_BYTES"]


# --- Forbidden constructs ---

FORBIDDEN_CASES = {
    "class": (with_top("class Helper:\n    pass\n"), {"FORBIDDEN_CLASS"}),
    "async def": (with_top("async def helper():\n    return 1\n"), {"FORBIDDEN_ASYNC_FUNCTION"}),
    # A source an AST rule already rejected is not compiled, so it never gets a TEST_* code (its code set is a subset).
    "async def test": (swap(b"def test_bench", b"async def test_bench"), {"FORBIDDEN_ASYNC_FUNCTION"}),
    "lambda": (with_top("key = lambda row: row\n"), {"FORBIDDEN_LAMBDA"}),
    "lambda-forged test": (with_top('test_zzz = lambda: print("BENCH_RESULT_DIGEST: " + "0" * 64)\n'), {"FORBIDDEN_LAMBDA"}),
    "try/except": (
        with_body("    try:\n    " + DIGEST_PRINT + "    except ValueError:\n        pass\n"), {"FORBIDDEN_TRY"}
    ),
    "except*": (
        with_body("    try:\n    " + DIGEST_PRINT + "    except* ValueError:\n        pass\n"), {"FORBIDDEN_TRY"}
    ),
    "with": (with_body("    with helper() as handle:\n    " + DIGEST_PRINT), {"FORBIDDEN_WITH"}),
    "with + type()": (
        # The round-3 attack: a context manager built from type() pads the benchmark with no Try or ClassDef.
        with_body('    Suppress = type("Suppress", (), {})\n    with Suppress():\n    ' + DIGEST_PRINT),
        {"FORBIDDEN_WITH"},
    ),
    "global": (with_top("LIMIT = 0\n\n\ndef helper():\n    global LIMIT\n    LIMIT = 1\n"), {"FORBIDDEN_GLOBAL"}),
    "nonlocal": (with_top("def o():\n    x = 1\n    def i():\n        nonlocal x\n        x = 2\n"), {"FORBIDDEN_NONLOCAL"}),
    "async with": (with_top("async with a:\n    pass\n"), {"FORBIDDEN_ASYNC_FUNCTION"}),
    "async for": (with_top("async for x in y:\n    pass\n"), {"FORBIDDEN_ASYNC_FUNCTION"}),
    "await": (with_top("await z\n"), {"FORBIDDEN_ASYNC_FUNCTION"}),
    "async comprehension": (with_top("XS = [x async for x in y]\n"), {"FORBIDDEN_ASYNC_FUNCTION"}),
    "decorator on a helper": (with_top("@helper_decorator\ndef other():\n    return 1\n"), {"FORBIDDEN_DECORATOR"}),
    "decorator on the test": (swap(b"def test_bench", b"@mark\ndef test_bench"), {"FORBIDDEN_DECORATOR"}),
    "decorated async def": (with_top("@mark\nasync def h():\n    pass\n"), {"FORBIDDEN_ASYNC_FUNCTION", "FORBIDDEN_DECORATOR"}),
}


@pytest.mark.parametrize("source, expected", list(FORBIDDEN_CASES.values()), ids=list(FORBIDDEN_CASES))
def test_forbidden_construct(source, expected):
    assert codes(source) == expected


# --- Imports ---

@pytest.mark.parametrize(
    "line",
    ["import pytest", "from pytest import fixture", "import string", "from string import Formatter", "import time",
     "import os", "import sys", "import os.path", "from os import path", "import subprocess", "import importlib",
     "import builtins", "import ctypes", "import third_party", "import _pytest"],
)
def test_import_not_allowed(line):
    assert codes(with_imports(line)) == {"IMPORT_NOT_ALLOWED"}


def test_repo_top_level_membership():
    source = with_imports("import lib.thing")
    assert lint(source, tops=frozenset({"app", "lib"})) == []
    assert codes(source) == {"IMPORT_NOT_ALLOWED"}
    assert codes(with_imports("from lib import thing")) == {"IMPORT_NOT_ALLOWED"}
    assert lint(with_imports("import app.orders as orders_module")) == []


def test_stdlib_name_wins_over_a_repo_top_level_and_pytest_is_always_rejected():
    for module in ("os", "string", "pytest", "_pytest"):
        assert codes(with_imports(f"import {module}"), tops=frozenset({"app", module})) == {"IMPORT_NOT_ALLOWED"}
    assert lint(with_imports("import os", "import sys", "import time", "import pytest")) == ["IMPORT_NOT_ALLOWED"]


# --- Banned names and dunders ---

BANNED = ["eval", "exec", "compile", "__import__", "getattr", "setattr", "hasattr", "delattr", "open", "globals",
          "locals", "vars", "dir", "breakpoint", "input"]
PLAIN_BANNED = [name for name in BANNED if not name.startswith("__")]


def test_banned_name_set_is_the_design_list():
    assert bg._BANNED_NAMES == frozenset(BANNED)


@pytest.mark.parametrize("template", ["    {}\n", "    build_report.{}\n"], ids=["as a Name", "as an Attribute"])
@pytest.mark.parametrize(
    "name, expected",
    [(n, {"BANNED_NAME"}) for n in PLAIN_BANNED]
    + [(n, {"DUNDER_NAME"}) for n in ("__builtins__", "__class__", "__globals__", "__dict__", "__subclasses__", "__code__")],
)
def test_banned_name_and_dunder_as_a_name_or_attribute(template, name, expected):
    assert codes(with_body(template.format(name) + DIGEST_PRINT)) == expected


def test_dunder_function_and_parameter_names_are_rejected_but_strings_and_underscores_are_fine():
    assert codes(with_top("def __getattr__(name):\n    return 1\n")) == {"DUNDER_NAME"}
    assert codes(with_top("def helper(__x__):\n    return __x__\n")) == {"DUNDER_NAME"}
    assert codes(with_top("def f(__x__):\n    pass\n")) == {"DUNDER_NAME"}  # unused: only the parameter name gives it away
    assert lint(with_top('NOTE = "__builtins__ and getattr are only words"\n_private = 1\nname__ = 2\n__ = 3\n____ = 4\n')) == []


# --- Exactly one parameterless module-level test function ---

TEST_NAME_CASES = {
    "no test function": (swap(b"def test_bench", b"def bench_one"), {"TEST_NAME_COUNT"}),
    "two test functions": (with_top("def test_other():\n    return 1\n"), {"TEST_NAME_COUNT"}),
    "redefined test function": (with_top("def test_bench():\n    return 1\n"), {"TEST_NAME_COUNT"}),
    "test-prefixed constant": (with_top("test_data = [1, 2]\n"), {"TEST_NAME_COUNT"}),
    "tuple targets": (with_top("test_a, test_b = 1, 2\n"), {"TEST_NAME_COUNT"}),
    "import as test_": (with_imports("import json as test_json"), {"TEST_NAME_COUNT"}),
    "from-import as test_": (with_imports("from json import dumps as test_dumps"), {"TEST_NAME_COUNT"}),
    "from-import of test_": (with_imports("from json import test_thing"), {"TEST_NAME_COUNT"}),
    "if-nested assignment": (with_top("LIMIT = 1\nif LIMIT:\n    test_flag = 1\n"), {"TEST_NAME_COUNT"}),
    "for target": (with_top("for test_i in range(2):\n    pass\n"), {"TEST_NAME_COUNT"}),
    "walrus": (with_top("while (test_w := 0):\n    pass\n"), {"TEST_NAME_COUNT"}),
    "walrus in a comprehension": (with_top("XS = [(test_w := x) for x in range(2)]\n"), {"TEST_NAME_COUNT"}),
    "walrus in a default": (with_top("def helper(x=(test_h := 1)):\n    return x\n"), {"TEST_NAME_COUNT"}),
    # Annotations and defaults run in the enclosing scope (annotations at def time on 3.12 and 3.13).
    # Nested walruses the compiler resolves; every one of these collected two tests under pytest on 3.12 and 3.14.
    "walrus in a comprehension that is another comprehension's first iterable": (
        # Python's symtable refuses a walrus anywhere in a comprehension iterable, so this can never run (both
        # 3.12 and 3.14); `ast.parse` accepts it and only the compile step knows.
        with_top("XS = [i for i in [(test_b := 1) for _ in range(1)]]\n"), {"PARSE_FAILED"}
    ),
    "walrus in a generator expression (binds through STORE_GLOBAL)": (
        with_top("XS = list((test_g := x) for x in range(2))\n"), {"TEST_NAME_COUNT"}
    ),
    "pytest_ hook function": (
        # A module-level hook makes pytest run the single test three times, printing three digests.
        with_top("def pytest_generate_tests(metafunc):\n    metafunc.parametrize([], [(), (), ()])\n"),
        {"TEST_NAME_COUNT"},
    ),
    "del of a name a (dead) nested walrus made global (DELETE_GLOBAL)": (
        with_top("if 0:\n    list((test_bench := i) for i in [0])\ndel test_bench\n"), {"TEST_NAME_COUNT"}
    ),
    "pytest_ assignment": (with_top("pytest_plugins = []\n"), {"TEST_NAME_COUNT"}),
    "pytestmark": (with_top("pytestmark = []\n"), {"TEST_NAME_COUNT"}),
    "Test* name collected as a class": (with_imports("from app.orders import TestThing"), {"TEST_NAME_COUNT"}),
    "walrus two code objects deep": (
        with_top("x = z = []\nXS = list((list(((test_a := 1) for _ in x)) for y in z))\n"), {"TEST_NAME_COUNT"}
    ),
    "walrus in a keyword-only default": (with_top("def _a(*, k=(test_kw := f)):\n    pass\n"), {"TEST_NAME_COUNT"}),
    "testforged is a test name too (prefix is test, not test_)": (with_top("testforged = f\n"), {"TEST_NAME_COUNT"}),
    "def testforged": (with_top("def testforged():\n    pass\n"), {"TEST_NAME_COUNT"}),
    "match star capture": (with_top("LIMIT = 1\nmatch LIMIT:\n    case [*test_m]:\n        pass\n"), {"TEST_NAME_COUNT"}),
    "match mapping rest": (with_top("LIMIT = 1\nmatch LIMIT:\n    case {**test_m}:\n        pass\n"), {"TEST_NAME_COUNT"}),
    "del of the test name": (with_top("del test_bench\n"), {"TEST_NAME_COUNT"}),
    "walrus in a comprehension if clause": (
        with_top("XS = [x for x in range(3) if (test_w := x)]\n"), {"TEST_NAME_COUNT"}
    ),
    "match capture": (with_top("LIMIT = 1\nmatch LIMIT:\n    case test_m:\n        pass\n"), {"TEST_NAME_COUNT"}),
    "only name is an assignment": (
        swap(b"def test_bench():", b"def helper_bench():") + b"\ntest_bench = helper_bench\n", {"TEST_NOT_FUNCTION"}
    ),
    "only name is an import": (
        swap(b"import hashlib\n", b"import hashlib\nfrom json import dumps as test_bench\n",
             swap(b"def test_bench():", b"def helper_bench():")),
        {"TEST_NOT_FUNCTION"},
    ),
    "only test is nested in an if": (
        swap(b"def test_bench():\n", b"LIMIT = 1\nif LIMIT:\n  def test_bench():\n").replace(b"    ", b"      "),
        {"TEST_NOT_FUNCTION"},
    ),
}


@pytest.mark.parametrize(
    "signature",
    ["(a: (test_z := f))", "(a: (test_z := f), /)", "() -> (test_z := f)", "(*a: (test_z := f))",
     "(**k: (test_z := f))", "(*, k: (test_z := f))"],
)
def test_walrus_in_an_annotation_never_hides_a_second_test_name(signature):
    # Without `from __future__ import annotations` this runs at def time on 3.12/3.13 and binds `test_z`; Python
    # 3.14 refuses to compile the walrus, which is a rejection too (PARSE_FAILED).
    result = lint(NO_FUTURE + f"\n\ndef _a{signature}:\n    pass\n".encode())
    if sys.version_info < (3, 14):  # strict: an inherited `from __future__ import annotations` would hide the bind
        assert result == ["TEST_NAME_COUNT"]
    else:
        assert result in (["TEST_NAME_COUNT"], ["PARSE_FAILED"])


@pytest.mark.parametrize("source, expected", list(TEST_NAME_CASES.values()), ids=list(TEST_NAME_CASES))
def test_test_name_rules(source, expected):
    assert codes(source) == expected


@pytest.mark.parametrize("signature", ["x", "x=1", "*args", "**kwargs", "*, x", "*, x=1", "x, /", "self"])
def test_test_function_with_parameters(signature):
    assert codes(swap(b"def test_bench():", f"def test_bench({signature}):".encode())) == {"TEST_HAS_PARAMETERS"}


# --- Required elements ---

def test_missing_print():
    assert codes(swap(b"    print(", b"    str(")) == {"MISSING_PRINT"}
    assert codes(swap(b"    print(", b"    build_report.print(")) == {"MISSING_PRINT"}  # an Attribute is not print()
    assert codes(swap(b"    print(", b"    str((print, ").replace(b"_digest(result))", b"_digest(result)))")) == {"MISSING_PRINT"}


def test_missing_digest_literal():
    for replacement in (b'"RESULT_DIGEST: "', b'"BENCH_RESULT_DIGEST:"', b'"bench_result_digest: "', b'b"BENCH_RESULT_DIGEST: "'):
        assert codes(swap(b'"BENCH_RESULT_DIGEST: "', replacement)) == {"MISSING_DIGEST_LITERAL"}, replacement
    in_comment = swap(b'"BENCH_RESULT_DIGEST: "', b'"x"') + b"# BENCH_RESULT_DIGEST: \n"
    assert codes(in_comment) == {"MISSING_DIGEST_LITERAL"}


@pytest.mark.parametrize(
    "call",
    [b"repr(value)", b"hashlib.sha512(repr(value).encode())", b"hashlib.md5(repr(value).encode())",
     b"other.sha256(repr(value).encode())", b"(hashlib.sha256, repr(value))[1]"],
)
def test_missing_sha256_as_an_attribute_call(call):
    assert codes(swap(b"hashlib.sha256(repr(value).encode())", call)) == {"MISSING_SHA256"}


SHA256_NAME_FORMS = [
    (b"from hashlib import sha256\n", b"sha256(", True),
    (b"from hashlib import sha256 as digest_of\n", b"digest_of(", True),
    (b"", b"sha256(", False),  # called without the import
    (b"from json import sha256\n", b"sha256(", False),  # imported from another module
    (b"from hashlib import sha512\n", b"sha256(", False),  # a different name imported
    (b"from hashlib import sha512\n", b"sha512(", False),  # sha512 imported and called
    (b"from heapq import sha256\n", b"sha256(", False),  # sha256 from a module whose name merely starts with `h`
]


@pytest.mark.parametrize("imp, call, ok", SHA256_NAME_FORMS)
def test_sha256_as_a_name_call_needs_from_hashlib_import(imp, call, ok):
    source = swap(b"import hashlib\n", imp).replace(b"hashlib.sha256(", call)
    assert (lint(source) == []) is ok
    if not ok:
        assert codes(source) == {"MISSING_SHA256"}


NO_CALL = b"[build_report(i) for i in range(3)]"
SYMBOL_FORMS = {
    "Name.id": (b"import app\n", {}, True),
    "Attribute.attr": (b"import app\n", {b"build_report(i)": b"app.build_report(i)"}, True),
    "import-from alias name": (b"from app.orders import build_report\n", {NO_CALL: b"[1, 2, 3]"}, True),
    "import-from asname": (b"from app.orders import report_builder as build_report\n", {NO_CALL: b"[1]"}, True),
    "import asname": (b"import app.orders as build_report\n", {NO_CALL: b"[1]"}, True),
    "only in a string": (b"import app\n", {NO_CALL: b"['build_report']"}, False),
    "only a prefix": (b"import app\n", {b"build_report(i)": b"build_report_v2(i)"}, False),
    "absent": (b"import app\n", {NO_CALL: b"[1]"}, False),
}


@pytest.mark.parametrize("imp, edits, ok", list(SYMBOL_FORMS.values()), ids=list(SYMBOL_FORMS))
def test_symbol_reference_forms(imp, edits, ok):
    source = swap(b"from app.orders import build_report\n", imp)
    for old, new in edits.items():
        source = source.replace(old, new)
    if ok:
        assert lint(source) == []
    else:
        assert codes(source) == {"MISSING_SYMBOL_REFERENCE"}


@pytest.mark.parametrize("line", ["import app.orders", "from app.orders import helper_fn", "from app import orders"])
def test_file_level_symbol_is_satisfied_by_a_module_component(line):
    # A file-level Location yields the module stem (`orders`) as the symbol.
    source = swap(b"from app.orders import build_report\n", line.encode() + b"\n").replace(NO_CALL, b"[1, 2, 3]")
    assert lint(source, symbol="orders") == []
    assert codes(source, symbol="nowhere") == {"MISSING_SYMBOL_REFERENCE"}


@pytest.mark.parametrize("symbol", ["ab", "main", "print", "__init__", "1abc", "x" * 65, "", "build-report", None])
def test_invalid_symbol_is_a_violation_not_a_free_pass(symbol):
    assert lint(GOOD, symbol=symbol) == ["SYMBOL_INVALID"]


def test_dunder_means_both_underscores_and_a_nested_def_is_not_module_level():
    assert lint(with_top("def h(__private):\n    return __private\n")) == []
    assert lint(with_top("def h():\n    def test_x():\n        return 1\n    return test_x\n")) == []
    assert lint(with_top("def h():\n    test_x = 1\n    del test_x\n")) == []
    assert lint(with_top("def f(a: int, *r: int, k: int = 1, **kw: int) -> int:\n    return a\n")) == []  # honest annotations


# --- Names that are only strings in the AST (no Name or Attribute node says so) ---

MY_TOPS = frozenset({"app", "mypkg"})


def _match(pattern: str) -> bytes:
    return with_top(f"def h(fib):\n    match fib:\n        case {pattern}:\n            return 1\n")


STRING_NAME_CASES = {
    "from-import dunder as alias (eval via __builtins__)": (
        with_imports("from json import __builtins__ as bb") + b"\n\ndef h():\n    return bb['eval']('6*7')\n",
        {"DUNDER_NAME"},
    ),
    "import as dunder": (with_imports("import json as __builtins__"), {"DUNDER_NAME"}),
    "from-import banned as alias": (with_imports("from mypkg import open as o"), {"BANNED_NAME"}),
    "stdlib from-import of a banned name": (with_imports("from re import compile"), {"BANNED_NAME"}),
    "dunder module component": (with_imports("import mypkg.__main__"), {"DUNDER_NAME"}),
    "dunder from-module component": (with_imports("from mypkg.__main__ import thing"), {"DUNDER_NAME"}),
    "banned first component of a plain import": (with_imports("import open"), {"BANNED_NAME", "IMPORT_NOT_ALLOWED"}),
    "banned asname of a plain import": (with_imports("import json as eval"), {"BANNED_NAME"}),
    "banned asname of a from-import": (with_imports("from json import loads as eval"), {"BANNED_NAME"}),
    "dunder in the middle of a dotted import": (with_imports("import mypkg.__x__.sub"), {"DUNDER_NAME"}),
    "dunder first component of a dotted import": (
        with_imports("import __x__.mypkg"), {"DUNDER_NAME", "IMPORT_NOT_ALLOWED"}
    ),
    "class pattern dunder attribute": (_match("object(__globals__=g)"), {"DUNDER_NAME"}),
    "class pattern banned attribute": (_match("object(open=o)"), {"BANNED_NAME"}),
    "match as-capture banned": (_match("int() as open"), {"BANNED_NAME"}),
    "match star capture banned": (_match("[*open]"), {"BANNED_NAME"}),
    "match mapping rest banned": (_match("{**open}"), {"BANNED_NAME"}),
    "relative import": (with_imports("from . import orders"), {"RELATIVE_IMPORT"}),
    "relative import of a submodule": (with_imports("from ..app.orders import build_report"), {"RELATIVE_IMPORT"}),
    "star import": (with_imports("from json import *"), {"STAR_IMPORT"}),
    "star import from the repo": (with_imports("from app.orders import *"), {"STAR_IMPORT"}),
    "relative star import": (with_imports("from . import *"), {"RELATIVE_IMPORT", "STAR_IMPORT"}),
    "string.Formatter route (only `import string` gives it away)": (
        swap(b"import hashlib\n", b"import hashlib\nimport string\n", with_body(
            '    string.Formatter().get_field("0.__globals__", (build_report,), {})\n' + DIGEST_PRINT)),
        {"IMPORT_NOT_ALLOWED"},
    ),
    "__import__ call": (with_body('    __import__("os")\n' + DIGEST_PRINT), {"BANNED_NAME", "DUNDER_NAME"}),
    "re.compile": (with_imports("import re") + b"\nPATTERN = re.compile('x')\n", {"BANNED_NAME"}),
    "TypeVar name": (with_top("def h[__t__](x):\n    return x\n"), {"DUNDER_NAME"}),
    "ParamSpec name": (with_top("def h[**__p__](x):\n    return x\n"), {"DUNDER_NAME"}),
    "TypeVarTuple name": (with_top("def h[*__t__](x):\n    return x\n"), {"DUNDER_NAME"}),
}


@pytest.mark.parametrize("source, expected", list(STRING_NAME_CASES.values()), ids=list(STRING_NAME_CASES))
def test_names_spelled_only_as_strings_are_rejected(source, expected):
    assert codes(source, tops=MY_TOPS) == expected


@pytest.mark.parametrize("builtin", sorted(n for n in bg._BANNED_NAMES if not n.startswith("__")))
def test_a_banned_name_in_a_module_path_binds_nothing_and_is_accepted(builtin):
    # `import a.b` binds only `a` and `from a.b import c` only `c`: `mypkg.open` is an honest module path.
    source = with_imports(f"import mypkg.{builtin} as m", f"import mypkg.{builtin}.sub", f"from mypkg.{builtin} import render")
    assert lint(source, tops=MY_TOPS) == []


def test_a_banned_first_component_is_only_flagged_when_it_is_the_bound_name():
    tops = frozenset({"app", "compile"})
    assert lint(with_imports("import compile as m", "import compile.parser as p"), tops=tops) == []
    assert codes(with_imports("import compile"), tops=tops) == {"BANNED_NAME"}
    assert codes(with_imports("import compile.parser"), tops=tops) == {"BANNED_NAME"}
    assert codes(with_imports("import compile.parser as eval"), tops=tops) == {"BANNED_NAME"}  # the asname is bound


def test_symbol_named_like_a_banned_builtin_is_satisfiable_through_a_module_path():
    # benchmark_symbol_from_location("src/app/open.py") is `open`; the benchmark must still be writable.
    source = with_imports("from app.open import go").replace(b"build_report(i)", b"go(i)")
    assert lint(source, symbol="open") == []


def test_honest_import_and_match_forms_are_not_rejected():
    for imports in ("from json import loads as x", "import json", "import json.decoder"):
        assert lint(with_imports(imports)) == []
    assert lint(_match("int() as number")) == [] and lint(_match("object(real=g)")) == []
    assert lint(with_top("def h[T](x: T) -> T:\n    return x\n")) == []


# --- Star imports, async constructs, and a repo_top_levels that must not fail open ---

STDLIB_ONLY = swap(b"from app.orders import build_report\n", b"").replace(b"build_report(i)", b"i")


class _AlwaysTrue:
    def __contains__(self, item):
        return True


class _FrozenSub(frozenset):
    pass


BAD_TOP_LEVELS = [
    "app", ["app"], ("app",), {"app": 1}, None, 5, _AlwaysTrue(), {"app", 5}, frozenset({b"app"}), _FrozenSub({"app"}),
    iter(["app"]),
]


@pytest.mark.parametrize("tops", BAD_TOP_LEVELS, ids=[type(t).__name__ for t in BAD_TOP_LEVELS])
def test_malformed_repo_top_levels_never_fail_open(tops):
    # Even a stdlib-only source: the argument is rejected before anything else is looked at.
    assert lint(STDLIB_ONLY, symbol="_digest", tops=tops) == ["ANALYSIS_FAILED"]
    assert lint(with_imports("import app"), tops=tops) == ["ANALYSIS_FAILED"]


def test_a_set_or_frozenset_of_str_is_accepted_as_repo_top_levels():
    assert lint(STDLIB_ONLY, symbol="_digest", tops=frozenset()) == []
    assert lint(GOOD, tops={"app"}) == lint(GOOD, tops=frozenset({"app"})) == []


def test_parse_failed_and_analysis_failed_are_distinct(monkeypatch):
    def boom(*args, **kwargs):
        raise RecursionError("maximum recursion depth exceeded")

    monkeypatch.setattr(ast, "parse", boom)
    assert lint(GOOD) == ["PARSE_FAILED"]
    monkeypatch.undo()
    monkeypatch.setattr(bg, "_module_level_names", lambda code: 1 / 0)
    assert lint(GOOD) == ["ANALYSIS_FAILED"]


@pytest.mark.parametrize(
    "target",
    ["slot[[(test_e := noop) for _ in [0]][0]]", "slot[[(test_e := noop) for _ in [0]][0]].attr",
     "(i, slot[[(test_e := noop) for _ in [0]][0]])", "slot[[(test_e := noop) for _ in [0]][0]:2]"],
)
def test_walrus_nested_inside_a_comprehension_target_is_counted(target):
    # Every shape collected two tests under pytest on 3.12 and 3.14; the compiler, not an AST walk, decides.
    assert codes(with_top(f"slot = {{}}\n[0 for {target} in [(1, 2)]]\n")) == {"TEST_NAME_COUNT"}


def test_pytest_collected_names_count_but_constants_and_locals_do_not():
    assert lint(with_top("TEST_SIZE = 5\n")) == [] and lint(with_top("def h():\n    pytest_x = 1\n    return pytest_x\n")) == []
    assert lint(swap(b"def test_bench", b"def testbench")) == []  # a lone `test*` name needs no underscore


def _nested_comprehension(depth: int, kind: str = "[{}]") -> str:
    inner = "1"
    for _ in range(depth):
        inner = kind.format(f"{inner} for a in [1]")
    return inner


@pytest.mark.parametrize("kind", ["[{}]", "({})", "{{{}}}", "{{1: {}}}"], ids=["list", "generator", "set", "dict"])
def test_comprehension_nesting_cap_boundary(kind):
    cap = bg._MAX_COMPREHENSION_DEPTH
    assert cap == 12  # well below the depth (about 20) at which CPython's compiler crashes
    assert lint(GOOD + f"x = {_nested_comprehension(cap, kind)}\n".encode()) == []
    assert lint(GOOD + f"x = {_nested_comprehension(cap + 1, kind)}\n".encode()) == ["PARSE_FAILED"]
    assert lint(with_top(f"x = {_nested_comprehension(3, kind)}\n")) == []  # honest nesting stays accepted


def _lint_in_subprocess(tmp_path, source: bytes, prelude: str = ""):
    """Run the lint CLI in a child interpreter (so a crash cannot take pytest down); `prelude` runs first."""
    path = tmp_path / "bench_child.py"
    path.write_bytes(source)
    script = (
        prelude + "import importlib.util, sys\n"
        "spec = importlib.util.spec_from_file_location('benchmark_gate', sys.argv[1])\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "sys.modules['benchmark_gate'] = module\n"
        "spec.loader.exec_module(module)\n"
        "sys.exit(module.main(['lint', '--benchmark', sys.argv[2], '--symbol', 'build_report', '--top-level', 'app']))\n"
    )
    run = subprocess.run([sys.executable, "-c", script, str(_SCRIPTS / "benchmark_gate.py"), str(path)],
                         capture_output=True, text=True, timeout=60, check=False)
    return run.returncode, run.stdout.split(), run.stderr


@pytest.mark.parametrize("depth", [22, 23, 60])
@pytest.mark.parametrize("flavour", ["list", "async"])
def test_deeply_nested_comprehensions_do_not_crash_the_interpreter(tmp_path, depth, flavour):
    # CPython's compiler SIGSEGVs on ~23 nested comprehensions (20 async) after `ast.parse` succeeds.
    nested = _nested_comprehension(depth)
    text = f"x = {nested}\n" if flavour == "list" else f"async def h():\n    return {nested.replace('for a', 'async for a')}\n"
    code, out, _ = _lint_in_subprocess(tmp_path, GOOD + text.encode())
    assert code == 1 and out in (["PARSE_FAILED"], ["FORBIDDEN_ASYNC_FUNCTION"])


def test_a_rejected_source_is_not_compiled_so_a_lambda_chain_is_fast():
    names = [f"{chr(97 + i % 26)}{i // 26}" if i >= 26 else chr(97 + i) for i in range(1000)]
    chain = "x = " + "".join(f"lambda {n}:" for n in names) + "(" + ",".join(names) + ")\n"
    start = time.perf_counter()
    result = lint(GOOD + chain.encode())
    assert result == ["FORBIDDEN_LAMBDA"] and len(chain) < 15000
    assert time.perf_counter() - start < 1.0  # compile alone took 8 to 11 s on 3.12


@pytest.mark.parametrize("digits, expected", [(3500, []), (3700, ["PARSE_FAILED"])])
def test_huge_integer_literal_dis_cannot_render_is_parse_failed(digits, expected):
    # 3700 hex digits is more than 4300 decimal digits, which `dis` cannot repr (ValueError).
    assert lint(GOOD + b"x = 0x" + b"f" * digits + b"\n") == expected


def test_a_syntax_warning_neither_changes_the_verdict_nor_prints():
    source = with_imports("import re") + b'\nPAT = re.findall("\\d+", "a1")\n'  # non-raw "\d": SyntaxWarning
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        default = lint(source)
        warnings.simplefilter("error")
        strict = lint(source)
    assert default == strict == [] and caught == []


# --- Honest benchmarks must stay accepted ---

def _honest(imports: str, body: str) -> bytes:
    return f"{imports}\n\ndef test_bench():\n{body}".encode()


HONEST = {
    "fib loop": (
        _honest("import hashlib\nfrom app.maths import fib",
                "    values = []\n    for n in range(20):\n        values.append(fib(n))\n"
                '    print("BENCH_RESULT_DIGEST: " + hashlib.sha256(repr(values).encode()).hexdigest())\n'),
        "fib",
    ),
    "sqlite3 N+1 fixture": (
        _honest("import hashlib\nimport sqlite3\nfrom app.orders import load_orders",
                '    conn = sqlite3.connect(":memory:")\n    conn.execute("CREATE TABLE t (id INTEGER, v INTEGER)")\n'
                '    conn.executemany("INSERT INTO t VALUES (?, ?)", [(i, i * 2) for i in range(100)])\n'
                '    rows = [conn.execute("SELECT v FROM t WHERE id = ?", (i,)).fetchone()[0] for i in range(100)]\n'
                '    conn.close()\n    print("BENCH_RESULT_DIGEST: " + hashlib.sha256(repr((rows, load_orders)).encode()).hexdigest())\n'),
        "load_orders",
    ),
    "from hashlib import sha256 with Counter": (
        _honest("from collections import Counter\nfrom hashlib import sha256\nfrom app.text import word_count",
                '    counts = Counter(word_count("a b a c"))\n'
                '    print("BENCH_RESULT_DIGEST: " + sha256(repr(sorted(counts.items())).encode()).hexdigest())\n'),
        "word_count",
    ),
    "lru_cache call form": (
        _honest("import functools\nimport hashlib\nfrom app.maths import fib",
                "    cached = functools.lru_cache(maxsize=None)(fib)\n"
                '    print("BENCH_RESULT_DIGEST: " + hashlib.sha256(repr(cached(25)).encode()).hexdigest())\n'),
        "fib",
    ),
    "from json import loads as x": (
        _honest("import hashlib\nfrom json import loads as x\nfrom app.orders import build_report",
                '    rows = x("[1, 2]") + [build_report(1)]\n'
                '    print("BENCH_RESULT_DIGEST: " + hashlib.sha256(repr(rows).encode()).hexdigest())\n'),
        "build_report",
    ),
}


@pytest.mark.parametrize("source, symbol", list(HONEST.values()), ids=list(HONEST))
def test_honest_benchmark_idioms_stay_accepted(source, symbol):
    assert lint(source, symbol=symbol) == []


# --- Output contract: de-duplicated, deterministic, canonical order, stable code set ---

def test_codes_are_deduplicated_deterministic_and_canonically_ordered():
    source = b"import os\nimport sys\nclass A:\n    pass\nclass B:\n    pass\nx = lambda: eval(__builtins__)\n"
    first = lint(source)
    assert first == lint(source) == lint(bytes(source))
    assert len(first) == len(set(first))
    assert first == sorted(first, key=bg.VIOLATION_CODES.index)


def test_documented_code_set_is_exactly_this():
    assert bg.VIOLATION_CODES == tuple(
        """SOURCE_NOT_BYTES FILE_TOO_LARGE NON_ASCII_SOURCE ENCODING_REJECTED PARSE_FAILED ANALYSIS_FAILED SYMBOL_INVALID
        FORBIDDEN_CLASS FORBIDDEN_ASYNC_FUNCTION FORBIDDEN_LAMBDA FORBIDDEN_TRY FORBIDDEN_WITH FORBIDDEN_GLOBAL
        FORBIDDEN_NONLOCAL FORBIDDEN_DECORATOR RELATIVE_IMPORT STAR_IMPORT IMPORT_NOT_ALLOWED BANNED_NAME DUNDER_NAME
        TEST_NAME_COUNT TEST_NOT_FUNCTION TEST_HAS_PARAMETERS MISSING_PRINT MISSING_DIGEST_LITERAL MISSING_SHA256
        MISSING_SYMBOL_REFERENCE""".split()
    )


def test_stdlib_allowlist_is_the_design_list_and_is_stdlib():
    assert bg._STDLIB_IMPORT_ALLOWLIST == frozenset(
        {"__future__", "hashlib", "json", "math", "statistics", "itertools", "functools", "collections", "re",
         "decimal", "fractions", "heapq", "bisect", "copy", "random", "io", "enum", "sqlite3"}
    )
    assert bg._STDLIB_IMPORT_ALLOWLIST <= sys.stdlib_module_names


# --- CLI: lint ---

def _lint_cli(tmp_path, capsys, source, *extra, symbol=SYMBOL):
    path = tmp_path / "bench_orders.py"
    path.write_bytes(source)
    code = bg.main(["lint", "--benchmark", str(path), "--symbol", symbol, *extra])
    return code, capsys.readouterr()


def test_cli_exit_codes_and_output_for_clean_and_violating_sources(tmp_path, capsys):
    code, cap = _lint_cli(tmp_path, capsys, GOOD, "--top-level", "app")
    assert (code, cap.out, cap.err) == (0, "", "")
    code, cap = _lint_cli(tmp_path, capsys, with_imports("import os") + b"\nclass A:\n    pass\n", "--top-level", "app")
    assert (code, cap.out) == (1, "FORBIDDEN_CLASS\nIMPORT_NOT_ALLOWED\n")  # one code per line, canonical order
    code, cap = _lint_cli(tmp_path, capsys, GOOD)  # no top levels given: only the stdlib allowlist passes
    assert (code, cap.out) == (1, "IMPORT_NOT_ALLOWED\n")


def test_cli_repo_root_derives_top_levels_and_combines_with_top_level(tmp_path, capsys):
    root = tmp_path / "repo"
    (root / "app").mkdir(parents=True)
    (root / "src" / "lib").mkdir(parents=True)
    (root / "single.py").write_text("x = 1\n", encoding="utf-8")
    (root / "notes.txt").write_text("x", encoding="utf-8")
    (root / "bad-name").mkdir()
    assert bg._repo_top_levels(root) == {"app", "lib", "single", "src"}
    code, cap = _lint_cli(tmp_path, capsys, with_imports("import lib", "import single"), "--repo-root", str(root))
    assert (code, cap.out) == (0, "")
    code, cap = _lint_cli(tmp_path, capsys, with_imports("import bad_name"), "--repo-root", str(root))
    assert (code, cap.out) == (1, "IMPORT_NOT_ALLOWED\n")
    code, cap = _lint_cli(tmp_path, capsys, with_imports("import extra"), "--repo-root", str(root), "--top-level", "extra")
    assert (code, cap.out) == (0, "")


def test_cli_repo_root_ignores_non_ascii_names_without_crashing(tmp_path, capsys):
    root = tmp_path / "repo"
    (root / "app").mkdir(parents=True)
    (root / "café").mkdir()
    (root / "café.py").write_text("x = 1\n", encoding="utf-8")
    (root / "pkg.py").mkdir()  # a directory named like a module is no module: `pkg` is not a top-level name
    assert bg._repo_top_levels(root) == {"app"}
    code, cap = _lint_cli(tmp_path, capsys, GOOD, "--repo-root", str(root))
    assert (code, cap.out) == (0, "")
    non_ascii_root = tmp_path / "répô"  # the --repo-root path itself is non-ASCII
    (non_ascii_root / "app").mkdir(parents=True)
    code, cap = _lint_cli(tmp_path, capsys, GOOD, "--repo-root", str(non_ascii_root))
    assert (code, cap.out) == (0, "")


@pytest.mark.skipif(not os.path.isdir("/dev/fd"), reason="needs /dev/fd to count descriptors")
def test_read_bounded_on_a_directory_does_not_leak_a_descriptor(tmp_path):
    before = len(os.listdir("/dev/fd"))
    for _ in range(50):
        with pytest.raises(ValueError):
            bg._read_bounded(str(tmp_path), 10)
    assert len(os.listdir("/dev/fd")) == before


def test_cli_over_size_file_is_the_file_too_large_violation_after_a_bounded_read(tmp_path, capsys, monkeypatch):
    lengths = []
    real = bg.validate_benchmark_content
    monkeypatch.setattr(bg, "validate_benchmark_content", lambda s, *a: lengths.append(len(s)) or real(s, *a))
    code, cap = _lint_cli(tmp_path, capsys, b"#" * (3 * 1024 * 1024))
    assert (code, cap.out) == (1, "FILE_TOO_LARGE\n")
    assert lengths == [16 * 1024 + 1]  # never reads more than the limit plus one byte


def test_cli_unreadable_inputs_exit_2(tmp_path, capsys):
    targets = [str(tmp_path / "missing.py"), str(tmp_path), "", "a\0b"]  # missing, a directory, empty, NUL
    if hasattr(os, "mkfifo"):  # a FIFO must not hang the open
        os.mkfifo(tmp_path / "bench_fifo.py")
        targets.append(str(tmp_path / "bench_fifo.py"))
    for target in targets:
        assert bg.main(["lint", "--benchmark", target, "--symbol", SYMBOL]) == 2
    assert bg.main(["lint", "--benchmark", str(tmp_path / "x.py"), "--symbol", SYMBOL, "--repo-root", str(tmp_path / "m")]) == 2
    cap = capsys.readouterr()
    assert cap.out == "" and cap.err.count("usage error") == len(targets) + 1


def test_lint_runs_with_posix_only_os_and_signal_attributes_removed(tmp_path):
    # A Windows-like interpreter has no os.O_NONBLOCK, mkfifo, killpg or SIGALRM (catches an unguarded O_NONBLOCK).
    prelude = (
        "import os, signal\n"
        "for mod, names in ((os, ('O_NONBLOCK', 'mkfifo', 'killpg')), (signal, ('SIGALRM',))):\n"
        "    [delattr(mod, n) for n in names if hasattr(mod, n)]\n"
    )
    code, out, err = _lint_in_subprocess(tmp_path, GOOD, prelude)
    assert (code, out) == (0, []), err


def test_cli_usage_errors_exit_2(tmp_path, capsys):
    existing = tmp_path / "bench_exists.py"
    existing.write_bytes(GOOD)
    for argv in (["lint"], ["lint", "--benchmark", "x"], ["lint", "--symbol", SYMBOL], ["lint", "--benchmark"],
                 ["lint", "--benchmark", str(existing)],  # an existing file with --symbol missing is still a usage error
                 ["lint", "--benchmark", "x", "--symbol", SYMBOL, "--bogus"]):
        assert bg.main(argv) == 2, argv
    assert capsys.readouterr().out == ""


def test_cli_invalid_symbol_parse_failure_and_cookie_are_violations_not_usage_errors(tmp_path, capsys):
    code, cap = _lint_cli(tmp_path, capsys, GOOD, "--top-level", "app", symbol="main")
    assert (code, cap.out) == (1, "SYMBOL_INVALID\n")
    code, cap = _lint_cli(tmp_path, capsys, b"def (:\n")
    assert (code, cap.out) == (1, "PARSE_FAILED\n")
    code, cap = _lint_cli(tmp_path, capsys, b"# coding: latin-1\n" + GOOD, "--top-level", "app")
    assert (code, cap.out) == (1, "ENCODING_REJECTED\n")


# --- C4b review carry-overs (B2, B3, B4, B5, B7) ---

def test_cli_repo_root_must_be_an_existing_directory(tmp_path, capsys):
    bench = tmp_path / "bench_exists.py"
    bench.write_bytes(GOOD)
    plain = tmp_path / "plain.txt"
    plain.write_text("x")
    for root in (tmp_path / "missing", plain):  # the benchmark itself exists, so only --repo-root can be the cause
        assert bg.main(["lint", "--benchmark", str(bench), "--symbol", SYMBOL, "--repo-root", str(root)]) == 2
    assert capsys.readouterr().out == ""


def test_a_long_ast_clean_binop_chain_does_not_recurse():
    assert lint(GOOD + b"x = " + b"+".join([b"1"] * 3000) + b"\n") == []  # `_comprehension_depth`/`_module_level_names` stay iterative


def test_the_counted_name_must_be_the_one_top_level_def():
    # `test_a = print` is the only name the compiler binds: the def after the infinite loop is dead code and vanishes.
    hidden = swap(b"def test_bench():", b"test_a = print\nwhile 1:\n    pass\n\n\ndef test_bench():")
    assert lint(hidden) == ["TEST_NOT_FUNCTION"]
    assert lint(GOOD) == [] and lint(swap(b"def test_bench():", b"def tester_bench():")) == []


def test_symbol_must_be_an_exact_str_and_not_a_keyword():
    class AlwaysEqual(str):
        def __eq__(self, other):
            return True

        __hash__ = str.__hash__

    assert lint(GOOD, symbol=AlwaysEqual("build_report")) == ["SYMBOL_INVALID"]
    assert lint(GOOD, symbol=AlwaysEqual("zzz_not_referenced")) == ["SYMBOL_INVALID"]
    assert not bg._valid_symbol(AlwaysEqual("build_report")) and bg._valid_symbol("build_report")
    assert bg.benchmark_symbol_from_location("class") is None and bg.benchmark_symbol_from_location("app/x.py::None") is None
    assert not bg._valid_symbol("lambda") and bg._valid_symbol("match")  # soft keywords are ordinary names


def test_repo_top_levels_elements_must_be_exact_str():
    class Name(str):
        pass

    assert lint(GOOD, tops=frozenset({Name("app")})) == ["ANALYSIS_FAILED"]
    assert lint(GOOD, tops={"app"}) == []


def test_test_prefix_rule_counts_tester_but_not_tes():
    assert lint(with_top("tester = 1\n")) == ["TEST_NAME_COUNT"]  # `tester` starts with `test`: a second counted name
    assert lint(with_top("tes = 1\n")) == []
    assert lint(with_top("pytestmark = 1\n")) == ["TEST_NAME_COUNT"] and lint(with_top("TestX = 1\n")) == ["TEST_NAME_COUNT"]
    assert lint(with_top("TEST_SIZE = 1\n")) == []
