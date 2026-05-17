"""Tests for the dependency graph: extractor, builder, and resolver.

All tests use tmp_path to create a real (tiny) repo structure — no mocking,
no monkey-patching. This matches how the tool runs in production.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from test_selector.graph.extractor import (
    extract_feature_info,
    extract_pytest_marks,
    extract_python_local_imports,
    extract_step_patterns,
    extract_ts_local_imports,
    extract_ts_tags,
    match_step_to_files,
    step_pattern_to_regex,
)
from test_selector.graph.builder import build
from test_selector.graph.resolver import resolve_tags


# ── Helpers ─────────────────────────────────────────────────────────────────

def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ── extract_python_local_imports ─────────────────────────────────────────────

class TestExtractPythonLocalImports:
    def test_absolute_import_resolved(self, tmp_path):
        (tmp_path / "utils.py").write_text("x = 1")
        caller = write(tmp_path / "app" / "main.py", "import utils\n")
        deps = extract_python_local_imports(caller, tmp_path)
        assert tmp_path / "utils.py" in deps

    def test_from_import_resolved(self, tmp_path):
        (tmp_path / "locators.py").write_text("URL = 'http://x'")
        caller = write(tmp_path / "steps.py", "from locators import URL\n")
        deps = extract_python_local_imports(caller, tmp_path)
        assert tmp_path / "locators.py" in deps

    def test_nested_package_resolved(self, tmp_path):
        pkg = tmp_path / "features" / "locators"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "api_locators.py").write_text("BASE = 'http://x'")
        caller = write(
            tmp_path / "features" / "steps" / "common_steps.py",
            "from features.locators.api_locators import BASE\n",
        )
        deps = extract_python_local_imports(caller, tmp_path)
        assert (pkg / "api_locators.py") in deps

    def test_stdlib_import_not_resolved(self, tmp_path):
        caller = write(tmp_path / "app.py", "import os\nimport json\n")
        assert extract_python_local_imports(caller, tmp_path) == []

    def test_self_import_excluded(self, tmp_path):
        f = write(tmp_path / "mod.py", "from mod import something\n")
        deps = extract_python_local_imports(f, tmp_path)
        assert f not in deps

    def test_syntax_error_returns_empty(self, tmp_path):
        bad = write(tmp_path / "broken.py", "def (:\n")
        assert extract_python_local_imports(bad, tmp_path) == []

    def test_deduplicates_multiple_imports_same_file(self, tmp_path):
        (tmp_path / "shared.py").write_text("A = 1\nB = 2")
        caller = write(tmp_path / "user.py", "from shared import A\nfrom shared import B\n")
        deps = extract_python_local_imports(caller, tmp_path)
        assert deps.count(tmp_path / "shared.py") == 1


# ── extract_step_patterns ────────────────────────────────────────────────────

class TestExtractStepPatterns:
    def test_given_pattern_extracted(self, tmp_path):
        f = write(tmp_path / "addition_steps.py", """\
from behave import given, when, then

@given('the calculator API is running')
def step_impl(context):
    pass
""")
        patterns = extract_step_patterns(f)
        assert ("given", "the calculator API is running") in patterns

    def test_multiple_decorators(self, tmp_path):
        f = write(tmp_path / "steps.py", """\
from behave import given, when, then

@given('user is on login page')
def step_a(context): pass

@when('user enters credentials')
def step_b(context): pass

@then('dashboard is visible')
def step_c(context): pass
""")
        patterns = extract_step_patterns(f)
        keywords = [k for k, _ in patterns]
        assert "given" in keywords
        assert "when" in keywords
        assert "then" in keywords

    def test_parse_style_pattern(self, tmp_path):
        f = write(tmp_path / "steps.py", """\
from behave import when

