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

ROOT = Path(__file__).resolve().parents[2]

_SAFE_LOAD_CALL = re.compile(r"\byaml\.safe_load\s*\(")

# Repo-relative path -> why a bare safe_load is correct there.
ALLOWED: dict[str, str] = {
    "scripts/yaml_safety.py": "the hardened loader itself",
    "migration-program-manager/scripts/aggregate_migration_status.py": (
        "fallback when neither a vendored nor a repository yaml_safety is present -- the same "
        "bare-environment tolerance this script already has for a missing PyYAML"
    ),
    "domain-comprehension/scripts/validate_manifest_yaml.py": "same bare-environment fallback",
    "k8s-overprovisioning-datadog/scripts/validate_decision_graph.py": "same bare-environment fallback",
    "incident-rca/scripts/validate_causal_graph.py": "same bare-environment fallback",
}

_SKIPPED_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "node_modules"}


def _production_python_files() -> list[Path]:
    files: list[Path] = []
    for path in sorted(ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT)
        if any(part in _SKIPPED_DIRS for part in rel.parts):
            continue
        if "tests" in rel.parts or path.name.startswith("test_"):
            continue
        files.append(path)
    return files


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
