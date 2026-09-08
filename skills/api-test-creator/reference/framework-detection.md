# Postman/Newman tooling detection

Documents what [scripts/detect-postman-tooling.sh](../scripts/detect-postman-tooling.sh) implements. Used
by [workflow/detect-conventions.md](../workflow/detect-conventions.md). This skill is single-tool
(Postman/Newman) — unlike `unit-test-creator`'s 11-ecosystem or `e2e-test-creator`'s 3-tool detection,
there is no "which tool" question here; the live ambiguity is **which collection file is canonical**.

## Markers

| Marker | Signal strength | Notes |
|--------|-------------------|-------|
| `*.postman_collection.json` anywhere under the target's scope | HIGH (when exactly one exists) | Commonly at repo root, `postman/`, or `tests/postman/` |
| `newman` in `package.json` `devDependencies`/`dependencies` | MEDIUM, only when zero collection files exist | The runner is wired in but hasn't produced/exercised a collection in this scope yet |
| `*.postman_environment.json` | Informational only — never a confidence signal on its own | Names which environment(s) exist; which one is actually run is resolved via §"Resolution order" below |
| A `postman/` or `tests/postman/` directory | Layout signal only | Not itself a confidence tier — informs where Generate tests writes, not whether tooling is detected |

## Confidence rules

- **HIGH** — exactly one `*.postman_collection.json` exists in scope, or 2+ exist and exactly one resolves
  as canonical via hint, naming convention, or CI reference (see "Resolution order" below).
- **MEDIUM** — zero collection files exist, but `newman` is declared as a dependency (tooling present,
  nothing to run yet).
- **AMBIGUOUS** — 2+ collection files exist and none of hint/naming-convention/CI-reference narrows it to
  exactly one.
- **NONE_DETECTED** — zero collection files and no `newman` dependency.

## Resolution order (when 2+ collection files exist)

1. If `test_framework_hint` names one of the printed `CANDIDATES` (by path or basename), select it — no
   gate fires.
2. Else if exactly one candidate's filename contains `main` or `primary` (case-insensitive), select it.
3. Else if exactly one candidate is referenced from a CI config (`.github/workflows/*.yml`,
   `.gitlab-ci.yml`) — a `newman run <path>` invocation naming that file — select it.
4. Else, this is the ambiguity gate
   ([gate-policy.md §2](gate-policy.md#2-ambiguous-canonical-collection)): list every candidate exactly as
   found and ask.

## Monorepo note

Detection scopes to the target's own file(s), same as every sibling skill: for a `backfill` target under
`services/orders-api/`, only that directory's markers matter; a collection file elsewhere in the repo is
not itself grounds for the ambiguity gate. Only candidates found *within the same target's scope* compete.
