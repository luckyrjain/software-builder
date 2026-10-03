"""Tests for the C4a core of `benchmark_gate.py` (performance-review -> loop-task-implementer, Epic C).

Covers the design's revision-5 contracts for `benchmark_symbol_from_location`, the layered
`validate_benchmark_command` (including the parity test against B3's copy), `validate_benchmark_gate`,
`evaluate_paired_samples`, `escape_diagnostic` and the `validate` CLI. See
`docs/superpowers/specs/2026-10-02-c4-performance-review-executor-handoff-design.md` (APIs table).
"""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, module)
    spec.loader.exec_module(module)
    return module


bg = _load(_SCRIPTS / "benchmark_gate.py", "benchmark_gate")

PATH = "benchmarks/bench_orders.py"
GOOD_GATE = {
    "command": f"pytest -q --no-header {PATH}",
    "benchmark_paths": [PATH],
    "benchmark_symbol": "build_report",
}


# ---------------------------------------------------------------------------
# benchmark_symbol_from_location
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "location, expected",
    [
        ("app/orders.py", "orders"),
        ("app/orders.py::build_report", "build_report"),
        ("app/orders.py::OrderService.list_orders", "list_orders"),
        ("OrderService.list_orders", "list_orders"),
        ("app/orders.py:42", "orders"),
        ("app/orders.py#L42", "orders"),
        ("app/orders.py:42:7", "orders"),
        ("app/orders.py L42", "orders"),
        ("build_report()", "build_report"),
        ("`build_report`", "build_report"),
        ("`app/orders.py::build_report`", "build_report"),
        ("app/orders.py::build_report:42", "build_report"),
        ("x" * 64, "x" * 64),
    ],
)
def test_symbol_accepted_shapes(location, expected):
    assert bg.benchmark_symbol_from_location(location) == expected


@pytest.mark.parametrize(
    "location",
    [
        "a/b/c.py#fn",  # '#fn' is not a '#L<digits>' tail, so the basename has a non-.py extension
        "app/orders.py::",
        "app/orders/__init__.py",
        "app/__main__.py",
        "lib/orders.js",
        "app/orders.pyi",
        "app/orders.PY",
        "app/orders.ts::build_report",
        "orders.js",
        "orders.pyi",
        "lib/orders.scala",
        "orders.scala",
        "orders.pyw",
        "app/orders.py:\u0664\u0662",  # Arabic-Indic digits are not a line tail (re.ASCII), so this is not .py
        "ab",  # under 3 characters
        "app/db.py",
        "x" * 65,
        "x" * 300,
        "app/ordérs.py",  # non-ASCII
        "build_répört",
        "build_report\n",
        "app/orders.py\n",
        "app/orders.py:42\n",
        "utils/",
        "/",
        "::",
        "",
        "``",
        None,
        42,
    ]
    + [f"app/{name}.py" for name in sorted(bg._SYMBOL_DENYLIST)]
    + [f"{name}()" for name in sorted(bg._SYMBOL_DENYLIST)],
)
def test_symbol_rejected_shapes(location):
    assert bg.benchmark_symbol_from_location(location) is None


def test_symbol_denylist_is_the_design_list():  # the rejected-shape cases above are generated from the set itself
    assert bg._SYMBOL_DENYLIST == frozenset(
        {"print", "hashlib", "sha256", "main", "data", "sort", "load", "list", "item", "time", "test", "bench", "run", "get", "set"}
    )


def test_symbol_known_file_extension_set_is_pinned():  # the parametrized test below iterates this set
    assert bg._KNOWN_FILE_EXTENSIONS == frozenset(
        "js jsx ts tsx pyi pyc pyw pyx pxd go rs java kt rb php c h cc cpp cs scala swift lua dart sql sh md json yaml "
        "yml toml txt html css".split()
    )


@pytest.mark.parametrize("ext", sorted(bg._KNOWN_FILE_EXTENSIONS))
def test_symbol_every_known_bare_file_extension_is_a_file_not_a_symbol(ext):
    assert bg.benchmark_symbol_from_location(f"orders.{ext}") is None
    assert bg.benchmark_symbol_from_location(f"orders.{ext.upper()}") is None  # matched casefolded


@pytest.mark.parametrize("name", sorted(n for n in bg._BANNED_NAMES if not n.startswith("__")))
def test_symbol_derived_from_a_method_or_function_named_like_a_banned_builtin_is_none(name):
    # The lint rejects these names as Name, Attribute and alias, so no benchmark could reference such a symbol.
    for location in (f"app/db.py::Database.{name}", f"app/db.py::{name}", f"Database.{name}", f"{name}()", f"`{name}`"):
        assert bg.benchmark_symbol_from_location(location) is None, location


@pytest.mark.parametrize("name", ["__eq__", "__hash__", "__mul__", "__contains__", "__iter__", "__init__", "__main__"])
def test_symbol_derived_dunder_is_none_and_the_gate_rejects_it(name):
    for location in (f"app/orders.py::Order.{name}", f"Order.{name}", f"{name}()"):
        assert bg.benchmark_symbol_from_location(location) is None, location
    assert bg.validate_benchmark_gate(_gate(benchmark_symbol=name)) == (None, "SYMBOL_REJECTED")


def test_symbol_file_level_module_stem_named_like_a_builtin_stays_derivable():
    # `src/app/open.py` -> `open` is satisfiable as a module path (`from app.open import go`), unlike a method.
    assert bg.benchmark_symbol_from_location("src/app/open.py") == "open"
    assert bg.benchmark_symbol_from_location("app/eval.py:42") == "eval"
    assert bg.validate_benchmark_gate(_gate(benchmark_symbol="open"))[1] == "OK"


