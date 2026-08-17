#!/usr/bin/env bash
# check_loop_recipes.sh — assert every executable /loop recipe in a SKILL.md carries an interval.
#
# SciencePal refuses self-paced `/loop <prompt>` (no interval) at dispatch: it replies
# {"loop": "rejected"} and arms nothing, so a recipe written in that form can never tick.
# Only `/loop <interval> <prompt>` and the control form `/loop stop` are dispatchable.
#
# Scope: the recipe bullets under the "Three patterns:" line. Prose elsewhere in the section
# deliberately names the refused form in order to document it, so it is not a recipe and is
# not checked.
#
# Emits one `GATE: PASS <token>` line per recipe checked, and `GATE: FAIL <token>` per
# violation. Exits 1 on any violation, and also on finding no recipes at all, so that a
# silently-empty scan can never read as consent.
#
# Usage: check_loop_recipes.sh <path-to-SKILL.md>

set -euo pipefail

file="${1:?usage: check_loop_recipes.sh <path-to-SKILL.md>}"
[ -f "$file" ] || { echo "no such file: $file" >&2; exit 1; }

awk '
/^Three patterns:$/ { in_recipes = 1; next }
in_recipes && /^## / { in_recipes = 0 }
in_recipes && /^- \*\*/ {
    if (match($0, /`\/loop [^ `]+/)) {
        tok = substr($0, RSTART + 7, RLENGTH - 7)
        checked++
        if (tok ~ /^[0-9]+[smhd]$/ || tok == "stop") {
            print "GATE: PASS " tok
        } else {
            print "GATE: FAIL " tok " (line " NR ": no interval, so this form is refused at dispatch)"
            failed++
        }
    }
}
END {
    if (checked == 0) {
        print "GATE: FAIL no /loop recipes found; the scan matched nothing, which is not a pass"
        exit 1
    }
    exit (failed > 0)
}
' "$file"
