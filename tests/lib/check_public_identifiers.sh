#!/usr/bin/env bash
# check_public_identifiers.sh — assert no tracked file publishes internal-workspace vocabulary.
#
# This repository is public. Its git history is the published artifact, so an internal identifier
# that reaches a tracked file is published the moment it is pushed, and stays published after the
# working tree is cleaned. Commit-message tooling does not help here: a message and a diff are
# different objects, and a clean message says nothing about the bytes it carries.
#
# Two families are refused.
#
#   internal   Vocabulary that only resolves inside a private workspace: absolute home paths,
#              scratch-directory names, the names of sibling private components, and internal
#              short codes. These leak the shape of a private system and are useless to everyone
#              else.
#
#   watermark  AI-authorship or co-credit markers. Deliverables in this project carry no such
#              marker, and a commit body cannot be corrected in place once pushed.
#
# TWO SCOPES, and the distinction is the point. `worktree` is what a commit would publish next.
# `HEAD` is what is published already. An earlier draft of this checker took its file LIST from
# git and its file CONTENT from disk, which meant scrubbing a file made the gate report PASS while
# the leak sat untouched at the tip. Both scopes are scanned, and a finding in either fails.
#
# WHAT THIS DOES NOT COVER, stated here because the sentence above is easy to over-read. HISTORY is
# a third scope and is NOT scanned. The contract of a PASS is "the tip is clean", not "this
# repository does not publish these strings", and the second claim is currently FALSE. Measured
# 2026-08-20 by scanning every commit reachable from every ref: 14 commits carry
# ~/cc-omni/cc/plugin/sciencepal, 6 carry ~/cc-plugins/cc-python, 11 carry ~/.claude/cc-python, and
# 26 carry the scratch-directory name, across CLAUDE.md, CLAUDE.local.md, README.md and
# skills/sciencepal/SKILL.md. Reproduce with:
#
#   for s in 'cc-omni/cc/plugin/sciencepal' 'cc-plugins/cc-python' '\.claude/cc-python' 'cc-scratch'; do
#       git rev-list --all | xargs -I{} git grep -l -E "$s" {} -- 2>/dev/null | sed 's/:.*//' | sort -u | wc -l
#   done
#
# Those strings stay fetchable at the commits that introduced them for as long as the repository is
# public, and removing them needs a history rewrite, which is not this file's decision to make.
# Widening the contract to the stronger claim means adding the history scope here, not relabelling
# what these two scopes already prove.
#
# Matching is word-boundaried, not substring, and case matters. That distinction is load-bearing.
# A naive substring scan for the internal token `orch` matches the ordinary English word
# "orchestrate". Anchoring only the left side against lowercase is not enough either: the pattern
# `(^|[^a-z])-?orch\b` matches PyTorch, because the capital T satisfies [^a-z]. A privacy gate that
# blocks on the name of a mainstream framework is a gate people learn to bypass, and the bypass
# then costs whatever else the gate protects. Anchoring is therefore against letters of either
# case.
#
# For the same reason the methodology codes are enumerated rather than described by shape. The
# first draft generalised them to `\b[0-9]?[a-z]?[a-z]dd\b`, which is the correct shape, and which
# matched `names.add(` in tests/test_pyproject_independence.py, `skills add` in README.md, and
# `numbers add up` in skills/sciencepal/SKILL.md: three files, six lines, all of them ordinary
# prose or code. A pattern loose enough to be future-proof is loose enough to be ignored.
#
# The codes are also bounded against DIGITS, not merely letters, which is a separate lesson with
# its own measurement. Bounded against letters alone, `6dd` matched four lines of uv.lock (111,
# 127, 129 and 138 at the time of writing): a sha256 digest and three package URLs whose hex
# happens to contain the sequence. The full first one, since an elided hash cannot be re-checked:
# https://files.pythonhosted.org/packages/cb/b1/3846dd7f199d53cb17f49cba7e651e9ce294d8497c8c150530ed11865bb8/iniconfig-2.3.0-py3-none-any.whl
# Machine-generated hex is long, tracked, and matches short lowercase alphanumeric tokens by
# chance, so any pattern that can appear inside a hash needs the digit boundary.
#
# Those two failures are one failure. A letter-class anchor treats an uppercase letter as a
# boundary, which is the PyTorch case, and a letter-and-digit anchor still treats an underscore as
# one, which matches `orch_worker`. Every anchor here is therefore `[^A-Za-z0-9_]`, which is what
# `\b` means, and it is spelled out rather than written as `\b` for a mechanical reason worth
# knowing before porting this file: `git grep -E` does NOT honour `\b`. It matches nothing and
# says so with exit 1, which is indistinguishable from a clean scan, so a table written with `\b`
# would be entirely inert while reporting PASS. `git grep -P` does honour it, but combining the
# two is order-dependent rather than additive: `-P -E` matched nothing here while `-E -P` worked,
# so the last flag wins and a table that assumes otherwise silently loses its engine. Verified on
# git 2.54.0; the neighbouring hazard is recorded as GOTCHA011.
#
# Scope is `git ls-files` via `git grep`, because tracked-ness is exactly what publishes. Binary
# files are skipped (-I): random bytes match short patterns readily, and a font file cannot leak
# vocabulary. Path quoting is git's own problem here rather than this script's, which is the other
# reason for using `git grep` instead of a shell loop over `git ls-files`.
#
# THE `private-component` ROW IS A CURATED LIST, and its contract is "the names I knew about when
# this was written", not "the private components". It cannot be anything else from inside a public
# repository: enumerating private repository names at run time would write the answer into the very
# tree being scanned. The failure mode is invisible from here, and it is not hypothetical. A peer
# running a hand-curated list of the same shape reported a repository CLEAN while missing a private
# name four lines below one it had caught, because the caught one matched a generic token by
# accident and the missed one was simply not on the list; a third name minted after the list was
# written was missed by both of us. So a PASS on this row means "no name on the list appears here",
# and a private component created since is invisible to it. Adding names is the only maintenance
# this row has.
#
# Exemptions live in the ALLOW table, keyed by path AND pattern id, each with a written reason.
# Wildcard ids are not accepted: an exemption that grants every pattern to a file also grants the
# ones nobody considered. This file and its test exempt themselves for the ids they genuinely
# trip, because a checker necessarily contains the strings it forbids.
#
# Silence is the failure mode of a scanner, so three things are refused outright rather than
# passed: an empty file list, an empty pattern table, and a regex the matcher rejects. The last
# one matters most. An earlier draft discarded stderr and treated every non-zero exit as "no
# match", so a single unbalanced parenthesis disabled its pattern while the summary still counted
# it as present.
#
# Output: `GATE: FAIL <id> [<family>/<scope>] <path>:<line> <text>` per violation, then a
# `GATE: SCANNED <n> files, <m> patterns` summary. Exits 1 on any violation or refusal.
#
# Usage: check_public_identifiers.sh [repo-root]   (default: the repo containing this script)

