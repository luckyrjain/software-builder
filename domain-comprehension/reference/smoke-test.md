# Smoke test

Conventions: [smoke-test-conventions.md](../../docs/skill-framework/shared/smoke-test-conventions.md).

## Invocation string

```
Comprehend the <domain> subsystem in <workspace_root> — Session 0 only (quick orientation)
```

## Preconditions

- Agent workspace is **software-builder** clone (skill installed) OR `domain-comprehension/SKILL.md` readable
- Target workspace has at least one git repo with README
- understand-anything plugin optional for Session 0 smoke

## Expected behavior

1. Reads [workflow/inputs.md](../workflow/inputs.md)
2. Creates or loads `domain-config.yaml`
3. Produces `EXEC_SUMMARY.md` with Draft Five Questions (DRAFT status)
4. Creates `PROGRESS.md`, `UNKNOWNS.md`, `SQUAD_MAP.md` stub, map skeleton
5. Runs Session 0b (delegates to **squad-map**) when GitLab or Datadog MCP connected
6. Reports scope/budget checkpoint before P0.5
7. Does **not** modify application source in target workspace

## Failure diagnosis

| Symptom | Likely cause |
|---------|--------------|
| No `domain-config.yaml` | Session 0 skipped |
| Five questions empty | Config not merged; check domain pack path |
| Writes to app source | Violates read-only rule — fix workflow |
| `/understand` before user approval | P0.5 started without checkpoint |

## Full pass smoke (optional, expensive)

After user approves P0.5 on a **single small repo**:

- `manifest.json` has one entry with `status: ok`
- `{map_file}` § Mechanical Insights non-empty
