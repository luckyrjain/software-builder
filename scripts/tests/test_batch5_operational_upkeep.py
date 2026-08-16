from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.operational_upkeep import (
    _collect_capability_names,
    _deprecation_candidates,
    _matches,
    _nested_mappings,
    _source_key_exists,
    _tracked_relative_files,
    _validate_deprecation_mapping,
    _yaml_mapping,
    build_health_report,
    classify_diff,
    classify_file_role,
    codeowners_for,
    load_policy,
    render_health_markdown,
    validate_diff_risk,
    validate_policy,
)
from scripts.registry.install_targets_sync import _read_makefile_graph
from scripts.yaml_safety import YAML_SAFETY_ERRORS


ROOT = Path(__file__).resolve().parents[2]


def _phony_targets_from_text(text: str) -> set[str]:
    targets: set[str] = set()
    for line in text.splitlines():
        if line.startswith(".PHONY:"):
            targets.update(line.removeprefix(".PHONY:").split())
    return targets


def _phony_targets(makefile: Path) -> set[str]:
    return _phony_targets_from_text(makefile.read_text(encoding="utf-8"))


def test_lint_prd_architect_is_declared_phony() -> None:
    assert "lint-prd-architect" in _phony_targets(ROOT / "Makefile")


def test_operational_upkeep_is_wired_into_make_lint() -> None:
    graph = _read_makefile_graph(ROOT)
    assert "validate-operational-upkeep" in _phony_targets_from_text(graph)
    lint_rule = next(
        line for line in graph.splitlines() if line.startswith("lint: ") or line.startswith("lint:\t")
    )
    assert "validate-operational-upkeep" in lint_rule.split()


def test_install_target_scan_follows_literal_make_includes(tmp_path: Path) -> None:
    (tmp_path / "make").mkdir()
    (tmp_path / "Makefile").write_text("include make/core.mk\n", encoding="utf-8")
    (tmp_path / "make" / "core.mk").write_text(
        "install-example:\n\tbash scripts/install.sh example\n",
        encoding="utf-8",
    )
    text = _read_makefile_graph(tmp_path)
    assert "bash scripts/install.sh example" in text


def test_install_target_scan_ignores_dynamic_and_escaping_includes(tmp_path: Path) -> None:
    (tmp_path / "Makefile").write_text(
        "include $(DYNAMIC)\ninclude ../outside.mk\n",
        encoding="utf-8",
    )
    (tmp_path.parent / "outside.mk").write_text("should-not-load\n", encoding="utf-8")
    assert "should-not-load" not in _read_makefile_graph(tmp_path)


def test_install_target_scan_follows_multi_file_include_lines(tmp_path: Path) -> None:
    (tmp_path / "make").mkdir()
    (tmp_path / "Makefile").write_text(
        "include make/core.mk make/extra.mk\n",
        encoding="utf-8",
    )
    (tmp_path / "make" / "core.mk").write_text(
        "install-example:\n\tbash scripts/install.sh example\n",
        encoding="utf-8",
    )
    (tmp_path / "make" / "extra.mk").write_text(
        "install-second:\n\tbash scripts/install.sh second\n",
        encoding="utf-8",
    )
    text = _read_makefile_graph(tmp_path)
    assert "bash scripts/install.sh example" in text
    assert "bash scripts/install.sh second" in text


def test_operational_policy_validates_repository() -> None:
    assert validate_policy(ROOT) == []


def test_file_roles_separate_runtime_reference_and_maintainer_surfaces() -> None:
    policy = load_policy(ROOT / "scripts" / "operational_upkeep.yaml")
    assert classify_file_role("pr-review/SKILL.md", policy) == "runtime"
    assert classify_file_role("pr-review/workflow/inputs.md", policy) == "runtime"
    assert classify_file_role("pr-review/reference/smoke-test.md", policy) == "reference"
    assert classify_file_role("pr-review/README.md", policy) == "reference"
    assert classify_file_role("scripts/registry/eval_contracts.yaml", policy) == "maintainer"
    assert classify_file_role("scripts/README.md", policy) == "maintainer"
    assert classify_file_role("make/README.md", policy) == "maintainer"
    assert classify_file_role("docs/superpowers/plans/README.md", policy) == "maintainer"


