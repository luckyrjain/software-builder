# Register Codex/ChatGPT in agent-hosts.yaml Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register `codex` and `chatgpt` as real hosts in `agent-hosts.yaml`, fixing
`python3 -m scripts.registry compatibility --host codex|chatgpt ...` currently erroring
`unknown host` even though both already exist as adapter-generation hosts
(`host_adapter.HOSTS`/`host_contracts.yaml`) with a real, validated packaging artifact
(`.codex-plugin/plugin.json`).

**Architecture:** One new shared target (`codex-chatgpt-plugin-root`) plus two new host entries
(`codex`, `chatgpt`) in `agent-hosts.yaml`, following the exact shape `github-copilot` (documentation-
tier evidence, `UNVERIFIED`, `BEST_EFFORT`) and `kiro` (not install.sh-resolvable, explicit
constraint sentence) already established. The new target is registered in
`scripts/registry/install_resolver.UNREACHABLE_TARGETS` so `check_target_reachability` stays green.
No schema changes anywhere (`host_registry.py`, `schema.py`, `host_adapter.py` are all untouched).

**Tech Stack:** Pure YAML data addition + Python dict entry; existing test infrastructure only.

## Global Constraints

- No new `install.sh`/`sb install` selector for Codex or ChatGPT (Codex/ChatGPT's real install
  mechanism is the existing `.codex-plugin/plugin.json` whole-repo packaging artifact — see design
  spec `docs/superpowers/specs/2026-09-13-agent-hosts-codex-chatgpt-design.md`).
- No dedicated `--agent github-copilot` selector, no change to Kiro's generate-only install model —
  both explicitly out of scope per the design spec's "Scope decisions from brainstorming" section.
- Both new host entries copy `github-copilot`'s exact verification/evidence/maintainer_support shape
  (`UNVERIFIED`, `DOCUMENTATION`-kind evidence only, `BEST_EFFORT`) — neither has been
  runtime-verified.
- Discovery `mode: ADAPTER` for both (matches `kiro`'s precedent: a generated, validated packaging
  artifact, not a live `NATIVE` per-user install.sh copy) — exact reasoning in the design spec's
  "The two host entries" section.
