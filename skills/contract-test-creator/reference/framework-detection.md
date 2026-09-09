# Pact tooling detection

Documents what [scripts/detect-pact-tooling.sh](../scripts/detect-pact-tooling.sh) implements. Used by
[workflow/detect-conventions.md](../workflow/detect-conventions.md).

## Marker files by ecosystem

| Ecosystem | Pact library | HIGH confidence | MEDIUM confidence | Layout convention |
|-----------|---------------|------------------|---------------------|--------------------|
| Node/TS | `@pact-foundation/pact` | `package.json` `devDependencies`/`dependencies` entry **and** a local `pacts/*.json` file | `package.json` entry only, no `pacts/` directory yet | Co-located `*.pact.test.ts`/`*.pact.spec.ts`, or a `test/pact/` dir |
| Python | `pact-python` | `requirements*.txt` / `pyproject.toml` entry **and** a local `pacts/*.json` file | Dependency manifest entry only, no `pacts/` directory yet | `tests/pact/` dir or `test_*_pact.py` |
| Java/Kotlin — "Pact JVM" | `au.com.dius.pact` group | `pom.xml` / `build.gradle(.kts)` entry **and** a local `pacts/*.json` file | Build-file entry only, no `pacts/` directory yet | `src/test/java` (Maven/Gradle convention), `*PactTest.java` |
| Go | `github.com/pact-foundation/pact-go` | `go.mod` entry **and** a local `pacts/*.json` file | `go.mod` entry only, no `pacts/` directory yet | `*_pact_test.go` beside source |
| Ruby | `pact` gem | `Gemfile` entry **and** a local `pacts/*.json` file | `Gemfile` entry only, no `pacts/` directory yet | `spec/pacts/` dir, `*_spec.rb` |

A local `pacts/` directory with at least one `*.json` contract file is this skill's analog of
`test-writer`'s "dedicated config file present" HIGH-confidence signal: it means the library isn't just
declared as a dependency, it has already produced or consumed a real contract.

## Broker detection (informational — not a confidence tier, not a gate)

Independently of the table above, the detection script also reports `BROKER: yes|no`:

- **`yes`** — a CI config file under `.github/workflows/*.yml` or `.gitlab-ci.yml` references
  `PACT_BROKER_BASE_URL` or invokes the `pact-broker` CLI.
- **`no`** — no such reference found; the repo's pact files (if any) are read/written locally only.

This informs whether Generate tests writes a provider-verification test that publishes/fetches against a
broker, versus one that reads a local pact file directly
([generate-tests.md §5](../workflow/generate-tests.md#5-broker-vs-local-pact-source)) — it never gates
detection status or confidence on its own.

## Confidence rules

- **HIGH** — the ecosystem's dependency manifest names the Pact library **and** a `pacts/` directory with
  at least one `*.json` file already exists in the target's scope.
- **MEDIUM** — only the dependency-manifest mention, no `pacts/` directory found yet (the library is
  wired in but hasn't produced/consumed a contract in this scope).
- **AMBIGUOUS** — two or more candidates at the same top confidence tier within the same target's scope —
  rare, but possible in a polyglot monorepo with two services both freshly wired for Pact.
- **NONE_DETECTED** — no marker matched in any ecosystem.

## Resolution order

1. If `test_framework_hint` names a printed `CANDIDATES` entry, select it — no gate fires.
2. Else if exactly one candidate exists at the top confidence tier, select it.
3. Else if 2+ candidates tie at the top tier, this is the ambiguity gate
   ([gate-policy.md §2](gate-policy.md#2-ambiguous-pact-tooling-detection)).
4. Else (zero candidates), this is the no-tooling gate
   ([gate-policy.md §3](gate-policy.md#3-zero-pact-tooling-detected)).

## Monorepo note

Detection scopes to the target's own file(s), same as `test-writer`: for a `backfill` target under
`services/orders-consumer/`, only that directory's markers matter; a Pact marker elsewhere in the repo is
not itself grounds for the ambiguity gate. Only candidates found *within the same target's scope*
compete.
