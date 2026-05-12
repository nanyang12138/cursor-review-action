import json
from pathlib import Path
from typing import Any, Dict

from .config import split_csv
from .guidance import format_guidance_for_prompt
from .localization import language_instruction
from .schemas import schema_text


TEMPLATE_DIR = Path(__file__).with_name("prompt_templates")
VERSION_FILE = TEMPLATE_DIR / "VERSION"


def prompt_template_version() -> str:
    if not VERSION_FILE.exists():
        return "unversioned"
    return VERSION_FILE.read_text(encoding="utf-8").strip() or "unversioned"


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
    return template.strip() + "\n\n" + language_instruction(language) + "\n"


def build_prompt(command: str, user_prompt: str, diff_text: str, stat: str, truncated: bool, meta: Dict[str, Any], settings: Dict[str, Any]) -> str:
    pull_request_context = meta.get("pull_request_context", {})
    repo_guidance = meta.get("repo_guidance") or {"sections": [], "diagnostics": {}}
    guidance_prompt = format_guidance_for_prompt(repo_guidance)
    diagnostics = {
        "command": command,
        "prompt_template_version": prompt_template_version(),
        "prompt_template_name": command if (TEMPLATE_DIR / f"{command}.md").exists() else "review",
        "model": settings.get("model"),
        "language": settings.get("language"),
        "config_loaded": settings.get("config_loaded"),
        "command_arg_overrides": settings.get("command_arg_overrides", {}),
        "command_arg_warnings": settings.get("command_arg_warnings", []),
        "repo_guidance": repo_guidance.get("diagnostics", {}),
        "diff_truncated": truncated,
        "diff_meta": meta,
    }
    guidance_section = f"\nRepository guidance:\n{guidance_prompt}\n" if guidance_prompt else ""
    return f"""{command_instructions(command, user_prompt, settings)}

Diagnostics:
{json.dumps(diagnostics, ensure_ascii=False, indent=2)}

Pull request context:
{json.dumps(pull_request_context, ensure_ascii=False, indent=2)}
{guidance_section}

Diff stat:
{stat}

Diff:
{diff_text}
"""
