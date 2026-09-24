#!/usr/bin/env python3
"""Static, non-LLM lock/signal/idempotency safety classifier (F1 Condition 1).

Resolves architecture review Condition 1 for the F1 review-evidence gate (see
docs/superpowers/specs/2026-09-25-f1-condition1-lock-safety-classifier-design.md): a narrow,
purpose-built AST classifier `scripts/check_review_evidence.py`'s `build_verdict` calls to let
`review-evidence-post` auto-approve a sensitive-path PR when its diff shows no evidence of the
specific bug class F1 exists to catch (PR #289's lock-concurrency regression), and block
(defer to a human) otherwise.

Pure classification module -- no I/O of its own, mirroring `scripts/sensitive_path_match.py`'s
shape (design doc, Components table). The one public entry point, `check()`, is a pure function
of (file contents, changed line ranges) -> violation list; its caller (`build_verdict`) is the
only place that fetches anything.

The four rules (v1 scope) are grounded directly in this repo's own existing, correct patterns --
`scripts/install_engine.py`'s `held_lock()`/`_try_lock()`/`_unlock()` and
`_sigterm_as_system_exit()`'s `_on_stop` handler, and
`skills/pr-gatekeeper/scripts/idempotency_store.py`'s `run_if_new()` -- so they describe what
"looking like this codebase's own correct code" means, not an invented standard. See the design
doc's "The four rules (v1 scope)" table for the full rationale behind each one.

Each rule only ever considers *added* lines (per the caller-supplied `changed_lines`) -- pre-
existing code the PR did not touch is never flagged. Every rule is independent; a violation from
any one of them blocks the whole PR (conservative OR, not a weighted score). A file that fails
`ast.parse` produces its own violation (`rule: "unparseable"`) rather than being silently
skipped -- fail-closed, per the design doc's Failure strategy table.

This module parses Python *source code* with `ast.parse` -- source text that ultimately comes
from a PR author's own changes, so untrusted the same way the diff text
`scripts/sensitive_path_match.py` matches against is untrusted (see
docs/skill-framework/shared/prompt-injection.md). `ast.parse` never executes anything it reads,
and this module never executes, imports, or otherwise runs any code it is given -- it only ever
parses and inspects the resulting syntax tree as data.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

RULE_LOCK_WITHOUT_TRYFINALLY = "lock-without-tryfinally"
RULE_BARE_EXCEPT_ADDED = "bare-except-added"
RULE_UNSAFE_SIGNAL_HANDLER = "unsafe-signal-handler"
RULE_IDEMPOTENCY_CHECK_AFTER_EFFECT = "idempotency-check-after-effect"
RULE_UNPARSEABLE = "unparseable"

# Best-effort tokens identifying a "file descriptor/handle" style argument (design doc, rule
# `lock-without-tryfinally`: "called with a file descriptor/handle argument"). Grounded in this
# codebase's own naming: `fd` throughout install_engine.py's lock helpers, `lock_fh` in
# idempotency_store.py's `mr_lock`.
_FD_ARG_TOKENS = frozenset({"fd", "fh", "handle", "handles"})

# Function-name fragments identifying a "mark done" / write-type effect call (rule
# `idempotency-check-after-effect`).
_EFFECT_NAME_PREFIXES = ("mark_", "save_")
# Function-name fragments identifying an "is it already done" check call.
_CHECK_NAME_PREFIXES = ("should_",)


@dataclass(frozen=True)
class Violation:
    """One finding from `check()`."""

    file: str
    line: int
    rule: str
    message: str


def _build_parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    """Map every node in `tree` to its direct parent, for ancestor walks."""
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    return parents


def _has_ancestor_try_finally(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    """True iff an ancestor of `node`, *within `node`'s own function scope*, is a `try` with a
    non-empty `finally` body.

    Deliberately checks *every* ancestor up to (but never past) the nearest enclosing scope
    boundary -- `FunctionDef`/`AsyncFunctionDef`/`Lambda`, or `GeneratorExp` -- not just the
    nearest enclosing `try` -- a release call (e.g. `_unlock(fd)`) sitting inside its own inner
    `try/except` (no `finally` of its own) but nested *within* an outer `try/finally` in the
    *same* function (as `held_lock()` itself does) is still guarded: the outer `finally` is what
    guarantees this code path runs. Requiring the *nearest* `try` alone to carry the `finally`
    would false-positive on exactly this codebase's own clean pattern.

    The walk stops the instant it reaches one of those boundary ancestors -- i.e. the moment it
    would leave `node`'s own lexical scope -- and reports unprotected from there, even if an
    *outer* scope happens to have its own enclosing `try/finally`. A lock call made from inside a
    callback, lambda, or thread-worker function runs on that function's own schedule (e.g. after
    `executor.submit`, or on another thread), possibly long after an outer `try/finally` that
    merely *contains the definition* of that function has already exited -- so that outer
    `finally` provides no real release guarantee for it.

    A generator expression is the same story even though it looks like an inline expression, not
    a `def`: in Python 3, a `GeneratorExp`'s body executes lazily, on each call to `next()` --
    typically well after the statement that defined it has finished, including after any
    enclosing `try/finally` has already run its `finally` and exited. A lock call sitting in a
    genexp's body is therefore not actually protected by an outer `try/finally` any more than one
    inside a `def` would be, so `GeneratorExp` is a scope boundary here too.

    `ListComp`/`SetComp`/`DictComp` are deliberately *not* in this boundary set, even though they
    also get their own AST scope in Python 3: unlike a `GeneratorExp`, their body executes eagerly
    -- as part of evaluating the single statement that contains them -- so a lock call inside one
    of those genuinely does run before an enclosing `finally`, while control is still inside the
    `try` block evaluating that statement (e.g. `return [flock(fd) for fd in fds]` inside a
    `try:` calls `flock` for every `fd`, still within the `try`, before `finally` can run). Adding
    them as boundaries would stop the walk at the comprehension and report this genuinely-
    protected call as unprotected -- a new false positive on exactly the "already correctly
    handled" case this rule must not regress.
    """
    current = node
    while current in parents:
        current = parents[current]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.GeneratorExp)):
            return False
        if isinstance(current, ast.Try) and current.finalbody:
            return True
    return False


def _name_tokens(node: ast.AST) -> set[str]:
    """Best-effort lowercase, underscore-split tokens naming an argument expression."""
    if isinstance(node, ast.Name):
        return set(node.id.lower().split("_"))
    if isinstance(node, ast.Attribute):
        return _name_tokens(node.value) | set(node.attr.lower().split("_"))
    if isinstance(node, ast.Call):
        return _name_tokens(node.func)
    return set()


def _keyword_tokens(kw: ast.keyword) -> set[str]:
    """Best-effort lowercase, underscore-split tokens naming a keyword argument -- both the
    keyword's own name (`fd=...`) and its value expression (`handle=some_fd`), the same
    token-matching approach `_name_tokens` uses for positional arguments."""
    name_tokens = set(kw.arg.lower().split("_")) if kw.arg else set()
    return name_tokens | _name_tokens(kw.value)


def _has_fd_like_argument(call: ast.Call) -> bool:
    if any(_name_tokens(arg) & _FD_ARG_TOKENS for arg in call.args):
        return True
    return any(_keyword_tokens(kw) & _FD_ARG_TOKENS for kw in call.keywords)


def _call_name(call: ast.Call) -> str | None:
    """The call's own function name -- the final attribute, or a bare name."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _check_lock_without_tryfinally(
    tree: ast.AST, path: str, changed: set[int], parents: dict[ast.AST, ast.AST]
) -> list[Violation]:
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if node.lineno not in changed:
            continue
        name = _call_name(node)
        if not name or "lock" not in name.lower():
            continue
        if not _has_fd_like_argument(node):
            continue
        if _has_ancestor_try_finally(node, parents):
            continue
        violations.append(
            Violation(
                file=path,
                line=node.lineno,
                rule=RULE_LOCK_WITHOUT_TRYFINALLY,
                message=(
                    f"call to `{name}(...)` on what looks like a file descriptor/handle "
                    "argument has no enclosing try/finally to guarantee release"
                ),
            )
        )
    return violations


