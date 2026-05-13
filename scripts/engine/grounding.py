import copy
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .diff_index import DIFF_INDEX_SCHEMA_VERSION, normalize_diff_path


GROUNDING_SCHEMA_VERSION = "finding-grounding/v1"
GROUNDING_STATUSES = {"anchored", "file_only", "unanchored", "invalid"}


@dataclass
class GroundingResult:
    findings_json: str
    diagnostics: Dict[str, Any]


def _line_value(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _entry_for_path(diff_index: Dict[str, Any], path: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    normalized = normalize_diff_path(path)
    aliases = diff_index.get("aliases") or {}
    canonical = aliases.get(normalized, normalized)
    files = diff_index.get("files") or {}
    return canonical, files.get(canonical)


def _anchor_for_line(entry: Dict[str, Any], line: int, line_side: str) -> Dict[str, Any]:
    anchor = {
        "file": entry.get("path", ""),
        "line_side": line_side,
    }
    if line_side == "old":
        anchor["old_line"] = line
    else:
        anchor["line"] = line
    for hunk in entry.get("hunks") or []:
        changed_lines = hunk.get("old_changed_lines" if line_side == "old" else "new_changed_lines") or []
        if line in changed_lines:
            anchor["hunk_header"] = hunk.get("header", "")
            break
    return anchor


def _classify_finding(finding: Dict[str, Any], diff_index: Dict[str, Any]) -> Tuple[str, str, Optional[Dict[str, Any]]]:
    raw_path = finding.get("file")
    path = normalize_diff_path(raw_path)
    if not path:
        return "unanchored", "missing_file_path", None

    canonical, entry = _entry_for_path(diff_index, path)
    skipped_paths = set(diff_index.get("skipped_file_paths") or [])
    if entry is None:
        if canonical in skipped_paths or path in skipped_paths:
            return "invalid", "skipped_file", None
        return "invalid", "file_not_in_selected_diff", None

    old_line = _line_value(finding.get("old_line"))
    new_line = _line_value(finding.get("line"))
    requested_side = str(finding.get("line_side") or "").strip().lower()
    line_side = "old" if requested_side == "old" or (old_line is not None and new_line is None) else "new"

    if line_side == "old":
        if old_line is None:
            return "file_only", "missing_old_line", None
        if old_line in set(entry.get("old_changed_lines") or []):
            return "anchored", "old_changed_line", _anchor_for_line(entry, old_line, "old")
        return "file_only", "old_line_not_in_selected_diff", None

    if new_line is None:
        return "file_only", "missing_new_line", None
    if new_line in set(entry.get("new_changed_lines") or []):
        return "anchored", "new_changed_line", _anchor_for_line(entry, new_line, "new")
    return "file_only", "new_line_not_in_selected_diff", None


def _apply_status_fields(finding: Dict[str, Any], status: str, reason: str, anchor: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    grounded = copy.deepcopy(finding)
    grounded["grounding_status"] = status
    grounded["grounding_reason"] = reason
    if anchor:
        grounded["anchor"] = anchor
    if status == "anchored":
        grounded["review_section"] = "main"
    elif status == "file_only":
        grounded["review_section"] = "needs_human_verification"
        grounded["needs_human_verification"] = True
    elif status in {"unanchored", "invalid"}:
        grounded["confidence"] = "low"
        grounded["suppressed"] = True
        grounded["suppression_reason"] = "invalid_anchor" if status == "invalid" else "unanchored_finding"
        grounded["review_section"] = "diagnostics"
    return grounded


def _empty_diagnostics(command: str, diff_index: Dict[str, Any], applied: bool, reason: str = "") -> Dict[str, Any]:
    diagnostics: Dict[str, Any] = {
        "schema_version": GROUNDING_SCHEMA_VERSION,
        "command": command,
        "applied": applied,
        "reason": reason or ("applied" if applied else "not_applicable"),
        "diff_index_schema_version": diff_index.get("schema_version", ""),
        "diff_index_file_count": diff_index.get("file_count", 0),
        "total_findings": 0,
        "anchored_count": 0,
        "file_only_count": 0,
        "unanchored_count": 0,
        "invalid_count": 0,
        "invalid_anchor_count": 0,
        "skipped_file_finding_count": 0,
    }
    return diagnostics


def ground_findings_json(findings_json: str, diff_index: Dict[str, Any], command: str = "review") -> GroundingResult:
    """Annotate parsed review findings with selected-diff grounding status.

    Capability IDs: DIFF-INDEX-P0, FINDING-GROUNDING-P0.
    """
    if command != "review":
        return GroundingResult(
            findings_json,
            _empty_diagnostics(command, diff_index, False, "unsupported_command"),
        )
    if diff_index.get("schema_version") != DIFF_INDEX_SCHEMA_VERSION:
        return GroundingResult(
            findings_json,
            _empty_diagnostics(command, diff_index, False, "missing_diff_index"),
        )

    try:
        payload = json.loads(findings_json or "[]")
    except Exception:
        return GroundingResult(
            "[]",
            _empty_diagnostics(command, diff_index, False, "invalid_findings_json"),
        )
    if not isinstance(payload, list):
        return GroundingResult(
            findings_json,
            _empty_diagnostics(command, diff_index, False, "non_review_payload"),
        )

    diagnostics = _empty_diagnostics(command, diff_index, True, "applied")
    grounded_findings: List[Any] = []
    for item in payload:
        if not isinstance(item, dict):
            grounded_findings.append(item)
            diagnostics["unanchored_count"] += 1
            continue
        status, reason, anchor = _classify_finding(item, diff_index)
        grounded_findings.append(_apply_status_fields(item, status, reason, anchor))
        diagnostics["total_findings"] += 1
        diagnostics[f"{status}_count"] += 1
        if status == "invalid":
            diagnostics["invalid_anchor_count"] += 1
        if reason == "skipped_file":
            diagnostics["skipped_file_finding_count"] += 1

    return GroundingResult(
        json.dumps(grounded_findings, ensure_ascii=False, indent=2),
        diagnostics,
    )
