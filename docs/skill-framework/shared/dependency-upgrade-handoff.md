# Dependency upgrade review → executor handoff (shared)

**Normative.** Reference doc for the `dependency-upgrade-review → loop-task-implementer` escalation
declared in [cross-skill-escalation.md](cross-skill-escalation.md) (forward table, "A dependency upgrade
has a Safe-to-upgrade or Upgrade-with-mitigations verdict" row; reverse table's matching entry). That
table has no room for this content — the real forward table is exactly 4 columns, the real reverse table
exactly 3 — so this doc holds the selection bar, the classification function's documented contract, the
hop-precondition function's documented contract, the envelope-population mapping, the stepwise-
decomposition rule, and the CVE-caveat/rollback-note carry-forward text, linked from the escalation row
itself.

## Selection bar

Not every `dependency_upgrade_report` becomes a `loop-task-implementer` task. A report qualifies for this
handoff only when **both** of the following hold:

1. `classify_dependency_upgrade` (see below) returns `QUALIFYING` for the report's own `**Verdict: ...**`
   line — i.e. the real, fixed, four-state verdict vocabulary
   [dependency-upgrade-review's report format](../../../skills/dependency-upgrade-review/reference/report-format.md)
   renders is exactly `Safe to upgrade` or `Upgrade with mitigations`. `Do not upgrade yet` and
   `Blocked — insufficient info` never qualify.
2. The report describes exactly **one** version hop (`current_version` → `target_version`). A large
   version gap that needs multiple hops is never authored as a single multi-hop task — see
   §Stepwise-decomposition rule below.

A report that fails either of these stays in the report for a human to read; it is never silently
dropped, and it never becomes an autonomous task by default.

## `classify_dependency_upgrade`

The real, single, consistently-applied classification mechanism for this handoff. Implemented at
[`skills/loop-task-implementer/scripts/classify_dependency_upgrade.py`](../../../skills/loop-task-implementer/scripts/classify_dependency_upgrade.py)
and tested at
[`skills/loop-task-implementer/tests/test_classify_dependency_upgrade.py`](../../../skills/loop-task-implementer/tests/test_classify_dependency_upgrade.py).
This doc cites that function's contract; it does not re-derive its logic in prose — read the module
docstring and tests for the authoritative behavior.

- **Signature:** `classify_dependency_upgrade(verdict: str) -> Literal["QUALIFYING", "NOT_QUALIFYING"]`
- **Pure function** — no I/O, no network, no file access, deterministic.
- **Exact string match only — no NLP, no heuristic.** Unlike `classify_security_finding` (which has to
  classify free-text `Recommendation` prose), this handoff's input is already a closed, fixed four-state
  enum that `report-format.md` itself enforces, so a simple exact-match check is genuinely sufficient —
  there is no paraphrase-evasion risk analogous to C1's own disclosed limitation.
- **Extraction step.** The function's actual input is never assumed to be a bare string — the real
  rendered verdict line is `**Verdict: <state>**` (literal bold markers and prefix). The extraction
  regex, stated explicitly: `^\*\*Verdict:\s*(.+?)\*\*$`, capture group 1 fed to the exact-match check.
  The function also accepts a caller-pre-extracted bare state string directly (callers may extract
  differently), documented explicitly in its own docstring.
- **The em-dash requirement.** One of the four canonical states contains a Unicode em-dash
  (`"Blocked — insufficient info"`, U+2014) — not a hyphen. Test fixtures (and any caller constructing
  this string) must use the literal em-dash, or that state silently never matches.
- **Fail-closed, always toward `NOT_QUALIFYING`** on any ambiguous, malformed, `None`, empty, or
  unrecognized input — including a future fifth verdict state this report format doesn't have today. It
  never fails open toward `QUALIFYING`.

## `verify_dependency_hop_precondition`

The real, code-enforced ground-truth check that a stepwise hop is being authored against the dependency's
actual current state, not a stale or assumed one. Implemented at
[`skills/loop-task-implementer/scripts/verify_dependency_hop_precondition.py`](../../../skills/loop-task-implementer/scripts/verify_dependency_hop_precondition.py)
and tested at
[`skills/loop-task-implementer/tests/test_verify_dependency_hop_precondition.py`](../../../skills/loop-task-implementer/tests/test_verify_dependency_hop_precondition.py).
This doc cites that function's contract and states the full extraction contract its input depends on; it
does not re-derive the function's own logic in prose — read the module docstring and tests for the
authoritative pure-comparison behavior.

- **Signature:** `verify_dependency_hop_precondition(manifest_pinned_version: str, expected_current_version: str) -> bool`
- **Pure function — no file I/O of its own.** `manifest_pinned_version` is the CALLER's (the Builder's)
  own already-extracted value — this function does no file reading itself. The per-ecosystem
  lockfile-reading logic described below is the Builder's own documented responsibility, not this
  function's.
- **`True` only on exact string equality**; `False` on any mismatch, including `None`/empty/non-string
  input for either argument — fail-closed, never guesses `True`.

### Extraction contract for `manifest_pinned_version`

`manifest_pinned_version` is **never** read from a manifest's own declared range (e.g. `package.json`'s
`^2.1.0`) — manifests typically declare a range, not an exact version. It is read from the ecosystem's
real **lockfile**, the resolved, exact version for the dependency, compared by exact string equality:

