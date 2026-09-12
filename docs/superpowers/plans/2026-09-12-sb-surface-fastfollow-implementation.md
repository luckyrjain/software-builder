# `--surface` Fast-Follow for `sb compatibility` / `sb doctor` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire real `--surface` support into `python3 -m scripts.registry compatibility` and the `sb` CLI's `compatibility`/`doctor` subcommands, now that both prerequisites (`compatibility_resolver.resolve(..., surface_kind=...)` from PR #256, and the `sb` package itself from PR #257) are merged to `main`.

**Architecture:** Pure plumbing — no new resolution logic. `cmd_compatibility` gains a `surface_kind` parameter threaded into the already-existing `resolve()` call, with the same unknown-surface validation guard `scripts/doctor.py`'s `main()` already has. `cli/sb/__main__.py` mirrors both additions verbatim against its vendored copy.

## Global Constraints

- No new resolution logic. `available_capabilities(host, surface_kind)` and `resolve(..., surface_kind=...)` already exist and are already tested (PR #256) — this plan only adds a CLI flag and threads it through.
- Match existing code style exactly, including the exact validation-guard wording already established in `scripts/doctor.py`.
- No new dependencies.
- `sb`'s copy of this logic must match `scripts/registry/cli.py`'s and `scripts/doctor.py`'s exactly (same validation message, same behavior) — `sb`'s `_cmd_doctor`/`compatibility` dispatch already duplicates library-adjacent logic intentionally (see `cli/sb/__main__.py`'s existing `_default_install_roots_for_host` docstring for the precedent and rationale); this plan's duplication follows the same, already-accepted pattern.

---

### Task 1: `--surface` on `python3 -m scripts.registry compatibility`

**Files:**
- Modify: `scripts/registry/cli.py`
- Test: `scripts/tests/test_discovery_compatibility_cli.py` (existing file — extend it)

**Interfaces:**
- Consumes: `scripts.registry.compatibility_resolver.resolve(host_registry, registry, host_id, skill_id, surface_kind=None)` (already exists, `surface_kind` param added in PR #256)
- Produces: `cmd_compatibility(root: Path, host_id: str, skill_id: str | None, surface_kind: str | None = None) -> int`

- [ ] **Step 1: Write the failing tests**

Append to `scripts/tests/test_discovery_compatibility_cli.py`:

```python
def test_compatibility_surface_flag_matches_default_for_claude_local_surface() -> None:
    # The real "claude" host's only surface is LOCAL with no per-surface overrides today, so
    # --surface LOCAL must resolve identically to omitting --surface entirely.
    with_surface = _run_cli("compatibility", "--host", "claude", "--skill", "pr-review", "--surface", "LOCAL")
    without_surface = _run_cli("compatibility", "--host", "claude", "--skill", "pr-review")

    assert with_surface.returncode == without_surface.returncode == 0
    assert with_surface.stdout == without_surface.stdout


def test_compatibility_rejects_unknown_surface() -> None:
    result = _run_cli("compatibility", "--host", "claude", "--surface", "NOT_A_REAL_SURFACE")

    assert result.returncode == 2
    assert "NOT_A_REAL_SURFACE" in result.stderr


def test_compatibility_surface_differentiates_per_surface_capability_overrides(tmp_path) -> None:
    """Direct-call test (not subprocess): cmd_compatibility itself has no --repo-root flag
    (unlike doctor.py), so a synthetic multi-surface registry can only be exercised by calling
    the function directly against a tmp_path root, not via _run_cli. Model the fixture on
    scripts/tests/test_doctor.py's _write_surface_fixture (a "claude" host with a LOCAL surface
    where host.repository.read_write is AVAILABLE and a CLOUD surface where it's UNAVAILABLE,
    plus one skill requiring it) -- read that fixture first and reuse its exact shape rather
    than inventing a new one.
    """
    from scripts.registry.cli import cmd_compatibility

    # ... build the tmp_path fixture here, following test_doctor.py's _write_surface_fixture
    # shape exactly (agent-hosts.yaml with claude's LOCAL/CLOUD surfaces, skills.yaml with one
    # skill requiring host.repository.read_write, VERSION) ...

    exit_code_local = cmd_compatibility(tmp_path, "claude", "demo-skill", "LOCAL")
    exit_code_cloud = cmd_compatibility(tmp_path, "claude", "demo-skill", "CLOUD")

    assert exit_code_local == 0
    assert exit_code_cloud == 0  # cmd_compatibility always returns 0 for a resolved (not unknown) host/skill --
    # the differentiation is in the printed status line, not the exit code (see cmd_compatibility's
    # existing body: only unknown host/skill affect the return code). Capture stdout via capsys
    # and assert the LOCAL line contains "READY" (or the real resolved status for an AVAILABLE
    # capability) while the CLOUD line contains "BLOCKED" (or the real resolved status for an
    # UNAVAILABLE one) -- check scripts/registry/compatibility_resolver.py's actual status
    # vocabulary and this fixture's host verification state to use the exact right expected
    # strings, the same way test_doctor.py's own surface test does.
```

(The third test's body has an intentional gap — build the fixture and finish the assertions against `test_doctor.py`'s real, existing `_write_surface_fixture` shape and this repo's real status vocabulary, not invented values.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest scripts/tests/test_discovery_compatibility_cli.py -k surface -v`
Expected: FAIL — `--surface` is not a recognized argument yet

- [ ] **Step 3: Add `--surface` to `cmd_compatibility`**

In `scripts/registry/cli.py`, replace the current `cmd_compatibility`:

```python
def cmd_compatibility(root: Path, host_id: str, skill_id: str | None) -> int:
    try:
        host_registry = parse_host_registry(root / "agent-hosts.yaml")
    except HostRegistryParseError as exc:
        for error in exc.errors:
            print(f"error: {error}", file=sys.stderr)
        return 2

    try:
        resolve_host(host_registry, host_id)
    except UnknownHostError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    registry = load_registry(root)
    if skill_id is not None:
        if skill_id not in registry.skills:
            print(f"error: unknown skill {skill_id!r}", file=sys.stderr)
            return 1
        skill_ids = [skill_id]
    else:
        skill_ids = sorted(registry.skills)

    for sid in skill_ids:
        result = resolve(host_registry, registry, host_id, sid)
        line = f"{result.host_id} {result.skill_id}: {result.status}"
        if result.missing_required:
            line += f" (missing required: {', '.join(result.missing_required)})"
        elif result.missing_optional:
            line += f" (missing optional: {', '.join(result.missing_optional)})"
        print(line)
    return 0
```

with:

```python
def cmd_compatibility(root: Path, host_id: str, skill_id: str | None, surface_kind: str | None = None) -> int:
    try:
        host_registry = parse_host_registry(root / "agent-hosts.yaml")
    except HostRegistryParseError as exc:
        for error in exc.errors:
            print(f"error: {error}", file=sys.stderr)
        return 2

    try:
        host = resolve_host(host_registry, host_id)
    except UnknownHostError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if surface_kind is not None:
        declared_surfaces = {surface.kind for surface in host.surfaces}
        if surface_kind not in declared_surfaces:
            print(
                f"error: unknown surface {surface_kind!r} for host {host_id!r} "
                f"(declared surfaces: {sorted(declared_surfaces)})",
                file=sys.stderr,
            )
            return 2

    registry = load_registry(root)
    if skill_id is not None:
        if skill_id not in registry.skills:
            print(f"error: unknown skill {skill_id!r}", file=sys.stderr)
            return 1
        skill_ids = [skill_id]
    else:
        skill_ids = sorted(registry.skills)

    for sid in skill_ids:
        result = resolve(host_registry, registry, host_id, sid, surface_kind)
        line = f"{result.host_id} {result.skill_id}: {result.status}"
        if result.missing_required:
            line += f" (missing required: {', '.join(result.missing_required)})"
        elif result.missing_optional:
            line += f" (missing optional: {', '.join(result.missing_optional)})"
        print(line)
    return 0
```

(Note this now uses the `host` object `resolve_host` returns, previously discarded after existence-checking — this also closes the "resolve_host called purely for validation, result discarded" observation from a prior review.)

- [ ] **Step 4: Wire the argparse flag and dispatch**

In `main()`, after `compatibility_parser.add_argument("--skill", ...)`:

```python
    compatibility_parser.add_argument(
        "--surface",
        help="surface kind (e.g. LOCAL, CLOUD) from agent-hosts.yaml; narrows resolution to "
        "that surface's overrides where the host declares any (Candidate 2)",
    )
```

Update the dispatch line:

```python
    if args.command == "compatibility":
        return _run_command(lambda: cmd_compatibility(ROOT, args.host, args.skill, args.surface))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest scripts/tests/test_discovery_compatibility_cli.py -v`
Expected: PASS (all tests, including the 3 new ones)

- [ ] **Step 6: Commit**

```bash
git add scripts/registry/cli.py scripts/tests/test_discovery_compatibility_cli.py
git commit -m "$(cat <<'EOF'
Add --surface to python -m scripts.registry compatibility

Threads the surface_kind parameter compatibility_resolver.resolve()
already accepts (PR #256) through the compatibility subcommand, with
the same unknown-surface validation guard scripts/doctor.py already
has. No new resolution logic -- pure CLI plumbing.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: `--surface` on `sb compatibility` / `sb doctor`

**Files:**
- Modify: `cli/sb/__main__.py`
- Test: `cli/tests/test_sb_compatibility_parity.py`, `cli/tests/test_sb_doctor_parity.py` (existing files — extend both)

**Interfaces:**
- Consumes: Task 1's `cmd_compatibility(root, host_id, skill_id, surface_kind)`; `scripts.registry.compatibility_resolver.available_capabilities(host, surface_kind)` (already imported in `cli/sb/__main__.py`, already used without the surface arg)

- [ ] **Step 1: Write the failing tests**

Append to `cli/tests/test_sb_compatibility_parity.py`:

```python
def test_sb_compatibility_surface_matches_checkout() -> None:
    sb_result = _run_sb("compatibility", "--host", "claude", "--skill", "pr-review", "--surface", "LOCAL")
    checkout_result = _run_checkout_registry_cli(
        "compatibility", "--host", "claude", "--skill", "pr-review", "--surface", "LOCAL"
    )

    assert sb_result.returncode == checkout_result.returncode == 0
    assert sb_result.stdout == checkout_result.stdout


def test_sb_compatibility_rejects_unknown_surface() -> None:
    result = _run_sb("compatibility", "--host", "claude", "--surface", "NOT_A_REAL_SURFACE")

    assert result.returncode == 2
    assert "NOT_A_REAL_SURFACE" in result.stderr
```

Append to `cli/tests/test_sb_doctor_parity.py`:

```python
def test_sb_doctor_surface_matches_checkout() -> None:
    sb_result = _run_sb(
        "doctor", "--skill", "pr-review", "--agent", "claude", "--surface", "LOCAL",
        "--install-root", "/nonexistent",
    )
    checkout_result = _run_checkout_doctor(
        "--skill", "pr-review", "--agent", "claude", "--surface", "LOCAL",
        "--install-root", "/nonexistent",
    )

    assert sb_result.returncode == checkout_result.returncode
    assert sb_result.stdout == checkout_result.stdout


def test_sb_doctor_rejects_unknown_surface() -> None:
    result = _run_sb(
        "doctor", "--agent", "claude", "--surface", "NOT_A_REAL_SURFACE",
        "--install-root", "/nonexistent",
    )

    assert result.returncode == 2
    assert "NOT_A_REAL_SURFACE" in result.stderr
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd cli && python3 -m pytest tests/test_sb_compatibility_parity.py tests/test_sb_doctor_parity.py -k surface -v`
Expected: FAIL — `--surface` not recognized by `sb`'s `compatibility`/`doctor` subparsers yet

- [ ] **Step 3: Wire `--surface` into `cli/sb/__main__.py`**

Add to the `compatibility_parser` block:

```python
    compatibility_parser.add_argument(
        "--surface",
        help="surface kind (e.g. LOCAL, CLOUD) from agent-hosts.yaml",
    )
```

Update the compatibility dispatch line:

```python
    if args.command == "compatibility":
        return cmd_compatibility(registry_snapshot_root(), args.host, args.skill, args.surface)
```

Add to the `doctor_parser` block:

```python
    doctor_parser.add_argument(
        "--surface",
        help="surface kind (e.g. LOCAL, CLOUD) from agent-hosts.yaml; narrows available "
        "capabilities to that surface's overrides where the host declares any",
    )
```

In `_cmd_doctor`, add the validation guard and pass `args.surface` through, mirroring `scripts/doctor.py`'s exact logic:

```python
        host_id = args.agent
        host_verification = host.verification
        if args.surface is not None:
            declared_surfaces = {surface.kind for surface in host.surfaces}
            if args.surface not in declared_surfaces:
                print(
                    f"error: unknown surface {args.surface!r} for host {args.agent!r} "
                    f"(declared surfaces: {sorted(declared_surfaces)})",
                    file=sys.stderr,
                )
                return 2
        available = set(available_capabilities(host, args.surface))
```

(This replaces the existing `host_id = args.agent`, `host_verification = host.verification`, `available = set(available_capabilities(host))` lines in that same spot — insert the surface validation between them and pass `args.surface` into `available_capabilities`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd cli && python3 -m pytest tests/ -v`
Expected: PASS (all tests, including the 4 new ones)

- [ ] **Step 5: Run the broader regression check**

Run: `make lint-cli-tests`
Run: `python3 -m pytest scripts/tests/test_discovery_compatibility_cli.py scripts/tests/test_doctor.py -v`
Expected: all green, no regressions

- [ ] **Step 6: Commit**

```bash
git add cli/sb/__main__.py cli/tests/test_sb_compatibility_parity.py cli/tests/test_sb_doctor_parity.py
git commit -m "$(cat <<'EOF'
Add --surface to sb compatibility / sb doctor

Mirrors Task 1's checkout-side plumbing into sb's vendored-copy shim:
same validation guard, same available_capabilities(host, surface_kind)
call. Parity tests confirm identical output to the checkout tools for
the same host/surface/skill.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Self-review

**Spec coverage:** both commands named in the goal (`sb compatibility`, `sb doctor`) get real `--surface` support; the shared `python -m scripts.registry compatibility` gets it too (not `sb`-only, matching the precedent set when `compatibility` was first added). No new resolution logic anywhere — every task only threads an existing parameter through.

**Placeholder scan:** Task 1's third test has one deliberate gap (fixture construction + final assertion values), explicitly flagged as intentional and pointing at the exact existing fixture (`test_doctor.py`'s `_write_surface_fixture`) to model it on, following the same pattern used successfully in two prior plans this session. Every other step has complete, runnable code.

**Type consistency:** `cmd_compatibility`'s new `surface_kind` parameter name and position (4th, defaulted to `None`) is identical in both its Task 1 definition and Task 2's call site in `cli/sb/__main__.py`.

**Scope check:** 2 tasks, each independently testable; Task 2 depends only on Task 1 landing (its vendored copy needs `cmd_compatibility`'s new signature). No further decomposition needed.
