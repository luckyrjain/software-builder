---
workflow_version: 1.14
phase: 1
produces:
  - per_repo_deep_dives
  - ownership_cards
  - bounded_contexts
  - data_ownership
  - domain_glossary
  - smells_initial
  - auth_gateway_table
consumes:
  - inventory
  - contract_inventory
  - domain_graph
  - mechanical_insights
---

# Comprehension Phase P1 — Domain Deep Dive

Manual deep reading and artifact synthesis for bounded contexts, data ownership, and architecture smells.

## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| Per-repo deep dives | `{map_file}` § Per-Repo Deep Dives | One subsection per in-scope application repo | Phase incomplete |
| Ownership cards | `{map_file}` § Per-Repo Deep Dives | Owns / does-not-own per repo with evidence | Phase incomplete |
| Bounded contexts (refined) | `BOUNDED_CONTEXTS.md` | Context cards + logical context Mermaid | Phase incomplete |
| Data ownership (initial) | `DATA_OWNERSHIP.md` | Per entity: authoritative source, repository methods, replicas, caches | Phase incomplete |
| Domain glossary | `DOMAIN_GLOSSARY.md` | Terms, definitions, evidence paths | Phase incomplete |
| Smells (initial) | `RISK_MAP.md` § Architectural smells | Smell, location, severity, evidence | Phase incomplete — empty allowed with note |
| Auth & Gateway | `{map_file}` § Per-Repo Deep Dives | Route-prefix → auth requirement, evidence | Phase incomplete — UNKNOWN allowed with reason |

## Investigation recipes

Prerequisite for any recipe below using `-U`/`(?s)` or other PCRE2 features: confirm `rg --pcre2-version`
succeeds before relying on a "no matches" result. A missing/wrong `rg` build (e.g. `rg` shadowed by a
shell alias instead of the real binary) fails silently rather than erroring — a clean scan result in
that state means "the scan didn't run," not "nothing was found." Never report `UNKNOWN`/"none found"
from one of these recipes without first confirming `rg --version` and `rg --pcre2-version` both succeed.

### Bounded contexts

- **Package/module boundaries:** enumerate top-level packages/modules under the main source root
  (`find <repo>/src/main -maxdepth 2 -type d` for Java/Kotlin, or the language equivalent) — each is a
  candidate bounded-context seed.
- **Aggregate roots / entity clusters:** `rg -l '@Entity|@Document|@AggregateRoot|class \w+Repository\b' --glob '!test*' <repo>` — cluster hits by package; a tight cluster of entities + one repository class is a strong single-context signal.
- **Dependency-direction leakage:** `rg -o '^import .*\.(domain|service|repository)\.' <repo> --glob '*.java' -g '!test*'` (adjust import syntax per language) — a package importing another package's internal implementation types (not its public interface/DTO) suggests contexts are not cleanly separated; record as an architecture-smell candidate too, not just a context-boundary note.
- Record: context name, owning package(s)/module(s), entry points, evidence paths. `UNKNOWN` with
  reason when package structure doesn't cleanly map to a context (e.g. a shared "common"/"util"
  module used by everything, or a single package mixing two domains).

### Data ownership

- **Entity/table ownership:** `rg -l '@Entity|@Table\(name' --glob '!test*' <repo>`, then per hit
  `rg -n '@Table\(name\s*=\s*"[^"]+"\)' <repo>` for the authoritative table name (adjust annotation
  syntax per ORM/language).
- **Cross-repo duplication (dual-write / replica signal):** grep the same entity/table name across
  every in-scope repo — `rg -rl '"<table_name>"' <workspace>` — if write calls (`save`/`persist`/
  `INSERT`/`UPDATE`) appear in more than one repo for the same table, flag a potential ownership
  conflict requiring evidence of which repo is authoritative; do not assume the first hit is owner.
- **Cache/replica indicators:** `rg -l '@Cacheable|RedisTemplate|@RedisHash' --glob '!test*' <repo>` —
  record as a replica/cache, never as the authoritative source, unless evidence shows write-through
  ownership.
- Record: entity, authoritative repo, repository methods (`rg -n 'interface \w+Repository'`),
  replicas, caches, evidence paths. `UNKNOWN` with reason when an entity is referenced in code with no
  `@Entity`/table annotation found (e.g. defined only via raw SQL or a migration file).

### Auth & Gateway

Per repo, per route-prefix:

- **Signature/JWT filters:** `rg -l 'SignatureVerificationFilter|JwtAuthFilter|WebSecurityConfig|@PreAuthorize' --glob '!test*'`
- **Header names:** `rg -o 'X-Signature|X-App-Version|Authorization|User-Id|Profession-Type' <repo> | sort -u`
- **Env bypass rules:** `rg -U -l '(?s)signature.{0,80}bypass|dev.{0,80}whitelist|sit.{0,80}skip' -g 'application*.y*ml' --glob '!test*' <repo>` (`-U`/`(?s)` + bounded span so nested YAML — `signature:\n  bypass:\n    enabled: true` — still matches; the {0,80} bound stops it from crossing into unrelated content further down the file)
- **Salt/secret source (name only, never value):** `rg -n 'signature\.salt|SIGNATURE_SALT' -g 'application*.y*ml' <repo>`
- **Redis OTP usage (for `api_tooling.otp_helper: auto` resolution):** `rg -l 'otp.*redis|redis.*otp|OtpService|OTP_TTL' --glob '!test*'` — record repo name + evidence path if found, `none found` if not. This is the only signal `otp_helper: auto` uses.

Record per route-prefix: required headers, JWT vs signature vs none, environment bypass rules, salt env-var
**name**, and (once per repo, not per-prefix) whether Redis OTP usage was found. `UNKNOWN` with reason when
no filter class is found for a prefix that clearly has protected routes (do not assume "no auth" from
absence of evidence).

## Checkpoint

[phase-completion-gate.md](../reference/phase-completion-gate.md)
