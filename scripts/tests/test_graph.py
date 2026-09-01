"""Tests for scripts/registry/graph.py's detect_cycles."""

from __future__ import annotations

from scripts.registry.graph import detect_cycles


def test_detect_cycles_acyclic_graph_reports_no_errors() -> None:
    skills = {
        "a": ["b", "c"],
        "b": ["d"],
        "c": ["d"],
        "d": [],
    }
    assert detect_cycles(skills, "test") == []


def test_detect_cycles_two_node_cycle() -> None:
    skills = {
        "a": ["b"],
        "b": ["a"],
    }
    errors = detect_cycles(skills, "test")
    assert len(errors) == 1
    assert "cycle detected" in errors[0]
    assert "a -> b -> a" in errors[0]


def test_detect_cycles_self_cycle() -> None:
    skills = {
        "a": ["a"],
    }
    errors = detect_cycles(skills, "test")
    assert len(errors) == 1
    assert "cycle detected" in errors[0]
    assert "a -> a" in errors[0]


def test_detect_cycles_deep_cycle_several_levels_down() -> None:
    # a -> b -> c -> d -> b forms a cycle buried three levels below the root,
    # exercising the visiting/visited distinction rather than a trivial
    # "any repeated node" check: b is revisited while still "visiting"
    # (on the current DFS stack), not merely already "visited" from an
    # earlier, finished branch.
    skills = {
        "a": ["b"],
        "b": ["c"],
        "c": ["d"],
        "d": ["b"],
    }
    errors = detect_cycles(skills, "test")
    assert len(errors) == 1
    assert "cycle detected" in errors[0]
    assert "b -> c -> d -> b" in errors[0]


def test_detect_cycles_revisiting_a_finished_node_is_not_a_false_positive() -> None:
    # d is reached via two separate acyclic paths (a->b->d and a->c->d). Once
    # d finishes DFS it moves from "visiting" to "visited", so the second
    # visit must be treated as a benign shared dependency, not a cycle.
    skills = {
        "a": ["b", "c"],
        "b": ["d"],
        "c": ["d"],
        "d": [],
    }
    assert detect_cycles(skills, "test") == []


def test_detect_cycles_includes_label_in_message() -> None:
    skills = {
        "a": ["a"],
    }
    errors = detect_cycles(skills, "my-label")
    assert len(errors) == 1
    assert "my-label" in errors[0]
