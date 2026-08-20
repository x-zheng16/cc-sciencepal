#!/usr/bin/env bats

bats_require_minimum_version 1.5.0

setup() {
    PLUGIN_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
    CHECKER="$PLUGIN_ROOT/tests/lib/check_public_identifiers.sh"
}

# Fixture builder: a throwaway git repo with one tracked, COMMITTED file. The checker scans both
# the working tree and HEAD, so a fixture has to be a real repo with a real commit; a bare
# directory of files would be scanned as empty and would pass for the wrong reason.
write_repo() {
    local dir="$1" content="$2"
    mkdir -p "$dir"
    git -C "$dir" init -q
    printf '%s\n' "$content" >"$dir/doc.md"
    git -C "$dir" add doc.md
    git -C "$dir" -c user.email=t@t -c user.name=t commit -qm fixture
    printf '%s' "$dir"
}

@test "no tracked file in this repo publishes internal-workspace vocabulary" {
    # This repo is public, and a commit message says nothing about the bytes in its diff.
    # Regression guard for the 2026-08-20 sweep, which found ten violations across three tracked
    # files: the download destination written as an internal scratch path in three places in
    # SKILL.md, and private component names paired with internal commit SHAs in two test files.
    run "$CHECKER" "$PLUGIN_ROOT"
    echo "$output"
    [ "$status" -eq 0 ]
    [[ "$output" == *"GATE: PASS"* ]]
}

