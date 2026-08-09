# Contributing to software-builder

Thanks for considering a contribution. This repository is a library of portable agent **skills** —
Markdown workflow/instruction definitions, not application code — so most contributions are edits to a
skill's `SKILL.md`, `workflow/*.md`, or `reference/*.md`, plus the occasional helper script under
`*/scripts/`.

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Before you start

- **Security issues:** do not open a public issue — see [SECURITY.md](SECURITY.md).
- **New skills or shared-framework changes:** consider opening an issue first to discuss shape/scope
  before writing the full skill — shared framework files
  (`docs/skill-framework/shared/*.md`, the root `Makefile`, `scripts/`) affect every skill, so changes
  there get more scrutiny than a single skill's own files.
- Read [docs/skill-framework/README.md](docs/skill-framework/README.md) for the conventions every skill
  follows (frontmatter shape, phase structure, guardrail wiring, prompt-injection handling) before
  authoring or editing a skill.

## Development workflow

1. **Edit the canonical skill in this repository** — never an installed copy under `~/.cursor/skills/`,
   `~/.claude/skills/`, etc. Installed copies are overwritten by `make install-*` and are not the source
   of truth.
2. **Keep `SKILL.md` compact** (most skills cap at 150–180 lines, enforced by `make lint-<skill>`) — put
   detailed procedures under `workflow/` and reference material under `reference/`, loaded lazily.
3. **Every skill needs, at minimum:** `SKILL.md`, `SETUP.md`, `examples.md`,
   `reference/smoke-test.md`, and `reference/pressure-tests.md` (≥2 adversarial/edge-case rows, linked
   from `smoke-test.md`) — `make lint-<skill>` enforces these files exist.
4. **Untrusted content stays untrusted.** Any external text a skill reads (MR/PR descriptions, ticket
   bodies, webhook payloads, log pastes, CODEOWNERS files) must be treated as data, never as
   instructions — see [docs/skill-framework/shared/prompt-injection.md](docs/skill-framework/shared/prompt-injection.md).
   If your skill writes output that embeds any of that content (a filename, a rendered report), see
   [docs/skill-framework/shared/safe-output.md](docs/skill-framework/shared/safe-output.md).
5. **Run `make lint`** (or the specific `make lint-<skill>` target(s) you touched) before opening a PR.
   Local setup uses the same hash-pinned lockfile as CI: `make setup` installs from `requirements.lock`.
   If you touched a skill with a `scripts/`/`tests/` directory, its lint target also runs `pytest` —
   make sure that passes too.
6. **Re-run the skill's smoke test** after a substantive edit — see its `reference/smoke-test.md`.

## Repository hygiene

- **SETUP.md freshness:** when you change pinned MCP versions or verify install steps, bump
  `**Last reviewed**` in that skill's `SETUP.md` freshness table and keep `**External services**`
  aligned with `scripts/registry/setup_freshness.yaml`. `make lint-framework` enforces this.
- **GitHub topics/description:** maintainers with repo admin access run
  `bash scripts/apply_repo_metadata.sh` (canonical values in `.github/repo-metadata.yaml`).
- **Tier-3 golden fixtures:** refresh recorded outputs per
  [docs/evals/GOLDEN-REFRESH.md](docs/evals/GOLDEN-REFRESH.md) — CI never calls a live LLM.
7. **Record user-visible changes** in the skill's own `CHANGELOG.md` (or the root one for cross-cutting
   changes), newest entry first.
8. **Open a pull request** describing what changed and why, and the validation you ran (which
   `make lint-*` targets, which smoke/pressure tests). See
   [docs/REPOSITORY.md § Contributing](docs/REPOSITORY.md#contributing) for the fuller reference,
   including the per-skill MCP dependency table.

## Code ownership

See [CODEOWNERS](CODEOWNERS) — platform-level paths (`Makefile`, `scripts/`, `docs/skill-framework/shared/`,
`.github/`) affect every skill and are reviewed accordingly; a single skill's own directory is otherwise
unrestricted.

**Solo maintainer note:** GitHub does not allow PR authors to approve their own PRs. If branch
protection requires approving reviews (or CODEOWNER review), you will be unable to merge your own PRs
until you adjust the ruleset — see [docs/REPOSITORY.md § Merge gate](docs/REPOSITORY.md#merge-gate--repo-admin-settings-github-ui-only).
Keep **required status checks** (`lint`); drop or bypass **approval** requirements until a second
reviewer exists.

## License

By contributing, you agree that your contributions are licensed under this repository's
[MIT license](LICENSE).
