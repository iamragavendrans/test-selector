from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, List, Optional, Tuple


class ChangeKind(Enum):
    ADD = "A"            # new file — always impactful
    MODIFY = "M"         # content changed — check for trivial
    DELETE = "D"         # file removed — always impactful (may break tests)
    RENAME_ONLY = "R100" # pure rename, zero content change — cosmetic
    RENAME_MODIFY = "R"  # renamed AND content changed — check for trivial


@dataclass
class FileChange:
    path: str                    # current (new) path
    kind: ChangeKind
    old_path: Optional[str] = None   # only set for renames

    @property
    def is_cosmetic(self) -> bool:
        return self.kind == ChangeKind.RENAME_ONLY


def parse_name_status(output: str) -> List[FileChange]:
    """Parse `git diff --name-status` output into FileChange objects.

    Handles: M (modify), A (add), D (delete), Rxx (rename with similarity score).
    R100 = pure rename (no content change). R85 = renamed + 15% content changed.
    """
    changes: List[FileChange] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]

        if status == "M":
            changes.append(FileChange(path=parts[1], kind=ChangeKind.MODIFY))
        elif status == "A":
            changes.append(FileChange(path=parts[1], kind=ChangeKind.ADD))
        elif status == "D":
            changes.append(FileChange(path=parts[1], kind=ChangeKind.DELETE))
        elif status.startswith("R"):
            similarity = int(status[1:]) if len(status) > 1 else 0
            old_path, new_path = parts[1], parts[2]
            kind = ChangeKind.RENAME_ONLY if similarity == 100 else ChangeKind.RENAME_MODIFY
            changes.append(FileChange(path=new_path, kind=kind, old_path=old_path))

    return changes


# Lines that are never logically significant, keyed by file extension.
# Empty tuple = no lines are trivial (every change in this type is meaningful).
_TRIVIAL_PREFIXES: dict[str, tuple[str, ...]] = {
    ".py":      ("#", "import ", "from "),
    ".ts":      ("//", "import "),
    ".js":      ("//", "import ", "require("),
    ".feature": (),   # any Gherkin change is meaningful
    ".yaml":    (),
    ".yml":     (),
}


def _is_trivial_line(line: str, ext: str) -> bool:
    stripped = line.strip()
    if not stripped:                             # blank line
        return True
    prefixes = _TRIVIAL_PREFIXES.get(ext.lower(), ())
    return bool(prefixes) and any(stripped.startswith(p) for p in prefixes)


def is_trivial_diff(diff_content: str, file_path: str) -> bool:
    """Return True if the unified diff only touches blank lines, comments, or imports.

    Changed lines are the `+` / `-` rows in the diff (excluding the `+++`/`---` headers).
    If every changed line is trivial for this file type, the whole change is cosmetic.
    """
    ext = Path(file_path).suffix
    changed_lines = [
        line[1:]
        for line in diff_content.splitlines()
        if (line.startswith("+") or line.startswith("-"))
        and not line.startswith("+++")
        and not line.startswith("---")
    ]
    if not changed_lines:
        return True   # only whitespace/context, no actual diff lines
    return all(_is_trivial_line(l, ext) for l in changed_lines)


def filter_impactful(
    changes: List[FileChange],
    diff_getter: Optional[Callable[[str], str]] = None,
) -> Tuple[List[str], List[FileChange]]:
    """Split changes into impactful paths and skipped (cosmetic) changes.

    Args:
        changes:     Parsed FileChange objects from git diff --name-status.
        diff_getter: Optional callable(path) → unified diff string.
                     When provided, MODIFY/RENAME_MODIFY files are checked for
                     trivial content (blanks, comments, imports only).

    Returns:
        (impactful_paths, skipped_changes)
        impactful_paths — pass directly to select_tags().
        skipped_changes — for --explain output; these triggered no test selection.
    """
    impactful: List[str] = []
    skipped: List[FileChange] = []

    for change in changes:
        # Pure renames carry no logic change — skip regardless.
        if change.kind == ChangeKind.RENAME_ONLY:
            skipped.append(change)
            continue

        # For content-bearing changes, optionally inspect the diff.
        if change.kind in (ChangeKind.MODIFY, ChangeKind.RENAME_MODIFY) and diff_getter:
            diff = diff_getter(change.old_path or change.path)
            if is_trivial_diff(diff, change.path):
                skipped.append(change)
                continue

        impactful.append(change.path)

    return impactful, skipped
