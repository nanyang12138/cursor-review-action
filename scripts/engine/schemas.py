import json
from copy import deepcopy
from typing import Any, Dict, List


SCHEMA_COMPATIBILITY_VERSION = "schema-compatibility/v1"
OUTPUT_SCHEMA_VERSION = "cursor-review-action/v1"
SCHEMA_VERSION = OUTPUT_SCHEMA_VERSION
FINDING_SCHEMA_VERSION = "cursor-review-finding/v1"
SUPPORTED_OUTPUT_SCHEMA_VERSIONS = (OUTPUT_SCHEMA_VERSION,)
SUPPORTED_FINDING_SCHEMA_VERSIONS = (FINDING_SCHEMA_VERSION,)

_REVIEW_FINDING = {
    "schema_version": FINDING_SCHEMA_VERSION,
    "category": "bug|security|test_gap|performance|regression_risk|maintainability|docs|question",
    "severity": "critical|high|medium|low|info",
    "confidence": "high|medium|low",
    "file": "path relative to repository root, or empty string when not file-specific",
    "line": "new-side line number as integer, or null when not line-specific",
    "title": "short actionable finding title",
    "body": "why this matters and what can go wrong",
    "suggestion": "concrete fix or mitigation",
    "evidence": "brief quote or description from the selected diff/context",
    "noise_control": "actionable_review",
}

SCHEMAS: Dict[str, Dict[str, Any]] = {
    "review": {
        "schema_version": SCHEMA_VERSION,
        "command": "review",
        "type": "array",
        "description": "Actionable review findings only.",
        "items": _REVIEW_FINDING,
    },
    "ask": {
        "schema_version": SCHEMA_VERSION,
        "command": "ask",
        "type": "object",
        "description": "Direct answer to the user's question, grounded in PR evidence.",
        "properties": {
            "answer": "direct answer in the requested language",
            "evidence": ["file path, hunk, or PR-context references used to answer"],
            "limitations": ["important uncertainty or missing context"],
            "follow_up_questions": ["optional clarifying questions when the PR context is insufficient"],
        },
    },
    "improve": {
        "schema_version": SCHEMA_VERSION,
        "command": "improve",
        "type": "object",
        "description": "Prioritized improvement suggestions that are not duplicate bug findings.",
        "properties": {
            "suggestions": [
                {
                    "schema_version": FINDING_SCHEMA_VERSION,
                    "priority": "high|medium|low",
                    "category": "maintainability|readability|tests|performance|developer-experience",
                    "file": "path relative to repository root, or empty string",
                    "line": "new-side line number as integer, or null",
                    "title": "short improvement title",
                    "rationale": "why this change improves the PR",
                    "suggestion": "specific implementation guidance",
                    "evidence": "brief quote or description from selected diff/context",
                }
            ]
        },
    },
    "describe": {
        "schema_version": SCHEMA_VERSION,
        "command": "describe",
        "type": "object",
        "description": "PR description content for a comment-only summary.",
        "properties": {
            "summary": "concise summary of the PR",
            "walkthrough": ["notable changed files or areas and what changed"],
            "risks": ["risk or compatibility notes"],
            "tests": ["tests observed in the PR or tests the author should run"],
            "changelog": "optional user-facing changelog entry, or empty string",
        },
    },
}


def schema_for_command(command: str) -> Dict[str, Any]:
    return deepcopy(SCHEMAS.get(command, SCHEMAS["review"]))


def schema_text(command: str) -> str:
    return json.dumps(schema_for_command(command), ensure_ascii=False, indent=2)


def schema_contract(command: str) -> Dict[str, Any]:
    schema = schema_for_command(command)
    return {
        "schema_compatibility": SCHEMA_COMPATIBILITY_VERSION,
        "command": schema.get("command", "review"),
        "current_output_schema_version": OUTPUT_SCHEMA_VERSION,
        "supported_output_schema_versions": list(SUPPORTED_OUTPUT_SCHEMA_VERSIONS),
        "current_finding_schema_version": FINDING_SCHEMA_VERSION,
        "supported_finding_schema_versions": list(SUPPORTED_FINDING_SCHEMA_VERSIONS),
        "stable_fields": stable_fields_for_command(command),
    }


def stable_fields_for_command(command: str) -> List[str]:
    schema = schema_for_command(command)
    fields = ["schema_version", "command"]
    properties = schema.get("properties")
    if isinstance(properties, dict):
        fields.extend(str(field) for field in properties.keys())
    if schema.get("type") == "array":
        fields.extend(str(field) for field in _REVIEW_FINDING.keys())
    return fields


def output_schema_diagnostics(payload: Any, command: str) -> Dict[str, Any]:
    contract = schema_contract(command)
    diagnostics: Dict[str, Any] = {
        **contract,
        "payload_shape": type(payload).__name__,
        "payload_schema_version": "",
        "payload_schema_status": "unknown",
        "finding_schema_versions": [],
        "command_match": True,
        "compatible": True,
        "reason": "compatible_current_schema",
    }

    if isinstance(payload, list):
        finding_versions = sorted(
            {
                str(item.get("schema_version") or "")
                for item in payload
                if isinstance(item, dict) and item.get("schema_version")
            }
        )
        diagnostics["payload_shape"] = "array"
        diagnostics["payload_schema_version"] = "finding-level"
        diagnostics["finding_schema_versions"] = finding_versions
        if not payload:
            diagnostics["payload_schema_status"] = "empty_review_array"
        elif finding_versions and all(version in SUPPORTED_FINDING_SCHEMA_VERSIONS for version in finding_versions):
            diagnostics["payload_schema_status"] = "finding_level_current"
        elif not finding_versions:
            diagnostics["payload_schema_status"] = "legacy_missing_finding_schema_version"
            diagnostics["reason"] = "legacy_missing_schema_version"
        else:
            diagnostics["compatible"] = False
            diagnostics["payload_schema_status"] = "unsupported_finding_schema_version"
            diagnostics["reason"] = "unsupported_schema_version"
        return diagnostics

    if isinstance(payload, dict):
        payload_version = str(payload.get("schema_version") or "")
        payload_command = str(payload.get("command") or "")
        diagnostics["payload_shape"] = "object"
        diagnostics["payload_schema_version"] = payload_version
        if payload_command and payload_command != contract["command"]:
            diagnostics["compatible"] = False
            diagnostics["command_match"] = False
            diagnostics["reason"] = "command_mismatch"

        if payload_version in SUPPORTED_OUTPUT_SCHEMA_VERSIONS:
            diagnostics["payload_schema_status"] = "current"
        elif not payload_version:
            diagnostics["payload_schema_status"] = "legacy_missing_schema_version"
            if diagnostics["compatible"]:
                diagnostics["reason"] = "legacy_missing_schema_version"
        else:
            diagnostics["compatible"] = False
            diagnostics["payload_schema_status"] = "unsupported_schema_version"
            diagnostics["reason"] = "unsupported_schema_version"
        return diagnostics

    diagnostics["compatible"] = False
    diagnostics["payload_schema_status"] = "unsupported_payload_shape"
    diagnostics["reason"] = "unsupported_payload_shape"
    return diagnostics
