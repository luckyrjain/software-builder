"""C4d-2: the trace plugin (``TRACE_PLUGIN_SOURCE``), ``trace_env`` and ``trace_paired``.

Covers: the plugin-source rules (ASCII, no annotations, the static 3.8 rules); unit tests of the plugin's exec contract (``_init``, tool claim and
release, ``on_event``, hooks, the terminal markers); the plugin file helpers; ``trace_paired`` with fake children (result validation, decision
table, error phase and side); and real-pytest rows that check relations and lower bounds only.

The plugin is a raw-string constant that is written into a side's harness-owned directory and loaded with ``-p``. These tests ``exec`` its
source in a scratch namespace (the module ends with ``_init(os.environ, sys)``, which runs on the real process objects, so each test sets the
``BENCH_TRACE_*`` variables, changes into a directory holding a real target file, and replaces ``sys.monitoring`` with a fake unless the row
deliberately claims the real tool id 4). Anything really claimed is released in a ``finally`` through the plugin's own ``_release_tool``.
"""

from __future__ import annotations

import ast
import importlib.util
import io
import os
import re
import sys
import textwrap
import threading
import tempfile
import tokenize
import types
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "benchmark_gate.py"
spec = importlib.util.spec_from_file_location("benchmark_gate_trace_under_test", SCRIPT)
bg = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bg
spec.loader.exec_module(bg)

posix_only = pytest.mark.skipif(os.name != "posix", reason="POSIX harness")
needs_monitoring = pytest.mark.skipif(not hasattr(sys, "monitoring"), reason="sys.monitoring needs CPython 3.12+")

NONCE = "0123456789abcdef" * 2


# --- helpers copied from test_benchmark_gate_measure.py (pytest_venv extended with per-side libraries) ------------------------

def fake_sides(tmp_path):
    roots, bins = {}, {}
    for side in ("base", "head"):
        roots[side] = tmp_path / f"{side}-root"
        bins[side] = tmp_path / f"{side}-venv" / "bin"
        roots[side].mkdir()
        bins[side].mkdir(parents=True)
    return roots, bins


def builder(script: str, *extra: str):
    """argv_builder running ``python -c script <side> <root> <extra...>``."""
    def build(side, bin_dir, root, target):
        return [sys.executable, "-c", textwrap.dedent(script), side, root, target, *extra]
    return build


def pytest_venv(path: Path, libs=None) -> Path:
    """A real, pip-less venv whose ``.pth`` makes the running interpreter's pytest importable, whichever site directory it lives in.
    ``libs`` maps a module file name to its source; each is written next to the ``.pth`` (the code under test, installed for ``-P``)."""
    import venv

    venv.create(path, with_pip=False, symlinks=True)
    sites = {os.path.dirname(os.path.dirname(sys.modules[name].__file__)) for name in ("pytest", "_pytest", "pluggy", "iniconfig", "packaging")
             if name in sys.modules}
    site = next((path / "lib").glob("python3*/site-packages"))
    (site / "zz_pytest.pth").write_text("\n".join(sorted(sites)) + "\n")
    for name, source in (libs or {}).items():
        (site / name).write_text(source)
    return path / "bin"


# --- fakes and the exec seam ----------------------------------------------------------------------------------------------

class FakeMonitoring:
    """Records every call; ``clear_tool_id`` exists only when asked for (it is absent on CPython 3.12)."""

    DISABLE = object()

    def __init__(self, with_clear=False, use_tool_id_raises=None):
        self.calls = []
        self.events = types.SimpleNamespace(LINE=2, JUMP=4)
        self._raises = use_tool_id_raises
        if with_clear:
            self.clear_tool_id = lambda tool: self.calls.append(("clear_tool_id", tool))

    def use_tool_id(self, tool, name):
        self.calls.append(("use_tool_id", tool, name))
        if self._raises is not None:
            raise self._raises

    def get_tool(self, tool):
        self.calls.append(("get_tool", tool))
        return "bench_trace_plugin"

    def set_events(self, tool, events):
        self.calls.append(("set_events", tool, events))

    def register_callback(self, tool, event, func):
        self.calls.append(("register_callback", tool, event, func))

    def free_tool_id(self, tool):
        self.calls.append(("free_tool_id", tool))


def plugin_env_vars(tmp_path, monkeypatch, target):
    """The plugin pops these on import, so a test that execs it twice sets them again."""
    monkeypatch.setenv("BENCH_TRACE_FILE", target)
    monkeypatch.setenv("BENCH_TRACE_OUT", str(tmp_path / "out" / "trace.out"))
    monkeypatch.setenv("BENCH_TRACE_NONCE", NONCE)


def plugin_env(tmp_path, monkeypatch, extra_pythonpath=None, in_sys_path=True):
    """A cwd holding a real target file, the three trace variables, and a plugin directory. Returns (plugin_path, cwd)."""
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    (cwd / "bench.py").write_text("def test_x():\n    pass\n")
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    monkeypatch.chdir(cwd)
    plugin_env_vars(tmp_path, monkeypatch, "bench.py")
    pythonpath = [str(plugin_dir)] + list(extra_pythonpath or [])
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(pythonpath))
    monkeypatch.setattr(sys, "path", list(sys.path) + ([str(plugin_dir)] if in_sys_path else []))
    return str(plugin_dir / "bench_trace_plugin.py"), cwd


def exec_plugin(plugin_path, monkeypatch, fake="default"):
    """Run the plugin source the way pytest would import it (``_init`` included). ``fake=None`` leaves the real ``sys.monitoring``."""
    if fake == "default":
        fake = FakeMonitoring()
    if fake is not None:
        monkeypatch.setattr(sys, "monitoring", fake, raising=False)
    namespace = {"__file__": plugin_path, "__name__": "bench_trace_plugin"}
    exec(compile(bg.TRACE_PLUGIN_SOURCE, plugin_path, "exec"), namespace)
    return namespace


def fresh_state(namespace):
    namespace["STATE"] = type(namespace["STATE"])()
    return namespace["STATE"]


def unique_code(tag):
    return compile("a = 1\nb = 2\nc = 3\n", f"/unique/{tag}.py", "exec")


# --- the static 3.8 rules --------------------------------------------------------------------------------------------------

_BUILTIN_TYPES = {"int", "str", "float", "bool", "bytes", "bytearray", "complex", "object", "list", "dict", "set", "frozenset", "tuple", "type"}
_SUBSCRIPTED = {"list", "dict", "set", "frozenset", "tuple", "type"}
_BANNED_NAMES = {"removeprefix", "removesuffix", "cache", "zoneinfo"}


def static_violations(source):
    """Rules the plugin must obey to import on CPython 3.8 (spec D2). Raises SyntaxError for syntax newer than 3.8."""
    tree = ast.parse(source, feature_version=(3, 8))
    isinstance_union = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "isinstance" and len(node.args) > 1:
            isinstance_union.add(id(node.args[1]))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.arg) and node.annotation is not None:
            found.append("argument annotation")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.returns is not None:
            found.append("return annotation")
        elif isinstance(node, ast.AnnAssign):
            found.append("annotated assignment")
        elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id in _SUBSCRIPTED:
            found.append("subscripted builtin " + node.value.id)
        elif isinstance(node, ast.Name) and node.id in _BANNED_NAMES:
            found.append("name " + node.id)
        elif isinstance(node, ast.Attribute) and node.attr in _BANNED_NAMES:
            found.append("attribute " + node.attr)
        elif isinstance(node, ast.alias) and node.name.split(".")[0] in _BANNED_NAMES:
            found.append("import " + node.name)
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in _BANNED_NAMES:
            found.append("import from " + node.module)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            operands = (node.left, node.right)
            typeish = any((isinstance(o, ast.Constant) and o.value is None) or (isinstance(o, ast.Name) and o.id in _BUILTIN_TYPES)
                          or isinstance(o, (ast.Subscript, ast.Dict)) for o in operands)
            if typeish or id(node) in isinstance_union:
                found.append("type or dict union")
    return found


def test_plugin_source_is_ascii_has_no_annotations_and_passes_the_static_3_8_rules():
    source = bg.TRACE_PLUGIN_SOURCE
    assert isinstance(source, str) and source
    source.encode("ascii")  # raises on any non-ASCII character
    assert static_violations(source) == []

    # the allowed flag arithmetic is not mistaken for a type union
    assert static_violations("import os\nx = os.O_CREAT | os.O_EXCL\ny = events.LINE | events.JUMP\n") == []
    for bad in ("x: int | None = None\n", "d1 = {}\nd2 = d1 | {}\n", "def f(a: int):\n    pass\n", "def f():\n    pass\n\ndef g() -> int:\n    return 1\n",
                "x = list[int]\n", "s.removeprefix('a')\n", "from functools import cache\n", "import zoneinfo\n",
                "isinstance(x, int | str)\n", "y = int | None\n"):
        assert static_violations(bad), bad
    with pytest.raises(SyntaxError):
        static_violations("match x:\n    case 1:\n        pass\n")

    # the constant is a raw string literal in the file (a non-raw one would turn a backslash escape into a different program)
    tokens = list(tokenize.tokenize(io.BytesIO(SCRIPT.read_bytes()).readline))
    for index, token in enumerate(tokens):
        if token.type == tokenize.NAME and token.string == "TRACE_PLUGIN_SOURCE" and token.start[1] == 0:
            literal = next(t for t in tokens[index + 1:] if t.type == tokenize.STRING)
            assert literal.string.startswith('r"""')
            break
    else:
        pytest.fail("no module-level TRACE_PLUGIN_SOURCE assignment")


def test_the_plugin_constant_lives_in_the_digested_file_and_the_literals_agree():
    text = Path(bg.__file__).read_bytes().decode("utf-8")
    assert bg.TRACE_PLUGIN_SOURCE in text
    assert re.search(r"use_tool_id\(\s*4\s*,\s*(['\"])" + re.escape(bg._TRACE_MODULE) + r"\1\s*\)", bg.TRACE_PLUGIN_SOURCE)


