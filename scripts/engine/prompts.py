import json
from pathlib import Path
from string import Template
from typing import Any, Dict

from .config import split_csv
from .schemas import output_schema_for_command, schema_contract_for_prompt, schema_for_command


TEMPLATE_DIR = Path(__file__).with_name("prompt_templates")
SUPPORTED_TEMPLATE_COMMANDS = {"review", "ask", "improve", "describe"}


def prompt_template_version() -> str:
    version_path = TEMPLATE_DIR / "VERSION"
    if not version_path.exists():
        return "prompt-template-unknown"
    return version_path.read_text(encoding="utf-8").strip() or "prompt-template-unknown"


def template_path_for_command(command: str) -> Path:
    normalized = command if command in SUPPORTED_TEMPLATE_COMMANDS else "review"
    return TEMPLATE_DIR / f"{normalized}.md"


def load_command_template(command: str) -> Template:
    return Template(template_path_for_command(command).read_text(encoding="utf-8"))


def format_guidance_for_prompt(repo_guidance: Dict[str, Any]) -> str:
    sections = repo_guidance.get("sections") or []
    formatted = []
    for section in sections:
        content = str(section.get("content") or "").strip()
        if not content:
            continue
        label = str(section.get("path") or section.get("kind") or "repo guidance")
        kind = str(section.get("kind") or "general")
        formatted.append(f"### {label} ({kind})\n{content}")
    return "\n\n".join(formatted)


def command_instructions(command: str, user_prompt: str, settings: Dict[str, Any]) -> str:
    language = settings.get("language", "zh-CN")
    max_findings = settings.get("max_findings", 5)
    focus = ", ".join(split_csv(settings.get("review_focus")))
    # Keep the concrete output schema reachable for prompt-shape tests and future
    # diagnostics without changing the template placeholder contract.
    output_schema_for_command(command)

    extra = ""
    if user_prompt:
        extra = f"\nAdditional user instructions from PR comment:\n{user_prompt}\n"

    template = load_command_template(command)
    rendered = template.safe_substitute(
        language=language,
        max_findings=max_findings,
        focus=focus,
        user_instructions=extra,
        schema=schema_contract_for_prompt(command),
    )
    language_contract = (
        f"Write all human-readable prose in {language}.\n"
        "Do not translate JSON field names, XML-style wrapper tags, diagnostics keys, or schema values."
    )
    return f"{language_contract}\n\n{rendered}"


def build_prompt(command: str, user_prompt: str, diff_text: str, stat: str, truncated: bool, meta: Dict[str, Any], settings: Dict[str, Any]) -> str:
    pull_request_context = meta.get("pull_request_context", {})
    repo_guidance = meta.get("repo_guidance") or {"sections": [], "diagnostics": {}}
    guidance_prompt = format_guidance_for_prompt(repo_guidance)
    diagnostics = {
        "command": command,
        "prompt_template": template_path_for_command(command).name,
        "output_schema": schema_for_command(command).get("schema_name"),
        "model": settings.get("model"),
        "language": settings.get("language"),
        "config_loaded": settings.get("config_loaded"),
        "command_arg_overrides": settings.get("command_arg_overrides", {}),
        "command_arg_warnings": settings.get("command_arg_warnings", []),
        "repo_guidance": repo_guidance.get("diagnostics", {}),
        "prompt_template_version": prompt_template_version(),
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
