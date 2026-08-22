# Skills Roadmap Implementation Plan (MR 1 hygiene + MR 2 incident-rca causal graph)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship two MRs: (1) repo hygiene — commit in-flight domain-comprehension v1.3 work and surface domain-comprehension in all documentation plus a `make setup` target; (2) incident-rca causal-graph determinism — a typed `causal_graph` YAML artifact, a Python invariant validator (CG-01…CG-08), workflow integration, and lint/test wiring.

**Architecture:** MR 1 is documentation + Makefile only (no skill-behavior change). MR 2 mirrors the k8s-overprovisioning v3 pattern (typed schema → machine-validated invariants → render gate) inside incident-rca, without extracting a shared framework. The validator cross-references the causal graph against the existing evidence bundle JSON (`schema_version: 4`) using `field[index]` references, so the evidence schema itself does not change.

**Tech Stack:** Markdown skill files, GNU Make, Python 3 (stdlib + PyYAML), pytest.

**Spec:** `docs/superpowers/specs/2026-07-02-skills-roadmap-design.md`

## Global Constraints

- `incident-rca/SKILL.md` must stay ≤ 180 lines (`lint-incident-rca` enforces).
- Every `incident-rca/workflow/*.md` must keep `workflow_version` frontmatter.
- No dangling markdown anchors — `make lint` anchor checks run on every `*.md` under each skill dir.
- Python scripts: stdlib + PyYAML only (already in `requirements.txt`); match the style of `incident-rca/scripts/validate_evidence_json.py` (pure functions returning `list[str]` errors, CLI `main(argv)` returning exit code).
- Tests: pytest, import via `sys.path.insert(0, str(ROOT / "scripts"))` like `incident-rca/tests/test_validate_evidence.py`.
- Commit messages end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Working branch: current `feat/incident-rca-deterministic-output` for MR 1 (Task 1–4). MR 2 (Task 5–8) goes on a new branch `feat/incident-rca-causal-graph-validator` cut from master after MR 1 merges (or from the MR 1 head if stacking).
- After every task: `make lint` must pass.

---

## Part 1 — MR 1: repo hygiene

### Task 1: Commit in-flight domain-comprehension v1.3 work

**Files:**
- No edits — commit the existing uncommitted diff (14 modified files under `domain-comprehension/` + untracked `domain-comprehension/templates/domain-config.yaml`).

**Interfaces:**
- Produces: clean working tree so later doc tasks commit in isolation.

- [ ] **Step 1: Verify lint passes with the diff applied**

Run: `make lint`
Expected: all targets end `ok`; pytest suites pass (23 + 13 tests). If lint fails, STOP and report — do not commit.

- [ ] **Step 2: Verify the diff is only domain-comprehension**

Run: `git status --short`
Expected: only `domain-comprehension/…` paths (14 `M` + 1 `??`). Anything else: STOP and report.

- [ ] **Step 3: Commit**

```bash
git add domain-comprehension/
git commit -m "feat(domain-comprehension): compliance retrofit mode, manifest writes, E2E_FLOW deliverable

Workflow v1.3: COMPLIANCE_RETROFIT delivery mode, manifest.yaml in allowed
writes (every phase), E2E_FLOW.md optional P2 supplement, domain-config.yaml
template, validator --check-content flag.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

Run: `git status --short` → empty output.

### Task 2: Add domain-comprehension to root README.md

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: existing README section layout (Skills table at ~line 17, install at ~25, lint at ~61, MCP at ~85, Usage sections at ~95+).

- [ ] **Step 1: Add Skills-table row**

In the `## Skills` table, after the `incident-rca` row, add:

```markdown
| [domain-comprehension](domain-comprehension/) | "map the domain …", "bounded contexts for …" | Evidence-backed domain map: bounded contexts, data ownership, dependency graphs, business flows, exec summary | [README](domain-comprehension/README.md) · [SETUP](domain-comprehension/SETUP.md) |
```

- [ ] **Step 2: Add install lines**

In the "Install a single skill" code block, after `make install-incident-rca`, add:

```bash
make install-domain-comprehension
```

In the "Or run the script directly" code block, after the `incident-rca` line, add:

```bash
bash scripts/install.sh domain-comprehension
```

- [ ] **Step 3: Update lint block and table**

In the "Run lint manually" code block, after the `make lint-incident-rca` line, add:

```bash
make lint-domain-comprehension  # domain-comprehension SKILL line limit, frontmatter, anchors, manifest validator
```

In the lint-target table (currently 3 rows), add two rows:

```markdown
| `lint-framework` | shared `docs/skill-framework/` docs present; required sections; SETUP.md links; metadata footer examples parse |
| `lint-domain-comprehension` | `SKILL.md` ≤ 180 lines; workflow frontmatter; dangling anchors; `templates/manifest.yaml` validator + pytest |
```

- [ ] **Step 4: Add MCP-config row**

In the `## Configure MCP` table, after the `incident-rca` row, add:

```markdown
| domain-comprehension | GitLab (optional, Session 0b squads), Datadog (optional, P2b runtime validation) | [domain-comprehension/SETUP.md](domain-comprehension/SETUP.md) |
```

- [ ] **Step 5: Add Usage section**

After the `## Usage (incident-rca)` section (end of file), add:

````markdown
---

## Usage (domain-comprehension)

Attach the skill or ask in natural language. Needs a workspace with source code and the
`understand-anything` toolchain (Node ≥ 22); GitLab and Datadog MCP are optional enrichments
(see [domain-comprehension/SETUP.md](domain-comprehension/SETUP.md)).

