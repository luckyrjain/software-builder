"""Regression suite for `validate_repro_command` (design doc: B3 regression gate, Fix 1).

This is a direct regression test for a real, previously-exploitable vulnerability class: four
consecutive rounds of adversarial security review each found a distinct file-write/injection bypass
in earlier versions of this validator (wrong regex capture group, incomplete `=`-splitting, missed
colon-delimiter syntax). The function under test here is reproduced verbatim from the design's Fix 1
(revision 6) — do not re-derive or "improve" it; any change to the function itself should come with a
fresh adversarial review, not a local edit.
"""

import re

_REPRO_COMMAND_BASE = re.compile(
    r"^(pytest|python3 -m pytest|make [\w-]+|npm test|npm run [\w:-]+)((?: [\w./:=-]+)*)$"
)
_DANGEROUS_PATH_MARKER = re.compile(r"[\s=:-]/|\.\.")


def validate_repro_command(command: str | None) -> str | None:
    """Return the command if it matches a known, safe test-runner invocation shape with no
    absolute-path or traversal content anywhere; else None.

    Closes: shell metacharacters/chaining/substitution/redirection (round 1); absolute-path
    arguments and ".." traversal, closed via a single delimiter-agnostic substring search rather
    than delimiter-specific splitting (rounds 3-5 each found a distinct delimiter shape -- bare,
    "=", multi-"=", pytest-cov's "TYPE:DEST" colon syntax -- slip past a splitting-based check;
    this version doesn't split at all, so no delimiter syntax needs to be individually enumerated).

    "..": rejected as a literal substring anywhere in the command, not just as an isolated path
    segment -- deliberately broader than strictly necessary (a value like "1..2" would also be
    rejected) because the allowed character class is narrow enough (test-runner invocations only)
    that this is not expected to reject any legitimate repro command, and over-rejection fails
    safe into Condition 3's existing "not automatable" fallback, never into executing something
    dangerous.

    Does NOT and cannot close: a syntactically clean, dangerous-substring-free, relative-path-only
    command still executes whatever the test runner's own extensibility points define at the
    checked-out commit (conftest.py collection, a Makefile recipe body, npm lifecycle hooks). No
    command-shape validator can constrain what a test runner itself chooses to execute; only
    execution-environment sandboxing could, and this design does not add that (accepted residual
    risk, Open questions).
    """
    if command is None:
        return None
    if not _REPRO_COMMAND_BASE.fullmatch(command):
        return None
    if _DANGEROUS_PATH_MARKER.search(command):
        return None
    return command


# ---------------------------------------------------------------------------
# Negative cases: each of the 8 confirmed bypasses found across rounds 3-5 must be individually
# rejected (return None). Each gets its own named test so a future regression names exactly which
# bypass shape reappeared, rather than one parametrized failure with no distinguishing name.
# ---------------------------------------------------------------------------


def test_rejects_junitxml_absolute_path_bypass():
    assert validate_repro_command("pytest tests/test_foo.py --junitxml=/etc/cron.d/x") is None


def test_rejects_cov_report_html_colon_delimiter_bypass():
    assert (
        validate_repro_command(
            "pytest tests/test_foo.py --cov-report=html:/home/user/.ssh/authorized_keys"
        )
        is None
    )


def test_rejects_cov_report_xml_colon_delimiter_bypass():
    assert (
        validate_repro_command("pytest tests/test_foo.py --cov-report=xml:/etc/cron.d/evil")
        is None
    )


def test_rejects_basetemp_absolute_path_bypass():
    assert validate_repro_command("pytest tests/test_foo.py --basetemp=/some/dir") is None


def test_rejects_bare_absolute_path_argument():
    assert validate_repro_command("pytest /etc/passwd") is None


def test_rejects_relative_path_traversal():
    assert validate_repro_command("pytest tests/../../etc/passwd") is None


def test_rejects_cov_report_relative_traversal_bypass():
    assert validate_repro_command("pytest tests/test_foo.py --cov-report=html:../etc/passwd") is None


def test_rejects_multi_equals_absolute_path_bypass():
    assert validate_repro_command("pytest tests/test_foo.py --x=y=/etc/passwd") is None


# ---------------------------------------------------------------------------
# Positive cases: legitimate repro commands must still validate (return unchanged).
# ---------------------------------------------------------------------------


def test_accepts_pytest_single_file():
    command = "pytest tests/test_foo.py"
    assert validate_repro_command(command) == command


def test_accepts_pytest_single_test_id():
    command = "pytest tests/test_foo.py::test_bar"
    assert validate_repro_command(command) == command


def test_accepts_pytest_multiple_files():
    command = "pytest tests/test_a.py tests/test_b.py"
    assert validate_repro_command(command) == command


def test_accepts_make_test():
    command = "make test"
    assert validate_repro_command(command) == command


def test_accepts_npm_run_test_unit():
    command = "npm run test:unit"
    assert validate_repro_command(command) == command


# ---------------------------------------------------------------------------
# Baseline: None in, None out.
# ---------------------------------------------------------------------------


def test_none_command_returns_none():
    assert validate_repro_command(None) is None
