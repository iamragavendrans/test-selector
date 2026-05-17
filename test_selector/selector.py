from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Set

import yaml


def load_config(config_path: Path) -> dict:
    with config_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def select_tags(changed_files: List[str], config: dict) -> Set[str]:
    default = config.get("default", {})
    always: Set[str] = set(default.get("include_tags", []))
    fallback: Set[str] = set(default.get("fallback_tags", []))

    matched: Set[str] = set()
    for mapping in config.get("mappings", []):
        if any(f in changed_files for f in mapping.get("match_any", [])):
            matched.update(mapping.get("include_tags", []))

    return always | (fallback if not matched else matched)


def explain_selection(changed_files: List[str], config: dict) -> Dict:
    """Returns a structured explanation of why each tag was selected."""
    default = config.get("default", {})
    always: Set[str] = set(default.get("include_tags", []))
    fallback: Set[str] = set(default.get("fallback_tags", []))

    matched_mappings = []
    for mapping in config.get("mappings", []):
        hit_files = [f for f in mapping.get("match_any", []) if f in changed_files]
        if hit_files:
            matched_mappings.append({
                "id": mapping.get("id", "unknown"),
                "hit_files": hit_files,
                "tags": mapping.get("include_tags", []),
                "rationale": mapping.get("rationale", ""),
            })

    fallback_used = not matched_mappings
    final_tags = always | (fallback if fallback_used else {t for m in matched_mappings for t in m["tags"]})

    return {
        "changed_files": changed_files,
        "always_tags": sorted(always),
        "fallback_used": fallback_used,
        "matched_mappings": matched_mappings,
        "final_tags": sorted(final_tags),
    }


def format_tags(tags: Set[str], fmt: str) -> str:
    sorted_tags = sorted(tags)
    if fmt == "json":
        return json.dumps(sorted_tags)
    if fmt == "lines":
        return "\n".join(sorted_tags)
    if fmt == "playwright":
        return "|".join(t.lstrip("@") for t in sorted_tags)
    if fmt == "pytest":
        return " or ".join(t.lstrip("@") for t in sorted_tags)
    return " or ".join(sorted_tags)
