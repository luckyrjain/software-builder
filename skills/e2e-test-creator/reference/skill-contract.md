# Skill contract — non-negotiable

Load immediately after [SKILL.md](../SKILL.md). These rules override convenience shortcuts.

Shared rules common to all four `*-test-creator` skills — test-first evidence, test-quality rules,
refactor limits, and the shared report skeleton — live in
[test-creation-principles.md](../../docs/skill-framework/shared/test-creation-principles.md) and are
**not restated here**. This file states only what's different for full-browser end-to-end tests.

## e2e-specific deltas

1. **Journeys, not files** — the unit this skill selects, generates, and reports on is a **user journey**
   ("user logs in and views their dashboard"), never a single file/function. `target_list`,
   `test_files_written`, and the report's `## Targets` table are all keyed by journey name. See
   [workflow/select-targets.md](../workflow/select-targets.md).
2. **User-visible assertions only** — every assertion is on visible text, ARIA role/accessible name, URL,
   or visibly rendered state. Never internal DOM structure or class names that aren't part of the page's
   real contract with a user. See
   [reference/test-quality-deltas.md](test-quality-deltas.md).
3. **Requires a reachable running app instance** — a meaningful e2e test can only be written or run
   against a real, currently-reachable instance of the app (locally started, a staging URL, or a preview
   deployment). Without one, gate the affected journeys `NEEDS_BROWSER_ENV` rather than fabricating what
   the UI would show — see [gate-policy.md §5](gate-policy.md#5-no-reachable-app-instance).
4. **No hard-coded waits** — never `sleep`/`cy.wait(<fixed ms>)`/`Thread.sleep`. Always the framework's
   own auto-waiting or retry-assertion mechanism.
5. **Scope is web browser flows only** — Playwright, Cypress, or Selenium/WebDriver driving a real
   browser. Not API/CLI black-box journeys — those are out of scope for this skill entirely (no
   equivalent skill handles them today; say so rather than stretching this skill to cover them).
6. **Escalate, don't stretch** — a caller who actually wants a below-the-UI service-seam test routes to
   **integration-test-creator**; the caller's own tooling being "harder to reach" than expected is not a
   reason to write a UI test where a seam test was actually requested. See
   [SKILL.md § Cross-skill escalation](../SKILL.md#cross-skill-escalation).

## Inherited from the shared contract (see the linked doc for full text)

- Detect before writing; never introduce a second browser-tooling framework, or invent one for a repo
  with none, without asking.
- Real assertions only; no tautological or always-pass tests.
- Gate, don't guess — HARD STOP / ask per [reference/gate-policy.md](gate-policy.md).
- Verify before claiming — never report a test as passing without having run it in this session.
- No silent caps — `max_files_per_run`/`deadline` overflow always listed by name.
- Never hide a failure — no `.skip`/`.only`-around/deleted assertion to force a suite green without
  flagging it in `E2E_TEST_REPORT.md`.
- Deliverable — emit [E2E_TEST_REPORT.md](report-format.md) every run, even a single-journey backfill.
- Lazy-load — only the reference file(s) named for the current phase in
  [lazy-load-index.md](lazy-load-index.md); do not bulk-read all of `reference/`.

Routing: [skill-routing.md](../../docs/skill-framework/shared/skill-routing.md).
