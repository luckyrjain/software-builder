"""Backward-compatible release manifest v2 parsing, trusted production-readiness
reuse, and conditional production-readiness invocation for release-readiness-checker.

Manifest v1 behavior (repo/service/since/release_ref, never invoking production
readiness) is completely preserved -- this module only adds behavior for entries
that carry v2-only fields. Everything here is pure, side-effect-free evidence
logic; registry wiring, dispatcher integration, and the real production-readiness-
review invocation live outside this module (`production_invoke` here is a
policy-level adapter only, matching scripts/production_readiness.py's own
`dispatch_child` convention).
"""

from __future__ import annotations

import copy
import dataclasses
import re
from typing import Any, Callable, Mapping, MutableMapping, Optional, Sequence

from scripts import production_readiness as pr
from scripts.registry.assessment_target import (
    normalize_environment_identity,
    normalize_repo_identity,
    normalize_service_identity,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_VERDICT_SEVERITY = {"READY": 0, "CONDITIONAL": 1, "UNKNOWN": 2, "NOT_READY": 3}

# Existing v1 checks (pr-review / k8s / incident) map their own outcome vocabulary
# onto the same four-state release verdict release-readiness-checker's Markdown
# contract already defines (reference/report-format.md) -- this table exists so
# the pure-python harness below can fold a per-check outcome into the overall
# release verdict the same way the real skill's fixed precedence does.
_CHECK_STATUS_VERDICT = {
    "PASS": "READY",
    "CLEAR": "READY",
    "READY": "READY",
    "CONDITIONAL": "CONDITIONAL",
    "FLAGGED": "CONDITIONAL",
    "NOT_READY": "NOT_READY",
    "BLOCKED": "NOT_READY",
    "FAIL": "NOT_READY",
    "UNKNOWN": "UNKNOWN",
    "NOT_RUN": "UNKNOWN",
}


def _safe_verdict(value: Any) -> str:
    """Coerce an external verdict value to a string, or "UNKNOWN" for any other
    shape (including an unhashable one like a list/dict).

    A verdict is read from a `trusted_reports` entry or a `production_invoke`
    return value -- both are external data this module does not control the
    shape of. Every downstream use compares it against `_VERDICT_SEVERITY`
    (a `dict`) via `in`/set-membership, which raises `TypeError` outright for
    an unhashable value; this must be sanitized once, at the point each
    verdict is first read, rather than guarded separately at every call site.
    """
    return value if isinstance(value, str) else "UNKNOWN"


def cap_release_verdict(current: str, production_verdict: str) -> str:
    """Worst-first cap: a release verdict is never better than production readiness's own.

    NOT_READY caps to NOT_READY, UNKNOWN caps to UNKNOWN, CONDITIONAL caps to at
    most CONDITIONAL, READY never downgrades an already-worse existing verdict.
    An unrecognized production verdict is never treated as the permissive READY.
    """
    production_verdict = _safe_verdict(production_verdict)
    if production_verdict not in _VERDICT_SEVERITY:
        production_verdict = "UNKNOWN"
    current = _safe_verdict(current)
    if current not in _VERDICT_SEVERITY:
        current = "UNKNOWN"
    return current if _VERDICT_SEVERITY[current] >= _VERDICT_SEVERITY[production_verdict] else production_verdict


# ---------------------------------------------------------------------------
# Manifest v1/v2 parsing (Included implementation slice 2)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ReleaseEntry:
    repo: Optional[str]
    service: Optional[str]
    since: Optional[str]
    release_ref: Optional[str] = None
    environment: Optional[str] = None
    source_revision: Optional[str] = None
    criticality: Optional[str] = None
    production_readiness_required: bool = False
    production_readiness_ref: Optional[str] = None

    def compatibility_projection(self) -> Mapping[str, Any]:
        """The exact v1 field/shape projection -- must equal `legacy_parse(entry)`
        for any v1-shaped entry, so v1 behavior is provably unchanged by the v2 parser.
        """
        return {
            "repo": self.repo,
            "service": self.service,
            "since": self.since,
            "release_ref": self.release_ref,
        }


def _is_required_flag(value: Any) -> bool:
    """True for the boolean True or the case-insensitive string "true".

    A manifest is YAML/JSON text; `production_readiness_required: true` parses
    to the real bool in normal YAML, but a quoted `"true"` (a plausible
    hand-authoring or templating mistake) must not silently degrade the entry
    to v1 behavior -- inputs.md's own documented invariant is that this flag
    "never silently skips the gate." Nothing else truthy (a nonzero int, an
    arbitrary non-empty string) is accepted; an unrecognized shape stays False
    rather than guessing, matching this module's fail-closed convention.
    """
    if value is True:
        return True
    return isinstance(value, str) and value.strip().lower() == "true"


def _as_str(value: Any) -> Optional[str]:
    """Coerce a manifest field to a string, or None for any other shape.

    `release_manifest` is caller-supplied text; a malformed field (an int, a
    list, ...) must degrade this one field to "absent" and let the existing
    None-handling everywhere downstream (`if not parsed.repo: ... UNKNOWN`)
    take over, never raise. Without this, a non-string `repo`/`service`/
    `environment`/`release_ref` would reach `normalize_repo_identity`/
    `normalize_service_identity`/`same_environment`/`_looks_like_source_revision`,
    all of which raise TypeError on a non-string input -- crashing the whole
    `run_release` call over one malformed entry instead of failing closed on
    just that entry, contrary to this codebase's pervasive fail-closed
    convention (see `scripts/production_readiness.py`'s own `_as_mapping`/
    `_is_strong_authority`/`_target_of`).
    """
    return value if isinstance(value, str) else None


def parse_release_entry(entry: Mapping[str, Any]) -> ReleaseEntry:
    entry = pr._as_mapping(entry)
    return ReleaseEntry(
        repo=_as_str(entry.get("repo")),
        service=_as_str(entry.get("service")),
        since=_as_str(entry.get("since")),
        release_ref=_as_str(entry.get("release_ref")),
        environment=_as_str(entry.get("environment")),
        source_revision=_as_str(entry.get("source_revision")),
        criticality=_as_str(entry.get("criticality")),
        production_readiness_required=_is_required_flag(entry.get("production_readiness_required")),
        production_readiness_ref=_as_str(entry.get("production_readiness_ref")),
    )


def _normalize_manifest(manifest: Any) -> list:
    if manifest is None:
        return []
    if isinstance(manifest, Mapping):
        return [manifest]
    if isinstance(manifest, Sequence) and not isinstance(manifest, (str, bytes)):
        # A non-mapping item (a string, a number, None, ...) is dropped here
        # rather than parsed into a phantom all-None ReleaseEntry -- a
        # manifest that is a non-empty list of nothing but garbage must still
        # reach run_release's own "no entries -> BLOCKED" hard stop, the same
        # as a literally empty manifest, rather than silently generating
        # NOT_RUN check rows for unidentifiable services.
        return [item for item in manifest if isinstance(item, Mapping)]
    return []


# ---------------------------------------------------------------------------
# Trusted reuse / matching (Included implementation slice 3)
# ---------------------------------------------------------------------------


def classify_report_for_release(report: Mapping[str, Any]) -> MutableMapping[str, Any]:
    """A schema-valid production_readiness_report is not automatically gate-trusted.

    Only a runtime-validated/direct-child acquisition can satisfy a release gate --
    a caller-supplied or repository-file artifact is discovery evidence only, per
    the design's "no generic artifact store / file self-attestation" invariant.
    """
    report = pr._as_mapping(report)
    if report.get("producer_trusted", True) is not True:
        return {"trusted_for_gate": False, "reason": "untrusted_producer"}
    acquisition = report.get("acquisition")
    trusted = acquisition in ("direct_child", "runtime_validated")
    return {
        "trusted_for_gate": trusted,
        "reason": "" if trusted else "untrusted_acquisition",
    }


def _safe_normalize_repo(value: Any) -> Optional[str]:
    """`normalize_repo_identity` raises TypeError for a non-string input; a
    report's own repo field is external data (trusted_reports / a
    production_invoke return value), never guaranteed to be a string, unlike
    a parsed manifest entry's already-`_as_str`-coerced `repo`.
    """
    return normalize_repo_identity(value) if isinstance(value, str) else None


def _safe_normalize_service(value: Any) -> Optional[str]:
    """See `_safe_normalize_repo` -- same rationale for `normalize_service_identity`."""
    return normalize_service_identity(value) if isinstance(value, str) else None


def _safe_normalize_environment(value: Any) -> Optional[str]:
    """See `_safe_normalize_repo` -- same rationale for `normalize_environment_identity`."""
    return normalize_environment_identity(value) if isinstance(value, str) else None


def match_release_report(entry: Any, report: Mapping[str, Any]) -> MutableMapping[str, Any]:
    """Deployable-scoped identity match: canonical repo/service, exact
    environment whenever either side declares one, exact release_ref ==
    report's deployable target, exact source_revision when the entry
    declares one, and an immutable identity anchor (a real digest/SHA, never
    a mutable tag) somewhere in that identity. No fuzzy matching.
    """
    parsed = entry if isinstance(entry, ReleaseEntry) else parse_release_entry(entry)
    report = pr._as_mapping(report)
    target = pr._target_of(report) or report

    if not parsed.repo or not parsed.service:
        return {"status": "UNKNOWN", "reason": "missing_candidate_identity"}

    normalized_report_repo = _safe_normalize_repo(target.get("repo"))
    if not normalized_report_repo or normalized_report_repo != _safe_normalize_repo(parsed.repo):
        return {"status": "UNKNOWN", "reason": "repo_mismatch"}

    normalized_report_service = _safe_normalize_service(target.get("service"))
    if not normalized_report_service or normalized_report_service != _safe_normalize_service(parsed.service):
        return {"status": "UNKNOWN", "reason": "service_mismatch"}

    report_env = target.get("environment")
    if parsed.environment is not None or report_env is not None:
        # A final production_readiness_report requires the exact candidate
        # environment (design v10 Sec8.11) -- an entry that simply omits
        # `environment` must never silently reuse a report produced for SOME
        # OTHER declared environment. Only "neither side declares one" is a
        # harmless match; any other combination (one side null, or both
        # non-null but different) is a mismatch. `pr._safe_same_environment`
        # (not the raw `same_environment`) because `report_env` is external
        # data that need not be a string.
        if parsed.environment is None or report_env is None or not pr._safe_same_environment(parsed.environment, report_env):
            return {"status": "UNKNOWN", "reason": "environment_mismatch"}

    if not parsed.release_ref:
        return {"status": "UNKNOWN", "reason": "missing_release_ref"}
    report_head = target.get("head_revision_or_digest")
    if not report_head or report_head != parsed.release_ref:
        return {"status": "UNKNOWN", "reason": "release_ref_mismatch"}

    if parsed.source_revision is not None:
        # Flat-only -- genuinely, not merely "flat-first" -- deliberately NOT
        # production_readiness.py's generic _effective_source_revision: that
        # helper's nested-target fallback chain treats a candidate's own
        # head_revision_or_digest as a stand-in for "revision" when no nested
        # source_revision is present -- correct for a generic candidate
        # object, but wrong here, since production_readiness_report's own
        # schema (composition_contracts.yaml) declares source_revision as a
        # top-level sibling of assessment_target, never nested inside it. A
        # report that omits the flat field is schema-nonconforming and must
        # never have its source_revision inferred from `target` (a prior
        # `or target.get("source_revision")` fallback here reopened exactly
        # this nested/flat ambiguity; a well-formed report's own
        # `head_revision_or_digest` inside `target` could otherwise be misread
        # as a source revision it never actually declared).
        report_source_revision = report.get("source_revision")
        if report_source_revision != parsed.source_revision:
            return {"status": "UNKNOWN", "reason": "source_revision_mismatch"}

    if not _release_ref_is_immutable_identity(parsed.release_ref):
        # release_ref is the actual deployable this match is keyed on (the
        # exact-string check against report_head above) -- an exact string
        # match against a mutable, non-identity-pinning tag (`latest`/`main`/
        # `v1.2.3`) is not proof this report was ever produced for the SAME
        # concrete content, since the tag can be repointed between when the
        # report was produced and now. Critically, a validly SHA-shaped
        # source_revision must NEVER redeem a mutable release_ref for reuse
        # purposes: unlike the invoke path (where the freshly-invoked child
        # independently re-validates build provenance linking source_revision
        # to today's actual deployable via validate_build_provenance), reuse
        # performs no such re-verification -- it is pure static string
        # matching against a possibly long-stale report, so a stale/replayed
        # source_revision value that happens to also match tells us nothing
        # about what the mutable tag resolves to right now.
        return {"status": "UNKNOWN", "reason": "unpinned_identity"}

    return {"status": "MATCH"}


# ---------------------------------------------------------------------------
# Conditional production-readiness invocation (Included implementation slice 4)
# ---------------------------------------------------------------------------


_GIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")
# The algorithm component is deliberately an explicit allowlist of genuine,
# registered content-hash algorithms, NOT an open-ended `[a-z0-9]+` -- this
# module performs no actual hash verification, so an unrecognized "algorithm"
# name provides zero cryptographic assurance over arbitrary text. An
# open-ended component would make an ordinary, fully mutable `name:tag`
# container reference (e.g. `nightly-build:<40 hex chars>` -- a common CI
# convention of tagging an image with a commit SHA) syntactically
# indistinguishable from a genuine `algo:hexdigest` content digest whenever
# the tag happens to be hex-shaped. The hex-length is likewise exact per
# algorithm (sha256=64, sha384=96, sha512=128 hex chars), not merely ">=32"
# for all three interchangeably -- an open length range would reopen this
# exact same reference-vs-tag ambiguity whenever the "name" component of a
# mutable tag happens to literally be one of the three allowlisted words
# (e.g. a repository or artifact store named `sha256` carrying a mutable,
# git-SHA-style tag `sha256:<40-hex-char-tag>` -- wrong length for a real
# sha256 digest, but still hex-shaped and thus still indistinguishable from
# one under an open-ended length).
_IMMUTABLE_DIGEST_RE = re.compile(
    r"^(?:sha256:[0-9a-fA-F]{64}|sha384:[0-9a-fA-F]{96}|sha512:[0-9a-fA-F]{128})$"
)


def _looks_like_source_revision(ref: str) -> bool:
    """True only for a ref that is actually shaped like a git commit SHA.

    design v10 Sec9 defines `release_ref` as "the immutable deployable ref
    (commit SHA when that is the deployable, otherwise image/artifact
    digest)". A colon-free string is not automatically a SHA -- a mutable,
    non-identity-pinning tag like "latest"/"main"/"staging" is colon-free too,
    and per Sec9.2, "if source_revision is absent ... and cannot be
    authoritatively resolved, do not invoke; release readiness is UNKNOWN".
    Requiring an actual hex-SHA shape (not merely "no colon") is what makes
    that non-source-revision-shaped case correctly insufficient below.
    """
    return bool(_GIT_SHA_RE.fullmatch(ref))


def _looks_like_immutable_digest(ref: str) -> bool:
    """True only for a ref shaped like a real content-addressed digest
    (`algo:hexhash`, e.g. `sha256:...`), as opposed to a mutable tag that
    merely lacks a colon.

    Unlike a git SHA, a digest is never itself sufficient to *invoke*
    production readiness (there is no source_revision to prove code-review/CI
    evidence against) -- but it IS a legitimate anchor for *reusing* an
    already-produced report keyed to that same immutable content hash, even
    with no source_revision separately known. See
    `_release_ref_is_immutable_identity`.
    """
    return bool(_IMMUTABLE_DIGEST_RE.fullmatch(ref))


def _release_ref_is_immutable_identity(release_ref: Optional[str]) -> bool:
    """True only when release_ref ITSELF -- never redeemable by a merely
    string-matching source_revision -- is pinned to something immutable.

    Used only to gate reuse (`match_release_report`). release_ref is the
    actual deployable identity that match already checks via exact string
    equality against the report's own `head_revision_or_digest`; if
    release_ref is a mutable tag (`latest`, `main`, `v1.2.3`), an exact
    string match today proves nothing about whether the tag still resolves
    to the same content it did when the trusted report was produced -- even
    when a SHA-shaped source_revision ALSO happens to match (e.g. a stale or
    replayed value copied alongside the tag). Unlike the invoke gate
    (`_candidate_identity_sufficient`), where the freshly-invoked child
    independently re-validates build provenance linking source_revision to
    today's actual deployable, reuse performs no such re-verification -- it
    is pure static string matching against a possibly long-stale report, so
    source_revision can never substitute for release_ref's own immutability
    here. A real digest qualifies (no source_revision needed for reuse); a
    real git SHA also qualifies.
    """
    if not release_ref:
        return False
    return _looks_like_source_revision(release_ref) or _looks_like_immutable_digest(release_ref)


def _candidate_identity_sufficient(entry: ReleaseEntry) -> bool:
    """True only when enough identity exists to safely invoke production readiness.

    repo and service are mandatory -- match_release_report already treats a
    repo-less/service-less candidate as unidentifiable ("missing_candidate_
    identity"), and invoking the real (expensive) production-readiness-review
    child for a candidate that can never be identified downstream is a wasted
    call, not merely a redundant check.

    A release_ref that is itself shaped like a source revision (a git commit
    SHA) needs nothing else beyond that. Anything else -- a build/image
    digest (`sha256:...`), a mutable tag (`latest`, `main`, a release name),
    or arbitrary caller text -- needs an explicit source_revision; without
    one, there is no way to prove code-review/CI evidence about *this*
    deployable, so invocation must not be attempted at all. (Reuse has
    different, more permissive rules for a bare digest release_ref -- see
    `match_release_report`/`_release_ref_is_immutable_identity`.)

    An explicit source_revision is itself required to look like a real git
    commit SHA -- design v10 defines source_revision as "the immutable
    source-control revision that code review and CI prove," and
    source_revision is untrusted `release_manifest` text (`_as_str`-coerced,
    same trust boundary as release_ref), so a mutable tag or arbitrary text
    supplied there is exactly as unproven an identity as one supplied via
    release_ref, and must not be treated as sufficient to invoke. Here (only
    here, unlike reuse) a validly-shaped source_revision legitimately
    substitutes for release_ref's own shape, because the invoked child
    independently re-validates build provenance linking that source revision
    to today's actual deployable -- there is no equivalent re-verification on
    the reuse path.
    """
    if not entry.repo or not entry.service:
        return False
    if not entry.release_ref:
        return False
    if entry.source_revision:
        return _looks_like_source_revision(entry.source_revision)
    return _looks_like_source_revision(entry.release_ref)


def _candidate_from_entry(entry: ReleaseEntry) -> MutableMapping[str, Any]:
    # criticality is deliberately NOT included here. assessment_target/candidate
    # fields are treated as the identity this assessment is scoped to; a manifest-
    # declared criticality is untrusted caller text (release_manifest is caller-
    # supplied data, not instructions) and per design v10 Sec9.2, release
    # readiness passes "criticality when authoritative/known" -- never an
    # unvetted manifest claim folded in as if it were identity. It is instead
    # surfaced via build_assessment_context's inputs/input_provenance, tagged
    # "caller" authority like `since`, so the invoked child can apply its own
    # documented authoritative-wins-over-caller precedence (never silently
    # lowering a tier0/tier1 authoritative value to a caller's lower claim).
    return {
        "repo": entry.repo,
        "service": entry.service,
        "environment": entry.environment,
        "source_revision": entry.source_revision,
        "head_revision_or_digest": entry.release_ref,
        "source_type": "release_candidate",
    }


def _coverage_is_trustworthy_and_complete(coverage: Optional[Mapping[str, Any]]) -> bool:
    """A release-assembled code_review_coverage bundle is usable only when it is
    both complete AND carries a host/runtime-authoritative acquisition.

    `coverage` must NEVER be sourced from a caller-supplied/manifest-text channel
    (see `resolve_production_readiness`'s own `code_review_coverage` parameter,
    which is deliberately kept separate from the parsed manifest entry) -- but
    even so, this checks the acquisition field defensively, the same way
    `scripts/production_readiness.py`'s `validate_code_review_coverage` gates its
    own `coverage.get("acquisition")` via `_is_host_or_runtime_acquisition`. A
    bundle claiming `status: COMPLETE` with no (or a weak) acquisition is never
    trusted merely because it claims completeness -- that is exactly the
    self-attestation this whole module exists to prevent. A bundle that is
    internally inconsistent (claims `COMPLETE` while still listing
    `uncovered_change_refs`) is likewise never trusted merely because it
    claims completeness -- mirroring `validate_code_review_coverage`'s own
    `not coverage.get("uncovered_change_refs")` check, which every bundle
    `build_code_review_coverage` itself produces already satisfies by
    construction, but a hand-built or otherwise-produced bundle might not.
    """
    coverage = pr._as_mapping(coverage) if coverage is not None else None
    if not coverage:
        return False
    if coverage.get("status") != "COMPLETE":
        return False
    if coverage.get("uncovered_change_refs"):
        return False
    return pr._is_host_or_runtime_acquisition(coverage.get("acquisition"))


def _coverage_for_entry(
    entry: ReleaseEntry, coverage: Optional[Mapping[str, Any]]
) -> Optional[Mapping[str, Any]]:
    """Scope a trusted-runtime `code_review_coverage` bundle to the exact entry
    it was assembled for.

    `run_release` accepts one `code_review_coverage` bundle per call, but a
    multi-entry manifest can require production readiness for more than one
    entry, each with its own source revision. Unlike `trusted_reports` (which
    is already identity-matched per entry via `match_release_report`), a bare
    `code_review_coverage` value has no such per-entry binding by construction
    -- without this check, a bundle assembled for one entry would be reused
    unmodified for every other entry in the same run, laundering review
    evidence for the wrong candidate into that other candidate's own verdict.
    A coverage bundle only applies when its own `repo`, `service`, AND
    `candidate_source_revision` all exactly match this entry's -- a
    source-revision string alone is caller-controlled manifest text and, in a
    multi-repo/multi-service manifest, is not itself proof the bundle was
    assembled for *this* candidate rather than a different one that happens
    to declare the same revision string (round-2's original fix). A bundle
    that omits `repo`/`service` entirely cannot be safely scoped by
    source_revision alone either, so it is likewise never applied to any
    entry -- `build_code_review_coverage`'s own `repo`/`service` parameters
    exist specifically so the trusted harness always supplies them. Any
    non-match is treated as not supplied for this entry (never as "supplied
    but untrustworthy" -- production-readiness-review remains free to derive
    its own coverage).
    """
    coverage = pr._as_mapping(coverage) if coverage is not None else None
    if not coverage:
        return None
    if not entry.source_revision or coverage.get("candidate_source_revision") != entry.source_revision:
        return None
    coverage_repo = coverage.get("repo")
    coverage_service = coverage.get("service")
    if not coverage_repo or not coverage_service:
        return None
    normalized_coverage_repo = _safe_normalize_repo(coverage_repo)
    if not normalized_coverage_repo or normalized_coverage_repo != _safe_normalize_repo(entry.repo):
        return None
    normalized_coverage_service = _safe_normalize_service(coverage_service)
    if not normalized_coverage_service or normalized_coverage_service != _safe_normalize_service(entry.service):
        return None
    return coverage


def build_assessment_context(
    entry: ReleaseEntry,
    *,
    candidate: Optional[Mapping[str, Any]] = None,
    code_review_coverage: Optional[Mapping[str, Any]] = None,
) -> MutableMapping[str, Any]:
    candidate = dict(candidate) if candidate is not None else _candidate_from_entry(entry)
    inputs: MutableMapping[str, Any] = {}
    input_provenance: MutableMapping[str, Any] = {}
    evidence_refs: list = []
    if entry.since:
        # Release base/since context for the child's own impact discovery
        # (design v10 Sec9.2) -- contextual scoping data, not a trust-bearing
        # claim, so "caller" authority is the honest label for it.
        inputs["since"] = entry.since
        input_provenance["since"] = {"authority": "caller", "evidence_refs": []}
    if entry.criticality:
        # A manifest-declared criticality is untrusted caller text -- this
        # module has no authoritative source (e.g. host.service.metadata.read)
        # to check it against, so it can never be tagged anything but "caller"
        # authority here. Per design v10 Sec9.2 ("criticality when
        # authoritative/known") and production-readiness-review's own
        # documented precedence (an authoritative tier always wins over a
        # caller's lower-stakes claim), the invoked child -- not this caller --
        # is responsible for resolving it against any authoritative evidence
        # it can independently obtain, defaulting to the strictest "unknown"
        # tier when it cannot.
        inputs["criticality"] = entry.criticality
        input_provenance["criticality"] = {"authority": "caller", "evidence_refs": []}
    if code_review_coverage is not None:
        # A defensive deep copy, mirroring `candidate`'s own `dict(candidate)`
        # copy above -- `production_invoke` is a plain caller-supplied
        # Callable (this module's own header docstring notwithstanding, it
        # has no enforcement mechanism preventing a careless or buggy
        # implementation from mutating whatever mapping it's handed). Without
        # a copy, an invoke that mutates `assessment_context["inputs"]
        # ["code_review_coverage"]` (or one of its nested mutable lists, e.g.
        # `trusted_review_refs`) would corrupt the CALLER's own trusted-
        # runtime-supplied bundle in place -- and `run_release` passes this
        # same object to every entry in a multi-entry manifest and to every
        # future call that reuses it, so one entry's invoke could silently
        # flip a later entry's (or a later run's) resolved verdict.
        code_review_coverage = copy.deepcopy(code_review_coverage) if isinstance(code_review_coverage, Mapping) else code_review_coverage
        inputs["code_review_coverage"] = code_review_coverage
        coverage_mapping = pr._as_mapping(code_review_coverage)
        trustworthy = _coverage_is_trustworthy_and_complete(code_review_coverage)
        authority = "trusted_runtime" if trustworthy else "caller"
        # When the bundle is trustworthy, propagate refs from
        # `trusted_review_refs` -- the field `_coverage_is_trustworthy_and_
        # complete`/`validate_code_review_coverage` actually vet -- never
        # from the bundle's own independently-settable `evidence_refs`.
        # `build_code_review_coverage` always sets `evidence_refs` to a copy
        # of `trusted_review_refs`, so this changes nothing for a
        # properly-constructed bundle; but a hand-built or otherwise-produced
        # bundle could satisfy every structural trustworthiness check
        # (status/uncovered_change_refs/acquisition) while declaring an
        # `evidence_refs` list unrelated to what was actually reviewed --
        # stamping that unrelated content "trusted_runtime" would be exactly
        # the kind of authority-tag mismatch this module's evidence-authority
        # discipline exists to prevent. An untrustworthy bundle's
        # `evidence_refs` remains merely descriptive caller text either way.
        refs_field = "trusted_review_refs" if trustworthy else "evidence_refs"
        raw_refs = coverage_mapping.get(refs_field)
        # A wrong-shaped value (a bare string, a mapping) must never be
        # silently shredded by `list(...)` into characters or dict keys --
        # only a genuine list is ever treated as a ref list.
        coverage_refs = list(raw_refs) if isinstance(raw_refs, list) else []
        input_provenance["code_review_coverage"] = {
            "authority": authority,
            "evidence_refs": coverage_refs,
        }
        evidence_refs.extend(coverage_refs)
    return {
        "assessment_target": candidate,
        "inputs": inputs,
        "input_provenance": input_provenance,
        "evidence_refs": evidence_refs,
        "unresolved": [],
    }


def resolve_production_readiness(
    entry: Any,
    *,
    trusted_reports: Optional[Sequence[Mapping[str, Any]]] = None,
    production_invoke: Optional[Callable[..., Any]] = None,
    code_review_coverage: Optional[Mapping[str, Any]] = None,
) -> MutableMapping[str, Any]:
    """Reuse-first, conditional-invoke resolution for one v2 manifest entry.

    `code_review_coverage` is a trusted-runtime input the caller (release-
    readiness-checker's own orchestration, after real SCM enumeration) supplies
    out of band -- deliberately NOT a field read off the untrusted manifest-entry
    mapping, so a `release_manifest` author can never inject a self-attested
    "already reviewed, trust me" coverage bundle merely by adding a key to their
    YAML. See `_coverage_is_trustworthy_and_complete` for the defensive
    acquisition check applied on top of that structural separation, and
    `_coverage_for_entry` for the per-entry source_revision scoping that keeps
    one entry's coverage from leaking into another entry's verdict in the same
    multi-entry `run_release` call.

    Never invoked at all for a v1 entry (production_readiness_required defaults
    False) -- callers must check that flag before calling this, matching
    `run_release`'s own behavior below.
    """
    parsed = entry if isinstance(entry, ReleaseEntry) else parse_release_entry(entry)
    if not parsed.production_readiness_required:
        return {"status": "NOT_REQUIRED", "source": None, "report": None}

    # 1. Reuse first. A trusted, fresh, deployable-scoped report always wins,
    # regardless of whether release-assembled code-review coverage is ready --
    # per release-readiness-checker/workflow/run-check.md Sec6, reuse is
    # attempted before the coverage-driven invoke gate below, never after it.
    matches = []
    for report in trusted_reports or ():
        classification = classify_report_for_release(report)
        if not classification["trusted_for_gate"]:
            continue
        match = match_release_report(parsed, report)
        if match["status"] == "MATCH":
            matches.append(report)

    if matches:
        # Conflict detection runs on the full unpinned match set. The pin is
        # caller/manifest-supplied text -- untrusted -- and must never be able
        # to silently resolve a genuine disagreement between two trusted,
        # identity-matching reports by hiding the one it doesn't name.
        #
        # _safe_verdict before the set/membership operations below: an
        # unhashable raw verdict (a list/dict a malformed report carries)
        # would otherwise raise TypeError building this very set.
        verdicts = {_safe_verdict(r.get("verdict")) for r in matches}
        if len(verdicts) > 1:
            # Two trusted, identity-matching reports that disagree are
            # conflicting authoritative evidence -- per the evidence-authority
            # policy, this is never silently resolved by picking one; it is
            # UNKNOWN until reconciled by a fresher/pinned report.
            return {"status": "UNKNOWN", "source": None, "report": None}

        pinned = matches
        if parsed.production_readiness_ref is not None:
            # An explicit pin selects which of the already-agreeing report
            # objects to attribute -- applied only after the conflict check
            # above. A pin that resolves to nothing (a typo, a stale/rotated
            # ref, or untrusted manifest text an attacker deliberately points
            # at nothing) must never suppress reuse of evidence that is
            # otherwise trusted and unanimous: since every remaining match
            # already agrees in verdict, which one gets attributed cannot
            # change the resolved status, so falling back to the full
            # agreeing set is safe and keeps a non-resolving pin from
            # discarding known trusted evidence in favor of a fresh
            # invocation (or UNKNOWN).
            by_ref = [r for r in matches if r.get("report_ref") == parsed.production_readiness_ref]
            if by_ref:
                pinned = by_ref

        return {"status": _safe_verdict(pinned[0].get("verdict")), "source": "REUSED", "report": pinned[0]}

    # 2. Otherwise, invoke only when safe.
    if not _candidate_identity_sufficient(parsed):
        return {"status": "UNKNOWN", "source": None, "report": None}

    scoped_coverage = _coverage_for_entry(parsed, code_review_coverage)
    if scoped_coverage is not None and not _coverage_is_trustworthy_and_complete(scoped_coverage):
        # Task 5.5: release-assembled code-review coverage that is known
        # incomplete (or not host/runtime-authoritative) must not trigger a
        # child invocation merely to obtain a predictable UNKNOWN -- and must
        # never be "fixed" by letting the child revisit pr-review, which would
        # both duplicate the release root's own review pass and risk defeating
        # the composition recursion guard.
        return {"status": "UNKNOWN", "source": None, "report": None}

    if production_invoke is None:
        return {"status": "UNKNOWN", "source": None, "report": None}

    candidate = _candidate_from_entry(parsed)
    assessment_context = build_assessment_context(parsed, candidate=candidate, code_review_coverage=scoped_coverage)
    invoked = production_invoke(candidate, assessment_context=assessment_context)
    if invoked is None:
        return {"status": "UNKNOWN", "source": None, "report": None}

    classification = classify_report_for_release(invoked)
    if not classification["trusted_for_gate"]:
        return {"status": "UNKNOWN", "source": None, "report": None}
    match = match_release_report(parsed, invoked)
    if match["status"] != "MATCH":
        return {"status": "UNKNOWN", "source": None, "report": None}
    return {"status": _safe_verdict(invoked.get("verdict")), "source": "INVOKED", "report": invoked}


# ---------------------------------------------------------------------------
# Code-review coverage handoff (Task 5)
# ---------------------------------------------------------------------------


def _change_ref_id(change: Any) -> Optional[str]:
    """Resolve one included-change entry to its ref string, or None when it's
    malformed/unresolvable (wrong key, non-mapping, empty string, ...).

    A malformed entry is never dropped by its caller -- see
    `build_code_review_coverage`, which unconditionally treats a `None`
    result as uncovered without ever comparing it by string equality against
    `trusted_review_refs`/`integrated_revisions`. Returning a fixed,
    predictable placeholder string here instead (as an earlier version of
    this function did) would let a real ref or `integrated_revisions` value
    that happens to collide with that exact placeholder text silently launder
    the malformed entry into "covered" -- exactly the self-attestation-style
    outcome this function exists to prevent. `None` can never collide with
    any string, so no such coincidence is possible.
    """
    if isinstance(change, Mapping):
        ref = change.get("ref")
        if isinstance(ref, str) and ref:
            return ref
    elif isinstance(change, str) and change:
        return change
    return None


def build_code_review_coverage(
    *,
    candidate_source_revision: str,
    included_change_refs: Sequence[Any],
    trusted_review_refs: Sequence[str],
    repo: Optional[str] = None,
    service: Optional[str] = None,
    integrated_revisions: Optional[Mapping[str, str]] = None,
    acquisition: str = "authoritative_host",
) -> MutableMapping[str, Any]:
    """Enumerate every material change in range and its trusted review coverage.

    `included_change_refs` must include every material change type -- merged
    PR/MR objects, direct commits, cherry-picks, and reverts alike; the caller
    (release-readiness-checker's own authoritative SCM enumeration) is
    responsible for never silently omitting one of those kinds.

    `integrated_revisions` is the ONLY source of PR/MR-to-merge-commit linkage
    this function trusts -- it must come from authoritative SCM merge/squash
    metadata. A change's own claimed/forged linkage (e.g. an untrusted
    `claimed_integrated_revision` field a caller attached to a ref mapping) is
    never consulted, so a forged integrated revision has no effect.

    `repo`/`service` are optional parameters here but effectively mandatory
    for the resulting bundle to ever be usable: `_coverage_for_entry` requires
    both to be present and to canonically match an entry before applying this
    bundle to it at all -- a bare `candidate_source_revision` string is
    manifest-entry text and, in a multi-repo/multi-service manifest, is not by
    itself proof of which candidate this bundle covers. Omitting them here
    means this bundle can never be reused via `run_release`'s
    `code_review_coverage` parameter for any entry.
    """
    resolved_refs = [_change_ref_id(change) for change in included_change_refs]
    # A malformed/unresolvable entry gets a synthetic placeholder for display
    # purposes only (`included_change_refs`/`uncovered_change_refs`) -- it is
    # never dropped, so a manifest with N real changes and one malformed
    # entry can never look identical to one with N-1 changes. The placeholder
    # never participates in the covered/uncovered decision itself; see
    # `_change_ref_id` and the `resolved_refs[index] is None` check below.
    included_refs = [
        ref if ref is not None else f"__unresolvable_change_{index}__"
        for index, ref in enumerate(resolved_refs)
    ]
    # `trusted_review_refs` comes from the same authoritative-SCM-enumeration
    # trust boundary as `included_change_refs` (whose own malformed entries
    # `_change_ref_id` already hardens against) -- a non-string/unhashable
    # item here must not crash `set(...)`; it simply can never match any real
    # ref, so it's silently excluded from `reviewed` rather than raising.
    reviewed = {ref for ref in trusted_review_refs if isinstance(ref, str) and ref}
    integrated_revisions = dict(integrated_revisions or {})

    def _is_covered(ref: str) -> bool:
        if ref in reviewed:
            return True
        integrated = integrated_revisions.get(ref)
        # isinstance guard before the `in` membership test: an unhashable
        # integrated_revisions value (a list/dict instead of a string) must
        # never reach `integrated in reviewed`, which would raise TypeError.
        return isinstance(integrated, str) and bool(integrated) and integrated in reviewed

    # A malformed entry (resolved_refs[index] is None) is unconditionally
    # uncovered -- never run through `_is_covered`, which compares by string
    # equality and would otherwise be exploitable via a coincidental (or
    # adversarially chosen) real ref/integrated-revision value matching that
    # entry's own display placeholder.
    uncovered = [
        included_refs[index]
        for index, ref in enumerate(resolved_refs)
        if ref is None or not _is_covered(ref)
    ]
    if not included_refs:
        status = "UNKNOWN"
    elif uncovered:
        status = "PARTIAL"
    else:
        status = "COMPLETE"

    return {
        "candidate_source_revision": candidate_source_revision,
        "repo": repo,
        "service": service,
        "status": status,
        "included_change_refs": included_refs,
        "trusted_review_refs": list(trusted_review_refs),
        "uncovered_change_refs": uncovered,
        "evidence_refs": list(trusted_review_refs),
        "acquisition": acquisition,
    }


# ---------------------------------------------------------------------------
# Release-result envelope + execution-status semantics (Task 7.5)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class SkillResult:
    status: str
    evidence_status: str = "UNKNOWN"


@dataclasses.dataclass
class ReleaseResult:
    verdict: str
    skill_result: SkillResult
    production_readiness_source: Optional[str] = None
    production_readiness: Optional[str] = None
    # Every entry that actually required production readiness in this run,
    # each as {"repo", "service", "source", "verdict"} -- `production_readiness`/
    # `production_readiness_source` above are a convenience projection of
    # whichever ONE entry here is most severe (see `run_release`), for the
    # common single-required-entry case every existing caller assumes; a
    # multi-entry manifest with more than one required entry should read this
    # list instead of assuming the top-level fields describe every entry.
    production_readiness_results: list = dataclasses.field(default_factory=list)
    checks: list = dataclasses.field(default_factory=list)
    candidate_changed_during_review: bool = False

    @property
    def overall(self) -> str:
        return self.verdict

    def __getitem__(self, key: str) -> Any:
        if key == "verdict":
            return self.verdict
        try:
            return getattr(self, key)
        except AttributeError as exc:
            # Mapping-like access must raise the conventional KeyError, not
            # leak the attribute-lookup's own AttributeError -- code using the
            # idiomatic `try: result[key] except KeyError` pattern on this
            # dict-like object must actually catch the miss.
            raise KeyError(key) from exc

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


def finalize_release(pre: Mapping[str, Any]) -> ReleaseResult:
    """Execution status vs decision status, mirroring production_readiness.py's own
    axis split: a resolved NOT_READY is a SUCCESSFUL analysis; an unresolved
    required dimension makes the result PARTIAL regardless of what the (possibly
    already-worst-case) verdict is; an empty manifest is BLOCKED, never FAILED.
    """
    pre = pr._as_mapping(pre)
    overall = pre.get("overall", "UNKNOWN")
    unknown_dimensions = list(pre.get("unknown_dimensions") or [])
    status = "PARTIAL" if unknown_dimensions else "SUCCESS"
    evidence_status = "UNKNOWN" if unknown_dimensions else "OBSERVED"
    return ReleaseResult(
        verdict=overall,
        skill_result=SkillResult(status=status, evidence_status=evidence_status),
        production_readiness_source=pre.get("production_readiness_source"),
        production_readiness=pre.get("production_readiness"),
        production_readiness_results=list(pre.get("production_readiness_results") or []),
        checks=list(pre.get("checks") or []),
        candidate_changed_during_review=bool(pre.get("candidate_changed_during_review", False)),
    )


# ---------------------------------------------------------------------------
# Top-level orchestration entry (Task 1 + Task 6 aggregate caps + Task 6.5 fence)
# ---------------------------------------------------------------------------

_EXISTING_CHECKS = ("pr_review", "k8s", "incident")


def _normalized_ref_pair_key(repo: Any, service: Any, environment: Any) -> tuple:
    return (
        _safe_normalize_repo(repo),
        _safe_normalize_service(service),
        _safe_normalize_environment(environment),
    )


def _resolve_ref_pair_mapping(mapping: Mapping[Any, Any], normalized_key: tuple) -> Any:
    # A raw `dict.get(key)` on the untrusted, merely-`_as_str`-coerced entry
    # identity would miss whenever the mapping's own keys use a differently
    # formatted-but-identity-equivalent spelling (a repo string with/without
    # a `.git` suffix, a differently cased environment) -- exactly the same
    # spellings `match_release_report` already treats as identical via
    # `_safe_normalize_repo`/`_safe_normalize_service`/`_safe_same_environment`.
    # Comparing raw tuples there would silently miss a genuine ref move and
    # let the freshness fence go inert instead of failing closed, while
    # identity-matching elsewhere still happily reuses the report keyed to
    # the other spelling. Normalizing both sides the same way closes that gap.
    for raw_key, ref in mapping.items():
        if not isinstance(raw_key, tuple) or len(raw_key) != 3:
            continue
        if _normalized_ref_pair_key(*raw_key) == normalized_key:
            return ref
    return None


def _ref_pair_for_entry(
    entry: ReleaseEntry,
    start_ref: Any,
    final_ref: Any,
) -> tuple[Optional[str], Optional[str]]:
    """Resolve the (start, final) ref pair to fence for one entry.

    `start_ref`/`final_ref` each accept either a single value (applied to
    every entry in the manifest -- the original single-entry-manifest shape)
    or a `{(repo, service, environment): ref}` mapping, so a multi-entry
    manifest where each entry tracks its own independently mutable
    `release_ref` gets its own freshness fence instead of one entry's
    identity silently standing in for every other entry's. `environment` is
    part of the key (not just repo/service) because the same repo/service
    legitimately appears as multiple manifest entries targeting different
    environments (e.g. staging and prod) -- keying by repo/service alone
    would let one environment's ref-resolution data silently mask another's.

    The lookup key is normalized the same way `match_release_report` compares
    identity, not a raw tuple -- see `_resolve_ref_pair_mapping`.
    """
    normalized_key = _normalized_ref_pair_key(entry.repo, entry.service, entry.environment)
    resolved_start = (
        _resolve_ref_pair_mapping(start_ref, normalized_key) if isinstance(start_ref, Mapping) else start_ref
    )
    resolved_final = (
        _resolve_ref_pair_mapping(final_ref, normalized_key) if isinstance(final_ref, Mapping) else final_ref
    )
    return resolved_start, resolved_final


def run_release(
    manifest: Any,
    *,
    trusted_reports: Optional[Sequence[Mapping[str, Any]]] = None,
    production_invoke: Optional[Callable[..., Any]] = None,
    check_spy: Any = None,
    start_ref: Any = None,
    final_ref: Any = None,
    code_review_coverage: Optional[Mapping[str, Any]] = None,
) -> ReleaseResult:
    """`code_review_coverage`, like `trusted_reports`/`production_invoke`, is a
    trusted-runtime input supplied by release-readiness-checker's own execution
    harness -- never sourced from `manifest` itself. It applies only to the
    entry whose own `repo`/`service`/`source_revision` all match the bundle's
    own declared scope (see `_coverage_for_entry`); for any other entry in a
    multi-entry manifest it is treated as not supplied.

    `start_ref`/`final_ref` each accept a single value (applied uniformly) or
    a `{(repo, service, environment): ref}` mapping for independent per-entry
    freshness tracking -- see `_ref_pair_for_entry`.
    """
    entries = _normalize_manifest(manifest)
    if not entries:
        # HARD STOP per v1's own definition_of_done -- an empty manifest is a
        # blocked precondition, never a resolved (SUCCESS/PARTIAL) analysis and
        # never an internal execution failure (FAILED).
        return ReleaseResult(
            verdict="UNKNOWN",
            skill_result=SkillResult(status="BLOCKED", evidence_status="UNKNOWN"),
        )

    overall = "READY"
    production_readiness_results: list = []
    checks: list = []
    unknown_dimensions: list = []
    candidate_changed = False

    for raw_entry in entries:
        parsed = parse_release_entry(raw_entry)
        entry_start_ref, entry_final_ref = _ref_pair_for_entry(parsed, start_ref, final_ref)
        ref_moved = entry_start_ref is not None and entry_final_ref is not None and entry_start_ref != entry_final_ref

        # Existing PR/K8s/incident checks are never skipped because of anything
        # production readiness does or doesn't find -- they always run first,
        # per entry, exactly as v1 already does. The candidate's own
        # repo/service/environment are passed to check_spy.run so a real
        # (non-stub) harness in a multi-entry manifest can run/attribute
        # pr-review/k8s/incident-rca against the correct per-entry candidate,
        # per run-check.md's own "once per service"/"per resolved MR" contract
        # -- a bare check name alone carries no such attribution.
        for name in _EXISTING_CHECKS:
            if check_spy is not None:
                outcome = check_spy.run(name, repo=parsed.repo, service=parsed.service, environment=parsed.environment)
                status = _safe_verdict(outcome.get("status")) if isinstance(outcome, Mapping) else "UNKNOWN"
                checks.append(
                    {
                        "name": name,
                        "repo": parsed.repo,
                        "service": parsed.service,
                        "environment": parsed.environment,
                        "status": status,
                        "executed": True,
                    }
                )
                # _safe_verdict already guarantees a hashable string, but an
                # arbitrary string not in this table (as opposed to one of the
                # dict/list shapes _safe_verdict guards against) still needs
                # the same UNKNOWN default -- _CHECK_STATUS_VERDICT.get(...)
                # handles that half; _safe_verdict handles the unhashable half.
                mapped = _CHECK_STATUS_VERDICT.get(status, "UNKNOWN")
                overall = cap_release_verdict(overall, mapped)
                if mapped == "UNKNOWN":
                    # An executed check that itself resolved to an evidence gap
                    # is exactly as unresolved as one that never ran at all --
                    # both must be reported PARTIAL, never a false SUCCESS.
                    unknown_dimensions.append(name)
            else:
                # No wrapped-skill harness supplied -- an unexecuted check is an
                # evidence gap (UNKNOWN), never an implicit PASS.
                checks.append(
                    {
                        "name": name,
                        "repo": parsed.repo,
                        "service": parsed.service,
                        "environment": parsed.environment,
                        "status": "NOT_RUN",
                        "executed": False,
                    }
                )
                overall = cap_release_verdict(overall, "UNKNOWN")
                unknown_dimensions.append(name)

        if ref_moved:
            # Task 6.5 final freshness fence: a mutable release reference that
            # resolved differently between the start and end of this run means
            # the candidate moved mid-review -- combining evidence gathered
            # against two different identities is never safe. Applies to every
            # entry (v1 included): this is a general release-candidate identity
            # fence, independent of whether production readiness is separately
            # gated for that entry. Capped, never overwritten: a proven
            # NOT_READY from a check that already ran this same iteration must
            # never be silently downgraded to the merely-uncertain UNKNOWN.
            candidate_changed = True
            overall = cap_release_verdict(overall, "UNKNOWN")
            unknown_dimensions.append("release_ref_freshness")
            if parsed.production_readiness_required:
                # This entry required production readiness -- it must still
                # appear in production_readiness_results (voided by the stale
                # ref, never simply absent) so a per-entry report render can
                # show it was required and why it's unresolved, matching this
                # field's own "every entry that actually required it" contract.
                production_readiness_results.append(
                    {
                        "repo": parsed.repo,
                        "service": parsed.service,
                        "environment": parsed.environment,
                        "source": None,
                        "verdict": "UNKNOWN",
                    }
                )
            continue

        if not parsed.production_readiness_required:
            continue

        resolution = resolve_production_readiness(
            parsed,
            trusted_reports=trusted_reports,
            production_invoke=production_invoke,
            code_review_coverage=code_review_coverage,
        )
        if resolution["status"] == "NOT_REQUIRED":
            continue
        resolved_status = resolution["status"] if resolution["status"] in _VERDICT_SEVERITY else "UNKNOWN"
        # Every required entry's own result is recorded -- a scalar
        # last-write-wins assignment here would silently discard every
        # entry's result but the last one processed, even though each
        # entry's status already correctly feeds the capped `overall` below.
        production_readiness_results.append(
            {
                "repo": parsed.repo,
                "service": parsed.service,
                "environment": parsed.environment,
                "source": resolution["source"],
                "verdict": resolved_status,
            }
        )
        if resolved_status == "UNKNOWN":
            unknown_dimensions.append("production_readiness")
        overall = cap_release_verdict(overall, resolved_status)

    # The top-level production_readiness/production_readiness_source fields
    # are a convenience projection for the common single-required-entry case:
    # when more than one entry required it, they reflect whichever entry's
    # result is most severe (the one that actually drove `overall`'s cap),
    # never an arbitrary "last processed" one.
    production_readiness_source: Optional[str] = None
    production_readiness_value: Optional[str] = None
    if production_readiness_results:
        worst = max(
            production_readiness_results,
            key=lambda r: _VERDICT_SEVERITY.get(r["verdict"], _VERDICT_SEVERITY["UNKNOWN"]),
        )
        production_readiness_source = worst["source"]
        production_readiness_value = worst["verdict"]

    return finalize_release(
        {
            "overall": overall,
            "unknown_dimensions": unknown_dimensions,
            "production_readiness_source": production_readiness_source,
            "production_readiness": production_readiness_value,
            "production_readiness_results": production_readiness_results,
            "checks": checks,
            "candidate_changed_during_review": candidate_changed,
        }
    )
