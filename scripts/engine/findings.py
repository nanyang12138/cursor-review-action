import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from .diff_index import normalize_diff_path


FINDING_DEDUP_SCHEMA_VERSION = "finding-dedup/v1"

_SEVERITY_RANK = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "low": 2,
    "info": 1,
}
_CONFIDENCE_RANK = {
    "high": 3,
    "medium": 2,
    "low": 1,
}
_GROUNDING_RANK = {
    "anchored": 4,
    "file_only": 3,
    "unanchored": 2,
    "invalid": 1,
}


@dataclass
class FindingPostprocessResult:
    findings_json: str
    diagnostics: Dict[str, Any]


def _normalized_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:16]


def _line_identity(finding: Dict[str, Any]) -> Tuple[str, str]:
    line_side = str(finding.get("line_side") or "").strip().lower()
    if line_side == "old" or (finding.get("old_line") and not finding.get("line")):
        return "old", str(finding.get("old_line") or "")
    return "new", str(finding.get("line") or "")


def finding_fingerprint(finding: Dict[str, Any]) -> str:
    """Build a same-run deduplication fingerprint for FINDING-DEDUP-P0."""
    path = normalize_diff_path(finding.get("file"))
    category = _normalized_text(finding.get("category") or "unknown")
    line_side, line = _line_identity(finding)
    anchor = finding.get("anchor") if isinstance(finding.get("anchor"), dict) else {}
    hunk_signature = _stable_hash(str(anchor.get("hunk_header") or ""))
    title = _normalized_text(finding.get("title"))
    evidence_hash = _stable_hash(_normalized_text(finding.get("evidence")))

    if path and line:
        identity = "|".join([path, category, line_side, line, hunk_signature])
    else:
        identity = "|".join([path, category, line_side, line, title, evidence_hash])
    return _stable_hash(identity)


def _finding_sort_key(indexed_finding: Tuple[int, Dict[str, Any]]) -> Tuple[int, int, int, int, int, int]:
    original_index, finding = indexed_finding
    severity = _SEVERITY_RANK.get(str(finding.get("severity") or "").strip().lower(), 0)
    confidence = _CONFIDENCE_RANK.get(str(finding.get("confidence") or "").strip().lower(), 0)
    grounding = _GROUNDING_RANK.get(str(finding.get("grounding_status") or "").strip().lower(), 0)
    suppressed = 1 if finding.get("suppressed") else 0
    actionable = 1 if finding.get("suggestion") or finding.get("body") else 0
    return (-severity, -confidence, -grounding, suppressed, -actionable, original_index)


def _max_findings(settings: Dict[str, Any]) -> int:
    try:
        value = int(settings.get("max_findings", 0))
    except (TypeError, ValueError):
        return 0
    return value if value > 0 else 0


def _empty_diagnostics(command: str, settings: Dict[str, Any], applied: bool, reason: str) -> Dict[str, Any]:
    max_findings = _max_findings(settings)
    return {
        "schema_version": FINDING_DEDUP_SCHEMA_VERSION,
        "command": command,
        "applied": applied,
        "reason": reason,
        "max_findings": max_findings,
        "input_count": 0,
        "normalized_count": 0,
        "duplicate_count": 0,
        "deduplicated_count": 0,
        "capped_count": 0,
        "output_count": 0,
        "suppressed_count": 0,
    }


def postprocess_findings_json(findings_json: str, settings: Dict[str, Any], command: str = "review") -> FindingPostprocessResult:
    """Deduplicate, rank, and cap same-run review findings.

    Capability IDs: FINDING-DEDUP-P0, FINDING-TAXONOMY-P0.
    """
    diagnostics = _empty_diagnostics(command, settings, False, "not_applicable")
    if command != "review":
        diagnostics["reason"] = "unsupported_command"
        return FindingPostprocessResult(findings_json, diagnostics)

    try:
        payload = json.loads(findings_json or "[]")
    except Exception:
        diagnostics["reason"] = "invalid_findings_json"
        return FindingPostprocessResult("[]", diagnostics)
    if not isinstance(payload, list):
        diagnostics["reason"] = "non_review_payload"
        return FindingPostprocessResult(findings_json, diagnostics)

    diagnostics.update(
        {
            "applied": True,
            "reason": "applied",
            "input_count": len(payload),
        }
    )

    indexed: List[Tuple[int, Dict[str, Any]]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            continue
        finding = dict(item)
        fingerprint = finding_fingerprint(finding)
        finding["finding_fingerprint"] = fingerprint
        indexed.append((index, finding))

    diagnostics["normalized_count"] = len(indexed)
    sorted_findings = sorted(indexed, key=_finding_sort_key)
    seen = set()
    deduplicated: List[Dict[str, Any]] = []
    for _index, finding in sorted_findings:
        fingerprint = finding["finding_fingerprint"]
        if fingerprint in seen:
            diagnostics["duplicate_count"] += 1
            continue
        seen.add(fingerprint)
        deduplicated.append(finding)

    diagnostics["deduplicated_count"] = len(deduplicated)
    max_findings = diagnostics["max_findings"]
    if max_findings and len(deduplicated) > max_findings:
        diagnostics["capped_count"] = len(deduplicated) - max_findings
        deduplicated = deduplicated[:max_findings]

    diagnostics["output_count"] = len(deduplicated)
    diagnostics["suppressed_count"] = sum(1 for finding in deduplicated if finding.get("suppressed"))
    return FindingPostprocessResult(
        json.dumps(deduplicated, ensure_ascii=False, indent=2),
        diagnostics,
    )
