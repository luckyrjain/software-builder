# Register Codex/ChatGPT in agent-hosts.yaml — Design

**Status:** Approved (user-approved in brainstorming dialogue 2026-09-13)
**Date:** 2026-09-13
**Type:** Data/registry addition, plus one approved `schema.py` exception (see below)
**Target:** `luckyrjain/software-builder`
**Spec path:** `docs/superpowers/specs/2026-09-13-agent-hosts-codex-chatgpt-design.md`

## Goal

Close the audit's Phase 2 gap for Codex/ChatGPT by registering them as real hosts in
`agent-hosts.yaml`, the repository's evidence-gated host-identity registry (spec Section 13,
`scripts/registry/host_registry.py`). This fixes a concrete, demonstrable bug: `codex` and
`chatgpt` already exist as hosts in `scripts/registry/host_adapter.HOSTS` /
`scripts/registry/host_contracts.yaml` (used for adapter-generation capability resolution) and have
a real, validated packaging artifact (`.codex-plugin/plugin.json`, checked by
`scripts/registry/host_portability._plugin_errors`), but neither appears in `agent-hosts.yaml` at
all. As a result:

```
$ python3 -m scripts.registry compatibility --host codex --skill squad-map
error: unknown host 'codex' (known hosts: ['claude', 'cursor', 'github-copilot', 'kiro'], known aliases: [])
```

This spec adds `codex` and `chatgpt` host entries so `sb compatibility`/`sb doctor --host
codex|chatgpt` work, and so `scripts/registry/generate_agent_compatibility.py`'s generated
compatibility doc includes them.

**Schema exception (approved mid-implementation):** adding codex/chatgpt as known hosts would
otherwise have required retrofitting all 50 skills in `skills.yaml` to explicitly declare
codex/chatgpt support in their `hosts:` block. That retrofit was rejected in favor of a smaller,
targeted change to `scripts/registry/schema.py`'s `_parse_hosts` — loosen "every skill must
declare every known host" to "iterate only hosts a skill actually declared" — plus a compensating
regression test guarding the hosts generator code still depends on unconditionally.

## Scope decisions from brainstorming

Three narrower alternatives were considered and explicitly rejected before landing on this scope:

1. **Codex/ChatGPT install path:** Codex/ChatGPT already install via the whole-repo
   `.codex-plugin/plugin.json` manifest, not a per-file `install.sh` copy. Decision: register them
   as hosts only — do **not** add a new `install.sh --agent codex` per-user copy path. The plugin
   manifest is their real, already-shipped install mechanism.
2. **Copilot:** `github-copilot-user`/`github-copilot-project` targets already exist in
   `agent-hosts.yaml` but are deliberately unreachable from any `--agent` selector, because
   `--agent agents` (the universal target) already reaches Copilot's documented discovery paths.
   Decision: leave as-is — no dedicated `--agent github-copilot` selector.
3. **Kiro:** its steering file is a generated, checked-in repo artifact (`make generate`), not a
   per-user install target — an explicit, documented non-goal in `agent-hosts.yaml`'s own comments
   today. Decision: no change to Kiro's install model.

So this spec's entire scope is: two new host entries (`codex`, `chatgpt`) plus the one new target
and `install_resolver.py` bookkeeping entry they require by schema. Nothing else in the audit's
Phase 2 roadmap item is in scope.

## Why a new target is required (not optional)

`scripts/registry/host_registry.py` fails closed on both of these (`_parse_surfaces`,
`_parse_discovery`):

```
"{host_label}.surfaces must not be empty"
"{surface_label}.discovery must not be empty"
```

So a host entry cannot exist with zero surfaces, and a surface cannot exist with zero discovery
bindings — every discovery binding must reference a real `targets:` entry. There is no way to
register `codex`/`chatgpt` as documentation-only, no-target hosts under the current schema, and
this spec does not propose relaxing that constraint (it exists to keep every host claim grounded in
a real, checkable location — relaxing it for two hosts just to skip writing one target entry would
be a foundation change, not a data addition).

## The new target

```yaml
- id: codex-chatgpt-plugin-root
  scope: project
  path: "{project_root}/.codex-plugin"
```

