from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from .changes import FileChange, filter_impactful, parse_name_status
from .selector import explain_selection, format_tags, load_config, select_tags

FORMATS = ("expr", "json", "lines", "playwright", "pytest")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="test-selector",
        description="Select tests to run based on changed files and a YAML mapping config.",
    )

    source = p.add_mutually_exclusive_group()
    source.add_argument(
        "--changed-files",
        metavar="FILES",
        help="Space-separated changed file paths (falls back to GIT_CHANGED_FILES env var).",
    )
    source.add_argument(
        "--from-git",
        action="store_true",
        help="Auto-detect changed files via git diff instead of passing them manually.",
    )

    p.add_argument(
        "--git-base",
        metavar="REF",
        default="HEAD~1",
        help="Base git ref for --from-git diff (default: HEAD~1). Use origin/main for PRs.",
    )
    p.add_argument(
        "--config",
        default="test_selection_map.yaml",
        metavar="PATH",
        help="Path to the YAML mapping config (default: test_selection_map.yaml in CWD).",
    )
    p.add_argument(
        "--format",
        choices=FORMATS,
        default="expr",
        help=(
            "Output format: expr (behave, default), json, lines, "
            "playwright (regex for --grep), pytest (marks without @)."
        ),
    )
    p.add_argument(
        "--output",
        metavar="FILE",
        help="Optional file to write the result into (in addition to stdout).",
    )
    graph_source = p.add_mutually_exclusive_group()
    graph_source.add_argument(
        "--graph",
        action="store_true",
        help=(
            "Build a code dependency graph (AST + imports) from the repo and use it "
            "to find affected tests. Results are unioned with YAML selection."
        ),
    )
    graph_source.add_argument(
        "--graph-file",
        metavar="PATH",
        help=(
            "Load a pre-built dependency graph JSON instead of scanning the repo. "
            "Use '-' to read from stdin. Accepts output from any language extractor "
            "(Java JAR, Ruby gem, etc.) that follows the GraphSpec protocol."
        ),
    )
    p.add_argument(
        "--export-graph",
        metavar="PATH",
        help="After building the graph (--graph), also write it as JSON to this path.",
    )
    p.add_argument(
        "--repo-root",
        metavar="PATH",
        help="Repository root for --graph (default: auto-detected via git).",
    )
    p.add_argument(
        "--explain",
        action="store_true",
        help="Print a human-readable breakdown of which rules matched and why (to stderr).",
    )
    return p


def _git(args: list[str]) -> str:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"test-selector: git error: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def _find_repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True,
    )
    return Path(result.stdout.strip()) if result.returncode == 0 else Path.cwd()


def _impactful_from_git(base_ref: str) -> tuple[list[str], list[FileChange]]:
    name_status = _git(["git", "diff", "--name-status", base_ref, "HEAD"])
    changes = parse_name_status(name_status)

    def get_diff(path: str) -> str:
        return _git(["git", "diff", "--unified=0", base_ref, "HEAD", "--", path])

    return filter_impactful(changes, diff_getter=get_diff)


def _print_explanation(
    explanation: dict,
    skipped: list[FileChange] | None = None,
    graph_impact: dict | None = None,
) -> None:
    sep = "-" * 52
    print(sep, file=sys.stderr)
    print("  test-selector - selection breakdown", file=sys.stderr)
    print(sep, file=sys.stderr)

    if skipped:
        print("  Skipped (cosmetic):", file=sys.stderr)
        for s in skipped:
            reason = "pure rename" if s.old_path else "trivial diff (blanks/comments/imports only)"
            label = f"{s.old_path} -> {s.path}" if s.old_path else s.path
            print(f"    {label}  [{reason}]", file=sys.stderr)

    files = explanation["changed_files"]
    print(f"  Impactful files: {' '.join(files) if files else '(none)'}", file=sys.stderr)
    print(f"  Always tags    : {' '.join(explanation['always_tags'])}", file=sys.stderr)

    if explanation["matched_mappings"]:
        print("  YAML rules     :", file=sys.stderr)
        for m in explanation["matched_mappings"]:
            print(f"    [{m['id']}] hit: {m['hit_files']}", file=sys.stderr)
            print(f"      tags     : {' '.join(m['tags'])}", file=sys.stderr)
            print(f"      rationale: {m['rationale']}", file=sys.stderr)
    else:
        print("  YAML rules     : (none - using fallback tags)", file=sys.stderr)

    if graph_impact:
        print("  Graph analysis :", file=sys.stderr)
        for changed_path, info in graph_impact["per_file"].items():
            print(f"    {changed_path}", file=sys.stderr)
            for node, chain in info["chains"].items():
                tags = ", ".join(info["tags_found"]) if info["tags_found"] else "(no tags)"
                print(f"      -> {node}  [{chain}]", file=sys.stderr)
            if info["tags_found"]:
                print(f"      tags: {' '.join(info['tags_found'])}", file=sys.stderr)
        print(f"  Graph tags     : {' '.join(graph_impact['total_tags'])}", file=sys.stderr)

    print(f"  Final tags     : {' '.join(explanation['final_tags'])}", file=sys.stderr)
    print(sep, file=sys.stderr)


def main() -> None:
    args = build_parser().parse_args()

    skipped: list[FileChange] = []
    if args.from_git:
        changed_files, skipped = _impactful_from_git(args.git_base)
    else:
        raw = args.changed_files or os.getenv("GIT_CHANGED_FILES", "")
        changed_files = raw.split() if raw.strip() else []

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"test-selector: config not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    config = load_config(config_path)
    tags = select_tags(changed_files, config)

    # ── Graph-based analysis (opt-in with --graph or --graph-file) ──────────
    graph_impact: dict | None = None
    if args.graph or args.graph_file:
        from .graph.builder import DependencyGraph, build
        from .graph.protocol import GraphSpec
        from .graph.resolver import explain_graph_impact, resolve_tags

        if args.graph_file:
            # Load a pre-built graph from any language extractor.
            text = sys.stdin.read() if args.graph_file == "-" else \
                   Path(args.graph_file).read_text(encoding="utf-8")
            graph = DependencyGraph.from_spec(GraphSpec.from_json(text))
        else:
            repo_root = Path(args.repo_root) if args.repo_root else _find_repo_root()
            graph = build(repo_root)
            if args.export_graph:
                Path(args.export_graph).write_text(
                    graph.to_spec().to_json(), encoding="utf-8"
                )

        graph_tags = resolve_tags(changed_files, graph)
        tags = tags | graph_tags

        if args.explain:
            graph_impact = explain_graph_impact(changed_files, graph)

    if args.explain:
        # Rebuild explanation with union tags for the final_tags field.
        exp = explain_selection(changed_files, config)
        exp["final_tags"] = sorted(format_tags(tags, "lines").splitlines())
        _print_explanation(exp, skipped=skipped, graph_impact=graph_impact)

    result = format_tags(tags, args.format)
    print(result)

    if args.output:
        Path(args.output).write_text(result, encoding="utf-8")


if __name__ == "__main__":
    main()
