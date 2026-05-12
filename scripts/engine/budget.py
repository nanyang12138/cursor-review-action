from typing import Any, Dict

from .config import DEFAULTS, to_int


def non_negative_budget(settings: Dict[str, Any], key: str) -> int:
    value = to_int(settings.get(key), int(DEFAULTS.get(key, 0)))
    return max(value, 0)


def positive_budget(settings: Dict[str, Any], key: str) -> int:
    value = to_int(settings.get(key), int(DEFAULTS.get(key, 1)))
    if value < 1:
        return int(DEFAULTS.get(key, 1))
    return value


def normalized_budget_settings(settings: Dict[str, Any]) -> Dict[str, int]:
    return {
        "max_diff_bytes": non_negative_budget(settings, "max_diff_bytes"),
        "max_files": non_negative_budget(settings, "max_files"),
        "max_hunks": non_negative_budget(settings, "max_hunks"),
        "max_cursor_calls": positive_budget(settings, "max_cursor_calls"),
        "timeout_seconds": positive_budget(settings, "timeout_seconds"),
    }
