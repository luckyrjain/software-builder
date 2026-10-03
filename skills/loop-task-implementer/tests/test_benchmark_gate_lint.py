"""Tests for the C4b AST lint of `benchmark_gate.py`: `validate_benchmark_content` and the `lint` CLI.

Covers every rule in the design's `validate_benchmark_content` row and every lint case named in Rollout row 2
(`docs/superpowers/specs/2026-10-02-c4-performance-review-executor-handoff-design.md`). The lint is a tripwire;
these tests pin what it does reject and accept, not that it is exhaustive.
"""

from __future__ import annotations

import ast
import importlib.util
import os
import sys
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


def with_body(body: str) -> bytes:
    """GOOD with the test function's body replaced (the body is 4-space indented text)."""
    return GOOD.split(b"def test_bench():\n")[0] + b"def test_bench():\n" + body.encode()


# ---------------------------------------------------------------------------
# Accepted sources
# ---------------------------------------------------------------------------

def test_good_source_is_clean():
    assert lint(GOOD) == []


def test_helpers_constants_and_from_future_annotations_are_allowed():
    source = with_top("LIMIT = 3\n\n\ndef helper(x, y=2, *rest, **kw):\n    return x + y\n")
    assert lint(source) == []
    assert GOOD.startswith(b"from __future__ import annotations")


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
        "Q = [test_q for test_q in range(2)]\n"
    )
    assert lint(source) == []


@pytest.mark.parametrize(
    "body",
    [
        '    print(f"BENCH_RESULT_DIGEST: {hashlib.sha256(build_report(1)).hexdigest()}")\n',
        '    digest = hashlib.sha256(build_report(1)).hexdigest()\n    print("BENCH_RESULT_DIGEST: %s" % digest)\n',
    ],
)
def test_digest_literal_inside_an_fstring_or_format(body):
    assert lint(with_body(body)) == []


# ---------------------------------------------------------------------------
# Byte-level rules: size, ASCII, encoding cookie, parse failures
# ---------------------------------------------------------------------------

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


def test_a_bom_is_non_ascii_and_a_utf8_sig_cookie():
    assert lint(b"\xef\xbb\xbf" + GOOD) == ["NON_ASCII_SOURCE", "ENCODING_REJECTED"]


@pytest.mark.parametrize("cookie", ["latin-1", "cp037", "ascii", "utf-16", "iso-8859-15", "no-such-codec"])
def test_coding_cookie_other_than_utf8_is_rejected(cookie):
    # The bypass: an ASCII-only file declaring another codec is parsed by ast.parse(bytes) with that codec.
    assert lint(f"# -*- coding: {cookie} -*-\n".encode("ascii") + GOOD) == ["ENCODING_REJECTED"]


def test_cookie_on_the_second_line_is_honoured_too():
    assert lint(b"#!/usr/bin/env python3\n# coding: latin-1\n" + GOOD) == ["ENCODING_REJECTED"]


@pytest.mark.parametrize("cookie", ["utf-8", "UTF-8", "utf8", "utf_8", "u8", "utf-8-sig"])  # aliases of the utf-8 codec
def test_utf8_cookie_spellings_are_accepted(cookie):
    assert lint(f"# coding: {cookie}\n".encode("ascii") + GOOD) == []


@pytest.mark.parametrize(
    "source",
    [GOOD + b"\x00", swap(b"result = [", b"res\x00ult = ["), b"def (:\n", b"x = (\n"],
)
def test_parse_failures_become_a_code(source):
    assert lint(source) == ["PARSE_FAILED"]


def test_300_deep_nesting_is_a_parse_failure():
    assert lint(GOOD + b"x = " + b"(" * 300 + b"1" + b")" * 300 + b"\n") == ["PARSE_FAILED"]