set -uo pipefail

root="${1:-}"
if [ -z "$root" ]; then
    root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi
cd "$root" 2>/dev/null || { echo "no such directory: $root" >&2; exit 1; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "not a git repo: $root" >&2; exit 1; }

# --- pattern table -----------------------------------------------------------------------------
# One entry per line: id, family, ERE. Ids are stable and are what the ALLOW table and the failure
# output refer to, so they are never renumbered when a pattern is added.
PATTERNS=(
    "home-path	internal	(~|/Users)/(os|cc-omni|cc-plugin|cc-plugins)/"
    "users-path	internal	/Users/[a-z]"
    "claude-dir	internal	~/\.claude/(docs|skills|commands|scripts|hooks|state|plugins)/"
    "scratch-dir	internal	cc-scratch"
    "slot-token	internal	<your-slot>|(^|[^A-Za-z0-9_])(your|the|its|per|owning|owner)[- ]slots?([^A-Za-z0-9_]|$)|(^|[^A-Za-z0-9_])slots?[- ](owner|root|path|dir|slug|launched|charter)([^A-Za-z0-9_]|$)"
    "config-file	internal	(^|[^A-Za-z0-9_])(ccmd|clmd)([^A-Za-z0-9_]|$)"
    "private-component	internal	cc-research-utils|cc-python|(^|[^A-Za-z0-9_])cc-plugin-[a-z-]+"
    "swarm-term	internal	(^|[^A-Za-z0-9_])(swarm|orch)([^A-Za-z0-9_]|$)"
    "rev-role-tag	internal	[a-z0-9]-rev(-[0-9]+)?([^A-Za-z0-9_]|$)"
    "method-code	internal	(^|[^A-Za-z0-9_#])(6dd|sdd|tdd|ddd|etdd|sadd|cadd)([^A-Za-z0-9_]|$)"
    "watermark-credit	watermark	co-authored-by|noreply@anthropic|claude\.(ai/code|com/claude-code)|generated (with|by) \[?claude"
    "watermark-label	watermark	ai-generated|本内容由AI生成|🤖"
)
# watermark patterns are matched case-insensitively; see CASE_INSENSITIVE below.
CASE_INSENSITIVE="watermark-credit watermark-label"