### Examples

| You say | What happens |
|---------|----------------|
| `Map the lending domain across these repos` | Full comprehension run: Session 0 → P0…P5, evidence-backed deliverables |
| `What are the bounded contexts and who owns the data?` | `BOUNDED_CONTEXTS.md` + `DATA_OWNERSHIP.md` with per-conclusion evidence and confidence |
| `Resume the domain comprehension` | Reads `manifest.yaml` and continues from the last incomplete phase |

### What you get (domain-comprehension)

- `EXEC_SUMMARY.md` — five questions answered with overall confidence
- Bounded contexts, data ownership, dependency graph (4 architecture views), business flows, state machines
- `RISK_MAP.md` (top architecture smells), `UNKNOWNS.md` / `KNOWN_OMISSIONS.md` (no speculation)
- `manifest.yaml` — machine-readable completion state for deterministic resume
````

- [ ] **Step 6: Lint and commit**

Run: `make lint` → green.

```bash
git add README.md
git commit -m "docs: add domain-comprehension to root README (skills, install, lint, MCP, usage)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

### Task 3: Add domain-comprehension to docs/README.md and docs/REPOSITORY.md

**Files:**
- Modify: `docs/README.md`
- Modify: `docs/REPOSITORY.md`

- [ ] **Step 1: docs/README.md — skills table + one-line summary**

In the `## Skills (what each one does)` table, add after the `k8s-overprovisioning-datadog` row:

```markdown
| **domain-comprehension** | [domain-comprehension/README.md](../domain-comprehension/README.md) | [domain-comprehension/SKILL.md](../domain-comprehension/SKILL.md) | [domain-comprehension/SETUP.md](../domain-comprehension/SETUP.md) |
```

In the `### One-line summary` table, add:

```markdown
| **domain-comprehension** | Natural language ("map the domain …") | Evidence-backed domain comprehension across repos: bounded contexts, data ownership, dependency graphs, business flows, exec summary with confidence |
```

- [ ] **Step 2: docs/README.md — cross-skill routing rows**

In the `## Cross-skill routing` table, add:

```markdown
| domain-comprehension | Incident / outage in a time window | incident-rca |
| domain-comprehension | "Review this MR" | pr-review |
| incident-rca / pr-review | "How does this domain work?" / onboarding | domain-comprehension |
```

- [ ] **Step 3: docs/README.md — domain-comprehension file map**

After the `## incident-rca file map` section, add:

```markdown
## domain-comprehension file map

| Path | What it does |
|------|--------------|
| `workflow/inputs.md` | Delivery mode (`FULL` / `RESUME` / `DELTA` / `COMPLIANCE_RETROFIT`), parameter intake |
| `workflow/session-0.md` … `phase-5.md` | Session 0 → P0…P5 comprehension phases, one file per phase |
| `reference/phase-outputs.md` | Mandatory artifacts per phase |
| `reference/phase-completion-gate.md` | Coverage report + completion gate after every phase |
| `reference/manifest-schema.md` | `manifest.yaml` machine-readable state schema |
| `reference/evidence-precedence.md` | Runtime → code → config → tests evidence ordering |
| `templates/manifest.yaml`, `templates/domain-config.yaml` | Starter templates |
| `scripts/validate_manifest_yaml.py` | Manifest validator (`--check-content`) |
| `tests/test_validate_manifest.py` | Pytest suite for the validator |
```

- [ ] **Step 4: docs/README.md — fix stale schema note + register spec**

In the incident-rca file map, the `reference/evidence.example.json` row says `schema_version: 3` — change to `schema_version: 4`.

In the `## Design specs (internal)` table, add:

```markdown
| [superpowers/specs/2026-07-02-skills-roadmap-design.md](superpowers/specs/2026-07-02-skills-roadmap-design.md) | Repo hygiene + incident-rca causal-graph determinism roadmap |
```

- [ ] **Step 5: docs/REPOSITORY.md — lint rows**

In the lint-target table (~line 70), add after the `make lint-incident-rca` row:

```markdown
| `make lint-domain-comprehension` | domain-comprehension `SKILL.md` ≤ 180 lines; workflow frontmatter; dangling anchors; `templates/manifest.yaml` validator + pytest |
| `make lint-framework` | shared `docs/skill-framework/` files present; required sections; SETUP.md links; metadata footer examples parse |
```

Then read the `### lint-incident-rca` / `### lint-pr-review` subsection format in the same file and add a matching `### lint-domain-comprehension` subsection describing: SKILL line count, workflow frontmatter, anchors, manifest validator + pytest.

- [ ] **Step 6: Lint and commit**

Run: `make lint` → green (anchor check validates all new links).

```bash
git add docs/README.md docs/REPOSITORY.md
git commit -m "docs: index domain-comprehension in docs/README and REPOSITORY; fix stale evidence schema note

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

### Task 4: `make setup` target + Develop docs + changelog

**Files:**
- Modify: `Makefile` (`.PHONY` line 1; new target after `install-domain-comprehension`)
- Modify: `README.md` (Develop section)
- Modify: `CHANGELOG.md` (Repository section)

- [ ] **Step 1: Add setup target**

In `Makefile`, append ` setup` to the `.PHONY` list, and add after the `install-domain-comprehension` target:

```make
setup:
	@echo "setup: installing Python dev dependencies (requirements.txt)"
	@python3 -m pip install -r requirements.txt 2>/dev/null || \
		python3 -m pip install --user --break-system-packages -r requirements.txt
	@$(MAKE) setup-hooks
