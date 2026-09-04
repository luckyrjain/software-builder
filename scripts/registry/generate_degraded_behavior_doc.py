"""Project the normative degraded-mode table in mcp-error-handling.md §4.

`docs/skill-framework/shared/mcp-error-handling.md` §4 is Normative and used to be a
hand-written table naming MCP servers ("Datadog ❌", "GitLab ❌") for 5 of 38 skills, while
`scripts/registry/degraded_behavior.yaml` -- the file the eval scenario harness actually
exercises -- named abstract capability ids for all 38. Two vocabularies, no bridge, and
only one of them checked.

`capability_families.yaml` is that bridge: it is the provider -> family mapping, so a
branded capability id can be rendered in the provider terms a user sees the failure in
while staying a projection of the tested policy. This module renders both halves into one
marker block, so the prose and the policy can no longer disagree.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.registry.generate_docs import escape_table_cell, update_marker_block
from scripts.yaml_safety import load_unique_yaml_file, require_mapping

DEGRADED_TABLE_START = "<!-- degraded-behavior-table:start -->"
DEGRADED_TABLE_END = "<!-- degraded-behavior-table:end -->"

# Display names for the provider prefixes `capability_families.yaml` resolves branded ids
# from. Only the human-facing spelling lives here; which prefixes are providers at all is
# derived from that file, so a new provider cannot be branded without being registered.
PROVIDER_LABELS: dict[str, str] = {
    "datadog": "Datadog",
    "github": "GitHub",
    "gitlab": "GitLab",
    "kubernetes": "Kubernetes MCP",
}


def doc_path(root: Path) -> Path:
    return root / "docs" / "skill-framework" / "shared" / "mcp-error-handling.md"


def _load(root: Path, filename: str, section: str) -> dict[str, Any]:
    path = root / "scripts" / "registry" / filename
    raw = require_mapping(load_unique_yaml_file(path), str(path))
    return require_mapping(raw.get(section), f"{filename} {section}")


def capability_providers(families: dict[str, Any], skill_ids: set[str]) -> dict[str, str]:
    """Branded capability id -> its family name.

    A `<skill-id>.invoke`-shaped id resolves through a family too, but names a skill rather
    than a provider, so it is not branded and is excluded here.
    """
    providers: dict[str, str] = {}
    for family, spec in families.items():
        for capability_id in require_mapping(spec, f"family {family}").get("resolves", []):
            if str(capability_id).split(".", 1)[0] in skill_ids:
                continue
            providers[str(capability_id)] = str(family)
    return providers


def _provider_label(capability_id: str) -> str | None:
    prefix = capability_id.split(".", 1)[0]
    return PROVIDER_LABELS.get(prefix)


def _unavailable_cell(capability_id: str, branded: dict[str, str]) -> str:
    label = _provider_label(capability_id) if capability_id in branded else None
    code = f"`{escape_table_cell(capability_id)}`"
    if label is None:
        return code
    return f"**{escape_table_cell(label)} ❌** {code}"


def render_degraded_behavior_block(root: Path) -> str:
    degraded = _load(root, "degraded_behavior.yaml", "skills")
    families = _load(root, "capability_families.yaml", "families")
    branded = capability_providers(families, set(degraded))

    labels = ", ".join(f"`{label} ❌`" for label in sorted(PROVIDER_LABELS.values()))
    lines = [
        "",
        "Every row below is projected from `scripts/registry/degraded_behavior.yaml` — itself",
        "generated from each skill's `scripts/registry/skills.d/<skill-id>.yaml` fragment — and named",
        "against the families in `scripts/registry/capability_families.yaml`. A provider-branded",
        "capability is shown by provider, because that is how the failure presents to a user",
        f"({labels}); the capability id beside it is what the eval scenario harness exercises.",
        "",
        "`BLOCKED` means all viable sources for that capability are gone and the skill must stop rather",
        "than guess. `FALLBACK` and `DEGRADED` continue on the remaining capabilities named in the last",
        "column.",
        "",
        "| Skill | Unavailable | Capability family | Behavior | Continues with |",
        "|-------|-------------|-------------------|----------|----------------|",
    ]
    for skill_id in sorted(degraded):
        entry = require_mapping(degraded[skill_id], f"degraded_behavior.skills.{skill_id}")
        missing = str(entry["missing_capability"])
        family = branded.get(missing, "—")
        available = [str(item) for item in entry.get("available_capabilities", [])]
        continues = ", ".join(f"`{escape_table_cell(item)}`" for item in available) or "—"
        lines.append(
            f"| `{escape_table_cell(skill_id)}` | {_unavailable_cell(missing, branded)} "
            f"| {escape_table_cell(family)} | {escape_table_cell(entry['behavior'])} | {continues} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_degraded_behavior_doc(root: Path) -> str:
    path = doc_path(root)
    return update_marker_block(
        path.read_text(encoding="utf-8"),
        DEGRADED_TABLE_START,
        DEGRADED_TABLE_END,
        render_degraded_behavior_block(root),
    )
