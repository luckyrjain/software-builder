# Evidence-authority policy — normative

Every piece of evidence this skill collects or receives from a child carries a source-authority level.
This level, not which child produced the evidence, decides whether it can set a dimension to `PASS`.

## The ladder

| Level | What qualifies | Can it set `PASS`? |
|---|---|---|
| `caller` | A field the invoking caller asserted directly, with no independent evidence behind it (e.g. "rollback plan: revert the deploy") | No |
| `model_knowledge` | An inference this skill or a child derived from general reasoning, without a citable source (e.g. "this pattern is usually safe") | No |
| `repository` | Content actually read from the repository at the exact source revision (diff, config, code, committed docs) | Yes |
| `authoritative_host` | A `host.*` read capability's own live answer (`host.ci.status`, `host.scm.policy.read`, `host.build.provenance.read`, `host.service.metadata.read`, `host.dependency.advisories.read`) | Yes |
| `trusted_runtime` | A live signal from a trusted running system a specialist child itself authenticates against (e.g. a specialist's own observability/runtime evidence source) | Yes |

`caller` and `model_knowledge` rank below `repository`, `authoritative_host`, and `trusted_runtime` —
they are always insufficient on their own to set a dimension `PASS`, regardless of how confident the
assertion sounds or how specific the caller's wording is.

## The no-laundering rule

**A trusted child producer can never launder caller- or model-knowledge-only evidence into a `PASS` on
this skill's behalf.** If a specialist's own report reaches a `PASS` conclusion, but the evidence trail
behind that conclusion — once traced back — bottoms out in only `caller` or `model_knowledge` sources
(the caller told the specialist a migration was reversible, and the specialist took that at face value
with no independent verification), this skill records that dimension `UNKNOWN`, not `PASS`. Being
produced by a trusted child does not itself confer authority on the evidence beneath the child's
conclusion — the child's own trustworthiness bounds how faithfully it reports what it found, not what
authority level the underlying evidence actually had.

This applies symmetrically to this skill's own directly-collected evidence: a `criticality` value the
caller typed in in chat, with no `host.service.metadata.read` corroboration, is `caller`-level and
cannot alone set an operational gate `PASS` (see
[operational-gates.md](operational-gates.md)).

## Applying the ladder

1. Every evidence item collected in Collect evidence and every child report received in Dispatch is
   tagged with its authority level at the point of collection — never re-derived after the fact from
   how confident the text sounds.
2. In Aggregate, a dimension is `PASS` only when its decisive evidence traces to `repository`,
   `authoritative_host`, or `trusted_runtime`.
3. A dimension whose only supporting evidence is `caller` or `model_knowledge` is `UNKNOWN` — not
   `FAIL` (nothing proven wrong) and not `CONDITIONAL` (that would imply some authoritative signal
   exists, just an imperfect one).
4. A dimension with **mixed** evidence (some authoritative, some caller-only) is judged on its
   authoritative evidence; the caller-only portion is noted but does not itself downgrade an otherwise
   authoritative `PASS` to `UNKNOWN` — it can, however, surface as a `CONDITIONAL` note when the
   authoritative evidence alone is incomplete.
5. Capability unavailability (a `host.*` capability not connected) removes the possibility of
   authoritative evidence for that dimension entirely — the dimension is `UNKNOWN`, not silently
   downgraded to relying on whatever `caller`/`model_knowledge` evidence happens to be present.
