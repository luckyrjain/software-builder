# Evidence precedence (normative)

When sources disagree, **higher tier wins**. Lower tier cannot raise confidence above the winning tier.

```
1. Executable code (handlers, migrations, committed protos/OpenAPI)
      ↓
2. Runtime telemetry (Datadog P2b — observed traffic)
      ↓
3. Committed configuration (Helm, K8s manifests, env templates in repo)
      ↓
4. Tests (integration/e2e > unit for cross-service claims)
      ↓
5. Code comments
      ↓
6. ADR (committed in repo, with code check)
      ↓
7. README / package docs (in repo)
      ↓
8. Wiki / Confluence / Jira / external decks
```

## Rules

1. **Code is primary truth; runtime validates behavior, not intent** — traffic proves an edge is exercised; absence does not prove dead code alone. Runtime does **not** outrank code on conflict: if telemetry shows traffic to a path the code scan didn't find, that means the scan missed something — escalate to `UNKNOWNS.md` and re-scan; do not let the runtime observation silently override the code finding.
2. **Code beats config** when config drift is suspected — note in `UNKNOWNS.md`.
3. **Wiki/README at HIGH forbidden** — see [confidence-rubric.md](confidence-rubric.md).
4. On conflict — document in `UNKNOWNS.md` or downgrade confidence; never average tiers.
5. **Producer beats consumer** for data ownership (unchanged from confidence rubric).

## P2b alignment

| Situation | Resolution |
|-----------|------------|
| Code + runtime agree | `runtime_confirmed`; confidence may be HIGH |
| Code only | `referenced` or implementation status only |
| Runtime only | `RUNTIME_ONLY`; investigate missing code — do not invent handlers |
| Neither | `unknown` / `dead_code` candidate after ref scan |
