"""Every registered skill's `lint-<lint.target>` Make target must be declared .PHONY.

Unlike install-<skill>/install-claude-<skill> (generated into make/generated-roster.mk
from ALL_SKILLS, see generate_makefile_roster.py), the lint-<skill> .PHONY declarations
are hand-maintained -- spread across three separate `.PHONY:` lines in Makefile and
make/core.mk, kept in sync with the registry by convention only. A target that isn't
declared .PHONY still runs correctly today, but silently stops running its recipe (Make
treats it as up to date and does nothing) the moment a same-named file or directory ever
exists at the repo root -- an easy, non-obvious regression for a target name that
otherwise looks like ordinary text. This test is the enforcement the hand-maintained
list doesn't have: it fails loudly instead.

Each skill's canonical lint target name is skills.yaml's own `lint.target` field (not
assumed to be `lint-<skill-id>`) -- k8s-overprovisioning-datadog declares
`target: k8s-skill`, so its target is `lint-k8s-skill`, not
`lint-k8s-overprovisioning-datadog`.
"""

from __future__ import annotations

import re
from pathlib import Path

from scripts.registry.schema import parse_registry

ROOT = Path(__file__).resolve().parents[2]


def _declared_phony_targets() -> set[str]:
    targets: set[str] = set()
    for path in (ROOT / "Makefile", ROOT / "make" / "core.mk"):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"^\.PHONY:\s*(.+)$", text, re.MULTILINE):
            targets.update(match.group(1).split())
    return targets


def test_every_skill_lint_target_is_declared_phony() -> None:
    registry = parse_registry(ROOT / "skills.yaml")
    phony = _declared_phony_targets()

    missing = sorted(
        f"lint-{entry.lint.target}"
        for entry in registry.skills.values()
        if f"lint-{entry.lint.target}" not in phony
    )
    assert not missing, (
        f"{len(missing)} skill lint target(s) exist as Make recipes but are not declared "
        f".PHONY in Makefile or make/core.mk: {missing}. Add them to one of the "
        "existing .PHONY: lines."
    )