def test_directory_glob_pattern_requires_path_separator_boundary() -> None:
    assert _matches("scripts/foo.py", "scripts/**") is True
    assert _matches("scripts-legacy/foo.py", "scripts/**") is False
    assert _matches("scripts", "scripts/**") is True


def test_bare_pattern_does_not_match_as_unanchored_substring() -> None:
    assert _matches("CODEOWNERS", "CODEOWNERS") is True
    assert _matches("docs/CODEOWNERS-policy.md", "CODEOWNERS") is False
    assert _matches("Makefile", "Makefile") is True
    assert _matches("scripts/legacy-Makefile-notes.md", "Makefile") is False


def test_leading_slash_pattern_requires_path_segment_boundary() -> None:
    assert _matches("pr-review/tests/foo.py", "/tests/") is True
    assert _matches("scripts/tests/foo.py", "/tests/") is True
    assert _matches("tests/root_level.py", "/tests/") is True
    assert _matches("contests/README.md", "/tests/") is False
    assert _matches("protests/notes.md", "/tests/") is False


def test_collect_capability_names_ignores_prose_and_skill_self_references() -> None:
    payload = {
        "capabilities": {
            "required": ["datadog.query_metrics"],
            "optional": [{"name": "squad-map.invoke", "enables": "full mapping table"}],
        },
        "degraded_modes": {
            "slack.post.message": "WEEKLY_SQUAD_DIGEST.md is still written; not delivered via Slack",
            "gitlab.create_merge_request_thread": "fall back to summary-only posting per auto-post-policy.md",
        },
    }
    names = _collect_capability_names(payload)
    assert names == {"datadog.query_metrics"}


def test_editorial_docs_pattern_matches_nested_paths() -> None:
    policy = load_policy(ROOT / "scripts" / "operational_upkeep.yaml")
    risk, matched = classify_diff(["docs/adr/0002-example.md"], policy)
    assert risk == "editorial"
    assert matched == ["editorial"]


def test_markdown_source_key_requires_an_actual_heading(tmp_path: Path) -> None:
    path = tmp_path / "prompt-injection.md"
    path.write_text(
        "# Prompt injection\n\n## Rule\n\nContent.\n",
        encoding="utf-8",
    )
    assert _source_key_exists(path, "Rule") is True

    # Renaming the heading must fail the check even though the word still
    # appears elsewhere in prose -- a bare substring search would stay True.
    path.write_text(
        "# Prompt injection\n\n## Guardrail Statement\n\n"
        "This companion rule repeats the rule from elsewhere.\n",
        encoding="utf-8",
    )
    assert _source_key_exists(path, "Rule") is False


