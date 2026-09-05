"""The one place that names skills.yaml's location.

Five modules (manifest.py, capability_catalog.py, composition_runtime.py,
composition_contracts.py, canonical_manifest.py) each independently declared
`ROOT / "skills.yaml"` under a differently-named constant of their own
(CONTRACTS_PATH, SKILLS_PATH, CANONICAL_RUNTIME_PATH, CANONICAL_CONTRACTS_PATH,
CANONICAL_PATH) -- if the canonical manifest were ever renamed or relocated, every
one of those needed updating by hand, with no single symbol to change and no test
that would catch a missed one. manifest.py's and canonical_manifest.py's copies
turned out to be entirely unused (dead code, not even read within their own file)
and were deleted outright; the three still-live ones (used as each function's
default `root`-relative path) now import this instead of redeclaring it.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS_YAML_PATH = ROOT / "skills.yaml"
