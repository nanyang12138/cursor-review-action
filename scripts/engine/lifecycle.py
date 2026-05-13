from typing import Any, Dict, Iterable, Mapping, Optional


LIFECYCLE_SCHEMA_VERSION = "review-lifecycle/v1"

QUEUED = "queued"
COLLECTING_CONTEXT = "collecting_context"
SELECTING_DIFF = "selecting_diff"
CALLING_CURSOR = "calling_cursor"
PARSING_OUTPUT = "parsing_output"
PUBLISHED = "published"
FAILED = "failed"
PARTIAL = "partial"
SKIPPED = "skipped"

TERMINAL_STATES = {PUBLISHED, FAILED, PARTIAL, SKIPPED}
KNOWN_STATES = {
    QUEUED,
    COLLECTING_CONTEXT,
    SELECTING_DIFF,
    CALLING_CURSOR,
    PARSING_OUTPUT,
    *TERMINAL_STATES,
}

PARTIAL_DECISIONS = {
    "publish_partial",
    "publish_with_diagnostics",
    "suppress_findings",
}


def _state_sequence_with(sequence: Iterable[str], state: str) -> list[str]:
    states = [item for item in sequence if item in KNOWN_STATES]
    if not states or states[-1] != state:
        states.append(state)
    return states


def _quality_decision(quality_gate: Optional[Mapping[str, Any]]) -> str:
    if not isinstance(quality_gate, Mapping):
        return ""
    return str(quality_gate.get("publish_decision") or "")


def start_lifecycle(command: Any, run_metadata: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Create P0 lifecycle diagnostics for REVIEW-LIFECYCLE-P0.

    The lifecycle is diagnostic-only: it does not publish progress comments, block
    merges, approve PRs, or change the action's public inputs.
    """
    run_metadata = run_metadata or {}
    return {
        "schema_version": LIFECYCLE_SCHEMA_VERSION,
        "command": str(command or "review"),
        "current_state": QUEUED,
        "final_state": "",
        "terminal": False,
        "reason": "queued",
        "state_sequence": [QUEUED],
        "partial_reason": "",
        "failed_stage": "",
        "publish_decision": "",
        "cursor_contacted": False,
        "should_comment": True,
        "run_id": str(run_metadata.get("run_id") or ""),
        "head_sha": str(run_metadata.get("head_sha") or ""),
    }


def advance_lifecycle(lifecycle: Mapping[str, Any], state: str, reason: str = "", **fields: Any) -> Dict[str, Any]:
    if state not in KNOWN_STATES:
        raise ValueError(f"unknown lifecycle state: {state}")
    updated = dict(lifecycle)
    updated["current_state"] = state
    updated["reason"] = reason or updated.get("reason") or state
    updated["state_sequence"] = _state_sequence_with(updated.get("state_sequence") or [], state)
    updated.update(fields)
    if state in TERMINAL_STATES:
        updated["final_state"] = state
        updated["terminal"] = True
    return updated


def finalize_lifecycle(
    lifecycle: Mapping[str, Any],
    *,
    exit_code: int = 0,
    parsed_ok: bool = True,
    diff_truncated: bool = False,
    quality_gate: Optional[Mapping[str, Any]] = None,
    cursor_contacted: bool = False,
    should_comment: bool = True,
    explicit_state: str = "",
    reason: str = "",
    failure_stage: str = "",
) -> Dict[str, Any]:
    decision = _quality_decision(quality_gate)
    if explicit_state:
        final_state = explicit_state
    elif exit_code != 0 or decision == "fail_before_publish":
        final_state = FAILED
    elif diff_truncated or not parsed_ok or decision in PARTIAL_DECISIONS:
        final_state = PARTIAL
    else:
        final_state = PUBLISHED

    if final_state not in TERMINAL_STATES:
        raise ValueError(f"unknown terminal lifecycle state: {final_state}")

    if not reason:
        if final_state == FAILED:
            reason = "quality_gate_blocked" if decision == "fail_before_publish" else "cursor_or_engine_error"
        elif final_state == PARTIAL:
            reason = "partial_review"
        elif final_state == SKIPPED:
            reason = "skipped_before_cursor"
        else:
            reason = "published"

    updated = advance_lifecycle(
        lifecycle,
        final_state,
        reason,
        publish_decision=decision,
        cursor_contacted=cursor_contacted,
        should_comment=should_comment,
    )
    if final_state == PARTIAL and not updated.get("partial_reason"):
        updated["partial_reason"] = reason
    if final_state == FAILED and failure_stage:
        updated["failed_stage"] = failure_stage
    return updated


def lifecycle_diagnostics(lifecycle: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": lifecycle.get("schema_version", LIFECYCLE_SCHEMA_VERSION),
        "command": lifecycle.get("command", "review"),
        "final_state": lifecycle.get("final_state") or lifecycle.get("current_state", QUEUED),
        "reason": lifecycle.get("reason", "unknown"),
        "state_sequence": list(lifecycle.get("state_sequence") or []),
        "partial_reason": lifecycle.get("partial_reason", ""),
        "failed_stage": lifecycle.get("failed_stage", ""),
        "publish_decision": lifecycle.get("publish_decision", ""),
        "cursor_contacted": bool(lifecycle.get("cursor_contacted", False)),
        "should_comment": bool(lifecycle.get("should_comment", True)),
        "terminal": bool(lifecycle.get("terminal", False)),
        "run_id": lifecycle.get("run_id", ""),
        "head_sha": lifecycle.get("head_sha", ""),
    }
