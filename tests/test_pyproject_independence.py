"""Anti-regression: every plugin .py imports only stdlib or declared deps.

Standalone pyproject migration (cc-python decom 2026-04-25).
Pilot: cc-dev-tools 65262c4 — same pattern, no template-dir exclusion needed
since cc-sciencepal has no scaffolded sub-projects.
"""
from __future__ import annotations

import ast
import sys
import tomllib
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
EXCLUDED_DIRS = {".venv", "__pycache__", ".pytest_cache", "node_modules", ".worktrees"}


def _plugin_py_files() -> list[Path]:
    files: list[Path] = []
    for p in PLUGIN_ROOT.rglob("*.py"):
        if any(part in EXCLUDED_DIRS for part in p.parts):
            continue
        files.append(p)
    return files


def _top_level_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def _declared_dists() -> set[str]:
    pyproject = PLUGIN_ROOT / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text())
    deps = list(data["project"].get("dependencies", []))
    deps.extend(data.get("dependency-groups", {}).get("dev", []))
    return {
        d.split(">=")[0].split("==")[0].split("<")[0].split("[")[0].strip().lower()
        for d in deps
    }


def test_every_import_is_stdlib_or_declared():
    """Each top-level import in plugin .py must be stdlib OR declared in pyproject."""
    stdlib = set(sys.stdlib_module_names)
    declared = _declared_dists()
    files = _plugin_py_files()
    assert files, "scan found no .py files -- test broken or plugin empty"

    leaks: dict[str, list[Path]] = {}
    for f in files:
        for imp in _top_level_imports(f):
            if imp in stdlib:
                continue
            if imp.lower() in declared:
                continue
            leaks.setdefault(imp, []).append(f.relative_to(PLUGIN_ROOT))

    if leaks:
        msg_lines = ["Undeclared imports (add to pyproject.toml or stdlib check):"]
        for imp, paths in sorted(leaks.items()):
            msg_lines.append(f"  {imp}:")
            for p in paths:
                msg_lines.append(f"    {p}")
        raise AssertionError("\n".join(msg_lines))
