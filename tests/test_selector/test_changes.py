"""Tests for the change classification and cosmetic-filtering layer."""
from test_selector.changes import (
    ChangeKind,
    FileChange,
    filter_impactful,
    is_trivial_diff,
    parse_name_status,
)


# ---------------------------------------------------------------------------
# parse_name_status
# ---------------------------------------------------------------------------

class TestParseNameStatus:
    def test_modify(self):
        changes = parse_name_status("M\tapp/main.py")
        assert len(changes) == 1
        assert changes[0].kind == ChangeKind.MODIFY
        assert changes[0].path == "app/main.py"

    def test_add(self):
        changes = parse_name_status("A\tfeatures/new.feature")
        assert changes[0].kind == ChangeKind.ADD

    def test_delete(self):
        changes = parse_name_status("D\tfeatures/old.feature")
        assert changes[0].kind == ChangeKind.DELETE

    def test_rename_only_r100(self):
        changes = parse_name_status("R100\tfeatures/add.feature\tfeatures/addition.feature")
        assert changes[0].kind == ChangeKind.RENAME_ONLY
        assert changes[0].path == "features/addition.feature"
        assert changes[0].old_path == "features/add.feature"
        assert changes[0].is_cosmetic is True

    def test_rename_with_content_change(self):
        changes = parse_name_status("R85\tfeatures/add.feature\tfeatures/addition.feature")
        assert changes[0].kind == ChangeKind.RENAME_MODIFY
        assert changes[0].is_cosmetic is False

    def test_mixed_batch(self):
        output = "M\tapp/main.py\nA\tfeatures/new.feature\nR100\told.py\tnew.py\nD\tobsolete.py"
        changes = parse_name_status(output)
        assert len(changes) == 4
        kinds = [c.kind for c in changes]
        assert ChangeKind.MODIFY in kinds
        assert ChangeKind.ADD in kinds
        assert ChangeKind.RENAME_ONLY in kinds
        assert ChangeKind.DELETE in kinds

    def test_empty_output(self):
        assert parse_name_status("") == []

    def test_blank_lines_ignored(self):
        assert parse_name_status("\n\n") == []


# ---------------------------------------------------------------------------
# is_trivial_diff — Python files
# ---------------------------------------------------------------------------

class TestIsTrivialDiffPython:
    def _diff(self, *added_lines: str) -> str:
        body = "\n".join(f"+{l}" for l in added_lines)
        return f"--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n{body}"

    def test_blank_line_added(self):
        assert is_trivial_diff(self._diff(""), "file.py") is True

    def test_comment_added(self):
        assert is_trivial_diff(self._diff("# this is a comment"), "file.py") is True

    def test_import_added(self):
        assert is_trivial_diff(self._diff("import os"), "file.py") is True

    def test_from_import_added(self):
        assert is_trivial_diff(self._diff("from pathlib import Path"), "file.py") is True

    def test_logic_change_not_trivial(self):
        assert is_trivial_diff(self._diff("result = a + b"), "file.py") is False

    def test_mixed_comment_and_logic_not_trivial(self):
        diff = self._diff("# new comment", "result = a * b")
        assert is_trivial_diff(diff, "file.py") is False

    def test_empty_diff_is_trivial(self):
        assert is_trivial_diff("", "file.py") is True

    def test_only_context_lines_trivial(self):
        diff = "--- a/f.py\n+++ b/f.py\n @@ -1 +1 @@\n existing line"
        assert is_trivial_diff(diff, "file.py") is True


# ---------------------------------------------------------------------------
# is_trivial_diff — TypeScript / feature files
# ---------------------------------------------------------------------------

