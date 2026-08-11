"""Tests for installed-package reference validation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_references import github_style_slug, heading_slugs, validate_tree  # noqa: E402


def test_slug_preserves_hyphens_within_heading_text() -> None:
    # Regression: an earlier keep-set (alnum-or-space only) dropped the hyphen from
    # "Test-first", producing "1-testfirst-evidence" instead of GitHub's real
    # "1-test-first-evidence" for this exact heading in
    # docs/skill-framework/shared/test-creation-principles.md.
    assert github_style_slug("## 1. Test-first evidence") == "1-test-first-evidence"


def test_slug_preserves_trailing_hyphen_from_stripped_trailing_character() -> None:
    # Regression: strip()+split()+join() silently discards the internal space left
    # behind when a trailing non-ASCII character (e.g. an emoji) is removed by the
    # character filter, producing "5-slack-pr-review" instead of the real GitHub
    # anchor "5-slack-pr-review-" (trailing hyphen) already used by the verified
    # link in pr-review/examples.md for this exact heading in
    # docs/skill-framework/shared/post-action-templates.md.
    assert github_style_slug("## 5. Slack — PR review \U0001f534") == "5-slack-pr-review-"


def test_slug_preserves_non_ascii_letters() -> None:
    # Regression: an ASCII-only keep-set regex ([^a-z0-9 -]) strips accented Latin
    # letters that GitHub's real anchor algorithm preserves — e.g. "Café Menu" must
    # slugify to "café-menu", not "caf-menu". Verified this diverges from the prior
    # (differently buggy) isalnum()-based implementation, which did preserve them.
    assert github_style_slug("## Café Menu") == "café-menu"


def test_heading_slugs_ignores_headings_inside_fenced_code_blocks(tmp_path: Path) -> None:
    # Regression: heading_slugs() scanned every "#"-prefixed line without stripping fenced
    # code blocks first, unlike its sibling extract_markdown_links() (which does). A
    # "## Example Section" line inside a ```markdown example block isn't a real heading —
    # GitHub never renders it as a navigable anchor — but the unstripped scan treated it as
    # one, letting a link to a genuinely-missing "#example-section" anchor pass unnoticed.
    # Newly consequential now that --source-tree wires anchor checking into make lint.
    md_file = tmp_path / "doc.md"
    md_file.write_text(
        "# Actual Real Heading\n"
        "\n"
        "Some text.\n"
        "\n"
        "```markdown\n"
        "## Example Section\n"
        "This is inside a fenced code block and must not count as a real heading.\n"
        "```\n",
        encoding="utf-8",
    )
    assert heading_slugs(md_file) == {"actual-real-heading"}


def test_source_tree_exclude_skips_historical_doc_tree(tmp_path: Path) -> None:
    (tmp_path / "docs" / "superpowers").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "old-plan.md").write_text(
        "Broken: [missing](./missing.md)\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("Fine: no links here.\n", encoding="utf-8")

    errors_without_exclude = validate_tree(tmp_path, check_anchors=True)
    assert any("missing.md" in error for error in errors_without_exclude)

    errors_with_exclude = validate_tree(tmp_path, check_anchors=True, exclude=["docs/superpowers"])
    assert errors_with_exclude == []


def test_source_tree_exclude_handles_multiple_roots(tmp_path: Path) -> None:
    # Exercises the generic multi-root --exclude mechanism (an earlier approach passed one
    # --exclude per registered skill directory here, before that was reverted for dropping
    # coverage of files outside each skill's legacy lint globs — see CHANGELOG.md). The real
    # lint-framework invocation only passes --exclude docs/superpowers --exclude
    # docs/skill-framework today, but several simultaneous excludes (each skipping only its
    # own subtree) is still worth covering generically rather than only ever with one root.
    (tmp_path / "docs" / "superpowers").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "old-plan.md").write_text(
        "Broken: [missing](./missing.md)\n",
        encoding="utf-8",
    )
    (tmp_path / "some-skill").mkdir()
    (tmp_path / "some-skill" / "SKILL.md").write_text(
        "Broken: [missing](./missing.md)\n",
        encoding="utf-8",
    )
    (tmp_path / "another-skill").mkdir()
    (tmp_path / "another-skill" / "SKILL.md").write_text(
        "Broken: [missing](./missing.md)\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(
        "Still checked: [missing](./missing.md)\n",
        encoding="utf-8",
    )

    errors = validate_tree(
        tmp_path,
        check_anchors=True,
        exclude=["docs/superpowers", "some-skill", "another-skill"],
    )
    assert len(errors) == 1
    assert "README.md" in errors[0]


def test_installed_package_flags_missing_skill_local_link(tmp_path: Path) -> None:
    package = tmp_path / "skill"
    package.mkdir()
    (package / "SKILL.md").write_text(
        "Broken: [missing](reference/missing.md)\n",
        encoding="utf-8",
    )

    errors = validate_tree(package, check_anchors=False, installed_package=True)
    assert any("reference/missing.md" in error for error in errors)


def test_installed_package_ignores_optional_external_link(tmp_path: Path) -> None:
    package = tmp_path / "skill"
    framework = package / "docs" / "skill-framework" / "shared"
    framework.mkdir(parents=True)
    (framework / "routing.md").write_text(
        "Optional: [other-skill](../../pr-review/SETUP.md)\n",
        encoding="utf-8",
    )

    errors = validate_tree(package, check_anchors=False, installed_package=True)
    assert errors == []


def test_installed_package_flags_missing_framework_link(tmp_path: Path) -> None:
    package = tmp_path / "skill"
    package.mkdir()
    (package / "SKILL.md").write_text(
        "Broken: [routing](docs/skill-framework/shared/routing.md)\n",
        encoding="utf-8",
    )
    (package / "docs" / "skill-framework" / "shared").mkdir(parents=True)

    errors = validate_tree(package, check_anchors=False, installed_package=True)
    assert any("routing.md" in error for error in errors)


def test_strip_fenced_code_blocks_tracks_delimiter_length() -> None:
    from reference_utils import strip_fenced_code_blocks

    # A 4-backtick fence containing a legitimately nested 3-backtick fenced excerpt: the
    # inner ``` line must not be treated as closing the outer fence (a naive boolean toggle
    # would exit the outer fence there, leaking the tail content — including a fake link
    # target — as unfenced text).
    text = (
        "Before [real](./real.md).\n"
        "````text\n"
        "outer content\n"
        "```python\n"
        "inner content [fake](./fake.md)\n"
        "```\n"
        "outer tail [also-fake](./also-fake.md)\n"
        "````\n"
        "After [real2](./real2.md).\n"
    )
    stripped = strip_fenced_code_blocks(text)
    assert "[real]" in stripped
    assert "[real2]" in stripped
    assert "[fake]" not in stripped
    assert "[also-fake]" not in stripped


def test_strip_fenced_code_blocks_handles_indented_list_fence() -> None:
    from reference_utils import strip_fenced_code_blocks

    # A fence indented up to 3 spaces (nested inside a numbered-list step, the shape used
    # throughout this repo's workflow/*.md files) is still a real CommonMark fence — its
    # content must be stripped, not treated as ordinary indented prose.
    text = (
        "1. Step one:\n"
        "   ```bash\n"
        "   echo [fake](./fake.md)\n"
        "   ```\n"
        "   After the fence, still list prose.\n"
        "\n"
        "After [real](./real.md).\n"
    )
    stripped = strip_fenced_code_blocks(text)
    assert "[fake]" not in stripped
    assert "[real]" in stripped
    assert "still list prose" in stripped


def test_fence_open_ignores_line_with_backtick_in_info_string() -> None:
    from reference_utils import has_unclosed_fenced_code_block, strip_fenced_code_blocks

    # Regression: prose demonstrating the delimiter-length inline-code-span technique
    # (e.g. "``` becomes ````, …") starts with a 3-backtick run, but CommonMark requires a
    # backtick fence's info string to contain NO backticks — so this line is not a fence
    # opener at all. Treating it as one silently swallowed everything after it (including a
    # real link and a real heading) as code-block content until EOF.
    text = (
        "Escalate the run: `` ` `` becomes `` `` ``, ``` ``` ```, and so on.\n"
        "\n"
        "[real link](./real.md).\n"
        "\n"
        "# Real Heading\n"
    )
    assert has_unclosed_fenced_code_block(text) is False
    stripped = strip_fenced_code_blocks(text)
    assert "[real link]" in stripped
    assert "# Real Heading" in stripped


def test_has_unclosed_fenced_code_block_detects_stray_opener() -> None:
    from reference_utils import has_unclosed_fenced_code_block

    # A genuine, real fence opener with no closer before EOF must still be caught — the
    # info-string check above must not make this detection blind to actual stray markers.
    text = "# Real Heading\n\n- item\n```\n\n## Hidden Heading\n"
    assert has_unclosed_fenced_code_block(text) is True


def test_validate_markdown_file_flags_unclosed_fenced_code_block(tmp_path: Path) -> None:
    md_file = tmp_path / "doc.md"
    md_file.write_text(
        "# Real Heading\n\n- item\n```\n\n## Hidden Heading\n",
        encoding="utf-8",
    )
    errors = validate_tree(tmp_path, check_anchors=True)
    assert any("unclosed fenced code block" in error for error in errors)
