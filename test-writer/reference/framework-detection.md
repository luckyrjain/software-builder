# Framework detection

Documents what [scripts/detect-test-framework.sh](../scripts/detect-test-framework.sh) implements. Used
by [workflow/detect-conventions.md](../workflow/detect-conventions.md).

## Marker files by ecosystem

| Ecosystem | HIGH confidence (config file present) | MEDIUM confidence (dependency manifest only) | Layout convention |
|-----------|----------------------------------------|-----------------------------------------------|--------------------|
| Python — pytest | `pytest.ini`, `pyproject.toml` with `[tool.pytest.ini_options]`, `setup.cfg` with `[tool:pytest]`, `conftest.py` | `pytest` in `requirements*.txt` / `pyproject.toml` deps | `tests/` dir or `test_*.py` / `*_test.py` beside source |
| Python — unittest | — (stdlib, no config file) | `test_*.py` files using `unittest.TestCase` with no pytest markers | Mirrored `tests/` tree |
| Node/TS — Jest | `jest.config.*` | `jest` in `package.json` deps | `__tests__/` dir or `*.test.ts`/`*.spec.ts` co-located |
| Node/TS — Vitest | `vitest.config.*` | `vitest` in `package.json` deps | `*.test.ts`/`*.spec.ts` co-located |
| Node/TS — Mocha | `.mocharc.*` | `mocha` in `package.json` deps | `test/` dir |
| Go | `go.mod` present + any `*_test.go` | — (stdlib `testing`, always available) | `*_test.go` beside source |
| Java/Kotlin — JUnit 5 | `pom.xml`/`build.gradle(.kts)` referencing `junit-jupiter` | — | `src/test/java` (Maven/Gradle convention) |
| Java/Kotlin — JUnit 4 | `pom.xml`/`build.gradle(.kts)` referencing `junit:junit` (no jupiter) | — | `src/test/java` |
| Ruby — RSpec | `.rspec`, `spec/spec_helper.rb` | `rspec` in `Gemfile` | `spec/` dir, `*_spec.rb` |
| Ruby — Minitest | `test/test_helper.rb` | — (stdlib-adjacent) | `test/` dir, `*_test.rb` |
| .NET — xUnit/NUnit/MSTest | `*.csproj` referencing `xunit`/`NUnit`/`MSTest.TestFramework` | — | Mirrored `*.Tests` project |
| Rust | `Cargo.toml` present | — (built-in `cargo test`) | `#[cfg(test)]` modules or `tests/` dir |

## Confidence rules

- **HIGH** — a dedicated config file or an unambiguous stdlib/build-tool signal (Go, Rust) is present.
- **MEDIUM** — only a dependency-manifest mention, no config file found (e.g. `jest` listed in
  `package.json` but no `jest.config.*` — Jest's own defaults still apply, just not confirmed by a
  config file).
- **AMBIGUOUS** — two or more candidates at the same top confidence tier, most commonly two JS/TS
  runners both configured (a mid-migration repo) or Maven **and** Gradle both present with different
  JUnit majors.
- **NONE_DETECTED** — no marker matched in any ecosystem.

## Resolution order

1. If `test_framework_hint` names a printed `CANDIDATES` entry, select it — no gate fires.
2. Else if exactly one candidate exists at the top confidence tier, select it.
3. Else if 2+ candidates tie at the top tier, this is the ambiguity gate
   ([gate-policy.md §2](gate-policy.md#2-ambiguous-framework-detection)).
4. Else (zero candidates), this is the no-framework gate
   ([gate-policy.md §3](gate-policy.md#3-zero-framework-markers-found)).

## Monorepo note

A monorepo may legitimately have different frameworks per package/service (e.g. a Python backend and a
TypeScript frontend in one repo). Detection scopes to the target's own file(s) — for a `backfill` target
under `frontend/`, only `frontend/`'s markers matter; a Python marker elsewhere in the repo is not itself
grounds for the ambiguity gate. Only candidates found *within the same target's scope* compete.
