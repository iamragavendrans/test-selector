#!/usr/bin/env python3
"""
Stand-in for the ML model. In production, this script would:
  1. Load a trained classifier (e.g., gradient boosted tree)
  2. Feature-encode: changed files + test metadata
  3. Predict P(fail) for each test
  4. Select top-K tests by predicted risk / time budget

For now, implements a rule-based heuristic that mimics ML behavior
and outputs the same interface the real ML model would use.
"""

import json
import os
from pathlib import Path

import yaml

LOG_PATH = Path("tests/test_run_log.jsonl")
MAPPING_PATH = Path("config/test_selection_map.yaml")
SELECTED_TAGS_FILE = Path("selected_tags.txt")
SELECTION_REASON_FILE = Path("selection_reason.json")


def load_entries(path: Path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def load_mapping(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Mapping file missing: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def changed_files_from_env():
    raw = os.getenv("GIT_CHANGED_FILES", "")
    parts = [p for p in raw.split() if p.strip()]
    return parts


def compute_selected_tags(changed_files, mapping):
    defaults = mapping.get("default", {})
    selected_tags = set(defaults.get("include_tags", ["@smoke", "@critical"]))
    matched_rules = []

    for rule in mapping.get("mappings", []):
        rule_hits = [
            f for f in changed_files
            if any(token in f for token in rule.get("match_any", []))
        ]
        if rule_hits:
            selected_tags.update(rule.get("include_tags", []))
            matched_rules.append(
                {
                    "id": rule.get("id", "unknown"),
                    "matched_files": rule_hits,
                    "added_tags": rule.get("include_tags", []),
                    "rationale": rule.get("rationale", ""),
                }
            )

    if not matched_rules:
        fallback = defaults.get("fallback_tags", ["@happy_path"])
        selected_tags.update(fallback)
        matched_rules.append(
            {
                "id": "default_fallback",
                "matched_files": changed_files,
                "added_tags": fallback,
                "rationale": defaults.get("rationale", "fallback"),
            }
        )

    return selected_tags, matched_rules


def main():
    changed_files = changed_files_from_env()
    entries = load_entries(LOG_PATH)
    mapping = load_mapping(MAPPING_PATH)

    selected_tags, matched_rules = compute_selected_tags(changed_files, mapping)
    selected_expr = " or ".join(sorted(selected_tags))
    SELECTED_TAGS_FILE.write_text(selected_expr, encoding="utf-8")

    total_tests = len(entries)
    if total_tests:
        selected_count = sum(
            1
            for row in entries
            if set(row.get("tags", [])) & {tag.lstrip("@") for tag in selected_tags}
        )
    else:
        selected_count = 0

    pct = int((selected_count / total_tests) * 100) if total_tests else 0
    reason_payload = {
        "changed_files": changed_files,
        "selected_tags_expression": selected_expr,
        "selected_tags": sorted(selected_tags),
        "matched_rules": matched_rules,
        "total_tests_seen": total_tests,
        "selected_tests_estimate": selected_count,
        "selected_percent_estimate": pct,
        "strategy": "heuristic (replace with model in v2)",
        "mapping_file": str(MAPPING_PATH),
    }
    SELECTION_REASON_FILE.write_text(json.dumps(reason_payload, indent=2), encoding="utf-8")

    print("── ML Test Selector ──────────────────────")
    print(f"Changed files : {' '.join(changed_files) if changed_files else '(none)'}")
    print(f"Total tests   : {total_tests}")
    print(f"Selected tests: {selected_count} ({pct}%)")
    print("Strategy      : heuristic (replace with model in v2)")
    print(f"Selected tags : {selected_expr}")
    print("──────────────────────────────────────────")


if __name__ == "__main__":
    main()
