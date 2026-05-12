import copy
import json
from typing import Any, Dict


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


def schema_for_command(command: str) -> Dict[str, Any]:
    return copy.deepcopy(COMMAND_SCHEMAS.get(command, COMMAND_SCHEMAS["review"]))


def schema_contract_for_prompt(command: str) -> str:
    contract = {
        "response_wrapper": COMMON_RESPONSE_WRAPPER,
        "command_schema": schema_for_command(command),
    }
    return json.dumps(contract, ensure_ascii=False, indent=2)
