from dataclasses import dataclass
from typing import Any, Dict, List

from .diff_selector import build_diff
from .guidance import load_repo_guidance
from .metadata_cache import resolve_metadata_cache


@dataclass
class ReviewContext:
    diff_text: str
    stat: str
    truncated: bool
    meta: Dict[str, Any]


def _clean_text(value: Any) -> str:
    return str(value or "").replace("\r\n", "\n").strip()


def _commit_messages(value: Any) -> List[str]:
    if isinstance(value, list):
        return [_clean_text(item) for item in value if _clean_text(item)]
    text = _clean_text(value)
    if not text:
        return []
    return [line.strip() for line in text.splitlines() if line.strip()]


def build_pull_request_context(settings: Dict[str, Any], stat: str, diff_meta: Dict[str, Any]) -> Dict[str, Any]:
    files = [str(item) for item in diff_meta.get("files", [])]
    guidance_diagnostics = (diff_meta.get("repo_guidance") or {}).get("diagnostics") or {}
    return {
        "pr_number": _clean_text(settings.get("pr_number")),
        "title": _clean_text(settings.get("pr_title")),
        "body": _clean_text(settings.get("pr_body")),
        "base_ref": _clean_text(settings.get("base_ref")),
        "head_ref": _clean_text(settings.get("head_ref")),
        "base_sha": _clean_text(diff_meta.get("base") or settings.get("base_sha")),
        "head_sha": _clean_text(diff_meta.get("head") or settings.get("head_sha")),
        "event_name": _clean_text(settings.get("event_name")),
        "resolved_command": _clean_text(settings.get("resolved_command") or settings.get("command")),
        "comment_prompt": _clean_text(settings.get("resolved_user_prompt")),
        "commit_messages": _commit_messages(settings.get("commit_messages")),
        "changed_files": files,
        "diff_stat": _clean_text(stat),
        "repo_config": {
            "config_loaded": _clean_text(settings.get("config_loaded")),
            "guidance_enabled": guidance_diagnostics.get("enabled", False),
            "guidance_loaded_files": [
                item.get("path") for item in guidance_diagnostics.get("loaded", []) if item.get("path")
            ],
        },
    }


def build_review_context(settings: Dict[str, Any]) -> ReviewContext:
    diff_text, stat, truncated, meta = build_diff(settings)
    meta = dict(meta)
    command = _clean_text(settings.get("resolved_command") or settings.get("command") or "review")
    meta["repo_guidance"] = load_repo_guidance(settings, command)
    metadata_cache = resolve_metadata_cache(settings, command)
    meta["metadata_cache"] = metadata_cache["diagnostics"]
    if metadata_cache.get("content"):
        meta["describe_metadata"] = metadata_cache["content"]
    meta["pull_request_context"] = build_pull_request_context(settings, stat, meta)
    return ReviewContext(diff_text=diff_text, stat=stat, truncated=truncated, meta=meta)
