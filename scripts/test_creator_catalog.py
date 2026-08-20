"""Canonical catalog shared by test-creator packaging and parity checks."""

from __future__ import annotations

TEST_CREATOR_SKILLS = (
    "unit-test-creator",
    "integration-test-creator",
    "contract-test-creator",
    "e2e-test-creator",
    "api-test-creator",
)
TEST_CREATOR_SKILL_SET = frozenset(TEST_CREATOR_SKILLS)