One target, shared by both new host entries' discovery bindings — `codex` and `chatgpt` consume the
exact same generated artifact (`host-adapter-contract.md`'s own Packaging validation section: "the
same portable skill package contract; no ChatGPT-only prompt copy is maintained"), so one target
correctly models that they point at the same place, the way `all`'s selector already reuses
`_CURSOR`/`_CLAUDE_PROJECT` routes across multiple destinations. `path` points at the `.codex-plugin`
directory itself (containing the validated `plugin.json`), mirroring `kiro-generated`'s
`{project_root}/.kiro/steering` — "the directory holding the generated/validated artifact", not the
bare repo root.

This target is **not** install.sh-resolvable, exactly like `kiro-generated`, and for the same
reason (generated/checked-in artifact, not a per-user or per-target-repo install destination). Add
it to `scripts/registry/install_resolver.py`'s `UNREACHABLE_TARGETS`:

```python
"codex-chatgpt-plugin-root": (
    "consumed via .codex-plugin/plugin.json, a generated and validated whole-repository "
    "packaging artifact (scripts/registry/host_portability._plugin_errors), never installed "
    "per-user or per-target-repo by install.sh -- see the codex/chatgpt hosts' own "
    "'not install.sh-resolvable' constraint"
),
```

## The two host entries

Both use `mode: ADAPTER` (the same discovery mode `kiro` uses) — the discovery mode enum
(`ALLOWED_DISCOVERY_MODES`) is documentation/metadata only; nothing in the codebase branches on its
value at runtime (verified: no `.mode ==` conditional exists anywhere outside
`host_registry.py`'s own parsing/validation). `ADAPTER` was chosen over `NATIVE` because
`.codex-plugin/plugin.json` is a generated, registry-derived artifact just as `.kiro/steering/*.md`
is — both are called out together under host-adapter-contract.md's "Packaging validation" section —
whereas `NATIVE` (used by `cursor`/`claude`) means "install.sh's own copy is the host's live,
per-user discovery location," which does not describe this mechanism.

Both entries copy `github-copilot`'s exact verification shape, since neither has been
runtime-verified (only `DOCUMENTATION`-kind evidence exists, same as Copilot):

```yaml
- id: codex
  surfaces:
    - kind: LOCAL
      discovery:
        - target: codex-chatgpt-plugin-root
          mode: ADAPTER
          precedence: 10
  capabilities:
    host.filesystem.read: UNKNOWN
    host.repository.read_write: UNKNOWN
  isolation:
    mode: UNKNOWN
  constraints:
    - "not install.sh-resolvable: codex-chatgpt-plugin-root is a generated, validated whole-repository
      packaging artifact (.codex-plugin/plugin.json), not a per-user or per-target-repo install
      destination -- there is no `--agent codex` selector and none should be added without first
      correcting this constraint"
  verification: UNVERIFIED
  evidence:
    - kind: DOCUMENTATION
      reference: "docs/skill-framework/shared/host-adapter-contract.md#packaging-validation (Codex
        / ChatGPT: .codex-plugin/plugin.json is valid and exposes the canonical skill tree)"
  maintainer_support: BEST_EFFORT

- id: chatgpt
  surfaces:
    - kind: LOCAL
      discovery:
        - target: codex-chatgpt-plugin-root
          mode: ADAPTER
          precedence: 10
  capabilities:
    host.filesystem.read: UNKNOWN
    host.repository.read_write: UNKNOWN
  isolation:
    mode: UNKNOWN
  constraints:
    - "not install.sh-resolvable: codex-chatgpt-plugin-root is a generated, validated whole-repository
      packaging artifact (.codex-plugin/plugin.json), not a per-user or per-target-repo install
      destination -- there is no `--agent chatgpt` selector and none should be added without first
      correcting this constraint"
  verification: UNVERIFIED
  evidence:
    - kind: DOCUMENTATION
      reference: "docs/skill-framework/shared/host-adapter-contract.md#packaging-validation (ChatGPT
        uses the same portable skill package contract as Codex; no ChatGPT-only prompt copy is
        maintained)"
  maintainer_support: BEST_EFFORT
```

`surfaces: kind: LOCAL` (not `WEB`/`CLOUD`) for both, including the web-based ChatGPT app: `LOCAL`
here describes where the *skill files* live and are discovered from (the local checkout's
`.codex-plugin/plugin.json`), the same axis every other host in this file already uses it for — it
is not a claim about where the agent's own UI runs. Re-litigating that axis for a genuinely
browser-hosted agent is a bigger modeling question than this spec's scope covers, and no existing
host entry uses `WEB`/`CLOUD` today to draw on as precedent.

`constraints` text is intentionally the mirror of `kiro`'s own constraint sentence (same
"not install.sh-resolvable... there is no `--agent X` selector and none should be added without
first correcting this constraint" shape) — this repo already has exactly one convention for stating
this, so both new hosts reuse it rather than inventing new phrasing.

## Downstream effects (no code changes needed, verified)

- `scripts/registry/compatibility_resolver.py`'s `resolve_host` will find `codex`/`chatgpt` in
  `host_registry.hosts` and stop raising `unknown host`.
- `scripts/registry/generate_agent_compatibility.py` iterates `host_registry.hosts` already; the two
  new hosts appear in the generated compatibility doc automatically, no generator change needed.
- `scripts/registry/install_resolver.check_target_reachability` already fails closed on any
  registered target with no selector and no `UNREACHABLE_TARGETS` entry — this is exactly why the
  new target must be added there (Step above), not an extra safeguard being introduced.
- `host_adapter.HOSTS`/`host_contracts.yaml` (the separate, pre-existing registry used for
  adapter-generation capability resolution) are untouched — `agent-hosts.yaml`'s own docstring
  already states the two registries "grow independently," and this spec does not reconcile them.

## Testing

- `scripts/tests/test_host_registry.py`: extend the fixture/parsing tests to cover the new target
  and two host entries — assert `parse_host_registry` succeeds on the real `agent-hosts.yaml`,
  `codex` and `chatgpt` appear in `host_registry.hosts`, and each resolves its discovery binding to
  `codex-chatgpt-plugin-root`.
- `scripts/tests/test_install_resolver.py` (or wherever `check_target_reachability` is tested):
  assert the new target does not trip "target not reachable" now that it's declared in
  `UNREACHABLE_TARGETS`.
- Real end-to-end check (matches this spec's own motivating example): after the change,
  `python3 -m scripts.registry compatibility --host codex --skill <any-registered-skill>` and
  `--host chatgpt` must both succeed (exit 0) instead of erroring `unknown host`.
- `python3 -m scripts.registry validate` and `python3 -m scripts.registry validate-hosts` (or
  whichever wraps `check_target_reachability`/`parse_host_registry` in CI) must stay green.

## Explicitly deferred

- Any `install.sh`/`sb install` per-user copy path for Codex or ChatGPT.
- A dedicated `--agent github-copilot` selector.
- Changing Kiro's generate-only install model.
- Reconciling `agent-hosts.yaml` with `host_adapter.HOSTS`/`host_contracts.yaml` into one registry.
- Modeling Claude's own `.claude-plugin` marketplace mechanism in `agent-hosts.yaml` (it isn't
  modeled today either — only Claude's `install.sh` copy path is — so this spec does not introduce
  an inconsistency, it just doesn't extend plugin-mechanism modeling to a second host pair).

## Self-review

- **Placeholder scan:** no TBD/TODO; every yaml value, error string, and file path is concrete.
- **Internal consistency:** the "no runtime code branches on discovery mode" claim was verified by
  grep before being stated, not assumed; the "schema requires non-empty surfaces/discovery" claim is
  quoted directly from `host_registry.py`'s own error strings.
- **Scope check:** single coherent registry addition (one target, two host entries, one
  `UNREACHABLE_TARGETS` entry, tests) — no further decomposition needed for one implementation plan.
- **Ambiguity check:** the LOCAL-vs-WEB surface-kind question for ChatGPT is explicitly addressed
  rather than left ambiguous, with a stated reason for the choice and the boundary of what this spec
  does not attempt to resolve.