# --- _init -----------------------------------------------------------------------------------------------------------------

@posix_only
def test_init_pops_with_defaults_captures_root_and_target_once_and_removes_only_its_dir_from_sys_path_and_pythonpath(tmp_path, monkeypatch):
    other = str(tmp_path / "other-lib")
    plugin_path, cwd = plugin_env(tmp_path, monkeypatch, extra_pythonpath=[other])
    plugin_dir = os.path.dirname(plugin_path)
    namespace = exec_plugin(plugin_path, monkeypatch)
    state = namespace["STATE"]

    for name in ("BENCH_TRACE_FILE", "BENCH_TRACE_OUT", "BENCH_TRACE_NONCE"):
        assert name not in os.environ
    assert state.out == str(tmp_path / "out" / "trace.out") and state.nonce == NONCE
    assert state.failed is False
    assert state.root_real == os.path.realpath(cwd)
    assert state.target_real == os.path.realpath(cwd / "bench.py")
    os.chdir("/")  # a benchmark that moves away cannot move what was captured at import
    assert state.root_real == os.path.realpath(cwd) and state.target_real == os.path.realpath(cwd / "bench.py")

    assert plugin_dir not in sys.path
    assert os.environ["PYTHONPATH"] == other
    assert any(p for p in sys.path)  # the other entries survive


@posix_only
def test_init_deletes_pythonpath_when_it_ends_up_empty_and_tolerates_a_dir_absent_from_sys_path(tmp_path, monkeypatch):
    plugin_path, _ = plugin_env(tmp_path, monkeypatch, in_sys_path=False)
    exec_plugin(plugin_path, monkeypatch)
    assert "PYTHONPATH" not in os.environ


@posix_only
@pytest.mark.parametrize("missing", ["BENCH_TRACE_FILE", "BENCH_TRACE_OUT", "BENCH_TRACE_NONCE"])
def test_init_with_an_absent_variable_sets_failed_and_leaves_no_variable_behind(tmp_path, monkeypatch, missing):
    plugin_path, _ = plugin_env(tmp_path, monkeypatch)
    monkeypatch.delenv(missing)
    fake = FakeMonitoring()
    namespace = exec_plugin(plugin_path, monkeypatch, fake=fake)
    assert namespace["STATE"].failed is True
    assert namespace["STATE"].claimed is False
    assert not [c for c in fake.calls if c[0] == "use_tool_id"]
    for name in ("BENCH_TRACE_FILE", "BENCH_TRACE_OUT", "BENCH_TRACE_NONCE"):
        assert name not in os.environ


@posix_only
def test_init_fails_for_a_target_outside_the_root_or_not_a_regular_file(tmp_path, monkeypatch):
    plugin_path, cwd = plugin_env(tmp_path, monkeypatch)
    (tmp_path / "outside.py").write_text("x = 1\n")
    (cwd / "link.py").symlink_to(tmp_path / "outside.py")
    (cwd / "adir").mkdir()
    for target in ("link.py", "../outside.py", "adir", "missing.py"):
        plugin_env_vars(tmp_path, monkeypatch, target)
        namespace = exec_plugin(plugin_path, monkeypatch)
        assert namespace["STATE"].failed is True, target
        assert namespace["STATE"].claimed is False, target
    plugin_env_vars(tmp_path, monkeypatch, "bench.py")
    assert exec_plugin(plugin_path, monkeypatch)["STATE"].failed is False


# --- _claim_tool and _release_tool -----------------------------------------------------------------------------------------

@posix_only
def test_claim_tool_reports_tool_in_use_no_monitoring_and_error_and_never_raises(tmp_path, monkeypatch):
    real_monitoring = getattr(sys, "monitoring", None)
    plugin_path, _ = plugin_env(tmp_path, monkeypatch)
    namespace = exec_plugin(plugin_path, monkeypatch)
    claim = namespace["_claim_tool"]

    ok = FakeMonitoring()
    assert claim(types.SimpleNamespace(monitoring=ok)) is None
    assert ok.calls == [("use_tool_id", 4, bg._TRACE_MODULE)]
    assert claim(types.SimpleNamespace(monitoring=FakeMonitoring(use_tool_id_raises=ValueError("in use")))) == "tool_in_use"
    assert claim(types.SimpleNamespace()) == "no_monitoring"
    assert claim(types.SimpleNamespace(monitoring=FakeMonitoring(use_tool_id_raises=AttributeError("x")))) == "error"
    assert claim(types.SimpleNamespace(monitoring=FakeMonitoring(use_tool_id_raises=RuntimeError("x")))) == "error"

    if real_monitoring is None:
        return
    real_sys = types.SimpleNamespace(monitoring=real_monitoring)
    try:
        first = claim(real_sys)
        if first is not None:
            pytest.skip("tool id 4 is already taken in this process")
        assert claim(real_sys) == "tool_in_use"
    finally:
        namespace["_release_tool"](real_sys)
    assert claim(real_sys) is None  # released: a fresh claim works again
    namespace["_release_tool"](real_sys)


@posix_only
def test_init_maps_the_claim_result_to_unavailable_failed_and_claimed(tmp_path, monkeypatch):
    plugin_path, _ = plugin_env(tmp_path, monkeypatch)
    namespace = exec_plugin(plugin_path, monkeypatch)

    def run_init(fake_sys, environ=None):
        state = fresh_state(namespace)
        namespace["_init"](environ if environ is not None else {
            "BENCH_TRACE_FILE": "bench.py", "BENCH_TRACE_OUT": "/o", "BENCH_TRACE_NONCE": NONCE}, fake_sys)
        return state

    state = run_init(types.SimpleNamespace(monitoring=FakeMonitoring()))
    assert (state.unavailable, state.failed, state.claimed) == (None, False, True)
    state = run_init(types.SimpleNamespace(monitoring=FakeMonitoring(use_tool_id_raises=ValueError("in use"))))
    assert (state.unavailable, state.failed, state.claimed) == ("tool_in_use", False, False)
    state = run_init(types.SimpleNamespace())
    assert (state.unavailable, state.failed, state.claimed) == ("no_monitoring", False, False)
    state = run_init(types.SimpleNamespace(monitoring=FakeMonitoring(use_tool_id_raises=RuntimeError("x"))))
    assert (state.unavailable, state.failed, state.claimed) == (None, True, False)

    skipped = FakeMonitoring()
    state = run_init(types.SimpleNamespace(monitoring=skipped), environ={"BENCH_TRACE_FILE": "bench.py"})  # out and nonce absent
    assert state.failed is True and state.claimed is False
    assert skipped.calls == []


def test_release_tool_without_clear_tool_id_registers_none_callbacks_then_frees(tmp_path, monkeypatch):
    plugin_path, _ = plugin_env(tmp_path, monkeypatch)
    namespace = exec_plugin(plugin_path, monkeypatch)

    bare = FakeMonitoring(with_clear=False)
    assert not hasattr(bare, "clear_tool_id")
    namespace["_release_tool"](types.SimpleNamespace(monitoring=bare))
    assert bare.calls == [("register_callback", 4, bare.events.LINE, None), ("register_callback", 4, bare.events.JUMP, None),
                          ("free_tool_id", 4)]

    with_clear = FakeMonitoring(with_clear=True)
    namespace["_release_tool"](types.SimpleNamespace(monitoring=with_clear))
    assert with_clear.calls == [("clear_tool_id", 4), ("free_tool_id", 4)]


# --- on_event ---------------------------------------------------------------------------------------------------------------

def test_on_event_accepts_line_and_jump_arities_disables_other_code_counts_traced_code_once_per_thread_and_marks_failed_on_exception(
        tmp_path, monkeypatch):
    plugin_path, _ = plugin_env(tmp_path, monkeypatch)
    fake = FakeMonitoring()
    namespace = exec_plugin(plugin_path, monkeypatch, fake=fake)
    state = fresh_state(namespace)
    on_event = namespace["on_event"]
    traced, other = unique_code("on_event_traced"), unique_code("on_event_other")
    state.traced_ids.add(id(traced))
    state.keep.append(traced)
    state.thread = threading.get_ident()

    assert on_event(other, 7) is fake.DISABLE  # a LINE event for code that is not ours
    assert on_event(other, 0, 12) is fake.DISABLE  # a JUMP event
    assert state.count == 0
    assert on_event(traced, 3) is None  # LINE: (code, line_number)
    assert on_event(traced, 0, 12) is None  # JUMP: (code, instruction_offset, destination_offset)
    assert state.count == 2

    worker = threading.Thread(target=on_event, args=(traced, 5))
    worker.start()
    worker.join()
    assert state.count == 2  # another thread is not counted
    assert state.failed is False
    assert not [c for c in fake.calls if c[0] in ("set_events", "register_callback")]

    class Exploding(object):
        def __getattribute__(self, name):
            raise RuntimeError(name)

        def __setattr__(self, name, value):
            object.__setattr__(self, name, value)

    boom = Exploding()
    namespace["STATE"] = boom
    assert on_event(traced, 3) is None  # swallowed, not propagated
    assert object.__getattribute__(boom, "__dict__")["failed"] is True


def test_membership_is_by_identity_an_equal_code_object_from_another_file_is_not_counted(tmp_path, monkeypatch):
    plugin_path, _ = plugin_env(tmp_path, monkeypatch)
    fake = FakeMonitoring()
    namespace = exec_plugin(plugin_path, monkeypatch, fake=fake)
    state = fresh_state(namespace)
    source = "x = 1\nif x:\n    x = 2\n"
    ours = compile(source, "/unique/identity_ours.py", "exec")
    twin = compile(source, "/unique/identity_twin.py", "exec")
    assert ours == twin and ours is not twin  # equal by value although compiled for different files
    state.traced_ids.add(id(ours))
    state.keep.append(ours)
    state.thread = threading.get_ident()

    assert namespace["on_event"](twin, 2) is fake.DISABLE
    assert state.count == 0
    assert namespace["on_event"](ours, 2) is None
    assert state.count == 1


