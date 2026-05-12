from typing import Any, Dict, Tuple

from .config import split_csv


COMMAND_ALIASES = {
    "/cursor-review": "review",
    "/cursor-ask": "ask",
    "/cursor-improve": "improve",
    "/cursor-describe": "describe",
    "/cursor-help": "help",
}


def _matches_trigger(stripped: str, trigger: str) -> bool:
    return stripped == trigger or stripped.startswith(f"{trigger} ") or stripped.startswith(f"{trigger}\n")


def _help_subcommand(remainder: str) -> Tuple[bool, str]:
    if not remainder:
        return False, ""
    parts = remainder.split(None, 1)
    if parts[0].lower() != "help":
        return False, ""
    return True, parts[1].strip() if len(parts) > 1 else ""


def derive_command_and_prompt(settings: Dict[str, Any]) -> Tuple[str, str]:
    explicit_prompt = str(settings.get("user_prompt", "") or "").strip()
    comment_body = str(settings.get("comment_body", "") or "")
    command = str(settings.get("command", "review") or "review").strip().lower()

    if explicit_prompt:
        settings["command_prompt_source"] = "user_prompt"
        return command, explicit_prompt

    stripped = comment_body.strip()
    if not stripped:
        settings["command_prompt_source"] = "none"
        return command, ""

    for trigger, mapped_command in COMMAND_ALIASES.items():
        if _matches_trigger(stripped, trigger):
            remainder = stripped[len(trigger):].strip()
            settings["command_prompt_source"] = "slash_command"
            if trigger == "/cursor-review":
                is_help, help_prompt = _help_subcommand(remainder)
                if is_help:
                    return "help", help_prompt
            return mapped_command, remainder

    trigger_phrase = str(settings.get("trigger_phrase", "/cursor-review"))
    if trigger_phrase in stripped:
        settings["command_prompt_source"] = "trigger_phrase"
        return command, stripped.replace(trigger_phrase, "", 1).strip()

    settings["command_prompt_source"] = "comment_body"
    return command, stripped


def ensure_command_enabled(command: str, settings: Dict[str, Any]) -> Tuple[bool, str]:
    if command == "help":
        return True, ""
    enabled = {item.lower() for item in split_csv(settings.get("enabled_commands"))}
    if command in enabled:
        return True, ""
    return False, f"Command `{command}` is not enabled. Enabled commands: {', '.join(sorted(enabled)) or 'none'}."
