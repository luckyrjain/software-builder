"""Atomic file writes: write to a temp file in the destination's own directory, then
os.replace() it into place on success -- never a partial/truncated file at the real path.

Extracted from scripts/package_release.py's private _atomic_write, which had exactly this
implementation and docstring; scripts/registry/cli.py's _write_outputs wrote generated files
directly with Path.write_text, so a failure partway through a multi-file `make generate` run
(disk full, a killed process) could leave a truncated file at one of the generated paths.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path


@contextlib.contextmanager
def atomic_write(path: Path, *, mode: str = "wb"):
    """Open a temp file in path's own directory; replace path with it atomically
    on success, remove it and leave path untouched on any failure.

    Without this, a failure partway through writing (disk-full, a killed process, ...)
    would truncate/corrupt whatever file previously existed at `path` -- silently
    destroying valid prior output -- instead of failing without touching it.
    """
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    tmp_path = Path(tmp_name)
    success = False
    try:
        with os.fdopen(fd, mode, encoding=None if "b" in mode else "utf-8") as handle:
            yield handle
        os.replace(tmp_path, path)
        success = True
    finally:
        if not success:
            tmp_path.unlink(missing_ok=True)


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with atomic_write(path, mode="w") as handle:
        handle.write(content)