# --- T3c: _traced_set, hooks and the terminal markers -----------------------------------------------------------------------

def make_function(filename, name, body="    return 1\n"):
    """A plain function whose code object reports ``filename`` and ``name``."""
    namespace = {}
    exec(compile(f"def {name}():\n{body}", filename, "exec"), namespace)
    return namespace[name]


def wrap_in(filename, inner, name="wrapper", use_wraps=True):
    """A decorator-style wrapper compiled for ``filename`` around ``inner`` (``functools.wraps`` unless told otherwise)."""
    import functools

    namespace = {"inner": inner, "wraps": functools.wraps}
    decorator = "@wraps(inner)\n" if use_wraps else ""
    exec(compile(f"{decorator}def {name}(*a, **k):\n    return inner(*a, **k)\n", filename, "exec"), namespace)
    return namespace[name]


def armed(tmp_path, monkeypatch, fake="default", **fields):
    """Exec the plugin, then give it a fresh STATE that is claimed, with ``out`` in a real directory. Returns (namespace, state, out)."""
    plugin_path, cwd = plugin_env(tmp_path, monkeypatch)
    if fake == "default":
        fake = FakeMonitoring()
    namespace = exec_plugin(plugin_path, monkeypatch, fake=fake)
    state = fresh_state(namespace)
    (tmp_path / "out").mkdir(exist_ok=True)
    state.out = str(tmp_path / "out" / "trace.out")
    state.nonce = NONCE
    state.root_real = os.path.realpath(cwd)
    state.target_real = os.path.realpath(cwd / "bench.py")
    state.claimed = True
    for key, value in fields.items():
        setattr(state, key, value)
    return namespace, state, state.out


@posix_only
def test_traced_set_rules(tmp_path, monkeypatch):
    namespace, state, _ = armed(tmp_path, monkeypatch)
    traced_set, target = namespace["_traced_set"], state.target_real

    plain = make_function(target, "test_x")
    assert traced_set(plain, "test_x") == (plain.__code__,)

    wrapper = wrap_in(target, plain)
    assert traced_set(wrapper, "test_x") == (wrapper.__code__, plain.__code__)  # the wrapper is counted too

    def chain(hops):
        link = plain
        for _ in range(hops):
            link = wrap_in(target, link)
        return link

    assert len(traced_set(chain(8), "test_x")) == 9  # obj plus exactly 8 hops
    assert traced_set(chain(9), "test_x") is None

    cyclic = make_function(target, "test_x")
    other = make_function(target, "test_x")
    cyclic.__wrapped__, other.__wrapped__ = other, cyclic
    assert traced_set(cyclic, "test_x") is None

    import functools
    assert traced_set(functools.partial(plain), "test_x") is None  # no __code__
    assert traced_set(wrap_in(target, functools.partial(plain)), "test_x") is None  # a link without __code__ inside the chain

    assert traced_set(make_function(target, "decoy"), "test_x") is None  # innermost name differs
    assert traced_set(wrap_in(target, make_function(target, "decoy")), "test_x") is None
    assert traced_set(wrap_in(target, plain, use_wraps=False), "test_x") is None  # no wraps: the wrapper is innermost and named differently
    assert traced_set(make_function("/unique/elsewhere.py", "test_x"), "test_x") is None  # innermost in another file
    assert traced_set(wrap_in(target, make_function("/unique/elsewhere.py", "test_x")), "test_x") is None


@posix_only
@pytest.mark.parametrize("count,failed", [(0, True), (1, False), (2, True)])
def test_collection_of_other_than_one_item_marks_failed(tmp_path, monkeypatch, count, failed):
    namespace, state, _ = armed(tmp_path, monkeypatch)
    namespace["pytest_collection_modifyitems"](None, None, [object() for _ in range(count)])
    assert state.failed is failed


@posix_only
def test_hooks_enable_line_and_jump_record_the_thread_disable_after_the_yield(tmp_path, monkeypatch):
    fake = FakeMonitoring()
    namespace, state, _ = armed(tmp_path, monkeypatch, fake=fake)
    func = wrap_in(state.target_real, make_function(state.target_real, "test_x"))
    item = types.SimpleNamespace(obj=func, originalname="test_x")
    fake.calls.clear()

    generator = namespace["pytest_pyfunc_call"](item)
    next(generator)
    assert fake.calls == [("register_callback", 4, 2, namespace["on_event"]), ("register_callback", 4, 4, namespace["on_event"]),
                          ("set_events", 4, 6)]
    assert state.thread == threading.get_ident()
    assert state.traced_ids == {id(func.__code__), id(func.__wrapped__.__code__)}
    assert {id(c) for c in state.keep} == state.traced_ids and len(state.keep) == 2
    with pytest.raises(StopIteration):
        next(generator)
    assert fake.calls[-1] == ("set_events", 4, 0)
    assert state.failed is False

    # a raising test body still ends the tracing (the wrapper is thrown into)
    fake.calls.clear()
    generator = namespace["pytest_pyfunc_call"](item)
    next(generator)
    with pytest.raises(RuntimeError):
        generator.throw(RuntimeError("boom"))
    assert fake.calls[-1] == ("set_events", 4, 0)

    # a decoy marks failed and drives nothing
    fake.calls.clear()
    state.failed = False
    decoy = types.SimpleNamespace(obj=make_function(state.target_real, "decoy"), originalname="test_x")
    generator = namespace["pytest_pyfunc_call"](decoy)
    next(generator)
    with pytest.raises(StopIteration):
        next(generator)
    assert state.failed is True
    assert fake.calls == []


class ForeignMonitoring(FakeMonitoring):
    """Another tool owns id 4: any claim fails and get_tool names someone else."""

    def get_tool(self, tool):
        self.calls.append(("get_tool", tool))
        return "somebody_else"


@posix_only
@pytest.mark.parametrize("mode", ["failed", "unavailable"])
def test_hooks_and_sessionfinish_make_no_monitoring_calls_when_not_claimed(tmp_path, monkeypatch, mode):
    fake = ForeignMonitoring()
    namespace, state, out = armed(tmp_path, monkeypatch, fake=fake)
    state.claimed = False
    if mode == "failed":
        state.failed = True
    else:
        state.unavailable = "tool_in_use"
    fake.calls.clear()
    item = types.SimpleNamespace(obj=make_function(state.target_real, "test_x"), originalname="test_x")

    generator = namespace["pytest_pyfunc_call"](item)
    next(generator)
    with pytest.raises(StopIteration):
        next(generator)
    namespace["pytest_sessionfinish"](None, 0)
    forbidden = ("set_events", "register_callback", "free_tool_id", "clear_tool_id")
    assert not [c for c in fake.calls if c[0] in forbidden]
    assert state.traced_ids == set() and state.thread is None
    if mode == "failed":
        assert Path(out + ".failed").read_text() == "failed\n" and not os.path.exists(out)
    else:
        assert Path(out).read_text().startswith("BENCH_TRACE_UNAVAILABLE: tool_in_use ")


def version_text():
    return "%d.%d.%d" % sys.version_info[:3]


def finish(namespace):
    namespace["pytest_sessionfinish"](None, 0)


def markers(out):
    return {suffix: Path(out + suffix).read_text() for suffix in ("", ".failed") if os.path.exists(out + suffix)}


@posix_only
def test_sessionfinish_writes_exactly_one_marker_with_the_documented_content_and_precedence(tmp_path, monkeypatch):
    impl = sys.implementation.name
    success = f"BENCH_TRACE_LINES: 7 {version_text()} {impl} {NONCE}\n"

    def fresh(name, **fields):
        sub = tmp_path / name
        sub.mkdir()
        return armed(sub, monkeypatch, **fields)

    # success
    namespace, state, out = fresh("success", count=7)
    finish(namespace)
    assert markers(out) == {"": success}
    assert os.stat(out).st_mode & 0o777 == 0o600

    # failed beats unavailable and a count; the marker is the .failed file
    namespace, state, out = fresh("failed", count=7, failed=True, unavailable="tool_in_use")
    finish(namespace)
    assert markers(out) == {".failed": "failed\n"}
    assert os.stat(out + ".failed").st_mode & 0o777 == 0o600

    # unavailable beats a zero count
    namespace, state, out = fresh("unavailable", claimed=False, unavailable="no_monitoring")
    finish(namespace)
    assert markers(out) == {"": f"BENCH_TRACE_UNAVAILABLE: no_monitoring {version_text()} {impl} {NONCE}\n"}

    # a zero count when not unavailable is a failure
    namespace, state, out = fresh("zero", count=0)
    finish(namespace)
    assert markers(out) == {".failed": "failed\n"}

    # two collected tests after a successful claim
    namespace, state, out = fresh("two", count=7)
    namespace["pytest_collection_modifyitems"](None, None, [object(), object()])
    finish(namespace)
    assert markers(out) == {".failed": "failed\n"}

    # a get_tool answer naming another tool
    namespace, state, out = fresh("othertool", count=7)
    monkeypatch.setattr(sys, "monitoring", ForeignMonitoring(), raising=False)
    finish(namespace)
    assert markers(out) == {".failed": "failed\n"}

    # a raising release is swallowed and yields .failed
    class RaisingRelease(FakeMonitoring):
        def free_tool_id(self, tool):
            raise RuntimeError("cannot free")

    namespace, state, out = fresh("release", count=7)
    monkeypatch.setattr(sys, "monitoring", RaisingRelease(), raising=False)
    finish(namespace)
    assert markers(out) == {".failed": "failed\n"}

    # a normal claimed finish: events off first, then the check, then the release
    fake = FakeMonitoring()
    namespace, state, out = fresh("sequence", count=7, fake=fake)
    fake.calls.clear()
    finish(namespace)
    assert fake.calls == [("set_events", 4, 0), ("get_tool", 4), ("register_callback", 4, 2, None), ("register_callback", 4, 4, None),
                          ("free_tool_id", 4)]


