# Finding gates (steps 3, 4, 6)

**Single load in Phase 2** — replaces separate `dont-guess-gate.md`, `false-positive-suppression.md`, and
`non-negotiable-checks.md`. Apply in pipeline order per [finding-pipeline.md](finding-pipeline.md).

---

## Don't-guess gate (pipeline step 3)

Distinct from the execution path gate (step 4).

Before asserting a defect, ask:

> **Do I have sufficient evidence from the diff (+ Phase 1 full-file context) — without inferring
> unseen implementation, callers, or runtime state?**

| Answer | Action |
|--------|--------|
| **YES** | Continue to execution path gate |
| **NO** | **Do not infer.** Suppress finding; optionally note once in chat or Notes as unverifiable |

### YES — sufficient evidence

- The changed line **is** the defect (wrong operator, removed check, secret literal, SQL concat with user input).
- Full-file context from Phase 1 shows the call pattern **in the same file** supporting the claim.
- Acceptance criterion gap with **explicit** AC text and no implementing line in boundary.
- Test assertion contradicts stated behavior **in the diff**.

### NO — insufficient evidence (suppress or unverifiable)

- *"This probably doesn't handle edge case X"* with no changed line demonstrating the gap.
- *"Callers might pass nil"* when callers are not in boundary and not in Phase 1 full-file read.
- *"Missing index"* with no query/SQL change and no perf evidence in diff.
- *"Race condition"* with no shared mutable state in changed hunk or visible file context.
- Behavior claims about **unchanged** files not read in Phase 1.

**Unverifiable (chat / Notes only):**

> ⚠️ **Unverifiable:** `<one line>` — insufficient diff evidence; manual check recommended.

**Never** assign L/I/Overall or post inline for unverifiable items.

Increment `review_metrics.suppressed.guess` for each suppressed candidate.

---

## Execution path gate (pipeline step 4)

Before adding a row to the findings table or posting a comment, ask:

> **Can I construct a realistic execution path where this defect occurs?**

| Answer | Action |
|--------|--------|
| **YES** | Emit the finding (with L/I, context, fix). Briefly state the path when non-obvious. |
| **NO** | **Suppress** — do not emit, do not post. Optional one-line chat note only. |

**Realistic** means: a normal caller/user input, feature flag state, or deploy path that would actually
reach this code in production — supported by the **diff + Phase 1 full-file context**, not invented
callers or impossible state.

### YES — emit (examples)

- New handler accepts webhook body without signature check — **any** POST reaches the defect.
- Removed null check on a field that callers pass from request JSON.
- Migration adds `NOT NULL` without default — **deploy** path runs migration on next release.
- Missing timeout on HTTP client used synchronously in the changed hot path.

### NO — suppress (examples)

- *"What if `user` is nil?"* when every call site guards `user != nil`.
- Speculative concurrency bug with no shared mutable state in the changed hunk.
- Missing auth when profile restriction is confirmed in the same diff (`@Profile("dev")` only).
- Missing auth when profile is **not** in diff — **do not suppress**; emit with OAR and Confidence **Medium**.

When suppressing, do **not** downgrade to Low/nit — **suppress entirely**.

Increment `review_metrics.suppressed.path` for each suppressed candidate.

### Path gate waived (observable hard floors)

| Exception | Why |
|-----------|-----|
| **Secret/credential** in diff | Material regardless of path |
| **Injection / auth bypass** on untrusted input in changed hunk | Attacker-controlled path assumed |
| **Unmet acceptance criterion** with evidence in diff | AC gate |
| **Breaking public API/schema change** visible in diff | Consumers will hit it |
| **Clear logic error** on changed lines | Executes whenever the branch runs |

Still require diff anchor (step 2) and dedupe (step 5).

---

## Non-negotiable checks (pipeline step 6)

Always run on applicable changed content — regardless of fast path, persona, or feedback learning.

| Check | Trigger | Notes |
|-------|---------|-------|
| **Secrets / credentials** | Literal keys, tokens, passwords, private keys in diff | Critical; never echo value |
| **Authentication changes** | New/changed auth middleware, session, token validation | Even on docs-only if auth code in boundary |
| **Authorization changes** | Permission checks, RBAC, policy gates added/removed/weakened | |
| **Injection** | SQL/NoSQL/command/HTML injection on untrusted input in changed hunk | |
| **Unsafe deserialization** | `pickle`, `yaml.load`, `ObjectInputStream`, eval on external data | |
| **Unmet acceptance criteria** | Linked Jira AC with ❌ Gap in Phase 1 table | High floor |
| **Breaking public API/schema** | Visible contract break without compat in diff | Critical floor |
| **New dependency CVE** | New package/version with known Critical/High CVE | **Systematic order:** (1) CI/Snyk/GitLab dependency scan on head pipeline when present; (2) **Snyk MCP** (`plugin-snyk-secure-development-Snyk`) package or manifest scan when MCP ✅ and lockfile/manifest in diff; (3) **OSV** lookup for new coordinates when Snyk unavailable; (4) record *"CVE scan not run — no CI/Snyk/OSV"* in Phase 5 when all absent. Never approve manifest bumps without one path attempted. |

**Fast path:** may skip checklist dimensions (§4, §8, §9, §16, §17); **may not** skip this table when
triggers match. Docs-only MRs still scan for secrets in changed text.

**Feedback learning:** **Never suppress** non-negotiable categories.

Non-negotiable matches **waive** guess and path gates when the defect is **observable on the changed
line**. **Do not waive** diff anchor (step 2) or dedupe (step 5).

When stop-search fires, **still complete** non-negotiable checks on the **current hunk** before stopping
new file/dimension scans.