def test_symbol_bare_dotted_name_with_an_unlisted_extension_is_a_dotted_symbol():
    # Documented limit: `OrderService.list_orders` must yield `list_orders`, so a bare `name.ext` whose extension is
    # not in _KNOWN_FILE_EXTENSIONS cannot be told apart from a dotted symbol. With a `/` it is always a file.
    assert bg.benchmark_symbol_from_location("config.JSON") is None  # a listed extension is matched casefolded
    assert bg.benchmark_symbol_from_location("orders.rake") == "rake"
    assert bg.benchmark_symbol_from_location("lib/orders.rake") is None


# ---------------------------------------------------------------------------
# validate_benchmark_command and the parity test against B3's validator
# ---------------------------------------------------------------------------

B3_PATH = ROOT / "skills" / "bug-diagnosis" / "tests" / "test_repro_command_validation.py"
b3 = _load(B3_PATH, "b3_repro_command_validation")

B3_BYPASSES = [
    "pytest tests/test_foo.py --junitxml=/etc/cron.d/x",
    "pytest tests/test_foo.py --cov-report=html:/home/user/.ssh/authorized_keys",
    "pytest tests/test_foo.py --cov-report=xml:/etc/cron.d/evil",
    "pytest tests/test_foo.py --basetemp=/some/dir",
    "pytest /etc/passwd",
    "pytest tests/../../etc/passwd",
    "pytest tests/test_foo.py --cov-report=html:../etc/passwd",
    "pytest tests/test_foo.py --x=y=/etc/passwd",
]
B3_POSITIVES = [
    "pytest tests/test_foo.py",
    "pytest tests/test_foo.py::test_bar",
    "pytest tests/test_a.py tests/test_b.py",
    "make test",
    "npm run test:unit",
]
CYRILLIC_COMMAND = "pytest -q benchmarks/bench_оrders.py"  # U+043E, a homoglyph of the ASCII "o"
EXTRA_CORPUS = [
    "make deploy",
    "npm run publish",
    "pytest -p x",
    "pytest -q -rA/benchmarks/test_bench_x.py",
    CYRILLIC_COMMAND,
    "pytest -q --no-header benchmarks/bench_orders.py",
    "python3 -m pytest benchmarks/bench_orders.py",
    "pytest benchmarks/bench_orders.py; rm -rf x",
    "pytest benchmarks/bench_orders.py\n",
    "",
    None,
]
CORPUS = B3_BYPASSES + B3_POSITIVES + EXTRA_CORPUS


def test_parity_patterns_and_flags_equal_b3():
    assert bg._REPRO_COMMAND_BASE.pattern == b3._REPRO_COMMAND_BASE.pattern
    assert bg._REPRO_COMMAND_BASE.flags == b3._REPRO_COMMAND_BASE.flags
    assert bg._DANGEROUS_PATH_MARKER.pattern == b3._DANGEROUS_PATH_MARKER.pattern
    assert bg._DANGEROUS_PATH_MARKER.flags == b3._DANGEROUS_PATH_MARKER.flags


def test_parity_corpus_is_read_from_b3_test_file():
    source = B3_PATH.read_text(encoding="utf-8")
    for command in B3_BYPASSES + B3_POSITIVES:
        assert command in source


@pytest.mark.parametrize("command", CORPUS, ids=[repr(c) for c in CORPUS])
def test_parity_layer1_results_identical(command):
    assert bg.validate_repro_command(command) == b3.validate_repro_command(command)


def test_parity_b3_bypasses_rejected_and_positives_accepted_by_layer1():
    assert all(bg.validate_repro_command(c) is None for c in B3_BYPASSES)
    assert all(bg.validate_repro_command(c) == c for c in B3_POSITIVES)


def test_layer1_accepts_what_layer2_must_reject():
    for command in ("make deploy", "npm run publish", "pytest -p x", "pytest -q -rA/benchmarks/test_bench_x.py"):
        assert bg.validate_repro_command(command) == command
        assert bg.validate_benchmark_command(command, "benchmarks/test_bench_x.py") == (None, "COMMAND_REJECTED")


def test_homoglyph_passes_layer1_and_is_rejected_by_layer2_ascii_equality():
    assert bg.validate_repro_command(CYRILLIC_COMMAND) == CYRILLIC_COMMAND
    assert b3.validate_repro_command(CYRILLIC_COMMAND) == CYRILLIC_COMMAND
    assert bg.validate_benchmark_command(CYRILLIC_COMMAND, "benchmarks/bench_orders.py") == (None, "COMMAND_REJECTED")
    # Even when the (non-ASCII) path is passed identically, the ASCII requirement still rejects it.
    assert bg.validate_benchmark_command(CYRILLIC_COMMAND, "benchmarks/bench_оrders.py") == (None, "COMMAND_REJECTED")


@pytest.mark.parametrize(
    "command",
    [
        f"pytest {PATH}",
        f"pytest -q {PATH}",
        f"pytest -q --no-header {PATH}",
        f"pytest --no-header -q {PATH}",
        f"python3 -m pytest {PATH}",
        f"python3 -m pytest -q {PATH}::test_bench",
        f"pytest {PATH}::test_bench_1",
    ],
)
def test_command_layer2_accepts(command):
    assert bg.validate_benchmark_command(command, PATH) == (command, "OK")