class TestIsTrivialDiffOtherExtensions:
    def test_ts_comment_trivial(self):
        diff = "--- a/f.ts\n+++ b/f.ts\n@@ -1 +1 @@\n+// comment\n"
        assert is_trivial_diff(diff, "file.ts") is True

    def test_ts_import_trivial(self):
        diff = "--- a/f.ts\n+++ b/f.ts\n@@ -1 +1 @@\n+import { foo } from './foo';\n"
        assert is_trivial_diff(diff, "file.ts") is True

    def test_ts_logic_not_trivial(self):
        diff = "--- a/f.ts\n+++ b/f.ts\n@@ -1 +1 @@\n+const x = 1;\n"
        assert is_trivial_diff(diff, "file.ts") is False

    def test_feature_file_never_trivial(self):
        # Any change to Gherkin is meaningful — even a comment
        diff = "--- a/f.feature\n+++ b/f.feature\n@@ -1 +1 @@\n+# comment\n"
        assert is_trivial_diff(diff, "file.feature") is False

    def test_yaml_file_never_trivial(self):
        diff = "--- a/f.yaml\n+++ b/f.yaml\n@@ -1 +1 @@\n+# comment\n"
        assert is_trivial_diff(diff, "config.yaml") is False

    def test_unknown_extension_not_trivial(self):
        diff = "--- a/f.toml\n+++ b/f.toml\n@@ -1 +1 @@\n+# comment\n"
        assert is_trivial_diff(diff, "file.toml") is False


# ---------------------------------------------------------------------------
# filter_impactful
# ---------------------------------------------------------------------------

class TestFilterImpactful:
    def test_rename_only_is_skipped(self):
        changes = [FileChange(path="new.py", kind=ChangeKind.RENAME_ONLY, old_path="old.py")]
        paths, skipped = filter_impactful(changes)
        assert paths == []
        assert len(skipped) == 1

    def test_delete_is_impactful(self):
        changes = [FileChange(path="gone.py", kind=ChangeKind.DELETE)]
        paths, skipped = filter_impactful(changes)
        assert "gone.py" in paths
        assert skipped == []

    def test_add_is_impactful(self):
        changes = [FileChange(path="new.feature", kind=ChangeKind.ADD)]
        paths, skipped = filter_impactful(changes)
        assert "new.feature" in paths

    def test_modify_with_trivial_diff_is_skipped(self):
        changes = [FileChange(path="app/main.py", kind=ChangeKind.MODIFY)]
        trivial_diff = "--- a/app/main.py\n+++ b/app/main.py\n@@ -1 +1 @@\n+# new comment\n"
        paths, skipped = filter_impactful(changes, diff_getter=lambda _: trivial_diff)
        assert paths == []
        assert len(skipped) == 1

    def test_modify_with_logic_change_is_impactful(self):
        changes = [FileChange(path="app/main.py", kind=ChangeKind.MODIFY)]
        logic_diff = "--- a/app/main.py\n+++ b/app/main.py\n@@ -10 +10 @@\n+    return a / b\n"
        paths, skipped = filter_impactful(changes, diff_getter=lambda _: logic_diff)
        assert "app/main.py" in paths
        assert skipped == []

    def test_no_diff_getter_treats_modify_as_impactful(self):
        # Without diff_getter we can't know, so we assume impactful (safe default).
        changes = [FileChange(path="app/main.py", kind=ChangeKind.MODIFY)]
        paths, skipped = filter_impactful(changes, diff_getter=None)
        assert "app/main.py" in paths

    def test_mixed_batch(self):
        changes = [
            FileChange(path="new.py", kind=ChangeKind.RENAME_ONLY, old_path="old.py"),
            FileChange(path="app/main.py", kind=ChangeKind.MODIFY),
            FileChange(path="gone.feature", kind=ChangeKind.DELETE),
        ]
        trivial_diff = "+# comment\n"
        paths, skipped = filter_impactful(changes, diff_getter=lambda _: trivial_diff)
        # RENAME_ONLY skipped + MODIFY with trivial diff skipped; DELETE impactful
        assert "gone.feature" in paths
        assert "app/main.py" not in paths
        assert len(skipped) == 2
