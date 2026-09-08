# DEPLOYMENT_RISK_REPORT.md format

**Normative.** The exact structure [workflow/report.md](../workflow/report.md) must produce.

## Safe rendered-output boundary

`change_description`, `affected_services`, `migration_steps`, `rollback_plan`, and
`traffic_pattern` are caller-supplied, untrusted content
([prompt-injection.md](../../docs/skill-framework/shared/prompt-injection.md)) that render directly
into this document's tables and quoted-evidence lines. Any raw excerpt quoted from
`change_description` or repository content (a migration script snippet, a config diff) is treated
the same way: **redact** plausible credentials/tokens/secrets before quoting it
([safe-output.md § Rule 5](../../docs/skill-framework/shared/safe-output.md#rule-5-pii-secret-redaction-in-rendered-output)),
and:

1. **Structurally escape or fence newlines, leading `#`/`>`/`-`, table `|` delimiters, and
   unbalanced triple-backtick fences in every one of them, always.**
2. Wrap short identifier-shaped values (service names, repo paths, migration/change refs) in an
   inline code span, first **removing** any backtick already in it
   ([safe-output.md § Rule 4](../../docs/skill-framework/shared/safe-output.md#rule-4-markdown-chat-escaping)).

## Structure (order fixed)

```markdown
# Deployment Risk Review — <change/release name>

**Risk: Low | Moderate | High | Critical**

## Blast radius

| Dimension | Finding |
|-----------|---------|
| What breaks if this is wrong | <affected services/users/data, or "Unknown — affected_services not supplied and not inferable"> |

## Migration risk

| Dimension | Finding |
|-----------|---------|
| Data/schema changes | <described change, or "None stated"> |
| Reversibility | <reversible / irreversible / unknown, with reason> |

## Rollback complexity

| Dimension | Finding |
|-----------|---------|
| Rollback plan | <summary, or "None stated — evidence gap"> |
| Speed / safety | <fast-and-safe / slow / unsafe / unknown> |

## Dependency risk

| Dimension | Finding |
|-----------|---------|
| Upstream dependencies (what this needs) | <list, or "None found"> |
| Downstream dependents (what depends on this) | <list, or "None found"> |

## Traffic risk

| Dimension | Finding |
|-----------|---------|
| Deploy timing vs. peak traffic | <off-peak / peak / unknown — conservative default per workflow/inputs.md> |
| Canary / staged-rollout coverage | <covered / not covered / unknown> |

## Confidence

**deployment_confidence: HIGH | MEDIUM | LOW | UNKNOWN**

<one-line reason — cite which sections had evidence gaps, if any>
```

## Rules

- Every one of the five analysis sections (Blast radius, Migration risk, Rollback complexity,
  Dependency risk, Traffic risk) appears in every report, even when the finding is clean/"none
  found" — never silently omitted.
- **Verdict derivation is fixed, worst-first, across the four Risk states:**
  - **Critical** — an irreversible migration with no rollback plan, or a blast radius covering a
    critical/customer-facing path with no rollback plan at all.
  - **High** — an irreversible migration with a rollback plan, a blast radius covering a
    critical/customer-facing path with a rollback plan, or a peak-traffic deploy with no canary/
    staged-rollout coverage.
  - **Moderate** — a reversible migration, a non-trivial blast radius with a rollback plan in
    place, or unresolved dependency risk on a non-critical path.
  - **Low** — reversible or no migration, a fast/safe rollback plan, contained blast radius, and
    either off-peak deploy or adequate canary coverage.
- **An evidence gap (a section that could not be assessed — e.g. no `rollback_plan` supplied and
  none discoverable in the repository) is never silently merged into Low or any other verdict.**
  It is recorded as an explicit "Unknown"/"evidence gap" finding within that section's table, and
  it caps `deployment_confidence` at `LOW` (or `UNKNOWN` when two or more sections have gaps) even
  when the assessed sections alone would otherwise support a lower Risk verdict. A gap on Migration
  risk or Rollback complexity — the two dimensions with the highest cost of being wrong — also
  floors the Risk verdict at **High**, never `Low`/`Moderate`, until the gap is resolved.
