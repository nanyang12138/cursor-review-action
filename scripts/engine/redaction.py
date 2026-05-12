import os
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


REDACTION_SCHEMA_VERSION = "redaction/v1"
REDACTION_PLACEHOLDER = "[REDACTED]"

_SECRET_ENV_MARKERS = ("TOKEN", "KEY", "SECRET", "PASSWORD", "CREDENTIAL", "AUTH")

_FULL_VALUE_PATTERNS: Sequence[re.Pattern[str]] = (
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bnpm_[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bpypi-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bhf_[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    re.compile(r"\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b"),
)

_GROUP_VALUE_PATTERNS: Sequence[tuple[re.Pattern[str], int]] = (
    (
        re.compile(r"(?i)\b(authorization\s*:\s*bearer\s+)([A-Za-z0-9._~+/=-]{8,})"),
        2,
    ),
    (
        re.compile(
            r"(?i)\b((?:api[_-]?key|token|secret|password|cursor[_-]?api[_-]?key|github[_-]?token)\s*[:=]\s*)([^\s`'\"<>]{4,})"
        ),
        2,
    ),
)


@dataclass(frozen=True)
class RedactionResult:
    text: str
    redacted_count: int
    secret_value_count: int = 0
    pattern_count: int = 0
    schema_version: str = REDACTION_SCHEMA_VERSION

    @property
    def status(self) -> str:
        return "applied" if self.redacted_count else "none"


def _is_secret_env_name(name: str) -> bool:
    upper = name.upper()
    return any(marker in upper for marker in _SECRET_ENV_MARKERS)


def _secret_values(env: Mapping[str, str]) -> list[str]:
    values = {
        value
        for key, value in env.items()
        if _is_secret_env_name(str(key)) and isinstance(value, str) and len(value) >= 4 and value.lower() not in {"true", "false", "none", "null"}
    }
    return sorted(values, key=len, reverse=True)


def _replace_group(text: str, pattern: re.Pattern[str], group_index: int, replacement: str) -> tuple[str, int]:
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        group_start, group_end = match.span(group_index)
        match_start, match_end = match.span(0)
        return (
            match.string[match_start:group_start]
            + replacement
            + match.string[group_end:match_end]
        )

    return pattern.sub(repl, text), count


def redact_text(value: Any, env: Mapping[str, str] | None = None, replacement: str = REDACTION_PLACEHOLDER) -> RedactionResult:
    text = "" if value is None else str(value)
    redacted = text
    secret_value_count = 0
    pattern_count = 0

    for secret in _secret_values(env or os.environ):
        redacted, count = re.subn(re.escape(secret), replacement, redacted)
        secret_value_count += count

    for pattern in _FULL_VALUE_PATTERNS:
        redacted, count = pattern.subn(replacement, redacted)
        pattern_count += count

    for pattern, group_index in _GROUP_VALUE_PATTERNS:
        redacted, count = _replace_group(redacted, pattern, group_index, replacement)
        pattern_count += count

    return RedactionResult(
        text=redacted,
        redacted_count=secret_value_count + pattern_count,
        secret_value_count=secret_value_count,
        pattern_count=pattern_count,
    )


def combine_results(results: Iterable[RedactionResult]) -> RedactionResult:
    result_list = list(results)
    return RedactionResult(
        text="",
        redacted_count=sum(result.redacted_count for result in result_list),
        secret_value_count=sum(result.secret_value_count for result in result_list),
        pattern_count=sum(result.pattern_count for result in result_list),
    )


def privacy_diagnostics(settings: Mapping[str, Any], result: RedactionResult) -> dict[str, Any]:
    return {
        "schema_version": REDACTION_SCHEMA_VERSION,
        "redaction_status": result.status,
        "redacted_count": result.redacted_count,
        "secret_value_count": result.secret_value_count,
        "pattern_count": result.pattern_count,
        "debug_artifacts_enabled": bool(settings.get("debug_artifacts")),
        "cursor_data": "selected_diff_pr_metadata_user_prompt_repo_guidance",
        "actions_log_policy": "redacted_summary_outputs_no_raw_prompt_or_diff_by_default",
        "pr_comment_policy": "redacted_markdown_and_compact_diagnostics",
    }
