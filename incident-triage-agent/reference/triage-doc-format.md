# Triage doc format (normative)

Short, on-call-facing. Not a replacement for incident-rca's full report — a pointer to act on fast, with
the full report available for follow-up.

```markdown
# Triage — <service> — <severity>

**Page:** <alert_title/symptom> (PagerDuty alert <alert_id>)
**Window investigated:** <from_time> – <to_time> UTC
**Owning team:** <squad> (<confidence>) — or **UNKNOWN** (see Gaps) — [squad-map/reference/squad-mapping.md](../../squad-map/reference/squad-mapping.md)

## Likely cause

<incident-rca's top-ranked hypothesis, its band, and one-line evidence — or, verbatim, "No defensible
root cause identified. Evidence insufficient for a causal claim." per incident-rca's own terminal state>

## Gaps

<any gate answered per reference/unattended-gate-policy.md that affects confidence — e.g. "Multi-site
Datadog ambiguity, queried all sites, capped MEDIUM" or "Signal is thin, continued anyway" or "Owning
team UNKNOWN — squad-map config missing">

## Full investigation

<pointer to incident-rca's full report if produced in the same run, or "Full RCA will follow" if this
triage doc had to skip ahead>

---
<Post-RCA-actions paste-ready block from incident-rca, if any — per unattended-gate-policy.md § Post-report offers>
```

## Rules

- **Never state a squad or a root cause with more certainty than incident-rca/squad-map actually
  assert** — LOW confidence findings are reported as LOW, not smoothed into a confident-sounding
  sentence.
- **Never omit the Gaps section** even when empty of content — an on-call engineer needs to know nothing
  was degraded, not just infer it from absence.
- One triage doc per page — this skill never posts more than one document per `page_triggered` event.