# --- ALLOW table -------------------------------------------------------------------------------
# One entry per line: path, pattern id, reason. One row per (path, id) pair; there is no wildcard.
ALLOW=(
    "tests/lib/check_public_identifiers.sh	home-path	The scope note names the retired layouts the history measurement found, and an elided path would make that measurement unre-runnable."
    "tests/lib/check_public_identifiers.sh	scratch-dir	A pattern table must contain the strings it searches for."
    "tests/lib/check_public_identifiers.sh	slot-token	Same, for the workspace placeholder the pattern matches literally."
    "tests/lib/check_public_identifiers.sh	config-file	Same, for the private instruction-file names."
    "tests/lib/check_public_identifiers.sh	private-component	Same, for the private component names."
    "tests/lib/check_public_identifiers.sh	swarm-term	Same, and the header names the PyTorch false positive it exists to avoid."
    "tests/lib/check_public_identifiers.sh	method-code	Same, for the enumerated methodology codes."
    "tests/lib/check_public_identifiers.sh	watermark-credit	Same, for the authorship markers."
    "tests/lib/check_public_identifiers.sh	watermark-label	Same, for the label markers."
    "tests/test_public_identifiers.bats	home-path	The fixtures assert on a leaking path and on its neutral rewrite."
    "tests/test_public_identifiers.bats	users-path	The arm-coverage fixture carries one line per pattern arm, and this is that line."
    "tests/test_public_identifiers.bats	slot-token	Same, the arm-coverage line for the workspace placeholder."
    "tests/test_public_identifiers.bats	rev-role-tag	Same, the arm-coverage line for the reviewer role tag."
    "tests/test_public_identifiers.bats	claude-dir	Same, the arm-coverage line for the config-directory pattern."
    "tests/test_public_identifiers.bats	config-file	Same, the arm-coverage line for the instruction-file names."
    "tests/test_public_identifiers.bats	private-component	Same, two arm-coverage lines, one per alternation branch."
    "tests/test_public_identifiers.bats	watermark-label	Same, the arm-coverage line for the label markers."
    "tests/test_public_identifiers.bats	scratch-dir	The uncompilable-pattern case corrupts the scratch-dir row by name to prove the checker refuses it."
    "tests/test_public_identifiers.bats	swarm-term	The false-positive fixture contains orchestrate and PyTorch deliberately."
    "tests/test_public_identifiers.bats	method-code	The false-positive fixture contains the add-words the shape pattern matched."
    "tests/test_public_identifiers.bats	watermark-credit	The watermark fixture asserts the canonical marker is caught."
    "tests/test_post_migration_paths.bats	home-path	Two regression guards assert that SKILL.md contains no reference to two retired layouts. A test for a forbidden string necessarily contains that string."
)

allowed() {  # $1 = path, $2 = pattern id
    local row
    for row in "${ALLOW[@]}"; do
        [ "${row%%	*}" = "$1" ] || continue
        local rest="${row#*	}"
        [ "${rest%%	*}" = "$2" ] && return 0
    done
    return 1
}

fail() { printf 'GATE: FAIL %s\n' "$1"; exit 1; }

[ "${#PATTERNS[@]}" -gt 0 ] || fail "empty pattern table; a scan with nothing to look for is not a pass"

nfiles=$(git ls-files -z | tr -cd '\0' | wc -c | tr -d ' ')
[ "${nfiles:-0}" -gt 0 ] || fail "no tracked files found; an empty scan is not consent"

# Validate every regex before scanning. A matcher that rejects a pattern must stop the gate, not
# quietly reduce its coverage.
for row in "${PATTERNS[@]}"; do
    id="${row%%	*}"; rest="${row#*	}"; regex="${rest#*	}"
    # -c rather than -q, deliberately. Under `set -o pipefail` a consumer that exits on its
    # FIRST match kills the producer with SIGPIPE, and the pipeline then returns 141 even though
    # the match succeeded, so a successful match reads as a failure. It cannot bite here, the
    # input being a constant empty string, but this file is meant to be lifted and the safe form
    # costs nothing. Measured by a peer on a 152 KB input: -q gives 141 with pipefail and 0
    # without; -c gives 0 under both. Size- and position-dependent, so it hides on small inputs
    # and on a match near the end.
    printf '' | grep -cE -- "$regex" >/dev/null 2>&1
    [ $? -le 1 ] || fail "pattern '$id' is not a valid ERE; refusing to scan with it disabled"
done

has_head=0
git rev-parse --verify --quiet HEAD >/dev/null 2>&1 && has_head=1

violations=0
for row in "${PATTERNS[@]}"; do
    id="${row%%	*}"; rest="${row#*	}"; family="${rest%%	*}"; regex="${rest#*	}"
    icase=""
    case " $CASE_INSENSITIVE " in *" $id "*) icase="-i" ;; esac

    for scope in worktree HEAD; do
        [ "$scope" = HEAD ] && [ "$has_head" -eq 0 ] && continue
        if [ "$scope" = worktree ]; then
            out=$(git grep -I -n -E $icase -e "$regex" -- . 2>&1); rc=$?
        else
            out=$(git grep -I -n -E $icase -e "$regex" HEAD -- . 2>&1); rc=$?
        fi
        [ "$rc" -le 1 ] || fail "matcher error on pattern '$id' ($scope): $out"
        [ "$rc" -eq 0 ] || continue
        while IFS= read -r line; do
            [ -n "$line" ] || continue
            [ "$scope" = HEAD ] && line="${line#HEAD:}"
            path="${line%%:*}"
            allowed "$path" "$id" && continue
            printf 'GATE: FAIL %s [%s/%s] %s\n' "$id" "$family" "$scope" "$line"
            violations=$((violations + 1))
        done <<<"$out"
    done
done

printf 'GATE: SCANNED %s files, %s patterns\n' "$nfiles" "${#PATTERNS[@]}"
[ "$violations" -eq 0 ] || fail "$violations violation(s)"
printf 'GATE: PASS no internal identifiers in tracked files\n'
