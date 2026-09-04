#!/usr/bin/env python3
"""One containment policy for loading executable modules out of this shared tree.

Skill scripts under `<skill>/scripts/` execute Python that ships in this directory. Where that
directory *is* depends on how the skill is running: an installed package carries its own vendored
copy, while a source checkout has one copy at the repository root shared by every skill. Resolving
that used to be each skill's own business, and the two implementations had already diverged in the
security-relevant direction -- one refused to walk out of an installed package, the other would
happily `exec_module` a path in the shared skills root that any other installed skill, or the
user's own tooling, can create.

The policy, in one place:

* A vendored copy inside the skill package always wins.
* If there is no vendored copy but an install manifest proves this *is* an installed package, that
  is a packaging fault -- refuse, never look outside the package.
* Otherwise accept the parent directory only when it proves itself a software-builder checkout
  (`skills.yaml` and `scripts/package_skill.py` both present).
* Otherwise refuse.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

SHARED_RELATIVE = "docs/skill-framework/shared"
INSTALL_MANIFEST = ".software-builder-manifest.json"
SOURCE_CHECKOUT_MARKERS = ("skills.yaml", "scripts/package_skill.py")


def shared_runtime_path(skill_root: Path, module_name: str, *, description: str = "shared runtime") -> Path:
    """The one path `module_name` may be executed from for a skill rooted at `skill_root`.

    `module_name` is a bare module name (no extension, no separators) -- callers name a module in
    this tree, never an arbitrary path. `description` names the module in error messages the way
    the calling skill already describes it.
    """
    if "/" in module_name or "\\" in module_name or module_name in {"", ".", ".."}:
        raise ValueError(f"invalid shared runtime module name {module_name!r}")
    filename = f"{module_name}.py"

    vendored = skill_root / SHARED_RELATIVE / filename
    if vendored.is_file():
        return vendored
    if (skill_root / INSTALL_MANIFEST).is_file():
        raise RuntimeError(f"unable to load packaged {description}: {vendored}")

    repo_root = skill_root.parent
    source = repo_root / SHARED_RELATIVE / filename
    if all((repo_root / marker).is_file() for marker in SOURCE_CHECKOUT_MARKERS) and source.is_file():
        return source
    raise RuntimeError(
        f"unable to load packaged {description} or verified source-checkout runtime: {vendored}"
    )


def load_shared_runtime(
    skill_root: Path,
    module_name: str,
    *,
    alias: str | None = None,
    description: str = "shared runtime",
) -> ModuleType:
    """Execute `module_name` from the tree `skill_root` is allowed to load from."""
    path = shared_runtime_path(skill_root, module_name, description=description)
    spec = importlib.util.spec_from_file_location(alias or f"shared_{module_name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load packaged {description}: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
