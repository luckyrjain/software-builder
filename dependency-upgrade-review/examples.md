# Examples — invocation patterns

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation table

| # | Caller sends | Behavior |
|---|---------------|----------|
| 1 | "Review upgrading `lodash` from `4.17.15` to `4.17.21`" plus changelog text and a manifest excerpt | Inputs → Analyze → Report; clean bump, verdict `Safe to upgrade` |
| 2 | "Should we bump `express` from `4.18.0` to `5.0.0`?" with changelog text showing removed middleware APIs and no replacement documented | Inputs → Analyze → Report; verdict `Do not upgrade yet` |
| 3 | "What breaks if we upgrade `django` `3.2`→`4.2`?" with changelog text showing a renamed setting with a documented drop-in fix | Inputs → Analyze → Report; verdict `Upgrade with mitigations` |
| 4 | "Review the `requests` `2.28.0`→`2.31.0` bump" with no changelog text and no manifest excerpt supplied | Inputs → Analyze → Report; verdict `Blocked — insufficient info` — both changelog- and manifest-dependent checks record an Unknown gap |
| 5 | "Review a dependency upgrade" with no dependency name or versions given | Inputs phase HARD STOPs and asks for `dependency_name`, `current_version`, `target_version` — no Analyze |
| 6 | "Bump `openssl` from `1.1.1t` to `3.0.9`" with changelog text but no manifest excerpt | Inputs → Analyze → Report; breaking-change/API-diff checks run from changelog text, transitive-dependency check records an explicit Unknown gap |
| 7 | "Review upgrading `jackson-databind` `2.9.0`→`2.15.0`" with changelog and manifest text describing a known deserialization CVE affecting `2.9.0`, fixed by `2.15.0`, and the caller asks whether it's exploitable in their own code paths | Inputs → Analyze → Report flags the CVE; offers the **security-review** handoff per Cross-skill escalation |
| 8 | "This MR also bumps `pytest` from `7.0` to `8.0` — is that part fine?" inside a broader MR-review request | This skill reviews the bump in isolation; offers the **pr-review** handoff for the MR as a whole per Cross-skill escalation |
| 9 | "Migrate our MySQL schema to Postgres" | Wrong skill — not a version-bump review → **mysql-to-postgres-sql** directly |

### Scenario: Clean happy path

**Caller:** "Review upgrading `lodash` from `4.17.15` to `4.17.21`" with changelog text (patch-level fixes
only, no removed APIs) and a manifest excerpt showing no transitive pin changes.

**Agent:**
1. Inputs — resolves `dependency_name: lodash`, `current_version: 4.17.15`, `target_version: 4.17.21`,
   both optional inputs present.
2. Analyze — breaking changes: none found in changelog text. CVEs: two CVEs affecting `4.17.15`, both
   fixed in `4.17.21`. API differences: none. Transitive impact: no conflicts in the manifest excerpt.
   Rollout risk: patch bump, trivially reversible.
3. Report — no proven blocker, no evidence gap, no unmitigated finding (the two CVEs are resolved by the
   upgrade itself) → `Safe to upgrade`.

**Expected fragment:**

```markdown
# Dependency upgrade review — lodash 4.17.15 → 4.17.21

**Verdict: Safe to upgrade**

## CVEs

| CVE | Affects | Fixed in | Severity |
|-----|---------|----------|----------|
| `CVE-2020-8203` | `4.17.15` | `4.17.20` | High |
| `CVE-2021-23337` | `4.17.15` | `4.17.21` | High |

Both CVEs affect only `current_version` and are resolved by this upgrade — not a blocker.
```

### Scenario: Worst-state blocker

**Caller:** "Should we bump `express` from `4.18.0` to `5.0.0`?" with changelog text stating several
middleware helper methods were removed with no replacement documented, and a manifest excerpt.

**Agent:**
1. Inputs — resolves the triple plus changelog text and manifest excerpt.
2. Analyze — breaking changes: middleware helpers removed, changelog explicitly states "no direct
   replacement." API differences: the removed symbols and their call sites. CVEs: none found. Transitive
   impact: no conflicts. Rollout risk: not reversible without reverting the whole bump, since callers
   would need to be rewritten either way.
3. Report — a breaking change with no available mitigation is a proven blocker → `Do not upgrade yet`,
   which wins precedence over any other finding.

**Expected fragment:**