@when('I POST to "{endpoint}" with {body}')
def step_impl(context, endpoint, body): pass
""")
        patterns = extract_step_patterns(f)
        assert len(patterns) == 1
        assert '{endpoint}' in patterns[0][1]

    def test_non_step_file_returns_empty(self, tmp_path):
        f = write(tmp_path / "utils.py", "def helper(): pass\n")
        assert extract_step_patterns(f) == []


# ── step_pattern_to_regex / match_step_to_files ──────────────────────────────

class TestStepMatching:
    def test_literal_pattern_matches(self):
        rx = step_pattern_to_regex("the calculator API is running")
        assert rx.match("the calculator API is running")

    def test_variable_placeholder_matches_value(self):
        rx = step_pattern_to_regex('I POST to "{endpoint}" with {body}')
        assert rx.match('I POST to "/add" with {"a": 1}')

    def test_wrong_text_does_not_match(self):
        rx = step_pattern_to_regex("the calculator API is running")
        assert not rx.match("the calculator API is stopped")

    def test_case_insensitive(self):
        rx = step_pattern_to_regex("The Calculator API Is Running")
        assert rx.match("the calculator api is running")

    def test_match_step_to_files_finds_correct_file(self, tmp_path):
        addition = write(tmp_path / "addition_steps.py", """\
from behave import given
@given('the calculator API is running')
def step(context): pass
""")
        health = write(tmp_path / "health_steps.py", """\
from behave import then
@then('the health check passes')
def step(context): pass
""")
        all_patterns = {
            addition: extract_step_patterns(addition),
            health: extract_step_patterns(health),
        }
        result = match_step_to_files("the calculator API is running", all_patterns)
        assert addition in result
        assert health not in result


# ── extract_feature_info ─────────────────────────────────────────────────────

class TestExtractFeatureInfo:
    def test_tags_extracted(self, tmp_path):
        f = write(tmp_path / "add.feature", """\
@smoke @critical
Feature: Addition
  @addition
  Scenario: Add two numbers
    Given the calculator API is running
    When I add 2 and 3
    Then the result is 5
""")
        info = extract_feature_info(f)
        assert "@smoke" in info["tags"]
        assert "@critical" in info["tags"]
        assert "@addition" in info["tags"]

    def test_steps_extracted(self, tmp_path):
        f = write(tmp_path / "add.feature", """\
Feature: Addition
  Scenario: Add
    Given the calculator API is running
    When I add 2 and 3
    Then the result is 5
""")
        info = extract_feature_info(f)
        assert "the calculator API is running" in info["steps"]
        assert "I add 2 and 3" in info["steps"]

    def test_no_tags_returns_empty_list(self, tmp_path):
        f = write(tmp_path / "bare.feature", "Feature: No tags\n  Scenario: X\n    Given x\n")
        assert extract_feature_info(f)["tags"] == []


# ── extract_ts_local_imports ─────────────────────────────────────────────────

class TestExtractTsLocalImports:
    def test_relative_import_resolved(self, tmp_path):
        page = write(tmp_path / "framework" / "pages" / "login.page.ts", "export class LoginPage {}")
        spec = write(tmp_path / "tests" / "ui" / "orangehrm.ui.spec.ts",
                     "import { LoginPage } from '../../framework/pages/login.page';\n")
        deps = extract_ts_local_imports(spec, tmp_path)
        assert page in deps

    def test_package_import_ignored(self, tmp_path):
        spec = write(tmp_path / "tests" / "test.spec.ts",
                     "import { test } from '@playwright/test';\n")
        deps = extract_ts_local_imports(spec, tmp_path)
        assert deps == []

    def test_parent_dir_import(self, tmp_path):
        fixture = write(tmp_path / "framework" / "fixtures" / "test-fixtures.ts",
                        "export const test = null;")
        spec = write(tmp_path / "framework" / "fixtures" / "sub" / "other.ts",
                     "import { test } from '../test-fixtures';\n")
        deps = extract_ts_local_imports(spec, tmp_path)
        assert fixture in deps


# ── extract_ts_tags ──────────────────────────────────────────────────────────

class TestExtractTsTags:
    def test_describe_tags_extracted(self, tmp_path):
        f = write(tmp_path / "spec.ts", """\