@posix_only
def test_sessionfinish_exits_with_status_3_when_no_marker_can_be_written(tmp_path, monkeypatch):
    for name, fields, pre in (("both", {"count": 3}, ("", ".failed")), ("failedonly", {"failed": True}, (".failed",)),
                              ("noout", {"count": 3, "out": None}, ())):
        sub = tmp_path / name
        sub.mkdir()
        namespace, state, out = armed(sub, monkeypatch, **fields)
        for suffix in pre:
            Path(out + suffix).write_text("pre-existing\n")
        with pytest.raises(pytest.exit.Exception) as caught:
            finish(namespace)
        assert caught.value.returncode == 3, name
        if pre:
            assert all(Path(out + suffix).read_text() == "pre-existing\n" for suffix in pre)  # nothing overwritten

    # only the primary marker exists: the success write loses O_EXCL, falls back to .failed
    sub = tmp_path / "primary"
    sub.mkdir()
    namespace, state, out = armed(sub, monkeypatch, count=3)
    Path(out).write_text("pre-existing\n")
    finish(namespace)
    assert markers(out) == {"": "pre-existing\n", ".failed": "failed\n"}


@posix_only
def test_a_one_byte_at_a_time_os_write_still_yields_the_whole_marker(tmp_path, monkeypatch):
    namespace, state, out = armed(tmp_path, monkeypatch, count=11)
    real_open, real_write = os.open, os.write
    marker_fds = set()

    def spy_open(path, flags, *args, **kwargs):
        fd = real_open(path, flags, *args, **kwargs)
        if str(path).startswith(str(tmp_path / "out")):
            marker_fds.add(fd)
        return fd

    def one_byte(fd, data):
        return real_write(fd, bytes(data)[:1]) if fd in marker_fds else real_write(fd, data)

    monkeypatch.setattr(os, "open", spy_open)
    monkeypatch.setattr(os, "write", one_byte)
    try:
        finish(namespace)
    finally:
        monkeypatch.undo()  # restores os.open and os.write (and the other patches; the test is over)
    assert markers(out) == {"": f"BENCH_TRACE_LINES: 11 {version_text()} {sys.implementation.name} {NONCE}\n"}
    assert os.write is real_write


def test_the_plugin_source_never_names_restart_events():
    tree = ast.parse(bg.TRACE_PLUGIN_SOURCE)
    for node in ast.walk(tree):
        assert not (isinstance(node, ast.Attribute) and node.attr == "restart_events")
        assert not (isinstance(node, ast.Name) and node.id == "restart_events")
    assert "get_tool" in bg.TRACE_PLUGIN_SOURCE and re.search(r"get_tool\(\s*4\s*\)\s*!=\s*['\"]" + re.escape(bg._TRACE_MODULE) + "['\"]",
                                                              bg.TRACE_PLUGIN_SOURCE)


@posix_only
@needs_monitoring
def test_a_real_smoke_launch_writes_a_success_marker(tmp_path):
    plugin_dir, out_dir, root, scratch = (tmp_path / name for name in ("plug", "outdir", "root", "scratch"))
    for directory in (plugin_dir, out_dir, root, scratch):
        directory.mkdir()
    (plugin_dir / "bench_trace_plugin.py").write_text(bg.TRACE_PLUGIN_SOURCE)
    (root / "test_x.py").write_text("def test_x():\n    total = 0\n    for i in range(50):\n        total += i\n")
    ini = tmp_path / "harness.ini"
    ini.write_text("[pytest]\n")
    bin_dir = str(pytest_venv(tmp_path / "venv"))
    out_path = str(out_dir / "trace.out")
    nonce = "f" * 32

    argv = bg.pytest_argv(bin_dir, str(root), "test_x.py::test_x", str(ini), plugins=(bg._TRACE_MODULE,))
    env = bg.trace_env(bg.side_env(bin_dir, str(scratch)), str(plugin_dir), "test_x.py", out_path, nonce)
    code, _elapsed, stdout, tail, _oversize = bg._run_once(argv, str(root), env, 120)

    assert code == 0, (stdout[-500:], tail)
    assert not os.path.exists(out_path + ".failed")
    match = re.search(r"^BENCH_TRACE_LINES: ([0-9]+) ([0-9.]+) ([a-z]+) " + nonce + r"$", Path(out_path).read_text(), re.M)
    assert match, Path(out_path).read_text()
    assert int(match.group(1)) >= 50


# --- T4a: the plugin file helpers ----------------------------------------------------------------------------------------------

@posix_only
def test_write_plugin_makes_one_read_only_file_and_verify_plugin_rejects_a_tampered_one(tmp_path):
    plugin_dir = tmp_path / "plug"
    plugin_dir.mkdir()
    path = bg._write_plugin(str(plugin_dir))
    assert path == str(plugin_dir / (bg._TRACE_MODULE + ".py"))
    assert os.listdir(plugin_dir) == [bg._TRACE_MODULE + ".py"]
    assert Path(path).read_bytes() == bg.TRACE_PLUGIN_SOURCE.encode("ascii")
    assert os.stat(path).st_mode & 0o777 == 0o400
    with pytest.raises((OSError, bg.BenchmarkGateError)):
        bg._write_plugin(str(plugin_dir))
    assert bg._verify_plugin(path) is None

    def refused():
        with pytest.raises(bg.BenchmarkGateError) as info:
            bg._verify_plugin(path)
        assert info.value.code == "MEASURE_FAILED"
        assert "plugin file hash mismatch" in info.value.detail

    os.chmod(path, 0o600)
    Path(path).write_bytes(b"# other\n")
    refused()
    os.unlink(path)
    Path(path).write_bytes(b"# recreated\n")
    refused()
    os.unlink(path)
    refused()

    colon_dir = tmp_path / "a:b"
    os.mkdir(colon_dir)
    with pytest.raises(bg.BenchmarkGateError) as info:
        bg._write_plugin(str(colon_dir))
    assert info.value.code == "MEASURE_FAILED"
    assert os.listdir(colon_dir) == []


# --- T4b: trace_paired with a fake child --------------------------------------------------------------------------------------
# The fake replaces ``bg._run_once``: it gets the real environment (so it reads BENCH_TRACE_OUT and BENCH_TRACE_NONCE from it, as the
# plugin would) and writes the marker file it wants. No real pytest is launched here (T4c does that).

class OsProxy:
    """Stands in for ``bg.os`` so ``os.name`` or ``os.getuid`` can be changed for the module under test only."""

    def __init__(self, **overrides):
        self._overrides = overrides

    def __getattr__(self, name):
        return self._overrides[name] if name in self._overrides else getattr(os, name)


def put(call, content):
    data = content.encode("ascii") if isinstance(content, str) else content
    with open(call.out, "wb") as handle:
        handle.write(data)


def good(count=5, version="3.12.1", impl="cpython"):
    def behave(call):
        put(call, f"BENCH_TRACE_LINES: {count} {version} {impl} {call.nonce}\n")
    return behave


def unavailable(token="no_monitoring", version="3.12.1", impl="cpython"):
    def behave(call):
        put(call, f"BENCH_TRACE_UNAVAILABLE: {token} {version} {impl} {call.nonce}\n")
    return behave


def valid_text(nonce, count=5):
    return f"BENCH_TRACE_LINES: {count} 3.12.1 cpython {nonce}\n"


class TraceFake:
    """The fake ``bg._run_once``: records each call, then runs the side's behaviour (which may write the marker and return a run tuple)."""

    def __init__(self, monkeypatch, roots, behaviors):
        self.calls = []
        self.sides = {os.path.realpath(str(path)): side for side, path in roots.items()}
        self.behaviors = behaviors
        monkeypatch.setattr(bg, "_run_once", self)

    def __call__(self, argv, cwd, env, timeout):
        side = self.sides[cwd]
        call = types.SimpleNamespace(side=side, argv=argv, env=env, timeout=timeout, out=env["BENCH_TRACE_OUT"],
                                     nonce=env["BENCH_TRACE_NONCE"], stdout=b"")
        self.calls.append(call)
        outcome = self.behaviors[side](call)
        return outcome if outcome is not None else (0, 1, call.stdout, b"", False)


def subdir(tmp_path, name):
    path = tmp_path / name
    path.mkdir()
    return path


def trace_setup(tmp_path, monkeypatch, base=None, head=None):
    roots, bins = fake_sides(tmp_path)
    fake = TraceFake(monkeypatch, roots, {"base": base or good(), "head": head or good()})

    def run(**overrides):
        kwargs = {"target": "bench.py::test_x", "timeout_seconds": 10, **overrides}
        return bg.trace_paired(str(roots["base"]), str(roots["head"]), str(bins["base"]), str(bins["head"]), **kwargs)

    return fake, run, roots, bins


def trace_error(run, **overrides):
    with pytest.raises(bg.BenchmarkGateError) as info:
        run(**overrides)
    return info.value


def run_with_deadline(run, **overrides):
    """Run ``run`` in a daemon thread and fail (instead of hanging the suite) when it does not finish within five seconds."""
    box = {}

    def target():
        try:
            box["result"] = run(**overrides)
        except BaseException as exc:  # noqa: BLE001 - handed back to the test
            box["error"] = exc

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(5)
    assert not thread.is_alive(), "trace_paired hung"
    if "error" in box:
        raise box["error"]
    return box["result"]


