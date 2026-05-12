import os
import re
from pathlib import Path
from typing import Any, Dict, List


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
    "scope_mode": "full",
    "scope_files": "",
    "guidance_enabled": True,
    "guidance_files": {
        "general": ".cursor-review-instructions.md",
        "improve": "best_practices.md",
    },
    "guidance_max_bytes": 20000,
    "guidance_max_lines": 400,
    "fail_on_error": False,
    "fail_on_findings": False,
    "trigger_phrase": "/cursor-review",
}


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
        "scope_mode": env("INPUT_SCOPE_MODE", DEFAULTS["scope_mode"]),
        "scope_files": env("INPUT_SCOPE_FILES", DEFAULTS["scope_files"]),
        "fail_on_error": env("INPUT_FAIL_ON_ERROR", "false"),
        "fail_on_findings": env("INPUT_FAIL_ON_FINDINGS", "false"),
    }
    settings.update({key: value for key, value in input_map.items() if value != ""})

    config_path = Path(str(settings["config_path"]))
    repo_config = load_simple_yaml(config_path)
    settings.update(repo_config)

    settings["max_findings"] = to_int(settings.get("max_findings"), DEFAULTS["max_findings"])
    settings["max_diff_bytes"] = max(to_int(settings.get("max_diff_bytes"), DEFAULTS["max_diff_bytes"]), 0)
    settings["max_files"] = max(to_int(settings.get("max_files"), DEFAULTS["max_files"]), 0)
    settings["max_hunks"] = max(to_int(settings.get("max_hunks"), DEFAULTS["max_hunks"]), 0)
    settings["max_cursor_calls"] = max(to_int(settings.get("max_cursor_calls"), DEFAULTS["max_cursor_calls"]), 1)
    settings["timeout_seconds"] = max(to_int(settings.get("timeout_seconds"), DEFAULTS["timeout_seconds"]), 1)
    settings["guidance_enabled"] = to_bool(settings.get("guidance_enabled"))
    settings["guidance_max_bytes"] = max(to_int(settings.get("guidance_max_bytes"), DEFAULTS["guidance_max_bytes"]), 0)
    settings["guidance_max_lines"] = max(to_int(settings.get("guidance_max_lines"), DEFAULTS["guidance_max_lines"]), 0)
    settings["fail_on_error"] = to_bool(settings.get("fail_on_error"))
    settings["fail_on_findings"] = to_bool(settings.get("fail_on_findings"))
    settings["cursor_api_key_present"] = bool(env("CURSOR_API_KEY").strip())
    settings["config_loaded"] = str(config_path if config_path.exists() else "")
    return settings
