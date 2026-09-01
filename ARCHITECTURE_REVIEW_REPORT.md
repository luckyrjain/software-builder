# Architecture review — Universal Coding-Agent Compatibility

**Decision: Needs rework**

Needs rework — unquantified host×skill/evidence scale growth (see Scale limits), undefined stale-lock
and partial multi-target-failure recovery (see Failure modes), an unenforced cross-host
permission-field-reinterpretation rule (see Security), and no named operability owner or evidence-refresh
process (see Operability). None of these are fatal to the architecture, and none block starting
**Candidate 0** (baseline freeze), which touches none of the flagged areas — see Notes at the end.

## Architecture decision

The proposal generalizes the already-merged Phase 1 host registry (`agent-hosts.yaml` +
`scripts/registry/host_registry.py`, which today models 3 hosts with `UNKNOWN` capabilities and no
resolver) into a full host × surface × skill compatibility system: a declarative registry owning host
identity/discovery/capabilities/evidence, a resolver that reuses `skills.yaml`'s existing
required/optional/any-of capability engine (already implemented in `scripts/doctor.py`'s
`_capability_status`) rather than building a second one, evidence-backed verification states
(`OBSERVED`/`INFERRED`/`UNKNOWN`/`CONFLICTED`, with staleness), and ownership-safe installation into a
new shared, multi-tool discovery directory (`.agents/skills`). The stated motivation (§72, the "final
invariant") is that a new host should be addable primarily as verified data, not as new per-host
implementation code — the current state (`HostCursor`/`HostClaude`/`HostKiro` hard-coded per §7) is
exactly the pattern being escaped. Rollout is explicitly incremental across 13 candidates, each with its
own exit criterion, with backward compatibility as a hard constraint (§29, §30, AD-07/AD-08) and a final
combined-diff review gate (Candidate 13) before the work is considered done.

## Risks

| Risk | Section | Severity | Notes |
|------|---------|----------|-------|
| Host×skill×surface combinatorial growth and evidence-record volume have no stated bound or resolver performance budget | Scale limits | Conditional | 12 named host selectors (`§32`) × 38 current skills × up to 3 surfaces; no perf/latency requirement anywhere in the 72 sections |
| Stale/crashed advisory-lock recovery is named as required but not designed | Failure modes | Conditional | `"A stale-lock strategy must be documented and tested"` (`§37`) — defers the actual mechanism |
| Multi-target `PARTIAL` result has no stated recovery procedure | Failure modes | Conditional | `§36` defines `SUCCESS`/`PARTIAL`/`FAILED` reporting but not what happens to already-succeeded targets when a later one fails |
| Cross-host permission-field reinterpretation principle (`§20`, `AD-14`) has no corresponding validation rule in the registry-validation list (`§47`) or negative-test list (`§63`) | Security | Conditional | Every other named security rule in the doc gets an explicit rejection rule or negative test; this one does not |
| No named operability owner or evidence-refresh cadence before staleness | Operability | Conditional | `§25` sets `evidence_max_age_days: 90` but nothing states who re-verifies before that clock expires |
| Thin alternatives-considered coverage relative to the proposal's size | Alternatives considered | Informational | Two alternatives are explicitly reasoned about (`§30`, `§1`); larger choices (filesystem-copy distribution vs. vendor package managers, declarative YAML vs. programmatic host discovery) are undiscussed |
| Advisory-lock file path itself is not covered by the same symlink-leaf hardening stated for install destinations | Security | Informational | `§48` hardens destination symlinks; the lock file's own path safety is unstated |

## Scale limits

| Dimension | Breaks down at | Evidence |
|-----------|-----------------|----------|
| Host × skill × surface compatibility matrix | Unknown — no bound or resolver performance target stated | `§32` lists 12 target host selectors; current repo has 38 skills (verified via `load_registry`); §11's resolver runs per host×surface×skill, with no stated evaluation-time budget anywhere in the document |
| Skill catalog metadata footprint on flat-layout hosts | Explicitly quantified: `catalog_metadata_budget_bytes: 50000` | `§22`, with an explicit preflight-failure requirement before mutation — the one dimension in the proposal that **is** properly bounded |
| Evidence-record volume over time (per host × surface × capability × claim, with provenance/observed_at) | Unknown — no retention/pruning strategy stated | `§24`–`§25` define the evidence shape and a 90-day staleness default but not storage growth handling |
| Concurrent installation load (lock contention) | Unknown — "must fail clearly" but no concurrency ceiling stated | `§37` |

## Failure modes

| Failure mode | Detection | Recovery | Notes |
|--------------|-----------|----------|-------|
| Vendor documentation conflict between authoritative sources | Explicit `CONFLICTED` evidence state | Project-level install stays available; global/ambiguous install is withheld until user explicitly selects a raw target | `§23`, `§57` — well-specified |
| Evidence goes stale past `evidence_max_age_days` | `STALE` status computed from `observed_at` | Blocks first-class promotion; does **not** break already-installed skills | `§25` — well-specified |
| Concurrent writers contend for the same install target | Target-scoped advisory lock, "contention SHALL fail clearly" | Unknown — `"stale-lock strategy must be documented and tested"` names the requirement without defining the mechanism | `§37` — recovery undefined |
| One target in a multi-target install operation fails after others succeeded | `PARTIAL` status with enumerated exact destinations changed | Unknown — no stated rollback-vs-leave-partial-state policy for the succeeded targets | `§36` — detection is strong, recovery is unstated |
| Existing unowned or corrupted-ownership directory collides with an install/uninstall target | Ownership state machine (`ABSENT`/`OWNED`/`UNOWNED`/`CORRUPT_OWNERSHIP`/`SYMLINK`) | Blocked outright, no force-overwrite; explicit adoption workflow deferred to later design | `§15`–`§16` — well-specified, recovery intentionally deferred rather than undefined |
| A higher-precedence discovery root shadows the newly installed skill | `BLOCKED_SHADOWED_INSTALL` / `UNVERIFIED_PRECEDENCE` | User can explicitly target the higher-precedence location; installer never claims false activation success | `§35` — well-specified |
| Compatibility-layer code is reverted after rollout | N/A (design-time invariant) | Already-installed manifests/packages remain readable and functional without the reverted code | `§66` — one of the strongest-specified sections |

## Security

| Concern | Trust boundary / data flow | Blast radius | Notes |
|---------|------------------------------|---------------|-------|
| Project-level skill installation as repository mutation | Untrusted repository content crosses into the installer only on explicit, named project-target selection — no silent discovery/modification of arbitrary repos | Limited to the explicitly targeted repo | `§21` — well-specified, consistent with the diagram's install-time boundary between `package_skill.py` output and host discovery directories |
| Path traversal / unsafe path expansion | Allowlisted template variables only (`{project_root}`, `~`), no arbitrary env-var interpolation, canonicalized project-root containment, symlink-leaf destinations forbidden | An escape would let install/uninstall touch arbitrary filesystem paths outside the project | `§48` — matches the path-safety validation already implemented and adversarially reviewed in the merged Phase 1 code (`scripts/registry/host_registry.py`'s `_validate_target_path`) |
| Moving into a shared, multi-tool discovery directory (`.agents/skills`) used by other tools/users | New surface: this system's writes now sit alongside third-party-owned content it does not control | Ownership state machine + block-by-default policy (`§15`–`§17`) contains blast radius to "refuse to touch," not "silently corrupt or delete" | This is the single largest new security-relevant surface this phase introduces, and it is the best-specified part of the document |
| Host-specific frontmatter field reinterpreted as a permission grant on one host while intended as a portable restriction on another | Named explicitly: `"a field that one host interprets as a permission grant MUST NOT be treated as a portable restriction mechanism"` | Unknown — no enforcement mechanism | `§20`, `AD-14` — the principle is correctly identified but, unlike nearly every other named security rule in this document, has no matching entry in the `§47` registry-rejection list or the `§63` negative-test list |
| Isolation-primitive conflation for security-sensitive, multi-agent workflows | Explicit fail-closed rule: unresolved isolation capability blocks READY; sequential role simulation may not be relabeled as strong isolation | Contained — a compatibility adapter cannot itself weaken this | `§52`–`§53` — well-specified |
| Advisory lock file's own path safety | Unknown — not addressed | Unknown | `§37` describes lock behavior but not whether the lock path is subject to the same symlink-leaf hardening as install destinations (`§48`) |

## Operability

| Concern | Owner | Operating cost | Notes |
|---------|-------|------------------|-------|
| Who runs/maintains the compatibility resolver, registry, and evidence store once shipped | Unknown — not named anywhere in the 72 sections | No new on-call surface implied (dev-tooling installer, not a running service); new failure classes (lock contention, evidence staleness, shadowing) are introduced with no stated process for who watches/responds to them | The proposal states three deterministic CI gates (`§46` doc-drift, `§47` registry validation, generated compatibility docs) but never names who owns the system day-to-day or who re-verifies evidence before it goes `STALE` |

## Alternatives considered

| Alternative | Why not chosen | Notes |
|-------------|-------------------|-------|
| Redefine `--agent all` to install into all supported host directories | Rejected — would violate backward compatibility and could create shadowed duplicate skills | `§30` — explicitly reasoned |
| One implementation per coding agent (the pattern being replaced) | Rejected — the stated central architectural goal is to avoid N per-host implementations in favor of declarative host data | `§1`, `§72` — explicitly reasoned, if implicitly framed as "the problem" rather than a formally rejected alternative |
| Vendor-native distribution channels (plugin/marketplace/CLI package installers) as the primary discovery mechanism, vs. filesystem-copy installation | Unknown — no rationale given | `§28` inventories that these channels exist and defers them, but does not explain why filesystem-copy installation was chosen as the primary mechanism over, e.g., symlinking or a package-manager-style install |
| Programmatic host auto-detection vs. an explicit declarative registry | Unknown — no rationale given | `§4` lists auto-detection as a non-goal but does not state why a declarative registry was preferred over detection-plus-inference |

## Notes for proceeding to Candidate 0

Candidate 0 ("baseline freeze": golden tests for the existing `scripts/install.sh` and `scripts/doctor.py`
behavior, per `§64`) does not touch the compatibility resolver, the evidence model, shared-directory
ownership, or concurrency — none of the areas that produced the `Needs rework` verdict above. It is safe
to start immediately; the flagged gaps should be resolved before Candidate 4 (compatibility resolver),
Candidate 6 (ownership hardening, which is explicitly the "release prerequisite for `.agents/skills`" per
`§64`), and Candidate 9+ (evidence-gated host promotion).