def test_yaml_mapping_fails_closed_on_duplicate_keys(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.yaml"
    path.write_text("status: active\nstatus: deprecated\n", encoding="utf-8")
    with pytest.raises(YAML_SAFETY_ERRORS):
        _yaml_mapping(path)


def test_all_shared_framework_docs_are_classified() -> None:
    policy = load_policy(ROOT / "scripts" / "operational_upkeep.yaml")
    shared_dir = ROOT / "docs" / "skill-framework" / "shared"
    for path in sorted(shared_dir.glob("*.md")):
        rel = path.relative_to(ROOT).as_posix()
        assert classify_file_role(rel, policy) is not None, f"{rel} is not classified by any file role"
    # The explicit core runtime contracts must still win over the broad reference default.
    assert classify_file_role("docs/skill-framework/shared/runtime-contract.md", policy) == "runtime"
    assert classify_file_role("docs/skill-framework/shared/skill-routing.md", policy) == "runtime"
    assert classify_file_role("docs/skill-framework/shared/prompt-injection.md", policy) == "runtime"
    assert classify_file_role("docs/skill-framework/shared/safe-output.md", policy) == "runtime"
    assert classify_file_role("docs/skill-framework/shared/cross-skill-escalation.md", policy) == "reference"


def test_contract_owner_resolution_uses_matching_codeowners_rule() -> None:
    codeowners = (ROOT / "CODEOWNERS").read_text(encoding="utf-8")
    assert "@luckyrjain" in codeowners_for("scripts/registry/eval_contracts.yaml", codeowners)
    assert "@luckyrjain" in codeowners_for("docs/skill-framework/shared/safe-output.md", codeowners)
    assert "@luckyrjain" in codeowners_for("make/core.mk", codeowners)


def test_deprecated_contract_fails_closed_when_lifecycle_metadata_is_missing() -> None:
    required = {"deprecated_since", "replacement", "remove_after", "migration_note", "aliases"}
    errors = _validate_deprecation_mapping(
        {"status": "deprecated", "deprecation": {"replacement": "route.new"}},
        "fixture.yaml",
        required,
    )
    assert len(errors) == 1
    assert "deprecated_since" in errors[0]
    assert "remove_after" in errors[0]
    assert "migration_note" in errors[0]
    assert "aliases" in errors[0]


def test_aliases_shape_check_honors_the_required_set() -> None:
    # "aliases" required (the shipped policy's shape): a non-list value fails.
    required_with_aliases = {"deprecated_since", "replacement", "remove_after", "migration_note", "aliases"}
    errors = _validate_deprecation_mapping(
        {
            "status": "deprecated",
            "deprecation": {
                "deprecated_since": "2026-01-01",
                "replacement": "route.new",
                "remove_after": "2026-04-01",
                "migration_note": "migrate",
                "aliases": "not-a-list",
            },
        },
        "fixture.yaml",
        required_with_aliases,
    )
    assert errors == ["error: fixture.yaml: deprecation aliases must be a list"]

    # "aliases" not required: an item that omits it entirely must not fail on
    # the aliases-shape check, since that check is meant to be parameterized
    # by `required`, not hardcoded.
    required_without_aliases = {"deprecated_since", "replacement", "remove_after", "migration_note"}
    errors = _validate_deprecation_mapping(
        {
            "status": "deprecated",
            "deprecation": {
                "deprecated_since": "2026-01-01",
                "replacement": "route.new",
                "remove_after": "2026-04-01",
                "migration_note": "migrate",
            },
        },
        "fixture.yaml",
        required_without_aliases,
    )
    assert errors == []


def test_nested_artifact_deprecation_is_reachable_by_validator() -> None:
    nested = {
        "artifact_schemas": {
            "legacy_report": {
                "status": "deprecated",
                "deprecation": {"replacement": "report.v2"},
            }
        }
    }
    mappings = list(_nested_mappings(nested, "composition_contracts.yaml"))
    labels = {label for label, _ in mappings}
    assert "composition_contracts.yaml.artifact_schemas.legacy_report" in labels
    required = {"deprecated_since", "replacement", "remove_after", "migration_note", "aliases"}
    errors = [
        error
        for label, mapping in mappings
        for error in _validate_deprecation_mapping(mapping, label, required)
    ]
    assert any("legacy_report" in error and "deprecated_since" in error for error in errors)


def test_deprecation_discovery_includes_yaml_and_yml_registry_files(tmp_path: Path) -> None:
    registry = tmp_path / "scripts" / "registry"
    registry.mkdir(parents=True)
    (registry / "one.yaml").write_text("status: active\n", encoding="utf-8")
    (registry / "two.yml").write_text("status: deprecated\n", encoding="utf-8")

    labels = {label for label, _ in _deprecation_candidates(tmp_path, [])}
    assert "scripts/registry/one.yaml" in labels
    assert "scripts/registry/two.yml" in labels


def test_health_inputs_ignore_untracked_worktree_files(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("tracked\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    (tmp_path / "untracked.txt").write_text("local-only\n", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "noise.pyc").write_bytes(b"noise")

    assert _tracked_relative_files(tmp_path) == [Path("tracked.txt")]


def test_health_report_is_deterministic_with_complete_provenance() -> None:
    first = build_health_report(ROOT, revision="deadbeef")
    second = build_health_report(ROOT, revision="deadbeef")
    assert first == second
    provenance = first["provenance"]
    assert provenance["repository_revision"] == "deadbeef"
    assert provenance["registry_schema_version"] == 1
    assert provenance["prompt_bundle_version"] == "1"
    assert provenance["evaluator_version"] == "1"
    assert provenance["operational_policy_version"] == "1.4"
    assert provenance["generator_version"] == "1.3"

    health = first["health"]
    assert health["skills"] >= 23
    assert health["stable_routes"] >= 6
    assert health["route_token_budget_coverage"] == health["stable_routes"]
    assert health["stable_stop_conditions"] >= 5
    assert health["stable_report_fields"] >= 6
    assert health["contract_owners"] >= 7
    assert 0 < health["external_dependency_count"] < 15
    assert all(" " not in family for family in health["external_dependency_families"])
    assert not any(family.endswith(".invoke") for family in health["external_dependency_families"])
    assert health["orphan_runtime_modules"] == []

    markdown = render_health_markdown(first)
    assert "Repository revision: `deadbeef`" in markdown
    assert "Prompt bundle: `1`" in markdown
    assert "Evaluator: `1`" in markdown
    assert "Route token-budget coverage:" in markdown
    assert "Orphan runtime modules: **0**" in markdown


def test_prompt_diff_risk_uses_highest_matching_class() -> None:
    policy = load_policy(ROOT / "scripts" / "operational_upkeep.yaml")
    risk, matched = classify_diff(
        [
            "README.md",
            "pr-review/workflow/phase-5.md",
            "scripts/registry/capability_catalog.yaml",
            "docs/skill-framework/shared/skill-routing.md",
        ],
        policy,
    )
    assert risk == "routing"
    assert matched == ["editorial", "behavioral", "authority-capability", "routing"]


def test_upkeep_enforcement_paths_are_self_protected() -> None:
    policy = load_policy(ROOT / "scripts" / "operational_upkeep.yaml")
    for path in (
        "scripts/operational_upkeep.py",
        "scripts/deprecation_lifecycle.py",
        "scripts/deprecation_diff_guard.py",
        "scripts/eval_tier_health.py",
        "scripts/registry/skill_frontmatter_schema.py",
        ".github/workflows/lint.yml",
    ):
        risk, errors = validate_diff_risk([path], policy)
        assert risk == "schema"
        assert errors and "requires changed eval/test evidence" in errors[0]


def test_high_risk_prompt_diff_requires_test_or_eval_evidence() -> None:
    policy = load_policy(ROOT / "scripts" / "operational_upkeep.yaml")
    risk, errors = validate_diff_risk(
        ["docs/skill-framework/shared/skill-routing.md"],
        policy,
    )
    assert risk == "routing"
    assert errors and "requires changed eval/test evidence" in errors[0]

    risk, errors = validate_diff_risk(
        [
            "docs/skill-framework/shared/skill-routing.md",
            "scripts/tests/test_batch5_operational_upkeep.py",
        ],
        policy,
    )
    assert risk == "routing"
    assert errors == []


def test_per_skill_tests_directory_satisfies_high_risk_evidence_gate() -> None:
    policy = load_policy(ROOT / "scripts" / "operational_upkeep.yaml")
    risk, errors = validate_diff_risk(
        ["pr-review/SKILL.md", "pr-review/tests/test_diff_to_positions.py"],
        policy,
    )
    assert risk == "behavioral"
    assert errors == []

    risk, errors = validate_diff_risk(["pr-review/SKILL.md"], policy)
    assert risk == "behavioral"
    assert errors and "requires changed eval/test evidence" in errors[0]


def test_capability_collection_is_scoped_to_capabilities_subtree() -> None:
    skills = {
        "example": {
            "path": "example",
            "notes": "see api.version for details",
            "capabilities": {
                "required": ["datadog.query_metrics"],
                "optional": [{"name": "squad-map.invoke", "enables": "full mapping table"}],
                "any_of": [
                    {
                        "name": "GitLab read",
                        "required": ["gitlab.get_merge_request"],
                    }
                ],
            },
        }
    }
    names: set[str] = set()
    for entry in skills.values():
        names.update(_collect_capability_names(entry.get("capabilities")))
    assert names == {"datadog.query_metrics", "gitlab.get_merge_request"}
