"""Tests for release tagging and compatibility matrix generation."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _write_release_contract(root: Path, tag_template: str = "v{version}") -> None:
    (root / "scripts").mkdir(exist_ok=True)
    (root / "scripts" / "release_contract.yaml").write_text(
        "schema_version: 1\n"
        f"tag_template: {tag_template!r}\n"
        "artifact_name_templates:\n"
        '  - "software-builder-{version}.tar.gz"\n'
        "compatibility:\n"
        "  registry_schema_version: 1\n"
        "  host_contract_schema_version: 1\n"
        "provenance:\n"
        "  required_fields: [schema_version]\n",
        encoding="utf-8",
    )


def test_verify_release_tag_matches_version(tmp_path: Path) -> None:
    (tmp_path / "VERSION").write_text("1.4.0\n", encoding="utf-8")
    _write_release_contract(tmp_path)
    from scripts.verify_release_tag import main

    assert main(["v1.4.0", "--repo-root", str(tmp_path)]) == 0
    assert main(["v1.3.0", "--repo-root", str(tmp_path)]) == 1
    # The shape comes from the contract, not from the verifier: no prefix, wrong prefix,
    # and a trailing suffix are all rejected by string equality with the rendered template.
    assert main(["1.4.0", "--repo-root", str(tmp_path)]) == 1
    assert main(["release-1.4.0", "--repo-root", str(tmp_path)]) == 1
    assert main(["v1.4.0-rc1", "--repo-root", str(tmp_path)]) == 1


def test_verify_release_tag_follows_the_contract_template(tmp_path: Path, capsys) -> None:
    (tmp_path / "VERSION").write_text("1.4.0\n", encoding="utf-8")
    _write_release_contract(tmp_path, tag_template="release-{version}")
    from scripts.verify_release_tag import main

    assert main(["release-1.4.0", "--repo-root", str(tmp_path)]) == 0
    assert main(["v1.4.0", "--repo-root", str(tmp_path)]) == 1
    assert "maps it to 'release-1.4.0'" in capsys.readouterr().err


def test_verify_release_tag_fails_closed_without_a_contract(tmp_path: Path, capsys) -> None:
    (tmp_path / "VERSION").write_text("1.4.0\n", encoding="utf-8")
    from scripts.verify_release_tag import main

    assert main(["v1.4.0", "--repo-root", str(tmp_path)]) == 1
    assert "release_contract.yaml" in capsys.readouterr().err


def test_compatibility_matrix_lists_all_skills() -> None:
    from scripts.registry.generate_compatibility import render_compatibility_matrix
    from scripts.registry.schema import parse_registry

    text = render_compatibility_matrix(ROOT)
    registry = parse_registry(ROOT / "skills.yaml")
    assert "GENERATED from skills.yaml" in text
    for skill_id in registry.skills:
        assert f"| {skill_id} |" in text


def test_compatibility_matrix_distinguishes_all_required_from_any_of_paths() -> None:
    from scripts.registry.generate_compatibility import render_compatibility_matrix

    text = render_compatibility_matrix(ROOT)
    loop_task_row = next(line for line in text.splitlines() if "| loop-task-implementer |" in line)
    pr_review_row = next(line for line in text.splitlines() if "| pr-review |" in line)

    assert "host.repository.read_write, host.role.isolation, host.ci.status" in loop_task_row
    assert "host.repository.read_write OR host.role.isolation" not in loop_task_row
    assert "GitLab read:" in pr_review_row
    assert " OR GitHub read:" in pr_review_row


def test_compatibility_matrix_gates_kiro_cell_on_required_capability_family() -> None:
    """Per-skill-per-host join regression test.

    loop-task-implementer requires host.role.isolation (family:
    task_isolation) and host.ci.status/host.pull_request.write (family: scm),
    both of which host_contracts.yaml marks Kiro `degraded` on. The audited
    gap was that host_cell rendered the same blanket host-profile string for
    every skill regardless of what it actually required, hiding that. A
    skill with no host.* required capability (pr-review) must keep the
    blanket profile unchanged, proving the two cells are computed
    differently rather than both happening to say "degraded".
    """
    from scripts.registry.generate_compatibility import render_compatibility_matrix

    text = render_compatibility_matrix(ROOT)
    loop_task_row = next(line for line in text.splitlines() if "| loop-task-implementer |" in line)
    pr_review_row = next(line for line in text.splitlines() if "| pr-review |" in line)

    assert "manual \\(degraded\\)" in loop_task_row
    assert "manual \\(full/degraded\\)" in pr_review_row


def test_required_host_families_maps_and_fails_closed() -> None:
    from scripts.registry.generate_compatibility import _required_host_families

    assert _required_host_families(
        ["host.repository.read_write", "host.role.isolation", "host.ci.status", "host.pull_request.write"],
    ) == {"read_repo", "write_repo", "task_isolation", "scm"}
    assert _required_host_families(["gitlab.get_merge_request"]) == set()

    with pytest.raises(ValueError, match="no entry in HOST_CAPABILITY_FAMILIES"):
        _required_host_families(["host.does_not_exist"])


def test_worst_required_support_picks_lowest_level_per_host() -> None:
    from scripts.registry.generate_compatibility import _worst_required_support

    assert _worst_required_support(ROOT, "kiro", set()) is None
    assert _worst_required_support(ROOT, "kiro", {"read_repo"}) == "full"
    assert _worst_required_support(ROOT, "kiro", {"read_repo", "task_isolation"}) == "degraded"
    assert _worst_required_support(ROOT, "generic", {"task_isolation"}) == "unsupported"
