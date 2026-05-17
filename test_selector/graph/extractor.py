"""Extract dependency information from individual source files.

Each function is pure (no side effects, no global state) so it is
trivially testable and replaceable with a smarter version later.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Directories that are never part of the project source tree.
SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"}


def _skip(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


# ── Python: import graph ────────────────────────────────────────────────────


def extract_python_local_imports(path: Path, repo_root: Path) -> List[Path]:
    """Return paths of locally-resolved modules imported by *path*.

    Uses Python's ast module — no runtime imports needed.
    Only files that actually exist inside repo_root are returned
    (stdlib / third-party imports are ignored).
    """
    if _skip(path):
        return []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return []

    results: List[Path] = []
    package_dir = path.parent

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                r = _resolve_py_module(alias.name, repo_root)
                if r and r != path:
                    results.append(r)

        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                # Relative import — compute absolute module name from package dir.
                base = package_dir
                for _ in range(node.level - 1):
                    base = base.parent
                try:
                    prefix = ".".join(base.relative_to(repo_root).parts)
                except ValueError:
                    continue
                module_name = f"{prefix}.{node.module}" if node.module else prefix
            else:
                module_name = node.module or ""

            r = _resolve_py_module(module_name, repo_root)
            if r and r != path:
                results.append(r)

    return list(dict.fromkeys(results))   # deduplicate, preserve order


def _resolve_py_module(module_name: str, repo_root: Path) -> Optional[Path]:
    """'a.b.c' → repo_root/a/b/c.py  or  repo_root/a/b/c/__init__.py, or None."""
    if not module_name:
        return None
    parts = module_name.split(".")
    candidate = repo_root.joinpath(*parts)
    if (f := candidate.with_suffix(".py")).exists():
        return f
    if (f := candidate / "__init__.py").exists():
        return f
    return None


# ── Python: step definitions (Behave) ──────────────────────────────────────

_STEP_KEYWORDS = {"given", "when", "then", "step"}


def extract_step_patterns(path: Path) -> List[Tuple[str, str]]:
    """Return [(keyword, pattern), ...] from @given/@when/@then decorated functions.

    Handles both ``@given("pattern")`` and ``@step("pattern")`` forms.
    Supports Parse-style patterns like ``"I add {a:d} and {b}"`` as well as
    plain strings.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return []

    results: List[Tuple[str, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for deco in node.decorator_list:
            name, args = _unpack_decorator(deco)
            if name and name.lower() in _STEP_KEYWORDS and args:
                first = args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    results.append((name.lower(), first.value))

    return results


def _unpack_decorator(deco: ast.expr) -> Tuple[Optional[str], list]:
    if isinstance(deco, ast.Call):
        func = deco.func
        name = func.id if isinstance(func, ast.Name) else (
            func.attr if isinstance(func, ast.Attribute) else None
        )
        return name, deco.args
    if isinstance(deco, ast.Name):
        return deco.id, []
    return None, []


def step_pattern_to_regex(pattern: str) -> re.Pattern:
    """Convert a Parse-style step pattern to a matching regex.

    ``"I add {a:d} to {b}"``  →  regex matching ``"I add 5 to foo"``
    """
    parts = re.split(r"\{[^}]+\}", pattern)
    regex = "(.+)".join(re.escape(p) for p in parts)
    return re.compile(r"^\s*" + regex + r"\s*$", re.IGNORECASE)


def match_step_to_files(
    step_text: str,
    step_patterns: Dict[Path, List[Tuple[str, str]]],
) -> List[Path]:
    """Return step definition files whose patterns match *step_text*."""
    matched: List[Path] = []
    for step_file, patterns in step_patterns.items():
        for _, pattern in patterns:
            try:
                if step_pattern_to_regex(pattern).match(step_text):
                    matched.append(step_file)
                    break
            except re.error:
                pass
    return matched


# ── Gherkin: feature files ─────────────────────────────────────────────────

_STEP_LINE_RE = re.compile(
    r"^\s+(?:Given|When|Then|And|But)\s+(.+)$",
    re.MULTILINE | re.IGNORECASE,
)


def extract_feature_info(path: Path) -> Dict:
    """Return ``{'tags': [...], 'steps': [...]}`` from a Gherkin ``.feature`` file.

    Tags come from ``@tagname`` annotations on Feature/Scenario/Outline lines.
    Steps are the raw step texts (after the keyword).
    """
    try:
        content = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return {"tags": [], "steps": []}

    tags = list({f"@{t}" for t in re.findall(r"@(\w+)", content)})
    steps = [s.strip() for s in _STEP_LINE_RE.findall(content)]
    return {"tags": tags, "steps": steps}


# ── TypeScript: import graph and tag extraction ────────────────────────────

_TS_IMPORT_RE = re.compile(r"""(?:import|from)\s+['"](\.[^'"]+)['"]""")

# Match tags only inside test.describe('...@tag...') and test('...@tag...')
# to avoid picking up @playwright/test package names as tags.
_TS_DESCRIBE_RE = re.compile(r"""test(?:\.describe)?\s*\(\s*['"]([^'"]+)['"]""")


def extract_ts_local_imports(path: Path, repo_root: Path) -> List[Path]:
    """Return locally-resolved import paths from a TypeScript/JavaScript file.

    Only relative imports (starting with ``.`` or ``..``) are resolved;
    package imports are ignored.
    """
    if _skip(path):
        return []
    try:
        content = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    repo_resolved = repo_root.resolve()
    results: List[Path] = []

    for rel_import in _TS_IMPORT_RE.findall(content):
        candidate = (path.parent / rel_import).resolve()
        for ext in (".ts", ".tsx", ".js", ".jsx"):
            # Append the extension as a string — with_suffix() would replace
            # the last suffix of multi-part names like 'login.page'.
            p = candidate.parent / (candidate.name + ext)
            if p.exists():
                try:
                    results.append(repo_root / p.relative_to(repo_resolved))
                except ValueError:
                    pass
                break
        else:
            for idx in ("index.ts", "index.js"):
                p = candidate / idx
                if p.exists():
                    try:
                        results.append(repo_root / p.relative_to(repo_resolved))
                    except ValueError:
                        pass
                    break

    return results


def extract_ts_tags(path: Path) -> List[str]:
    """Extract ``@tagname`` annotations from ``test.describe()`` / ``test()`` strings.

    Only string arguments to test functions are scanned so that package
    names like ``@playwright/test`` are not misidentified as test tags.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    tags: set[str] = set()
    for match in _TS_DESCRIBE_RE.finditer(content):
        for tag in re.findall(r"@(\w+)", match.group(1)):
            tags.add(f"@{tag}")
    return list(tags)


# ── Python: pytest marks ────────────────────────────────────────────────────

# Built-in pytest marks that control test mechanics, not test categorisation.
# These are not meaningful for test selection and are filtered out.
_PYTEST_INFRA_MARKS = frozenset({"parametrize", "usefixtures", "filterwarnings"})


def extract_pytest_marks(path: Path) -> List[str]:
    """Extract ``@pytest.mark.X`` tags from a Python test file.

    Scans test functions (``test_*``) and test classes (``Test*``) for
    ``@pytest.mark.X`` and ``@pytest.mark.X(...)`` decorators.
    Returns tags as ``["@X", ...]`` to match the Behave/Playwright format.
    Built-in infrastructure marks (parametrize, usefixtures, filterwarnings)
    are excluded — they control test mechanics, not test category.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return []

    marks: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if not (node.name.startswith("test") or node.name.startswith("Test")):
            continue
        for deco in node.decorator_list:
            mark = _extract_pytest_mark_name(deco)
            if mark and mark not in _PYTEST_INFRA_MARKS:
                marks.add(f"@{mark}")

    return list(marks)


def _extract_pytest_mark_name(deco: ast.expr) -> Optional[str]:
    """Return the mark name from ``@pytest.mark.X`` or ``@pytest.mark.X(...)``."""
    func = deco.func if isinstance(deco, ast.Call) else deco
    # pytest.mark.X  →  Attribute(value=Attribute(value=Name(id='pytest'), attr='mark'), attr='X')
    if (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Attribute)
        and isinstance(func.value.value, ast.Name)
        and func.value.value.id == "pytest"
        and func.value.attr == "mark"
    ):
        return func.attr
    return None
