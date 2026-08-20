# Canonical test-creator workflow (shared)

**Normative.** The five test creators use the same phase ordering and common
contracts. Their own files contain only level-specific behavior, artifact
layouts, detection rules, and gates.

## Common phases

1. **Inputs** — validate the caller-owned target and `repo_root`; preserve
   ordinary specialist fields exactly; treat `execution_context` as
   framework-owned and advance it only according to the runtime contract.
2. **Detect conventions** — inspect the repository and report observed tooling
   and layout; ask only when that level's required convention is ambiguous.
3. **Select targets** — derive a bounded, ordered target list from the
   validated input and existing coverage; never infer a broader scope.
4. **Generate tests** — build a complete write plan, run the shared
   [write-safety contract](test-creator-write-safety.md), and write only the
   level's declared artifacts.
5. **Verify and iterate** — run the observed command when capability and
   environment permit; preserve real expected/actual evidence and use shared
   status vocabulary.
6. **Report** — emit the level report using the shared skeleton, preserve the
   raw guard result and child authority, then optionally update coverage state
   only after a fresh report-only guard check.

## Parity invariants

- Common inputs are forwarded unchanged, including falsey values and explicit
  empty collections. Defaults are applied only by the owning specialist.
- A child `skill_result` and raw report are authoritative. A router may map
  only the documented portable status alias; it must not rewrite blockers,
  artifacts, evidence, or recommendations.
- All creators produce the compatible `test_suite` shape
  (`tests`, `framework`, `target_path`) plus level-specific details inside
  their own report/artifact files.
- Missing capability, unsafe repository state, and unavailable verification
  produce a degraded `BLOCKED` or level-specific blocked status; they never
  become a passing result.
- No common phase may add an interactive question. Only a specialist's
  documented level-specific gate may ask the caller for missing information.