@posix_only
def test_result_file_is_read_from_out_dir_after_scratch_is_removed(tmp_path, monkeypatch):
    outs = []

    def straight_base(call):
        outs.append(call.out)
        # rewrite the benchmark while the base child runs: the control-flow flag was fixed before the first run
        (tmp_path / "base-root" / "bench.py").write_text("def test_x():\n    for i in range(3):\n        pass\n")
        good(7)(call)

    fake, run, roots, bins = trace_setup(tmp_path, monkeypatch, base=straight_base, head=good(7))
    (roots["base"] / "bench.py").write_text("def test_x():\n    x = 1\n")
    ini = tmp_path / "given.ini"
    ini.write_text("[pytest]\n")
    result = run(ini_path=str(ini))
    assert result["base"] == 7 and result["head"] == 7
    assert result["interpreter"] == "3.12.1 cpython"
    assert result["body_has_control_flow"] is False
    assert [c.side for c in fake.calls] == ["base", "head"]
    assert fake.calls[0].nonce != fake.calls[1].nonce
    for side, call in zip(("base", "head"), fake.calls):
        assert result["argv"][side] == call.argv
        assert result["argv"][side] == bg.pytest_argv(os.path.realpath(str(bins[side])), os.path.realpath(str(roots[side])),
                                                      "bench.py::test_x", str(ini), plugins=(bg._TRACE_MODULE,))
        scratch = os.path.dirname(call.env["HOME"])
        assert not call.out.startswith(scratch + os.sep) and os.path.dirname(call.out) != scratch
        assert os.path.basename(call.out) == "trace.out"
        assert re.fullmatch(r"[0-9a-f]{32}", call.nonce)
        assert not os.path.exists(os.path.dirname(call.out))  # the whole per-side work directory is gone
        assert os.path.basename(call.env["PYTHONPATH"]).startswith("plugin-")
    # the default ini lives in the side's work directory
    fake2, run2, _, _ = trace_setup(subdir(tmp_path, "second"), monkeypatch)
    result2 = run2()
    argv = result2["argv"]["base"]
    assert argv[argv.index("-c") + 1].endswith(os.sep + "empty.ini")
    assert argv[argv.index("-p", argv.index("no:cacheprovider")) + 1] == bg._TRACE_MODULE
    assert [c.side for c in fake2.calls] == ["base", "head"]


@posix_only
def test_a_looping_benchmark_reports_control_flow(tmp_path, monkeypatch):
    _, run, roots, _ = trace_setup(tmp_path, monkeypatch)
    (roots["base"] / "bench.py").write_text("def test_x():\n    for i in range(3):\n        pass\n")
    assert run()["body_has_control_flow"] is True


def valid_variants():
    return {
        "trailing text": lambda n: valid_text(n) + "extra\n",
        "no newline": lambda n: valid_text(n)[:-1],
        "hex count": lambda n: f"BENCH_TRACE_LINES: 12ab 3.12.1 cpython {n}\n",
        "float count": lambda n: f"BENCH_TRACE_LINES: 5.5 3.12.1 cpython {n}\n",
        "19 digits": lambda n: f"BENCH_TRACE_LINES: {10 ** 18} 3.12.1 cpython {n}\n",
        "zero count": lambda n: valid_text(n, 0),
        "wrong nonce": lambda n: valid_text("f" * 32),
        "empty": lambda n: "",
        "257 bytes": lambda n: valid_text(n) + "x" * (257 - len(valid_text(n))),
        "unknown line": lambda n: f"BENCH_TRACE_OTHER: 5 3.12.1 cpython {n}\n",
    }


@posix_only
@pytest.mark.parametrize("name", sorted(valid_variants()))
def test_the_result_validation_matrix_content(tmp_path, monkeypatch, name):
    make = valid_variants()[name]
    _, run, _, _ = trace_setup(tmp_path, monkeypatch, base=lambda call: put(call, make(call.nonce)))
    error = trace_error(run)
    assert (error.code, error.side, error.phase, error.partial) == ("TRACE_MISMATCH", "base", "trace", None)
    assert error.detail == "no trace result"


@posix_only
def test_a_valid_result_is_accepted_up_to_the_size_cap(tmp_path, monkeypatch):
    _, run, _, _ = trace_setup(tmp_path, monkeypatch, base=lambda call: put(call, valid_text(call.nonce, 10 ** 17)),
                               head=lambda call: put(call, valid_text(call.nonce, 10 ** 17)))
    assert run()["base"] == 10 ** 17


def structural_rows():
    def symlink(call):
        real = Path(call.out).parent.parent / "elsewhere"
        real.write_text(valid_text(call.nonce))
        os.symlink(real, call.out)

    def hardlink(call):
        put(call, valid_text(call.nonce))
        os.link(call.out, call.out + ".twin")

    def failed_marker(call):
        good()(call)
        put(SimpleCall(call.out + ".failed"), "failed\n")

    def dangling_failed(call):
        good()(call)
        os.symlink("/nonexistent-bench-trace-target", call.out + ".failed")

    def only_failed(call):
        put(SimpleCall(call.out + ".failed"), "failed\n")

    return {
        "symlink": (symlink, "no trace result"),
        "hardlink": (hardlink, "no trace result"),
        "failed marker": (failed_marker, "plugin reported failure"),
        "dangling failed symlink": (dangling_failed, "plugin reported failure"),
        "only failed": (only_failed, "plugin reported failure"),
        "absent": (lambda call: None, "no trace result"),
    }


class SimpleCall:
    def __init__(self, out):
        self.out = out


@posix_only
@pytest.mark.parametrize("name", sorted(structural_rows()))
def test_the_result_validation_matrix_structure(tmp_path, monkeypatch, name):
    behave, detail = structural_rows()[name]
    _, run, _, _ = trace_setup(tmp_path, monkeypatch, base=behave)
    error = trace_error(run)
    assert (error.code, error.side, error.phase, error.partial) == ("TRACE_MISMATCH", "base", "trace", None)
    assert error.detail == detail


@posix_only
def test_the_result_validation_matrix_wrong_uid(tmp_path, monkeypatch):
    _, run, _, _ = trace_setup(tmp_path, monkeypatch)
    monkeypatch.setattr(bg, "os", OsProxy(getuid=lambda: os.getuid() + 1))
    error = trace_error(run)
    assert (error.code, error.side, error.detail) == ("TRACE_MISMATCH", "base", "no trace result")


@posix_only
def test_a_fifo_at_the_out_path_is_rejected_without_hanging(tmp_path, monkeypatch):
    paths = []

    def fifo(call):
        os.mkfifo(call.out)
        paths.append(call.out)

    _, run, _, _ = trace_setup(tmp_path, monkeypatch, base=fifo)
    try:
        with pytest.raises(bg.BenchmarkGateError) as info:
            run_with_deadline(run)
    finally:
        for path in paths:  # unblock a reader that is stuck in open(), if the implementation hangs
            try:
                os.close(os.open(path, os.O_NONBLOCK | os.O_WRONLY))
            except OSError:
                pass
    assert (info.value.code, info.value.side, info.value.detail) == ("TRACE_MISMATCH", "base", "no trace result")


@posix_only
def test_a_directory_at_the_out_path_is_rejected_without_hanging(tmp_path, monkeypatch):
    _, run, _, _ = trace_setup(tmp_path, monkeypatch, base=lambda call: os.mkdir(call.out))
    with pytest.raises(bg.BenchmarkGateError) as info:
        run_with_deadline(run)
    assert (info.value.code, info.value.side, info.value.detail) == ("TRACE_MISMATCH", "base", "no trace result")


@posix_only
@pytest.mark.parametrize("base,head,code,side,needle", [
    (unavailable("no_monitoring"), good(), "TRACE_MISMATCH", "base", "unavailable on one side only"),
    (good(), unavailable("no_monitoring"), "TRACE_MISMATCH", "head", "unavailable on one side only"),
    (unavailable("no_monitoring"), unavailable("tool_in_use"), "TRACE_MISMATCH", None, "no_monitoring"),
    (unavailable("tool_in_use"), unavailable("tool_in_use"), "TRACE_UNAVAILABLE", None, "tool_in_use"),
    (unavailable("no_monitoring"), unavailable("no_monitoring"), "TRACE_UNAVAILABLE", None, "no_monitoring"),
    (unavailable("tool_in_use", "3.12.1"), unavailable("tool_in_use", "3.12.2"), "TRACE_MISMATCH", None, "3.12.2"),
    (good(5, "3.12.1"), good(5, "3.13.0"), "TRACE_MISMATCH", None, "3.13.0"),
    (good(5), good(6), "TRACE_MISMATCH", None, "5"),
])
def test_the_unavailable_decision_table(tmp_path, monkeypatch, base, head, code, side, needle):
    _, run, _, _ = trace_setup(tmp_path, monkeypatch, base=base, head=head)
    error = trace_error(run)
    assert (error.code, error.side, error.phase, error.partial) == (code, side, "trace", None)
    assert needle in error.detail


@posix_only
def test_the_decision_table_details_name_both_values(tmp_path, monkeypatch):
    _, run, _, _ = trace_setup(tmp_path, monkeypatch, base=good(5, "3.12.1"), head=good(5, "3.13.0", "pypy"))
    detail = trace_error(run).detail
    assert "3.12.1 cpython" in detail and "3.13.0 pypy" in detail
    _, run, _, _ = trace_setup(subdir(tmp_path, "b"), monkeypatch, base=good(5), head=good(6))
    detail = trace_error(run).detail
    assert "5" in detail and "6" in detail


@posix_only
def test_a_base_unavailable_result_is_overridden_by_a_head_hard_failure(tmp_path, monkeypatch):
    fake, run, _, _ = trace_setup(tmp_path, monkeypatch, base=unavailable(), head=lambda call: (3, 1, b"", b"boom", False))
    error = trace_error(run)
    assert (error.code, error.side, error.phase, error.partial) == ("TRACE_MISMATCH", "head", "trace", None)
    assert error.detail.startswith("nonzero:")
    assert [c.side for c in fake.calls] == ["base", "head"]


