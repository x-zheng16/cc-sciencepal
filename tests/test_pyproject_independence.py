"""Anti-regression: every plugin .py imports only stdlib, declared deps, or plugin-local modules.

Stage 4 (back-port v3 canonical) of cc-python decommissioning (2026-04-25):
plugin owns its Python deps via uv. This test ensures no script silently
re-introduces a transitive dep on the retired shared env.

SCOPE: every .py under PLUGIN_ROOT minus EXCLUDED_DIRS.

LOCAL DISCOVERY: cc-sciencepal currently ships zero plugin-local Python
modules -- the 3 scripts in skills/sciencepal/scripts/ are standalone and
import only stdlib + httpx. The `_local_module_names` framework still applies
(returns the empty set today; future-proof against adding sibling helpers).

Pilot precedent: cc-research-utils 2c1b213. Differences vs pilot:
- IMPORT_TO_DIST starts empty (httpx import name == dist name).
- `test_local_discovery_finds_known_internal_modules` is omitted -- no
  internal package to assert discovery for; the no-shadow guard still
  serves as forward defense.
- All dependency-groups iterated (per Stage 4 dispatch spec) rather than
  only `dev`, future-proofing for additional PEP 735 groups.
- [build-system] hatchling-editable omitted from pyproject.toml -- scripts
  do not use cwd-rooted package imports, so the build backend is unneeded.
"""
from __future__ import annotations

import ast
import re
import sys
import tomllib
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
EXCLUDED_DIRS = {".venv", "__pycache__", ".pytest_cache", "node_modules", ".worktrees", ".git"}

IMPORT_TO_DIST: dict[str, str] = {}


def _plugin_py_files() -> list[Path]:
    return [
        p
        for p in PLUGIN_ROOT.rglob("*.py")
        if not any(part in EXCLUDED_DIRS for part in p.parts)
    ]


def _local_module_names() -> set[str]:
    """Names that refer to plugin-local modules/packages, not pypi distributions.

    A name is local if it matches either:
      - a directory containing __init__.py (regular package), or
      - a directory containing any .py children (PEP 420 namespace package), or
      - the stem of any .py file in the plugin (a sibling module reachable via
        cwd-rooted imports when scripts are invoked directly).
    """
    names: set[str] = set()
    for p in PLUGIN_ROOT.rglob("*"):
        if any(part in EXCLUDED_DIRS for part in p.parts):
            continue
        if p.is_dir():
            if (p / "__init__.py").exists():
                names.add(p.name)
            elif any(child.is_file() and child.suffix == ".py" for child in p.iterdir()):
                names.add(p.name)
        elif p.is_file() and p.suffix == ".py" and p.name != "__init__.py":
            names.add(p.stem)
    return names


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


def _strip_specifier(dep: str) -> str:
    """Return the lowercased distribution name from a PEP 508 dependency string.

    Splits on the first PEP 508 separator: comparison ops (>, <, =, !, ~),
    extras opener `[`, environment-marker `;`, whitespace, comma. The naive
    chained ``str.split`` form silently mis-parses ``>``, ``~=``, ``!=`` and
    PEP 508 environment markers as part of the dist name.
    """
    return re.split(r"[><=!~\[;\s,]", dep, maxsplit=1)[0].strip().lower()


def _declared_dists() -> set[str]:
    pyproject = PLUGIN_ROOT / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text())
    deps = list(data["project"].get("dependencies", []))
    for group_deps in data.get("dependency-groups", {}).values():
        deps.extend(group_deps)
    return {_strip_specifier(d) for d in deps}


def test_every_import_is_stdlib_local_or_declared():
    """Each top-level import must be stdlib, plugin-local, or declared in pyproject."""
    stdlib = set(sys.stdlib_module_names)
    local = _local_module_names()
    declared = _declared_dists()
    files = _plugin_py_files()
    assert files, "scan found no .py files -- test broken or plugin empty"

    leaks: dict[str, list[Path]] = {}
    for f in files:
        for imp in _top_level_imports(f):
            if imp in stdlib or imp in local:
                continue
            dist = IMPORT_TO_DIST.get(imp, imp).lower()
            if dist in declared:
                continue
            leaks.setdefault(imp, []).append(f.relative_to(PLUGIN_ROOT))

    if leaks:
        msg_lines = ["Undeclared imports (add to pyproject.toml or stdlib check):"]
        for imp, paths in sorted(leaks.items()):
            msg_lines.append(f"  {imp}:")
            for p in paths:
                msg_lines.append(f"    {p}")
        raise AssertionError("\n".join(msg_lines))


def test_pyproject_required_fields():
    """pyproject.toml must declare name, version, requires-python, dependencies."""
    pyproject = PLUGIN_ROOT / "pyproject.toml"
    assert pyproject.is_file(), f"missing {pyproject}"
    data = tomllib.loads(pyproject.read_text())
    project = data["project"]
    assert project["name"] == "cc-sciencepal"
    assert project["version"]
    assert project["requires-python"]
    assert project["dependencies"]


@pytest.mark.parametrize(
    ("dep", "expected"),
    [
        ("click>=8.1", "click"),
        ("pymupdf>1.24", "pymupdf"),
        ("requests~=2.31", "requests"),
        ("foo!=2.0", "foo"),
        ("openreview-py<=2.0", "openreview-py"),
        ("requests<3", "requests"),
        ("name[extras]>=1.0", "name"),
        ('name; python_version >= "3.12"', "name"),
        ("Pillow", "pillow"),
        ("ruff==0.6.0", "ruff"),
        ("foo===1.2.3", "foo"),
    ],
)
def test_strip_specifier_handles_pep508_forms(dep: str, expected: str):
    """`_strip_specifier` survives the full PEP 508 separator set.

    Regression alarm for the chained-``str.split`` form (only handled ``>=``,
    ``==``, ``<``, ``[``) -- silently mis-parsed bare ``>``, ``~=``, ``!=`` and
    environment markers as part of the dist name.
    """
    assert _strip_specifier(dep) == expected


def test_no_local_module_shadows_declared_import():
    """Forward guard: a plugin-local file/dir name must not shadow a declared dep's
    import name.

    Without this, `skills/foo/requests.py` would silently mark `requests` as local
    and bypass the leak check for any future undeclared `from requests import ...`.
    """
    local = _local_module_names()
    declared = _declared_dists()
    declared_imports = set(declared) | {
        imp for imp, dist in IMPORT_TO_DIST.items() if dist in declared
    }
    shadows = local & declared_imports
    assert not shadows, f"local module shadows declared dep import name: {sorted(shadows)}"
