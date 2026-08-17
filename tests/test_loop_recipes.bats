#!/usr/bin/env bats

bats_require_minimum_version 1.5.0

setup() {
    PLUGIN_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
    CHECKER="$PLUGIN_ROOT/tests/lib/check_loop_recipes.sh"
    SKILL="$PLUGIN_ROOT/skills/sciencepal/SKILL.md"
}

# Fixture writer: one recipe bullet in the same shape SKILL.md uses, with a caller-chosen
# /loop argument. The two fixtures below differ only in that argument, which is the property
# the checker keys on.
write_fixture() {
    local path="$1" arg="$2"
    cat >"$path" <<EOF
## /loop Prompt Design

Three patterns:

- **Drive-to-complete** (finish a large task autonomously): \`/loop $arg 自主推进直至完成，不要提问；完成后调用 stop_loop。\`

## Result Quality Signals
EOF
}

@test "every /loop recipe in SKILL.md carries an interval" {
    # SciencePal refuses self-paced /loop (no interval) at dispatch, replying
    # {"loop": "rejected"} and arming nothing. A recipe in that form can never tick.
    # Regression guard for the 2026-08-17 fix (plugin 1.3.1 / skill 0.5.1), where two
    # shipped recipes still used the refused form.
    run "$CHECKER" "$SKILL"
    echo "$output"
    [ "$status" -eq 0 ]

    # Population + predicate: three recipe bullets, each asserted to pass, so a scan that
    # silently stopped matching cannot read as a pass.
    [ "$(echo "$output" | grep -c '^GATE: PASS ')" -eq 3 ]
}

@test "checker rejects a recipe whose /loop argument is not an interval (positive control)" {
    # The negative half of the boundary pair: identical bullet, argument moved to the
    # refused side of the predicate. Proves the checker can emit the opposite verdict.
    fixture="$BATS_TEST_TMPDIR/refused.md"
    write_fixture "$fixture" "自主推进直至完成"
    run "$CHECKER" "$fixture"
    echo "$output"
    [ "$status" -eq 1 ]
    [[ "$output" == *"GATE: FAIL"* ]]
}

@test "checker accepts the same recipe once an interval is present (boundary neighbour)" {
    # The positive half, differing from the fixture above only in the argument.
    fixture="$BATS_TEST_TMPDIR/accepted.md"
    write_fixture "$fixture" "10m"
    run "$CHECKER" "$fixture"
    echo "$output"
    [ "$status" -eq 0 ]
    [ "$(echo "$output" | grep -c '^GATE: PASS 10m$')" -eq 1 ]
}

@test "checker fails when it finds no recipes at all (empty scan is not consent)" {
    fixture="$BATS_TEST_TMPDIR/empty.md"
    printf '# SciencePal\n\nNo loop section here.\n' >"$fixture"
    run "$CHECKER" "$fixture"
    echo "$output"
    [ "$status" -eq 1 ]
    [[ "$output" == *"no /loop recipes found"* ]]
}
