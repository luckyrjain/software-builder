#!/usr/bin/env bash
# Check relative .md links in markdown files (with optional #anchors).
# Skips fenced code blocks (``` ... ```) so example links are not validated.
# Usage: lint-dangling-md-links.sh file1.md file2.md ...
set -euo pipefail

strip_fences() {
	awk 'BEGIN { in_fence = 0 }
		/^```/ { in_fence = !in_fence; next }
		!in_fence { print }' "$1"
}

resolve_path() {
	local base="$1" rel="$2"
	BASE="$base" REL="$rel" python3 -c 'import os; print(os.path.normpath(os.path.join(os.environ["BASE"], os.environ["REL"])))'
}

fail=0
for f in "$@"; do
	[ -f "$f" ] || continue
	dir=$(dirname "$f")
	refs=$(strip_fences "$f" | grep -oE '\]\([a-zA-Z0-9_./~-]+\.md(#[a-zA-Z0-9_-]+)?\)' | sed -E 's/^\]\(//; s/\)$//') || true
	while IFS= read -r ref; do
		[ -n "$ref" ] || continue
		path_part="${ref%%#*}"
		case "$path_part" in
		"~"*) continue ;;
		esac
		target=$(resolve_path "$dir" "$path_part")
		if [ ! -f "$target" ]; then
			echo "  dangling: $ref (missing $target) referenced in $f" >&2
			fail=1
			continue
		fi
		if [[ "$ref" == *#* ]]; then
			anchor=$(printf '%s' "${ref##*#}" | tr '[:upper:]' '[:lower:]')
			slugs=$(grep -E '^#{1,6} ' "$target" | sed -E 's/^#+ +//' | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9 -]//g; s/ +/ /g; s/ /-/g')
			if ! printf '%s\n' "$slugs" | grep -qx "$anchor"; then
				echo "  dangling anchor: $ref referenced in $f" >&2
				fail=1
			fi
		fi
	done <<< "$refs"
done
exit "$fail"