```

(Tab indentation, not spaces — Make requires it.)

- [ ] **Step 2: Verify target runs**

Run: `make setup`
Expected: pip installs (or confirms) `pytest` + `PyYAML`, then the existing `setup-hooks` output. Then `make lint` → green.

- [ ] **Step 3: Update README Develop section**

Replace the Develop section intro ("One-time setup to run shellcheck before each commit:" + `make setup-hooks` block) with:

````markdown
One-time setup — installs Python dev deps (`requirements.txt`: pytest, PyYAML) and the shellcheck pre-commit hook:

```bash
make setup
```
````

Keep the rest of the section (lint instructions) unchanged; drop the trailing sentence "For `diff-to-positions.py` tests, install pytest: `python3 -m pip install pytest`." since `make setup` now covers it.

- [ ] **Step 4: CHANGELOG entry**

In `CHANGELOG.md` under `## Repository`, add a new subsection above "Documentation index":

```markdown
### Repo hygiene (2026-07-02)

- domain-comprehension added to root [README.md](README.md) (skills table, install, lint, MCP, usage) and
  [docs/README.md](docs/README.md) (skills index, routing, file map).
- `make setup` — installs `requirements.txt` dev deps + git hooks.
- Fixed stale `schema_version: 3` note for `evidence.example.json` in docs/README.md.
```

- [ ] **Step 5: Lint and commit**

Run: `make lint` → green.

```bash
git add Makefile README.md CHANGELOG.md
git commit -m "build: add make setup for dev deps; document it in README

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

MR 1 complete — open the merge request for this branch.

---

## Part 2 — MR 2: incident-rca causal-graph determinism

> Branch: `feat/incident-rca-causal-graph-validator` (from master after MR 1 merges, or stacked).

### Task 5: Causal-graph schema + example artifact

**Files:**
- Create: `incident-rca/reference/causal-graph-schema.md`
- Create: `incident-rca/reference/causal-graph.example.yaml`

**Interfaces:**
- Produces: `causal_graph` YAML shape (`schema_version: 1`) consumed by the Task 6 validator and the Task 8 workflow edits. Evidence refs use `field[index]` into the evidence bundle JSON.

- [ ] **Step 1: Write the schema doc**

Create `incident-rca/reference/causal-graph-schema.md`:

````markdown
# Causal graph artifact (schema_version 1)

Machine-checkable form of the report's **Causal graph** section. Phase 4 writes
`rca_causal_graph.yaml` next to the evidence bundle; Phase 5 must not render until
[validate_causal_graph.py](../scripts/validate_causal_graph.py) passes. Prose rules it enforces live in
[evidence-quality.md](evidence-quality.md) (§Causal graph rules, §Hypothesis score algorithm,
§Confidence caps, §Insufficient evidence).

## Top-level fields (all required)

| Field | Type | Meaning |
|-------|------|---------|
| `schema_version` | int | `1` |
| `service` | string | Investigated service (matches evidence bundle) |
| `window` | object | `from_time` / `to_time` (matches evidence bundle) |
| `trigger_status` | enum | `identified` \| `unknown` |
| `observability_sources_responded` | int | Count of independent observability sources that returned data (Datadog, KubeSense, …) |
| `nodes` | list | Causal graph nodes |
| `edges` | list | Directed cause → effect edges |
| `hypotheses` | list | Ranked hypotheses with scoring arithmetic |
| `conclusion` | object | `primary` (hypothesis id or `"none"`) + `statement` |

## Nodes

| Field | Type | Meaning |
|-------|------|---------|
| `id` | string | Unique within the graph |
| `kind` | enum | `event` \| `trigger` \| `root_cause` \| `contributing` \| `systemic` |
| `label` | string | One-line description; customer-visible symptoms are `event` nodes at the bottom of the chain |

## Edges

Directed **cause → effect**. Feedback loops stay in report prose — the graph must be acyclic.

| Field | Type | Meaning |
|-------|------|---------|
| `from` / `to` | string | Node ids |
| `evidence` | list of string | ≥1 reference into the evidence bundle: `<list_field>[<index>]`, e.g. `error_signals[0]`, `deploy_events[0]`. Valid list fields: `error_signals`, `deploy_events`, `jira_issues`, `infra_signals`, `known_issue_matches`, `evidence_links`, `query_signals`, `recurrence_history` |

## Hypotheses

Mirror the Ranked hypotheses table; the validator recomputes the arithmetic from
[evidence-quality.md](evidence-quality.md) §Hypothesis score algorithm.

| Field | Type | Meaning |
|-------|------|---------|
| `id` | string | `H1`, `H2`, … |
| `type` | string | Hypothesis type from [evidence-schema.md](evidence-schema.md) |
| `base` | number | Sum of matched signal weights ([manual-scoring.md](manual-scoring.md)) |
| `quality_bonus` | number | ≤ 15 |
| `source_bonus` | number | `0` or `10` |
| `counter_penalty` | number | `10 ×` unresolved contradicting signals (≥ 0) |
| `gap_penalty` | number | `0` or `15` |
| `adjusted` | number | `max(0, base + quality_bonus + source_bonus − counter_penalty − gap_penalty)` |
| `display_score` | int | `round(adjusted / Σ adjusted × 100)`, half-up; `0` when Σ = 0 |
| `band` | enum | `HIGH` \| `MEDIUM` \| `LOW` \| `UNKNOWN` — after confidence caps |
| `unresolved_contradictions` | int | Count feeding `counter_penalty` and the MEDIUM cap |
| `supporting_quality` | list | Evidence-quality labels of supporting signals (`Observed` / `Correlated` / `Inferred` / `Assumed`) |
| `ruled_out` | bool | True iff `adjusted < 0.5 × max(adjusted)` |

## Invariants (validator)

| ID | Check |
|----|-------|
| CG-01 | Graph is acyclic |
| CG-02 | Node ids unique; kinds valid; edge endpoints exist |
| CG-03 | Every edge has ≥1 evidence ref; every ref resolves in the evidence bundle |
| CG-04 | `adjusted` matches the formula; `quality_bonus` ≤ 15 |
| CG-05 | `display_score` matches normalization (half-up rounding) |
| CG-06 | Band respects caps: sources < 2 → ≤ MEDIUM; contradictions > 0 → ≤ MEDIUM; all-Assumed support → ≤ LOW; `trigger_status: unknown` → ≤ MEDIUM; band never exceeds the score-implied band (75+ HIGH, 50–74 MEDIUM, 25–49 LOW, else UNKNOWN) |
| CG-07 | `conclusion.primary` is `"none"` unless some hypothesis band is HIGH; when set it names an existing HIGH hypothesis (see §Insufficient evidence — no best-guess primary) |
| CG-08 | `ruled_out` consistent with the 0.5 × primary rule |

Run: `python3 incident-rca/scripts/validate_causal_graph.py <graph.yaml> <evidence.json>`
````

- [ ] **Step 2: Write the example artifact**

Create `incident-rca/reference/causal-graph.example.yaml` (consistent with `evidence.example.json` — the MR !482 deploy-regression scenario):

```yaml
# Companion to evidence.example.json — validated by scripts/validate_causal_graph.py
schema_version: 1
service: neo-disbursement-service
window:
  from_time: "2026-06-28T14:00:00Z"
  to_time: "2026-06-28T16:00:00Z"