@pytest.mark.parametrize("depth", [100, 1000, 5000])
@pytest.mark.parametrize("kind", ["paren", "list", "unary", "binop", "attribute"])
def test_deep_inputs_never_raise(kind, depth):
    text = {
        "paren": "(" * depth + ")" * depth,
        "list": "[" * depth + "]" * depth,
        "unary": "-" * depth + "1",
        "binop": "1 + " * depth + "1",
        "attribute": "build_report" + ".a" * depth,
    }[kind]
    result = lint(GOOD + b"x = " + text.encode() + b"\n")
    assert isinstance(result, list) and set(result) <= set(bg.VIOLATION_CODES)


def test_deep_but_parseable_tree_is_analysed_without_recursion_error():
    # The bindings walk and the lint walk are iterative: 150 nested parentheses parse and lint clean.
    assert lint(GOOD + b"x = " + b"(" * 150 + b"1" + b")" * 150 + b"\n") == []


@pytest.mark.parametrize("source", [None, "def test_x(): pass", bytearray(GOOD), memoryview(GOOD), 5, [GOOD]])
def test_non_bytes_source_is_a_code(source):
    assert lint(source) == ["SOURCE_NOT_BYTES"]


def test_bytes_subclass_is_not_trusted():
    class Sneaky(bytes):
        def isascii(self):
            return True

    assert lint(Sneaky(GOOD)) == ["SOURCE_NOT_BYTES"]


def test_hostile_arguments_never_raise():
    assert lint(GOOD, symbol=None) == ["SYMBOL_INVALID"]


# ---------------------------------------------------------------------------
# Forbidden constructs
# ---------------------------------------------------------------------------

FORBIDDEN_CASES = {
    "class": (with_top("class Helper:\n    pass\n"), {"FORBIDDEN_CLASS"}),
    "class body is not module scope": (with_top("class Helper:\n    test_attr = 1\n"), {"FORBIDDEN_CLASS"}),
    "async def": (with_top("async def helper():\n    return 1\n"), {"FORBIDDEN_ASYNC_FUNCTION"}),
    "async def test": (swap(b"def test_bench", b"async def test_bench"), {"FORBIDDEN_ASYNC_FUNCTION", "TEST_NOT_FUNCTION"}),
    "lambda": (with_top("key = lambda row: row\n"), {"FORBIDDEN_LAMBDA"}),
    "lambda-forged test": (
        with_top('test_zzz = lambda: print("BENCH_RESULT_DIGEST: " + "0" * 64)\n'),
        {"FORBIDDEN_LAMBDA", "TEST_NAME_COUNT"},
    ),
    "sorted key lambda": (with_body(DIGEST_PRINT + "    sorted([1], key=lambda x: x)\n"), {"FORBIDDEN_LAMBDA"}),
    "try/except": (
        with_body("    try:\n    " + DIGEST_PRINT + "    except ValueError:\n        pass\n"), {"FORBIDDEN_TRY"}
    ),
    "try/finally": (with_body("    try:\n    " + DIGEST_PRINT + "    finally:\n        pass\n"), {"FORBIDDEN_TRY"}),
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
    "nonlocal": (
        with_top("def outer():\n    x = 1\n\n    def inner():\n        nonlocal x\n        x = 2\n"),
        {"FORBIDDEN_NONLOCAL"},
    ),
    "decorator on a helper": (with_top("@helper_decorator\ndef other():\n    return 1\n"), {"FORBIDDEN_DECORATOR"}),
    "decorator on the test": (swap(b"def test_bench", b"@mark\ndef test_bench"), {"FORBIDDEN_DECORATOR"}),
    "autouse fixture": (
        with_top("@pytest.fixture(autouse=True)\ndef _tweak(request):\n    return request.config\n"),
        {"FORBIDDEN_DECORATOR"},
    ),
    "decorated async def": (
        with_top("@mark\nasync def helper():\n    return 1\n"), {"FORBIDDEN_ASYNC_FUNCTION", "FORBIDDEN_DECORATOR"}
    ),
}


@pytest.mark.parametrize("source, expected", list(FORBIDDEN_CASES.values()), ids=list(FORBIDDEN_CASES))
def test_forbidden_construct(source, expected):
    assert codes(source) == expected