@posix_only
def test_a_hard_failure_stops_before_the_second_side_and_names_the_side(tmp_path, monkeypatch):
    fake, run, _, _ = trace_setup(tmp_path, monkeypatch, base=lambda call: (1, 1, b"", b"", False))
    error = trace_error(run)
    assert (error.code, error.side, error.phase) == ("TRACE_MISMATCH", "base", "trace")
    assert [c.side for c in fake.calls] == ["base"]
    fake, run, _, _ = trace_setup(subdir(tmp_path, "h"), monkeypatch, head=lambda call: (1, 1, b"", b"", False))
    error = trace_error(run)
    assert (error.code, error.side) == ("TRACE_MISMATCH", "head")
    assert [c.side for c in fake.calls] == ["base", "head"]


def spawn_failure(call):
    raise bg._SpawnFailed("no python")


@posix_only
@pytest.mark.parametrize("side", ["base", "head"])
@pytest.mark.parametrize("kind,outcome", [
    ("timeout", lambda call: (None, 1, b"", b"", False)),
    ("nonzero", lambda call: (2, 1, b"", b"it broke", False)),
    ("nonzero", lambda call: (-9, 1, b"", b"", False)),
    ("oversize", lambda call: (0, 1, b"", b"", True)),
    ("spawn", spawn_failure),
])
def test_each_trace_failure_kind_is_trace_mismatch_with_the_kind_prefix(tmp_path, monkeypatch, side, kind, outcome):
    behaviors = {"base": good(), "head": good()}
    behaviors[side] = outcome
    _, run, _, _ = trace_setup(tmp_path, monkeypatch, **behaviors)
    error = trace_error(run, timeout_seconds=4)
    assert (error.code, error.side, error.phase, error.partial) == ("TRACE_MISMATCH", side, "trace", None)
    assert error.detail.startswith(kind + ":")
    if kind == "timeout":
        assert error.detail.endswith(" (3x the per-run timeout)")
        assert "12 s" in error.detail


@posix_only
@pytest.mark.parametrize("timeout_seconds", [7, 2.5, 1])
def test_trace_timeout_argument_is_three_times_timeout_seconds(tmp_path, monkeypatch, timeout_seconds):
    fake, run, _, _ = trace_setup(tmp_path, monkeypatch)
    run(timeout_seconds=timeout_seconds)
    assert [c.timeout for c in fake.calls] == [3 * timeout_seconds, 3 * timeout_seconds]


@posix_only
def test_validation_precedence_platform_then_timeout_then_sides_and_phase_none_for_them(tmp_path, monkeypatch):
    fake, run, roots, bins = trace_setup(tmp_path, monkeypatch)
    good_args = (str(roots["base"]), str(roots["head"]), str(bins["base"]), str(bins["head"]))

    def attempt(args=good_args, target="bench.py::t", timeout=10, **kw):
        with pytest.raises(bg.BenchmarkGateError) as info:
            bg.trace_paired(*args, target, timeout_seconds=timeout, **kw)
        error = info.value
        assert (error.side, error.phase, error.partial) == (None, None, None)
        return error

    bad_args = ("relative", *good_args[1:])
    with monkeypatch.context() as patch:
        patch.setattr(bg, "os", OsProxy(name="nt"))
        assert attempt(args=bad_args, timeout=0).code == "UNSUPPORTED_PLATFORM"
    timeout_error = attempt(args=bad_args, timeout=0)
    assert timeout_error.code == "MEASURE_ARGS_INVALID" and "timeout_seconds" in timeout_error.detail
    assert attempt(args=bad_args, target="/abs.py").detail == "base root must be an existing absolute directory"
    assert attempt(target="/abs.py").detail == bg._TARGET_MESSAGE
    assert "ini_path" in attempt(ini_path="relative.ini").detail
    assert fake.calls == []


@posix_only
def test_every_error_after_validation_carries_phase_trace(tmp_path, monkeypatch):
    _, run, _, _ = trace_setup(tmp_path, monkeypatch, base=unavailable("tool_in_use"), head=unavailable("tool_in_use"))
    error = trace_error(run)
    assert (error.code, error.side, error.phase, error.partial) == ("TRACE_UNAVAILABLE", None, "trace", None)
    _, run, _, _ = trace_setup(subdir(tmp_path, "m"), monkeypatch, head=good(9))
    error = trace_error(run)
    assert (error.code, error.side, error.phase, error.partial) == ("TRACE_MISMATCH", None, "trace", None)
    _, run, _, _ = trace_setup(subdir(tmp_path, "f"), monkeypatch)

    def refuse(plugin_dir):
        raise bg.BenchmarkGateError("MEASURE_FAILED", "plugin write failed: nope")

    monkeypatch.setattr(bg, "_write_plugin", refuse)
    error = trace_error(run)
    assert (error.code, error.side, error.phase, error.partial) == ("MEASURE_FAILED", None, "trace", None)
    assert error.detail == "plugin write failed: nope"


def assert_harness_fault(error, needle=None):
    assert (error.code, error.side, error.phase, error.partial) == ("MEASURE_FAILED", None, "trace", None)
    if needle:
        assert needle in error.detail


@posix_only
def test_harness_faults_are_measure_failed_with_phase_trace_no_side_and_no_partial(tmp_path, monkeypatch):
    real_mkdtemp = tempfile.mkdtemp
    fake, run, _, _ = trace_setup(tmp_path, monkeypatch)

    # a failing mkdtemp for the out directory
    with monkeypatch.context() as patch:
        def mkdtemp(suffix=None, prefix=None, dir=None):
            if prefix == "out-":
                raise OSError("no space")
            return real_mkdtemp(suffix, prefix, dir)

        patch.setattr(tempfile, "mkdtemp", mkdtemp)
        assert_harness_fault(trace_error(run), "OSError: no space")

    # an OSError out of _write_plugin
    with monkeypatch.context() as patch:
        def write_plugin(plugin_dir):
            raise OSError("read-only file system")

        patch.setattr(bg, "_write_plugin", write_plugin)
        assert_harness_fault(trace_error(run), "read-only file system")

    # a failing per-side work directory: the first side, then (after one good side) the second
    for fail_on in (1, 2):
        with monkeypatch.context() as patch:
            seen = []

            def mkdtemp_work(suffix=None, prefix=None, dir=None):
                if prefix == "bench-trace-":
                    seen.append(prefix)
                    if len(seen) == fail_on:
                        raise OSError("no space for work")
                return real_mkdtemp(suffix, prefix, dir)

            patch.setattr(tempfile, "mkdtemp", mkdtemp_work)
            assert_harness_fault(trace_error(run), "no space for work")
    assert [c.side for c in fake.calls] == ["base"]  # only the fail_on == 2 round got as far as a child run

    # a path separator in the temp directory name
    unique = tmp_path / "a:b"
    unique.mkdir()
    before = len(fake.calls)
    with monkeypatch.context() as patch:
        patch.setattr(tempfile, "tempdir", str(unique))
        assert_harness_fault(trace_error(run), "path separator")
    assert len(fake.calls) == before


@posix_only
def test_a_tampered_plugin_is_caught_after_the_argv_builder_runs(tmp_path, monkeypatch):
    import glob

    unique = tmp_path / "unique-temp"
    unique.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(unique))
    fake, run, _, _ = trace_setup(tmp_path, monkeypatch)
    rewritten = []

    def build(side, bin_dir, root, target):
        for path in glob.glob(str(unique / "bench-trace-*" / "plugin-*" / "bench_trace_plugin.py")):
            os.chmod(path, 0o600)
            Path(path).write_text("# tampered\n")
            rewritten.append(path)
        return [sys.executable, "-c", "pass"]

    error = trace_error(run, argv_builder=build)
    assert_harness_fault(error, "plugin file hash mismatch")
    assert len(rewritten) == 1
    assert fake.calls == []


@posix_only
def test_interpreters_must_match_across_sides(tmp_path, monkeypatch):
    for index, (base, head) in enumerate([(("3.12.1", "cpython"), ("3.12.2", "cpython")), (("3.12.1", "cpython"), ("3.12.1", "pypy"))]):
        _, run, _, _ = trace_setup(subdir(tmp_path, str(index)), monkeypatch, base=good(5, *base), head=good(5, *head))
        error = trace_error(run)
        assert (error.code, error.side) == ("TRACE_MISMATCH", None)
        assert " ".join(base) in error.detail and " ".join(head) in error.detail


@posix_only
def test_the_digest_is_not_checked_and_stdout_is_not_parsed(tmp_path, monkeypatch):
    def noisy(call):
        call.stdout = b"BENCH_RESULT_DIGEST: not-a-digest\nBENCH_TRACE_LINES: 999 3.12.1 cpython " + call.nonce.encode() + b"\n"
        good(4)(call)

    _, run, _, _ = trace_setup(tmp_path, monkeypatch, base=noisy, head=noisy)
    result = run()
    assert (result["base"], result["head"]) == (4, 4)

    def forged_only(call):
        call.stdout = b"BENCH_TRACE_LINES: 999 3.12.1 cpython " + call.nonce.encode() + b"\n"

    _, run, _, _ = trace_setup(subdir(tmp_path, "f"), monkeypatch, base=forged_only)
    assert trace_error(run).detail == "no trace result"


