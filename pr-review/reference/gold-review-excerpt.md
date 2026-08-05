# Gold review excerpt (format few-shot)

Load in **Phase 5** before rendering the executive summary. This is a **shape reference** — do not copy
findings; match section order, table columns, gate matrix, and **Reason:** prose pattern.

MR context (fictional): `acme/payments` !482 · 3 files · Principal Engineer persona · first review.

---

### Review findings

| ID | Score | Overall | L | I | Conf | Blast radius | Business impact | Location | Evidence | Finding |
|----|-------|---------|---|---|------|--------------|-----------------|----------|----------|---------|
| PRR-DATA-001 | 9 | 🟠 High | H | H | High | All refund webhooks | Wrong amount debited → dispute risk | `RefundHandler.java:88` | `RefundHandler.java:88` | Refund amount uses `int` cents; webhook payload is decimal string — truncation on values ≥ $10.24 |

> **No actionable findings** — use this line instead of an empty table when `emitted = 0`.

### Not raised (suppressed)

- 2 candidates merged into PRR-DATA-001 (thematic cluster)
- 1 suppressed — don't-guess gate (speculative race; no shared state in hunk)

### Engineering improvements

- No `.gitlab-ci.yml` coverage gate on `payments/` — suggest diff coverage threshold

### Positive observations

- ✓ Idempotency key on webhook handler before side effects
- ✓ Regression test covers duplicate delivery case

### Production risk

**Overall:** Medium — one High data-integrity finding on hot payment path; CI green on head.

### Architectural summary

**Overall design:** Adequate — handler logic clear; money type should use `BigDecimal` or fixed-scale long.

---

## Executive Summary

This MR adds refund webhook handling for Juspay callbacks. One High data-integrity issue on amount
parsing should be fixed before merge. CI is green on head; linked Jira AC partially met.

**Files reviewed:** 3 changed · **Review lens:** Principal Engineer

### Evidence

- ✓ 3/3 changed files reviewed in diff
- ✓ CI pipeline success on `diff_refs.head_sha`
- ✓ Linked Jira PAY-1421 with explicit AC

**Confidence:** High — full boundary reviewed; ticket linked; no truncation.

### Code blockers

| Finding | Severity | Blast radius | Business impact | Conf |
|---------|----------|--------------|-----------------|------|
| PRR-DATA-001 | 🟠 High | All refund webhooks | Wrong amount debited → dispute risk | High |

### Decision gates

| Gate | Result |
|------|--------|
| Runtime correctness | ❌ |
| Acceptance criteria | ⚠️ Partial |
| **Recommendation** | **🔴 Request changes** |

### Technical blockers

| Gate | Status |
|------|--------|
| Critical findings | ✅ None |
| High findings | ⚠️ 1 |
| Test quality (§8) | ⚠️ Adequate |

### Process blockers

| Gate | Status |
|------|--------|
| CI pipeline | ✅ Green |
| CODEOWNERS | ✅ @payments-team approved |

**Reason:**

- PRR-DATA-001 is a confirmed logic defect on a cited diff line affecting refund amounts on a
  production payment path — blocks merge per severity matrix.
- AC gap: no test for decimal-string amounts; recommend fix + regression test before approval.

### Must fix

- PRR-DATA-001 — parse refund amount as fixed-scale decimal; add regression test for `$10.25` payload

### Nice to have

- **P2** — Add diff coverage gate for `payments/` module

**Recommendation:** 🔴 Request changes

## Conclusion

Fix the refund amount parsing and add a decimal regression test; then re-review. No Critical security
or auth issues found in the changed hunks.

---

```yaml
# review_metadata (footer — abbreviated)
review_hash: abc123…
findings:
  - id: PRR-DATA-001
    severity: high
    confidence: high
    status: open
    evidence: ["RefundHandler.java:88"]
recommendation: request_changes
```