def test_except_star_is_a_trystar_and_not_an_ast_try():
    tree = ast.parse(FORBIDDEN_CASES["except*"][0])
    assert any(isinstance(n, ast.TryStar) for n in ast.walk(tree))
    assert not any(type(n) is ast.Try for n in ast.walk(tree))


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "line",
    ["import pytest", "from pytest import fixture", "import string", "from string import Formatter", "import time",
     "import os", "import sys", "import os.path", "from os import path", "import subprocess", "import socket",
     "import importlib", "import builtins", "import inspect", "import ctypes", "import threading",
     "import third_party", "import _pytest"],
)
def test_import_not_allowed(line):
    assert codes(with_imports(line)) == {"IMPORT_NOT_ALLOWED"}


def test_string_formatter_route_is_rejected_because_string_is_not_allowlisted():
    # `string.Formatter().get_field("0.__globals__", ...)` reaches globals with no dunder Name or Attribute; only
    # the `import string` it needs gives it away.
    body = '    string.Formatter().get_field("0.__globals__", (build_report,), {})\n' + DIGEST_PRINT
    assert codes(swap(b"import hashlib\n", b"import hashlib\nimport string\n", with_body(body))) == {"IMPORT_NOT_ALLOWED"}


def test_repo_top_level_membership():
    source = with_imports("import lib.thing")
    assert lint(source, tops=frozenset({"app", "lib"})) == []
    assert codes(source) == {"IMPORT_NOT_ALLOWED"}
    assert codes(with_imports("from lib import thing")) == {"IMPORT_NOT_ALLOWED"}
    assert lint(with_imports("import app.orders as orders_module")) == []


def test_stdlib_name_wins_over_a_repo_top_level_and_pytest_is_always_rejected():
    for module in ("os", "string", "pytest", "_pytest"):
        assert codes(with_imports(f"import {module}"), tops=frozenset({"app", module})) == {"IMPORT_NOT_ALLOWED"}


@pytest.mark.parametrize(
    "line",
    ["from . import orders", "from .orders import build_report", "from .. import app", "from ..app.orders import build_report"],
)
def test_relative_imports_are_rejected(line):
    assert codes(with_imports(line)) == {"RELATIVE_IMPORT"}


def test_several_bad_imports_are_one_code():
    assert lint(with_imports("import os", "import sys", "import time", "import pytest")) == ["IMPORT_NOT_ALLOWED"]


# ---------------------------------------------------------------------------
# Banned names and dunders
# ---------------------------------------------------------------------------

BANNED = ["eval", "exec", "compile", "__import__", "getattr", "setattr", "hasattr", "delattr", "open", "globals",
          "locals", "vars", "dir", "breakpoint", "input"]
PLAIN_BANNED = [name for name in BANNED if not name.startswith("__")]


def test_banned_name_set_is_the_design_list():
    assert bg._BANNED_NAMES == frozenset(BANNED)


@pytest.mark.parametrize("name", PLAIN_BANNED)
def test_banned_name_as_a_name(name):
    assert codes(with_body(f"    {name}\n" + DIGEST_PRINT)) == {"BANNED_NAME"}


@pytest.mark.parametrize("name", PLAIN_BANNED)
def test_banned_name_as_an_attribute(name):
    assert codes(with_body(f"    build_report.{name}\n" + DIGEST_PRINT)) == {"BANNED_NAME"}


def test_honest_idioms_the_lint_rejects():
    assert codes(with_imports("import re") + b"\nPATTERN = re.compile('x')\n") == {"BANNED_NAME"}
    assert codes(with_top("HANDLE = build_report.open\n")) == {"BANNED_NAME"}


def test_dunder_import_is_banned_and_a_dunder():
    assert codes(with_body('    __import__("os")\n' + DIGEST_PRINT)) == {"BANNED_NAME", "DUNDER_NAME"}


