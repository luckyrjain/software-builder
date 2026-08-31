# Task 1 report: freeze legacy installer behavior

## Files changed

- `scripts/tests/test_install_legacy_golden.py` — added legacy installer golden tests.
- `.superpowers/sdd/2026-08-31-agent-compatibility-phase1/task-1-report.md` — this report.
- `scripts/tests/test_install_integration.sh` was not modified; no shared fixture helper was needed.

## Design choices

- Tests invoke `bash scripts/install.sh` from the repository root and capture stdout and stderr separately.
- Each subprocess receives an isolated temporary `HOME`; project-target cases use an exact temporary project root.
- The helper prepends the repository `.venv/bin` to `PATH`, allowing the installer’s existing `python3` subprocess calls to use the required local environment without changing production installer behavior.
- Dry-run cases assert exact destination and host text, both `all` destinations, and that no destination is created.
- The list test compares output to `scripts.install_support.registry_skill_ids(ROOT)`, while verify and invalid-agent tests assert non-zero status and the required error text.

## Commands and outputs

Initial required command (before the test helper selected `.venv/bin`):

```text
PYTHONPATH=. .venv/bin/python -m pytest -p no:cacheprovider scripts/tests/test_install_legacy_golden.py scripts/tests/test_install_safety.py -q
```

Output: `3 failed, 3 passed in 0.28s`; installer subprocesses resolved system `python3`, which lacked PyYAML (`ModuleNotFoundError: No module named 'yaml'`).

Required command after the test-only PATH adjustment:

```text
PYTHONPATH=. .venv/bin/python -m pytest -p no:cacheprovider scripts/tests/test_install_legacy_golden.py scripts/tests/test_install_safety.py -q
```

Output:

```text
......                                                                   [100%]
6 passed in 2.67s
```

Self-review checks:

```text
git diff --check
```

Output: no findings.

## Self-review

- Only the requested new golden-test module was added to the installer test area.
- Production installer files were not changed.
- The existing safety tests pass alongside the new tests.
- Tests are independent of the invoking user’s home directory and verify dry-run non-writing behavior.

## Concerns

- The installer hardcodes `python3`; on this checkout’s system PATH, that interpreter lacks PyYAML. The test-only PATH setup is required to honor the brief’s `.venv` test requirement. No production behavior was changed.

## Fix round: address review finding

### Files changed

- `scripts/tests/test_install_legacy_golden.py` — changed individual selector assertions and the `all` selector assertion to require exact output lines.
- `.superpowers/sdd/2026-08-31-agent-compatibility-phase1/task-1-report.md` — appended this fix-round record.

### Command and output

```text
PYTHONPATH=. .venv/bin/python -m pytest -p no:cacheprovider scripts/tests/test_install_legacy_golden.py scripts/tests/test_install_safety.py -q
```

Output:

```text
......                                                                   [100%]
6 passed in 3.04s
```

### Self-review

- The `all` case now requires stdout to contain exactly the two expected destination lines, so an extra destination cannot pass.
- Each individual selector now requires exactly one expected output line.
- No production installer behavior or unrelated files were changed.

### Concerns

- The existing test-only `.venv/bin` PATH adjustment remains necessary because the installer’s system `python3` lacks PyYAML.