@pytest.mark.parametrize(
    "command",
    [
        f"make test {PATH}",
        f"npm test {PATH}",
        f"pytest {PATH} {PATH}",  # two positionals
        "pytest",  # no positional
        "pytest -q",
        f"pytest -x {PATH}",  # option not allowed
        f"pytest -p x {PATH}",
        f"pytest --no-header=1 {PATH}",
        f"pytest -q -rA/{PATH}",
        f"pytest {PATH}::",
        f"pytest {PATH}::1abc",
        f"pytest {PATH}::test_x::y",
        f"pytest {PATH}::test_x=1",
        f"pytest {PATH}x",
        "pytest benchmarks/other_bench.py",
        f"pytest {PATH}::test_о",  # non-ASCII identifier: Layer 1's \w admits it, Layer 2 must not
        f"pytest  {PATH}",  # double space
        f"python3 -m pytest -m {PATH}",
        f"python -m pytest {PATH}",
        f"pytest {PATH}\n",
    ],
)
def test_command_layer2_rejects(command):
    assert bg.validate_benchmark_command(command, PATH) == (None, "COMMAND_REJECTED")


def test_command_layer1_is_invoked_before_layer2():
    # Layer 2 alone would accept this (one positional, equal to the path); only Layer 1's "[\s=:-]/" marker rejects it.
    assert bg.validate_repro_command("pytest -q /abs/bench.py") is None
    assert bg.validate_benchmark_command("pytest -q /abs/bench.py", "/abs/bench.py") == (None, "COMMAND_REJECTED")


def test_command_option_is_classified_before_comparing_to_the_path():
    # A path that starts with '-' must never be accepted as a positional.
    assert bg.validate_benchmark_command("pytest -q", "-q") == (None, "COMMAND_REJECTED")
    assert bg.validate_benchmark_command("pytest --no-header", "--no-header") == (None, "COMMAND_REJECTED")


@pytest.mark.parametrize("command, path", [(None, PATH), (PATH, None), (1, PATH), (f"pytest {PATH}", "")])
def test_command_non_string_inputs_fail_closed(command, path):
    assert bg.validate_benchmark_command(command, path) == (None, "COMMAND_REJECTED")


# ---------------------------------------------------------------------------
# validate_benchmark_gate
# ---------------------------------------------------------------------------

def _gate(**overrides):
    gate = dict(GOOD_GATE)
    gate.update(overrides)
    return gate


def test_gate_defaults_are_filled_in():
    normalized, code = bg.validate_benchmark_gate(GOOD_GATE)
    assert code == "OK"
    assert normalized == {
        **GOOD_GATE,
        "warmup_runs": 1,
        "repeats": 6,
        "per_run_timeout_seconds": 80,
        "min_improvement": 0.10,
        "max_noise": 0.10,
    }
    assert (1 + 6 + 3) * 2 * 80 == 1600


def test_gate_does_not_mutate_input_or_alias_the_path_list():
    gate = _gate()
    before = json.dumps(gate, sort_keys=True)
    normalized, _ = bg.validate_benchmark_gate(gate)
    assert json.dumps(gate, sort_keys=True) == before
    assert normalized["benchmark_paths"] is not gate["benchmark_paths"]


@pytest.mark.parametrize("gate", [None, "x", [], 1, True])
def test_gate_missing(gate):
    assert bg.validate_benchmark_gate(gate) == (None, "GATE_MISSING")


@pytest.mark.parametrize("key", ["command", "benchmark_paths", "benchmark_symbol"])
def test_gate_key_missing(key):
    gate = _gate()
    del gate[key]
    assert bg.validate_benchmark_gate(gate) == (None, "KEY_MISSING")
    assert bg.validate_benchmark_gate({}) == (None, "KEY_MISSING")


def test_gate_key_unknown():
    assert bg.validate_benchmark_gate(_gate(extra=1)) == (None, "KEY_UNKNOWN")
    assert bg.validate_benchmark_gate({**_gate(), 5: 1}) == (None, "KEY_UNKNOWN")


@pytest.mark.parametrize(
    "overrides",
    [
        {"command": None},
        {"command": 5},
        {"benchmark_symbol": None},
        {"benchmark_paths": PATH},  # a string, not a list
        {"benchmark_paths": (PATH,)},
        {"benchmark_paths": [5]},
        {"warmup_runs": True},
        {"warmup_runs": 1.0},
        {"warmup_runs": "1"},
        {"repeats": True},
        {"repeats": 6.0},
        {"per_run_timeout_seconds": 80.0},
        {"per_run_timeout_seconds": True},
        {"min_improvement": True},
        {"min_improvement": "0.1"},
        {"min_improvement": Decimal("0.1")},
        {"min_improvement": Fraction(1, 10)},
        {"min_improvement": None},
        {"max_noise": True},
        {"max_noise": "0.1"},
        {"max_noise": Decimal("0.1")},
        {"max_noise": Fraction(1, 10)},
    ],
)
def test_gate_type_rejected(overrides):
    assert bg.validate_benchmark_gate(_gate(**overrides)) == (None, "TYPE_REJECTED")


