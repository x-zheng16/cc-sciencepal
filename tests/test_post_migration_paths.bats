#!/usr/bin/env bats

bats_require_minimum_version 1.5.0

setup() {
    PLUGIN_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
}

# SCOPE, stated once for both guards below, because the difference matters and the test names do
# not carry it. These assert that the WORKING TREE is free of the retired paths. They are runtime
# guards: a stale path in the checked-out SKILL.md is what ENOENTs when someone follows it. They
# are NOT a claim that the repository does not publish those paths, and that stronger claim is
# false: the strings remain fetchable at the commits that introduced them, 14 commits for one
# layout and 11 for another as of 2026-08-20. That surface is measured in the header of
# tests/lib/check_public_identifiers.sh, and closing it needs a history rewrite rather than a
# stronger test here.

@test "skills/sciencepal/SKILL.md contains no stale ~/cc-plugin/ paths (post-2026-04-24 retirement)" {
    # The ~/cc-plugin/ layout was retired on 2026-04-24 and the shared Python
    # environment moved. Any literal ~/cc-plugin/ reference left in
    # skills/sciencepal/SKILL.md would ENOENT at runtime.
    run grep -n '~/cc-plugin/' "$PLUGIN_ROOT/skills/sciencepal/SKILL.md"
    if [ "$status" -eq 0 ]; then
        echo "stale ~/cc-plugin/ references in skills/sciencepal/SKILL.md:"
        echo "$output"
        return 1
    fi
}

@test "skills/sciencepal/SKILL.md points at the plugin-local project, not the retired shared one" {
    # The shared Python environment was retired on 2026-04-25. The runtime
    # invocation must point at the plugin-local pyproject rather than at the
    # retired shared environment under ~/cc-omni/cc/python.
    run grep -nF -- '--project ~/cc-omni/cc/python' "$PLUGIN_ROOT/skills/sciencepal/SKILL.md"
    if [ "$status" -eq 0 ]; then
        echo "deprecated --project ~/cc-omni/cc/python references in skills/sciencepal/SKILL.md:"
        echo "$output"
        return 1
    fi
}
