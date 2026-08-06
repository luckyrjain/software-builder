---
workflow_version: 1.0
phase: detect_conventions
produces:
  - test_framework
  - orchestration
  - integration_convention
  - test_layout
  - mock_style
  - detection_confidence
consumes:
  - repo_root
  - test_framework_hint
---

# Detect conventions

Run [scripts/detect-integration-setup.sh](../scripts/detect-integration-setup.sh) against `repo_root`
before selecting or writing anything. Full marker-file tables and confidence rules:
[reference/framework-detection.md](../reference/framework-detection.md).

```bash
scripts/detect-integration-setup.sh <repo_root>
```

This skill detects **two dimensions**, plus one informational signal, in a single run:

1. **Base test runner** — `FRAMEWORK`/`CONFIDENCE`/`MARKER`: the same ecosystem set unit-test-creator
   detects (pytest, Jest/Vitest/Mocha, Go `testing`, JUnit via Maven/Gradle, RSpec/Minitest, .NET, cargo
   test). Integration tests still run inside one of these runners, just with a different marker/tag/
   directory convention.
2. **Real-dependency orchestration mechanism** — `ORCHESTRATION`/`ORCHESTRATION_CONFIDENCE`/
   `ORCHESTRATION_MARKER`: what the repo uses to stand up a real dependency — `testcontainers`,
   `docker-compose`, `embedded` (an in-memory/embedded-DB convention), or `none`.
3. **Integration naming/tag convention** — `CONVENTION`: an informational signal (`tests/integration/`
   dir, a registered pytest `integration` marker, JUnit `@Tag("integration")`/Failsafe `*IT.java`, a Jest
   `*.integration.test.ts` pattern, a Go `//go:build integration` tag), or `none`. This does **not** by
   itself satisfy the orchestration requirement — a repo can have the naming convention with nothing to
   actually run tests against a real dependency (see §3 below).

## 1. Interpret the `STATUS`/exit-code result (base runner dimension)

| Script output | Action |
|----------------|--------|
| `STATUS: DETECTED` (exit 0) | One clear base-runner candidate — use `FRAMEWORK`/`CONFIDENCE` as-is |
| `STATUS: AMBIGUOUS` (exit 2) | See §2 |
| `STATUS: NONE_DETECTED` (exit 3) | See §3 |

`detection_confidence` is the script's `CONFIDENCE` field (`HIGH` — a framework config file present;
`MEDIUM` — inferred from a dependency manifest only, no dedicated config file). `STATUS`/exit code reflect
the base-runner dimension only, per
[reference/framework-detection.md](../reference/framework-detection.md) — `ORCHESTRATION` and
`CONVENTION` are always reported alongside and never change the exit code themselves.

## 2. Ambiguous base-runner detection — ask once, never guess

If `test_framework_hint` names one of the listed `CANDIDATES`, select it and proceed without asking —
the caller already resolved the ambiguity. Otherwise this is a live gate
([gate-policy.md §2](../reference/gate-policy.md#2-ambiguous-base-runner-detection)): list the candidates
exactly as printed and ask which one is actually in use. Never pick the first alphabetically, the most
common industry default, or the one this session "prefers."

## 3. No orchestration mechanism detected — the level-specific gate

`ORCHESTRATION: none` — no testcontainers, docker-compose, or embedded-DB convention found, and this
session has no other way to stand one up (e.g. no reachable Docker daemon) — is **not** a HARD STOP the
way a missing base runner is. It is this skill's own status,
[`NEEDS_INTEGRATION_ENV`](../reference/gate-policy.md#5-zero-orchestration-mechanism-detected), applied
per-target in Verify & iterate. Detect conventions still records `test_framework`/`test_layout` normally
and Generate tests still writes the test — it just cannot be run against a real dependency this session.
**Never** fabricate a fake dependency and never silently fall back to mocking it — that would secretly
turn an integration test into a unit test; see
[test-quality-deltas.md](../reference/test-quality-deltas.md).

A `CONVENTION` value with `ORCHESTRATION: none` — the naming/tag convention exists but nothing actually
stands up a real dependency — is exactly this gate case, not a reason to relax it.

## 4. No base-runner markers found — ask before writing anything

A repo with zero base-runner markers has no established convention to match, so there is nothing to
detect a "correct" answer from
([gate-policy.md §3](../reference/gate-policy.md#3-zero-base-runner-markers-found)). Ask the caller which
test command to use; never default silently to whatever this skill would pick for a greenfield project.

## 5. Layout and mocking style

Beyond the base-runner name, note from the scan (or a quick follow-up read of 1–2 existing integration
test files when present):

- **Layout** — a `tests/integration/`/`test/integration/`/`it/` tree, `*IT.java` naming, or
  `*.integration.test.ts` co-located files — matched exactly in Generate tests, never introduced as a
  second convention.
- **Mock style** — reserved for anything *other* than the dependency under test (e.g. an existing
  fixtures module for auxiliary test data). The dependency under test itself is never mocked — see
  [test-quality-deltas.md](../reference/test-quality-deltas.md).

If no existing integration test files exist yet (an orchestration mechanism is configured but nothing
written), layout/mock style default to the framework's own idiomatic convention, stated explicitly in the
report as inferred rather than observed.