@pytest.mark.parametrize(
    "path",
    [
        "benchmarks/bench_orders.pyc",
        "benchmarks/bench_orders.txt",
        "/benchmarks/bench_orders.py",
        "benchmarks\\bench_orders.py",
        "benchmarks/../benchmarks/bench_orders.py",
        "../benchmarks/bench_orders.py",
        "./benchmarks/bench_orders.py",
        "benchmarks//bench_orders.py",
        "benchmarks/./bench_orders.py",
        "benchmarks/bench_orders.py\0",
        "benchmarks/bench_orders.py\n",
        "benchmarks/bench_оrders.py",
        "benchmarks/bench orders.py",
        "benchmarks/.bench_orders.py",
        "benchmarks/-bench_orders.py",
        "bench_orders.py",  # no benchmark-ish directory
        "src/bench_orders.py",
        "benchmarks/orders.py",  # basename does not contain 'bench'
        "benchmarks/bench_orders.PY",
        "benchmarks/Bench_orders.py",
        "benchmarks/bench-orders.py",
        "benchmarks/credentials_bench.py",
        "benchmarks/id_rsa_bench.py",
        "benchmarks/kubeconfig_bench.py",
        "benchmarks/Credentials_bench.py",  # the deny list is matched casefolded (macOS filesystems fold case)
        "perf/ID_RSA/bench_a.py",
        "benchmarks/x.PEM/bench_a.py",
        ".git/benchmarks/bench_orders.py",
        ".aws/perf/bench_orders.py",
        "perf/.ssh/bench_orders.py",
        "benchmarks/" + "d/" * 100 + "bench_orders.py",
    ],
)
def test_gate_path_rejected(path):
    gate = _gate(benchmark_paths=[path], command=f"pytest {path}")
    assert bg.validate_benchmark_gate(gate) == (None, "PATH_REJECTED")


@pytest.mark.parametrize("paths", [[], [PATH, PATH], [PATH, "perf/bench_b.py"]])
def test_gate_path_list_must_hold_exactly_one_path(paths):
    assert bg.validate_benchmark_gate(_gate(benchmark_paths=paths)) == (None, "PATH_REJECTED")


@pytest.mark.parametrize(
    "path",
    [
        "benchmarks/bench_orders.py",
        "benchmarks/test_bench_orders.py",
        "benchmarks/orders_bench.py",
        "benchmarks/bench.py",
        "perf/bench_a.py",
        "performance/sub/test_bench_a1.py",
        "tests/benchmarks/bench_orders.py",
        "pkg/bench/orders_bench_v2.py",
    ],
)
def test_gate_path_accepted(path):
    normalized, code = bg.validate_benchmark_gate(_gate(benchmark_paths=[path], command=f"pytest {path}"))
    assert code == "OK" and normalized["benchmark_paths"] == [path]


def test_gate_deny_sets_match_validate_task_target():
    vtt = _load(_SCRIPTS / "validate_task_target.py", "validate_task_target_for_c4a")
    assert bg._DENIED_COMPONENTS == vtt._DENIED_COMPONENTS
    assert bg._DENIED_NAMES_EXACT == vtt._DENIED_NAMES_EXACT
    assert bg._DENIED_NAME_PREFIXES == vtt._DENIED_NAME_PREFIXES
    assert bg._DENIED_SUFFIXES == vtt._DENIED_SUFFIXES


@pytest.mark.parametrize("symbol", ["ab", "main", "print", "__init__", "1abc", "x" * 65, "build-report", "buïld", "build_report\n", ""])
def test_gate_symbol_rejected(symbol):
    assert bg.validate_benchmark_gate(_gate(benchmark_symbol=symbol)) == (None, "SYMBOL_REJECTED")


@pytest.mark.parametrize(
    "command",
    [
        "make bench",
        f"pytest -x {PATH}",
        f"pytest {PATH} --junitxml=/etc/x",
        "pytest benchmarks/bench_other.py",
        "",
    ],
)
def test_gate_command_rejected(command):
    assert bg.validate_benchmark_gate(_gate(command=command)) == (None, "COMMAND_REJECTED")


@pytest.mark.parametrize(
    "overrides",
    [
        {"warmup_runs": -1},
        {"warmup_runs": 3},
        {"repeats": 5},
        {"repeats": 2},
        {"repeats": 10},
        {"per_run_timeout_seconds": 9},
        {"per_run_timeout_seconds": 301},
        {"min_improvement": 0.049},
        {"min_improvement": 0.91},
        {"min_improvement": 0},
        {"min_improvement": float("nan")},
        {"min_improvement": float("inf")},
        {"max_noise": 0.019},
        {"max_noise": 0.31},
        {"max_noise": float("-inf")},
        {"max_noise": float("nan")},
    ],
)
def test_gate_bounds_rejected(overrides):
    assert bg.validate_benchmark_gate(_gate(**overrides)) == (None, "BOUNDS_REJECTED")


@pytest.mark.parametrize(
    "overrides",
    [
        {"warmup_runs": 0, "repeats": 4, "per_run_timeout_seconds": 10},
        {"warmup_runs": 2, "repeats": 8, "per_run_timeout_seconds": 69},
        {"min_improvement": 0.05, "max_noise": 0.02},
        {"min_improvement": 0.9, "max_noise": 0.3},
        {"min_improvement": 0.10, "max_noise": 0.10, "per_run_timeout_seconds": 80},
    ],
)
def test_gate_bounds_edges_accepted(overrides):
    assert bg.validate_benchmark_gate(_gate(**overrides))[1] == "OK"


@pytest.mark.parametrize(
    "overrides",
    [
        {"repeats": 8},  # (1 + 8 + 3) * 2 * 80 = 1920 > 1800
        {"repeats": 8, "per_run_timeout_seconds": 76},  # 12 * 2 * 76 = 1824
        {"per_run_timeout_seconds": 91},  # 10 * 2 * 91 = 1820
        {"warmup_runs": 2, "repeats": 8, "per_run_timeout_seconds": 70},  # 13 * 2 * 70 = 1820
        {"warmup_runs": 2, "repeats": 8, "per_run_timeout_seconds": 300},
    ],
)
def test_gate_budget_rejected(overrides):
    assert bg.validate_benchmark_gate(_gate(**overrides)) == (None, "BUDGET_REJECTED")


