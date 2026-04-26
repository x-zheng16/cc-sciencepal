#!/usr/bin/env bats

bats_require_minimum_version 1.5.0

setup() {
    PLUGIN_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"
}

@test "skills/sciencepal/SKILL.md contains no stale ~/cc-plugin/ paths (post-2026-04-24 retirement)" {
    # ~/cc-plugin/ retired on 2026-04-24; cc-python migrated to
    # ~/cc-omni/cc/python/. Any literal ~/cc-plugin/ reference in
    # skills/sciencepal/SKILL.md ENOENTs at runtime.
    # Parallel fixes: ccmd 3e36d6a, cc-plugin-swarm bc3e8bc.
    run grep -n '~/cc-plugin/' "$PLUGIN_ROOT/skills/sciencepal/SKILL.md"
    if [ "$status" -eq 0 ]; then
        echo "stale ~/cc-plugin/ references in skills/sciencepal/SKILL.md:"
        echo "$output"
        return 1
    fi
}