import { test } from '@playwright/test';
test.describe('OrangeHRM UI @ui @smoke @scenario', () => {
  test('login', async ({ page }) => {});
});
""")
        tags = extract_ts_tags(f)
        assert "@ui" in tags
        assert "@smoke" in tags
        assert "@scenario" in tags

    def test_package_name_not_extracted_as_tag(self, tmp_path):
        f = write(tmp_path / "spec.ts",
                  "import { test } from '@playwright/test';\n")
        tags = extract_ts_tags(f)
        assert "@playwright" not in tags

    def test_multiple_describe_blocks(self, tmp_path):
        f = write(tmp_path / "spec.ts", """\
test.describe('Suite A @api @critical', () => {});
test.describe('Suite B @e2e', () => {});
""")
        tags = extract_ts_tags(f)
        assert "@api" in tags
        assert "@critical" in tags
        assert "@e2e" in tags


# ── build() + resolve_tags() — integration ───────────────────────────────────

class TestGraphIntegration:
    def _make_repo(self, tmp_path: Path) -> Path:
        """Build a small but realistic repo structure."""
        # Python: locators → common_steps → addition_steps
        write(tmp_path / "features" / "locators" / "__init__.py", "")
        write(tmp_path / "features" / "locators" / "api_locators.py",
              "BASE_URL = 'http://localhost:8000'\n")

        write(tmp_path / "features" / "steps" / "common_steps.py", """\
from behave import given
from features.locators.api_locators import BASE_URL

@given('the calculator API is running')
def step(context):
    context.base_url = BASE_URL
""")
        write(tmp_path / "features" / "steps" / "addition_steps.py", """\
from behave import when, then
from features.steps.common_steps import step

@when('I add {a:d} and {b:d}')
def step_add(context, a, b):
    context.result = a + b

@then('the result is {expected:d}')
def step_result(context, expected):
    assert context.result == expected
""")

        # Feature files
        write(tmp_path / "features" / "addition.feature", """\
@smoke @critical
Feature: Addition
  @addition
  Scenario: Add two numbers
    Given the calculator API is running
    When I add 2 and 3
    Then the result is 5
""")
        write(tmp_path / "features" / "health.feature", """\
@smoke @health
Feature: Health
  Scenario: Health check
    Given the calculator API is running
""")

        # TypeScript: client → fixture → spec
        write(tmp_path / "framework" / "api" / "reqres.client.ts",
              "export class ReqResClient { listUsers() {} }\n")
        write(tmp_path / "framework" / "fixtures" / "test-fixtures.ts", """\
import { ReqResClient } from '../api/reqres.client';
export const test = null;
""")
        write(tmp_path / "tests" / "api" / "reqres.api.spec.ts", """\
import { test } from '../../framework/fixtures/test-fixtures';
test.describe('ReqRes API @api @critical', () => {});
""")
        write(tmp_path / "framework" / "pages" / "login.page.ts",
              "export class LoginPage { goto() {} }\n")
        write(tmp_path / "tests" / "ui" / "orangehrm.ui.spec.ts", """\
