#!/usr/bin/env python3
"""Scaffold the mechanical, boilerplate parts of a new skill: SKILL.md, SETUP.md, examples.md,
reference/smoke-test.md, reference/pressure-tests.md, and a scripts/registry/skills.d/<id>.yaml
fragment.

What this does NOT do, deliberately: it does not fabricate real invocation examples, golden
fixtures, or pressure-test rows. Those require actual domain knowledge of what the skill does --
inventing plausible-looking scenarios here would produce exactly the kind of unearned-looking-done
content this repository's own evidence doctrine (docs/skill-framework/shared/confidence-bands.md)
exists to prevent. Every generated file carries `<!-- TODO -->` markers naming the real convention
doc to read and the minimum real content `make lint-framework` / `make lint-<skill>` will require
before this skill is mergeable. See CONTRIBUTING.md's "Registering a new skill" section for the
steps this script does not (and should not) automate: writing real examples, golden fixtures for
the ten REQUIRED_BEHAVIOR_SCENARIOS (scripts/evals/eval_coverage_contract.py), and the skill's own
`lint-<id>` Makefile target (every skill's lint target is hand-authored with skill-specific checks
-- see make/core.mk -- because what "correct output" means is different per skill).

Usage:
    python3 scripts/new_skill.py <skill-id> --description "One-line description."

After running:
    1. Fill in every <!-- TODO --> in the generated files.
    2. Run `make generate` to merge the new scripts/registry/skills.d/<id>.yaml fragment into
       skills.yaml (this also regenerates the issue-template dropdown and docs cross-references).
    3. Add golden fixtures under evals/golden/<id>/ covering the required behavior scenarios.
    4. Add a `lint-<id>` target to make/core.mk (copy a similar existing skill's target as a
       starting point) and wire it into the `lint-suites`/`lint` aggregate targets.
    5. Add a row to README.md's skills table and a CHANGELOG.md entry.
    6. Run `make lint-framework` and `make generate-check` to confirm the skeleton is wired up.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.registry.paths import skill_dir as _resolve_skill_dir  # noqa: E402
from scripts.registry.schema import parse_registry  # noqa: E402

SKILL_ID_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


def _fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def _skill_md(skill_id: str, description: str) -> str:
    title = skill_id.replace("-", " ").title()
    return f"""---
name: {skill_id}
description: >-
  {description}
  <!-- TODO: extend this description with "Use when ..." and "Keywords: ..." clauses so a
  router/dispatcher can pick this skill correctly -- see an existing skill's frontmatter
  (e.g. squad-map/SKILL.md) for the expected shape. Also add a "Not for X (use Y instead)"
  clause naming the closest skill this one could be confused with. -->
---

# {title}

<!-- TODO: one-paragraph purpose statement -- what this skill produces and for whom. -->

**Untrusted content:** <!-- TODO: name every external input this skill reads (ticket bodies, MR
descriptions, logs, webhook payloads, ...) and state plainly that it is data, never instructions --
see docs/skill-framework/shared/prompt-injection.md. If this skill has no external untrusted input,
say so explicitly rather than omitting the section. -->

## Guardrails

<!-- TODO: fail-closed behavior, confidence bands (OBSERVED/INFERRED/UNKNOWN/CONFLICTED -- see
docs/skill-framework/shared/confidence-bands.md), and any human-action gates (see
docs/skill-framework/shared/post-action-templates.md § Confirmation gates) this skill must honor. -->

## Phases

