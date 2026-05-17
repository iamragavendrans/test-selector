"""Build a directed dependency graph from the repository source tree.

Graph semantics
---------------
An edge  A → B  means "B depends on A".
Consequence: if A changes, B *may* be affected.

Node identifiers are POSIX-relative paths (relative to repo_root) stored as
plain strings, matching the format git diff produces.

Convention-based rules (not derivable from imports)
----------------------------------------------------
The following files are treated as broadcasting dependencies — a change to
any of them can affect ALL test files in their scope:

  environment.py      Behave lifecycle hooks, auto-discovered by filename.
  conftest.py         pytest shared fixtures, auto-discovered by filename.
  *-fixtures.ts       Playwright shared fixture files.
  playwright.config.* Playwright runner configuration (testDir, projects, etc.)
  behave.ini          Behave runner configuration.
  pytest.ini          pytest runner configuration.
  setup.cfg           setuptools/pytest configuration.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Set

import networkx as nx

from .extractor import (
    SKIP_DIRS,
    extract_feature_info,
    extract_pytest_marks,
    extract_python_local_imports,
    extract_step_patterns,
    extract_ts_local_imports,
    extract_ts_tags,
    match_step_to_files,
)

TagMap = Dict[str, List[str]]   # node_id → list of test tags

# Files whose change should broadcast to every test in their scope.
# The value is the glob scope: "feature" (behave), "spec" (playwright), "all".
_BROADCAST_BY_NAME: Dict[str, str] = {
    "environment.py": "feature",   # behave auto-discovery
    "conftest.py":    "all",        # pytest auto-discovery
    "behave.ini":     "feature",
    "pytest.ini":     "all",
    "setup.cfg":      "all",
}

_BROADCAST_PREFIXES: Dict[str, str] = {
    "playwright.config": "spec",    # playwright.config.ts / .js
    "jest.config":       "spec",
    "vitest.config":     "spec",
}

def _broadcast_scope(rel_path: str) -> str | None:
    """Return the broadcast scope if *rel_path* is auto-discovered by a test runner.

    Only files that test runners discover by CONVENTION (not by import) are
    broadcasters.  Files that are explicitly imported are already covered by the
    import graph and must NOT be treated as broadcasters — that would cause every
    transitive change to spread to all tests.
    """
    name = Path(rel_path).name
    if name in _BROADCAST_BY_NAME:
        return _BROADCAST_BY_NAME[name]
    stem = name.rsplit(".", 1)[0]
    for prefix, scope in _BROADCAST_PREFIXES.items():
        if stem == prefix or name.startswith(prefix + "."):
            return scope
    return None


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _skip(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


class DependencyGraph:
    """Reverse dependency graph for test impact analysis.

    An edge dep → dependent means: if dep changes, dependent is affected.
    ``tag_map`` records which test tags are associated with each file.
    """

    def __init__(self) -> None:
        self._g: nx.DiGraph = nx.DiGraph()
        self.tag_map: TagMap = {}

    def add_dependency(self, dependency: str, dependent: str) -> None:
        self._g.add_edge(dependency, dependent)

    def record_tags(self, node: str, tags: List[str]) -> None:
        self.tag_map[node] = tags

    def all_test_nodes(self) -> Set[str]:
        """Return every node that has at least one test tag."""
        return {n for n, tags in self.tag_map.items() if tags}

    def affected_by(self, changed_path: str) -> Set[str]:
        if changed_path not in self._g:
            return {changed_path}
        return nx.descendants(self._g, changed_path) | {changed_path}

    def tags_for_files(self, file_paths: Set[str]) -> Set[str]:
        tags: Set[str] = set()
        for p in file_paths:
            tags.update(self.tag_map.get(p, []))
        return tags

    def node_count(self) -> int:
        return self._g.number_of_nodes()

    def edge_count(self) -> int:
        return self._g.number_of_edges()

    def dependency_chain(self, changed_path: str) -> Dict[str, List[str]]:
        if changed_path not in self._g:
            return {}
        chains: Dict[str, List[str]] = {}
        for target in nx.descendants(self._g, changed_path):
            try:
                chains[target] = nx.shortest_path(self._g, changed_path, target)
            except nx.NetworkXNoPath:
                pass
        return chains

    # ── Protocol serialisation ───────────────────────────────────────────────

    def to_spec(self) -> "GraphSpec":  # type: ignore[name-defined]
        """Export this graph to a portable, JSON-serialisable GraphSpec."""
        from .protocol import GraphEdge, GraphNode, GraphSpec

        node_ids = set(self._g.nodes()) | set(self.tag_map.keys())
        nodes = []
        for nid in node_ids:
            tags = self.tag_map.get(nid, [])
            node_type = "test" if tags else "source"
            nodes.append(GraphNode(id=nid, type=node_type, tags=tags))

        edges = [GraphEdge(from_=f, to=t) for f, t in self._g.edges()]
        return GraphSpec(nodes=nodes, edges=edges)

    @classmethod
    def from_spec(cls, spec: "GraphSpec") -> "DependencyGraph":  # type: ignore[name-defined]
        """Reconstruct a DependencyGraph from any GraphSpec (e.g. from a Java extractor)."""
        g = cls()
        for node in spec.nodes:
            if node.tags:
                g.record_tags(node.id, node.tags)
        for edge in spec.edges:
            g.add_dependency(edge.from_, edge.to)
        return g


def build(repo_root: Path) -> DependencyGraph:
    """Scan *repo_root* and return a fully populated DependencyGraph.

    Scanning order:
    1. Collect all step definition patterns (needed to link features → steps).
    2. Build Python import edges (ast-based, handles relative imports).
    3. Build feature file nodes with tag metadata + step→feature edges.
    4. Build TypeScript import edges + spec file tag metadata.
    5. Wire convention-based broadcasters (environment.py, config files, etc.)
    """
    g = DependencyGraph()

    # ── 1. Step definition patterns ─────────────────────────────────────────
    step_patterns: dict[Path, list] = {}
    for step_file in repo_root.rglob("*_steps.py"):
        if _skip(step_file):
            continue
        patterns = extract_step_patterns(step_file)
        if patterns:
            step_patterns[step_file] = patterns

    # ── 2. Python import graph ───────────────────────────────────────────────
    for py_file in repo_root.rglob("*.py"):
        if _skip(py_file):
            continue
        rel_file = _rel(py_file, repo_root)
        for dep in extract_python_local_imports(py_file, repo_root):
            g.add_dependency(_rel(dep, repo_root), rel_file)

    # ── 3. Feature files: tags + step→feature edges ──────────────────────────
    for feature_file in repo_root.rglob("*.feature"):
        if _skip(feature_file):
            continue
        rel_feature = _rel(feature_file, repo_root)
        info = extract_feature_info(feature_file)
        g.record_tags(rel_feature, info["tags"])

        for step_text in info["steps"]:
            for matched in match_step_to_files(step_text, step_patterns):
                g.add_dependency(_rel(matched, repo_root), rel_feature)

    # ── 4. TypeScript import graph + spec tags ───────────────────────────────
    for ts_file in repo_root.rglob("*.ts"):
        if _skip(ts_file):
            continue
        rel_ts = _rel(ts_file, repo_root)
        for dep in extract_ts_local_imports(ts_file, repo_root):
            g.add_dependency(_rel(dep, repo_root), rel_ts)

        if ts_file.name.endswith(".spec.ts"):
            g.record_tags(rel_ts, extract_ts_tags(ts_file))

    # ── 5. pytest test files: marks as tags ────────────────────────────────────
    for py_file in repo_root.rglob("*.py"):
        if _skip(py_file):
            continue
        name = py_file.name
        if name.startswith("test_") or name.endswith("_test.py"):
            marks = extract_pytest_marks(py_file)
            if marks:
                g.record_tags(_rel(py_file, repo_root), marks)

    # ── 6. Convention-based broadcasters ────────────────────────────────────
    # These files are auto-discovered by test runners (not via imports), so
    # the import graph cannot detect their influence.  We wire them explicitly:
    # a broadcaster → every test file it governs.
    feature_nodes = {n for n in g.tag_map if n.endswith(".feature")}
    spec_nodes    = {n for n in g.tag_map if n.endswith(".spec.ts")}
    pytest_nodes  = {
        n for n in g.tag_map
        if n.endswith(".py") and (
            Path(n).name.startswith("test_") or Path(n).name.endswith("_test.py")
        )
    }
    all_test_nodes = feature_nodes | spec_nodes | pytest_nodes

    for candidate in repo_root.rglob("*"):
        if _skip(candidate) or candidate.is_dir():
            continue
        rel = _rel(candidate, repo_root)
        scope = _broadcast_scope(rel)
        if scope is None:
            continue
        targets = (
            feature_nodes if scope == "feature" else
            spec_nodes    if scope == "spec"    else
            all_test_nodes
        )
        for test_node in targets:
            g.add_dependency(rel, test_node)

    return g
