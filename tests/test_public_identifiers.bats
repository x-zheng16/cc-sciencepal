#!/usr/bin/env bats

bats_require_minimum_version 1.5.0

setup() {
    PLUGIN_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
    CHECKER="$PLUGIN_ROOT/tests/lib/check_public_identifiers.sh"
}

# Fixture builder: a throwaway git repo containing one tracked file whose single line is
# caller-chosen. The checker's scope is `git ls-files`, so a fixture has to be a real repo with a
# real commit; a bare directory of files would be scanned as empty and would pass for the wrong
# reason. The two fixtures below differ only in that line, which is the property under test.
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
    # This repo is PUBLIC, and the commit-time privacy hook reads commit messages and
    # pull-request bodies only, never the body of the files in the diff. Regression guard for the
    # 2026-08-20 sweep, which found ten violations across three tracked files: the download
    # destination written as an internal scratch path in three places in SKILL.md, and internal
    # component names paired with internal commit SHAs in two test files.
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
    [ "$patterns" -ge 10 ]
}

@test "checker rejects an internal path in a tracked file (positive control)" {
    # The negative half of the boundary pair. Without this, a checker whose regex never matched
    # anything would pass the test above for the wrong reason.
    repo=$(write_repo "$BATS_TEST_TMPDIR/leak" 'Download results to ~/os/cc/plugin/cc-sciencepal/out/.')
    run "$CHECKER" "$repo"
    echo "$output"
    [ "$status" -eq 1 ]
    [[ "$output" == *"GATE: FAIL home-path"* ]]
}

@test "checker rejects an AI-authorship watermark in a tracked file" {
    repo=$(write_repo "$BATS_TEST_TMPDIR/mark" 'Co-Authored-By: some agent <noreply@example.invalid>')
    run "$CHECKER" "$repo"
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

@test "checker does not flag an English word that merely contains an internal token" {
    # The measured false positive that shaped the pattern table: a substring scan for the internal
    # token `orch` also matches "orchestrate", which SKILL.md uses legitimately, and a shape-based
    # methodology-code pattern matched `names.add(`, `skills add`, and `numbers add up`.
    repo=$(write_repo "$BATS_TEST_TMPDIR/fp" 'Do not orchestrate sub-steps; names.add(x) and the numbers add up.')
    run "$CHECKER" "$repo"
    echo "$output"
    [ "$status" -eq 0 ]
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

@test "CLAUDE.local.md is not tracked" {
    # Separate predicate from the content scan above: this file's published CONTENT was benign,
    # but the name is the convention for the private per-directory instruction layer, and it sat
    # on the public default branch from 2026-04-28 until the 2026-08-20 sweep. Untracking it does
    # not unpublish the history; this guard only stops it being re-added.
    run git -C "$PLUGIN_ROOT" ls-files --error-unmatch CLAUDE.local.md
    [ "$status" -ne 0 ]
}