import { LoginPage } from '../../framework/pages/login.page';
test.describe('OrangeHRM UI @ui @smoke', () => {});
""")
        return tmp_path

    def test_changing_ts_client_affects_api_spec(self, tmp_path):
        repo = self._make_repo(tmp_path)
        g = build(repo)
        tags = resolve_tags(["framework/api/reqres.client.ts"], g)
        assert "@api" in tags
        assert "@critical" in tags

    def test_changing_page_object_affects_ui_spec(self, tmp_path):
        repo = self._make_repo(tmp_path)
        g = build(repo)
        tags = resolve_tags(["framework/pages/login.page.ts"], g)
        assert "@ui" in tags
        assert "@smoke" in tags

    def test_changing_ts_client_does_not_affect_ui_spec(self, tmp_path):
        repo = self._make_repo(tmp_path)
        g = build(repo)
        tags = resolve_tags(["framework/api/reqres.client.ts"], g)
        assert "@ui" not in tags

    def test_changing_locators_affects_both_features_via_common_steps(self, tmp_path):
        repo = self._make_repo(tmp_path)
        g = build(repo)
        # api_locators → common_steps → addition.feature AND health.feature
        tags = resolve_tags(["features/locators/api_locators.py"], g)
        assert "@addition" in tags
        assert "@health" in tags

    def test_changing_addition_steps_affects_only_addition_feature(self, tmp_path):
        repo = self._make_repo(tmp_path)
        g = build(repo)
        tags = resolve_tags(["features/steps/addition_steps.py"], g)
        assert "@addition" in tags
        # health.feature uses "Given the calculator API is running" which is in
        # common_steps, not addition_steps — health should NOT be selected here.
        assert "@health" not in tags

    def test_unrelated_file_returns_no_tags(self, tmp_path):
        repo = self._make_repo(tmp_path)
        write(tmp_path / "README.md", "# docs\n")
        g = build(repo)
        tags = resolve_tags(["README.md"], g)
        assert tags == set()

    def test_graph_has_nodes_and_edges(self, tmp_path):
        repo = self._make_repo(tmp_path)
        g = build(repo)
        assert g.node_count() > 0
        assert g.edge_count() > 0

    def test_fixture_change_propagates_to_spec(self, tmp_path):
        repo = self._make_repo(tmp_path)
        g = build(repo)
        # test-fixtures.ts imports reqres.client.ts and is imported by reqres.api.spec.ts
        tags = resolve_tags(["framework/fixtures/test-fixtures.ts"], g)
        assert "@api" in tags

    # ── Convention-based broadcaster tests ───────────────────────────────────

    def test_environment_py_change_affects_all_feature_files(self, tmp_path):
        repo = self._make_repo(tmp_path)
        # Add environment.py — behave auto-discovers it; not imported by features.
        write(tmp_path / "features" / "environment.py",
              "def before_all(context): pass\n")
        g = build(repo)
        tags = resolve_tags(["features/environment.py"], g)
        # Should affect both feature files even though nothing imports environment.py
        assert "@addition" in tags
        assert "@health" in tags

    def test_environment_py_does_not_affect_ts_specs(self, tmp_path):
        repo = self._make_repo(tmp_path)
        write(tmp_path / "features" / "environment.py",
              "def before_all(context): pass\n")
        g = build(repo)
        tags = resolve_tags(["features/environment.py"], g)
        # Behave lifecycle file → behave features only, not Playwright specs
        assert "@ui" not in tags
        assert "@api" not in tags

    def test_playwright_config_change_affects_all_specs(self, tmp_path):
        repo = self._make_repo(tmp_path)
        write(tmp_path / "playwright.config.ts",
              "export default { testDir: './tests' };\n")
        g = build(repo)
        tags = resolve_tags(["playwright.config.ts"], g)
        assert "@api" in tags
        assert "@ui" in tags

    def test_playwright_config_does_not_affect_behave_features(self, tmp_path):
        repo = self._make_repo(tmp_path)
        write(tmp_path / "playwright.config.ts",
              "export default { testDir: './tests' };\n")
        g = build(repo)
        tags = resolve_tags(["playwright.config.ts"], g)
        assert "@addition" not in tags
        assert "@health" not in tags

    def test_behave_ini_change_affects_all_feature_files(self, tmp_path):
        repo = self._make_repo(tmp_path)
        write(tmp_path / "behave.ini", "[behave]\nstdout_capture=false\n")
        g = build(repo)
        tags = resolve_tags(["behave.ini"], g)
        assert "@addition" in tags
        assert "@health" in tags

    def test_conftest_change_affects_all_tests(self, tmp_path):
        repo = self._make_repo(tmp_path)
        write(tmp_path / "conftest.py", "import pytest\n")
        g = build(repo)
        tags = resolve_tags(["conftest.py"], g)
        # conftest.py scope is "all" — affects both feature and spec tests
        assert "@addition" in tags
        assert "@api" in tags


# ── extract_pytest_marks ─────────────────────────────────────────────────────

class TestExtractPytestMarks:
    def test_single_mark_extracted(self, tmp_path):
        f = write(tmp_path / "test_calc.py", """\
