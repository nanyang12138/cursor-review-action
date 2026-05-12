import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional


COMMAND_TITLES = {
    "review": "Cursor Review",
    "ask": "Cursor Ask",
    "improve": "Cursor Improve",
    "describe": "Cursor Describe",
}


def normalize_command_name(command: Any) -> str:
    normalized = re.sub(r"[^a-z0-9_-]", "", str(command or "review").strip().lower())
    return normalized or "review"


def comment_marker(command: Any) -> str:
    return f"<!-- cursor-review-action:{normalize_command_name(command)} -->"


def comment_title(command: Any) -> str:
    normalized = normalize_command_name(command)
    return COMMAND_TITLES.get(normalized, f"Cursor {normalized.replace('-', ' ').title()}")


def _metadata_value(settings: Mapping[str, Any], key: str, env: Mapping[str, str], env_key: str = "") -> str:
    value = settings.get(key)
    if value is None or value == "":
        value = env.get(env_key or key.upper(), "")
    return str(value or "")


def _stale_status(head_sha: str, expected_head_sha: str) -> str:
    if not expected_head_sha:
        return "unknown"
    if not head_sha:
        return "unknown"
    return "current" if head_sha == expected_head_sha else "stale"


def build_run_metadata(
    settings: Mapping[str, Any],
    now: Optional[datetime] = None,
    env: Optional[Mapping[str, str]] = None,
) -> Dict[str, str]:
    env = env or os.environ
    generated_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    command = normalize_command_name(settings.get("resolved_command") or settings.get("command"))
    head_sha = _metadata_value(settings, "head_sha", env, "GITHUB_SHA")
    expected_head_sha = _metadata_value(settings, "expected_head_sha", env, "INPUT_EXPECTED_HEAD_SHA")
    pr_number = _metadata_value(settings, "pr_number", env, "INPUT_PR_NUMBER")

    metadata = {
        "schema_version": "run-state/v1",
        "generated_at": generated_at,
        "command": command,
        "command_source": str(settings.get("command_prompt_source") or "unknown"),
        "event_name": _metadata_value(settings, "event_name", env, "GITHUB_EVENT_NAME"),
        "repository": env.get("GITHUB_REPOSITORY", ""),
        "workflow": env.get("GITHUB_WORKFLOW", ""),
        "run_id": env.get("GITHUB_RUN_ID", ""),
        "run_attempt": env.get("GITHUB_RUN_ATTEMPT", ""),
        "actor": env.get("GITHUB_ACTOR", ""),
        "pr_number": pr_number,
        "base_ref": _metadata_value(settings, "base_ref", env, "INPUT_BASE_REF"),
        "head_ref": _metadata_value(settings, "head_ref", env, "INPUT_HEAD_REF"),
        "base_sha": _metadata_value(settings, "base_sha", env, "INPUT_BASE_SHA"),
        "head_sha": head_sha,
        "expected_head_sha": expected_head_sha,
        "stale_status": _stale_status(head_sha, expected_head_sha),
    }
    metadata["idempotency_key"] = ":".join(
        [
            "cursor-review-action",
            command,
            pr_number or "no-pr",
            head_sha or "unknown-head",
        ]
    )
    return metadata


def metadata_comment(metadata: Mapping[str, str]) -> str:
    compact = json.dumps(dict(metadata), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"<!-- cursor-review-action-meta:{compact.replace('--', '- -')} -->"


def run_metadata_json(metadata: Mapping[str, str]) -> str:
    return json.dumps(dict(metadata), ensure_ascii=False, sort_keys=True)


def build_run_state(settings: Mapping[str, Any]) -> Dict[str, Any]:
    command = settings.get("resolved_command") or settings.get("command")
    metadata = build_run_metadata(settings)
    return {
        "comment_marker": comment_marker(command),
        "comment_title": comment_title(command),
        "metadata": metadata,
        "metadata_comment": metadata_comment(metadata),
        "metadata_json": run_metadata_json(metadata),
    }
