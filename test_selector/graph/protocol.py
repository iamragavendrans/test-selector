"""Universal JSON protocol for dependency graphs.

This is the interchange format between language-specific extractors and the
selector engine.  Any language/framework can implement an extractor that
outputs this schema — the selector engine stays language-agnostic.

Schema
------
{
  "version": "1.0",
  "nodes": [
    {"id": "src/Calculator.java", "type": "source", "tags": [], "metadata": {}},
    {"id": "test/CalculatorTest.java", "type": "test", "tags": ["@smoke"], "metadata": {}}
  ],
  "edges": [
    {"from": "src/Calculator.java", "to": "test/CalculatorTest.java", "kind": "imports"}
  ]
}

Node types
----------
source   — production code (not a test file itself)
test     — a test file; carries test tags
config   — framework/runner config file (change → all tests affected)
data     — test data file (CSV, JSON, XML) read by tests
fixture  — shared test setup file (conftest.py, environment.py, *-fixtures.ts)

Edge kinds
----------
imports        — file A imports/requires file B
step-implements — step definition file implements steps used by a feature file
configures     — config file controls a test or source file
reads          — test reads a data file at runtime
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class GraphNode:
    id: str
    type: str = "source"       # source | test | config | data | fixture
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    from_: str
    to: str
    kind: str = "imports"      # imports | step-implements | configures | reads


@dataclass
class GraphSpec:
    """Portable, JSON-serializable representation of a dependency graph."""

    version: str = "1.0"
    nodes: List[GraphNode] = field(default_factory=list)
    edges: List[GraphEdge] = field(default_factory=list)

    # ── serialisation ───────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "nodes": [
                {"id": n.id, "type": n.type, "tags": n.tags, "metadata": n.metadata}
                for n in self.nodes
            ],
            "edges": [
                {"from": e.from_, "to": e.to, "kind": e.kind}
                for e in self.edges
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    # ── deserialisation ─────────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, data: dict) -> "GraphSpec":
        nodes = [
            GraphNode(
                id=n["id"],
                type=n.get("type", "source"),
                tags=n.get("tags", []),
                metadata=n.get("metadata", {}),
            )
            for n in data.get("nodes", [])
        ]
        edges = [
            GraphEdge(from_=e["from"], to=e["to"], kind=e.get("kind", "imports"))
            for e in data.get("edges", [])
        ]
        return cls(version=data.get("version", "1.0"), nodes=nodes, edges=edges)

    @classmethod
    def from_json(cls, text: str) -> "GraphSpec":
        return cls.from_dict(json.loads(text))
