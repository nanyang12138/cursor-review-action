import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .localization import normalize_language


CONFIG_SCHEMA_VERSION = "config/v1"

DEFAULTS: Dict[str, Any] = {
    "command": "review",
    "enabled_commands": "review",
    "config_path": ".cursor-review.yml",
    "model": "auto",
    "language": "zh-CN",
    "review_focus": "correctness,security,performance,tests,edge-cases",
    "max_findings": 5,
    "max_diff_bytes": 120000,
    "max_files": 0,
    "max_hunks": 0,
    "max_cursor_calls": 1,
    "timeout_seconds": 600,
    "filter_mode": "added",
    "pr_title": "",
    "pr_body": "",
    "base_ref": "",
    "head_ref": "",
    "pr_is_fork": "",
    "comment_author_association": "",
    "trusted_author_associations": "OWNER,MEMBER,COLLABORATOR",
    "commit_messages": "",
    "include_patterns": "",
    "exclude_patterns": "",
    "skip_generated_files": True,
    "scope_mode": "full",
    "scope_files": "",
    "guidance_enabled": True,
    "guidance_files": {
        "general": ".cursor-review-instructions.md",
        "improve": "best_practices.md",
    },
    "guidance_max_bytes": 20000,
    "guidance_max_lines": 400,
    "debug_artifacts": False,
    "fail_on_error": False,
    "fail_on_findings": False,
    "trigger_phrase": "/cursor-review",
}

KNOWN_CONFIG_KEYS = set(DEFAULTS) | {
    "persistent_comment",
    "comment_mode",
    "review",
    "ask",
    "improve",
    "describe",
}

INT_SETTINGS: Dict[str, Tuple[int, int]] = {
    "max_findings": (DEFAULTS["max_findings"], 0),
    "max_diff_bytes": (DEFAULTS["max_diff_bytes"], 0),
    "max_files": (DEFAULTS["max_files"], 0),
    "max_hunks": (DEFAULTS["max_hunks"], 0),
    "max_cursor_calls": (DEFAULTS["max_cursor_calls"], 1),
    "timeout_seconds": (DEFAULTS["timeout_seconds"], 1),
    "guidance_max_bytes": (DEFAULTS["guidance_max_bytes"], 0),
    "guidance_max_lines": (DEFAULTS["guidance_max_lines"], 0),
}

BOOL_SETTINGS = {"guidance_enabled", "debug_artifacts", "fail_on_error", "fail_on_findings", "skip_generated_files"}
SUPPORTED_FILTER_MODES = {"added", "diff_context", "file"}
SAFE_DIAGNOSTIC_VALUE_RE = re.compile(r"^[A-Za-z0-9 ._/@:+,*?=|-]{0,80}$")


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def to_int(value: Any, default: int) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _safe_value_preview(value: Any) -> str:
    raw = str(value)
    if SAFE_DIAGNOSTIC_VALUE_RE.fullmatch(raw):
        return raw
    return "<redacted>"


def empty_config_diagnostics(path: Path) -> Dict[str, Any]:
    return {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "path": str(path),
        "loaded": False,
        "unknown_keys": [],
        "invalid_values": [],
        "warnings": [],
        "fallback_count": 0,
        "unknown_key_count": 0,
    }


def _add_config_warning(diagnostics: Dict[str, Any], warning: str) -> None:
    diagnostics.setdefault("warnings", []).append(warning)