| Ecosystem | Lockfile(s) |
|-----------|-------------|
| npm / yarn / pnpm | `package-lock.json` / `yarn.lock` / `pnpm-lock.yaml` |
| Python | `poetry.lock` / `Pipfile.lock` |
| Ruby | `Gemfile.lock` |
| Go | `go.sum` |
| Rust | `Cargo.lock` |

**Round-4 fallback rule:** when no ecosystem lockfile exists at all, and the manifest itself declares an
exact pin with no range operator (e.g. a bare `requirements.txt` line with `==`, no `^`/`~`/`>=`), treat
that exact pin as the resolved version.

**Fail-closed default:** any other case — no lockfile and no exact-pin manifest, a dependency absent from
wherever is checked, or a monorepo/workspace with multiple manifests and no stated disambiguation rule —
fails closed (`False`), same as any other mismatch. This degrades the precondition check to "never
passes" for that repo shape rather than silently passing — safe but incomplete. Ecosystems beyond the
five listed above (PHP/`composer.lock`, Java/Gradle, .NET/`packages.lock.json`, Elixir/`mix.lock`, etc.)
are covered by the same fail-closed default, not individually enumerated.

### Where it is invoked

Invoked by the Builder, at a new named sub-section at the very top of
[`workflow/builder.md`](../../../skills/loop-task-implementer/workflow/builder.md)'s
`## 1. Understand before changing code` step, whenever the task's
`specialist_inputs.dependency_upgrade_origin` is `true`. A `False` result stops the task before any
upgrade code is written — the Builder reports `BLOCKED` with the mismatch as evidence, never proceeding
to Plan or Implement.

Independently re-checked by the Reviewer's Blocking-standard **condition 8** in
[`workflow/reviewer.md`](../../../skills/loop-task-implementer/workflow/reviewer.md), which compares the
PR's actual dependency-manifest version delta against the same `expected_current_version` →
`expected_target_version` span, using the identical lockfile-based extraction rule above — a second,
independent checkpoint, not a replacement for the Builder-side check.

## Stepwise-decomposition rule

A single upgrade request (`dependency_name`, `current_version` → `target_version`) can require multiple,
sequentially-dependent hops when the version distance is large enough that a direct jump is unsafe. The
concrete, simple rule: **one major version per hop**, for a semver-following package — if
`target_version`'s major differs from `current_version`'s major by more than one, the first hop targets
`current_version`'s next major only, not `target_version` directly. Each hop is authored, dispatched,
reviewed, and merged as its own, single `implementation_task` — there is no merge-group concept here, and
the legacy envelope bypass gains no new `dependencies` field for this.

**Do not conflate these two, differently-enforced properties:**

- **Hop *ordering*** — when a human/Orchestrator chooses to author and dispatch the next hop (only after
  the previous hop's own PR has actually merged) — is a **human/Orchestrator-applied convention, not
  code-enforced**. No code prevents a human from choosing never to author the next hop (chain
  abandonment), or from re-attempting an already-aborted chain without a fresh decision.
- **Hop *precondition*** — whether the hop about to be authored/dispatched is actually starting from the
  real, current state of the dependency — **is code-enforced**, twice: `verify_dependency_hop_precondition`
  at Builder dispatch (see above), and the Reviewer's Blocking-standard condition 8 at review time (see
  above). A premature or mis-ordered hop fails loudly and early rather than silently executing an
  unintended larger jump.