trigger_status: identified
observability_sources_responded: 2
nodes:
  - id: trigger_deploy
    kind: trigger
    label: "Production deploy build #1234 at 14:20 UTC (MR !482)"
  - id: root_cause_npe
    kind: root_cause
    label: "NullPointerException in TransferMoneyHandler introduced by MR !482 validation refactor"
  - id: event_5xx
    kind: event
    label: "5xx spike on transfer-money from 14:45 UTC (12% vs 0.3% baseline)"
edges:
  - from: trigger_deploy
    to: root_cause_npe
    evidence: ["deploy_events[0]"]
  - from: root_cause_npe
    to: event_5xx
    evidence: ["error_signals[0]", "evidence_links[0]"]
hypotheses:
  - id: H1
    type: deploy_regression
    base: 45
    quality_bonus: 7        # error_rate Observed (+5) + deploy Correlated (+2)
    source_bonus: 10        # deploy + error = 2 independent signal types
    counter_penalty: 0
    gap_penalty: 0          # diff on failing path confirmed
    adjusted: 62
    display_score: 86       # 62 / 72
    band: HIGH
    unresolved_contradictions: 0
    supporting_quality: [Observed, Correlated]
    ruled_out: false
  - id: H2
    type: infra_capacity
    base: 10
    quality_bonus: 0
    source_bonus: 0
    counter_penalty: 0
    gap_penalty: 0
    adjusted: 10
    display_score: 14       # 10 / 72
    band: UNKNOWN
    unresolved_contradictions: 0
    supporting_quality: []
    ruled_out: true         # 10 < 0.5 × 62
conclusion:
  primary: H1
  statement: >-
    MR !482 introduced an NPE on the transfer-money validation path; the 14:20 UTC
    production deploy caused the 14:45 5xx spike.
```

- [ ] **Step 3: Sanity-check YAML parses**

Run: `python3 -c "import yaml; yaml.safe_load(open('incident-rca/reference/causal-graph.example.yaml')); print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add incident-rca/reference/causal-graph-schema.md incident-rca/reference/causal-graph.example.yaml
git commit -m "feat(incident-rca): causal-graph artifact schema v1 + example

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

### Task 6: Causal-graph validator (TDD)

**Files:**
- Create: `incident-rca/tests/test_validate_causal_graph.py`
- Create: `incident-rca/scripts/validate_causal_graph.py`

**Interfaces:**
- Consumes: `causal-graph.example.yaml` + `evidence.example.json` (Task 5).
- Produces: `validate_causal_graph(graph: Any, evidence: Any) -> list[str]` (error strings prefixed `CG-0X:`) and CLI `main(argv) -> int` taking `<graph.yaml> <evidence.json>`. Task 7 lint and Task 8 workflow text depend on this CLI shape.

- [ ] **Step 1: Write the failing tests**

Create `incident-rca/tests/test_validate_causal_graph.py`:

