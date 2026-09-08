---
workflow_version: 1.2
phase: 3b
produces:
  - fraud_compliance_review
consumes:
  - core_domain_deep_dive
---

# Comprehension Phase P3b — Fraud & compliance (adversarial)

**Sub-agent:** one read-only `generalPurpose` agent with checklist below.

**Required first step:** Re-read every P3 claim; attempt to **disprove** each with counter-evidence or a
bypass path in code. Only write `Exists? YES` after failing to find a bypass.

## Investigation recipes

### Replay / duplicate protection

```bash
rg -l 'ON CONFLICT|idempoten|dedup|requestId|UNIQUE.*constraint|duplicate.*key' \
  --glob '!test*' --glob '!vendor' <repo>
```

### Webhook spoofing / signature verification

```bash
rg -l 'signature|hmac|X-Hub-Signature|webhook.*secret|verify.*signature' \
  --glob '!test*' <repo>
```

### Hardcoded secrets

```bash
# Flag file paths only — never print values
rg -rn 'password\s*=\s*["'"'"'][^$\{]|api_key\s*=\s*["'"'"']|secret\s*=\s*["'"'"']' \
  config/ src/ --glob '!*.md' --glob '!*test*' <repo> | cut -d: -f1-2
```

### Audit trail / immutable log

```bash
rg -l '@Audit|auditLog|audit_trail|AuditEvent|immutable.*log|append.only' \
  --glob '!test*' <repo>
```

### PII in log statements

```bash
# Find log calls near PII field names
rg -l 'log\.(info|debug|warn|error)' --glob '!test*' <repo> | \
  xargs rg -l 'pan\b|aadhaar|phone|email|account.*number|card.*number' 2>/dev/null
```

### Maker–checker / dual control

```bash
rg -l 'approve|checker|dual.*control|four.*eye|second.*factor.*approval|makerChecker' \
  --glob '!test*' <repo>
```

### Privilege escalation

```bash
rg -l 'hasRole|@PreAuthorize|isAdmin|bypass.*auth|skipAuth|ADMIN.*role' \
  --glob '!test*' <repo>
```

## Controls checklist

For each control, attempt to **disprove** with a bypass path before recording `Exists? YES`.

- Replay / duplicate operations (beyond happy-path idempotency)
- Webhook spoofing / signature verification
- Maker–checker / dual control
- Compliance bypass paths (KYC/AML/sanctions as relevant)
- Privilege escalation (unauthorized trigger/approve)
- Manual override + audit trail
- Stale state, orphaned records, recon mismatches
- Audit log immutability; PII in logs (sample log statements)
- Cross-border / regulatory constraints from config
- **Hardcoded secrets** — flag paths only, **never print values**

## Output format

Write to `{map_file}` § Fraud & Compliance. One row per control:

| Control | Exists? | Evidence | Gaps | Confidence |
|---------|---------|----------|------|------------|

## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| Fraud & compliance table | `{map_file}` § Fraud & Compliance | Control, Exists?, Evidence, Gaps, Confidence | Phase incomplete |

## Checkpoint

[phase-completion-gate.md](../reference/phase-completion-gate.md) · [phase-outputs.md § P3b](../reference/phase-outputs.md#p3b-adversarial)
