# Framework detection

Documents what [scripts/detect-e2e-tooling.sh](../scripts/detect-e2e-tooling.sh) implements. Used by
[workflow/detect-conventions.md](../workflow/detect-conventions.md).

Scope is **web browser flows only** — Playwright, Cypress, and Selenium/WebDriver. API/CLI black-box
journey tooling is not detected here; it is out of scope for this skill entirely.

## Marker files by framework

| Framework | HIGH confidence (config file present) | MEDIUM confidence (dependency manifest only) | Layout convention |
|-----------|----------------------------------------|-----------------------------------------------|--------------------|
| Playwright | `playwright.config.*` at repo root | `@playwright/test` in `package.json` devDependencies | `e2e/`, `tests/e2e/`, or `playwright-tests/`; `*.spec.ts` naming |
| Cypress | `cypress.config.*` at repo root | `cypress` in `package.json` devDependencies | `cypress/e2e/` (Cypress ≥10 default) or `cypress/integration/` (legacy Cypress <10); `*.cy.ts` naming |
| Selenium/WebDriver | — (no single canonical config file across ecosystems) | `selenium-webdriver` in `package.json` (Node); `selenium` in `requirements*.txt` (Python); `org.seleniumhq.selenium` in `pom.xml`/`build.gradle*` (Java) | `e2e/` or `tests/e2e/`; naming varies by language, matched to whatever the repo already uses |

## Confidence rules

- **HIGH** — a dedicated config file is present (Playwright, Cypress only — Selenium has no equivalent
  single canonical config file, so it never reaches HIGH by this script; a real repo may still layer a
  runner config like a WebdriverIO config on top, which is out of this skill's detection scope).
- **MEDIUM** — only a dependency-manifest mention (Node `package.json`, Python `requirements*.txt`, Java
  `pom.xml`/`build.gradle*`).
- **AMBIGUOUS** — two or more candidates at the same top confidence tier, most commonly a repo mid-
  migration with both `playwright.config.*` and `cypress.config.*` present.
- **NONE_DETECTED** — no marker matched for any of the three frameworks.

## Resolution order

1. If `test_framework_hint` names a printed `CANDIDATES` entry, select it — no gate fires.
2. Else if exactly one candidate exists at the top confidence tier, select it.
3. Else if 2+ candidates tie at the top tier, this is the ambiguity gate
   ([gate-policy.md §2](gate-policy.md#2-ambiguous-browser-tooling-detection)).
4. Else (zero candidates), this is the no-tooling gate
   ([gate-policy.md §3](gate-policy.md#3-zero-browser-tooling-markers-found)).

## Monorepo note

A monorepo may legitimately have different browser tooling per app (e.g. a marketing site on Playwright
and a dashboard app on Cypress in one repo). Detection scopes to the target journey's own app/directory —
for a `backfill` journey whose `start_route` lives under `apps/dashboard/`, only `apps/dashboard/`'s
markers matter; a Playwright marker elsewhere in the repo is not itself grounds for the ambiguity gate.
Only candidates found *within the same journey's scope* compete.
