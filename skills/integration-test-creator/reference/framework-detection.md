# Framework detection

Documents what [scripts/detect-integration-setup.sh](../scripts/detect-integration-setup.sh) implements.
Used by [workflow/detect-conventions.md](../workflow/detect-conventions.md). Detection covers three
signals in one run: the base test runner, the real-dependency orchestration mechanism, and an
informational integration naming/tag convention.

## 1. Base test runner (same ecosystem set as unit-test-creator)

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

`STATUS`/exit code (0 `DETECTED`, 2 `AMBIGUOUS`, 3 `NONE_DETECTED`) reflect **this dimension only** — the
same contract as unit-test-creator's own base-runner detection. `ORCHESTRATION`/`CONVENTION` never change
the exit code.

## 2. Real-dependency orchestration mechanism

| Mechanism | Marker(s) | Confidence |
|-----------|-----------|------------|
| `testcontainers` | Python `testcontainers` in `requirements*.txt`/`pyproject.toml`; Node `testcontainers` in `package.json`; Java `org.testcontainers` in `pom.xml`/`build.gradle*`; Go `github.com/testcontainers/testcontainers-go` in `go.mod` | HIGH — an explicit dependency naming the library is unambiguous |
| `docker-compose` | `docker-compose.yml`/`.yaml`, `docker-compose.test.yml`/`.yaml`, or `docker-compose.override.yml`/`.yaml` at repo root, or under `docker/`/`test/` | HIGH — a compose file is a direct, unambiguous orchestration artifact |
| `embedded` | Java `com.h2database` in `pom.xml`/`build.gradle*`; Python `fakeredis`/`mongomock` in `requirements*.txt`; Node `ioredis-mock`/`mongodb-memory-server` in `package.json` | MEDIUM — a lower-confidence signal by design (an embedded/in-memory substitute can diverge in behavior from the real production dependency; a SQLite-in-memory pattern isn't grep-friendly and isn't checked) |
| `none` | No marker above found | — |

When more than one mechanism is present, the script reports by priority `testcontainers` >
`docker-compose` > `embedded` — this is not an ambiguity gate (a repo legitimately using testcontainers
for one service and docker-compose for another is normal, not a conflict requiring a human decision).

## 3. Integration naming/tag convention (informational)

| Ecosystem | Marker |
|-----------|--------|
| Any | A `tests/integration/`, `test/integration/`, or `it/` directory |
| pytest | `markers = integration` (or similar) registered in `pytest.ini`/`pyproject.toml` |
| JUnit | `@Tag("integration")` usage, or the Maven Failsafe plugin / `*IT.java` naming convention |
| Jest/Vitest | A `*.integration.test.ts` naming pattern |
| Go | A `//go:build integration` build tag |

This signal is reported as `CONVENTION` and is purely informational — it never substitutes for an
`ORCHESTRATION` value. A repo can have a clear integration-test naming convention with `ORCHESTRATION:
none`; that combination is exactly the gate case in
[gate-policy.md §5](gate-policy.md#5-zero-orchestration-mechanism-detected), not evidence the convention
alone is enough to run against.

## Confidence rules

- **HIGH** — a dedicated config file, an unambiguous stdlib/build-tool signal (Go, Rust), or an explicit
  orchestration dependency/compose file is present.
- **MEDIUM** — only a dependency-manifest mention with no config file (base runner), or an embedded/
  in-memory substitute (orchestration) whose fidelity to the real dependency is inherently lower.
- **AMBIGUOUS** (base runner only) — two or more candidates at the same top confidence tier, most
  commonly two JS/TS runners both configured (a mid-migration repo) or Maven **and** Gradle both present
  with different JUnit majors.
- **NONE_DETECTED** (base runner) / **`none`** (orchestration/convention) — no marker matched.

## Resolution order

1. Base runner: if `test_framework_hint` names a printed `CANDIDATES` entry, select it — no gate fires.
2. Base runner: else if exactly one candidate exists at the top confidence tier, select it.
3. Base runner: else if 2+ candidates tie at the top tier, this is the ambiguity gate
   ([gate-policy.md §2](gate-policy.md#2-ambiguous-base-runner-detection)).
4. Base runner: else (zero candidates), this is the no-base-runner gate
   ([gate-policy.md §3](gate-policy.md#3-zero-base-runner-markers-found)).
5. Orchestration: checked independently of the base-runner resolution, by the priority order in §2 above.
   `none` triggers the level-specific gate
   ([gate-policy.md §5](gate-policy.md#5-zero-orchestration-mechanism-detected)) at Verify & iterate, not
   at Detect conventions itself.

## Monorepo note

A monorepo may legitimately have different base runners and different orchestration mechanisms per
package/service (e.g. a Python backend using testcontainers and a Node frontend using docker-compose).
Detection scopes to the target's own file(s) — for a `backfill` target under `backend/`, only
`backend/`'s markers matter for both dimensions; markers found elsewhere in the repo are not grounds for
either the ambiguity gate or a false `ORCHESTRATION` reading.
