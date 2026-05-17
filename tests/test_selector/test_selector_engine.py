"""Tests for the test_selector engine — selection logic, explain, and format."""
import json
from pathlib import Path

import pytest

from test_selector.selector import (
    explain_selection,
    format_tags,
    load_config,
    select_tags,
)

# ---------------------------------------------------------------------------
# Minimal fixture config that mirrors the real YAML structure
# ---------------------------------------------------------------------------

CONFIG = {
    "default": {
        "include_tags": ["@smoke", "@critical"],
        "fallback_tags": ["@happy_path"],
    },
    "mappings": [
        {
            "id": "calc_add",
            "match_any": ["app/main.py", "features/addition.feature", "features/steps/addition_steps.py"],
            "include_tags": ["@smoke", "@critical", "@addition"],
            "rationale": "Addition related code changed.",
        },
        {
            "id": "calc_subtract",
            "match_any": ["app/main.py", "features/subtraction.feature", "features/steps/subtraction_steps.py"],
            "include_tags": ["@smoke", "@critical", "@subtraction"],
            "rationale": "Subtraction related code changed.",
        },
        {
            "id": "health",
            "match_any": ["features/health.feature", "features/steps/health_steps.py"],
            "include_tags": ["@smoke", "@critical", "@health"],
            "rationale": "Health checks changed.",
        },
    ],
}


# ---------------------------------------------------------------------------
# select_tags
# ---------------------------------------------------------------------------

class TestSelectTags:
    def test_no_changes_returns_always_plus_fallback(self):
        tags = select_tags([], CONFIG)
        assert "@smoke" in tags
        assert "@critical" in tags
        assert "@happy_path" in tags

    def test_no_changes_does_not_return_mapping_tags(self):
        tags = select_tags([], CONFIG)
        assert "@addition" not in tags
        assert "@subtraction" not in tags

    def test_unknown_file_falls_back(self):
        tags = select_tags(["src/some_unrelated_file.py"], CONFIG)
        assert "@happy_path" in tags
        assert "@addition" not in tags

    def test_matching_file_returns_its_tags(self):
        tags = select_tags(["features/addition.feature"], CONFIG)
        assert "@addition" in tags

    def test_matching_file_always_includes_always_tags(self):
        tags = select_tags(["features/addition.feature"], CONFIG)
        assert "@smoke" in tags
        assert "@critical" in tags

    def test_matching_file_suppresses_fallback(self):
        tags = select_tags(["features/addition.feature"], CONFIG)
        assert "@happy_path" not in tags

    def test_shared_file_hits_multiple_mappings(self):
        # app/main.py is in both calc_add and calc_subtract match_any
        tags = select_tags(["app/main.py"], CONFIG)
        assert "@addition" in tags
        assert "@subtraction" in tags

    def test_two_distinct_files_union_of_tags(self):
        tags = select_tags(["features/addition.feature", "features/health.feature"], CONFIG)
        assert "@addition" in tags
        assert "@health" in tags

    def test_empty_config_returns_empty_set(self):
        tags = select_tags([], {"default": {}, "mappings": []})
        assert tags == set()


# ---------------------------------------------------------------------------
# format_tags
# ---------------------------------------------------------------------------

class TestFormatTags:
    TAGS = {"@smoke", "@critical", "@addition"}

    def test_expr_sorted_or_joined(self):
        result = format_tags(self.TAGS, "expr")
        assert result == "@addition or @critical or @smoke"

    def test_playwright_strips_at_and_pipe_joins(self):
        result = format_tags(self.TAGS, "playwright")
        assert result == "addition|critical|smoke"

    def test_pytest_strips_at_and_or_joins(self):
        result = format_tags(self.TAGS, "pytest")
        assert result == "addition or critical or smoke"

    def test_json_is_valid_sorted_list(self):
        result = format_tags(self.TAGS, "json")
        parsed = json.loads(result)
        assert parsed == ["@addition", "@critical", "@smoke"]

    def test_lines_one_per_line_sorted(self):
        result = format_tags(self.TAGS, "lines")
        assert result == "@addition\n@critical\n@smoke"

    def test_empty_set_returns_empty_string(self):
        assert format_tags(set(), "expr") == ""
        assert format_tags(set(), "playwright") == ""


# ---------------------------------------------------------------------------
# explain_selection
# ---------------------------------------------------------------------------

class TestExplainSelection:
    def test_structure_keys_present(self):
        exp = explain_selection([], CONFIG)
        assert "changed_files" in exp
        assert "always_tags" in exp
        assert "fallback_used" in exp
        assert "matched_mappings" in exp
        assert "final_tags" in exp

    def test_no_changes_fallback_used_true(self):
        exp = explain_selection([], CONFIG)
        assert exp["fallback_used"] is True
        assert "@happy_path" in exp["final_tags"]

    def test_matching_file_fallback_used_false(self):
        exp = explain_selection(["features/addition.feature"], CONFIG)
        assert exp["fallback_used"] is False

    def test_matched_mappings_contains_correct_id(self):
        exp = explain_selection(["features/addition.feature"], CONFIG)
        ids = [m["id"] for m in exp["matched_mappings"]]
        assert "calc_add" in ids

    def test_matched_mapping_hit_files_correct(self):
        exp = explain_selection(["features/addition.feature"], CONFIG)
        m = next(m for m in exp["matched_mappings"] if m["id"] == "calc_add")
        assert "features/addition.feature" in m["hit_files"]

    def test_always_tags_always_in_final(self):
        for files in [[], ["features/addition.feature"], ["unknown.py"]]:
            exp = explain_selection(files, CONFIG)
            assert "@smoke" in exp["final_tags"]
            assert "@critical" in exp["final_tags"]

    def test_changed_files_recorded(self):
        files = ["features/addition.feature"]
        exp = explain_selection(files, CONFIG)
        assert exp["changed_files"] == files


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_loads_valid_yaml(self, tmp_path: Path):
        cfg = tmp_path / "map.yaml"
        cfg.write_text(
            "default:\n  include_tags: ['@smoke']\n  fallback_tags: ['@happy_path']\nmappings: []\n"
        )
        result = load_config(cfg)
        assert result["default"]["include_tags"] == ["@smoke"]
        assert result["mappings"] == []

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.yaml")

    def test_loads_real_config(self):
        real_config = Path("config/test_selection_map.yaml")
        if not real_config.exists():
            pytest.skip("real config not present")
        cfg = load_config(real_config)
        assert "default" in cfg
        assert "mappings" in cfg
        assert isinstance(cfg["mappings"], list)
