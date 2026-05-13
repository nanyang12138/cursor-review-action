import copy
import json
from typing import Any, Dict

OUTPUT_SCHEMA_VERSION = "cursor-review-action/v1"
SCHEMA_VERSION = OUTPUT_SCHEMA_VERSION
SCHEMA_COMPATIBILITY_VERSION = "schema-compatibility/v1"
FINDING_SCHEMA_VERSION = "cursor-review-finding/v1"
SUPPORTED_OUTPUT_SCHEMA_VERSIONS = [OUTPUT_SCHEMA_VERSION]


COMMON_RESPONSE_WRAPPER: Dict[str, Any] = {
    "review_markdown": "string with the human-readable response",
    "findings_json": "JSON array matching the command schema below",
}


COMMAND_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "review": {
        "schema_name": "cursor_review_findings",
        "schema_version": "1.0",
        "type": "array",
        "items": {
            "type": "object",
            "required": ["severity", "file", "line", "title", "body", "confidence", "suggestion", "evidence"],
            "properties": {
                "severity": "critical | high | medium | low",
                "file": "changed file path",
                "line": "changed line number, or null when only file-level evidence is available",
                "title": "short actionable finding title",
                "body": "why this is a correctness, security, performance, test, or regression risk",
                "confidence": "high | medium | low",
                "suggestion": "concrete fix direction",
                "evidence": "short quote or summary from the selected diff/context",
            },
        },
    },
    "ask": {
        "schema_name": "cursor_ask_evidence",
        "schema_version": "1.0",
        "type": "array",
        "items": {
            "type": "object",
            "required": ["file", "line", "question_relevance", "evidence"],
            "properties": {
                "file": "changed file path, or null for PR-level evidence",
                "line": "changed line number, or null for PR-level evidence",
                "question_relevance": "why this evidence answers the user question",
                "evidence": "short quote or summary from the selected diff/context",
            },
        },
    },
    "improve": {
        "schema_name": "cursor_improve_suggestions",
        "schema_version": "1.0",
        "type": "array",
        "items": {
            "type": "object",
            "required": ["priority", "file", "line", "title", "body", "confidence", "suggestion", "evidence"],
            "properties": {
                "priority": "high | medium | low",
                "file": "changed file path, or null for PR-level suggestion",
                "line": "changed line number, or null for PR-level suggestion",
                "title": "short improvement title",
                "body": "why the improvement is useful and not a duplicate review finding",
                "confidence": "high | medium | low",
                "suggestion": "concrete before/after guidance when safe",
                "evidence": "short quote or summary from the selected diff/context",
            },
        },
    },
    "describe": {
        "schema_name": "cursor_describe_sections",
        "schema_version": "1.0",
        "type": "array",
        "items": {
            "type": "object",
            "required": ["section", "content", "evidence"],
            "properties": {
                "section": "summary | walkthrough | risk | tests | changelog",
                "content": "concise section content suitable for a PR comment",
                "evidence": "short quote or summary from the selected diff/context",
            },
        },
    },
}


COMMAND_OUTPUT_EXAMPLES: Dict[str, Dict[str, Any]] = {
    "review": {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "command": "review",
        "findings": [
            {
                "schema_version": FINDING_SCHEMA_VERSION,
                "category": "bug|security|test_gap|performance|regression_risk|maintainability|docs|question",
                "severity": "critical|high|medium|low|info",
                "confidence": "high|medium|low",
                "file": "changed file path",
                "line": "changed new-side line number or null",
                "old_line": "changed old-side line number or null for deleted-line evidence",
                "line_side": "new|old|file",
                "title": "short actionable finding title",
                "body": "why this is a correctness, security, performance, test, or regression risk",
                "suggestion": "concrete fix direction",
                "evidence": "short quote or summary from the selected diff/context",
            }
        ],
    },
    "ask": {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "command": "ask",
        "answer": "direct answer to the user's question",
        "evidence": ["short evidence citations from the selected diff/context"],
        "limitations": ["missing context or uncertainty"],
        "follow_up_questions": [],
    },
    "improve": {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "command": "improve",
        "suggestions": [
            {
                "schema_version": FINDING_SCHEMA_VERSION,
                "category": "maintainability|readability|tests|performance|developer-experience",
                "priority": "high|medium|low",
                "confidence": "high|medium|low",
                "file": "changed file path or null",
                "line": "changed line number or null",
                "title": "short improvement title",
                "body": "why the improvement is useful and not a duplicate review finding",
                "suggestion": "concrete before/after guidance when safe",
                "evidence": "short quote or summary from the selected diff/context",
            }
        ],
    },
    "describe": {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "command": "describe",
        "summary": "concise PR summary",
        "walkthrough": ["changed-area walkthrough items"],
        "risks": ["risk or uncertainty items"],
        "tests": ["test notes or missing test evidence"],
        "changelog": "optional changelog-style note",
    },
}