def load_repo_config(path: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    diagnostics = empty_config_diagnostics(path)
    if not path.exists():
        return {}, diagnostics

    diagnostics["loaded"] = True
    loaded = load_simple_yaml(path)
    config: Dict[str, Any] = {}
    for key, value in loaded.items():
        if key in KNOWN_CONFIG_KEYS:
            config[key] = value
            continue
        diagnostics["unknown_keys"].append({"key": key, "action": "ignored"})
        _add_config_warning(diagnostics, f"Unknown config key `{key}` was ignored.")
    diagnostics["unknown_key_count"] = len(diagnostics["unknown_keys"])
    return config, diagnostics


def _normalize_int_setting(settings: Dict[str, Any], diagnostics: Dict[str, Any], key: str) -> None:
    default, minimum = INT_SETTINGS[key]
    raw = settings.get(key)
    try:
        if isinstance(raw, bool):
            raise ValueError("bool is not an integer setting")
        parsed = int(str(raw).strip())
    except Exception:
        settings[key] = default
        diagnostics["invalid_values"].append(
            {
                "key": key,
                "value": _safe_value_preview(raw),
                "reason": "invalid_integer",
                "fallback": default,
            }
        )
        _add_config_warning(diagnostics, f"Config `{key}` expected an integer; using `{default}`.")
        return

    if parsed < minimum:
        settings[key] = minimum
        diagnostics["invalid_values"].append(
            {
                "key": key,
                "value": _safe_value_preview(raw),
                "reason": "below_minimum",
                "fallback": minimum,
            }
        )
        _add_config_warning(diagnostics, f"Config `{key}` was below `{minimum}`; using `{minimum}`.")
        return

    settings[key] = parsed


def _normalize_bool_setting(settings: Dict[str, Any], diagnostics: Dict[str, Any], key: str) -> None:
    raw = settings.get(key)
    if isinstance(raw, bool):
        settings[key] = raw
        return
    normalized = str(raw).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        settings[key] = True
        return
    if normalized in {"0", "false", "no", "n", "off"}:
        settings[key] = False
        return

    fallback = bool(DEFAULTS.get(key, False))
    settings[key] = fallback
    diagnostics["invalid_values"].append(
        {
            "key": key,
            "value": _safe_value_preview(raw),
            "reason": "invalid_boolean",
            "fallback": fallback,
        }
    )
    _add_config_warning(diagnostics, f"Config `{key}` expected a boolean; using `{str(fallback).lower()}`.")


def normalize_settings(settings: Dict[str, Any], diagnostics: Dict[str, Any]) -> None:
    for key in INT_SETTINGS:
        _normalize_int_setting(settings, diagnostics, key)
    for key in BOOL_SETTINGS:
        _normalize_bool_setting(settings, diagnostics, key)

    filter_mode = str(settings.get("filter_mode", DEFAULTS["filter_mode"]) or "").strip().lower()
    if filter_mode not in SUPPORTED_FILTER_MODES:
        fallback = DEFAULTS["filter_mode"]
        diagnostics["invalid_values"].append(
            {
                "key": "filter_mode",
                "value": _safe_value_preview(settings.get("filter_mode")),
                "reason": "unsupported_value",
                "fallback": fallback,
            }
        )
        _add_config_warning(diagnostics, f"Config `filter_mode` is unsupported; using `{fallback}`.")
        settings["filter_mode"] = fallback
    else:
        settings["filter_mode"] = filter_mode

    diagnostics["fallback_count"] = len(diagnostics["invalid_values"])


def split_csv(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def normalize_key(key: str) -> str:
    return key.strip().replace("-", "_")


def parse_scalar(value: str) -> Any:
    raw = value.strip()
    if not raw:
        return ""
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(part) for part in inner.split(",")]
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        return raw[1:-1]
    lower = raw.lower()
    if lower in {"true", "false"}:
        return lower == "true"
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    return raw


def _clean_config_line(line: str) -> str:
    return line.split("#", 1)[0].rstrip()


def load_simple_yaml(path: Path) -> Dict[str, Any]:
    """Load a deliberately small YAML subset: scalars, lists, and one-level maps."""
    if not path.exists():
        return {}

    config: Dict[str, Any] = {}
    lines = [_clean_config_line(line) for line in path.read_text(encoding="utf-8", errors="replace").splitlines()]
    index = 0

    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line.startswith((" ", "\t")):
            index += 1
            continue

        if ":" not in line:
            index += 1
            continue
        key, value = line.split(":", 1)
        key = normalize_key(key)
        if value.strip():
            config[key] = parse_scalar(value)
            index += 1
            continue

        nested_lines: List[str] = []
        index += 1
        while index < len(lines):
            nested_line = lines[index]
            if not nested_line.strip():
                index += 1
                continue
            if not nested_line.startswith((" ", "\t")):
                break
            nested_lines.append(nested_line.strip())
            index += 1

        if not nested_lines:
            config[key] = []
        elif all(item.startswith("- ") for item in nested_lines):
            config[key] = [parse_scalar(item[2:]) for item in nested_lines]
        else:
            nested_map: Dict[str, Any] = {}
            for item in nested_lines:
                if ":" not in item:
                    continue
                nested_key, nested_value = item.split(":", 1)
                nested_map[normalize_key(nested_key)] = parse_scalar(nested_value)
            config[key] = nested_map

    return config


def load_settings() -> Dict[str, Any]:
    settings = DEFAULTS.copy()

    input_map = {
        "base_sha": env("INPUT_BASE_SHA"),
        "head_sha": env("INPUT_HEAD_SHA"),
        "pr_number": env("INPUT_PR_NUMBER"),
        "pr_title": env("INPUT_PR_TITLE"),
        "pr_body": env("INPUT_PR_BODY"),
        "base_ref": env("INPUT_BASE_REF"),
        "head_ref": env("INPUT_HEAD_REF"),
        "pr_is_fork": env("INPUT_PR_IS_FORK"),
        "comment_author_association": env("INPUT_COMMENT_AUTHOR_ASSOCIATION"),
        "trusted_author_associations": env(
            "INPUT_TRUSTED_AUTHOR_ASSOCIATIONS", DEFAULTS["trusted_author_associations"]
        ),
        "commit_messages": env("INPUT_COMMIT_MESSAGES"),
        "event_name": env("INPUT_EVENT_NAME"),
        "comment_body": env("INPUT_COMMENT_BODY"),
        "user_prompt": env("INPUT_USER_PROMPT"),
        "trigger_phrase": env("INPUT_TRIGGER_PHRASE", DEFAULTS["trigger_phrase"]),
        "command": env("INPUT_COMMAND", DEFAULTS["command"]),
        "enabled_commands": env("INPUT_ENABLED_COMMANDS", DEFAULTS["enabled_commands"]),
        "config_path": env("INPUT_CONFIG_PATH", DEFAULTS["config_path"]),
        "model": env("INPUT_MODEL", DEFAULTS["model"]),
        "language": env("INPUT_LANGUAGE", DEFAULTS["language"]),
        "review_focus": env("INPUT_REVIEW_FOCUS", DEFAULTS["review_focus"]),
        "max_findings": env("INPUT_MAX_FINDINGS", str(DEFAULTS["max_findings"])),
        "max_diff_bytes": env("INPUT_MAX_DIFF_BYTES", str(DEFAULTS["max_diff_bytes"])),
        "max_files": env("INPUT_MAX_FILES", str(DEFAULTS["max_files"])),
        "max_hunks": env("INPUT_MAX_HUNKS", str(DEFAULTS["max_hunks"])),
        "max_cursor_calls": env("INPUT_MAX_CURSOR_CALLS", str(DEFAULTS["max_cursor_calls"])),
        "timeout_seconds": env("INPUT_TIMEOUT_SECONDS", str(DEFAULTS["timeout_seconds"])),
        "filter_mode": env("INPUT_FILTER_MODE", DEFAULTS["filter_mode"]),
        "include_patterns": env("INPUT_INCLUDE_PATTERNS", ""),
        "exclude_patterns": env("INPUT_EXCLUDE_PATTERNS", ""),
        "skip_generated_files": DEFAULTS["skip_generated_files"],
        "scope_mode": env("INPUT_SCOPE_MODE", DEFAULTS["scope_mode"]),
        "scope_files": env("INPUT_SCOPE_FILES", DEFAULTS["scope_files"]),
        "debug_artifacts": env("INPUT_DEBUG_ARTIFACTS", "false"),
        "fail_on_error": env("INPUT_FAIL_ON_ERROR", "false"),
        "fail_on_findings": env("INPUT_FAIL_ON_FINDINGS", "false"),
    }
    settings.update({key: value for key, value in input_map.items() if value != ""})

    config_path = Path(str(settings["config_path"]))
    repo_config, config_diagnostics = load_repo_config(config_path)
    settings.update(repo_config)

    normalize_settings(settings, config_diagnostics)
    language_diagnostics = normalize_language(settings.get("language"))
    settings["language"] = language_diagnostics["effective_language"]
    settings["language_diagnostics"] = language_diagnostics
    settings["cursor_api_key_present"] = bool(env("CURSOR_API_KEY").strip())
    settings["config_loaded"] = str(config_path if config_path.exists() else "")
    settings["config_diagnostics"] = config_diagnostics
    return settings
