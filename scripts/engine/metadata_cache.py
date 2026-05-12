import json
import re
from typing import Any, Dict, Mapping, Tuple

from .redaction import redact_text
from .run_state import normalize_command_name
from .schemas import OUTPUT_SCHEMA_VERSION


METADATA_CACHE_SCHEMA_VERSION = "metadata-cache/v1"
METADATA_CACHE_MARKER_PREFIX = "<!-- cursor-review-action-metadata-cache:"
METADATA_CACHE_MARKER_RE = re.compile(
    r"<!--\s*cursor-review-action-metadata-cache:(.*?)\s*-->",
    re.DOTALL,
)
DEFAULT_METADATA_CACHE_MAX_BYTES = 10000
DESCRIBE_CONTENT_FIELDS = ("summary", "walkthrough", "risks", "tests", "changelog")


def _enabled(settings: Mapping[str, Any]) -> bool:
    value = settings.get("metadata_cache_enabled", True)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "n", "off"}


def _max_bytes(settings: Mapping[str, Any]) -> int:
    try:
        parsed = int(str(settings.get("metadata_cache_max_bytes", DEFAULT_METADATA_CACHE_MAX_BYTES)).strip())
    except Exception:
        return DEFAULT_METADATA_CACHE_MAX_BYTES
    return max(0, parsed)


def _current_head_sha(settings: Mapping[str, Any]) -> str:
    run_state = settings.get("run_state") or {}
    return str(settings.get("head_sha") or run_state.get("head_sha") or "").strip()


