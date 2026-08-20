#!/usr/bin/env bats

bats_require_minimum_version 1.5.0

setup() {
    PLUGIN_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
}

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
