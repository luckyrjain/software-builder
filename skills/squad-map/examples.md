# Examples — invocation patterns

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation table

| # | User says | Behavior |
|---|-----------|----------|
| 1 | "Map squads for repos in `/Projects` — org acme, segment 2" | Inputs → Phase 0 → Phase 1 → `SQUAD_MAP.md` |
| 2 | "Who owns api-disbursement?" | Single-repo scope → GitLab + Datadog lookup |
| 3 | "Refresh squad map" | `refresh: true` → re-query MCP even if artifact exists |
| 4 | "Squad mapping for disbursement-service, neo-disbursement-service" | Explicit repo list + aliases from config |
| 5 | "Map squads — GitLab only" (Datadog ❌) | GitLab squad filled; Datadog UNKNOWN |
| 6 | "Map squads — no MCP" | CODEOWNERS fallback; confidence LOW |
| 7 | "Full domain map for lending" | **Wrong skill** → domain-comprehension (which delegates 0b to squad-map) |
| 8 | "RCA for outage on disbursement-service" | **Wrong skill** → incident-rca |

---

### Scenario: Multi-repo workspace — happy path

**User:** "Map squads for repos in `/Users/me/Projects/disbursement` — org prefix acme, squad segment 2."

**Agent:**

1. Inputs — load `squad-map-config.yaml` or ask for segment; discover ~12 git repos
2. Phase 0 — GitLab ✅ (queried), Datadog ✅ (queried)
3. Phase 1 — `get_project` + `search_datadog_services` per repo → reconcile → write `SQUAD_MAP.md`

**Expected fragments:**

```
Squad map MCP profile: GitLab ✅ (queried) | Datadog ✅ (queried)
```

```
| api-disbursement | acme/disbursement/api-disbursement | disbursement | neo-disbursement-service | disbursement-platform | HIGH | GitLab get_project; Datadog name:neo-disbursement-service* |
```

```
Mapped: 10/12 repos | HIGH: 7 | MEDIUM: 2 | UNKNOWN: 3 | Conflicts: 1
```

---

### Scenario: GitLab only — degraded path

**User:** "Who owns auth-gateway in this workspace?"

**Agent:** GitLab ✅, Datadog ❌ → GitLab squad from namespace; Datadog team UNKNOWN; note in header.

**Expected fragment:**

```
Squad map MCP profile: GitLab ✅ (queried) | Datadog ❌
```

```
| auth-gateway | acme/platform/auth-gateway | platform | UNKNOWN | UNKNOWN | MEDIUM | GitLab get_project |
```

---

### Scenario: No MCP — CODEOWNERS fallback

**User:** "Map squads for payment-service — no GitLab or Datadog access."

**Agent:** Both ❌ → Phase 1 Step 7 → grep CODEOWNERS + git log hints.

**Expected fragment:**

```
| payment-service | N/A | UNKNOWN | UNKNOWN | UNKNOWN | LOW | CODEOWNERS @org/payments-team |
```

---

### Scenario: Cross-skill — domain-comprehension delegation

**User:** (via domain-comprehension Session 0b after census)

**Agent:** Invokes squad-map with census repo list + `domain-config.yaml` ownership block; on return,
domain-comprehension pre-fills `UNKNOWNS.md` Likely owner for confidence ≥ MEDIUM.

**Handoff prompt (user):**

> Map bounded contexts and data ownership for disbursement — full domain comprehension

(Routes to **domain-comprehension**, which calls squad-map at Session 0b.)