```markdown
# Dependency upgrade review — express 4.18.0 → 5.0.0

**Verdict: Do not upgrade yet**

## Breaking changes

| Change | Source | Impact |
|--------|--------|--------|
| `res.sendfile()` and related legacy helpers removed | `"removed with no direct replacement" — changelog_text` | Every caller using the removed helpers must be rewritten before upgrade is safe |
```

### Scenario: Evidence-gap multi-finding

**Caller:** "Review the `requests` `2.28.0`→`2.31.0` bump" — no changelog text and no manifest excerpt
supplied, caller wants a quick read anyway.

**Agent:**
1. Inputs — resolves the triple; both optional fields absent, noted before Analyze starts.
2. Analyze — breaking changes / API differences: cannot be checked from version numbers alone without
   changelog text → recorded Unknown. CVEs: reasoned from the version delta and public advisory
   knowledge of the package/version pair, not blocked by the missing changelog. Transitive impact: cannot
   be checked without a manifest excerpt → recorded Unknown. Rollout risk: minor-version bump, typically
   reversible, but stated with the same evidence caveat.
3. Report — no proven blocker found, but two checks recorded an evidence gap → `Blocked — insufficient
   info`, per precedence.

**Expected fragment:**

```markdown
# Dependency upgrade review — requests 2.28.0 → 2.31.0

**Verdict: Blocked — insufficient info**

## Breaking changes

| Change | Source | Impact |
|--------|--------|--------|
| Unknown — no changelog supplied | — | Cannot assess without `changelog_text` |

## Transitive dependencies

| Package | Current pin | New pin/range | Conflict / new CVE |
|---------|-------------|-----------------|----------------------|
| Unknown — no manifest/lockfile excerpt supplied | — | — | — |

## Notes

Two required checks could not run: breaking-change/API-difference analysis (no `changelog_text`) and
transitive-dependency impact (no `manifest_excerpt`). Verdict reflects the evidence gap, not a clean pass.
```

### Scenario: Degraded path — evidence gap on a single check

**Caller:** "Bump `openssl` from `1.1.1t` to `3.0.9`" with changelog text supplied but no manifest
excerpt.

**Agent:**
1. Inputs — resolves the triple and `changelog_text`; notes `manifest_excerpt` absent.
2. Analyze — breaking changes/API differences run fully from changelog text: several API/build-flag
   changes documented, each with a stated migration path. CVEs: one CVE affecting `1.1.1t`, fixed in
   `3.0.x`. Transitive impact: cannot be checked → recorded Unknown, not assumed clean. Rollout risk:
   major version, staged rollout recommended.
3. Report — no proven blocker, one evidence gap (transitive check), findings otherwise mitigated →
   `Blocked — insufficient info` wins over `Upgrade with mitigations` per precedence, since the gap is
   unresolved.

**Expected fragment:**

```markdown
## Transitive dependencies

| Package | Current pin | New pin/range | Conflict / new CVE |
|---------|-------------|-----------------|----------------------|
| Unknown — no manifest/lockfile excerpt supplied | — | — | — |

**Verdict: Blocked — insufficient info** — breaking changes and CVEs were both fully assessed and
mitigated, but the transitive-dependency check could not run without a manifest/lockfile excerpt.
```

### Scenario: Cross-skill handoff

**Caller:** "Review upgrading `jackson-databind` from `2.9.0` to `2.15.0`" with changelog and manifest
text; the changelog describes a known deserialization CVE affecting `2.9.0`, and the caller adds "we use
`ObjectMapper.readValue` on request bodies in three services — is this actually exploitable for us?"

**Agent:**
1. Inputs — resolves the triple plus both optional fields.
2. Analyze — CVEs: the deserialization CVE affecting `2.9.0`, fixed in `2.15.0`. Breaking changes/API
   differences: minor, all mitigated. Transitive impact: no conflicts. Rollout risk: reversible.
3. Report — CVE is resolved by the upgrade itself, no other blocker → `Safe to upgrade`, but the caller's
   question about actual exploitability in their own request-handling code is outside this skill's scope
   (it reviews the version bump, not the codebase's usage of the library) → offer the escalation.

**Expected fragment:**

```markdown
**Verdict: Safe to upgrade**

## CVEs

| CVE | Affects | Fixed in | Severity |
|-----|---------|----------|----------|
| `CVE-2019-12384` | `2.9.0` | `2.15.0` | Critical |

This CVE is resolved by the upgrade. Whether it was actually exploitable in your own
`ObjectMapper.readValue` call sites before this upgrade is outside this skill's scope — run
**security-review** if you need that codebase-usage assessment.
```