def control_flow_cases():
    nested_only = "def test_x():\n    f = lambda: [i for i in range(3)]\n    def g():\n        for i in f():\n            pass\n    return g\n"
    cases = {
        "straight": ("def test_x():\n    x = 1\n    assert x\n", "bench.py::test_x", False),
        "for": ("def test_x():\n    for i in range(3):\n        pass\n", "bench.py::test_x", True),
        "async for": ("async def test_x():\n    async for i in y:\n        pass\n", "bench.py::test_x", True),
        "while": ("def test_x():\n    while False:\n        pass\n", "bench.py::test_x", True),
        "if": ("def test_x():\n    if 1:\n        pass\n", "bench.py::test_x", True),
        "ifexp": ("def test_x():\n    x = 1 if 2 else 3\n", "bench.py::test_x", True),
        "try": ("def test_x():\n    try:\n        pass\n    except Exception:\n        pass\n", "bench.py::test_x", True),
        "boolop": ("def test_x(a, b):\n    x = a or b\n", "bench.py::test_x", True),
        "listcomp": ("def test_x():\n    x = [i for i in range(3)]\n", "bench.py::test_x", True),
        "setcomp": ("def test_x():\n    x = {i for i in range(3)}\n", "bench.py::test_x", True),
        "dictcomp": ("def test_x():\n    x = {i: i for i in range(3)}\n", "bench.py::test_x", True),
        "match": ("def test_x(a):\n    match a:\n        case 1:\n            pass\n", "bench.py::test_x", True),
        "nested lambda and def only": (nested_only, "bench.py::test_x", False),
        "generator expression only": ("def test_x():\n    x = sum(i for i in range(3))\n", "bench.py::test_x", False),
        "nested async def only": ("def test_x():\n    async def g():\n        for i in y:\n            pass\n", "bench.py::test_x", False),
        "no test function": ("def helper():\n    for i in range(3):\n        pass\n", "bench.py", False),
        "no target name picks the first test": ("def helper():\n    pass\n\ndef test_a():\n    for i in range(3):\n        pass\n", "bench.py", True),
        "name picks the straight one": ("def test_a():\n    for i in range(3):\n        pass\n\ndef test_b():\n    pass\n", "bench.py::test_b", False),
        "name picks the looping one": ("def test_a():\n    pass\n\ndef test_b():\n    for i in range(3):\n        pass\n", "bench.py::test_b", True),
        "no name takes the first": ("def test_a():\n    pass\n\ndef test_b():\n    for i in range(3):\n        pass\n", "bench.py", False),
        "absent name falls back": ("def test_a():\n    for i in range(3):\n        pass\n", "bench.py::test_missing", True),
        "method target falls back": ("def test_a():\n    pass\n\nclass TestC:\n    def test_m(self):\n        for i in range(3):\n            pass\n",
                                     "bench.py::TestC::test_m", False),
        "class target falls back": ("def test_a():\n    pass\n\nclass TestC:\n    def test_m(self):\n        for i in range(3):\n            pass\n",
                                    "bench.py::TestC", False),
        "syntax error": ("def test_x(:\n", "bench.py::test_x", False),
        "NUL bytes": (b"def test_x():\n    for i in range(3):\n        pass\n\x00\n", "bench.py::test_x", False),
        "over 16 KiB": ("def test_x():\n    for i in range(3):\n        pass\n" + "#" * 17000 + "\n", "bench.py::test_x", False),
        "deeply nested": ("def test_x():\n    x = " + "(" * 400 + "1" + ")" * 400 + "\n    for i in x:\n        pass\n", "bench.py::test_x", False),
    }
    return cases


@posix_only
@pytest.mark.parametrize("name", sorted(control_flow_cases()))
def test_body_has_control_flow(tmp_path, monkeypatch, name):
    source, target, expected = control_flow_cases()[name]
    _, run, roots, _ = trace_setup(tmp_path, monkeypatch)
    path = roots["base"] / "bench.py"
    path.write_bytes(source if isinstance(source, bytes) else source.encode("ascii"))
    assert run(target=target)["body_has_control_flow"] is expected


@posix_only
def test_body_has_control_flow_is_false_for_a_missing_file_a_symlink_and_a_fifo(tmp_path, monkeypatch):
    _, run, roots, _ = trace_setup(tmp_path, monkeypatch)
    assert run()["body_has_control_flow"] is False  # missing
    real = tmp_path / "real.py"
    real.write_text("def test_x():\n    for i in range(3):\n        pass\n")
    os.symlink(real, roots["base"] / "bench.py")
    assert run()["body_has_control_flow"] is False  # O_NOFOLLOW
    os.unlink(roots["base"] / "bench.py")
    os.mkfifo(roots["base"] / "bench.py")
    assert run_with_deadline(run)["body_has_control_flow"] is False


# --- T4c: real-pytest rows (the real argv, plugin, markers and harness reading; relations and lower bounds only) ------------------

TARGET = "test_bench.py::test_bench"


def claiming_pth():
    """A venv ``.pth`` whose line takes sys.monitoring tool id 4 at interpreter start (before the plugin is imported)."""
    return {"zz_claim.pth": "import sys; sys.monitoring.use_tool_id(4, 'x')\n"}


def real_sides(tmp_path, bench, head_bench=None, base_libs=None, head_libs=None, extra_base=None, extra_head=None):
    """Two real sides: a root holding ``test_bench.py`` (plus ``extra_*`` files) and a pip-less venv with that side's library modules
    installed. Returns ``(base_root, head_root, base_bin, head_bin)`` as strings."""
    if head_libs is None:
        head_libs = base_libs
    roots, bins = [], []
    for side, source, libs, extra in (("base", bench, base_libs, extra_base), ("head", head_bench or bench, head_libs, extra_head)):
        root = tmp_path / f"{side}-root"
        root.mkdir()
        (root / "test_bench.py").write_text(textwrap.dedent(source))
        for name, content in (extra or {}).items():
            (root / name).write_text(textwrap.dedent(content))
        roots.append(str(root))
        bins.append(str(pytest_venv(tmp_path / f"{side}-venv", libs={k: textwrap.dedent(v) for k, v in (libs or {}).items()})))
    return roots[0], roots[1], bins[0], bins[1]


def launch(tmp_path, bench, target=TARGET, **kwargs):
    """The real ``trace_paired`` (no argv_builder). Returns the result dict."""
    base_root, head_root, base_bin, head_bin = real_sides(tmp_path, bench, **kwargs)
    return bg.trace_paired(base_root, head_root, base_bin, head_bin, target, timeout_seconds=120)


def launch_error(tmp_path, bench, target=TARGET, **kwargs):
    with pytest.raises(bg.BenchmarkGateError) as info:
        launch(tmp_path, bench, target=target, **kwargs)
    return info.value


@posix_only
@needs_monitoring
def test_batching_with_a_helper_below_the_callback_has_equal_counts(tmp_path):
    bench = """
        import lib

        def helper():
            return 1

        def callback(n=1):
            return helper()

        def test_bench():
            lib.go(callback)
    """
    base = {"lib.py": "def go(cb):\n    for _ in range(7):\n        cb()\n"}
    head = {"lib.py": "def go(cb):\n    cb(7)\n"}
    result = launch(tmp_path, bench, base_libs=base, head_libs=head)
    assert result["base"] == result["head"] >= 1


@posix_only
@needs_monitoring
def test_python_and_c_level_entries_count_the_same(tmp_path):
    bench = """
        import lib

        def callback(i):
            return i

        def test_bench():
            lib.entry(callback)
    """
    base = {"lib.py": "def entry(cb):\n    return [cb(i) for i in range(5)]\n"}
    head = {"lib.py": "def entry(cb):\n    return list(map(cb, range(5)))\n"}
    result = launch(tmp_path, bench, base_libs=base, head_libs=head)
    assert result["base"] == result["head"] >= 1


@posix_only
@needs_monitoring
@pytest.mark.parametrize("name,body", [
    ("while", "    total = 0\n    while lib.more():\n        total += 1\n"),
    ("one-line while", "    total = 0\n    while lib.more(): total += 1\n"),
    ("one-line for", "    total = 0\n    for x in lib.items(): total += x\n"),
])
def test_a_different_loop_count_differs_including_one_line_loops(tmp_path, name, body):
    bench = "import lib\n\n\ndef test_bench():\n" + body
    library = ("_left = [%d]\n\n\ndef more():\n    _left[0] -= 1\n    return _left[0] >= 0\n\n\n"
               "def items():\n    return range(%d)\n")
    error = launch_error(tmp_path, bench, base_libs={"lib.py": library % (3, 3)}, head_libs={"lib.py": library % (9, 9)})
    assert error.code == "TRACE_MISMATCH" and error.side is None and error.phase == "trace"
    match = re.fullmatch(r"line counts differ: base ([0-9]+), head ([0-9]+)", error.detail)
    assert match, error.detail
    assert 1 <= int(match.group(1)) < int(match.group(2))


@posix_only
@needs_monitoring
@pytest.mark.parametrize("name,body,base_lib,head_lib", [
    ("early return",
     "    for i in lib.items():\n        if i == lib.STOP:\n            return\n        lib.use(i)\n",
     "STOP = 99\n\n\ndef items():\n    return range(6)\n\n\ndef use(i):\n    return i\n",
     "STOP = 2\n\n\ndef items():\n    return range(6)\n\n\ndef use(i):\n    return i\n"),
    ("caught exception",
     "    try:\n        for i in lib.items():\n            lib.use(i)\n    except ValueError:\n        pass\n",
     "def items():\n    return range(6)\n\n\ndef use(i):\n    return i\n",
     "def items():\n    return range(6)\n\n\ndef use(i):\n    if i == 2:\n        raise ValueError(i)\n    return i\n"),
])
def test_early_return_and_a_caught_exception_abandoning_the_loop_differ(tmp_path, name, body, base_lib, head_lib):
    bench = "import lib\n\n\ndef test_bench():\n" + body
    error = launch_error(tmp_path, bench, base_libs={"lib.py": base_lib}, head_libs={"lib.py": head_lib})
    assert error.code == "TRACE_MISMATCH" and error.side is None
    assert error.detail.startswith("line counts differ: base "), error.detail


@posix_only
@needs_monitoring
def test_an_honest_fixed_count_benchmark_matches_itself(tmp_path):
    bench = "import lib\n\n\ndef test_bench():\n    a = lib.one()\n    b = lib.one()\n    assert a == b\n"
    library = {"lib.py": "def one():\n    return 1\n"}
    result = launch(tmp_path, bench, base_libs=library)
    assert result["base"] == result["head"] >= 3
    assert result["body_has_control_flow"] is False