```python
"""Tests for incident-rca causal graph validator (CG-01..CG-08)."""

import copy
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_causal_graph import validate_causal_graph  # noqa: E402

GRAPH_EXAMPLE = ROOT / "reference" / "causal-graph.example.yaml"
EVIDENCE_EXAMPLE = ROOT / "reference" / "evidence.example.json"


def load():
    graph = yaml.safe_load(GRAPH_EXAMPLE.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE_EXAMPLE.read_text(encoding="utf-8"))
    return graph, evidence


def test_example_graph_valid():
    graph, evidence = load()
    assert validate_causal_graph(graph, evidence) == []


def test_cg01_cycle_detected():
    graph, evidence = load()
    graph["edges"].append(
        {"from": "event_5xx", "to": "trigger_deploy", "evidence": ["error_signals[0]"]}
    )
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-01") for e in errors)


def test_cg02_unknown_node_kind():
    graph, evidence = load()
    graph["nodes"][0]["kind"] = "symptom"
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-02") for e in errors)


def test_cg02_edge_to_missing_node():
    graph, evidence = load()
    graph["edges"][0]["to"] = "nonexistent_node"
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-02") for e in errors)


def test_cg03_edge_without_evidence():
    graph, evidence = load()
    graph["edges"][0]["evidence"] = []
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-03") for e in errors)


def test_cg03_dangling_evidence_ref():
    graph, evidence = load()
    graph["edges"][0]["evidence"] = ["error_signals[5]"]
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-03") for e in errors)


def test_cg03_malformed_evidence_ref():
    graph, evidence = load()
    graph["edges"][0]["evidence"] = ["not a ref"]
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-03") for e in errors)


def test_cg04_arithmetic_mismatch():
    graph, evidence = load()
    graph["hypotheses"][0]["adjusted"] = 70  # should be 62
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-04") for e in errors)


def test_cg04_quality_bonus_over_cap():
    graph, evidence = load()
    h = graph["hypotheses"][0]
    h["quality_bonus"] = 20
    h["adjusted"] = 75  # keep arithmetic self-consistent so only the cap fires
    h["display_score"] = 88  # 75/85
    graph["hypotheses"][1]["display_score"] = 12  # 10/85
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-04") for e in errors)


def test_cg05_display_score_mismatch():
    graph, evidence = load()
    graph["hypotheses"][0]["display_score"] = 99  # should be 86
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-05") for e in errors)


def test_cg06_single_source_caps_medium():
    graph, evidence = load()
    graph["observability_sources_responded"] = 1
    errors = validate_causal_graph(graph, evidence)  # H1 still HIGH → violation
    assert any(e.startswith("CG-06") for e in errors)


def test_cg06_trigger_unknown_caps_medium():
    graph, evidence = load()
    graph["trigger_status"] = "unknown"
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-06") for e in errors)


def test_cg06_assumed_only_caps_low():
    graph, evidence = load()
    h = graph["hypotheses"][0]
    h["supporting_quality"] = ["Assumed"]
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-06") for e in errors)


def test_cg06_band_exceeds_score_band():
    graph, evidence = load()
    graph["hypotheses"][1]["band"] = "HIGH"  # display 14 → UNKNOWN band max
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-06") for e in errors)


def test_cg07_primary_requires_high_band():
    graph, evidence = load()
    graph["hypotheses"][0]["band"] = "MEDIUM"
    errors = validate_causal_graph(graph, evidence)  # primary still H1
    assert any(e.startswith("CG-07") for e in errors)


def test_cg07_no_high_requires_primary_none():
    graph, evidence = load()
    graph["hypotheses"][0]["band"] = "MEDIUM"
    graph["conclusion"]["primary"] = "none"
    errors = validate_causal_graph(graph, evidence)
    assert not any(e.startswith("CG-07") for e in errors)


def test_cg08_ruled_out_inconsistent():
    graph, evidence = load()
    graph["hypotheses"][1]["ruled_out"] = False  # 10 < 31 → must be ruled out
    errors = validate_causal_graph(graph, evidence)
    assert any(e.startswith("CG-08") for e in errors)


def test_missing_top_level_field():
    graph, evidence = load()
    del graph["trigger_status"]
    errors = validate_causal_graph(graph, evidence)
    assert any("trigger_status" in e for e in errors)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest incident-rca/tests/test_validate_causal_graph.py -q`
Expected: collection error — `ModuleNotFoundError: No module named 'validate_causal_graph'`

- [ ] **Step 3: Write the validator**

Create `incident-rca/scripts/validate_causal_graph.py`:

