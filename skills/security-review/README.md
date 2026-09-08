# security-review

**Dedicated security review** of supplied code, config, or design content — authentication,
authorization (including tenant isolation), secrets handling, injection, SSRF, data leakage,
cryptography, and dependency exposure. Produces `SECURITY_REVIEW_REPORT.md`: a verdict plus one
section per category, every category populated with findings or an explicit "None found" — never
silently omitted, and an unreachable category is recorded as a gap, never assumed clean.

## When to use

- A dedicated security pass over specific code, config, or a design description before it ships.
- Checking a specific concern: an auth flow, a multi-tenant data-access path, a crypto choice.
- pr-review escalated a security-sensitive finding here for deeper analysis.
- **Not** for a general code-quality MR review — use **pr-review** (it escalates here when it finds
  something security-sensitive).
- **Not** for a plain dependency-upgrade CVE sweep with no broader review scope — use
  **dependency-upgrade-review**.

## Install

```bash
cd software-builder
make install-security-review
```

See [SETUP.md](SETUP.md) for details, including the Claude Code and in-repo discovery paths.

## Pipeline

`Inputs → Analyze → Report`

Full agent instructions: [SKILL.md](SKILL.md).
