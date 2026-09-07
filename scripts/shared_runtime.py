"""Load a module from `docs/skill-framework/shared/` for this repository's own top-level
`scripts/*.py` tools (not a packaged skill's scripts, which use the generated bootstrap in
`scripts/registry/generate_shared_runtime_bootstrap.py` instead -- those must also handle
running from an *installed* package, which these never do).

Three of these top-level tools (`change_impact.py`, `validate_metadata_footer.py`,
`validate_review_contracts.py`) used to each carry their own ~10-line `importlib.util`
block to `exec_module` a shared-tree module by path, all with the same "loaded by path
rather than imported: it lives under docs/ so it can be vendored verbatim into installed
skill packages" rationale. `docs/skill-framework/shared/shared_runtime_loader.py` already
owns the one containment policy for this (vendored-copy-wins, refuse to leave an installed
package) -- it just cannot itself be `import`ed, being the very thing not yet locatable, so
every caller needs a few lines of bootstrap first. This module is that bootstrap, done once.

A repo-root script is always running from a source checkout (it already does
`from scripts.registry import ...`, which only resolves there), so passing `ROOT` itself as
`shared_runtime_loader`'s `skill_root` argument takes its "vendored copy" branch directly:
`ROOT / "docs/skill-framework/shared" / f"{name}.py"` **is** the real file.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]

_LOADER_PATH = ROOT / "docs" / "skill-framework" / "shared" / "shared_runtime_loader.py"


def _shared_runtime_loader() -> ModuleType:
    spec = importlib.util.spec_from_file_location("software_builder_shared_runtime_loader", _LOADER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load shared_runtime_loader: {_LOADER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load(name: str, *, alias: str | None = None, description: str = "shared runtime") -> ModuleType:
    """Execute `docs/skill-framework/shared/{name}.py` and return it as a module."""
    return _shared_runtime_loader().load_shared_runtime(ROOT, name, alias=alias, description=description)
