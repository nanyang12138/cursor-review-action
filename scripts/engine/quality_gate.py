import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .redaction import RedactionResult


QUALITY_GATE_SCHEMA_VERSION = "output-quality-gate/v1"

PUBLISH = "publish"
PUBLISH_PARTIAL = "publish_partial"
PUBLISH_WITH_DIAGNOSTICS = "publish_with_diagnostics"
SUPPRESS_FINDINGS = "suppress_findings"
FAIL_BEFORE_PUBLISH = "fail_before_publish"

PUBLISH_DECISIONS = {
    PUBLISH,
    PUBLISH_PARTIAL,
    PUBLISH_WITH_DIAGNOSTICS,
    SUPPRESS_FINDINGS,
    FAIL_BEFORE_PUBLISH,
}

REVIEW_REQUIRED_FIELDS = ("severity", "file", "line", "title", "body", "confidence", "suggestion", "evidence")
UNSUPPORTED_CLAIM_PATTERNS = (
    re.compile(r"\b(?:all\s+)?tests?\s+(?:passed|pass|green|succeeded)\b", re.IGNORECASE),
    re.compile(r"\b(?:i\s+)?(?:ran|executed)\s+(?:the\s+)?tests?\b", re.IGNORECASE),
    re.compile(r"\bsecurity\s+(?:verified|proven|confirmed)\b", re.IGNORECASE),
    re.compile(r"\bperformance\s+(?:verified|proven|confirmed|benchmarked)\b", re.IGNORECASE),
    re.compile(r"\b(?:deployed|verified)\s+in\s+(?:production|prod|staging)\b", re.IGNORECASE),
    re.compile(r"\b(?:customer|ticket|issue)\s+(?:fixed|resolved|closed)\b", re.IGNORECASE),
)


@dataclass
class QualityGateResult:
    findings_json: str
    diagnostics: Dict[str, Any]

    @property
    def publish_decision(self) -> str:
        return str(self.diagnostics.get("publish_decision") or PUBLISH_WITH_DIAGNOSTICS)


def _load_payload(findings_json: str) -> tuple[Any, bool]:
    try:
        return json.loads(findings_json or "[]"), True
    except Exception:
        return [], False


def _text_for_claim_scan(finding: Dict[str, Any]) -> str:
    parts = [
        finding.get("title", ""),
        finding.get("body", ""),
        finding.get("suggestion", ""),
        finding.get("evidence", ""),
    ]
    return " ".join(str(part) for part in parts if part)


def _has_unsupported_claim(finding: Dict[str, Any]) -> bool:
    text = _text_for_claim_scan(finding)
    return any(pattern.search(text) for pattern in UNSUPPORTED_CLAIM_PATTERNS)


def _missing_required_fields(finding: Dict[str, Any]) -> List[str]:
    missing = []
    for field in REVIEW_REQUIRED_FIELDS:
        if field == "line":
            if field not in finding:
                missing.append(field)
            continue
        value = finding.get(field)
        if value is None or str(value).strip() == "":
            missing.append(field)
    return missing


def _coverage_status(truncated: bool, meta: Dict[str, Any]) -> str:
    if truncated or meta.get("truncation_reasons"):
        return "partial"
    return "complete"


def _redaction_status(redaction_result: Optional[RedactionResult], runner_diagnostics: Dict[str, Any]) -> tuple[str, bool]:
    if runner_diagnostics.get("redaction_failure"):
        return "failed", True
    if isinstance(redaction_result, RedactionResult):
        return redaction_result.status, False
    diagnostic = runner_diagnostics.get("redaction") or {}
    if isinstance(diagnostic, dict):
        status = str(diagnostic.get("redaction_status") or diagnostic.get("status") or "unknown")
        return status, status == "failed"
    return "unknown", False


def _base_diagnostics(
    command: str,
    exit_code: int,
    parsed_ok: bool,
    truncated: bool,
    meta: Dict[str, Any],
    runner_diagnostics: Dict[str, Any],
    redaction_result: Optional[RedactionResult],
) -> Dict[str, Any]:
    parser_diagnostics = runner_diagnostics.get("parser") or {}
    schema_diagnostics = parser_diagnostics.get("schema") or {}
    grounding = parser_diagnostics.get("grounding") or {}
    taxonomy = parser_diagnostics.get("taxonomy") or {}
    findings = parser_diagnostics.get("findings") or {}
    redaction_status, redaction_failed = _redaction_status(redaction_result, runner_diagnostics)
    coverage_status = _coverage_status(truncated, meta)
    skipped_files = meta.get("skipped_files") or []
    return {
        "schema_version": QUALITY_GATE_SCHEMA_VERSION,
        "command": command,
        "applied": True,
        "publish_decision": PUBLISH,
        "reason": "passed",
        "parsed_ok": bool(parsed_ok),
        "schema_valid": bool(parsed_ok and schema_diagnostics.get("compatible", parsed_ok)),
        "schema_status": schema_diagnostics.get("payload_schema_status", "unknown"),
        "grounding_applied": bool(grounding.get("applied", False)),
        "taxonomy_applied": bool(taxonomy.get("applied", False)),
        "dedup_applied": bool(findings.get("applied", False)),
        "coverage_status": coverage_status,
        "diff_truncated": bool(truncated),
        "skipped_file_count": len(skipped_files),
        "redaction_status": redaction_status,
        "redaction_failed": redaction_failed,
        "cursor_exit_code": int(exit_code),
        "input_finding_count": 0,
        "publishable_finding_count": 0,
        "human_verification_finding_count": 0,
        "suppressed_finding_count": 0,
        "invalid_grounding_count": int(grounding.get("invalid_count", grounding.get("invalid_anchor_count", 0)) or 0),
        "unanchored_finding_count": int(grounding.get("unanchored_count", 0) or 0),
        "duplicate_finding_count": int(findings.get("duplicate_count", 0) or 0),
        "missing_required_field_count": 0,
        "unsupported_claim_count": 0,
        "downgraded_finding_count": 0,
        "quality_gate_notes": [],
    }