def test_gate_budget_boundary_is_inclusive():
    assert bg.validate_benchmark_gate(_gate(repeats=8, per_run_timeout_seconds=75))[1] == "OK"  # 12*2*75 == 1800
    assert bg.validate_benchmark_gate(_gate(per_run_timeout_seconds=90))[1] == "OK"  # 10*2*90 == 1800


def test_gate_int_thresholds_are_numbers_but_out_of_bounds():
    # An int is a real number for the two thresholds (so not TYPE_REJECTED), but 0 and 1 are out of bounds.
    assert bg.validate_benchmark_gate(_gate(min_improvement=1)) == (None, "BOUNDS_REJECTED")


@pytest.mark.parametrize("field", ["min_improvement", "max_noise"])
@pytest.mark.parametrize("huge", [10**5000, -(10**5000)], ids=["positive", "negative"])
def test_gate_huge_int_threshold_is_bounds_rejected_not_a_crash(field, huge):
    # str(int) raises ValueError above 4300 digits; the thresholds must reach the bounds check instead.
    assert bg.validate_benchmark_gate(_gate(**{field: huge})) == (None, "BOUNDS_REJECTED")


@pytest.mark.parametrize("warmup, largest", [(0, 81), (1, 75), (2, 69)])
def test_gate_budget_largest_timeout_at_repeats_8_per_warmup(warmup, largest):
    # The figures in validate_benchmark_gate's docstring.
    gate = _gate(warmup_runs=warmup, repeats=8, per_run_timeout_seconds=largest)
    assert bg.validate_benchmark_gate(gate)[1] == "OK"
    gate["per_run_timeout_seconds"] = largest + 1
    assert bg.validate_benchmark_gate(gate) == (None, "BUDGET_REJECTED")


# ---------------------------------------------------------------------------
# evaluate_paired_samples
# ---------------------------------------------------------------------------

def _ev(base, head, repeats=6, min_improvement=0.10, max_noise=0.10):
    return bg.evaluate_paired_samples(
        base, head, repeats=repeats, min_improvement=min_improvement, max_noise=max_noise
    )


def test_exact_ten_percent_boundary_is_clear_win():
    assert _ev([1000] * 6, [900] * 6) == ("IMPROVED", "IMPROVED_CLEAR")


def test_just_under_ten_percent_is_not_a_clear_win():
    # 9.99% improvement: not clear, not noisy, not past the threshold, above half of it.
    assert _ev([10000] * 6, [9001] * 6) == ("INCONCLUSIVE", "BORDERLINE")


def test_float_threshold_uses_decimal_not_binary_value():
    # Fraction(0.10) > 1/10, which would make an exact 10% win fail; Fraction(str(0.10)) is exactly 1/10.
    assert Fraction(0.10) > Fraction(1, 10)
    assert _ev([1000] * 6, [900] * 6, min_improvement=0.10) == ("IMPROVED", "IMPROVED_CLEAR")
    assert _ev([1000] * 6, [850] * 6, min_improvement=0.15) == ("IMPROVED", "IMPROVED_CLEAR")
    assert _ev([100] * 6, [95] * 6, min_improvement=0.05) == ("IMPROVED", "IMPROVED_CLEAR")


def test_median_exactly_half_threshold_is_borderline():
    assert _ev([1000] * 6, [950] * 6) == ("INCONCLUSIVE", "BORDERLINE")


def test_median_just_above_and_below_half_threshold():
    assert _ev([10000] * 6, [9501] * 6) == ("NOT_IMPROVED", "BELOW_HALF_THRESHOLD")
    assert _ev([10000] * 6, [9499] * 6) == ("INCONCLUSIVE", "BORDERLINE")


def test_equal_ratios_have_zero_mad_and_pass_the_noise_gate():
    assert _ev([1000] * 6, [980] * 6) == ("NOT_IMPROVED", "BELOW_HALF_THRESHOLD")
    assert _ev([1000] * 6, [930] * 6) == ("INCONCLUSIVE", "BORDERLINE")


def test_base_equals_head_is_not_improved():
    assert _ev([500, 510, 490, 505, 495, 500], [500, 510, 490, 505, 495, 500]) == ("NOT_IMPROVED", "BELOW_HALF_THRESHOLD")


def test_real_regression_is_not_improved():
    assert _ev([1000] * 6, [1500] * 6) == ("NOT_IMPROVED", "BELOW_HALF_THRESHOLD")
    assert _ev([1000] * 4, [2000] * 4, repeats=4) == ("NOT_IMPROVED", "BELOW_HALF_THRESHOLD")


def test_n4_three_clear_and_one_unchanged_has_no_tolerance():
    assert _ev([1000] * 4, [900, 900, 900, 1000], repeats=4) == ("INCONCLUSIVE", "INCONSISTENT")
    assert _ev([1000] * 4, [900] * 4, repeats=4) == ("IMPROVED", "IMPROVED_CLEAR")


def test_n6_need_is_five():
    assert _ev([1000] * 6, [900, 900, 900, 900, 900, 1000]) == ("IMPROVED", "IMPROVED_CLEAR")
    assert _ev([1000] * 6, [900, 900, 900, 900, 1000, 1000]) == ("INCONCLUSIVE", "INCONSISTENT")


def test_n8_need_is_seven_not_six():
    assert _ev([1000] * 8, [900] * 7 + [1000], repeats=8) == ("IMPROVED", "IMPROVED_CLEAR")
    assert _ev([1000] * 8, [900] * 6 + [1000] * 2, repeats=8) == ("INCONCLUSIVE", "INCONSISTENT")


