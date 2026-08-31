"""Parity test for the repo's two independent markdown-link regexes.

scripts/reference_utils.py's MARKDOWN_LINK_RE and scripts/registry/cross_skill_routing.py's
_MARKDOWN_LINK both parse "](target)"-shaped markdown link syntax, kept as two separate regexes
(one allows whitespace in the target, one doesn't) rather than one shared implementation -- see
their own module comments for why. A full-system review found the same paren-truncation bug
independently in both; this test runs a shared corpus of edge cases through both so a future fix
to one's target-matching behavior doesn't quietly go unmatched by the other.
"""
from __future__ import annotations

from scripts.reference_utils import MARKDOWN_LINK_RE
from scripts.registry.cross_skill_routing import _MARKDOWN_LINK

# (label, target) pairs every markdown-link regex in this repo must extract correctly.
_TARGET_CASES = [
    ("plain", "plain/path.md"),
    ("one nested paren", "https://en.wikipedia.org/wiki/Foo_(bar)"),
    ("relative with fragment", "../shared/foo.md#anchor"),
]


def test_both_markdown_link_regexes_capture_one_level_of_nested_parens() -> None:
    for label, target in _TARGET_CASES:
        text = f"[x]({target})"

        reference_utils_match = MARKDOWN_LINK_RE.search(text)
        cross_skill_routing_match = _MARKDOWN_LINK.search(text)

        assert reference_utils_match is not None, f"{label}: reference_utils regex found no match"
        assert cross_skill_routing_match is not None, f"{label}: cross_skill_routing regex found no match"
        assert reference_utils_match.group(1) == target, f"{label}: reference_utils captured {reference_utils_match.group(1)!r}"
        assert cross_skill_routing_match.group(2) == target, f"{label}: cross_skill_routing captured {cross_skill_routing_match.group(2)!r}"


def test_both_markdown_link_regexes_document_the_same_two_level_nesting_gap() -> None:
    # Neither regex matches a target with two or more levels of nested parens (documented,
    # accepted limitation in both modules) -- confirmed here so if one is ever upgraded to handle
    # it, this test fails as a reminder to upgrade the other too, rather than the two silently
    # diverging on what they support.
    text = "[x](foo_(a_(b)_c).md)"

    assert MARKDOWN_LINK_RE.search(text) is None
    assert _MARKDOWN_LINK.search(text) is None
