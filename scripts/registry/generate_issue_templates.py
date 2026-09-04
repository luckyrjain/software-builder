"""Regenerate the skill dropdowns in .github/ISSUE_TEMPLATE/*.yml from the registry.

Three issue forms ask "which skill is this about?" and each answered it with its own
hand-typed list. All three had gone stale the same way -- 16 of the 38 registered skills,
frozen at whatever the roster was when the form was written -- because nothing connected
them to the registry. They are now generated from it, and only the non-skill choices each
form adds ("Installer / discovery generally", "Other / not sure") stay hand-authored.

The rewrite is a line splice rather than a YAML round-trip: these forms carry `|` block
scalars and comments GitHub renders verbatim, and re-dumping them would rewrite every
untouched field to make one list current.
"""

from __future__ import annotations

import re
from pathlib import Path

from scripts.registry.models import Registry

ISSUE_TEMPLATE_DIR = (".github", "ISSUE_TEMPLATE")
GENERATED_COMMENT = "# GENERATED from skills.yaml — run make generate"
# The dropdown whose options are the skill roster. Forms use `id:` for the field name, so this
# is the one field id a form has to use to opt in.
SKILL_DROPDOWN_ID = "skill"

_OPTION_RE = re.compile(r"^(?P<indent>\s+)- (?P<value>.*)$")


def issue_template_dir(root: Path) -> Path:
    return root.joinpath(*ISSUE_TEMPLATE_DIR)


def _options_span(lines: list[str]) -> tuple[int, int] | None:
    """The half-open line range of the skill dropdown's `options:` entries, or None.

    Walks to `id: skill`, then to that field's `options:`; the block is every following
    option (and generated comment) line at one indent level deeper.
    """
    try:
        field = next(i for i, line in enumerate(lines) if line.strip() == f"id: {SKILL_DROPDOWN_ID}")
    except StopIteration:
        return None
    options = next(
        (i for i in range(field + 1, len(lines)) if lines[i].strip() == "options:"),
        None,
    )
    if options is None:
        return None
    indent = len(lines[options]) - len(lines[options].lstrip()) + 2
    end = options + 1
    while end < len(lines):
        line = lines[end]
        stripped = line.strip()
        if not stripped:
            break
        if len(line) - len(line.lstrip()) != indent:
            break
        if not (stripped.startswith("- ") or stripped.startswith("#")):
            break
        end += 1
    return options + 1, end


def render_issue_template(text: str, skill_ids: list[str]) -> str | None:
    """Return `text` with its skill dropdown listing every registered skill id, or None when
    the form has no skill dropdown to regenerate.

    Options that are not registered skill ids are the form's own extra choices; they keep
    their text and their relative order, after the generated roster.
    """
    lines = text.splitlines(keepends=True)
    span = _options_span(lines)
    if span is None:
        return None
    start, end = span
    indent = " " * (len(lines[start]) - len(lines[start].lstrip())) if end > start else "        "
    registered = set(skill_ids)
    extras = []
    for line in lines[start:end]:
        match = _OPTION_RE.match(line.rstrip("\n"))
        if match is not None and match["value"] not in registered:
            extras.append(match["value"])
    rendered = [f"{indent}{GENERATED_COMMENT}\n"]
    rendered.extend(f"{indent}- {value}\n" for value in [*sorted(skill_ids), *extras])
    return "".join(lines[:start] + rendered + lines[end:])


def generate_issue_templates(root: Path, registry: Registry) -> dict[Path, str]:
    """Every issue form that carries a skill dropdown, with that dropdown regenerated."""
    outputs: dict[Path, str] = {}
    skill_ids = list(registry.skills)
    for path in sorted(issue_template_dir(root).glob("*.yml")):
        rendered = render_issue_template(path.read_text(encoding="utf-8"), skill_ids)
        if rendered is not None:
            outputs[path] = rendered
    return outputs