def test_clear_win_skips_the_noise_gate():
    # Five clear ratios plus one wild outlier: MAD/median is small here, so build a case where it would be
    # NOISY without the short-circuit: median is clear but the spread is large.
    base = [1000] * 6
    head = [100, 200, 300, 400, 500, 3000]
    assert _ev(base, head) == ("IMPROVED", "IMPROVED_CLEAR")


def test_noisy():
    base = [1000] * 6
    head = [500, 1500, 600, 1400, 700, 1300]
    assert _ev(base, head) == ("INCONCLUSIVE", "NOISY")


def test_noise_exactly_at_the_limit_is_not_noisy():
    # ratios .9 .9 1 1 1.1 1.1: median 1, MAD 0.1, so MAD / median == max_noise exactly; the gate is strict `>`.
    head = [900, 900, 1000, 1000, 1100, 1100]
    assert _ev([1000] * 6, head, max_noise=0.10) == ("NOT_IMPROVED", "BELOW_HALF_THRESHOLD")
    assert _ev([1000] * 6, head, max_noise=0.099) == ("INCONCLUSIVE", "NOISY")


def test_noise_is_relative_to_the_median():
    # ratios 2 2 2.2 2.2 2.4 2.4: MAD 0.2 but median 2.2, so MAD / median is 0.0909 (< 0.10). An undivided MAD
    # (0.2) would wrongly be NOISY.
    head = [2000, 2000, 2200, 2200, 2400, 2400]
    assert _ev([1000] * 6, head) == ("NOT_IMPROVED", "BELOW_HALF_THRESHOLD")
    assert _ev([1000] * 6, head, max_noise=0.09) == ("INCONCLUSIVE", "NOISY")


def test_even_count_median_is_mean_of_middle_two():
    # ratios .90 .90 1.0 1.0 1.0 1.0: median 1.0. Ratios .85 .85 .85 .95 .95 .95: median .90 (the mean of .85
    # and .95), one clear fewer than needed, so the median clause (3) fires.
    assert _ev([1000] * 6, [850, 850, 850, 950, 950, 950]) == ("INCONCLUSIVE", "INCONSISTENT")
    assert bg._median([Fraction(1), Fraction(3)]) == Fraction(2)
    assert bg._median([Fraction(5)]) == Fraction(5)