```python
#!/usr/bin/env python3
"""Validate incident-rca causal graph YAML (schema_version 1) against an evidence bundle.

Machine checks (CG-01..CG-08) for the prose rules in reference/evidence-quality.md:
acyclicity, evidence-backed edges, hypothesis score arithmetic, confidence caps,
and the no-best-guess-primary rule. Schema: reference/causal-graph-schema.md.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

NODE_KINDS = ("event", "trigger", "root_cause", "contributing", "systemic")
BAND_ORDER = {"UNKNOWN": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
EVIDENCE_LIST_FIELDS = (
    "error_signals",
    "deploy_events",
    "jira_issues",
    "infra_signals",
    "known_issue_matches",
    "evidence_links",
    "query_signals",
    "recurrence_history",
)
EVIDENCE_REF_RE = re.compile(r"^([a-z_]+)\[(\d+)\]$")

REQUIRED_TOP_LEVEL = (
    "schema_version",
    "service",
    "window",
    "trigger_status",
    "observability_sources_responded",
    "nodes",
    "edges",
    "hypotheses",
    "conclusion",
)

HYPOTHESIS_REQUIRED = (
    "id",
    "type",
    "base",
    "quality_bonus",
    "source_bonus",
    "counter_penalty",
    "gap_penalty",
    "adjusted",
    "display_score",
    "band",
    "unresolved_contradictions",
    "supporting_quality",
    "ruled_out",
)


def _score_band(display_score: int) -> str:
    if display_score >= 75:
        return "HIGH"
    if display_score >= 50:
        return "MEDIUM"
    if display_score >= 25:
        return "LOW"
    return "UNKNOWN"


def _display_score(adjusted: float, total: float) -> int:
    if total <= 0:
        return 0
    value = adjusted / total * 100
    return max(0, min(100, int(value + 0.5)))


def _check_structure(graph: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(graph, dict):
        return ["root must be a mapping"]
    for key in REQUIRED_TOP_LEVEL:
        if key not in graph:
            errors.append(f"missing required field: {key}")
    if graph.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if graph.get("trigger_status") not in ("identified", "unknown"):
        errors.append("trigger_status must be 'identified' or 'unknown'")
    for key in ("nodes", "edges", "hypotheses"):
        if key in graph and not isinstance(graph.get(key), list):
            errors.append(f"{key} must be a list")
    if "conclusion" in graph and not isinstance(graph.get("conclusion"), dict):
        errors.append("conclusion must be a mapping")
    for index, hyp in enumerate(graph.get("hypotheses") or []):
        if not isinstance(hyp, dict):
            errors.append(f"hypotheses[{index}] must be a mapping")
            continue
        for key in HYPOTHESIS_REQUIRED:
            if key not in hyp:
                errors.append(f"hypotheses[{index}] missing required field: {key}")
    return errors


def _check_nodes_edges(graph: dict) -> list[str]:
    errors: list[str] = []
    nodes = graph.get("nodes") or []
    node_ids: list[str] = []
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            errors.append(f"CG-02: nodes[{index}] must be a mapping")
            continue
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            errors.append(f"CG-02: nodes[{index}] missing id")
            continue
        if node_id in node_ids:
            errors.append(f"CG-02: duplicate node id: {node_id}")
        node_ids.append(node_id)
        if node.get("kind") not in NODE_KINDS:
            errors.append(f"CG-02: node {node_id} has invalid kind: {node.get('kind')!r}")
    known = set(node_ids)
    for index, edge in enumerate(graph.get("edges") or []):
        if not isinstance(edge, dict):
            errors.append(f"CG-02: edges[{index}] must be a mapping")
            continue
        for endpoint in ("from", "to"):
            if edge.get(endpoint) not in known:
                errors.append(
                    f"CG-02: edges[{index}].{endpoint} references unknown node: {edge.get(endpoint)!r}"
                )
    return errors


def _check_acyclic(graph: dict) -> list[str]:
    adjacency: dict[str, list[str]] = {}
    for edge in graph.get("edges") or []:
        if isinstance(edge, dict):
            adjacency.setdefault(str(edge.get("from")), []).append(str(edge.get("to")))
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {}

    def visit(node: str) -> bool:
        color[node] = GRAY
        for nxt in adjacency.get(node, []):
            state = color.get(nxt, WHITE)
            if state == GRAY:
                return True
            if state == WHITE and visit(nxt):
                return True
        color[node] = BLACK
        return False

    for start in list(adjacency):
        if color.get(start, WHITE) == WHITE and visit(start):
            return ["CG-01: causal graph contains a cycle — feedback loops belong in prose"]
    return []


def _check_edge_evidence(graph: dict, evidence: Any) -> list[str]:
    errors: list[str] = []
    evidence = evidence if isinstance(evidence, dict) else {}
    for index, edge in enumerate(graph.get("edges") or []):
        if not isinstance(edge, dict):
            continue
        refs = edge.get("evidence")
        if not isinstance(refs, list) or not refs:
            errors.append(f"CG-03: edges[{index}] must cite at least one evidence ref")
            continue
        for ref in refs:
            match = EVIDENCE_REF_RE.match(ref) if isinstance(ref, str) else None
            if not match:
                errors.append(f"CG-03: edges[{index}] malformed evidence ref: {ref!r}")
                continue
            field, pos = match.group(1), int(match.group(2))
            if field not in EVIDENCE_LIST_FIELDS:
                errors.append(f"CG-03: edges[{index}] unknown evidence field: {field}")
                continue
            entries = evidence.get(field)
            if not isinstance(entries, list) or pos >= len(entries):
                errors.append(
                    f"CG-03: edges[{index}] evidence ref does not resolve: {field}[{pos}]"
                )
    return errors


def _check_hypotheses(graph: dict) -> list[str]:
    errors: list[str] = []
    hypotheses = [h for h in (graph.get("hypotheses") or []) if isinstance(h, dict)]
    numeric_ok: list[dict] = []
    for hyp in hypotheses:
        hid = hyp.get("id", "?")
        try:
            base = float(hyp["base"])
            quality_bonus = float(hyp["quality_bonus"])
            source_bonus = float(hyp["source_bonus"])
            counter_penalty = float(hyp["counter_penalty"])
            gap_penalty = float(hyp["gap_penalty"])
            adjusted = float(hyp["adjusted"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"CG-04: hypothesis {hid} has missing or non-numeric score fields")
            continue
        if quality_bonus > 15:
            errors.append(f"CG-04: hypothesis {hid} quality_bonus {quality_bonus} exceeds cap 15")
        expected = max(
            0.0, base + quality_bonus + source_bonus - counter_penalty - gap_penalty
        )
        if abs(adjusted - expected) > 1e-6:
            errors.append(
                f"CG-04: hypothesis {hid} adjusted {adjusted} != expected {expected}"
            )
        numeric_ok.append(hyp)

    total = sum(float(h["adjusted"]) for h in numeric_ok)
    max_adjusted = max((float(h["adjusted"]) for h in numeric_ok), default=0.0)

    sources = graph.get("observability_sources_responded")
    trigger_unknown = graph.get("trigger_status") == "unknown"

    for hyp in numeric_ok:
        hid = hyp.get("id", "?")
        expected_display = _display_score(float(hyp["adjusted"]), total)
        if hyp.get("display_score") != expected_display:
            errors.append(
                f"CG-05: hypothesis {hid} display_score {hyp.get('display_score')} "
                f"!= expected {expected_display}"
            )
        band = hyp.get("band")
        if band not in BAND_ORDER:
            errors.append(f"CG-06: hypothesis {hid} invalid band: {band!r}")
            continue
        caps: list[tuple[str, str]] = []
        if isinstance(sources, int) and sources < 2:
            caps.append(("MEDIUM", "single observability source"))
        if int(hyp.get("unresolved_contradictions") or 0) > 0:
            caps.append(("MEDIUM", "unresolved contradictions"))
        if trigger_unknown:
            caps.append(("MEDIUM", "trigger unknown"))
        quality = hyp.get("supporting_quality") or []
        if quality and all(q == "Assumed" for q in quality):
            caps.append(("LOW", "Assumed-only support"))
        caps.append((_score_band(expected_display), "score band"))
        for cap_band, reason in caps:
            if BAND_ORDER[band] > BAND_ORDER[cap_band]:
                errors.append(
                    f"CG-06: hypothesis {hid} band {band} exceeds {cap_band} cap ({reason})"
                )
        expected_ruled_out = max_adjusted > 0 and float(hyp["adjusted"]) < 0.5 * max_adjusted
        if bool(hyp.get("ruled_out")) != expected_ruled_out:
            errors.append(
                f"CG-08: hypothesis {hid} ruled_out must be {expected_ruled_out} "
                f"(adjusted {hyp['adjusted']} vs 0.5 × {max_adjusted})"
            )

    conclusion = graph.get("conclusion")
    if isinstance(conclusion, dict):
        primary = conclusion.get("primary")
        high_ids = [h.get("id") for h in numeric_ok if h.get("band") == "HIGH"]
        if primary == "none" or primary is None:
            if high_ids:
                errors.append(
                    f"CG-07: conclusion.primary is none but HIGH hypotheses exist: {high_ids}"
                )
        elif primary not in high_ids:
            errors.append(
                f"CG-07: conclusion.primary {primary!r} must name a HIGH-band hypothesis "
                "(no best-guess primary when all <= MEDIUM after caps)"
            )
    return errors


def validate_causal_graph(graph: Any, evidence: Any) -> list[str]:
    errors = _check_structure(graph)
    if not isinstance(graph, dict) or any("must be a list" in e for e in errors):
        return errors
    errors.extend(_check_nodes_edges(graph))
    errors.extend(_check_acyclic(graph))
    errors.extend(_check_edge_evidence(graph, evidence))
    errors.extend(_check_hypotheses(graph))
    return errors


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if yaml is None:
        print("PyYAML is required — pip install PyYAML", file=sys.stderr)
        return 2
    if len(args) != 2:
        print(
            "usage: validate_causal_graph.py <causal-graph.yaml> <evidence.json>",
            file=sys.stderr,
        )
        return 2
    graph_path, evidence_path = Path(args[0]), Path(args[1])
    try:
        graph = yaml.safe_load(graph_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        print(f"{graph_path}: {exc}", file=sys.stderr)
        return 1
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"{evidence_path}: {exc}", file=sys.stderr)
        return 1
    errors = validate_causal_graph(graph, evidence)
    if errors:
        print(f"{graph_path}: validation failed", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print(f"{graph_path}: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest incident-rca/tests/test_validate_causal_graph.py -q`
