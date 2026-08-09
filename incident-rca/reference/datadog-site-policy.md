# Datadog site selection — no shared config mutation

incident-rca sessions are often long-lived and may run alongside other agents sharing the same Datadog
MCP / **ddconfig** profile. **Never mutate shared Datadog configuration** (site, API key, default tags)
for one RCA run — that can redirect unrelated sessions to the wrong site.

## Rules

| Do | Don't |
|----|-------|
| Pass an explicit **site** (or region) on each Datadog MCP query when the tool supports it | Run **ddconfig** to change `datadog_site` mid-session |
| Ask the user which site to use, then **record** the choice in `query_references[]` | Assume US1 when EU metrics are empty without checking site |
| Label evidence `"source": "datadog_eu"` / `"datadog_us1"` when multiple sites are queried | Leave site implicit when cross-site correlation is required |
| Re-run **ddsetup** only when auth is broken and the user approves | Re-run ddsetup/ddconfig proactively "to be safe" |

## Multi-site workflow (replaces ddconfig mutation)

When [workflow/phase-0.md](../workflow/phase-0.md) §Multi-site Datadog applies:

1. Ask which site(s) the affected service reports to (or read from org profile / evidence).
2. For each site, issue Datadog MCP calls with that site's scope — use per-call site parameters when
   available; when the MCP only supports one active site, **ask the user to switch the MCP session** (or
   run a separate read-only session) rather than writing ddconfig from this skill.
3. Collect signals per site; cap cross-site correlation confidence at **MEDIUM** (clock drift).

## Log redaction

All log paths must follow [log-redaction.md](log-redaction.md) regardless of site.
