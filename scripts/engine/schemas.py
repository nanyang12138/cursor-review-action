from typing import Any, Dict


SCHEMA_VERSION = "cursor-review-action/v0.4"


def _base_item(kind: str) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
    }


COMMAND_OUTPUT_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "review": {
        "tag": "findings_json",
        "shape": "JSON array of review finding objects. Use [] when there are no actionable findings.",
        "item": {
            **_base_item("review_finding"),
            "severity": "critical|high|medium|low",
            "category": "bug|security|performance|tests|regression|edge_case",
            "file": "repository-relative path, or empty string when not file-specific",
            "line": "new-file line number when anchored, otherwise null",
            "line_side": "new|old|file|unknown",
            "title": "short actionable finding title",
            "body": "why this matters, grounded in selected diff or PR context",
            "confidence": "high|medium|low",
            "evidence": "brief selected-diff or PR-context evidence",
            "suggestion": "concrete fix guidance, or empty string",
            "grounding": "anchored|file_only|unanchored|invalid",
        },
    },
    "ask": {
        "tag": "findings_json",
        "shape": "JSON array with one answer object. Use [] only when the question cannot be answered from context.",
        "item": {
            **_base_item("answer"),
            "question": "user question being answered",
            "answer": "direct answer using only selected PR context",
            "evidence_refs": [
                {
                    "file": "repository-relative path, or empty string",
                    "line": "line number when available, otherwise null",
                    "quote": "short supporting excerpt from selected context",
                }
            ],
            "confidence": "high|medium|low",
            "follow_up_needed": "boolean",
        },
    },
    "improve": {
        "tag": "findings_json",
        "shape": "JSON array of improvement suggestion objects. Use [] when no safe suggestions are available.",
        "item": {
            **_base_item("improvement_suggestion"),
            "priority": "high|medium|low",
            "category": "tests|maintainability|readability|performance|docs|refactor",
            "file": "repository-relative path, or empty string when repo-wide",
            "line": "line number when relevant, otherwise null",
            "title": "short suggestion title",
            "rationale": "why the suggestion improves the PR",
            "before": "current behavior or code shape, or empty string",
            "after": "suggested behavior or code shape, or empty string",
            "confidence": "high|medium|low",
        },
    },
    "describe": {
        "tag": "findings_json",
        "shape": "JSON array with one PR description object. Do not request or imply PR body updates.",
        "item": {
            **_base_item("pr_description"),
            "summary": "concise PR summary",
            "walkthrough": ["bullet describing an important changed area"],
            "risk_level": "high|medium|low",
            "risks": ["notable review or release risk"],
            "test_plan": ["test or validation item from context, or suggested verification"],
            "changelog": "optional changelog-style sentence, or empty string",
        },
    },
}


def output_schema_for_command(command: str) -> Dict[str, Any]:
    return COMMAND_OUTPUT_SCHEMAS.get(command, COMMAND_OUTPUT_SCHEMAS["review"])