`current_version` is always re-derived from the live manifest/lockfile at the current repo head before
re-invoking `dependency-upgrade-review` for the next hop — never carried forward from the stepwise plan's
own memory. This re-derivation step is itself convention-level, not code-enforced, but it is backstopped
by the two real checks above: a forgotten re-derivation either harmlessly matches reality or gets caught
at Builder dispatch, never silently proceeds.

A multi-hop stepwise chain is **never** dispatched through `backlog-runner`'s automated nightly
batch-picking — each hop is a direct, standalone `loop-task-implementer` invocation, once its own fresh
`dependency-upgrade-review` verdict is in hand. `backlog-runner`'s own dependency-ordering mechanism
requires a dependent ticket's content to pre-exist with a declared `dependencies: []` field; a hop has no
content until the prior hop's PR merges, so there is no ticket to pre-register that dependency on.

A transitive-dependency conflict flagged in the report is surfaced as information for a human to
separately decide on — it is never auto-escalated into its own recursive upgrade-task chain. This
handoff scopes to the one, directly-requested dependency's own upgrade only.

## Envelope-population mapping

A qualifying report (one hop) is authored into the real, existing legacy `implementation_task` envelope
(the 16-field schema a human or the Orchestrator populates directly, per B6's own confirmed "legacy
bypass, cite the real fields" precedent — no new typed artifact, no `composition_contracts.yaml`/
`skills.yaml` registration needed). Each field is populated as follows:

| Field | Population rule |
|-------|-------------------|
| `task_id` | Generated per existing convention. |
| `scope` | `"{dependency_name} {current_version} → {target_version}"`, one step only, never a multi-hop span. |
| `acceptance_criteria` | Built from named source columns only: for a `Breaking changes`-driven mitigation, the table's own `Impact` column; for an `API differences`-driven mitigation, the table's own `Caller action` column; for a CVE-driven `Upgrade with mitigations` verdict, the mitigation is the upgrade itself — cite the CVE identifier plus the target version (the real CVE table — `CVE \| Affects \| Fixed in \| Severity` — has no `Source` column at all, so there is nothing to avoid citing there; the actual rule is simply "cite the CVE ID and target version, never the Notes section's own free-text caveat"). The Breaking-changes table's own `Source` column, which can quote `changelog_text` directly, is **never** the source for this field. Every value copied in is re-redacted per [safe-output.md Rule 5](safe-output.md#rule-5-pii-secret-redaction-in-rendered-output) at copy time — this applies to the Rollout-risk paragraph too, since `report-format.md` itself instructs that paragraph to cite the same untrusted `manifest_excerpt`/`changelog_text` evidence — PLUS the report's own `Rollout risk` paragraph cited as the required rollback note. The CVE-training-cutoff caveat is **not** populated here (see `specialist_inputs` below). |
| `request` | Synthesized trigger phrase: `"Upgrade {dependency} from {current_version} to {target_version} per dependency-upgrade-review's own mitigations"` (the same template as the escalation row in `cross-skill-escalation.md`). |
| `repo_root` / `target` | The manifest/lockfile path from the report's own evidence. |
| `level_hint` | Same default as any legacy-envelope task — no finding-specific rule. |
| `specialist_inputs` | Carries six fields, individually justified: `dependency_upgrade_origin: true` (the origin marker); `cve_training_cutoff_caveat` — the literal standing-disclosure text (see §Literal CVE-caveat carry-forward text below), moved out of `acceptance_criteria` because an epistemic disclaimer isn't an actionable, testable criterion; `dependency_chain_id` — a stable identifier for the whole stepwise chain, computed once when the plan is first decided as `canonical_payload_digest({"dependency_name": ..., "original_current_version": ..., "final_target_version": ...})[:16]` (reuses the codebase's own existing namespaced-digest helper instead of raw string concatenation; truncated to 16 hex characters, distinct from `derive_plan_id`'s own 8-character truncation so the two are visually distinguishable — chosen deliberately not to collide in name with the existing, different, code-tracked `plan_execution_state.plan_id`/`task.plan_context.plan_id` concept in `reference/state-schema.yaml`); `hop_index` — this hop's 1-based position in the chain, reused (not incremented) on a retry of an aborted hop, only a successfully merged hop advances it; `expected_current_version` / `expected_target_version` — this hop's own machine-readable start/end versions, the exact values `verify_dependency_hop_precondition` and Reviewer Blocking-standard condition 8 check against. **No tracker/issue entry is filed for a hop task** — consistent with the whole legacy-envelope-bypass family, this is ad-hoc, no-tracker-entry dispatch by construction. |
| `test_framework_hint` | The test-runner identity discovered for `regression_gate` (see below), not a generic unchanged default. |
| `run_tests` | `true` — "each PR keeps tests green" is enforced by this skill's own existing, unmodified completion-gate discipline, not a new mechanism. |
| `deadline` / `session_token_budget` / `output_dir` | Same defaults as any legacy-envelope task, unchanged — the 3 fields genuinely generic enough for a blanket clause. |
| `app_run` | Same default as any legacy-envelope task, unchanged — a dependency-upgrade-derived task has no app-run/UI verification requirement of its own. |
| `max_files_per_run` | A concrete absolute value of **5**. This does **not** need to scale with hop count: the one-major-version-per-hop granularity rule (§Stepwise-decomposition rule above) already bounds each hop's own footprint to a single major-version jump — file-count risk doesn't compound across hops, only within one hop, and 5 is set for that single-hop case (plausibly broader call-site footprint than a single security finding, hence higher than C1's 2–3). **Disclosed residual, not fully closed**: hop-count-invariance and absolute sufficiency are different claims — a single major-version hop for a large, central, actively-maintained framework could plausibly exceed 5 files, while a hop for a small utility library may need far fewer; `workflow/builder.md` has no documented overflow-handling convention for `max_files_per_run` at all (an inherited gap from C1, not newly introduced here). |
| `regression_gate` | Populated via a stated discovery order: check, in order, the repo's `Makefile` for a `test` target, `package.json`'s `scripts.test`, `pytest.ini`/`pyproject.toml`'s test configuration, `tox.ini`, then CI config for an explicit test-invocation line. The discovered command is only used if it matches the real `validate_repro_command` shape (documented at [`skills/bug-diagnosis/workflow/repro.md`](../../../skills/bug-diagnosis/workflow/repro.md), tested at [`skills/bug-diagnosis/tests/test_repro_command_validation.py`](../../../skills/bug-diagnosis/tests/test_repro_command_validation.py)): `pytest`/`python3 -m pytest`/`make <target>`/`npm test`/`npm run <script>` shapes only. For a repo whose real test command doesn't fit that shape (`tox`, `go test`, `cargo test`, `bundle exec rspec`, `./gradlew test`), `regression_gate` falls back to `null` with the gap disclosed, mirroring C1's own honest null-path treatment — never asserting a command re-verification will reject. |

None of these fields ever carry raw, un-redacted `changelog_text`/`manifest_excerpt` excerpts.

## Literal CVE-caveat carry-forward text

Quoted verbatim from the report's own real standing disclosure, carried in
`specialist_inputs.cve_training_cutoff_caveat` rather than `acceptance_criteria`:

> "CVE findings are reasoned from the model's training-time knowledge of public advisories, not a live
> database (this skill has no CVE/advisory MCP or external lookup), and may miss advisories disclosed
> after the training cutoff or for very recent releases."

This is the exact copy-paste text, not a paraphrase, since it becomes the literal field value — a human
reading any hop's task must not lose this context once the report's verdict is reduced to a
classification bit.

## Non-qualifying reports

`classify_dependency_upgrade` never returns a value that maps to an envelope-population path for
`NOT_QUALIFYING`. A `Do not upgrade yet` or `Blocked — insufficient info` verdict only ever reaches a
human via the report's own existing rendering — it is never authored into an `implementation_task`,
autonomous or otherwise.

## Rule-5 re-redaction discipline

Every field populated from `changelog_text`, `manifest_excerpt`, or the Rollout-risk paragraph is
re-redacted per [safe-output.md Rule 5](safe-output.md#rule-5-pii-secret-redaction-in-rendered-output) at
copy time, independently for each field — the same citation-by-reference discipline C1 established for
its own free-text `Recommendation` field, restated here for every verbatim-copied field in this handoff,
not just the first.
