#!/usr/bin/env bash
# check_public_identifiers.sh — assert no tracked file publishes internal-workspace vocabulary.
#
# This repository is a PUBLIC GitHub repo. Its git history is the published artifact, so any
# internal identifier that reaches a tracked file is published the moment it is pushed and stays
# published even after the working tree is cleaned. Nothing upstream of this checker catches that:
# the commit-time privacy hook reads commit messages and pull-request bodies, never the body of the
# files in the diff, so a clean commit message publishes whatever the diff happens to contain.
#
# Two families are refused.
#
#   internal   Vocabulary that only resolves inside the author's private workspace: absolute home
#              paths, scratch-directory names, the names of sibling private components, internal
#              short codes, and bare commit SHAs cited from repositories a public reader cannot
#              open. These leak the shape of a private system and are useless to everyone else.
#
#   watermark  AI-authorship or co-credit markers. Deliverables in this project carry no such
#              marker, and a commit body cannot be corrected in place once pushed.
#
# Matching is word-boundaried, not substring. That distinction is load-bearing: a naive substring
# scan for the internal token `orch` also matches the ordinary English word "orchestrate", which
# occurs legitimately in the skill documentation. Every pattern below is therefore anchored so that
# it matches the identifier and not a word that merely contains it.
#
# For the same reason the methodology codes are enumerated rather than described by shape. The first
# draft of this checker generalised them to `\b[0-9]?[a-z]?[a-z]dd\b`, which is the correct shape and
# which matched `names.add(`, `skills add`, and `numbers add up` across three files. A pattern loose
# enough to be future-proof is loose enough to train the reader to ignore the gate.
#
# Scope is `git ls-files`, because tracked-ness is exactly what publishes. Untracked and ignored
# files are out of scope by construction.
#
# Exemptions live in the ALLOW table near the bottom, keyed by path and pattern id, each with a
# written reason. A checker that names what it forbids necessarily contains the forbidden strings,
# so this file and its test exempt themselves; that is the only structural exemption.
#
# Emits `GATE: FAIL <id> <path>:<line>` per violation and a `GATE: SCANNED <n> files, <m> patterns`
# summary. Exits 1 on any violation, and also when the file list or the pattern table comes back
# empty, so that a silently-empty scan can never read as consent.
#
# Usage: check_public_identifiers.sh [repo-root]   (default: the repo containing this script)

set -euo pipefail

root="${1:-}"
if [ -z "$root" ]; then
    root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi
[ -d "$root/.git" ] || [ -f "$root/.git" ] || { echo "not a git repo: $root" >&2; exit 1; }

# --- pattern table: id<TAB>family<TAB>ERE ---------------------------------------------------
# Ordered by family, then by how specific the pattern is. Each id is stable and is what the ALLOW
# table and the failure output refer to, so ids are never renumbered when a pattern is added.
patterns=$(cat <<'PATTERNS'
home-path	internal	(~|/Users)/(os|cc-omni|cc-plugin|cc-plugins)/
users-path	internal	/Users/[a-z]
scratch-dir	internal	cc-scratch
slot-token	internal	<your-slot>|(^|[^a-z-])slots?([^a-z-]|$)
config-file	internal	\bccmd\b|\bclmd\b
swarm-term	internal	\bswarm\b|(^|[^a-z])-?orch\b|\bcc-plugin-[a-z-]+\b|\bcc-research-utils\b
method-code	internal	\b(6dd|sdd|tdd|ddd|etdd|sadd|cadd)\b
skill-name	internal	\bbeautify-bib\b|\bxz-profile\b|\bxmem\b
watermark-credit	watermark	Co-Authored-By|noreply@anthropic|claude\.ai/code|generated (with|by) Claude
watermark-label	watermark	AI-generated|本内容由AI生成|🤖
PATTERNS
)

# --- ALLOW table: path<TAB>id<TAB>reason ------------------------------------------------------
# An entry here suppresses exactly one pattern id in exactly one path, and must state why the
# match is legitimate rather than merely tolerated.
allow=$(cat <<'ALLOW'
tests/lib/check_public_identifiers.sh	*	The checker must contain every string it forbids in order to search for it.
tests/test_public_identifiers.bats	*	The checker's own test asserts on those strings and on its fixtures.
tests/test_post_migration_paths.bats	home-path	Two regression guards assert that SKILL.md contains no reference to the retired ~/cc-plugin/ and ~/cc-omni/ layouts. A test for a forbidden string necessarily contains that string; the guards still have regression value, so the literals stay and only the internal cross-reference comments were removed.
ALLOW
)

allowed() {  # $1 = path, $2 = pattern id
    printf '%s\n' "$allow" | awk -F'\t' -v p="$1" -v id="$2" '
        $1 == p && ($2 == "*" || $2 == id) { found = 1 }
        END { exit !found }
    '
}

npatterns=$(printf '%s\n' "$patterns" | grep -c . || true)
[ "$npatterns" -gt 0 ] || { echo "GATE: FAIL empty pattern table; a scan with nothing to look for is not a pass"; exit 1; }

files=$(cd "$root" && git ls-files)
nfiles=$(printf '%s\n' "$files" | grep -c . || true)
[ "$nfiles" -gt 0 ] || { echo "GATE: FAIL no tracked files found; an empty scan is not consent"; exit 1; }

failed=0
while IFS=$'\t' read -r id family regex; do
    [ -n "${id:-}" ] || continue
    while IFS= read -r path; do
        [ -n "$path" ] || continue
        allowed "$path" "$id" && continue
        while IFS=: read -r lineno text; do
            [ -n "${lineno:-}" ] || continue
            printf 'GATE: FAIL %s [%s] %s:%s %s\n' "$id" "$family" "$path" "$lineno" "$text"
            failed=$((failed + 1))
        done < <(cd "$root" && grep -nE "$regex" -- "$path" 2>/dev/null || true)
    done <<<"$files"
done <<<"$patterns"

printf 'GATE: SCANNED %s files, %s patterns\n' "$nfiles" "$npatterns"
[ "$failed" -eq 0 ] || { printf 'GATE: FAIL %s violation(s)\n' "$failed"; exit 1; }
printf 'GATE: PASS no internal identifiers in tracked files\n'