@pytest.mark.parametrize("name", ["__builtins__", "__class__", "__globals__", "__dict__", "__name__", "__file__"])
def test_dunder_as_a_name(name):
    assert codes(with_body(f"    {name}\n" + DIGEST_PRINT)) == {"DUNDER_NAME"}


@pytest.mark.parametrize("name", ["__builtins__", "__class__", "__globals__", "__dict__", "__subclasses__", "__code__"])
def test_dunder_as_an_attribute(name):
    assert codes(with_body(f"    build_report.{name}\n" + DIGEST_PRINT)) == {"DUNDER_NAME"}


def test_bare_builtins_name_is_rejected():
    assert codes(with_top("B = __builtins__\n")) == {"DUNDER_NAME"}


def test_dunder_function_and_parameter_names_are_rejected():
    assert codes(with_top("def __getattr__(name):\n    return 1\n")) == {"DUNDER_NAME"}
    assert codes(with_top("def helper(__x__):\n    return __x__\n")) == {"DUNDER_NAME"}


def test_dunder_in_a_string_or_a_non_dunder_underscore_name_is_fine():
    assert lint(with_top('NOTE = "__builtins__ and getattr are only words"\n_private = 1\nname__ = 2\n__ = 3\n____ = 4\n')) == []


# ---------------------------------------------------------------------------
# Exactly one parameterless module-level test function
# ---------------------------------------------------------------------------

NESTED_TEST = (
    "if LIMIT:\n  def test_bench():\n    result = [build_report(i) for i in range(3)]\n"
    '    print("BENCH_RESULT_DIGEST: " + _digest(result))\n'
)
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
    "walrus in a positional annotation": (with_top("def _a(a: (test_z := f)):\n    pass\n"), {"TEST_NAME_COUNT"}),
    "walrus in a positional-only annotation": (with_top("def _a(a: (test_z := f), /):\n    pass\n"), {"TEST_NAME_COUNT"}),
    "walrus in a return annotation": (with_top("def _a() -> (test_z := f):\n    pass\n"), {"TEST_NAME_COUNT"}),
    "walrus in a *args annotation": (with_top("def _a(*a: (test_z := f)):\n    pass\n"), {"TEST_NAME_COUNT"}),
    "walrus in a **kwargs annotation": (with_top("def _a(**k: (test_z := f)):\n    pass\n"), {"TEST_NAME_COUNT"}),
    "walrus in a keyword-only annotation": (with_top("def _a(*, k: (test_z := f)):\n    pass\n"), {"TEST_NAME_COUNT"}),
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
        GOOD.split(b"def test_bench():")[0] + b"LIMIT = 1\n" + NESTED_TEST.encode(), {"TEST_NOT_FUNCTION"}
    ),
}


@pytest.mark.parametrize("source, expected", list(TEST_NAME_CASES.values()), ids=list(TEST_NAME_CASES))
def test_test_name_rules(source, expected):
    assert codes(source) == expected


@pytest.mark.parametrize("signature", ["x", "x=1", "*args", "**kwargs", "*, x", "*, x=1", "x, /", "self"])
def test_test_function_with_parameters(signature):
    assert codes(swap(b"def test_bench():", f"def test_bench({signature}):".encode())) == {"TEST_HAS_PARAMETERS"}


# ---------------------------------------------------------------------------
# Required elements
# ---------------------------------------------------------------------------

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
    [b"repr(value)", b"hashlib.sha512(repr(value).encode())", b"other.sha256(repr(value).encode())",
     b"(hashlib.sha256, repr(value))[1]"],
)
def test_missing_sha256_as_an_attribute_call(call):
    assert codes(swap(b"hashlib.sha256(repr(value).encode())", call)) == {"MISSING_SHA256"}