def schema_for_command(command: str) -> Dict[str, Any]:
    return copy.deepcopy(COMMAND_SCHEMAS.get(command, COMMAND_SCHEMAS["review"]))


def output_schema_for_command(command: str) -> Dict[str, Any]:
    return copy.deepcopy(COMMAND_OUTPUT_EXAMPLES.get(command, COMMAND_OUTPUT_EXAMPLES["review"]))


def schema_contract(command: str) -> Dict[str, Any]:
    output_schema = output_schema_for_command(command)
    return {
        "schema_compatibility": SCHEMA_COMPATIBILITY_VERSION,
        "current_output_schema_version": OUTPUT_SCHEMA_VERSION,
        "supported_output_schema_versions": SUPPORTED_OUTPUT_SCHEMA_VERSIONS[:],
        "command": command,
        "stable_fields": sorted(output_schema.keys()),
        "output_schema": output_schema,
        "legacy_findings_array_supported": command == "review",
        "command_schema": schema_for_command(command),
    }


def schema_contract_for_prompt(command: str) -> str:
    contract = {
        "response_wrapper": COMMON_RESPONSE_WRAPPER,
        "schema_contract": schema_contract(command),
    }
    return json.dumps(contract, ensure_ascii=False, indent=2)


def schema_text(command: str) -> str:
    return schema_contract_for_prompt(command)


def _payload_schema_version(payload: Any) -> str:
    if isinstance(payload, dict):
        return str(payload.get("schema_version") or "")
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict) and item.get("schema_version"):
                return str(item.get("schema_version"))
    return ""


def output_schema_diagnostics(payload: Any, command: str) -> Dict[str, Any]:
    payload_version = _payload_schema_version(payload)
    command_match = True
    status = "current"
    reason = "current"
    compatible = True

    if isinstance(payload, dict):
        payload_command = str(payload.get("command") or command)
        command_match = payload_command == command
        if not command_match:
            status = "command_mismatch"
            reason = "command_mismatch"
            compatible = False
        elif not payload_version:
            status = "legacy_missing_schema_version"
            reason = "legacy_missing_schema_version"
        elif payload_version not in SUPPORTED_OUTPUT_SCHEMA_VERSIONS:
            status = "unsupported_schema_version"
            reason = "unsupported_schema_version"
            compatible = False
        else:
            status = "current"
            reason = "current"
    elif isinstance(payload, list):
        status = "finding_array"
        reason = "legacy_review_findings_array" if command == "review" else "legacy_command_array"
        if payload_version and payload_version not in {FINDING_SCHEMA_VERSION, OUTPUT_SCHEMA_VERSION}:
            status = "unsupported_schema_version"
            reason = "unsupported_schema_version"
            compatible = False
    else:
        status = "invalid_payload_type"
        reason = "invalid_payload_type"
        compatible = False

    return {
        "schema_compatibility": SCHEMA_COMPATIBILITY_VERSION,
        "current_output_schema_version": OUTPUT_SCHEMA_VERSION,
        "supported_output_schema_versions": SUPPORTED_OUTPUT_SCHEMA_VERSIONS[:],
        "payload_schema_status": status,
        "payload_schema_version": payload_version,
        "command": command,
        "command_match": command_match,
        "compatible": compatible,
        "reason": reason,
    }
