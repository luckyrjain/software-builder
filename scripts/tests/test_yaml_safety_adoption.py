"""Every non-test YAML read goes through the hardened loader, or is allowlisted with a reason.

scripts/yaml_safety.py is the deep module for parsing YAML: it rejects duplicate mapping keys
(plain safe_load silently last-key-wins) and caps document size and nesting. That protection used
to be applied to this repository's own code-reviewed registry files and skipped for the
target-workspace files nobody here wrote -- the trust gradient inverted. This test keeps the
default from drifting back: a new bare `yaml.safe_load(` in production code has to be a deliberate
entry below, not an oversight.
"""

from __future__ import annotations

import re
from pathlib import Path

from scripts.git_paths import tracked_relative_paths

ROOT = Path(__file__).resolve().parents[2]

_SAFE_LOAD_CALL = re.compile(r"\byaml\.safe_load\s*\(")

# Repo-relative path -> why a bare safe_load is correct there.
ALLOWED: dict[str, str] = {
    "scripts/yaml_safety.py": "the hardened loader itself",
    "skills/migration-program-manager/scripts/aggregate_migration_status.py": (
        "fallback when neither a vendored nor a repository yaml_safety is present -- the same "
        "bare-environment tolerance this script already has for a missing PyYAML"
    ),
    "skills/domain-comprehension/scripts/validate_manifest_yaml.py": "same bare-environment fallback",
    "skills/k8s-overprovisioning-datadog/scripts/validate_decision_graph.py": "same bare-environment fallback",
    "skills/incident-rca/scripts/validate_causal_graph.py": "same bare-environment fallback",
    "scripts/registry/generate_yaml_safety_bootstrap.py": (
        "the four skill scripts' own bare-environment fallback call appears verbatim inside this "
        "generator's _BOOTSTRAP_BODY template string (projected into them by `make generate`) -- "
        "text to be generated, not a bare safe_load this file itself executes"
    ),
}

def _production_python_files() -> list[Path]:
    """Tracked .py files only, so a local worktree or scratch directory never masquerades as production code.

    An untracked directory under the repo root -- e.g. a `.claude/worktrees/<name>` checkout of an
    older branch, which this repository's own worktree workflow creates -- previously showed up here
    via a raw filesystem walk and could fail this check on code nobody here wrote and nothing here
    reviews. Git's tracked-file list is the same "code-reviewed registry" boundary the module
    docstring above describes.
    """
    tracked, error = tracked_relative_paths(ROOT)
    if error:
        raise RuntimeError(f"yaml-safety adoption check requires a Git worktree: {error}")
    files: list[Path] = []
    for rel in tracked:
        if not rel.endswith(".py"):
            continue
        path = Path(rel)
        if "tests" in path.parts or path.name.startswith("test_"):
            continue
        files.append(ROOT / rel)
    return sorted(files)


def test_no_new_bare_yaml_safe_load_outside_the_allowlist() -> None:
    offenders = []
    for path in _production_python_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel in ALLOWED:
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        # Only real calls, not the several docstrings/comments that explain safe_load's behavior.
        source = re.sub(r'"""(?:.|\n)*?"""', "", source)
        source = "\n".join(line.split("#", 1)[0] for line in source.splitlines())
        if _SAFE_LOAD_CALL.search(source):
            offenders.append(rel)
    assert offenders == [], (
        "use scripts/yaml_safety.load_unique_yaml_file, or add the file to this test's ALLOWED "
        f"map with a reason: {offenders}"
    )


def test_allowlist_entries_still_exist_and_carry_a_reason() -> None:
    for rel, reason in ALLOWED.items():
        assert (ROOT / rel).is_file(), f"stale allowlist entry: {rel}"
        assert reason.strip(), f"{rel} needs a reason"