def _bare_except_body_is_trivial(handler: ast.ExceptHandler) -> bool:
    return all(isinstance(stmt, ast.Pass) for stmt in handler.body)


def _is_name(node: ast.AST | None, name: str) -> bool:
    return isinstance(node, ast.Name) and node.id == name


def _check_bare_except_added(tree: ast.AST, path: str, changed: set[int]) -> list[Violation]:
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if node.lineno not in changed:
            continue
        is_bare = node.type is None
        is_trivial_base_exception = _is_name(node.type, "BaseException") and _bare_except_body_is_trivial(node)
        if not (is_bare or is_trivial_base_exception):
            continue
        violations.append(
            Violation(
                file=path,
                line=node.lineno,
                rule=RULE_BARE_EXCEPT_ADDED,
                message=(
                    "bare `except:` (or an empty/pass-only `except BaseException:`) swallows "
                    "KeyboardInterrupt/SystemExit along with real errors"
                ),
            )
        )
    return violations


def _is_sys_exit_or_os_exit_call(call: ast.Call) -> bool:
    func = call.func
    if not isinstance(func, ast.Attribute) or not isinstance(func.value, ast.Name):
        return False
    return (func.value.id == "sys" and func.attr == "exit") or (func.value.id == "os" and func.attr == "_exit")


def _is_safe_signal_handler_stmt(stmt: ast.stmt) -> bool:
    if isinstance(stmt, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Global, ast.Nonlocal, ast.Pass, ast.Raise, ast.Return)):
        return True
    if isinstance(stmt, ast.If):
        return all(_is_safe_signal_handler_stmt(s) for s in stmt.body) and all(
            _is_safe_signal_handler_stmt(s) for s in stmt.orelse
        )
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        return _is_sys_exit_or_os_exit_call(stmt.value)
    return False


def _find_function_def(tree: ast.AST, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _is_signal_signal_call(call: ast.Call) -> bool:
    func = call.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "signal"
        and isinstance(func.value, ast.Name)
        and func.value.id == "signal"
    )


