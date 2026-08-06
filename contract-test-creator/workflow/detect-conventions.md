---
workflow_version: 1.0
phase: detect_conventions
produces:
  - pact_library
  - broker_configured
  - test_layout
  - detection_confidence
consumes:
  - repo_root
  - test_framework_hint
---

# Detect conventions

Run [scripts/detect-pact-tooling.sh](../scripts/detect-pact-tooling.sh) against `repo_root` (or the
target's own scoped directory in a monorepo) before selecting or writing anything. Full marker-file table
and broker-detection rules: [reference/framework-detection.md](../reference/framework-detection.md).

```bash
scripts/detect-pact-tooling.sh <repo_root>
```

## 1. Interpret the result

| Script output | Action |
|----------------|--------|
| `STATUS: DETECTED` (exit 0) | One clear candidate — use `FRAMEWORK`/`CONFIDENCE`/`MARKER` as-is |
| `STATUS: AMBIGUOUS` (exit 2) | See §2 |
| `STATUS: NONE_DETECTED` (exit 3) | See §3 |

`detection_confidence` is the script's `CONFIDENCE` field (`HIGH` — a `pacts/` directory with a real
contract file already exists; `MEDIUM` — inferred from a dependency manifest only, no local pact file
yet). `broker_configured` is the script's `BROKER` field (`yes`/`no`) — read on every branch, including
`NONE_DETECTED`, since it's informational rather than part of the detection gate.

## 2. Ambiguous detection — ask once, never guess

If `test_framework_hint` names one of the listed `CANDIDATES`, select it and proceed without asking —
the caller already resolved the ambiguity. Otherwise this is a live gate
([gate-policy.md §2](../reference/gate-policy.md#2-ambiguous-pact-tooling-detection)): list the candidates
exactly as printed and ask which one is actually in use. Never pick the first alphabetically or the one
this session "prefers."

## 3. No Pact tooling detected — ask before writing anything

A repo with zero markers has no established Pact library to match, so there is nothing to detect a
"correct" answer from ([gate-policy.md §3](../reference/gate-policy.md#3-zero-pact-tooling-detected)). Ask
the caller which Pact library/broker setup to use; never default silently to whatever this skill would
pick for a greenfield project.

## 4. Role resolution — never inferred here either

`target.role` was already required and validated at Inputs
([gate-policy.md §1](../reference/gate-policy.md#1-missing-or-malformed-target-reporoot-or-role)) — this
phase does not re-derive or second-guess it from the detected tooling or file layout. A repo that only has
provider-side Pact verification wired up today does not by itself mean the caller wants a provider
target; if `target.role` conflicts with what the repo's own layout suggests (e.g. `role: consumer`
pointed at a directory that only contains provider verification code), surface that mismatch to the
caller as a question rather than silently overriding either value.

## 5. Layout and interaction conventions

Beyond the library name and broker status, note from the scan (or a quick follow-up read of 1–2 existing
pact test files when present):

- **Layout** — co-located `*.pact.test.ts` vs. a `test/pact/`/`spec/pacts/` tree — matched exactly in
  Generate tests, never introduced as a second convention.
- **Matcher style** — how the repo's existing pact tests express type/regex/array-like matchers (e.g. the
  Pact DSL's own `like`/`term`/`eachLike` helpers) — reused rather than re-invented per file.
- **Broker vs. local** — if `broker_configured: yes`, note the CI invocation pattern (env vars, broker
  URL, publish step) so Generate tests can match it; if `no`, note the local `pacts/` path convention
  instead.

If no existing pact test files exist yet (a library is configured but nothing written), layout/matcher
style default to the library's own idiomatic convention, stated explicitly in the report as inferred
rather than observed.
