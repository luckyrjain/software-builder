"""One canonical copy of the yaml-safety bare-environment import shim, projected into every
packaged skill script that parses target-workspace YAML with the hardened loader.

Each of these scripts parses YAML written by the *target workspace* rather than by this
repository, so it wants `scripts/yaml_safety.py`'s duplicate-key rejection and size/nesting caps
-- but it must also keep working in a bare environment where neither a vendored nor a repository
copy of that module is importable (falling back to plain `yaml.safe_load`, tolerated the same way
each of these scripts already tolerates a missing PyYAML). That resolution -- prefer a copy
vendored beside the script, else the repository's own `scripts/yaml_safety.py` from a source
checkout, else `None` -- had been hand-copied into four validator scripts across four skills,
byte-for-byte identical: exactly the copy-drift risk `generate_shared_runtime_bootstrap.py`
already removes for the sibling shared-runtime-loader bootstrap.

Each target file keeps its own `try: import yaml` fallback and `_parse_yaml_file` helper
immediately below the generated block (those differ script to script) -- only the import-shim
itself, identical everywhere, is generated.
"""

from __future__ import annotations

from pathlib import Path

from scripts.registry.generate_docs import update_marker_block
from scripts.registry.models import Registry
from scripts.registry.paths import skill_dir

BOOTSTRAP_START = (
    "# GENERATED yaml-safety-bootstrap:start -- do not edit; run `make generate`. "
    "See scripts/registry/generate_yaml_safety_bootstrap.py"
)
BOOTSTRAP_END = "# GENERATED yaml-safety-bootstrap:end"

# (skill_id, path relative to that skill's own directory), resolved through skill_dir() -- the
# registry's `path:` field -- rather than assumed to be `root / skill_id`, so this stays correct
# once a skill moves. Order is alphabetical by (skill_id, path); it has no effect on output.
TARGET_FILES: tuple[tuple[str, str], ...] = (
    ("domain-comprehension", "scripts/validate_manifest_yaml.py"),
    ("incident-rca", "scripts/validate_causal_graph.py"),
    ("k8s-overprovisioning-datadog", "scripts/validate_decision_graph.py"),
    ("migration-program-manager", "scripts/aggregate_migration_status.py"),
)

_BOOTSTRAP_BODY = '''_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
# A source checkout resolves this repository's own scripts/yaml_safety.py; an installed package
# -- proved by its manifest -- may only ever load the copy vendored beside this script, never a
# path in the shared skills root that another tool could have written.
if not (_SCRIPT_DIR.parent / ".software-builder-manifest.json").is_file():
    _REPO_ROOT = _SCRIPT_DIR.parents[2]
    if (_REPO_ROOT / "skills.yaml").is_file() and str(_REPO_ROOT) not in sys.path:
        sys.path.append(str(_REPO_ROOT))

try:
    # This script parses YAML written by the target workspace rather than by this repository, so
    # it wants the shared loader's duplicate-key rejection and size/nesting caps: a duplicate key
    # in a workspace file silently last-key-wins under plain safe_load.
    from yaml_safety import load_unique_yaml_file
except ImportError:
    try:
        from scripts.yaml_safety import load_unique_yaml_file
    except ImportError:  # pragma: no cover - bare environment; falls back to plain safe_load
        load_unique_yaml_file = None  # type: ignore[assignment]'''


def render_yaml_safety_bootstrap_block() -> str:
    """The content `update_marker_block` splices between BOOTSTRAP_START and BOOTSTRAP_END --
    markers are added by `update_marker_block` itself, not included here."""
    return f"\n{_BOOTSTRAP_BODY}\n"


def generate_yaml_safety_bootstrap(root: Path, registry: Registry) -> dict[Path, str]:
    outputs: dict[Path, str] = {}
    for skill_id, rel in TARGET_FILES:
        path = skill_dir(root, registry, skill_id) / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        outputs[path] = update_marker_block(
            text, BOOTSTRAP_START, BOOTSTRAP_END, render_yaml_safety_bootstrap_block()
        )
    return outputs