import pytest

@pytest.mark.smoke
def test_add():
    assert 1 + 1 == 2
""")
        marks = extract_pytest_marks(f)
        assert "@smoke" in marks

    def test_multiple_marks_on_one_function(self, tmp_path):
        f = write(tmp_path / "test_calc.py", """\
import pytest

@pytest.mark.smoke
@pytest.mark.critical
def test_add():
    pass
""")
        marks = extract_pytest_marks(f)
        assert "@smoke" in marks
        assert "@critical" in marks

    def test_marks_on_class_and_methods(self, tmp_path):
        f = write(tmp_path / "test_suite.py", """\
import pytest

@pytest.mark.integration
class TestSuite:
    @pytest.mark.slow
    def test_something(self):
        pass
""")
        marks = extract_pytest_marks(f)
        assert "@integration" in marks
        assert "@slow" in marks

    def test_parametrize_decorator_ignored(self, tmp_path):
        f = write(tmp_path / "test_calc.py", """\
import pytest

@pytest.mark.parametrize("x,y", [(1, 2), (3, 4)])
def test_add(x, y):
    pass
""")
        marks = extract_pytest_marks(f)
        assert "@parametrize" not in marks

    def test_non_test_functions_ignored(self, tmp_path):
        f = write(tmp_path / "test_calc.py", """\
import pytest

@pytest.mark.smoke
def helper():
    pass

def test_real():
    pass
""")
        marks = extract_pytest_marks(f)
        assert "@smoke" not in marks

    def test_mark_with_args_extracted(self, tmp_path):
        f = write(tmp_path / "test_calc.py", """\
import pytest

@pytest.mark.smoke(reason="fast path")
def test_add():
    pass
""")
        marks = extract_pytest_marks(f)
        assert "@smoke" in marks

    def test_non_test_file_returns_empty(self, tmp_path):
        f = write(tmp_path / "utils.py", """\
import pytest

@pytest.mark.smoke
def helper():
    pass
""")
        marks = extract_pytest_marks(f)
        assert marks == []

    def test_syntax_error_returns_empty(self, tmp_path):
        f = write(tmp_path / "test_broken.py", "def (:\n")
        assert extract_pytest_marks(f) == []


# ── pytest test file integration ──────────────────────────────────────────────

class TestPytestIntegration:
    def _make_pytest_repo(self, tmp_path: Path) -> Path:
        write(tmp_path / "src" / "calculator.py", "def add(a, b): return a + b\n")
        write(tmp_path / "src" / "validator.py", "def validate(x): return x > 0\n")
        write(tmp_path / "tests" / "test_calculator.py", """\
import pytest
from src.calculator import add

@pytest.mark.smoke
@pytest.mark.unit
def test_add():
    assert add(1, 2) == 3

@pytest.mark.regression
def test_add_negative():
    assert add(-1, -2) == -3
""")
        write(tmp_path / "tests" / "test_validator.py", """\
import pytest
from src.validator import validate

@pytest.mark.smoke
def test_validate_positive():
    assert validate(5)
