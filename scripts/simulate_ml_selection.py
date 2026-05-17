#!/usr/bin/env python3
"""
Stand-in for the ML model. Delegates all selection logic to the
test_selector package so there is a single source of truth.

In production v2, replace the heuristic engine in test_selector/selector.py
with a trained classifier (gradient boosted tree, etc.) — this script stays
the same.
"""

import os
import sys
from pathlib import Path

# Allow running from repo root before the package is installed
sys.path.insert(0, str(Path(__file__).parent.parent))

from test_selector.selector import explain_selection, format_tags, load_config, select_tags

CONFIG_PATH = Path("config/test_selection_map.yaml")
SELECTED_TAGS_FILE = Path("selected_tags.txt")


def main() -> None:
    changed_files = [f for f in os.getenv("GIT_CHANGED_FILES", "").split() if f]
    config = load_config(CONFIG_PATH)
    explanation = explain_selection(changed_files, config)
    tags = select_tags(changed_files, config)
    result = format_tags(tags, "expr")

    SELECTED_TAGS_FILE.write_text(result, encoding="utf-8")

    print("-- ML Test Selector ------------------------------")
    print(f"  Changed files : {' '.join(changed_files) or '(none)'}")
    if explanation["matched_mappings"]:
        for m in explanation["matched_mappings"]:
            print(f"  Rule matched  : [{m['id']}] - {m['rationale']}")
    else:
        print("  Strategy      : fallback (no mapping matched changed files)")
    print(f"  Selected tags : {result}")
    print("--------------------------------------------------")


if __name__ == "__main__":
    main()
