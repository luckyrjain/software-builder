# Make includes

The root `Makefile` remains the public entry point. Large legacy target definitions live in `core.mk`; the root file contains repository-wide phony declarations and includes the core target set.

`generated-roster.mk` is generated from `skills.yaml` by
`scripts/registry/generate_makefile_roster.py` and pulled in with `-include`, not `include`, so a
missing or stale roster leaves `make generate` reachable as the recovery command rather than aborting
Make outright. It defines `ALL_SKILLS`, which the per-skill loops in `lint-framework` iterate, and
every `install-<skill>` / `install-claude-<skill>` rule, whose prerequisite edges are each skill's
`install.requires` read straight from the registry. Adding a skill therefore needs no `core.mk` edit,
and `make generate-check` is the only drift guard the install graph needs. The default goal is pinned
to `install` in `core.mk` before the include, since Make otherwise takes it from the first generated
rule.

## Target families

`core.mk` and the generated roster define ~160 targets between them. They group as follows — prefer
the aggregate; the per-skill targets exist so a single skill's checks can run in isolation.

| Family | What it does |
|--------|--------------|
| `install`, `install-<skill>` | `bash scripts/install.sh [skill]` — install everything, or one skill, with the default `--agent all`. A few carry prerequisites (`install-pr-gatekeeper` depends on `install-pr-review`). |
| `install-claude`, `install-claude-<skill>` | The same, with `--agent claude-user`. |
| `lint` | Everything: `lint-static` then `lint-suites`. |
| `lint-static` | Pure structural/grep checks and the registry validators — no pytest, fails fast. Includes `validate-*`, `generate-check`, `lint-framework`, `verify-install*`, shellcheck, and the per-skill lint targets that need no test run. |
| `lint-suites` | Every pytest-bearing target, including `lint-framework-tests` (the `scripts/tests/` suite). This is the dominant test cost; CI runs it as a separate parallel job from `lint-static`. |
| `lint-<skill>` | One skill's own checks: `python3 scripts/lint_skills.py --skill <id>` for the shared structural set (`SKILL.md` length, workflow frontmatter, dangling links, required `reference/` files, framework links), then that skill's own content assertions. Some also compile and pytest that skill's script. |
| `lint-framework` | The shared `docs/skill-framework/` tree: required files and sections, per-skill `examples.md`/`SETUP.md`/`SKILL.md` wiring, `SETUP.md` freshness, and source-tree reference validation. |
| `generate`, `generate-check` | `python3 -m scripts.registry generate`, with and without `--check`. `generate-check` fails when any generated output has drifted; it is part of `lint-static`. |
| `validate-registry`, `validate-agent-skills`, `validate-hosts`, `validate-evals`, `validate-operational-upkeep`, `validate-release-contract`, `validate-review-contracts` | Registry, frontmatter-conformance, `agent-hosts.yaml`, eval-contract, upkeep-policy, release-contract, and shared review-contract validators. Each is independently runnable. |
| `verify-install`, `verify-install-all`, `verify-release-tag`, `verify-release-bundle`, `verify-github-ruleset` | Post-hoc verification of an installed package, every installed package, a release tag against `VERSION`, a built bundle, and the live GitHub `main` ruleset. `verify-github-ruleset` is maintainer-run only — it needs admin API access CI cannot be granted. |
| `doctor`, `setup`, `setup-hooks`, `package-release`, `backfill-capabilities*` | One-off tooling: preflight, local setup, pre-commit hooks, release packaging, and capability backfill from the catalog. |

## Assertion style

Per-skill lint splits in two.

**Shared structural checks live in Python**, in `scripts/lint_skills.py`, and every `lint-<skill>`
target invokes them with one line: `python3 scripts/lint_skills.py --skill <id>`. That module owns
the `SKILL.md` line cap (read from the registry's `lint.skill_md_max_lines`), workflow frontmatter,
dangling markdown links, required `reference/` files, the shared
skill-routing/prompt-injection/safe-output/cross-skill-escalation links, the `SETUP.md` framework
link, `examples.md`'s `## Invocation` section, the `disable-model-invocation` gate, and the
sanitization contract each skill's rendered-output surface must state. Because it is driven by the
registry rather than by a call site per skill, adding a skill needs **no `core.mk` edit** for any of
them — and each check's wording is written once. `--all` runs the set over every registered skill;
per-skill differences that are genuinely data are either registry fields or one explicit,
commented table in the module.

**Skill-unique content assertions stay in `core.mk`**, as `grep -q '<literal>' <file>` against that
one skill's own prose (`schema_version: 3` in the k8s decision-graph schema, `INV-12`, the KubeSense
strings), alongside that skill's `py_compile`/`pytest`/shellcheck steps. Editing a documented string
can therefore still break a lint target with no reference to the string from the doc's side — grep
`make/core.mk` for a file's path before rewording it. Every such assertion carries a failure
message, either inline (`|| { echo "error: …" >&2; exit 1; }`) or through the `require_heading` /
`require_content` / `require_file` helpers at the top of `core.mk`; a bare `@grep -q` would fail
with nothing but `make: *** [lint-<skill>] Error 1`.