def _quality_status_for_finding(finding: Dict[str, Any]) -> tuple[str, bool]:
    if finding.get("suppressed"):
        return "suppressed", False
    grounding_status = str(finding.get("grounding_status") or "").strip().lower()
    if grounding_status == "anchored":
        return "publishable", True
    if grounding_status == "file_only":
        return "needs_human_verification", False
    if grounding_status in {"invalid", "unanchored"}:
        return "diagnostics", False
    return "needs_human_verification", False


def _annotate_review_findings(payload: List[Any], diagnostics: Dict[str, Any]) -> List[Any]:
    annotated: List[Any] = []
    diagnostics["input_finding_count"] = len(payload)
    for item in payload:
        if not isinstance(item, dict):
            diagnostics["suppressed_finding_count"] += 1
            annotated.append(item)
            continue

        finding = dict(item)
        reasons: List[str] = []
        missing_fields = _missing_required_fields(finding)
        if missing_fields:
            diagnostics["missing_required_field_count"] += 1
            diagnostics["downgraded_finding_count"] += 1
            reasons.append("missing_required_fields:" + ",".join(missing_fields))
            finding["confidence"] = "low"
            finding["suppressed"] = True
            finding["suppression_reason"] = "missing_required_fields"
            finding["missing_required_fields"] = missing_fields

        if _has_unsupported_claim(finding):
            diagnostics["unsupported_claim_count"] += 1
            diagnostics["downgraded_finding_count"] += 1
            reasons.append("unsupported_claim")
            finding["confidence"] = "low"
            finding["suppressed"] = True
            finding["suppression_reason"] = "unsupported_claim"
            finding["unsupported_claim"] = True

        status, publishable = _quality_status_for_finding(finding)
        finding["quality_gate_status"] = status
        finding["publishable"] = publishable
        if reasons:
            finding["quality_gate_reasons"] = reasons

        if publishable:
            diagnostics["publishable_finding_count"] += 1
        elif status == "needs_human_verification":
            diagnostics["human_verification_finding_count"] += 1
        else:
            diagnostics["suppressed_finding_count"] += 1
        annotated.append(finding)
    return annotated


def _decision(diagnostics: Dict[str, Any]) -> tuple[str, str]:
    if diagnostics["redaction_failed"]:
        return FAIL_BEFORE_PUBLISH, "redaction_failed"
    if diagnostics["cursor_exit_code"] != 0:
        return FAIL_BEFORE_PUBLISH, "cursor_error"
    if not diagnostics["parsed_ok"] or not diagnostics["schema_valid"]:
        return PUBLISH_WITH_DIAGNOSTICS, "parser_or_schema_diagnostics"
    if diagnostics["coverage_status"] == "partial":
        return PUBLISH_PARTIAL, "partial_review"
    if diagnostics["input_finding_count"] and not diagnostics["publishable_finding_count"]:
        return SUPPRESS_FINDINGS, "no_publishable_findings"
    if (
        diagnostics["missing_required_field_count"]
        or diagnostics["unsupported_claim_count"]
        or diagnostics["invalid_grounding_count"]
        or diagnostics["unanchored_finding_count"]
        or diagnostics["duplicate_finding_count"]
    ):
        return PUBLISH_WITH_DIAGNOSTICS, "quality_diagnostics"
    return PUBLISH, "passed"


def evaluate_output_quality(
    markdown: str,
    findings_json: str,
    exit_code: int,
    parsed_ok: bool,
    truncated: bool,
    meta: Dict[str, Any],
    settings: Dict[str, Any],
    runner_diagnostics: Optional[Dict[str, Any]] = None,
    redaction_result: Optional[RedactionResult] = None,
) -> QualityGateResult:
    """Apply deterministic publication rules before rendering.

    Capability IDs: OUTPUT-QUALITY-GATE-P0, FINDING-GROUNDING-P0,
    FINDING-DEDUP-P0, SEC-PRIVACY-P0.
    """
    del markdown  # The P0 gate publishes markdown diagnostics but only mutates structured findings.
    runner_diagnostics = runner_diagnostics or {}
    command = str(settings.get("resolved_command") or settings.get("command") or "review")
    diagnostics = _base_diagnostics(command, exit_code, parsed_ok, truncated, meta, runner_diagnostics, redaction_result)
    payload, payload_valid = _load_payload(findings_json)
    if not payload_valid:
        diagnostics["schema_valid"] = False
        diagnostics["quality_gate_notes"].append("invalid_findings_json")

    gated_payload = payload
    if command == "review" and isinstance(payload, list):
        gated_payload = _annotate_review_findings(payload, diagnostics)
    elif command != "review":
        diagnostics["quality_gate_notes"].append("command_policy_non_review")
    elif not isinstance(payload, list):
        diagnostics["schema_valid"] = False
        diagnostics["quality_gate_notes"].append("review_payload_not_array")

    decision, reason = _decision(diagnostics)
    diagnostics["publish_decision"] = decision
    diagnostics["reason"] = reason
    return QualityGateResult(
        json.dumps(gated_payload, ensure_ascii=False, indent=2),
        diagnostics,
    )
