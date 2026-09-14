# Versioned Plugin Bundle — Design

**Status:** Approved (user-approved in brainstorming dialogue 2026-09-13/14)
**Date:** 2026-09-14
**Type:** New release artifact (additive)
**Target:** `luckyrjain/software-builder`
**Spec path:** `docs/superpowers/specs/2026-09-14-versioned-plugin-bundle-design.md`

## Goal

Close the audit's Phase 3 gap ("native plugin distribution incomplete") by publishing a versioned,
checksummed archive per tagged release that a user can download and point Claude Code / Codex at as
a plugin marketplace source — an alternative to tracking `main` live via `git clone`.

## Why this is a real gap (verified, not assumed)

`.claude-plugin/` and `.codex-plugin/` already exist and already work as a **live** plugin source:
`marketplace.json`'s plugin entry has `"source": "./"`, so adding this GitHub repo as a marketplace
tracks whatever is checked out — normally `main`. That part of Phase 3 needed no code at all. The gap
that remains is version pinning: there is no way to install a specific tagged plugin version from a
downloaded, checksummed artifact, the way `docs/RELEASE.md` already supports for a checkout-based
install (`software-builder-<version>.tar.gz`) and `sb update` now supports for the CLI
(`software_builder_cli-<version>-py3-none-any.whl`).

## Why this is a new archive, not a change to the existing release tarball

`scripts/package_release.py`'s existing release tarball explicitly **excludes**
`.claude-plugin/`/`.codex-plugin/` — `docs/RELEASE.md` and the exclusion code's own comments state
these "must never ship" in that artifact, with dedicated test coverage. That tarball exists for a
different flow (extract, then run `install.sh`) and conflating it with plugin-marketplace use would
break a deliberate, documented, tested contract for no real benefit. This spec adds a second,
separate artifact instead.

## Reuse: `scripts/registry/generic_package.py` already does most of this work

The existing `package-generic` CLI command already builds a deterministic, git-tracked-only,
transitively-link-validated archive of exactly the portable skill set (`skills/`, `skills.yaml`,
`docs/skill-framework/`, `README.md`, `LICENSE`, plus test-creator runtime files when needed) —
everything a generic agent host needs, and everything a plugin loader needs *except* the plugin
manifests themselves. It excludes `.claude-plugin/`/`.codex-plugin/` only because nothing in the
existing markdown-reference-following logic reaches JSON manifest files, not by an explicit rule —
so this is a natural, additive extension rather than a fork.

## What the plugin bundle contains

Everything `generic_package._package_files()` already collects, **plus** every git-tracked file
under `.claude-plugin/` and `.codex-plugin/` (both plugin manifests, in full) — the "generic bundle
+ plugin manifests" option, confirmed in brainstorming: one archive serves as a plugin source for
Claude Code and Codex/ChatGPT, and doubles as the same generic bundle for any other host, so there is
exactly one definition of "the portable skill set" to keep in sync, not two.

## Implementation shape

**`scripts/registry/generic_package.py`** (modify, additively):
- Extract the existing `build_generic_package_bytes()`'s inner tar-writing loop (currently coupled to
  `_package_files()`) into a small shared helper parameterized by a file list, so both the existing
  generic bundle and the new plugin bundle build their tar.gz through the same code — no duplicated
  archive-writing logic.
- New `_plugin_package_files(root) -> list[Path]`: `_package_files(root)` unioned with every
  git-tracked, non-symlink file under `.claude-plugin/` and `.codex-plugin/` (reusing the same
  `_tracked_files()`/`_is_safe_file()` machinery already used for every other root in this module).
- New `build_plugin_package_bytes(root) -> bytes` and `build_plugin_package(root, output)`, mirroring
  the existing `build_generic_package_bytes`/`build_generic_package` pair exactly.

**`scripts/registry/cli.py`** (modify, additively): new `package-plugin` subcommand, mirroring
`package-generic`'s existing wiring exactly (`cmd_package_plugin(root, output)`, default output
`dist/software-builder-plugin.tar.gz`).

**`.github/workflows/release.yml`** (modify, additively): new step after the existing "Build and
upload sb wheel" step, mirroring its exact shape:

```yaml
      - name: Build and upload plugin bundle
        env:
          GH_TOKEN: ${{ github.token }}
          RELEASE_TAG: ${{ steps.tag.outputs.name }}
        run: |
          VERSION="${RELEASE_TAG#v}"
          python3 -m scripts.registry package-plugin --output "dist/software-builder-plugin-${VERSION}.tar.gz"
          sha256sum "dist/software-builder-plugin-${VERSION}.tar.gz" > "dist/software-builder-plugin-${VERSION}.tar.gz.sha256"
          gh release upload "$RELEASE_TAG" \
            "dist/software-builder-plugin-${VERSION}.tar.gz" \
            "dist/software-builder-plugin-${VERSION}.tar.gz.sha256" \
            --clobber
```

**`docs/RELEASE.md`** (modify, additively): new section documenting the plugin bundle alongside the
existing "Installing a tagged release" section — how to download it, verify its checksum, and add
the extracted directory as a Claude Code / Codex plugin marketplace source.

## Testing

- Extend `scripts/tests/test_generic_package.py` (or a new sibling file, decided at planning time):
  the plugin bundle contains everything the generic bundle does, plus every tracked file currently
  under `.claude-plugin/`/`.codex-plugin/` in this repo, by exact path.
- A tracked symlink or sensitive-named file under `.claude-plugin/`/`.codex-plugin/` is rejected the
  same way `_is_safe_file` already rejects one anywhere else (reuse, not reimplementation — a
  regression test proves this without duplicating `test_generic_package_security.py`'s existing
  coverage of that logic elsewhere).
- Real end-to-end check: build the plugin bundle from this repo, extract it, and confirm
  `.claude-plugin/plugin.json`'s `"skills": "./skills"` and `.codex-plugin/plugin.json`'s equivalent
  both resolve to a real, populated `skills/` directory inside the extracted bundle.
- `.github/workflows/release.yml`'s new step is reviewed for correctness against the proven sb-wheel
  step's pattern but, like that step's own release-side change, cannot be exercised for real until an
  actual tag is pushed — the same honestly-stated testing constraint `sb update`'s design spec
  already used for its own release-side change.

## Explicitly deferred

- Any change to the existing `package_release.py` tarball's contents or its "must never ship"
  exclusion list.
- A per-host split (a Claude-only archive vs. a Codex-only archive) — one shared archive was chosen
  in brainstorming since both hosts consume the identical canonical tree.
- Any new `make` target — `package-generic` has none today (CLI/CI-invoked only), and this mirrors
  that convention rather than introducing a new one.
- Version pinning support inside Claude Code/Codex's own plugin manager UI — out of this repo's
  control; this spec only makes a versioned, checksummed artifact available to point at manually.

## Self-review

- **Placeholder scan:** no TBD/TODO; every file path, CLI name, and workflow step is concrete.
- **Internal consistency:** the "why a new archive, not a tarball change" reasoning is backed by
  quoting the actual exclusion code's own comment ("must never ship"), not asserted without basis.
- **Scope check:** one coherent unit (one module extension, one CLI subcommand, one CI step, one docs
  update) — no further decomposition needed for a single implementation plan.
- **Ambiguity check:** the exact test-file placement (extend vs. new sibling file) is explicitly left
  to planning time as the one genuinely cosmetic decision remaining; everything else is concrete.
