# Smoke test — expected minimal output

Run this on a **known incident** (a window where you already know roughly what happened) to confirm the
skill and its MCP tools work end to end. **Also run it after any edit to this skill** to catch
regressions, not just after install.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

## Invocation

> RCA for `<service>` between `<from>` and `<to>` UTC — `<symptom>`

Example:

> RCA for `neo-disbursement-service` between `2026-06-28 14:00` and `2026-06-28 16:00` UTC — 5xx spike on transfer-money

## Expected first output

**RCA MCP profile:** `Datadog ✅ | KubeSense … | GitLab … | Jenkins … | Jira … | CLI ✅/❌` — naming
which GitLab/Jira instance was used.

## A correct minimal output contains

1. **MCP profile line** — as above.
2. **Incident scope block** — window, environment, service, symptom.
3. **At least one observability signal** (error rate / log count / latency) **or** an explicit gap
   note when no source returned data. When **both** `error_signals` and `infra_signals` are empty,
   the report must state *"No observability data found for this window"* and skip hypothesis ranking.
4. **Deploy/change timeline** — from `get_change_stories` (or Jenkins/GitLab fallback), or an explicit
   *"no change events in window"*.
5. **Primary hypothesis** — band + Reason ✓ / Remaining uncertainty (no decimal in narrative body);
   at least one **alternate** hypothesis.
6. **Evidence table** with a deep link on every row.
7. **Risks** — `Overall:` sentence, then tiered table.
8. **Conclusion** — 2–4 sentence capstone; no `Type ACT` or agent mode instructions in report body.
9. **Gaps / next steps** — and, when the CLI is absent, the note *"hypotheses ranked manually —
   correlator CLI not installed."*
10. **Phase checkpoints** — after Phase 1 (and when sparse, a proceed/stop prompt); partial report when user stops early.
11. **Runbook section** — when a matching runbook/KNOWN_ISSUES entry exists for the primary hypothesis.
12. **MCP profile suffixes** — `(queried)` / `(attempted — no rows)` / `❌`; no *(not queried — Datadog sufficient)* rationalizations.

Post-RCA actions and K8s handoff blocks belong in **chat only** — not inside the report file body.

## Expected for the example incident (deploy regression)

For `neo-disbursement-service`, 14:00–16:00 UTC, "5xx spike on transfer-money" with a 14:20 deploy:

- Signal: error rate ~12% (baseline ~0.3%) starting ~14:45.
- Change: `deployment` change story / Jenkins build at 14:20.
- Primary: **deploy_regression**, **HIGH** with Reason checkmarks; diff touches `TransferMoneyHandler`.
- Alternate ruled out: `infra_capacity` (no OOM/restarts).
- **Conclusion** restates rollback/hotfix action.

## Script self-test

From repo root:

```bash
make lint-incident-rca
make install-incident-rca-deps   # verify kubesense-mcp skill installs
test -f ~/.cursor/skills/kubesense-mcp/SKILL.md || test -f .agents/skills/kubesense-mcp/SKILL.md
python3 incident-rca/scripts/kubesense_logs.py --help   # SPL fallback; requires KUBESENSE_API_KEY for live fetch
```

Validates `evidence.example.json`, schema validator, kubesense_logs tests, and pytest suite.

## Failure diagnosis

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| MCP profile all ❌ | MCP disconnected / auth | Re-auth; check Cursor MCP settings |
| Empty hypothesis rank with no gap message | Regression in Phase 4 gate | Both `error_signals` and `infra_signals` empty — must block with explicit gap |
| No deploy timeline | GitLab/Jenkins MCP missing | Expected gap note; widen window |
| Report contains `Type ACT` | Render regression | Remove agent CTAs from report body; chat only |
| pytest / schema validator fails | evidence JSON or script drift | `make lint-incident-rca` |
| Smoke passes but edge case fails | Pressure scenario regression | See [pressure-tests.md](pressure-tests.md) |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
