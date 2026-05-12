import json
from typing import Any, Dict, List


CI_POLICY_SCHEMA_VERSION = "ci-policy/v1"
HIGH_SEVERITIES = {"critical", "high"}


def _load_findings(findings_json: str) -> List[Dict[str, Any]]:
    try:
        payload = json.loads(findings_json or "[]")
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _highest_severity(findings: List[Dict[str, Any]]) -> str:
    severity_rank = {
        "critical": 5,
        "high": 4,
        "medium": 3,
        "low": 2,
        "info": 1,
    }
    highest = "none"
    highest_rank = 0
    for finding in findings:
        severity = str(finding.get("severity") or "").strip().lower()
        rank = severity_rank.get(severity, 0)
        if rank > highest_rank:
            highest = severity
            highest_rank = rank
    return highest


def evaluate_ci_policy(exit_code: int, findings_json: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate workflow status policy without letting model opinion block by default."""
    findings = _load_findings(findings_json)
    high_severity_count = sum(
        1
        for finding in findings
        if str(finding.get("severity") or "").strip().lower() in HIGH_SEVERITIES
    )
    fail_on_error = bool(settings.get("fail_on_error"))
    fail_on_findings = bool(settings.get("fail_on_findings"))

    workflow_exit_code = 0
    reason = "success"
    if exit_code != 0:
        if fail_on_error:
            workflow_exit_code = exit_code
            reason = "cursor_error_failed"
        else:
            reason = "cursor_error_non_blocking"
    elif findings:
        reason = "findings_non_blocking_default"

    findings_gate_status = "disabled"
    if fail_on_findings:
        # P0 keeps findings advisory. Severity-threshold gating is documented as a
        # future opt-in release gate and must not be inferred from a boolean alone.
        findings_gate_status = "reserved_no_threshold"

    return {
        "schema_version": CI_POLICY_SCHEMA_VERSION,
        "default": "advisory_non_blocking",
        "fail_on_error": fail_on_error,
        "fail_on_findings": fail_on_findings,
        "findings_gate_status": findings_gate_status,
        "findings_gate_enforced": False,
        "finding_count": len(findings),
        "high_severity_finding_count": high_severity_count,
        "highest_severity": _highest_severity(findings),
        "cursor_exit_code": exit_code,
        "workflow_exit_code": workflow_exit_code,
        "reason": reason,
    }


def ci_policy_json(decision: Dict[str, Any]) -> str:
    return json.dumps(decision, ensure_ascii=False, sort_keys=True)