@posix_only
@needs_monitoring
def test_wraps_traced_plain_wrapper_and_decoy_fail_closed(tmp_path):
    wrapped = """
        import functools


        def deco(f):
            @functools.wraps(f)
            def wrapper():
                return f()
            return wrapper


        @deco
        def test_bench():
            a = 1
            b = 2
    """
    result = launch(tmp_path, wrapped)
    assert result["base"] == result["head"] >= 2

    plain = """
        def deco(f):
            def wrapper():
                return f()
            return wrapper


        @deco
        def test_bench():
            a = 1
    """
    decoy = """
        def decoy():
            return 1


        def deco(f):
            def wrapper():
                return f()
            wrapper.__wrapped__ = decoy
            return wrapper


        @deco
        def test_bench():
            a = 1
    """
    for index, source in enumerate((plain, decoy)):
        error = launch_error(subdir(tmp_path, f"case{index}"), source)
        assert error.code == "TRACE_MISMATCH" and error.detail == "plugin reported failure" and error.side == "base"


@posix_only
@needs_monitoring
def test_two_tests_async_and_plugin_failure_are_trace_mismatch(tmp_path):
    two = """
        import pytest


        @pytest.mark.parametrize("n", [1, 2])
        def test_bench(n):
            a = n
    """
    error = launch_error(tmp_path, two)
    assert error.code == "TRACE_MISMATCH" and error.detail == "plugin reported failure" and error.side == "base"

    error = launch_error(subdir(tmp_path, "async"), "async def test_bench():\n    a = 1\n")
    assert error.code == "TRACE_MISMATCH"


def forged_library(action):
    """A library whose ``go()`` runs ``action`` (child code) with ``STATE``, ``OUT`` and ``FORGED`` (a 999 line with the right nonce) in scope."""
    return {"lib.py": (
        "import atexit\nimport os\nimport sys\n\n\n"
        "def go():\n"
        "    STATE = sys.modules['bench_trace_plugin'].STATE\n"
        "    OUT = STATE.out\n"
        "    FORGED = 'BENCH_TRACE_LINES: 999 %d.%d.%d cpython ' % sys.version_info[:3] + STATE.nonce + '\\n'\n"
        + textwrap.indent(textwrap.dedent(action), "    ") + "\n"
    )}


FORGE_BENCH = "import lib\n\n\ndef test_bench():\n    lib.go()\n    a = 1\n"
FORGE_TWO_TESTS = ("import lib\nimport pytest\n\n\n@pytest.mark.parametrize('n', [1, 2])\ndef test_bench(n):\n    lib.go()\n    a = n\n")


@posix_only
@needs_monitoring
def test_forged_results_are_not_accepted(tmp_path):
    counter = iter(range(100))

    def case(bench, action):
        library = forged_library(action)
        return launch(subdir(tmp_path, f"case{next(counter)}"), bench, base_libs=library)

    def case_error(bench, action):
        library = forged_library(action)
        return launch_error(subdir(tmp_path, f"case{next(counter)}"), bench, base_libs=library)

    # (a) 999 lines on stdout, at import time and at exit: stdout is never parsed
    result = case(FORGE_BENCH, "print('BENCH_TRACE_LINES: 999 3.12.0 cpython ' + 'f' * 32, flush=True)\n"
                               "atexit.register(print, 'BENCH_TRACE_LINES: 999 3.12.0 cpython ' + STATE.nonce)\n")
    assert "999" not in (result["base"], result["head"]) and result["base"] == result["head"] >= 1

    # (b) the out path created early in an honest run, with the right nonce: the plugin's O_EXCL fails -> .failed
    error = case_error(FORGE_BENCH, "with open(OUT, 'w') as handle:\n    handle.write(FORGED)\n")
    assert error.code == "TRACE_MISMATCH" and error.detail == "plugin reported failure" and error.side == "base"

    # (c) the same in a failing run (two tests)
    error = case_error(FORGE_TWO_TESTS, "with open(OUT, 'w') as handle:\n    handle.write(FORGED)\n")
    assert error.code == "TRACE_MISMATCH" and error.detail == "plugin reported failure"

    # (d) pre-create the file (wrong nonce) and leave through os._exit, so the plugin never runs its sessionfinish
    error = case_error(FORGE_BENCH, "with open(OUT, 'w') as handle:\n    handle.write(FORGED.replace(STATE.nonce, '0' * 32))\n"
                                    "getattr(os, '_e' + 'xit')(0)\n")
    assert error.code == "TRACE_MISMATCH" and error.side == "base" and error.detail == "no trace result"
    # ... and with no nonce at all
    error = case_error(FORGE_BENCH, "with open(OUT, 'w') as handle:\n    handle.write('BENCH_TRACE_LINES: 999 3.12.0 cpython\\n')\n"
                                    "getattr(os, '_e' + 'xit')(0)\n")
    assert error.code == "TRACE_MISMATCH" and error.side == "base" and error.detail == "no trace result"

    # (e) a FIFO at the out path, then os._exit: rejected without hanging
    error = case_error(FORGE_BENCH, "os.mkfifo(OUT)\ngetattr(os, '_e' + 'xit')(0)\n")
    assert error.code == "TRACE_MISMATCH" and error.side == "base" and error.detail == "no trace result"

    # (f) an atexit rewrite of the honest result with a wrong nonce, and one with no nonce
    for rewritten in ("FORGED.replace(STATE.nonce, '1' * 32)", "'BENCH_TRACE_LINES: 999 3.12.0 cpython\\n'"):
        error = case_error(FORGE_BENCH, (
            "def rewrite(path=OUT, text=%s):\n"
            "    os.unlink(path)\n"
            "    with open(path, 'w') as handle:\n"
            "        handle.write(text)\n\n\n"
            "atexit.register(rewrite)\n") % rewritten)
        assert error.code == "TRACE_MISMATCH" and error.side == "base" and error.detail == "no trace result"
        assert "999" not in error.detail


@posix_only
@needs_monitoring
def test_a_real_launch_with_tool_id_4_taken_by_a_venv_pth_reports_tool_in_use(tmp_path):
    bench = "def test_bench():\n    a = 1\n"
    error = launch_error(subdir(tmp_path, "both"), bench, base_libs=claiming_pth(), head_libs=claiming_pth())
    assert error.code == "TRACE_UNAVAILABLE" and "tool_in_use" in error.detail and error.phase == "trace"

    error = launch_error(subdir(tmp_path, "base"), bench, base_libs=claiming_pth(), head_libs={})
    assert error.code == "TRACE_MISMATCH" and error.side == "base"
    error = launch_error(subdir(tmp_path, "head"), bench, base_libs={}, head_libs=claiming_pth())
    assert error.code == "TRACE_MISMATCH" and error.side == "head"


@posix_only
@needs_monitoring
def test_release_and_reclaim_work_on_the_ci_interpreter(tmp_path, monkeypatch):
    plugin_path, _cwd = plugin_env(tmp_path, monkeypatch)
    monitoring = sys.monitoring
    namespace = None
    try:
        namespace = exec_plugin(plugin_path, monkeypatch, fake=None)
        assert namespace["STATE"].claimed and monitoring.get_tool(4) == bg._TRACE_MODULE
        namespace["_release_tool"](sys)
        assert monitoring.get_tool(4) is None
        assert namespace["_claim_tool"](sys) is None  # claimed again, for real
        assert monitoring.get_tool(4) == bg._TRACE_MODULE
    finally:
        if monitoring.get_tool(4) == bg._TRACE_MODULE:
            (namespace or {"_release_tool": None})["_release_tool"](sys)
        monitoring.restart_events()
    assert monitoring.get_tool(4) is None


@posix_only
@needs_monitoring
def test_an_outside_pointing_symlink_is_rejected_by_the_plugin(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "bench.py").write_text("def test_bench():\n    a = 1\n")
    base_root, head_root, base_bin, head_bin = real_sides(tmp_path, "def test_bench():\n    a = 1\n")
    for root in (base_root, head_root):
        os.symlink(outside, os.path.join(root, "evil"))
    target = "evil/bench.py::test_bench"

    error = None
    try:
        bg.trace_paired(base_root, head_root, base_bin, head_bin, target, timeout_seconds=120)
    except bg.BenchmarkGateError as exc:
        error = exc
    assert error is not None and error.code == "TRACE_MISMATCH" and error.detail == "plugin reported failure" and error.side == "base"

    # the same launch by hand: pytest itself is happy (exit 0), so the failure came from the plugin's init, not from the exit code
    plugin_dir, out_dir, scratch = (tmp_path / name for name in ("plug", "outdir", "scratch"))
    for directory in (plugin_dir, out_dir, scratch):
        directory.mkdir()
    bg._write_plugin(str(plugin_dir))
    ini = tmp_path / "harness.ini"
    ini.write_text("[pytest]\n")
    out_path = str(out_dir / "trace.out")
    argv = bg.pytest_argv(base_bin, base_root, target, str(ini), plugins=(bg._TRACE_MODULE,))
    env = bg.trace_env(bg.side_env(base_bin, str(scratch)), str(plugin_dir), target.split("::")[0], out_path, "e" * 32)
    code, _elapsed, stdout, tail, _oversize = bg._run_once(argv, base_root, env, 120)
    assert code == 0, (stdout[-500:], tail)
    assert os.path.lexists(out_path + ".failed") and not os.path.exists(out_path)


@posix_only
@needs_monitoring
@pytest.mark.parametrize("destination", ["'/'", "__import__('tempfile').gettempdir()"])
def test_a_benchmark_that_chdirs_at_import_still_matches(tmp_path, destination):
    bench = "import lib\n\n\ndef test_bench():\n    a = 1\n    b = 2\n"
    library = {"lib.py": "import os\n\nos.chdir(%s)\n" % destination}
    result = launch(tmp_path, bench, base_libs=library)
    assert result["base"] == result["head"] >= 2
