import fnmatch
import re
from typing import Any, Dict, List, Tuple

from .config import split_csv


SCOPE_SCHEMA_VERSION = "review-scope/v1"
SUPPORTED_SCOPE_MODES = {"full", "files"}
SAFE_SCOPE_PATTERN_RE = re.compile(r"^[A-Za-z0-9._/@:+*?\[\]-]+$")


def normalize_scope_mode(value: Any) -> Tuple[str, List[str]]:
    requested = str(value or "full").strip().lower().replace("-", "_")
    if requested in {"", "all"}:
        return "full", []
    if requested in {"file", "files", "command_files", "command_scoped", "command_scope"}:
        return "files", []
    if requested == "incremental":
        return "full", ["Incremental since-last-run scope is not supported yet; reviewing the full selected PR diff."]
    if requested not in SUPPORTED_SCOPE_MODES:
        return "full", [f"Unknown scope mode `{requested}`; reviewing the full selected PR diff."]
    return requested, []


def normalize_scope_patterns(value: Any) -> Tuple[List[str], List[str]]:
    patterns: List[str] = []
    warnings: List[str] = []
    for item in split_csv(value):
        normalized = item.strip()
        if not normalized:
            continue
        if normalized.startswith("/"):
            normalized = normalized.lstrip("/")
        if not normalized or ".." in normalized.split("/"):
            warnings.append("A scoped file pattern was ignored because it is not repository-relative.")
            continue
        if not SAFE_SCOPE_PATTERN_RE.fullmatch(normalized):
            warnings.append(f"Scoped file pattern `{normalized}` contains unsupported characters and was ignored.")
            continue
        patterns.append(normalized)
    return patterns, warnings


def _matches_scope(file_name: str, patterns: List[str]) -> bool:
    normalized = file_name.lstrip("/")
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in patterns)


def apply_review_scope(files: List[str], settings: Dict[str, Any]) -> Tuple[List[str], List[Dict[str, str]], Dict[str, Any]]:
    mode, mode_warnings = normalize_scope_mode(settings.get("scope_mode"))
    patterns, pattern_warnings = normalize_scope_patterns(settings.get("scope_files"))
    warnings = mode_warnings + pattern_warnings

    diagnostics: Dict[str, Any] = {
        "schema_version": SCOPE_SCHEMA_VERSION,
        "mode": mode,
        "requested_mode": str(settings.get("scope_mode") or "full"),
        "requested_files": patterns,
        "warnings": warnings,
        "changed_file_count": len(files),
        "selected_file_count": len(files),
        "skipped_file_count": 0,
    }

    if mode == "full":
        diagnostics["reason"] = "full_selected_diff"
        return files, [], diagnostics

    if not patterns:
        diagnostics["mode"] = "full"
        diagnostics["reason"] = "missing_scope_files"
        diagnostics["warnings"] = warnings + ["File-scoped review requested without --files; reviewing the full selected PR diff."]
        return files, [], diagnostics

    selected = [file_name for file_name in files if _matches_scope(file_name, patterns)]
    skipped = [
        {"path": file_name, "reason": "scope_not_requested"}
        for file_name in files
        if file_name not in selected
    ]
    diagnostics["selected_file_count"] = len(selected)
    diagnostics["skipped_file_count"] = len(skipped)
    diagnostics["reason"] = "command_scoped_files"
    if not selected:
        diagnostics["warnings"] = warnings + ["File-scoped review matched no changed files."]
    return selected, skipped, diagnostics
