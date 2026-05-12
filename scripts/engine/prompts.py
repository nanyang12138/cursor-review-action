import json
from pathlib import Path
from string import Template
from typing import Any, Dict

from .config import split_csv
from .schemas import schema_contract_for_prompt, schema_for_command


TEMPLATE_DIR = Path(__file__).with_name("prompt_templates")
SUPPORTED_TEMPLATE_COMMANDS = {"review", "ask", "improve", "describe"}


def template_path_for_command(command: str) -> Path:
    normalized = command if command in SUPPORTED_TEMPLATE_COMMANDS else "review"
    return TEMPLATE_DIR / f"{normalized}.md"


def load_command_template(command: str) -> Template:
    return Template(template_path_for_command(command).read_text(encoding="utf-8"))


def command_instructions(command: str, user_prompt: str, settings: Dict[str, Any]) -> str:
    language = settings.get("language", "zh-CN")
    max_findings = settings.get("max_findings", 5)
    focus = ", ".join(split_csv(settings.get("review_focus")))

    extra = ""
    if user_prompt:
        extra = f"\nAdditional user instructions from PR comment:\n{user_prompt}\n"

    template = load_command_template(command)
    return template.safe_substitute(
        language=language,
        max_findings=max_findings,
        focus=focus,
        user_instructions=extra,
        schema=schema_contract_for_prompt(command),
    )


def build_prompt(command: str, user_prompt: str, diff_text: str, stat: str, truncated: bool, meta: Dict[str, Any], settings: Dict[str, Any]) -> str:
    pull_request_context = meta.get("pull_request_context", {})
    diagnostics = {
        "command": command,
        "prompt_template": template_path_for_command(command).name,
        "output_schema": schema_for_command(command).get("schema_name"),
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
