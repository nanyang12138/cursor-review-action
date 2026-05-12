import json
from pathlib import Path
from typing import Any, Dict

from .config import split_csv
from .schemas import schema_text


TEMPLATE_DIR = Path(__file__).with_name("prompt_templates")


def command_instructions(command: str, user_prompt: str, settings: Dict[str, Any]) -> str:
    language = settings.get("language", "zh-CN")
    max_findings = settings.get("max_findings", 5)
    focus = ", ".join(split_csv(settings.get("review_focus")))
    template_path = TEMPLATE_DIR / f"{command}.md"
    if not template_path.exists():
        template_path = TEMPLATE_DIR / "review.md"

    extra = ""
    if user_prompt:
        extra = f"\nAdditional user instructions from PR comment:\n{user_prompt}\n"

    template = template_path.read_text(encoding="utf-8")
    replacements = {
        "{{language}}": str(language),
        "{{max_findings}}": str(max_findings),
        "{{focus}}": focus,
        "{{user_prompt_section}}": extra.rstrip(),
        "{{schema_json}}": schema_text(command),
    }
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
    return template.strip() + "\n"


def build_prompt(command: str, user_prompt: str, diff_text: str, stat: str, truncated: bool, meta: Dict[str, Any], settings: Dict[str, Any]) -> str:
    pull_request_context = meta.get("pull_request_context", {})
    diagnostics = {
        "command": command,
        "model": settings.get("model"),
        "language": settings.get("language"),
        "config_loaded": settings.get("config_loaded"),
        "command_arg_overrides": settings.get("command_arg_overrides", {}),
        "command_arg_warnings": settings.get("command_arg_warnings", []),
        "diff_truncated": truncated,
        "diff_meta": meta,
    }
    return f"""{command_instructions(command, user_prompt, settings)}

Diagnostics:
{json.dumps(diagnostics, ensure_ascii=False, indent=2)}

Pull request context:
{json.dumps(pull_request_context, ensure_ascii=False, indent=2)}

Diff stat:
{stat}

Diff:
{diff_text}
"""
