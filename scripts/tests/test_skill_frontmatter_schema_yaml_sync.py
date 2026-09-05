"""scripts/registry/skill_frontmatter.schema.yaml must match its Python source of truth.

skill_frontmatter_schema.py's ALLOWED_FRONTMATTER_KEYS (enforced by
validate_skill_frontmatter_fields, wired into crosscheck.py's registry validation) and
skill_frontmatter.schema.yaml's allowed_keys: declare the same fact -- which SKILL.md
frontmatter keys are legal. Nothing in this repo loads the YAML file: it exists as a
machine-readable schema doc for tooling outside this repo (its own header comment says
so), not as an input to any validator here. That means the two lists can drift apart
with nothing to catch it. This test is that catch.
"""

from __future__ import annotations

from pathlib import Path

from scripts.registry.skill_frontmatter_schema import ALLOWED_FRONTMATTER_KEYS
from scripts.yaml_safety import load_unique_yaml_file

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_YAML_PATH = ROOT / "scripts" / "registry" / "skill_frontmatter.schema.yaml"

# agent_skills.py's _validate_name/_validate_description are what actually enforce these
# two keys are present -- the YAML's required_keys: is a restatement, checked here too.
REQUIRED_FRONTMATTER_KEYS = frozenset({"name", "description"})


def test_allowed_keys_match_the_python_frozenset() -> None:
    schema = load_unique_yaml_file(SCHEMA_YAML_PATH)
    assert set(schema["allowed_keys"]) == set(ALLOWED_FRONTMATTER_KEYS)


def test_required_keys_match_what_agent_skills_py_enforces() -> None:
    schema = load_unique_yaml_file(SCHEMA_YAML_PATH)
    assert set(schema["required_keys"]) == REQUIRED_FRONTMATTER_KEYS
