# Domain Comprehension — Round 4: Unconditional Auth & Gateway (P1)

**Date:** 2026-07-31
**Skill:** `domain-comprehension`

---

## Problem statement

Round 3's final review flagged (as an explicit out-of-scope recommendation, not a defect) that
`workflow/phase-1.md`'s "Auth & Gateway" required-output row and its entire "Investigation recipes"
section are still gated behind `api_tooling.export_mode != never` — the identical architectural mistake
round 3 just corrected for P2's base-URL capture. Route-prefix → auth-requirement mapping is core
comprehension data (security posture, JWT/signature filter presence, env bypass rules) independent of
wanting a Postman export; by default (`export_mode: never`) it currently never runs at all.

---

## Scope

**In:** remove the conditional from `workflow/phase-1.md`'s required-output row and section heading, add
the missing `reference/phase-outputs.md` § P1 mirror (this file never had an Auth & Gateway row at all,
conditional or not — proactive fix, same class as round 3's base-URL mirror).

**Out:** nothing else — this is a narrow, single-precedent-following fix.

---

## Decision: unconditional, Redis-OTP bullet stays as-is

Same reasoning as round 3's base-URL decision: matches the skill's UNKNOWN-over-speculation convention.
The Redis-OTP grep bullet (`otp.*redis|redis.*otp|OtpService|OTP_TTL`) stays inside the now-unconditional
section unchanged — it remains useful security/session-infra evidence on its own; `api_tooling`'s
`otp_helper: auto` is one *consumer* of that evidence, not what causes it to be collected. Same
"collect once, consume many" separation already established for base URLs.

---

## Task A — Unconditional Auth & Gateway (P1)

### `workflow/phase-1.md`

Bumps `workflow_version` (currently `1.8`) to `1.11`, matching the changelog row this feature adds (last
row currently `1.10`, verified at spec-writing time — implementation plan must re-verify before assuming).

Find:
```markdown
| Auth & Gateway (when `api_tooling.export_mode` != `never`) | `{map_file}` § Per-Repo Deep Dives | Route-prefix → auth requirement, evidence | Phase incomplete only when export_mode requires it — otherwise skip, no note needed |
```

Replace with:
```markdown
| Auth & Gateway | `{map_file}` § Per-Repo Deep Dives | Route-prefix → auth requirement, evidence | Phase incomplete — UNKNOWN allowed with reason |
```

Find:
```markdown
## Investigation recipes (Auth & Gateway — only when `api_tooling.export_mode` != `never`)
```

Replace with:
```markdown
## Investigation recipes (Auth & Gateway)
```

### `reference/phase-outputs.md`

The P1 section never had an Auth & Gateway row at all. Find:
```markdown
| Smells (initial) | `RISK_MAP.md` § Architectural smells | Smell, location, severity, evidence |

---

## P2 — Flow
```

Replace with:
```markdown
| Smells (initial) | `RISK_MAP.md` § Architectural smells | Smell, location, severity, evidence |
| Auth & Gateway | `{map_file}` § Per-Repo Deep Dives | Route-prefix → auth requirement, evidence |

---

## P2 — Flow
```

---

## Changelog

New row `1.11`, files: `phase-1.md, phase-outputs.md`.

---

## Open items for implementation plan

- None — markdown-only, no code, no new tests.
