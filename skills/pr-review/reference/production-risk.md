# Production Risk (Phase 5)

Load when rendering **Production risk** — immediately **before the executive summary**, after findings and
(optional) Architectural summary. Informed by §17 Rollback safety, §4/§9 hot paths, merge train status,
`domain-overrides.md`, and open Critical/High findings — not a separate deep pass.

## When to include

- **Include** for any non-mechanical MR with production runtime, schema, API, deploy, or IaC touch.
- **Omit** for lockfile/generated/docs-only mechanical diffs.
- **Brief** for isolated low-traffic bugfixes: still render the table; sub-ratings may all be **Low**.

## Rating scale (Low / Medium / High only)

Use exactly **Low**, **Medium**, or **High** for every row including **Production risk** (overall).

| Level | Meaning |
|-------|---------|
| **Low** | Limited blast radius; easy rollback; failure affects few users or internal-only paths |
| **Medium** | Meaningful deploy or rollback steps; partial/outage risk for a subset of users or features |
| **High** | Hard rollback, wide blast radius, or severe user impact if wrong — needs flag, canary, or extra care |

## Dimensions

| Dimension | Assess |
|-----------|--------|
| **Production risk** | Overall ops risk if merged as-is — **synthesize** sub-ratings + §17 + open Critical/High findings. Not always the mathematical max; mitigations (flag, canary, additive migration) can lower overall. |
| **Deployment risk** | Deploy steps, migration order, merge train, multi-service coord, config/IaC change, feature-flag default |
| **Rollback difficulty** | From §17 checklist — revert deploy sufficient? forward migration? irreversible DDL? kill switch? |
| **Blast radius** | How many users, services, regions, or data domains affected if this fails |
| **User impact** | Severity to end users — outage, wrong money, data loss, auth bypass, degraded UX on hot path |

**Production risk** should be **High** when any sub-dimension is **High**, or when open **Critical**
findings remain. **Low** only when all subs are Low and no blocking security/data findings.

Cross-ref §17 — Rollback difficulty should mirror the rollback checklist; do not contradict it.

## Output format

Render in chat and summary (`### Production risk`) **immediately before** the executive summary:

```markdown
### Production risk

| Dimension | Rating | Notes |
|-----------|--------|-------|
| **Production risk** | Medium | … |
| Deployment risk | Low | … |
| Rollback difficulty | Medium | … |
| Blast radius | Low | … |
| User impact | Medium | … |
```

One short **Notes** cell per row (≤1 sentence). Point to §17 table or findings when relevant.
