"""Resolve test tags from a dependency graph given a set of changed files."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Set

from .builder import DependencyGraph, _broadcast_scope


def resolve_tags(changed_files: List[str], graph: DependencyGraph) -> Set[str]:
    """Return all test tags transitively affected by *changed_files*.

    Special case: if a changed file is a broadcaster (environment.py,
    playwright.config.ts, etc.), its scope of test nodes is immediately
    added without further traversal — the broadcaster edges in the graph
    already handle this, but this early-exit makes the intent explicit.
    """
    affected: Set[str] = set()

    for f in changed_files:
        normalized = Path(f).as_posix()

        # Broadcaster files (environment.py, playwright.config.ts, …) are
        # already wired to all relevant test nodes via graph edges, so the
        # normal traversal picks them up correctly.  No special-casing needed.
        affected.update(graph.affected_by(normalized))

    return graph.tags_for_files(affected)


def explain_graph_impact(
    changed_files: List[str],
    graph: DependencyGraph,
) -> Dict[str, object]:
    """Structured explanation of graph-based impact for --explain output."""
    per_file: Dict[str, dict] = {}
    all_tags: Set[str] = set()

    for f in changed_files:
        normalized = Path(f).as_posix()
        affected = graph.affected_by(normalized)
        tags = graph.tags_for_files(affected)
        all_tags.update(tags)
        chains = graph.dependency_chain(normalized)

        broadcaster_scope = _broadcast_scope(normalized)
        per_file[normalized] = {
            "is_broadcaster": broadcaster_scope is not None,
            "broadcaster_scope": broadcaster_scope,
            "affected_nodes": sorted(affected - {normalized}),
            "chains": {k: " -> ".join(v) for k, v in chains.items()},
            "tags_found": sorted(tags),
        }

    return {"per_file": per_file, "total_tags": sorted(all_tags)}
