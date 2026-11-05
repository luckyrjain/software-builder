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
    # T3c adds the `get_tool` check; until then only the `use_tool_id` literal exists.
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
