from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


FINDING_SCHEMA_VERSION = "cursor-review-finding/v1"

REVIEW_CATEGORIES = {
    "bug",
    "security",
    "test_gap",
    "performance",
    "regression_risk",
    "maintainability",
    "docs",
    "question",
}
IMPROVEMENT_CATEGORIES = {
    "maintainability",
    "readability",
    "tests",
    "performance",
    "developer-experience",
}
NOISE_REVIEW_CATEGORIES = {
    "style",
    "readability",
    "refactor",
    "formatting",
    "nit",
    "maintainability",
    "docs",
    "question",
}
SEVERITIES = {"critical", "high", "medium", "low", "info"}
CONFIDENCES = {"high", "medium", "low"}


@dataclass
class TaxonomyResult:
    payload: Any
    diagnostics: Dict[str, Any]


def _normalized_value(value: Any) -> str:
    return str(value or "").strip().lower()


def _text_blob(finding: Dict[str, Any]) -> str:
    parts = [
        finding.get("category", ""),
        finding.get("title", ""),
        finding.get("body", ""),
        finding.get("suggestion", ""),
        finding.get("evidence", ""),
    ]
    return " ".join(str(part).lower() for part in parts if part)


def infer_review_category(finding: Dict[str, Any]) -> str:
    text = _text_blob(finding)
    if any(keyword in text for keyword in ("secret", "token", "auth", "permission", "xss", "csrf", "sql injection")):
        return "security"
    if any(keyword in text for keyword in ("test", "coverage", "assert", "fixture")):
        return "test_gap"
    if any(keyword in text for keyword in ("latency", "slow", "performance", "memory", "cpu")):
        return "performance"
    if any(keyword in text for keyword in ("breaking", "compat", "migration", "api contract")):
        return "regression_risk"
    if any(keyword in text for keyword in ("build", "ci", "dependency", "package", "workflow")):
        return "regression_risk"
    if any(keyword in text for keyword in ("readme", "docs", "documentation")):
        return "docs"
    return "bug"


def _normalize_review_finding(finding: Dict[str, Any], diagnostics: Dict[str, Any]) -> Dict[str, Any]:
    normalized = deepcopy(finding)
    normalized["schema_version"] = FINDING_SCHEMA_VERSION

    severity = _normalized_value(normalized.get("severity"))
    if severity not in SEVERITIES:
        severity = "medium"
        diagnostics["invalid_severity_count"] += 1
    normalized["severity"] = severity

    confidence = _normalized_value(normalized.get("confidence"))
    if confidence not in CONFIDENCES:
        confidence = "medium"
        diagnostics["invalid_confidence_count"] += 1
    normalized["confidence"] = confidence

    raw_category = _normalized_value(normalized.get("category"))
    if not raw_category:
        normalized["category"] = infer_review_category(normalized)
        diagnostics["defaulted_category_count"] += 1
        if normalized["category"] in NOISE_REVIEW_CATEGORIES:
            normalized["severity"] = "low"
            normalized["confidence"] = "low"
            normalized["suppressed"] = True
            normalized["suppression_reason"] = "review_noise_control"
            normalized["noise_control"] = "route_to_cursor_improve"
            diagnostics["noise_suppressed_count"] += 1
    elif raw_category in NOISE_REVIEW_CATEGORIES:
        normalized["category"] = raw_category
        normalized["severity"] = "low"
        normalized["confidence"] = "low"
        normalized["suppressed"] = True
        normalized["suppression_reason"] = "review_noise_control"
        normalized["noise_control"] = "route_to_cursor_improve"
        diagnostics["noise_suppressed_count"] += 1
    elif raw_category in REVIEW_CATEGORIES:
        normalized["category"] = raw_category
    else:
        normalized["category"] = infer_review_category(normalized)
        diagnostics["invalid_category_count"] += 1

    normalized.setdefault("noise_control", "actionable_review")
    diagnostics["normalized_count"] += 1
    return normalized


def _normalize_improve_suggestion(suggestion: Dict[str, Any], diagnostics: Dict[str, Any]) -> Dict[str, Any]:
    normalized = deepcopy(suggestion)
    normalized["schema_version"] = FINDING_SCHEMA_VERSION
    category = _normalized_value(normalized.get("category"))
    if category not in IMPROVEMENT_CATEGORIES:
        normalized["category"] = "maintainability"
        diagnostics["invalid_category_count"] += 1
    else:
        normalized["category"] = category
    diagnostics["normalized_count"] += 1
    return normalized


def apply_finding_taxonomy(payload: Any, command: str) -> TaxonomyResult:
    diagnostics: Dict[str, Any] = {
        "schema_version": FINDING_SCHEMA_VERSION,
        "command": command,
        "applied": False,
        "normalized_count": 0,
        "defaulted_category_count": 0,
        "invalid_category_count": 0,
        "invalid_severity_count": 0,
        "invalid_confidence_count": 0,
        "noise_suppressed_count": 0,
    }

    if command == "review" and isinstance(payload, list):
        diagnostics["applied"] = True
        return TaxonomyResult(
            [_normalize_review_finding(item, diagnostics) if isinstance(item, dict) else item for item in payload],
            diagnostics,
        )

    if command == "improve" and isinstance(payload, dict) and isinstance(payload.get("suggestions"), list):
        normalized = deepcopy(payload)
        diagnostics["applied"] = True
        normalized["suggestions"] = [
            _normalize_improve_suggestion(item, diagnostics) if isinstance(item, dict) else item
            for item in normalized["suggestions"]
        ]
        return TaxonomyResult(normalized, diagnostics)

    diagnostics["reason"] = "command_or_shape_not_taxonomized"
    return TaxonomyResult(payload, diagnostics)


def taxonomy_summary(diagnostics: Dict[str, Any]) -> List[Tuple[str, Any]]:
    if not diagnostics:
        return []
    keys = [
        ("Taxonomy schema", "schema_version"),
        ("Taxonomy applied", "applied"),
        ("Taxonomy normalized findings", "normalized_count"),
        ("Taxonomy defaulted categories", "defaulted_category_count"),
        ("Taxonomy invalid categories", "invalid_category_count"),
        ("Taxonomy invalid severities", "invalid_severity_count"),
        ("Taxonomy invalid confidences", "invalid_confidence_count"),
        ("Taxonomy noise suppressed", "noise_suppressed_count"),
    ]
    return [(label, diagnostics.get(key)) for label, key in keys if key in diagnostics]
