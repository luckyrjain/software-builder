# deployment-risk-review

Assess the shipping risk of one specific release or change before it goes out. Given a description
of what's changing — affected services, migration steps, rollback plan, and traffic pattern — it
evaluates blast radius, migration risk, rollback complexity, dependency risk, and traffic risk, and
lands on a single `Risk: Low | Moderate | High | Critical` verdict plus a separate confidence read
on the assessment itself.

Unlike a checklist filler, it derives the verdict from a fixed, worst-first precedence rule and
treats every missing input (no rollback plan, no stated traffic pattern) as an explicit evidence gap
that floors the verdict conservatively — never a silent pass.

## When to use

- "Should we ship this change?" for one specific release
- Pre-deploy risk check: blast radius, migration reversibility, rollback speed/safety
- Assessing whether a rollback plan is actually safe for an irreversible migration
- Peak-traffic deploy timing and canary coverage review before shipping

Full routing table: [SKILL.md](SKILL.md#when-to-use-not-to-use).

## Install

```bash
make install-deployment-risk-review
```

Details: [SETUP.md](SETUP.md).

## Pipeline

```
Inputs → Analyze → Report
```

Agent instructions: [SKILL.md](SKILL.md).