def _diagnostics(status: str, reason: str, settings: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    settings = settings or {}
    return {
        "schema_version": METADATA_CACHE_SCHEMA_VERSION,
        "enabled": _enabled(settings),
        "status": status,
        "reason": reason,
        "source": "none",
        "head_sha": _current_head_sha(settings),
        "cache_head_sha": "",
        "head_sha_match": False,
        "output_schema_version": "",
        "cached_command": "",
        "bytes": 0,
        "redacted_count": 0,
    }


def _clean_text(value: Any, limit: int = 2000) -> str:
    redacted = redact_text(value)
    text = redacted.text.replace("\r\n", "\n").strip()
    if len(text) > limit:
        return text[:limit].rstrip() + "..."
    return text


def _clean_list(value: Any) -> list[str]:
    if isinstance(value, list):
        items = value
    elif value:
        items = [value]
    else:
        items = []
    return [_clean_text(item, 800) for item in items[:20] if _clean_text(item, 800)]


def _describe_content(payload: Mapping[str, Any]) -> Dict[str, Any]:
    content: Dict[str, Any] = {}
    for field in DESCRIBE_CONTENT_FIELDS:
        value = payload.get(field)
        if field in {"walkthrough", "risks", "tests"}:
            cleaned_list = _clean_list(value)
            if cleaned_list:
                content[field] = cleaned_list
        else:
            cleaned_text = _clean_text(value)
            if cleaned_text:
                content[field] = cleaned_text
    return content


def _compact_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")).replace("--", "- -")


def metadata_cache_comment(payload: Mapping[str, Any]) -> str:
    return f"{METADATA_CACHE_MARKER_PREFIX}{_compact_json(payload)} -->"


def extract_metadata_cache_marker(comment_body: Any) -> str:
    match = METADATA_CACHE_MARKER_RE.search(str(comment_body or ""))
    return match.group(0) if match else ""


def _loads_marker(raw_comment_or_marker: Any) -> Tuple[Dict[str, Any], str]:
    marker = extract_metadata_cache_marker(raw_comment_or_marker) or str(raw_comment_or_marker or "").strip()
    if not marker:
        return {}, "missing"
    match = METADATA_CACHE_MARKER_RE.search(marker)
    raw_payload = match.group(1) if match else marker
    try:
        payload = json.loads(raw_payload)
    except Exception:
        return {}, "invalid_json"
    if not isinstance(payload, dict):
        return {}, "invalid_payload_type"
    return payload, ""


def build_describe_metadata_cache_comment(
    command: Any,
    findings_json: str,
    settings: Mapping[str, Any],
    quality_gate: Mapping[str, Any] | None = None,
) -> Tuple[str, Dict[str, Any]]:
    """Build hidden describe metadata for METADATA-CACHE-P1.

    The marker is safe to publish inside the bot's own describe comment. It stores
    only redacted structured describe output, never raw prompt or raw diff.
    """
    diagnostics = _diagnostics("not_applicable", "consumer_or_non_describe_command", settings)
    diagnostics["source"] = "generated"
    if not _enabled(settings):
        diagnostics.update({"status": "disabled", "reason": "metadata_cache_disabled"})
        return "", diagnostics
    if normalize_command_name(command) != "describe":
        return "", diagnostics
    if (quality_gate or {}).get("publish_decision") == "fail_before_publish":
        diagnostics.update({"status": "suppressed", "reason": "quality_gate_blocked"})
        return "", diagnostics

    try:
        payload = json.loads(findings_json or "{}")
    except Exception:
        diagnostics.update({"status": "invalid", "reason": "describe_output_not_json"})
        return "", diagnostics
    if not isinstance(payload, dict):
        diagnostics.update({"status": "invalid", "reason": "describe_output_not_object"})
        return "", diagnostics
    if payload.get("command") != "describe":
        diagnostics.update({"status": "invalid", "reason": "describe_command_mismatch"})
        return "", diagnostics
    if payload.get("schema_version") != OUTPUT_SCHEMA_VERSION:
        diagnostics.update({"status": "invalid", "reason": "unsupported_output_schema"})
        diagnostics["output_schema_version"] = str(payload.get("schema_version") or "")
        return "", diagnostics

    head_sha = _current_head_sha(settings)
    if not head_sha:
        diagnostics.update({"status": "suppressed", "reason": "missing_head_sha"})
        return "", diagnostics

    content = _describe_content(payload)
    if not content:
        diagnostics.update({"status": "empty", "reason": "no_cacheable_describe_content"})
        return "", diagnostics

    redaction = redact_text(json.dumps(content, ensure_ascii=False))
    cache_payload = {
        "schema_version": METADATA_CACHE_SCHEMA_VERSION,
        "source_command": "describe",
        "head_sha": head_sha,
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "prompt_template_version": str(settings.get("prompt_template_version") or ""),
        "generated_at": str((settings.get("run_state") or {}).get("generated_at") or ""),
        "content": json.loads(redaction.text),
    }
    comment = metadata_cache_comment(cache_payload)
    max_bytes = _max_bytes(settings)
    diagnostics.update(
        {
            "status": "valid",
            "reason": "metadata_cache_generated",
            "cache_head_sha": cache_payload["head_sha"],
            "head_sha_match": bool(cache_payload["head_sha"]),
            "output_schema_version": OUTPUT_SCHEMA_VERSION,
            "cached_command": "describe",
            "bytes": len(comment.encode("utf-8")),
            "redacted_count": redaction.redacted_count,
        }
    )
    if max_bytes and diagnostics["bytes"] > max_bytes:
        diagnostics.update({"status": "too_large", "reason": "metadata_cache_exceeds_budget"})
        return "", diagnostics
    return comment, diagnostics


def resolve_metadata_cache(settings: Mapping[str, Any], command: Any) -> Dict[str, Any]:
    diagnostics = _diagnostics("missing", "no_metadata_cache_comment", settings)
    if not _enabled(settings):
        diagnostics.update({"status": "disabled", "reason": "metadata_cache_disabled"})
        return {"content": {}, "diagnostics": diagnostics}

    normalized_command = normalize_command_name(command)
    if normalized_command not in {"review", "improve"}:
        diagnostics.update({"status": "not_applicable", "reason": "consumer_command_not_supported"})
        return {"content": {}, "diagnostics": diagnostics}

    raw_comment = settings.get("metadata_cache_comment") or ""
    if not raw_comment:
        return {"content": {}, "diagnostics": diagnostics}
    diagnostics["source"] = "comment_marker"
    diagnostics["bytes"] = len(str(raw_comment).encode("utf-8"))
    max_bytes = _max_bytes(settings)
    if max_bytes and diagnostics["bytes"] > max_bytes:
        diagnostics.update({"status": "invalid", "reason": "metadata_cache_input_exceeds_budget"})
        return {"content": {}, "diagnostics": diagnostics}

    payload, error = _loads_marker(raw_comment)
    if error:
        diagnostics.update({"status": "invalid", "reason": error})
        return {"content": {}, "diagnostics": diagnostics}

    diagnostics["cache_head_sha"] = str(payload.get("head_sha") or "")
    diagnostics["output_schema_version"] = str(payload.get("output_schema_version") or "")
    diagnostics["cached_command"] = str(payload.get("source_command") or "")
    if payload.get("schema_version") != METADATA_CACHE_SCHEMA_VERSION:
        diagnostics.update({"status": "invalid", "reason": "unsupported_metadata_cache_schema"})
        return {"content": {}, "diagnostics": diagnostics}
    if payload.get("source_command") != "describe":
        diagnostics.update({"status": "invalid", "reason": "source_command_not_describe"})
        return {"content": {}, "diagnostics": diagnostics}
    if payload.get("output_schema_version") != OUTPUT_SCHEMA_VERSION:
        diagnostics.update({"status": "invalid", "reason": "unsupported_output_schema"})
        return {"content": {}, "diagnostics": diagnostics}

    current_head = _current_head_sha(settings)
    cache_head = str(payload.get("head_sha") or "")
    diagnostics["head_sha_match"] = bool(current_head and cache_head and current_head == cache_head)
    if not current_head:
        diagnostics.update({"status": "invalid", "reason": "missing_current_head_sha"})
        return {"content": {}, "diagnostics": diagnostics}
    if not cache_head or current_head != cache_head:
        diagnostics.update({"status": "stale", "reason": "head_sha_mismatch"})
        return {"content": {}, "diagnostics": diagnostics}

    content = payload.get("content") if isinstance(payload.get("content"), dict) else {}
    if not content:
        diagnostics.update({"status": "empty", "reason": "no_cacheable_describe_content"})
        return {"content": {}, "diagnostics": diagnostics}
    diagnostics.update({"status": "valid", "reason": "metadata_cache_reused"})
    return {"content": dict(content), "diagnostics": diagnostics}