Expected: `18 passed`

Also run the CLI against the examples:

Run: `python3 incident-rca/scripts/validate_causal_graph.py incident-rca/reference/causal-graph.example.yaml incident-rca/reference/evidence.example.json`
Expected: `incident-rca/reference/causal-graph.example.yaml: ok`

- [ ] **Step 5: Commit**

```bash
git add incident-rca/scripts/validate_causal_graph.py incident-rca/tests/test_validate_causal_graph.py
git commit -m "feat(incident-rca): causal-graph invariant validator CG-01..CG-08 with tests

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

### Task 7: Lint wiring

**Files:**
- Modify: `Makefile` (`lint-incident-rca` target, "evidence JSON schema validator" block)
- Modify: `README.md` (lint table row for `lint-incident-rca`)
- Modify: `docs/REPOSITORY.md` (same row)

**Interfaces:**
- Consumes: CLI `validate_causal_graph.py <graph.yaml> <evidence.json>` (Task 6).

- [ ] **Step 1: Extend lint-incident-rca**

In the `lint-incident-rca` target's final block (after the `validate_evidence_json.py` run, before the pytest check), add:

```make
	python3 -m py_compile incident-rca/scripts/validate_causal_graph.py || exit 1; \
	python3 incident-rca/scripts/validate_causal_graph.py \
		incident-rca/reference/causal-graph.example.yaml \
		incident-rca/reference/evidence.example.json || exit 1; \
```

(Insert inside the existing `@cache=…` shell block so it shares the `PYTHONPYCACHEPREFIX` setup; keep line continuations `; \` consistent with neighbors.)

The existing `python3 -m pytest … incident-rca/tests/` invocation picks up the new test file automatically.

- [ ] **Step 2: Run lint**

Run: `make lint-incident-rca`
Expected: new validator line prints `…causal-graph.example.yaml: ok`; pytest count rises (23 + 18 = 41 passed); target green.

- [ ] **Step 3: Update lint documentation rows**

`README.md` lint table, `lint-incident-rca` row — replace with:

```markdown
| `lint-incident-rca` | `SKILL.md` ≤ 180 lines; frontmatter; valid `evidence.example.json`; causal-graph validator (CG-01–CG-08); anchors |
```

`docs/REPOSITORY.md` — extend the equivalent `make lint-incident-rca` row the same way (append "; causal-graph example validated (CG-01–CG-08)").

- [ ] **Step 4: Lint and commit**

Run: `make lint` → green.

```bash
git add Makefile README.md docs/REPOSITORY.md
git commit -m "build(incident-rca): lint validates causal-graph example via CG invariant script

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