SHA256_NAME_FORMS = [
    (b"from hashlib import sha256\n", b"sha256(", True),
    (b"from hashlib import sha256 as digest_of\n", b"digest_of(", True),
    (b"", b"sha256(", False),  # called without the import
    (b"from json import sha256\n", b"sha256(", False),  # imported from another module
    (b"from hashlib import sha512\n", b"sha256(", False),  # a different name imported
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
    "import dotted component": (b"import app.build_report\n", {NO_CALL: b"[1]"}, True),
    "from-module dotted component": (b"from app.build_report import helper_fn\n", {NO_CALL: b"[1]"}, True),
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


@pytest.mark.parametrize("symbol", ["ab", "main", "print", "__init__", "1abc", "x" * 65, "", "build-report"])
def test_invalid_symbol_is_a_violation_not_a_free_pass(symbol):
    assert lint(GOOD, symbol=symbol) == ["SYMBOL_INVALID"]


def test_more_required_element_forms():
    assert codes(swap(b"hashlib.sha256(repr(value).encode())", b"hashlib.md5(repr(value).encode())")) == {"MISSING_SHA256"}
    # The design says the literal is "in a string constant", not at its start.
    assert lint(swap(b'"BENCH_RESULT_DIGEST: "', b'"x BENCH_RESULT_DIGEST: "')) == []
    sha512 = swap(b"import hashlib\n", b"from hashlib import sha512\n").replace(b"hashlib.sha256(", b"sha512(")
    assert codes(sha512) == {"MISSING_SHA256"}


def test_dunder_means_both_underscores_and_a_nested_def_is_not_module_level():
    assert lint(with_top("def h(__private):\n    return __private\n")) == []
    assert lint(with_top("def h():\n    def test_x():\n        return 1\n    return test_x\n")) == []
    assert lint(with_top("def h():\n    test_x = 1\n    del test_x\n")) == []
    assert lint(with_top("def f(a: int, *r: int, k: int = 1, **kw: int) -> int:\n    return a\n")) == []  # honest annotations


# ---------------------------------------------------------------------------
# Names that are only strings in the AST (no Name or Attribute node says so)
# ---------------------------------------------------------------------------

MY_TOPS = frozenset({"app", "mypkg"})


def _match(pattern: str) -> bytes:
    return with_top(f"def h(fib):\n    match fib:\n        case {pattern}:\n            return 1\n")


STRING_NAME_CASES = {
    "from-import dunder as alias (eval via __builtins__)": (
        with_imports("from json import __builtins__ as bb") + b"\n\ndef h():\n    return bb['eval']('6*7')\n",
        {"DUNDER_NAME"},
    ),
    "from-import dunder, no alias": (with_imports("from json import __builtins__"), {"DUNDER_NAME"}),
    "import as dunder": (with_imports("import json as __builtins__"), {"DUNDER_NAME"}),
    "from-import banned as alias": (with_imports("from mypkg import open as o"), {"BANNED_NAME"}),
    "from-import banned asname only": (with_imports("from mypkg import thing as open"), {"BANNED_NAME"}),
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
    "match as-capture dunder": (_match("int() as __builtins__"), {"DUNDER_NAME"}),
    "match as-capture banned": (_match("int() as open"), {"BANNED_NAME"}),
    "match star capture banned": (_match("[*open]"), {"BANNED_NAME"}),
    "match mapping rest banned": (_match("{**open}"), {"BANNED_NAME"}),
    "TypeVar name": (with_top("def h[__t__](x):\n    return x\n"), {"DUNDER_NAME"}),
    "TypeVar banned name": (with_top("def h[open](x):\n    return x\n"), {"BANNED_NAME"}),
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


def test_symbol_named_like_a_banned_builtin_is_satisfiable_through_a_module_path():
    # benchmark_symbol_from_location("src/app/open.py") is `open`; the benchmark must still be writable.
    source = with_imports("from app.open import go").replace(b"build_report(i)", b"go(i)")
    assert lint(source, symbol="open") == []


def test_honest_import_and_match_forms_are_not_rejected():
    for imports in ("from json import loads as x", "import json", "from __future__ import annotations", "import json.decoder"):
        assert lint(with_imports(imports)) == []
    assert lint(_match("int() as number")) == [] and lint(_match("object(real=g)")) == []
    assert lint(with_top("def h[T](x: T) -> T:\n    return x\n")) == []


# ---------------------------------------------------------------------------
# Star imports, async constructs, and a repo_top_levels that must not fail open
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("line", ["from json import *", "from app.orders import *"])
def test_star_import_is_rejected(line):
    assert codes(with_imports(line)) == {"STAR_IMPORT"}
    assert codes(with_imports("from . import *")) == {"RELATIVE_IMPORT", "STAR_IMPORT"}


@pytest.mark.parametrize(
    "text", ["async with a:\n    pass\n", "async for x in y:\n    pass\n", "await z\n", "XS = [x async for x in y]\n"],
)
def test_async_constructs_outside_an_async_def_are_rejected(text):
    assert codes(with_top(text)) == {"FORBIDDEN_ASYNC_FUNCTION"}


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


def test_well_formed_repo_top_levels_are_accepted_as_set_or_frozenset():
    assert lint(STDLIB_ONLY, symbol="_digest", tops=frozenset()) == []
    assert lint(GOOD, tops={"app"}) == []
    assert lint(GOOD, tops=frozenset({"app"})) == []


def test_parse_failed_and_analysis_failed_are_distinct(monkeypatch):
    def boom(*args, **kwargs):
        raise RecursionError("maximum recursion depth exceeded")

    monkeypatch.setattr(ast, "parse", boom)
    assert lint(GOOD) == ["PARSE_FAILED"]
    monkeypatch.undo()
    monkeypatch.setattr(bg, "_module_level_bindings", boom)
    assert lint(GOOD) == ["ANALYSIS_FAILED"]


def test_a_real_parser_resource_failure_under_the_size_cap_is_parse_failed():
    # The 16 KiB cap keeps almost every deep input away from the parser's recursion limit; 16000 unary minus signs
    # still defeat it (MemoryError on 3.14, RecursionError on some versions), and must be a code, not a crash.
    source = b"x = " + b"-" * 16000 + b"1\n"
    try:
        ast.parse(source)
    except (RecursionError, MemoryError):
        assert len(source) < 16 * 1024 and lint(source) == ["PARSE_FAILED"]
    else:
        pytest.skip("this interpreter parses the expression")


# ---------------------------------------------------------------------------
# Honest benchmarks must stay accepted
# ---------------------------------------------------------------------------

HONEST = {
    "fib loop": (
        b"import hashlib\nfrom app.maths import fib\n\n\ndef _checksum(values):\n"
        b"    return hashlib.sha256(repr(values).encode()).hexdigest()\n\n\ndef test_bench():\n"
        b"    total = 0\n    values = []\n    for n in range(20):\n        total += fib(n)\n        values.append(total)\n"
        b'    print("BENCH_RESULT_DIGEST: " + _checksum(values))\n',
        "fib",
    ),
    "sqlite3 N+1 fixture": (
        b"import hashlib\nimport sqlite3\nfrom app.orders import load_orders\n\n\ndef _setup():\n"
        b'    conn = sqlite3.connect(":memory:")\n    conn.execute("CREATE TABLE t (id INTEGER, v INTEGER)")\n'
        b'    conn.executemany("INSERT INTO t VALUES (?, ?)", [(i, i * 2) for i in range(100)])\n    return conn\n\n\n'
        b"def test_bench():\n    conn = _setup()\n"
        b'    rows = [conn.execute("SELECT v FROM t WHERE id = ?", (i,)).fetchone()[0] for i in range(100)]\n'
        b'    conn.close()\n    print("BENCH_RESULT_DIGEST: " + hashlib.sha256(repr((rows, load_orders)).encode()).hexdigest())\n',
        "load_orders",
    ),
    "from hashlib import sha256 with Counter": (
        b"from collections import Counter\nfrom hashlib import sha256\nfrom app.text import word_count\n\n\n"
        b'def test_bench():\n    counts = Counter(word_count("a b a c"))\n'
        b'    print("BENCH_RESULT_DIGEST: " + sha256(repr(sorted(counts.items())).encode()).hexdigest())\n',
        "word_count",
    ),
    "lru_cache call form": (
        b"import functools\nimport hashlib\nfrom app.maths import fib\n\n\ndef test_bench():\n"
        b"    cached = functools.lru_cache(maxsize=None)(fib)\n"
        b'    print("BENCH_RESULT_DIGEST: " + hashlib.sha256(repr(cached(25)).encode()).hexdigest())\n',
        "fib",
    ),
    "from json import loads as x": (
        b"import hashlib\nfrom json import loads as x\nfrom app.orders import build_report\n\n\ndef test_bench():\n"
        b'    rows = x("[1, 2]") + [build_report(1)]\n'
        b'    print("BENCH_RESULT_DIGEST: " + hashlib.sha256(repr(rows).encode()).hexdigest())\n',
        "build_report",
    ),
}


@pytest.mark.parametrize("source, symbol", list(HONEST.values()), ids=list(HONEST))
def test_honest_benchmark_idioms_stay_accepted(source, symbol):
    assert lint(source, symbol=symbol) == []


# ---------------------------------------------------------------------------
# Output contract: de-duplicated, deterministic, canonical order, stable code set
# ---------------------------------------------------------------------------

def test_codes_are_deduplicated_deterministic_and_canonically_ordered():
    source = b"import os\nimport sys\nclass A:\n    pass\nclass B:\n    pass\nx = lambda: eval(__builtins__)\n"
    first = lint(source)
    assert first == lint(source) == lint(bytes(source))
    assert len(first) == len(set(first))
    assert first == sorted(first, key=bg.VIOLATION_CODES.index)
    assert first[0] == "FORBIDDEN_CLASS" and first[-1] == "MISSING_SYMBOL_REFERENCE"


def test_documented_code_set_is_exactly_this():
    assert bg.VIOLATION_CODES == (
        "SOURCE_NOT_BYTES", "FILE_TOO_LARGE", "NON_ASCII_SOURCE", "ENCODING_REJECTED", "PARSE_FAILED",
        "ANALYSIS_FAILED", "SYMBOL_INVALID", "FORBIDDEN_CLASS", "FORBIDDEN_ASYNC_FUNCTION", "FORBIDDEN_LAMBDA",
        "FORBIDDEN_TRY", "FORBIDDEN_WITH", "FORBIDDEN_GLOBAL", "FORBIDDEN_NONLOCAL", "FORBIDDEN_DECORATOR",
        "RELATIVE_IMPORT", "STAR_IMPORT", "IMPORT_NOT_ALLOWED", "BANNED_NAME", "DUNDER_NAME", "TEST_NAME_COUNT",
        "TEST_NOT_FUNCTION", "TEST_HAS_PARAMETERS", "MISSING_PRINT", "MISSING_DIGEST_LITERAL", "MISSING_SHA256",
        "MISSING_SYMBOL_REFERENCE",
    )


def test_every_code_is_reachable():
    reached = set()
    samples = [b"", GOOD + b"#" * 20000, GOOD + b"\xff", b"# coding: latin-1\n" + GOOD, b"def (:\n", 5]
    samples += [source for source, _ in FORBIDDEN_CASES.values()] + [source for source, _ in TEST_NAME_CASES.values()]
    samples += [with_imports("import os", "from . import x"), with_top("def helper(__a__):\n    eval(1)\n")]
    for sample in samples:
        reached.update(lint(sample))
    reached.update(lint(GOOD, symbol="ab"))
    reached.update(lint(GOOD, tops=5))
    reached.update(lint(with_imports("from json import *")))
    reached.update(lint(swap(b"def test_bench():", b"def test_bench(x):")))
    assert reached == set(bg.VIOLATION_CODES)


def test_stdlib_allowlist_is_the_design_list_and_is_stdlib():
    assert bg._STDLIB_IMPORT_ALLOWLIST == frozenset(
        {"__future__", "hashlib", "json", "math", "statistics", "itertools", "functools", "collections", "re",
         "decimal", "fractions", "heapq", "bisect", "copy", "random", "io", "enum", "sqlite3"}
    )
    assert bg._STDLIB_IMPORT_ALLOWLIST <= sys.stdlib_module_names


# ---------------------------------------------------------------------------
# CLI: lint
# ---------------------------------------------------------------------------

def _lint_cli(tmp_path, capsys, source, *extra, symbol=SYMBOL):
    path = tmp_path / "bench_orders.py"
    path.write_bytes(source)
    code = bg.main(["lint", "--benchmark", str(path), "--symbol", symbol, *extra])
    return code, capsys.readouterr()


def test_cli_clean_exits_0_with_empty_stdout(tmp_path, capsys):
    code, cap = _lint_cli(tmp_path, capsys, GOOD, "--top-level", "app")
    assert (code, cap.out, cap.err) == (0, "", "")


def test_cli_violations_exit_1_one_code_per_line_in_canonical_order(tmp_path, capsys):
    code, cap = _lint_cli(tmp_path, capsys, with_imports("import os") + b"\nclass A:\n    pass\n", "--top-level", "app")
    assert (code, cap.out) == (1, "FORBIDDEN_CLASS\nIMPORT_NOT_ALLOWED\n")


def test_cli_without_top_levels_only_the_stdlib_allowlist_passes(tmp_path, capsys):
    code, cap = _lint_cli(tmp_path, capsys, GOOD)  # GOOD imports app.orders
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


def test_cli_repo_root_that_is_not_a_directory_is_a_usage_error(tmp_path, capsys):
    code, cap = _lint_cli(tmp_path, capsys, GOOD, "--repo-root", str(tmp_path / "missing"))
    assert (code, cap.out) == (2, "")
    assert "usage error" in cap.err


def test_cli_over_size_file_is_the_file_too_large_violation_after_a_bounded_read(tmp_path, capsys, monkeypatch):
    lengths = []
    real = bg.validate_benchmark_content
    monkeypatch.setattr(bg, "validate_benchmark_content", lambda s, *a: lengths.append(len(s)) or real(s, *a))
    code, cap = _lint_cli(tmp_path, capsys, b"#" * (3 * 1024 * 1024))
    assert (code, cap.out) == (1, "FILE_TOO_LARGE\n")
    assert lengths == [16 * 1024 + 1]  # never reads more than the limit plus one byte


def test_cli_unreadable_inputs_exit_2(tmp_path, capsys):
    for target in (str(tmp_path / "missing.py"), str(tmp_path), "", "a\0b"):  # missing, a directory, empty, NUL
        assert bg.main(["lint", "--benchmark", target, "--symbol", SYMBOL]) == 2
    cap = capsys.readouterr()
    assert cap.out == "" and cap.err.count("usage error") == 4


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs POSIX FIFOs")
def test_cli_fifo_does_not_hang_and_is_a_usage_error(tmp_path, capsys):
    fifo = tmp_path / "bench_fifo.py"
    os.mkfifo(fifo)
    assert bg.main(["lint", "--benchmark", str(fifo), "--symbol", SYMBOL]) == 2
    assert capsys.readouterr().out == ""


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


def test_cli_reads_bytes_not_text(tmp_path, capsys):
    code, cap = _lint_cli(tmp_path, capsys, GOOD.replace(b"\n", b"\r\n"), "--top-level", "app")  # CRLF is ASCII
    assert (code, cap.out) == (0, "")
    code, cap = _lint_cli(tmp_path, capsys, b"\xef\xbb\xbf" + GOOD, "--top-level", "app")
    assert (code, cap.out) == (1, "NON_ASCII_SOURCE\nENCODING_REJECTED\n")
