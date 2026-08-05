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

## Investigation recipes (Auth & Gateway)

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
