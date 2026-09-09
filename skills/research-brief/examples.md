# Examples — research-brief

Conventions: [examples-conventions](../../docs/skill-framework/shared/examples-conventions.md).

## Invocation

Invoke `research-brief` whenever a question needs an evidenced, cited answer from primary sources —
repository evidence and, when available, external documentation — rather than a recollection. It is
read-only and report-only: gather and cite evidence, emit `RESEARCH_BRIEF.md` / `research_brief`, and
never edit source, tests, configuration, or docs, or implement anything automatically.

| # | Caller sends | Resolves to | Notes |
|---|-----------------|---------------|-------|
| 1 | "Research this question: does our rate limiter apply per IP address or per API key, based on the code?" | Inputs → Gather → Report; repository evidence alone answers the question, cited to the code | Happy path |
| 2 | "Find out whether the upstream Stripe API still supports the legacy webhook signature scheme — check their current docs." | Inputs → Gather → Report; Gather fetches the vendor's current docs via `host.web.fetch` and cites the URL | External-research path |
| 3 | "Investigate this question: does the vendor's SDK documentation still confirm TLS 1.1 support? Web access isn't available this session, so rely on whatever's vendored in the repo." | Inputs → Gather → Report; degraded mode recorded explicitly, external-dependent claims marked `UNKNOWN` | Degraded-mode path |
| 4 | "I need you to investigate a question for our team, but let me get back to you on the specifics." | Inputs HARD STOP — ask what the actual research question is | Boundary rule |
| 5 | "Investigate our current-state domain and map out the bounded contexts across the order and payment services." | Wrong scope — offer `domain-comprehension` | Wrong-skill row |
| 6 | "Investigate this question: should we retry on 5xx responses from the billing API, or back off entirely? I found conflicting guidance in the code and the vendor's docs." | Inputs → Gather → Report; Findings mark the guidance `CONFLICTED`; Report offers `engineering-decision-discovery` | Escalation offered |
| 7 | "Help me decide which option is best: Postgres or DynamoDB for our new service." | Wrong scope — offer `engineering-decision-discovery` | Wrong-skill row |
| 8 | "What does the ORM library's documentation say about connection pool sizing, and does our own config match that guidance?" | Inputs → Gather → Report; repository config cross-checked against the library's fetched documentation | Happy path (repo + external) |

## Example: a claim with no source is marked UNKNOWN, never asserted

**Evidence:** The research question asks whether the payment service retries on network timeouts. The
repository shows retry logic in `payment_client.py`, but whether the *upstream* payment gateway itself
retries idempotent requests on its own side is undocumented anywhere in the repository, and the
vendor's docs don't address it either.

**Result:**

```
## Findings

| Claim | Evidence status | Source |
|-------|-------------------|--------|
| This service retries network timeouts up to 3 times with backoff | OBSERVED | `payment_client.py:L20-45` |
| The upstream payment gateway also retries idempotent requests on its side | UNKNOWN | none |
```

The first claim is cited and stated as fact. The second has no repository or fetched source, so it is
rendered `UNKNOWN` rather than assumed true or false either way.

## Example: an external claim resolved with a fetched source

**Evidence:** The research question asks whether the upstream Stripe API still supports the legacy
webhook signature scheme. `host.web.fetch` retrieves Stripe's current webhook documentation, which
states the legacy scheme was deprecated.

**Result:**

```
## Findings

| Claim | Evidence status | Source |
|-------|-------------------|--------|
| Stripe deprecated the legacy webhook signature scheme | OBSERVED | https://stripe.com/docs/webhooks/signatures |
```

The claim is cited to the actual URL fetched this session, not a remembered summary of Stripe's docs.

## Example: no decision surfaced, no fabricated escalation

**Evidence:** The research question asks only "what timeout does our HTTP client currently use?" — the
repository answers this directly and unambiguously; no conflicting evidence or open decision exists.

**Result:** The Recommendation section states the answer plainly and offers no escalation, rather than
inventing an `engineering-decision-discovery` or `prd-architect` handoff to fill the section. An
escalation is named only when its trigger — a genuine unresolved decision or PRD input — was actually
met.

## Degraded path: host.web.search/host.web.fetch unavailable

**Evidence:** The research question asks whether a third-party library's latest pinned release still
supports Node 16. `host.web.search`/`host.web.fetch` are unavailable this session, and the repository
only pins the library's version without documenting its Node compatibility.

**Result:**

```
## Degraded-mode note

host.web.search/host.web.fetch were unavailable this session. The claim "the pinned library version
supports Node 16" could not be verified against the vendor's release notes and is marked UNKNOWN below.

## Findings

| Claim | Evidence status | Source |
|-------|-------------------|--------|
| The repository pins the library to version 4.2.0 | OBSERVED | `package.json:L18` |
| Version 4.2.0 supports Node 16 | UNKNOWN | none |
```

The degraded mode is stated explicitly rather than silently answered from training-data recollection.
