"""Guard against reintroducing the shared `.pycache-lint` race.

`lint-suites` runs its member targets concurrently under `make -j` (see
.github/workflows/lint.yml). Each target that sets PYTHONPYCACHEPREFIX for its own
py_compile/pytest run cleans that directory up with `trap 'rm -rf "$cache"' EXIT`, so
two targets sharing the same literal path race: whichever finishes first deletes the
directory out from under the other's still-running compile/test step. This bit
`lint-pr-review-scripts` and `lint-loop-task-implementer-scripts`, which both used the
bare `.pycache-lint` path. Every target must use a path suffixed uniquely to itself.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE_PATH_RE = re.compile(r'cache="\$\(CURDIR\)/(\.pycache-lint[\w-]*)"')


def test_every_pycache_lint_path_in_core_mk_is_unique() -> None:
    text = (ROOT / "make" / "core.mk").read_text(encoding="utf-8")
    paths = CACHE_PATH_RE.findall(text)
    assert paths, "expected at least one .pycache-lint cache path in make/core.mk"
    duplicates = {path for path in paths if paths.count(path) > 1}
    assert not duplicates, (
        f"make/core.mk has {len(paths)} PYTHONPYCACHEPREFIX cache paths but reuses "
        f"{duplicates!r} across more than one target -- targets sharing a literal "
        "$(CURDIR)/.pycache-lint* path race under `make -j` (lint-suites runs them "
        "concurrently) since each one deletes it on exit. Give the reused path(s) a "
        "unique suffix."
    )