def test_huge_and_tiny_integers():
    huge = 10**30
    assert _ev([huge] * 6, [huge * 9 // 10] * 6) == ("IMPROVED", "IMPROVED_CLEAR")
    assert _ev([huge] * 6, [huge + 1] * 6) == ("NOT_IMPROVED", "BELOW_HALF_THRESHOLD")
    assert _ev([1] * 6, [1] * 6) == ("NOT_IMPROVED", "BELOW_HALF_THRESHOLD")
    assert _ev([10] * 6, [9] * 6) == ("IMPROVED", "IMPROVED_CLEAR")
    assert _ev([1] * 6, [10**400] * 6) == ("NOT_IMPROVED", "BELOW_HALF_THRESHOLD")


INVALID = ("INCONCLUSIVE", "INVALID_INPUT")


@pytest.mark.parametrize(
    "base, head",
    [
        ([1000] * 6, [900.0] * 6),  # float sample
        ([1000.0] * 6, [900] * 6),
        ([1000] * 6, [True] * 6),  # bool sample
        ([True] * 6, [900] * 6),
        ([1000] * 6, [0] * 6),  # zero
        ([0] * 6, [900] * 6),  # zero base: would divide by zero
        ([1000] * 6, [-900] * 6),  # negative
        ([-1000] * 6, [900] * 6),
        ([1000] * 5, [900] * 6),  # wrong length
        ([1000] * 6, [900] * 7),
        ([], []),
        ("abcdef", [900] * 6),
        (None, [900] * 6),
        ([1000] * 6, None),
        ([1000] * 6, ["900"] * 6),
        ([1000] * 6, [Decimal(900)] * 6),
        ([1000] * 6, [Fraction(900)] * 6),
        ([1000] * 5 + [None], [900] * 6),
    ],
)
def test_invalid_samples(base, head):
    assert _ev(base, head) == INVALID


@pytest.mark.parametrize(
    "kwargs",
    [
        {"repeats": 5},
        {"repeats": 2},
        {"repeats": True},
        {"repeats": 6.0},
        {"repeats": "6"},
        {"repeats": None},
        {"min_improvement": float("nan")},
        {"min_improvement": float("inf")},
        {"min_improvement": True},
        {"min_improvement": "0.1"},
        {"min_improvement": Decimal("0.1")},
        {"min_improvement": Fraction(1, 10)},
        {"min_improvement": None},
        {"min_improvement": 0.049},
        {"min_improvement": 0.91},
        {"min_improvement": 1},
        {"max_noise": float("nan")},
        {"max_noise": float("-inf")},
        {"max_noise": True},
        {"max_noise": "0.1"},
        {"max_noise": Decimal("0.1")},
        {"max_noise": Fraction(1, 10)},
        {"max_noise": 0.019},
        {"max_noise": 0.31},
    ],
)
def test_invalid_parameters(kwargs):
    params = {"repeats": 6, "min_improvement": 0.10, "max_noise": 0.10}
    params.update(kwargs)
    assert bg.evaluate_paired_samples([1000] * 6, [900] * 6, **params) == INVALID


def test_huge_int_threshold_is_invalid_input_not_a_crash():
    assert _ev([1000] * 6, [900] * 6, min_improvement=10**5000) == INVALID
    assert _ev([1000] * 6, [900] * 6, max_noise=-(10**5000)) == INVALID


def test_parameter_bounds_are_inclusive():
    assert _ev([1000] * 6, [900] * 6, min_improvement=0.05, max_noise=0.02)[0] == "IMPROVED"
    assert _ev([1000] * 6, [100] * 6, min_improvement=0.90, max_noise=0.30)[0] == "IMPROVED"


def test_evaluate_never_raises_on_hostile_objects():
    class Boom:
        def __len__(self):
            raise RuntimeError("boom")

        def __iter__(self):
            raise RuntimeError("boom")

    for bad in (Boom(), object(), 5, {"a": 1}):
        assert _ev(bad, bad) == INVALID
        assert bg.evaluate_paired_samples(bad, bad, repeats=bad, min_improvement=bad, max_noise=bad) == INVALID


def test_evaluate_accepts_tuples():
    assert _ev(tuple([1000] * 6), tuple([900] * 6)) == ("IMPROVED", "IMPROVED_CLEAR")


# ---------------------------------------------------------------------------
# escape_diagnostic
# ---------------------------------------------------------------------------

def test_escape_printable_ascii_only():
    out = bg.escape_diagnostic("café \x00\x1b[31mred\x7f")
    assert out.isascii() and all(" " <= c <= "~" for c in out)
    assert out == "caf? ??[31mred?"


def test_escape_backticks_newlines_and_pipes():
    out = bg.escape_diagnostic("a`b\nc\r\nd|e\tf")
    assert "`" not in out and "\n" not in out and "\r" not in out and "|" not in out and "\t" not in out
    assert out == "a'b c  d/e f"


@pytest.mark.parametrize("lead", ["#", ">", "-", "*", "+"])
def test_escape_neutralizes_leading_markdown(lead):
    assert bg.escape_diagnostic(f"{lead} heading") == f"'{lead} heading"
    assert bg.escape_diagnostic(f"\n\n  {lead} heading") == f"'{lead} heading"
    assert bg.escape_diagnostic(f"x {lead} y") == f"x {lead} y"


def test_escape_caps_length_after_escaping():
    assert len(bg.escape_diagnostic("a" * 5000)) == 2048
    assert len(bg.escape_diagnostic("# " + "a" * 5000, limit=10)) == 10
    assert bg.escape_diagnostic("abc", limit=0) == ""
    assert bg.escape_diagnostic("abc", limit=-5) == ""
    assert bg.escape_diagnostic("") == ""
    assert bg.escape_diagnostic(None) == "None"


# ---------------------------------------------------------------------------
# CLI: validate
# ---------------------------------------------------------------------------

def _run(tmp_path, capsys, payload, *, raw=None):
    path = tmp_path / "si.json"
    path.write_text(raw if raw is not None else json.dumps(payload), encoding="utf-8")
    code = bg.main(["validate", "--specialist-inputs", str(path)])
    return code, capsys.readouterr()


def test_cli_ok_prints_gate_sha256(tmp_path, capsys):
    code, cap = _run(tmp_path, capsys, {"performance_review_origin": True, "benchmark_gate": GOOD_GATE})
    normalized, _ = bg.validate_benchmark_gate(GOOD_GATE)
    expected = bg.hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert code == 0
    assert cap.out.splitlines() == ["OK", f"gate_sha256: {expected}"]
    assert bg.gate_sha256(normalized) == expected


def test_cli_hash_ignores_key_order_and_includes_defaults(tmp_path, capsys):
    reordered = dict(reversed(list(GOOD_GATE.items())))
    explicit = {**GOOD_GATE, "warmup_runs": 1, "repeats": 6, "per_run_timeout_seconds": 80, "min_improvement": 0.1, "max_noise": 0.1}
    outputs = {
        _run(tmp_path, capsys, {"performance_review_origin": True, "benchmark_gate": g})[1].out
        for g in (GOOD_GATE, reordered, explicit)
    }
    assert len(outputs) == 1


def test_cli_not_gated_when_key_absent_and_origin_not_true(tmp_path, capsys):
    for payload in ({}, {"other": 1}, {"performance_review_origin": False}, {"performance_review_origin": "true"}, {"performance_review_origin": 1}):
        code, cap = _run(tmp_path, capsys, payload)
        assert (code, cap.out) == (3, "NOT_GATED\n"), payload


@pytest.mark.parametrize("gate_value", [GOOD_GATE, None, {}, "x", 5])
@pytest.mark.parametrize("origin", [False, "true", 1, None, 0])
def test_cli_gate_key_without_true_origin_is_rejected(tmp_path, capsys, gate_value, origin):
    code, cap = _run(tmp_path, capsys, {"performance_review_origin": origin, "benchmark_gate": gate_value})
    assert (code, cap.out) == (1, "REJECT:GATE_WITHOUT_ORIGIN\n")


def test_cli_gate_key_without_origin_key_is_rejected(tmp_path, capsys):
    code, cap = _run(tmp_path, capsys, {"benchmark_gate": GOOD_GATE})
    assert (code, cap.out) == (1, "REJECT:GATE_WITHOUT_ORIGIN\n")
    code, cap = _run(tmp_path, capsys, {"benchmark_gate": None})
    assert (code, cap.out) == (1, "REJECT:GATE_WITHOUT_ORIGIN\n")


@pytest.mark.parametrize("payload", [{"performance_review_origin": True}, {"performance_review_origin": True, "benchmark_gate": None}])
def test_cli_origin_without_gate_is_gate_missing(tmp_path, capsys, payload):
    code, cap = _run(tmp_path, capsys, payload)
    assert (code, cap.out) == (1, "REJECT:GATE_MISSING\n")


def test_cli_non_dict_gate_with_origin_is_gate_missing(tmp_path, capsys):
    code, cap = _run(tmp_path, capsys, {"performance_review_origin": True, "benchmark_gate": "x"})
    assert (code, cap.out) == (1, "REJECT:GATE_MISSING\n")


@pytest.mark.parametrize(
    "gate, reject_code",
    [
        ({"command": "x"}, "KEY_MISSING"),
        ({**GOOD_GATE, "extra": 1}, "KEY_UNKNOWN"),
        ({**GOOD_GATE, "command": "make bench"}, "COMMAND_REJECTED"),
        ({**GOOD_GATE, "benchmark_paths": ["src/x.py"]}, "PATH_REJECTED"),
        ({**GOOD_GATE, "benchmark_symbol": "main"}, "SYMBOL_REJECTED"),
        ({**GOOD_GATE, "repeats": "6"}, "TYPE_REJECTED"),
        ({**GOOD_GATE, "repeats": 5}, "BOUNDS_REJECTED"),
        ({**GOOD_GATE, "repeats": 8}, "BUDGET_REJECTED"),
    ],
)
def test_cli_every_gate_rejection_code(tmp_path, capsys, gate, reject_code):
    code, cap = _run(tmp_path, capsys, {"performance_review_origin": True, "benchmark_gate": gate})
    assert (code, cap.out) == (1, f"REJECT:{reject_code}\n")


def test_cli_nan_in_json_is_a_fail_closed_rejection(tmp_path, capsys):
    raw = '{"performance_review_origin": true, "benchmark_gate": {"command": "pytest %s", "benchmark_paths": ["%s"], "benchmark_symbol": "build_report", "min_improvement": NaN}}' % (PATH, PATH)
    code, cap = _run(tmp_path, capsys, None, raw=raw)
    assert (code, cap.out) == (1, "REJECT:BOUNDS_REJECTED\n")


def test_cli_usage_errors_exit_2(tmp_path, capsys):
    assert bg.main([]) == 2
    assert bg.main(["validate"]) == 2
    assert bg.main(["bogus"]) == 2
    assert bg.main(["validate", "--specialist-inputs"]) == 2
    capsys.readouterr()
    assert bg.main(["validate", "--specialist-inputs", str(tmp_path / "missing.json")]) == 2
    assert capsys.readouterr().out == ""
    for raw in ("not json", "[]", '"str"', "null", ""):
        code, cap = _run(tmp_path, capsys, None, raw=raw)
        assert (code, cap.out) == (2, ""), raw
    big = tmp_path / "big.json"
    big.write_text('{"x": "' + "a" * (1 << 20) + '"}', encoding="utf-8")
    assert bg.main(["validate", "--specialist-inputs", str(big)]) == 2
    directory = tmp_path / "dir"
    directory.mkdir()
    assert bg.main(["validate", "--specialist-inputs", str(directory)]) == 2


# Everything the module may import at import time. Platform-specific modules (resource, fcntl, termios, ...) must
# be imported lazily inside the function that needs them, so the module imports on every platform.
_TOP_LEVEL_IMPORT_ALLOWLIST = {
    "__future__", "argparse", "ast", "codecs", "dis", "fractions", "hashlib", "io", "json", "math", "os", "pathlib",
    "posixpath", "re", "stat", "sys", "tokenize", "types", "warnings",
}


def test_module_imports_only_portable_modules_at_top_level():
    tree = ast.parse((_SCRIPTS / "benchmark_gate.py").read_text(encoding="utf-8"))
    imported = set()
    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue  # a lazy import inside a function is the sanctioned way to use a platform-specific module
        for node in ast.walk(statement):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
    assert imported, "the walk found no imports; the test is broken"
    assert imported <= _TOP_LEVEL_IMPORT_ALLOWLIST, sorted(imported - _TOP_LEVEL_IMPORT_ALLOWLIST)


# --- CLI: validate hardening (bounded read, deep JSON) ---

def test_cli_validate_deeply_nested_json_is_exit_2_with_nothing_on_stdout(tmp_path, capsys):
    code, cap = _run(tmp_path, capsys, None, raw="[" * 500000 + "]" * 500000)  # under the 1 MiB cap
    assert (code, cap.out) == (2, "")


def test_cli_validate_huge_int_gate_value_is_a_rejection_not_a_crash(tmp_path, capsys):
    # 4000 digits is under the interpreter's int-parsing limit, so json accepts it and the gate must reject it.
    gate = {**GOOD_GATE, "min_improvement": 10**4000}
    code, cap = _run(tmp_path, capsys, {"performance_review_origin": True, "benchmark_gate": gate})
    assert (code, cap.out) == (1, "REJECT:BOUNDS_REJECTED\n")


def test_cli_validate_input_cap_boundary_is_exactly_1_mib(tmp_path, capsys):
    exact = tmp_path / "exact.json"
    exact.write_bytes(b"{}" + b" " * (bg._MAX_INPUT_BYTES - 2))
    over = tmp_path / "over.json"
    over.write_bytes(b"{}" + b" " * (bg._MAX_INPUT_BYTES - 1))
    assert bg._MAX_INPUT_BYTES == 1 << 20
    assert bg.main(["validate", "--specialist-inputs", str(exact)]) == 3
    assert capsys.readouterr().out == "NOT_GATED\n"
    assert bg.main(["validate", "--specialist-inputs", str(over)]) == 2
    assert capsys.readouterr().out == ""
