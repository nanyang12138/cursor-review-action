import re
from typing import Any, Dict


DEFAULT_LANGUAGE = "zh-CN"
LOCALIZATION_SCHEMA_VERSION = "localization/v1"
MAX_LANGUAGE_LENGTH = 40
_SAFE_LANGUAGE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_. -]{0,39}$")


def normalize_language(value: Any) -> Dict[str, Any]:
    requested = str(value or "").strip()
    normalized = requested.replace("_", "-")
    reason = "configured_language"

    if not normalized:
        normalized = DEFAULT_LANGUAGE
        reason = "empty_language_defaulted"
    elif len(normalized) > MAX_LANGUAGE_LENGTH:
        normalized = DEFAULT_LANGUAGE
        reason = "language_too_long_defaulted"
    elif "\n" in normalized or "\r" in normalized:
        normalized = DEFAULT_LANGUAGE
        reason = "multiline_language_defaulted"
    elif not _SAFE_LANGUAGE_RE.fullmatch(normalized):
        normalized = DEFAULT_LANGUAGE
        reason = "unsafe_language_defaulted"

    return {
        "schema_version": LOCALIZATION_SCHEMA_VERSION,
        "requested_language": requested,
        "effective_language": normalized,
        "fallback_used": normalized != requested,
        "reason": reason,
    }


def language_instruction(language: Any) -> str:
    effective = normalize_language(language)["effective_language"]
    return (
        f"Write all human-readable prose in {effective}. "
        "Do not translate JSON field names, diagnostic keys, schema_version values, "
        "XML-style response tags, file paths, or code identifiers."
    )
