#!/usr/bin/env python3
import sys
from pathlib import Path

from engine.commands import derive_command_and_prompt, ensure_command_enabled
from engine.context import build_review_context
from engine.config import load_settings
from engine.parser import parse_agent_output
from engine.prompts import build_prompt
from engine.render import render_comment, set_output, write_step_summary
from engine.runner import run_cursor_result


def main() -> int:
    settings = load_settings()
    command, user_prompt = derive_command_and_prompt(settings)
    settings["resolved_command"] = command
    set_output("resolved_command", command)

    enabled, message = ensure_command_enabled(command, settings)
    if not enabled:
        rendered = f"{message}\n"
        set_output("summary", rendered)
        set_output("findings_json", "[]")
        set_output("exit_code", "78")
        set_output("diff_truncated", "false")
        write_step_summary(rendered)
        return 78 if settings.get("fail_on_error") else 0

    context = build_review_context(settings)
    prompt = build_prompt(
        command,
        user_prompt,
        context.diff_text,
        context.stat,
        context.truncated,
        context.meta,
        settings,
    )
    Path("cursor_review_prompt.txt").write_text(prompt, encoding="utf-8")

    runner_result = run_cursor_result(prompt, settings)
    exit_code = runner_result.exit_code
    stdout = runner_result.raw_text
    stderr = runner_result.stderr
    raw_output = stdout + ("\n\nSTDERR:\n" + stderr if stderr else "")
    Path("cursor_review_raw.txt").write_text(raw_output, encoding="utf-8")

    markdown, findings_json, parsed_ok = parse_agent_output(stdout)
    rendered = render_comment(
        markdown,
        findings_json,
        exit_code,
        stderr,
        context.truncated,
        parsed_ok,
        context.meta,
        settings,
        runner_result.diagnostics,
    )
    Path("cursor_review.md").write_text(rendered, encoding="utf-8")
    Path("findings.json").write_text(findings_json, encoding="utf-8")

    set_output("summary", rendered)
    set_output("findings_json", findings_json)
    set_output("exit_code", str(exit_code))
    set_output("diff_truncated", str(context.truncated).lower())
    write_step_summary(rendered)

    if exit_code != 0 and settings.get("fail_on_error"):
        return exit_code

    return 0


if __name__ == "__main__":
    sys.exit(main())
