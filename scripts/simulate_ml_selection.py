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

LOG_PATH = Path("tests/test_run_log.jsonl")
SELECTED_TAGS_FILE = Path("selected_tags.txt")


def main():
    changed_files = os.getenv("GIT_CHANGED_FILES", "").split()
    entries = []
    if LOG_PATH.exists():
        with LOG_PATH.open("r", encoding="utf-8") as handle:
            entries = [json.loads(line) for line in handle if line.strip()]

    selected_tags = {"@smoke", "@critical"}
    changed_blob = " ".join(changed_files).lower()
    if "add" in changed_blob:
        selected_tags.add("@addition")
    if "subtract" in changed_blob:
        selected_tags.add("@subtraction")
    if "add" not in changed_blob and "subtract" not in changed_blob:
        selected_tags.add("@happy_path")

    selected_expr = " or ".join(sorted(selected_tags))
    SELECTED_TAGS_FILE.write_text(selected_expr, encoding="utf-8")

    total_tests = len(entries)
    selected_tests = sum(1 for e in entries if set(e.get("tags", [])) & set(tag.strip("@") for tag in selected_tags))
    if total_tests == 0:
        selected_tests = 0
    ratio = int((selected_tests / total_tests) * 100) if total_tests else 0

    print("── ML Test Selector ──────────────────────")
    print(f"Changed files : {' '.join(changed_files) if changed_files else '(none)'}")
    print(f"Total tests   : {total_tests}")
    print(f"Selected tests: {selected_tests} ({ratio}%)")
    print("Strategy      : heuristic (replace with model in v2)")
    print(f"Selected tags : {selected_expr}")
    print("──────────────────────────────────────────")


if __name__ == "__main__":
    main()
