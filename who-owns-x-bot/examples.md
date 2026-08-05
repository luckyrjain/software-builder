# Examples — invocation patterns

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation table

| # | Caller sends | Behavior |
|---|----------------|----------|
| 1 | `query: api-disbursement` | Inputs → Lookup → Resolved reply |
| 2 | `query: legacy-ledger` (known GitLab/Datadog conflict) | Inputs → Lookup → Ambiguous reply |
| 3 | `query: ledger` (matches 3 repos) | Inputs → Lookup → Ambiguous reply, up to 3 candidates listed |
| 4 | `query: some-typo-repo` (no match) | Inputs → Lookup → Unknown reply |
| 5 | `query: ` (empty) | Inputs HARD STOP → usage-hint reply, Lookup never runs |
| 6 | `query: payment-service`, squad-map has no MCP (CODEOWNERS fallback, LOW confidence) | Unknown reply — LOW confidence never surfaces as Resolved |
| 7 | "Who owns api-disbursement?" typed in an interactive chat session | **Wrong skill** → squad-map (this skill doesn't auto-invoke; see `disable-model-invocation`) |
| 8 | "Map squads for the whole workspace" | **Wrong skill** → squad-map (full table, not a single answer) |

---

### Scenario: Resolved — happy path

**Caller:** `query: api-disbursement`, `workspace_root: /Users/me/Projects/disbursement`

**Agent:**

1. Inputs — `query` present, non-empty
2. Lookup — existing `SQUAD_MAP.md` has a fresh HIGH-confidence row for `api-disbursement`, no conflict
   flag → skip re-query
3. Classify → Resolved → format and reply

**Expected fragment:**

```
:white_check_mark: *api-disbursement* → *disbursement* squad (HIGH confidence)
GitLab namespace acme/disbursement/api-disbursement; Datadog team disbursement-platform
```

---

### Scenario: Ambiguous — GitLab/Datadog conflict

**Caller:** `query: legacy-ledger`

**Agent:** squad-map row exists with a conflict flag (GitLab squad `payments` ≠ Datadog team
`collections`) → Ambiguous shape, both squads listed, no pick made for the user.

**Expected fragment:**

```
:warning: *legacy-ledger* — GitLab and Datadog disagree, need a human to confirm:
• GitLab squad: *payments* …
• Datadog team: *collections* …
```

---

### Scenario: Unknown — no match

**Caller:** `query: some-typo-repo`

**Agent:** squad-map finds no matching row and a fresh lookup also returns no match → Unknown shape with
configured fallback contact.

**Expected fragment:**

```
:grey_question: Couldn't find ownership for *some-typo-repo*. Try #ask-platform.
```

---

### Scenario: Cross-skill — wrong entry point

**Caller:** (human, typing in an interactive Cursor/Claude Code session) "Who owns api-disbursement?"

**Agent:** This skill does not auto-invoke (`disable-model-invocation: true`); the request routes to
**squad-map** instead, which can hold a follow-up conversation this skill cannot.

**Handoff prompt (user):**

> Who owns api-disbursement?

(Routes to **squad-map** directly — see
[skill-routing.md](../docs/skill-framework/shared/skill-routing.md) rule 4.)
