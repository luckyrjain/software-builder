"""C4d-2: the trace plugin (``TRACE_PLUGIN_SOURCE``) and, in later tasks, ``trace_paired``.

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