def _signal_handler_arg(call: ast.Call) -> ast.expr | None:
    if len(call.args) >= 2:
        return call.args[1]
    for kw in call.keywords:
        if kw.arg == "handler":
            return kw.value
    return None


def _check_unsafe_signal_handler(tree: ast.AST, path: str, changed: set[int]) -> list[Violation]:
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_signal_signal_call(node):
            continue
        if node.lineno not in changed:
            continue
        handler_arg = _signal_handler_arg(node)
        if not isinstance(handler_arg, ast.Name):
            # Not a reference to a locally-defined function this classifier can resolve (e.g. a
            # lambda, an imported handler, `signal.SIG_IGN`) -- absence of a recognized-safe
            # shape is not evidence of safety, but it is also not this rule's job to guess at an
            # unresolvable shape; only an actively-recognized-and-unsafe handler fires here (see
            # module docstring / design doc Failure strategy).
            continue
        handler_def = _find_function_def(tree, handler_arg.id)
        if handler_def is None:
            continue
        unsafe_stmt = next((s for s in handler_def.body if not _is_safe_signal_handler_stmt(s)), None)
        if unsafe_stmt is None:
            continue
        violations.append(
            Violation(
                file=path,
                line=getattr(unsafe_stmt, "lineno", node.lineno),
                rule=RULE_UNSAFE_SIGNAL_HANDLER,
                message=(
                    f"signal handler `{handler_arg.id}` (registered at line {node.lineno}) does "
                    "more than assign/branch/return/raise/sys.exit/os._exit -- not "
                    "async-signal-safe"
                ),
            )
        )
    return violations


def _matches_effect_call(call: ast.Call, name: str | None) -> bool:
    if name and name.startswith(_EFFECT_NAME_PREFIXES):
        return True
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr == "write":
        return True
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        if func.value.id == "subprocess" and func.attr == "run":
            return True
        if func.value.id == "os" and func.attr == "replace":
            return True
    return False


def _matches_check_call(call: ast.Call, name: str | None) -> bool:
    if name and (name.startswith(_CHECK_NAME_PREFIXES) or "check" in name.lower()):
        return True
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr == "get":
        return True
    return False


def _calls_within_function_scope(func: ast.AST) -> list[ast.Call]:
    """Every `Call` node directly inside `func`'s own body -- not descending into a nested
    function/lambda's own separate scope, so "within one function" (design doc, rule
    `idempotency-check-after-effect`) means what it says."""
    calls: list[ast.Call] = []
    stack = list(ast.iter_child_nodes(func))
    while stack:
        node = stack.pop()
        if isinstance(node, ast.Call):
            calls.append(node)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        stack.extend(ast.iter_child_nodes(node))
    return calls


def _check_idempotency_check_after_effect(tree: ast.AST, path: str, changed: set[int]) -> list[Violation]:
    violations: list[Violation] = []
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        calls = _calls_within_function_scope(func)
        effect_calls = [c for c in calls if _matches_effect_call(c, _call_name(c))]
        check_calls = [c for c in calls if _matches_check_call(c, _call_name(c))]
        for effect_call in effect_calls:
            for check_call in check_calls:
                if effect_call is check_call:
                    continue
                if effect_call.lineno >= check_call.lineno:
                    continue
                if effect_call.lineno not in changed and check_call.lineno not in changed:
                    continue
                violations.append(
                    Violation(
                        file=path,
                        line=effect_call.lineno,
                        rule=RULE_IDEMPOTENCY_CHECK_AFTER_EFFECT,
                        message=(
                            f"`{_call_name(effect_call)}(...)` at line {effect_call.lineno} runs "
                            f"before `{_call_name(check_call)}(...)` at line {check_call.lineno} "
                            f"in `{func.name}` -- the 'mark done' effect appears before the 'is "
                            "it already done' check in source order"
                        ),
                    )
                )
    return violations


def check(files: dict[str, str], changed_lines: dict[str, set[int]]) -> list[Violation]:
    """Run all four rules over every `.py` entry in `files`, using `changed_lines` to scope each
    rule to added/modified lines only. Returns every violation found (never short-circuits on
    the first one) -- see the design doc's state machine table, `checking_patterns`.

    `files` maps changed-file path -> full file content string; non-`.py` paths are skipped, not
    flagged (design doc, APIs table). `changed_lines` maps the same paths -> the set of line
    numbers the diff actually added/modified.
    """
    violations: list[Violation] = []
    for path, source in files.items():
        if not path.endswith(".py"):
            continue
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError as exc:
            violations.append(
                Violation(
                    file=path,
                    line=exc.lineno or 1,
                    rule=RULE_UNPARSEABLE,
                    message=f"could not parse as Python: {exc}",
                )
            )
            continue

        changed = changed_lines.get(path, set())
        parents = _build_parents(tree)
        violations.extend(_check_lock_without_tryfinally(tree, path, changed, parents))
        violations.extend(_check_bare_except_added(tree, path, changed))
        violations.extend(_check_unsafe_signal_handler(tree, path, changed))
        violations.extend(_check_idempotency_check_after_effect(tree, path, changed))
    return violations