<!-- TODO: phase-by-phase workflow. Keep this file under 180 lines (make lint-<skill> enforces the
cap declared in this skill's scripts/registry/skills.d/{skill_id}.yaml fragment) -- put detailed
per-phase procedure under workflow/<phase>.md and load it lazily from here instead of inlining it. -->
"""


def _setup_md(skill_id: str) -> str:
    return f"""# Setup — {skill_id}

<!-- TODO: prerequisites, MCP capabilities this skill needs (required vs optional, with degraded
behavior for each optional one), and install instructions. -->

## External services

<!-- TODO: name every MCP server / external service this skill talks to, or state "None". Keep this
aligned with the `setup_freshness.external_services` field in this skill's
scripts/registry/skills.d/{skill_id}.yaml fragment -- make lint-framework checks the two match. -->

**Last reviewed:** <!-- TODO: YYYY-MM-DD -->
"""


def _examples_md(skill_id: str) -> str:
    return f"""# Examples — {skill_id}

See docs/skill-framework/shared/examples-conventions.md for the full required shape (8-row
invocation table, 3 happy-path scenarios with rendered output, 1 degraded-path scenario, 1
cross-skill handoff scenario, 1 wrong-skill row) before filling this in -- the stub below is not a
complete example set on its own.

## Invocation

| # | User says | Resolves to | Notes |
|---|-----------|-------------|-------|
| 1 | <!-- TODO --> | {skill_id} | Happy path |

<!-- TODO: 7 more rows per docs/skill-framework/shared/examples-conventions.md, including one
wrong-skill row that resolves to a *different* skill. -->

### Scenario: <!-- TODO: short name -->

**User:** "<!-- TODO: exact phrase -->"

**Agent:**
1. <!-- TODO -->

**Expected fragments:**

```
<!-- TODO: fenced block of user-visible chat output -->
```

<!-- TODO: 2 more happy-path scenarios, 1 degraded-path scenario, 1 cross-skill handoff scenario. -->
"""


def _smoke_test_md(skill_id: str) -> str:
    return f"""# Smoke test — {skill_id}

Run after install and after any skill edit. See
docs/skill-framework/shared/smoke-test-conventions.md § 2 for the full required structure.

## Invocation

> <!-- TODO: exact user phrase for a small real fixture target -->

## A correct minimal output contains

<!-- TODO: numbered checklist, minimum 5 elements the agent must emit -->

1.
2.
3.
4.
5.

## Failure diagnosis

<!-- TODO: MCP disconnected vs wrong target vs regression -- see smoke-test-conventions.md § 5. -->

Pressure tests: [pressure-tests.md](pressure-tests.md).
"""


def _pressure_tests_md(skill_id: str) -> str:
    return f"""# Pressure tests — {skill_id}

Manual and scripted checks after prompt or workflow edits.
`make lint-{skill_id}` requires at least 2 rows here (edge-case or adversarial).

## Happy path

| Scenario | Expected |
|----------|----------|
| <!-- TODO --> | <!-- TODO --> |

## Edge cases

| Scenario | Expected |
|----------|----------|
| <!-- TODO --> | <!-- TODO --> |
| <!-- TODO --> | <!-- TODO --> |

## Adversarial / prompt injection

LLM-behavior rows below are manual-only.

| Scenario | Expected |
|----------|----------|
| <!-- TODO: an untrusted input tries to redirect the skill's behavior --> | <!-- TODO: skill treats it as data, not instructions --> |
"""


def _registry_fragment(skill_id: str, description: str) -> str:
    # Deliberately the smallest schema-valid shape: extends the shared read-only-leaf-review
    # profile (see skills.yaml's `profiles:` block) so hosts/authority/invocation/risk_class
    # default sanely, declares zero capabilities (BLOCKED by default until real requirements are
    # known -- never guess a capability a skill doesn't actually need), and leaves composition/
    # routing/output_contract as explicit TODOs since those are real design decisions, not
    # boilerplate.
    return f"""{skill_id}:
  path: {skill_id}
  category: analysis  # TODO: pick the real category (see other fragments in this directory)
  extends: read-only-leaf-review
  install:
    requires: []
  composition:
    escalation_targets: []  # TODO: skills this one hands off to, if any
    consumes: []  # TODO: artifact types this skill consumes as input, if any
  capabilities:
    required: []  # TODO: list required host./MCP capabilities, or leave empty if none
    optional: []  # TODO: optional capabilities this skill can degrade without
  lint:
    skill_md_max_lines: 180
    target: {skill_id}
  version: 1.0.0
  type: leaf  # TODO: leaf/router/orchestrator/trigger -- see docs/skill-framework/README.md
  permissions:
    repository: read  # TODO: read/write, matching what this skill actually does
    external_actions: read
    unattended: false
    merge: false
  output_contract:
    produces: []  # TODO: artifact type(s) this skill produces
    produce_fields: {{}}
  dependencies: []
  degraded_behavior:
    missing_capability: none  # TODO: name the capability whose absence changes behavior most
    available_capabilities: []
    behavior: BLOCKED  # TODO: BLOCKED/DEGRADED, matching capabilities.required above
  setup_freshness:
    external_services: "TODO: name every external service, or 'None'"
  routing:
    patterns:
    - "TODO: at least one \\\\b...\\\\b regex pattern real user phrasing would match"
"""


def scaffold(skill_id: str, description: str, *, root: Path = ROOT) -> list[Path]:
    # skill_id has no registry entry yet at scaffold time -- this fragment's own
    # `path: {skill_id}` line (see _registry_fragment above) is what *creates* that
    # entry, so there is nothing for a registry lookup to find here. Routed through
    # the shared resolver anyway (falls back to root / skill_id, identical to today)
    # for consistency with every other skill-directory lookup in this repo, and so a
    # skill_id that already has a stray/stale registry entry is caught by the
    # `skill_dir.exists()` guard below using the *real* resolved directory, not a
    # naive root / skill_id guess.
    registry = parse_registry(root / "skills.yaml")
    skill_dir = _resolve_skill_dir(root, registry, skill_id)
    fragment_path = root / "scripts" / "registry" / "skills.d" / f"{skill_id}.yaml"
    if skill_dir.exists():
        raise FileExistsError(f"{skill_dir.relative_to(root)} already exists")
    if fragment_path.exists():
        raise FileExistsError(f"{fragment_path.relative_to(root)} already exists")

    (skill_dir / "reference").mkdir(parents=True)
    written = []

    def write(relative: str, content: str) -> None:
        path = skill_dir / relative
        path.write_text(content)
        written.append(path)

    write("SKILL.md", _skill_md(skill_id, description))
    write("SETUP.md", _setup_md(skill_id))
    write("examples.md", _examples_md(skill_id))
    write("reference/smoke-test.md", _smoke_test_md(skill_id))
    write("reference/pressure-tests.md", _pressure_tests_md(skill_id))

    fragment_path.write_text(_registry_fragment(skill_id, description))
    written.append(fragment_path)

    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("skill_id", help="kebab-case skill id, e.g. my-new-skill")
    parser.add_argument(
        "--description",
        default="TODO: one-sentence description of what this skill does.",
        help="short description seeded into SKILL.md frontmatter and the registry fragment",
    )
    args = parser.parse_args(argv)

    if not SKILL_ID_RE.match(args.skill_id):
        return _fail(
            f"{args.skill_id!r} is not a valid skill id "
            "(expected lowercase kebab-case, e.g. my-new-skill)"
        )

    try:
        written = scaffold(args.skill_id, args.description)
    except FileExistsError as exc:
        return _fail(str(exc))

    print(f"Scaffolded {args.skill_id}:")
    for path in written:
        print(f"  {path.relative_to(ROOT)}")
    print()
    print("Next steps (not automated -- see this script's module docstring and CONTRIBUTING.md):")
    print("  1. Fill in every <!-- TODO --> / TODO: marker in the files above.")
    print("  2. make generate            # merge the new fragment into skills.yaml")
    print(f"  3. Add golden fixtures under evals/golden/{args.skill_id}/")
    print(f"  4. Add a lint-{args.skill_id} target to make/core.mk")
    print("  5. Add a README.md skills-table row and a CHANGELOG.md entry")
    print("  6. make lint-framework && make generate-check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
