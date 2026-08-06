---
workflow_version: 1.0
phase: select_targets
produces:
  - target_list
consumes:
  - target
  - collection_path
---

# Select targets

Turn `target` into a concrete, bounded `target_list` of **endpoints** (method + path) to write Postman
requests and assertions for — never files, similar in spirit to contract-test-creator's interactions.

## 1. Diff mode

Parse the diff named by `target.source` (an MR, a branch range, or the working tree) for new/changed
route/handler definitions — a new route registration, a new/changed handler function, a new/changed
response payload the handler serializes.

- **Skip if the diff itself already includes a matching collection-request change** (a new/edited request
  in the Postman collection that plausibly covers the same endpoint) — tag `SKIPPED_ALREADY_COVERED`. Do
  not duplicate coverage the author already wrote.
- **Skip if an existing collection request clearly already exercises the changed endpoint** — only skip on
  a reasonably confident match (same method + path); when uncertain, keep the target rather than guess
  it's covered.
- Otherwise tag `NEW`.

## 2. Backfill mode

Expand `target.scope` literally:

- An entry already shaped `METHOD /path` is one target directly.
- A file or directory entry is expanded by reading the route-handler source at that path and enumerating
  every endpoint it defines (recursively for a directory), scoped to the file types the repo's detected web
  framework actually uses for route registration.

## 3. Exclusions (both modes)

Never select a target under a generated/vendored/build path — `node_modules/`, `vendor/`, `dist/`,
`build/`, `.venv/`, `target/`, `__pycache__/`, `.git/`, or any directory the repo's own `.gitignore` marks
as generated. Never select an internal-only route not meant to be called externally (e.g. a
framework-internal health/metrics endpoint already excluded from the repo's own OpenAPI spec) unless the
caller's `target.scope` names it explicitly.

## 4. Prioritize using domain-comprehension (optional)

If `<workspace_root>/API_CATALOG.md` exists, use its per-endpoint method/path/producer/consumers/
implementation/exercise-status rows two ways: (a) reorder the `NEW` list so documented-but-unexercised
endpoints (an `API_CATALOG.md` row with no matching test today) come first — determines survival order
under §5's cap, not inclusion; (b) as corroborating evidence (never sole evidence —
[gate-policy.md §5](../reference/gate-policy.md#5-target-has-no-real-observed-endpoint-to-derive-its-shape-from)
still requires the actual route-handler code or an OpenAPI/Swagger spec) for a request/response shape
before Generate tests writes an assertion. If `RISK_MAP.md` also exists, treat a flagged critical/
high-fan-out endpoint with weak test signal the same way. Absent these files, skip this step. Full artifact
table and precedence rules:
[domain-comprehension-integration.md](../../docs/skill-framework/shared/domain-comprehension-integration.md).

## 5. Cap and report overflow

Apply `max_files_per_run` (default 20) to the resulting `NEW` list, in prioritized order (§4) or discovery
order when §4 didn't apply. Anything past the cap is tagged `SKIPPED_MAX_FILES` — listed by name in
`API_TEST_REPORT.md`, never dropped silently (see
[gate-policy.md §8](../reference/gate-policy.md#8-maxfilesperrun-reached)).

## 6. Zero targets

If every candidate resolves to `SKIPPED_ALREADY_COVERED` (diff mode) or `target.scope` is empty after
expansion (backfill mode), report that plainly instead of proceeding to Generate tests with nothing to do:
"No untested endpoints found" / "No endpoints defined under `<scope>`." This is a normal outcome, not a
failure.
