import json
from copy import deepcopy
from typing import Any, Dict


SCHEMA_VERSION = "cursor-review-action/v1"

_REVIEW_FINDING = {
    "severity": "critical|high|medium|low",
    "confidence": "high|medium|low",
    "file": "path relative to repository root, or empty string when not file-specific",
    "line": "new-side line number as integer, or null when not line-specific",
    "title": "short actionable finding title",
    "body": "why this matters and what can go wrong",
    "suggestion": "concrete fix or mitigation",
    "evidence": "brief quote or description from the selected diff/context",
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
