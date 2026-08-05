# ai-skills roadmap: repo hygiene + incident-rca causal-graph determinism

**Date:** 2026-07-02
**Status:** Approved design
**Scope decision:** Approach A — hygiene sprint first (MR 1), then capability project (MR 2). Review
covered the 4 main skills only (pr-review, k8s-overprovisioning-datadog, incident-rca,
domain-comprehension); vendored kubesense skills out of scope. Ranking lenses: correctness, new
capabilities, team adoption/DX.

## Review findings (context)

### P0 — correctness / hygiene

1. **domain-comprehension invisible in docs.** Zero mentions in root `README.md` and `docs/README.md`:
   no Skills-table row, no install-target documentation, no lint-table row, no MCP-config row. The
   Makefile (`install-domain-comprehension`, `lint-domain-comprehension`) and `scripts/install.sh`
   (generic `*/SKILL.md` glob) already handle it — documentation only is stale.
2. **In-flight work uncommitted; branch name misleading.** Branch
   `feat/incident-rca-deterministic-output` describes work already merged on 2026-07-01 (see
   incident-rca CHANGELOG "deterministic executive RCA output"). The actual uncommitted diff is
   domain-comprehension workflow v1.3: `COMPLIANCE_RETROFIT` delivery mode, `manifest.yaml` in allowed
   writes, `E2E_FLOW.md` deliverable, `templates/domain-config.yaml`, validator `--check-content` flag.
   All lint and tests pass with the diff applied.
3. **Dev-setup friction.** `make lint` fails with per-file "PyYAML is required" / "pytest not installed"
   messages when Python dev deps are absent. `requirements.txt` exists but is not referenced by README
   or any Makefile target.
4. **README lint table stale.** Root README documents 3 lint targets; `make lint` runs 5
   (missing `lint-framework`, `lint-domain-comprehension`).

### P1 — capability gap

5. **incident-rca determinism lags k8s v3.** k8s-overprovisioning has a typed decision graph,
   INV-01–INV-11 machine-validated invariants, and renderers. incident-rca has an evidence JSON schema
   (v4) with a validator, but its causal graph, acyclicity rule, hypothesis-score arithmetic, and
   confidence caps are prose-only rules in SKILL.md / evidence-quality.md — nothing machine-checks them.

### P2 — deferred (recorded, not designed here)

- Confidence-semantics convergence audit across skills against `confidence-bands.md`.
- Scripted smoke/pressure tests (currently prose-only).
- `skills-lock.json`-style pinning for skills other than incident-rca.
- pr-review feedback-learning persistence across sessions.
- Shared deterministic-artifact framework extraction (Approach B) — revisit after MR 2 proves the
  pattern twice.

## MR 1 — repo hygiene

1. **Commit the in-flight domain-comprehension v1.3 diff** (14 modified files + new
   `templates/domain-config.yaml`) as
   `feat(domain-comprehension): compliance retrofit mode + manifest writes`. Commit on the current
   branch; the MR title/description states the real content (branch rename optional, not required).
2. **Root README.md** — add domain-comprehension to: Skills table (invoke phrase, what it does, docs
   links), single-skill install list, lint-target table (also add `lint-framework` and
   `lint-domain-comprehension` rows), and the Configure MCP table (optional GitLab + Datadog).
   Add a short Usage section consistent with the other three skills.
3. **docs/README.md** — add a domain-comprehension section: file map, invocation, cross-skill routing.
4. **`make setup` target** — installs `requirements.txt` (documenting the
   `--user --break-system-packages` fallback for externally-managed Python) and chains `setup-hooks`.
   README Develop section leads with `make setup`.

**Acceptance:** `make lint` green from a clean checkout after `make setup`; no dangling anchors; every
skill appears in both READMEs.

## MR 2 — incident-rca causal-graph determinism

Mirrors the k8s v3 pattern (schema → invariants → validated render) without extracting a shared
framework.

1. **`reference/causal-graph-schema.md`** — typed node kinds (`event`, `trigger`, `root_cause`,
   `contributing`, `systemic`), edges carrying evidence-ID references that resolve into the existing
   evidence JSON. Companion `reference/causal-graph.example.yaml`.
2. **`scripts/validate_causal_graph.py`** — machine-checks the existing prose rules:
   - graph is acyclic;
   - every edge cites an evidence ID present in the evidence JSON;
   - hypothesis scores recompute from the normative formula and match the recorded values;
   - confidence caps enforced: single signal source → max MEDIUM, unresolved contradiction → max
     MEDIUM, missing trigger → max LOW;
   - when all hypotheses ≤ MEDIUM after caps, conclusion must be "No defensible root cause" (no
     primary);
   - trigger Unknown with root cause Unknown is valid, not an error.
3. **Workflow integration** — Phase 4 emits the causal-graph artifact alongside evidence JSON; Phase 5
   render checklist requires a passing validator verdict before the report is produced.
4. **Lint + tests** — `lint-incident-rca` validates the example graph; pytest cases per invariant
   (cycle, dangling evidence ref, score mismatch, cap violation, all-MEDIUM-no-primary).

**Not in scope:** k8s-style `render/` split, correlator-CLI changes, shared framework extraction.

**Acceptance:** validator green on example graph; each invariant has a failing-fixture test; `make lint`
green; phase files reference the new artifacts with no dangling anchors.
