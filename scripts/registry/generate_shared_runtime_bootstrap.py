"""One canonical copy of the shared-runtime bootstrap, projected into every entrypoint script
that needs it.

`docs/skill-framework/shared/shared_runtime_loader.py` owns the containment policy for loading a
module out of the vendored framework tree, but a script cannot `import` that loader to find it --
the loader is exactly the thing not yet locatable. Every entrypoint that calls
`load_shared_runtime()` therefore needs a small amount of bootstrap code first: `SKILL_ROOT` /
`_SCRIPT_DIR` / `_INSTALL_MANIFEST` and the `_shared_runtime_loader()` function that uses them to
find and `importlib`-load `shared_runtime_loader.py` itself, whether running from a packaged
install (loader vendored beside the script) or a source checkout (loader read from
docs/skill-framework/shared/). That bootstrap had been hand-copied into eight entrypoint scripts
across four skills, byte-for-byte identical apart from each script's own `_RUNTIME_DESCRIPTION`
(which the generated function only ever reads by name, never inlines) -- exactly the copy-drift
risk every other `make generate` output in this package removes.

Each target file keeps `_RUNTIME_DESCRIPTION` hand-authored immediately above the generated
block (it says what that script's own call to `load_shared_runtime()` is for), and keeps its own
`load_shared_runtime(...)` call site immediately below it (which shared-runtime module, what alias)
-- only the bootstrap itself, identical everywhere, is generated.
"""

from __future__ import annotations

from pathlib import Path

from scripts.registry.generate_docs import update_marker_block

BOOTSTRAP_START = (
    "# GENERATED shared-runtime-bootstrap:start -- do not edit; run `make generate`. "
    "See scripts/registry/generate_shared_runtime_bootstrap.py"
)
BOOTSTRAP_END = "# GENERATED shared-runtime-bootstrap:end"

# Relative to the repository root. Order is alphabetical by path; it has no effect on output.
TARGET_FILES: tuple[str, ...] = (
    "incident-rca/scripts/incident_rca_policy_guards.py",
    "incident-rca/scripts/kubesense_logs.py",
    "loop-task-implementer/scripts/validate_loop_lifecycle.py",
    "pr-review/scripts/diff-to-positions.py",
    "pr-review/scripts/github-comment-positions.py",
    "pr-review/scripts/pr_review_policy_guards.py",
    "pr-review/scripts/validate_review_coverage.py",
    "prd-architect/scripts/prd_safe_output.py",
)

_BOOTSTRAP_BODY = '''SKILL_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT_DIR = Path(__file__).resolve().parent
_INSTALL_MANIFEST = ".software-builder-manifest.json"


def _shared_runtime_loader() -> ModuleType:
    """Import shared_runtime_loader, which owns the containment policy for every module this
    script executes out of docs/skill-framework/shared/.

    Only locating the loader itself is handled here, and it needs no policy of its own: an
    installed package carries the loader beside this script (package_skill.py vendors it), so the
    lookup never leaves the package, and the install manifest is what proves a missing vendored
    copy is a packaging fault rather than an invitation to read a sibling path.
    """
    beside = _SCRIPT_DIR / "shared_runtime_loader.py"
    if beside.is_file():
        path = beside
    elif (SKILL_ROOT / _INSTALL_MANIFEST).is_file():
        raise RuntimeError(f"unable to load packaged {_RUNTIME_DESCRIPTION} loader: {beside}")
    else:
        path = SKILL_ROOT.parent / "docs/skill-framework/shared/shared_runtime_loader.py"
    if not path.is_file():
        raise RuntimeError(f"unable to load packaged {_RUNTIME_DESCRIPTION} loader: {path}")
    spec = importlib.util.spec_from_file_location("software_builder_shared_runtime_loader", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load packaged {_RUNTIME_DESCRIPTION} loader: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module'''


def render_shared_runtime_bootstrap_block() -> str:
    """The content `update_marker_block` splices between BOOTSTRAP_START and BOOTSTRAP_END --
    markers are added by `update_marker_block` itself, not included here."""
    return f"\n{_BOOTSTRAP_BODY}\n"


def generate_shared_runtime_bootstrap(root: Path) -> dict[Path, str]:
    outputs: dict[Path, str] = {}
    for rel in TARGET_FILES:
        path = root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        outputs[path] = update_marker_block(
            text, BOOTSTRAP_START, BOOTSTRAP_END, render_shared_runtime_bootstrap_block()
        )
    return outputs
