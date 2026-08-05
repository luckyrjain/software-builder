# Smoke test conventions (shared)

**Normative.** Each skill extends these conventions with a dedicated `reference/smoke-test.md` (or anchored section in k8s `workflow/render.md` until Phase 3 extracts it).

**Reference implementations:** `pr-review/reference/smoke-test.md`, `incident-rca/reference/smoke-test.md`, `k8s-overprovisioning-datadog/reference/smoke-test.md`, `domain-comprehension/reference/smoke-test.md`, `squad-map/reference/smoke-test.md`, `mysql-to-postgres-sql/reference/smoke-test.md`.

## 1. When to run

| Event | Run smoke? |
|-------|------------|
| Fresh install (`make install-*`) | Yes |
| Any edit to `SKILL.md`, `workflow/`, `reference/` | Yes |
| Pre-release / before merge to master | Yes |
| User invocation in production | No (use real target) |

Re-run after **any** skill edit — not only after install.

## 2. Required structure

Each skill's smoke doc MUST include:

1. **Fixture** — small real target (MR <10 files; known service + 1h window; deployment with ≥7d metrics)
2. **Invocation string** — exact user phrase to type in chat
3. **Numbered output checklist** — minimum 5 elements agents must emit
4. **Expected first output** — what Phase 0 / MCP profile line looks like when healthy
5. **Script self-test** — if `scripts/` exist: `py_compile` + pytest or shellcheck
6. **Failure diagnosis** — MCP disconnected vs wrong target vs regression (§5 below)
7. **Pressure-test link** — pointer to `reference/pressure-tests.md`

## 3. Standalone `reference/smoke-test.md` format

Every compliant skill maintains a file at `reference/smoke-test.md` with this skeleton:

```markdown
# Smoke test — expected minimal output

Run after install and after any skill edit.

## Invocation

> <exact user phrase for fixture target>

## A correct minimal output contains

1. **Phase 0 / MCP profile** — which integrations are ✅/❌
2. **Scope announcement** — what is being analyzed and boundaries
3. **Core findings** — table or explicit "none"
4. **Summary / report** — executive or human report section
5. **Structured footer** — YAML/JSON metadata where applicable
6. **Confirmation or next step** — post gate, handoff offer, or re-run hint

## Script self-test

<commands or make target>

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
```

### Per-skill invocation strings

| Skill | Invocation string | Expected first output |
|-------|-------------------|------------------------|
| pr-review | `/pr-review` on open MR <10 files in test project | Phase 0: posting mode (`full`/`summary-only`/…) + GitLab server name |
| incident-rca | `RCA for <service> between <from> and <to> UTC — <symptom>` | MCP profile: `Datadog ✅ \| KubeSense … \| GitLab …` |
| k8s | Assess single deployment with ≥7d Datadog metrics, <5 containers | Prerequisites: Datadog ✅; scope: deployment + env + window |
| domain-comprehension | `Map bounded contexts in <domain> workspace` | Session 0 MCP profile + census scope |
| squad-map | `Map squads for repos in <workspace>` | Phase 0: `GitLab ✅ \| Datadog …` |
| mysql-to-postgres-sql | `Scan tests/fixtures/mysql-dialect/hits for MySQL-only SQL` | Scan command + hit file:line list or OK |

## 4. Output checklist template

```markdown
A correct minimal output should contain:

1. **Phase 0 / MCP profile** — which integrations are ✅/❌
2. **Scope announcement** — what is being analyzed and boundaries
3. **Core findings** — table or explicit "none" (not empty header)
4. **Summary / report** — executive or human report section
5. **Structured footer** — YAML/JSON metadata where applicable
6. **Confirmation or next step** — post gate, handoff offer, or re-run hint
```

## 5. Failure diagnosis

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Phase 0 shows all MCP ❌ | MCP server disconnected / auth | Re-auth; check Cursor MCP settings |
| Smoke passes but pressure test fails | Edge case regression | Check `pressure-tests.md` row |
| pytest fails in pr-review | Script change broke diff parser | `make lint-pr-review-scripts` |
| k8s INV failure in smoke | Schema or template drift | `make lint-k8s-skill` |
| incident-rca empty hypothesis rank | Both `error_signals` and `infra_signals` empty | Expected blocked path; verify gap message |
| pr-review stops at Phase 1 | MR closed/merged or merge conflicts | Use open MR fixture |
| k8s Human Report shows formula arithmetic | Render regression | Check `workflow/report.md` smoke rules |

## 6. Makefile integration

| Skill | Lint target |
|-------|-------------|
| pr-review | `make lint-pr-review` (includes pytest) |
| k8s | `make lint-k8s-skill` |
| incident-rca | `make lint-incident-rca` |
| domain-comprehension | `make lint-domain-comprehension` |
| squad-map | `make lint-squad-map` |
| mysql-to-postgres-sql | `make lint-mysql-to-postgres-sql` |
| Framework | `make lint-framework` |
| All | `make lint` |

## 7. Maintainer pressure tests

Smoke = happy path. `pressure-tests.md` = edge cases and **wrong behavior** rows (≥2 per skill). Every smoke doc links to pressure tests.
