import re
from typing import Any, Dict, Iterable, List, Optional


DIFF_INDEX_SCHEMA_VERSION = "diff-index/v1"

_HUNK_RE = re.compile(r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? \+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@")


def normalize_diff_path(path: Any) -> str:
    value = str(path or "").strip()
    if not value or value == "/dev/null":
        return ""
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1]
    if value.startswith("a/") or value.startswith("b/"):
        value = value[2:]
    return value


def _new_file(path: str, old_path: str = "", new_path: str = "") -> Dict[str, Any]:
    return {
        "path": path,
        "old_path": old_path,
        "new_path": new_path or path,
        "hunks": [],
        "new_changed_lines": [],
        "old_changed_lines": [],
    }


def _ensure_file(index: Dict[str, Any], path: str, old_path: str = "", new_path: str = "") -> Optional[Dict[str, Any]]:
    normalized_path = normalize_diff_path(path or new_path or old_path)
    if not normalized_path:
        return None
    files = index["files"]
    if normalized_path not in files:
        files[normalized_path] = _new_file(normalized_path, normalize_diff_path(old_path), normalize_diff_path(new_path))
    entry = files[normalized_path]
    for alias in {normalized_path, normalize_diff_path(old_path), normalize_diff_path(new_path)}:
        if alias:
            index["aliases"][alias] = normalized_path
    return entry


def _parse_diff_git_paths(line: str) -> Dict[str, str]:
    parts = line.split()
    if len(parts) >= 4:
        old_path = normalize_diff_path(parts[2])
        new_path = normalize_diff_path(parts[3])
        return {"old_path": old_path, "new_path": new_path, "path": new_path or old_path}
    return {"old_path": "", "new_path": "", "path": ""}


def _sorted_unique(values: Iterable[int]) -> List[int]:
    return sorted({value for value in values if value > 0})


def build_diff_index(diff_text: str, skipped_files: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Build a selected-diff line index for FINDING-GROUNDING-P0.

    The index records changed new-side and old-side line numbers from the selected
    diff only. It is intentionally independent from GitHub inline-comment APIs.
    """
    index: Dict[str, Any] = {
        "schema_version": DIFF_INDEX_SCHEMA_VERSION,
        "files": {},
        "aliases": {},
        "skipped_files": skipped_files or [],
        "skipped_file_paths": sorted(
            {
                normalize_diff_path(item.get("path"))
                for item in (skipped_files or [])
                if isinstance(item, dict) and normalize_diff_path(item.get("path"))
            }
        ),
    }
    current: Optional[Dict[str, Any]] = None
    current_old_path = ""
    current_new_path = ""
    old_line = 0
    new_line = 0
    active_hunk: Optional[Dict[str, Any]] = None

    for raw_line in (diff_text or "").splitlines():
        if raw_line.startswith("diff --git "):
            paths = _parse_diff_git_paths(raw_line)
            current_old_path = paths["old_path"]
            current_new_path = paths["new_path"]
            current = _ensure_file(index, paths["path"], current_old_path, current_new_path)
            active_hunk = None
            continue

        if raw_line.startswith("--- "):
            current_old_path = normalize_diff_path(raw_line[4:])
            continue

        if raw_line.startswith("+++ "):
            current_new_path = normalize_diff_path(raw_line[4:])
            path = current_new_path or current_old_path
            current = _ensure_file(index, path, current_old_path, current_new_path)
            active_hunk = None
            continue

        match = _HUNK_RE.match(raw_line)
        if match and current is not None:
            old_line = int(match.group("old_start"))
            new_line = int(match.group("new_start"))
            active_hunk = {
                "header": raw_line,
                "old_start": old_line,
                "new_start": new_line,
                "old_changed_lines": [],
                "new_changed_lines": [],
            }
            current["hunks"].append(active_hunk)
            continue

        if current is None or active_hunk is None:
            continue

        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            current["new_changed_lines"].append(new_line)
            active_hunk["new_changed_lines"].append(new_line)
            new_line += 1
            continue

        if raw_line.startswith("-") and not raw_line.startswith("---"):
            current["old_changed_lines"].append(old_line)
            active_hunk["old_changed_lines"].append(old_line)
            old_line += 1
            continue

        if raw_line.startswith(" "):
            old_line += 1
            new_line += 1

    for entry in index["files"].values():
        entry["new_changed_lines"] = _sorted_unique(entry.get("new_changed_lines", []))
        entry["old_changed_lines"] = _sorted_unique(entry.get("old_changed_lines", []))
        for hunk in entry.get("hunks", []):
            hunk["new_changed_lines"] = _sorted_unique(hunk.get("new_changed_lines", []))
            hunk["old_changed_lines"] = _sorted_unique(hunk.get("old_changed_lines", []))

    index["file_count"] = len(index["files"])
    index["new_changed_line_count"] = sum(len(entry["new_changed_lines"]) for entry in index["files"].values())
    index["old_changed_line_count"] = sum(len(entry["old_changed_lines"]) for entry in index["files"].values())
    return index