""")
        return tmp_path

    def test_pytest_marks_collected_from_test_files(self, tmp_path):
        repo = self._make_pytest_repo(tmp_path)
        g = build(repo)
        assert "@smoke" in g.tag_map.get("tests/test_calculator.py", [])
        assert "@unit" in g.tag_map.get("tests/test_calculator.py", [])
        assert "@regression" in g.tag_map.get("tests/test_calculator.py", [])

    def test_changing_source_affects_importing_test(self, tmp_path):
        repo = self._make_pytest_repo(tmp_path)
        g = build(repo)
        tags = resolve_tags(["src/calculator.py"], g)
        assert "@smoke" in tags
        assert "@unit" in tags
        assert "@regression" in tags

    def test_changing_unrelated_source_does_not_affect_test(self, tmp_path):
        repo = self._make_pytest_repo(tmp_path)
        g = build(repo)
        # validator.py is not imported by test_calculator.py
        tags = resolve_tags(["src/validator.py"], g)
        assert "@unit" not in tags
        assert "@regression" not in tags

    def test_conftest_change_affects_pytest_tests(self, tmp_path):
        repo = self._make_pytest_repo(tmp_path)
        write(tmp_path / "conftest.py", "import pytest\n")
        g = build(repo)
        tags = resolve_tags(["conftest.py"], g)
        assert "@smoke" in tags
        assert "@unit" in tags

    def test_pytest_ini_change_affects_pytest_tests(self, tmp_path):
        repo = self._make_pytest_repo(tmp_path)
        write(tmp_path / "pytest.ini", "[pytest]\ntestpaths = tests\n")
        g = build(repo)
        tags = resolve_tags(["pytest.ini"], g)
        assert "@smoke" in tags


# ── GraphSpec protocol ────────────────────────────────────────────────────────

class TestGraphProtocol:
    def _make_spec(self):
        from test_selector.graph.protocol import GraphEdge, GraphNode, GraphSpec
        return GraphSpec(
            nodes=[
                GraphNode(id="src/calc.py", type="source", tags=[]),
                GraphNode(id="tests/calc_test.py", type="test", tags=["@smoke", "@unit"]),
            ],
            edges=[GraphEdge(from_="src/calc.py", to="tests/calc_test.py", kind="imports")],
        )

    def test_to_dict_has_required_keys(self):
        spec = self._make_spec()
        d = spec.to_dict()
        assert "version" in d
        assert "nodes" in d
        assert "edges" in d

    def test_round_trip_dict(self):
        from test_selector.graph.protocol import GraphSpec
        spec = self._make_spec()
        restored = GraphSpec.from_dict(spec.to_dict())
        assert len(restored.nodes) == 2
        assert len(restored.edges) == 1
        assert restored.nodes[0].id == "src/calc.py"

    def test_round_trip_json(self):
        from test_selector.graph.protocol import GraphSpec
        spec = self._make_spec()
        restored = GraphSpec.from_json(spec.to_json())
        assert restored.edges[0].from_ == "src/calc.py"
        assert restored.edges[0].to == "tests/calc_test.py"

    def test_node_tags_preserved(self):
        from test_selector.graph.protocol import GraphSpec
        spec = self._make_spec()
        restored = GraphSpec.from_dict(spec.to_dict())
        test_node = next(n for n in restored.nodes if n.type == "test")
        assert "@smoke" in test_node.tags

    def test_dependency_graph_to_spec_round_trip(self, tmp_path):
        from test_selector.graph.builder import DependencyGraph
        g = DependencyGraph()
        g.add_dependency("src/a.py", "tests/a_test.py")
        g.record_tags("tests/a_test.py", ["@smoke"])

        spec = g.to_spec()
        g2 = DependencyGraph.from_spec(spec)

        tags = resolve_tags(["src/a.py"], g2)
        assert "@smoke" in tags

    def test_external_graph_json_works_with_resolver(self):
        """Simulate a Java extractor outputting JSON that the Python selector reads."""
        from test_selector.graph.builder import DependencyGraph
        from test_selector.graph.protocol import GraphSpec

        java_extractor_output = """{
            "version": "1.0",
            "nodes": [
                {"id": "src/main/java/Calculator.java", "type": "source", "tags": []},
                {"id": "src/test/java/CalculatorTest.java", "type": "test",
                 "tags": ["@smoke", "@unit"], "metadata": {"framework": "junit"}}
            ],
            "edges": [
                {"from": "src/main/java/Calculator.java",
                 "to": "src/test/java/CalculatorTest.java",
                 "kind": "imports"}
            ]
        }"""

        spec = GraphSpec.from_json(java_extractor_output)
        graph = DependencyGraph.from_spec(spec)
        tags = resolve_tags(["src/main/java/Calculator.java"], graph)
        assert "@smoke" in tags
        assert "@unit" in tags
