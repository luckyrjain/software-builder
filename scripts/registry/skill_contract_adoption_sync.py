"""Every skill must reference the shared result/authorization/completion contracts.

platform_contracts.yaml and runtime-contract.md define skill_result,
action_gates, and definition_of_done once, centrally. This validator makes
sure every registered skill's own SKILL.md actually points back to them,
instead of the contracts existing only as unreferenced scaffolding that no
individual skill is checked against.
"""
from __future__ import annotations

import re
from pathlib import Path

from scripts.registry.models import Registry

REQUIRED_CONTRACT_MARKERS = (
    "skill_result",
    "action_gates",
    # Requiring the umbrella term alone let a skill "adopt" definition_of_done
    # by mentioning the word without ever declaring its own four fields --
    # require each field name so the check reflects real per-skill content,
    # not a copy-pasted disclaimer.
    "required_artifacts",
    "required_checks",
    "blocked_conditions",
    "partial_result_behavior",
)
REQUIRED_CONTRACT_LINK = "runtime-contract.md"

_FRAMEWORK_SECTION_RE = re.compile(r"^## Framework\s*$", re.MULTILINE)
_NEXT_SECTION_RE = re.compile(r"^## ", re.MULTILINE)


def _framework_section(text: str) -> str | None:
    """Return the "## Framework" section's own text, or None if absent.

    Scoped deliberately: a bare substring search over the whole file would
    pass if the three marker words showed up anywhere at all -- an unrelated
    troubleshooting note or a "we don't use action_gates here" caveat would
    satisfy it without the skill actually declaring adoption.
    """
    start_match = _FRAMEWORK_SECTION_RE.search(text)
    if start_match is None:
        return None
    end_match = _NEXT_SECTION_RE.search(text, start_match.end())
    end = end_match.start() if end_match else len(text)
    return text[start_match.end() : end]


def validate_skill_contract_adoption(root: Path, registry: Registry) -> list[str]:
    errors: list[str] = []
    for skill_id, entry in sorted(registry.skills.items()):
        skill_md = root / entry.path / "SKILL.md"
        if not skill_md.is_file():
            continue
        section = _framework_section(skill_md.read_text(encoding="utf-8"))
        if section is None:
            errors.append(f"error: {skill_id}: SKILL.md has no '## Framework' section")
            continue
        missing = [marker for marker in REQUIRED_CONTRACT_MARKERS if marker not in section]
        if REQUIRED_CONTRACT_LINK not in section:
            missing.append(REQUIRED_CONTRACT_LINK)
        if missing:
            errors.append(
                f"error: {skill_id}: SKILL.md's Framework section does not reference: "
                + ", ".join(missing),
            )
    return errors