@test "the scan covers every tracked file and every pattern (no silent narrowing)" {
    # The count line exists so that a checker which quietly stopped matching cannot read as a
    # pass. Assert both operands are non-trivial rather than pinning exact numbers, which would
    # fail on every ordinary file addition.
    run "$CHECKER" "$PLUGIN_ROOT"
    echo "$output"
    [ "$status" -eq 0 ]

    scanned=$(echo "$output" | sed -n 's/^GATE: SCANNED \([0-9]*\) files, \([0-9]*\) patterns$/\1 \2/p')
    [ -n "$scanned" ]
    files=${scanned% *}
    patterns=${scanned#* }
    [ "$files" -ge 15 ]
    [ "$patterns" -ge 11 ]
}

@test "a leak that is committed but scrubbed from the worktree still fails" {
    # The defect this checker shipped with on its first draft: it took the file LIST from git and
    # the file CONTENT from disk. Scrubbing the working copy made it report PASS while the leak
    # sat untouched in the committed history, which is the exact thing the repo publishes.
    repo=$(write_repo "$BATS_TEST_TMPDIR/scrubbed" 'Download results to ~/os/cc/plugin/secret/out/.')
    printf 'Download results to <output-dir>/out/.\n' >"$repo/doc.md"

    run "$CHECKER" "$repo"
    echo "$output"
    [ "$status" -eq 1 ]
    [[ "$output" == *"[internal/HEAD]"* ]]
    [[ "$output" != *"[internal/worktree]"* ]]
}

@test "checker rejects an internal path in a tracked file (positive control)" {
    repo=$(write_repo "$BATS_TEST_TMPDIR/leak" 'Download results to ~/os/cc/plugin/cc-sciencepal/out/.')
    run "$CHECKER" "$repo"
    echo "$output"
    [ "$status" -eq 1 ]
    [[ "$output" == *"GATE: FAIL home-path"* ]]
}

@test "checker rejects the canonical AI-authorship watermark, with and without the emoji" {
    # The first pattern table missed the canonical form twice over: it anchored on a lowercase
    # "generated with Claude" with no bracket, and it named the retired claude.ai/code URL. Strip
    # the emoji, which a reformatter or a paste routinely does, and the marker published clean.
    repo=$(write_repo "$BATS_TEST_TMPDIR/mark" 'Generated with [Claude Code](https://claude.com/claude-code)')
    run "$CHECKER" "$repo"
    echo "$output"
    [ "$status" -eq 1 ]
    [[ "$output" == *"GATE: FAIL watermark-credit"* ]]

    repo2=$(write_repo "$BATS_TEST_TMPDIR/mark2" 'Co-authored-by: Some Agent <agent@example.invalid>')
    run "$CHECKER" "$repo2"
    echo "$output"
    [ "$status" -eq 1 ]
    [[ "$output" == *"GATE: FAIL watermark-credit"* ]]
}

@test "checker accepts the neutral rewrite of the same line (boundary neighbour)" {
    # The positive half, differing from the leak fixture only in the path. This is the exact
    # substitution applied to SKILL.md, so it pins the fix rather than merely the failure.
    repo=$(write_repo "$BATS_TEST_TMPDIR/clean" 'Download results to <output-dir>/sciencepal/<run_id>/.')
    run "$CHECKER" "$repo"
    echo "$output"
    [ "$status" -eq 0 ]
    [[ "$output" == *"GATE: PASS"* ]]
}

@test "checker does not flag ordinary words, framework names, or hex digests" {
    # Three measured false positives, each of which killed a plausible pattern:
    #   orchestrate   a substring scan for the internal token `orch`
    #   PyTorch       left-anchoring against lowercase only, since capital T satisfies [^a-z]
    #   names.add     describing the methodology codes by shape instead of enumerating them
    #   3846dd7f      bounding those codes against letters but not digits, so `6dd` hit hashes
    repo=$(write_repo "$BATS_TEST_TMPDIR/fp" 'Do not orchestrate: PyTorch, names.add(x), numbers add up, sha256:3846dd7f199d, orch_worker.')
    run "$CHECKER" "$repo"
    echo "$output"
    [ "$status" -eq 0 ]
}

@test "every arm of every alternation fires, at its own line" {
    # A per-PATTERN fixture proves the pattern matched the file somewhere, never that a particular
    # ARM did, so a dead arm hides behind a live sibling for as long as both are in one regex. A
    # peer adopting this table found exactly that: their role-tag arm required one alphanumeric
    # before the hyphen and so matched nothing at all, and no per-pattern fixture could have shown
    # it. This asserts per LINE: each line names the id that must hit it AT ITS OWN LINE NUMBER,
    # so covering a new arm is one more line.
    fixture="$BATS_TEST_TMPDIR/arms.txt"
    cat >"$fixture" <<'ARMS'
download to ~/os/cc/plugin/thing/	home-path
a path under /Users/someone/	users-path
see ~/.claude/docs/references/x	claude-dir
write to cc-scratch/out	scratch-dir
the <your-slot> placeholder	slot-token
consult the ccmd for this	config-file
fixed in cc-research-utils	private-component
routed via cc-plugin-swarm	private-component
the orch decides	swarm-term
ask a peer named cc-thing-rev	rev-role-tag
built with 6dd throughout	method-code
Co-authored-by: someone	watermark-credit
this is AI-generated text	watermark-label
ARMS

    C="$CHECKER"
    while IFS=$'\t' read -r text id; do
        [ -n "$text" ] || continue
        regex=$(awk -v want="$id" '/^PATTERNS=\(/{f=1;next} f&&/^\)/{f=0}
                                   f{ sub(/^ *"/,""); sub(/"$/,"");
                                      n=split($0, p, "\t"); if (p[1]==want) { print p[3] } }' "$C")
        [ -n "$regex" ] || { echo "unknown pattern id in fixture: $id"; return 1; }
        icase=""
        case "$id" in watermark-*) icase="-i" ;; esac
        printf '%s\n' "$text" | grep -qE $icase -e "$regex" \
            || { echo "arm not covered: '$text' should hit $id but does not"; return 1; }
    done <"$fixture"
}

@test "a web-components slot element is not a workspace slot" {
    # Bare `slots?` gave 17 hits on a peer's static-site repo and was right zero times: `<slot>`
    # is a standard web-components element, `include.slot` and `slot="..."` are template
    # parameters in authored includes, and `$fa-var-check-to-slot` is an icon name. The pattern
    # now requires a companion word, which keeps the workspace placeholder and drops all of that.
    repo=$(write_repo "$BATS_TEST_TMPDIR/webslot" '<slot name="x"></slot> include.slot and $fa-var-check-to-slot')
    run "$CHECKER" "$repo"
    echo "$output"
    [ "$status" -eq 0 ]

    # The positive half on the same predicate, so the case above cannot pass by inertness.
    repo2=$(write_repo "$BATS_TEST_TMPDIR/wsslot" 'write it under your slot root, not the repo')
    run "$CHECKER" "$repo2"
    echo "$output"
    [ "$status" -eq 1 ]
    [[ "$output" == *"GATE: FAIL slot-token"* ]]
}

@test "a CSS hex colour is not a methodology code" {
    # `#ddd` is a valid three-digit hex colour and `ddd` is the code for domain-driven
    # development, so a word-boundary anchor alone matches it: `#` is a non-word character.
    # Found by a peer running this table against a repository with stylesheets in it, which this
    # one does not have. The left anchor now excludes `#`; `#dddddd` never matched and still does
    # not, since its second `ddd` is preceded by a hex digit.
    repo=$(write_repo "$BATS_TEST_TMPDIR/css" 'a { color: #ddd; border: 1px solid #dddddd; }')
    run "$CHECKER" "$repo"
    echo "$output"
    [ "$status" -eq 0 ]
}

@test "the anchors are live under the matcher the checker actually uses" {
    # `git grep -E` does not honour \b: it matches nothing and exits 1, which is exactly what a
    # clean scan looks like. A pattern table written with \b would therefore be entirely inert
    # while the gate reported PASS. This asserts the property directly rather than trusting that
    # no future edit reaches for the shorter spelling.
    repo=$(write_repo "$BATS_TEST_TMPDIR/anchor" 'the orch decides')

    run git -C "$repo" grep -n -E -e '\borch\b' -- doc.md
    [ "$status" -eq 1 ]

    run git -C "$repo" grep -n -E -e '(^|[^A-Za-z0-9_])orch([^A-Za-z0-9_]|$)' -- doc.md
    [ "$status" -eq 0 ]

    # Scoped to the pattern table, not the file: the header discusses \b by name, which is the
    # point of the header.
    table=$(awk '/^PATTERNS=\(/{f=1;next} f&&/^\)/{f=0} f' "$CHECKER")
    [ -n "$table" ]
    run grep -c '\\b' <<<"$table"
    [ "$output" = "0" ]
}

@test "checker refuses a pattern its matcher cannot compile" {
    # An earlier draft discarded stderr and read every non-zero grep exit as "no match", so one
    # unbalanced parenthesis disabled a pattern while the summary still counted it as present.
    # Silence is a scanner's failure mode, so an uncompilable pattern must stop the gate.
    cp "$CHECKER" "$BATS_TEST_TMPDIR/broken.sh"
    sed -i.bak 's|"scratch-dir	internal	cc-scratch"|"scratch-dir	internal	cc-scratch(unbalanced"|' "$BATS_TEST_TMPDIR/broken.sh"
    grep -q 'unbalanced' "$BATS_TEST_TMPDIR/broken.sh"

    repo=$(write_repo "$BATS_TEST_TMPDIR/regex" 'nothing to see here')
    run bash "$BATS_TEST_TMPDIR/broken.sh" "$repo"
    echo "$output"
    [ "$status" -eq 1 ]
    [[ "$output" == *"not a valid ERE"* ]]
}

@test "checker fails when the tracked-file list is empty (empty scan is not consent)" {
    dir="$BATS_TEST_TMPDIR/empty"
    mkdir -p "$dir"
    git -C "$dir" init -q
    run "$CHECKER" "$dir"
    echo "$output"
    [ "$status" -eq 1 ]
    [[ "$output" == *"empty scan is not consent"* ]]
}

@test "checker parses under the macOS system bash" {
    # /bin/bash on macOS is 3.2.57. The first draft held its pattern and ALLOW tables in
    # heredocs inside command substitution, where an apostrophe in a reason string tripped a 3.2
    # quoting bug and the script failed to parse at all. It failed closed, but a gate that cannot
    # run on the stock interpreter is a gate that does not run in CI either.
    run /bin/bash -n "$CHECKER"
    echo "$output"
    [ "$status" -eq 0 ]
}

@test "every ALLOW row names a file that exists and a pattern that really fires in it" {
    # An exemption whose path was deleted, or whose pattern no longer matches there, outlives its
    # reason and quietly widens the next one. There is no wildcard id by design: a row that grants
    # every pattern to a file also grants the ones nobody considered, which is how the first
    # draft handed this very test file seven ids it did not use.
    rows=$(awk '/^ALLOW=\(/{f=1;next} f&&/^\)/{f=0} f' "$CHECKER" | sed 's/^ *"//; s/"$//')
    [ -n "$rows" ]

    checked=0
    while IFS=$'\t' read -r path id _reason; do
        [ -n "$path" ] || continue
        [ -f "$PLUGIN_ROOT/$path" ] || { echo "ALLOW row names a missing file: $path"; return 1; }

        regex=$(awk -v want="$id" '/^PATTERNS=\(/{f=1;next} f&&/^\)/{f=0}
                                   f{ sub(/^ *"/,""); sub(/"$/,"");
                                      n=split($0, p, "\t"); if (p[1]==want) { print p[3] } }' "$CHECKER")
        [ -n "$regex" ] || { echo "ALLOW row names an unknown pattern id: $id"; return 1; }

        icase=""
        case "$id" in watermark-*) icase="-i" ;; esac
        grep -qE $icase -e "$regex" "$PLUGIN_ROOT/$path" \
            || { echo "ALLOW row is stale: pattern '$id' no longer fires in $path"; return 1; }
        checked=$((checked + 1))
    done <<<"$rows"

    # An exemption table that parsed to nothing would pass every assertion above.
    [ "$checked" -ge 10 ]
}

@test "CLAUDE.local.md is not tracked" {
    # Separate predicate from the content scan above: this file's published CONTENT was benign,
    # but the name is the convention for the private per-directory instruction layer, and it sat
    # on the public default branch from 2026-04-28 until the 2026-08-20 sweep. Untracking it does
    # not unpublish the history; this guard only stops it being re-added.
    run git -C "$PLUGIN_ROOT" ls-files --error-unmatch CLAUDE.local.md
    [ "$status" -ne 0 ]
}
