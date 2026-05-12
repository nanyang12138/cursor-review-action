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
    "timeout_seconds": 600,
    "filter_mode": "added",
    "include_patterns": "",
    "exclude_patterns": "",
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


def load_simple_yaml(path: Path) -> Dict[str, Any]:
    """Load a deliberately small YAML subset: key: value plus simple lists."""
    if not path.exists():
        return {}

    config: Dict[str, Any] = {}
    current_key = None
    current_list: List[str] = []

    for original_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = original_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue

        if current_key and line.lstrip().startswith("- "):
            current_list.append(parse_scalar(line.lstrip()[2:]))
            continue
        if current_key:
            config[current_key] = current_list
            current_key = None
            current_list = []

        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = normalize_key(key)
        if value.strip() == "":
            current_key = key
            current_list = []
        else:
            config[key] = parse_scalar(value)

    if current_key:
        config[current_key] = current_list

    return config


def load_settings() -> Dict[str, Any]:
    settings = DEFAULTS.copy()

    input_map = {
        "base_sha": env("INPUT_BASE_SHA"),
        "head_sha": env("INPUT_HEAD_SHA"),
        "pr_number": env("INPUT_PR_NUMBER"),
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
        "timeout_seconds": env("INPUT_TIMEOUT_SECONDS", str(DEFAULTS["timeout_seconds"])),
        "filter_mode": env("INPUT_FILTER_MODE", DEFAULTS["filter_mode"]),
        "include_patterns": env("INPUT_INCLUDE_PATTERNS", ""),
        "exclude_patterns": env("INPUT_EXCLUDE_PATTERNS", ""),
        "fail_on_error": env("INPUT_FAIL_ON_ERROR", "false"),
        "fail_on_findings": env("INPUT_FAIL_ON_FINDINGS", "false"),
    }
    settings.update({key: value for key, value in input_map.items() if value != ""})

    config_path = Path(str(settings["config_path"]))
    repo_config = load_simple_yaml(config_path)
    settings.update(repo_config)

    settings["max_findings"] = to_int(settings.get("max_findings"), DEFAULTS["max_findings"])
    settings["max_diff_bytes"] = to_int(settings.get("max_diff_bytes"), DEFAULTS["max_diff_bytes"])
    settings["timeout_seconds"] = to_int(settings.get("timeout_seconds"), DEFAULTS["timeout_seconds"])
    settings["fail_on_error"] = to_bool(settings.get("fail_on_error"))
    settings["fail_on_findings"] = to_bool(settings.get("fail_on_findings"))
    settings["config_loaded"] = str(config_path if config_path.exists() else "")
    return settings