- `agent-hosts.yaml` and `host_contracts.yaml`/`host_adapter.py` are separate registries that grow
  independently (agent-hosts.yaml's own docstring) — this plan does not reconcile them.

---

### Task 1: Add codex/chatgpt to agent-hosts.yaml, mark the new target unreachable, update tests

**Files:**
- Modify: `agent-hosts.yaml`
- Modify: `scripts/registry/install_resolver.py`
- Modify: `scripts/tests/test_host_registry.py`

**Interfaces:**
- Consumes: `scripts.registry.host_registry.parse_host_registry` (existing, unchanged),
  `scripts.registry.install_resolver.UNREACHABLE_TARGETS` (existing dict, existing shape:
  `target_id -> reason string`).
- Produces: two new entries in `agent-hosts.yaml`'s `hosts:` list (`codex`, `chatgpt`) and one new
  entry in its `targets:` list (`codex-chatgpt-plugin-root`), consumable by every existing reader of
  `HostRegistry` with no code change (`compatibility_resolver.py`, `generate_agent_compatibility.py`,
  `schema.py._skill_host_ids`).

- [ ] **Step 1: Add the new target to `agent-hosts.yaml`'s `targets:` list**

Add after the existing `kiro-generated` target entry (matching its comment style — explain why this
target exists and that it's not install.sh-resolvable):

```yaml
  # Codex and ChatGPT both consume the exact same generated, validated whole-repository packaging
  # artifact (.codex-plugin/plugin.json, checked by
  # scripts/registry/host_portability._plugin_errors) -- "the same portable skill package contract;
  # no ChatGPT-only prompt copy is maintained" per
  # docs/skill-framework/shared/host-adapter-contract.md's Packaging validation section. Like
  # kiro-generated above, this is not an install.sh destination: there is no `--agent codex` or
  # `--agent chatgpt` selector, and none should be added without first correcting this constraint.
  - id: codex-chatgpt-plugin-root
    scope: project
    path: "{project_root}/.codex-plugin"
```

- [ ] **Step 2: Add the `codex` and `chatgpt` host entries to `agent-hosts.yaml`'s `hosts:` list**

Add after the existing `kiro` host entry (end of file):

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
      - "not install.sh-resolvable: codex-chatgpt-plugin-root is a generated, validated
        whole-repository packaging artifact (.codex-plugin/plugin.json), not a per-user or
        per-target-repo install destination -- there is no `--agent codex` selector and none should
        be added without first correcting this constraint"
    verification: UNVERIFIED
    evidence:
      - kind: DOCUMENTATION
        reference: "docs/skill-framework/shared/host-adapter-contract.md#packaging-validation
          (Codex / ChatGPT: .codex-plugin/plugin.json is valid and exposes the canonical skill
          tree)"
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
      - "not install.sh-resolvable: codex-chatgpt-plugin-root is a generated, validated
        whole-repository packaging artifact (.codex-plugin/plugin.json), not a per-user or
        per-target-repo install destination -- there is no `--agent chatgpt` selector and none
        should be added without first correcting this constraint"
    verification: UNVERIFIED
    evidence:
      - kind: DOCUMENTATION
        reference: "docs/skill-framework/shared/host-adapter-contract.md#packaging-validation
          (ChatGPT uses the same portable skill package contract as Codex; no ChatGPT-only prompt
          copy is maintained)"
    maintainer_support: BEST_EFFORT
```

- [ ] **Step 3: Register the new target as not install.sh-reachable**

In `scripts/registry/install_resolver.py`, add to `UNREACHABLE_TARGETS` (alongside the existing
`kiro-generated`/`github-copilot-user`/`github-copilot-project` entries):

```python
    "codex-chatgpt-plugin-root": (
        "consumed via .codex-plugin/plugin.json, a generated and validated whole-repository "
        "packaging artifact (scripts/registry/host_portability._plugin_errors), never installed "
        "per-user or per-target-repo by install.sh -- see the codex/chatgpt hosts' own "
        "'not install.sh-resolvable' constraint"
    ),
```

- [ ] **Step 4: Update the existing checked-in-registry test to expect the two new hosts**

In `scripts/tests/test_host_registry.py`, `test_checked_in_host_registry_validates` (around line
375-389) currently asserts:

```python
    assert sorted(registry.hosts) == ["claude", "cursor", "github-copilot", "kiro"]
```

Update the expected list to include the two new hosts, alphabetically sorted:

```python
    assert sorted(registry.hosts) == ["chatgpt", "claude", "codex", "cursor", "github-copilot", "kiro"]
```

The same test's other assertions (`claude` is the only `VERIFIED` host, everything else
`UNVERIFIED`, every host is `BEST_EFFORT`) already generalize over `registry.hosts.items()`/
`.values()` and need no further change — `codex`/`chatgpt` will automatically satisfy them since they
follow the same `UNVERIFIED`/`BEST_EFFORT` shape as every other non-`claude` host.

- [ ] **Step 5: Write a new regression test pinning the codex/chatgpt shape**

Add to `scripts/tests/test_host_registry.py`, directly after
`test_checked_in_github_copilot_host_has_documentation_evidence` (around line 428):

```python
def test_checked_in_codex_and_chatgpt_share_the_plugin_root_target() -> None:
    """Codex and ChatGPT consume the identical .codex-plugin/plugin.json packaging artifact
    (host-adapter-contract.md: "the same portable skill package contract; no ChatGPT-only prompt
    copy is maintained"), so both hosts' discovery bindings must resolve to the same target --
    and, like kiro, that target must not be install.sh-resolvable."""
    registry = parse_host_registry(ROOT / "agent-hosts.yaml")

    assert "codex-chatgpt-plugin-root" in registry.targets

    for host_id in ("codex", "chatgpt"):
        host = registry.hosts[host_id]
        bindings = [binding for surface in host.surfaces for binding in surface.discovery]
        assert len(bindings) == 1
        assert bindings[0].target.id == "codex-chatgpt-plugin-root"
        assert bindings[0].mode == "ADAPTER"
        assert host.verification == "UNVERIFIED"
        assert len(host.evidence) == 1
        assert host.evidence[0].kind == "DOCUMENTATION"
        assert host.constraints.values, f"{host_id} must document why it's not install.sh-resolvable"
        assert "not install.sh-resolvable" in host.constraints.values[0]

    from scripts.registry.install_resolver import install_selectors

    assert "codex" not in install_selectors()
    assert "chatgpt" not in install_selectors()
```

- [ ] **Step 6: Run the targeted tests to verify they pass**

Run: `python3 -m pytest scripts/tests/test_host_registry.py scripts/tests/test_legacy_install_resolver.py -v`

Expected: all pass, including the updated `test_checked_in_host_registry_validates`, the new
`test_checked_in_codex_and_chatgpt_share_the_plugin_root_target`, and
`test_every_registry_target_is_reachable_or_explicitly_allowlisted` /
`test_unreachable_allowlist_entries_each_carry_a_reason` (both already generalize over every
registered target/`UNREACHABLE_TARGETS` entry, so they cover the new target automatically with no
test change).

- [ ] **Step 7: Verify the motivating bug is actually fixed, end to end**

Run: `python3 -m scripts.registry compatibility --host codex --skill squad-map`
Expected: exits 0 and prints a compatibility result — no longer `error: unknown host 'codex'`.

Run: `python3 -m scripts.registry compatibility --host chatgpt --skill squad-map`
Expected: same — exits 0, no `unknown host` error.

(If `squad-map` is not a registered skill by the time this runs, substitute any currently-registered
skill id — `python3 -m scripts.registry list` prints the full roster.)

- [ ] **Step 8: Run full registry validation**

Run: `python3 -m scripts.registry validate`
Expected: exits 0, same `ok: ...` success line as before this change (host portability / host
adapter contract / etc. all still pass — this task touches only `agent-hosts.yaml` and
`install_resolver.py`, neither of which those checks read).

Run: `python3 -m pytest scripts/tests/ -k "host_registry or install_resolver or agent_compatibility" -v`
Expected: all pass — this also exercises `generate_agent_compatibility.py`'s consumption of the two
new hosts, confirming no generator crashes on the new entries.

- [ ] **Step 9: Commit**

```bash
git add agent-hosts.yaml scripts/registry/install_resolver.py scripts/tests/test_host_registry.py
git commit -m "Register codex and chatgpt hosts in agent-hosts.yaml"
```

## Self-Review

- **Placeholder scan:** no TBD/TODO; every yaml block, error string, and test is complete, runnable
  code — nothing deferred to "add appropriate X."
- **Spec coverage:** the design spec's entire scope (one target, two host entries, one
  `UNREACHABLE_TARGETS` entry, tests proving the motivating bug is fixed) is covered by this single
  task — nothing in the design was left undetailed.
- **Type consistency:** the new target id (`codex-chatgpt-plugin-root`) and host ids (`codex`,
  `chatgpt`) are spelled identically everywhere they're referenced (yaml, `install_resolver.py`,
  both test additions) — matches `host_adapter.HOSTS`'s existing spelling (`"codex"`, `"chatgpt"`,
  confirmed in `scripts/registry/host_adapter.py`'s `EXPECTED_SURFACES`).