### Task 8: Workflow integration + changelog

**Files:**
- Modify: `incident-rca/workflow/phase-4.md` (emit artifact; frontmatter)
- Modify: `incident-rca/workflow/phase-5.md` (render gate; frontmatter)
- Modify: `incident-rca/reference/lazy-load-index.md` (Phase 4/5 rows)
- Modify: `incident-rca/SKILL.md` (one-line pointer)
- Modify: `incident-rca/CHANGELOG.md`, `CHANGELOG.md`

- [ ] **Step 1: phase-4.md**

Frontmatter: bump `workflow_version: 1.0` → `1.1`; add `- causal_graph` under `produces:`.

Add a new section immediately before `## Phase 4 exit`:

````markdown
## Causal graph artifact (required)

After ranking (CLI or manual), write the machine-checkable causal graph per
[causal-graph-schema.md](../../../incident-rca/reference/causal-graph-schema.md) and validate it:

```bash
scratchpad="${CURSOR_SCRATCHPAD:-${TMPDIR:-/tmp}}"
python3 incident-rca/scripts/validate_causal_graph.py \
  "$scratchpad/rca_causal_graph.yaml" \
  "$scratchpad/rca_evidence.json"
```

Fix every reported `CG-*` violation before Phase 5 — the validator enforces acyclicity, evidence-backed
edges, score arithmetic, confidence caps, and the no-best-guess-primary rule
([evidence-quality.md](../../../incident-rca/reference/evidence-quality.md)). If Python or PyYAML is unavailable, state that
in **Gaps** ("causal graph not machine-validated") and verify the CG checks by hand against
[causal-graph-schema.md](../../../incident-rca/reference/causal-graph-schema.md) §Invariants.
````

- [ ] **Step 2: phase-5.md**

Frontmatter: bump `workflow_version: 1.0` → `1.1`; add `- causal_graph` under `consumes:`.

In the "Merge logic" numbered list, add a new first item (renumber the rest):

```markdown
1. **Causal-graph gate** — confirm the Phase 4 causal-graph artifact validated cleanly
   ([causal-graph-schema.md](../../../incident-rca/reference/causal-graph-schema.md)). Unvalidated or failing → return to
   Phase 4; render only with a Gaps note when validation was impossible (no Python/PyYAML).
   The report's **Causal graph** section must mirror the validated artifact's nodes and edges.
```

- [ ] **Step 3: lazy-load-index.md**

Phase 4 row: append `; [causal-graph-schema.md](../../../incident-rca/reference/causal-graph-schema.md) when writing the causal-graph artifact`.
Phase 5 row: append `, [causal-graph-schema.md](../../../incident-rca/reference/causal-graph-schema.md) (gate)`.

- [ ] **Step 4: SKILL.md pointer**

In the `## Report schema (mandatory section order)` section, item `7. Causal graph (acyclic)` — change to:

```markdown
7. Causal graph (acyclic — validated artifact: [causal-graph-schema.md](../../../incident-rca/reference/causal-graph-schema.md))
```

Check line count stays ≤ 180: `wc -l incident-rca/SKILL.md`.

- [ ] **Step 5: Changelogs**

`incident-rca/CHANGELOG.md` — add at top of the entries:

```markdown
## 2026-07-02 — causal-graph invariant validator

- **`reference/causal-graph-schema.md`** — `causal_graph` YAML artifact (`schema_version: 1`): typed nodes
  (event/trigger/root_cause/contributing/systemic), evidence-backed edges (`field[index]` refs into the
  evidence bundle), hypothesis scoring arithmetic, conclusion.
- **`scripts/validate_causal_graph.py`** — CG-01–CG-08: acyclicity, edge evidence resolution, score
  arithmetic, confidence caps (single source / contradictions / trigger unknown / Assumed-only), display-score
  normalization, ruled-out consistency, no best-guess primary.
- **Phase 4** emits + validates the artifact; **Phase 5** gates rendering on it (workflow_version 1.1).
- **Lint** — `lint-incident-rca` validates the example graph; 22 new pytest cases.
```

Root `CHANGELOG.md` — under `## incident-rca`, add a matching short entry at the top:

```markdown
### Causal-graph invariant validator (2026-07-02)

- `causal_graph` YAML artifact + `validate_causal_graph.py` (CG-01–CG-08) — machine-checks acyclicity,
  evidence-backed edges, hypothesis score arithmetic, confidence caps, and the no-best-guess-primary rule.
- Phase 4 emits and validates the artifact; Phase 5 gates rendering on it. Lint + 22 tests wired in.
```

- [ ] **Step 6: Lint and commit**

Run: `make lint` → green (anchor check covers new links; frontmatter check passes).

```bash
git add incident-rca/workflow/phase-4.md incident-rca/workflow/phase-5.md \
  incident-rca/reference/lazy-load-index.md incident-rca/SKILL.md \
  incident-rca/CHANGELOG.md CHANGELOG.md
git commit -m "feat(incident-rca): Phase 4 emits validated causal graph; Phase 5 render gate

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

MR 2 complete — open the merge request.
