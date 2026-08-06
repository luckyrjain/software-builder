# Examples conventions (shared)

**Normative.** Each skill's `examples.md` must comply with these rules.

**Reference bar:** `pr-review/examples.md` (depth and format).

## 1. Required sections

| Section | Minimum |
|---------|---------|
| Invocation table | 8 rows: user phrase → resolved behavior |
| Happy-path scenarios | 3 multi-step walkthroughs with output fragments |
| Degraded path | 1 scenario (MCP missing, sparse data, chat-only, blocked gate) |
| Cross-skill handoff | 1 scenario showing escalation prompt |
| Wrong-skill | 1 row in invocation table → correct skill |

### Invocation table template

| # | User says | Resolves to | Notes |
|---|-----------|-------------|-------|
| 1 | "Review MR !123 in group/project" | pr-review Phase 0→5 | Happy path |
| 2 | "RCA for `service` 14:00–16:00 UTC" | incident-rca Phase 0→5 | Window from user |
| 3 | "Assess rightsizing for `deployment` in prod" | k8s DISCOVER_SOURCES→RENDER | Single deployment |
| 4 | "RCA for INC-4521" | incident-rca Phase 0b → 1→5 | Jira anchor |
| 5 | "Review and post MR !482" | pr-review; Phase 3 gate applies | Posting mode |
| 6 | "RCA payment-api — logs unavailable" | incident-rca slo_breach fallback | Degraded path |
| 7 | "Assess checkout-api — RCA found OOM" | k8s with handoff window | Cross-skill |
| 8 | "Size my K8s deployment" | k8s skill (not pr-review) | Wrong-skill row |

## 2. Scenario format

Every scenario MUST use this structure with **rendered markdown blocks** for expected output (not paraphrase alone):

```markdown
### Scenario: <short name>

**User:** "<exact phrase>"

**Agent:**
1. Phase 0 — …
2. Phase 1 — …

**Expected fragments:**

\```
MCP profile line or scope block as user would see in chat
\```

\```
Finding, hypothesis, or summary line with confidence + reason
\```
```

Minimum **3** scenarios following this format. Each scenario MUST include at least one fenced block showing user-visible chat output.

## 3. Output fragments

- Use fenced code blocks for chat output the user should see — **required**, not optional
- Include at least one confidence label + reason per scenario where applicable
- For pr-review: finding ID (`PRR-SEC-001`, category-prefixed); k8s: `DEC_`/`REC_`; rca: hypothesis type (`deploy_regression`, etc.)
- Degraded scenarios MUST show explicit gap messages or blocked-report text

## 4. Cross-links

Reference phases by canonical name from [phase-glossary.md](phase-glossary.md), not file paths alone.

Examples:

- "Phase 0 (Detect) — MCP profile"
- "DISCOVER_SOURCES → RESOLVE — select Kubernetes MCP/Datadog routes before COLLECT"
- "Phase 2–3 gate — minimum evidence before posting"

## 5. Anti-patterns

| Anti-pattern | Why wrong |
|--------------|-----------|
| Invocation table with only URLs and no behavior column | Agent cannot route user intent |
| Scenarios without expected output fenced blocks | No verification bar for maintainers |
| Copy-paste of workflow steps without user-visible result | Examples become internal docs |
| Examples that contradict `when NOT to use` in SKILL.md | Confuses routing |
| Wrong-skill row missing from invocation table | Agents may mis-invoke skill |
