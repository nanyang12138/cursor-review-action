#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

from engine.budget import normalized_budget_settings
from engine.ci_policy import ci_policy_json, evaluate_ci_policy
from engine.command_args import parse_command_args
from engine.commands import derive_command_and_prompt, ensure_command_enabled
from engine.context import build_review_context
from engine.config import load_settings
from engine.findings import postprocess_findings_json
from engine.grounding import ground_findings_json
from engine.help import render_help
from engine.local_dry_run import run_local_dry_run, write_local_dry_run_artifacts
from engine.parser import build_repair_prompt, parse_agent_output_result
from engine.prompts import build_prompt, prompt_template_version
from engine.redaction import combine_results, redact_text
from engine.render import render_comment, render_trigger_skip, set_output, write_step_summary
from engine.runner import run_cursor_result
from engine.run_state import build_run_state
from engine.trust_policy import evaluate_trigger_trust


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Cursor Review Action engine.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run config/context/diff/prompt/parser/render locally without contacting Cursor.",
    )
    parser.add_argument(
        "--dry-run-output",
        default="",
        help="Optional stored Cursor-like output file to parse during --dry-run.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args([] if argv is None else argv)
    settings = load_settings()
    command, user_prompt = derive_command_and_prompt(settings)
    settings["resolved_command"] = command
    settings["resolved_user_prompt"] = user_prompt
    run_state = build_run_state(settings)
    settings["run_state"] = run_state["metadata"]
    set_output("resolved_command", command)
    set_output("comment_marker", run_state["comment_marker"])
    set_output("comment_title", run_state["comment_title"])
    set_output("run_metadata_json", run_state["metadata_json"])
    set_output("run_metadata_comment", run_state["metadata_comment"])

    if command == "help":
        rendered = render_help(settings)
        ci_policy = evaluate_ci_policy(0, "[]", settings)
        Path("cursor_review.md").write_text(rendered, encoding="utf-8")
        Path("findings.json").write_text("[]", encoding="utf-8")
        set_output("summary", rendered)
        set_output("findings_json", "[]")
        set_output("ci_policy_json", ci_policy_json(ci_policy))
        set_output("exit_code", "0")
        set_output("diff_truncated", "false")
        set_output("should_comment", "true")
        write_step_summary(rendered)
        return 0

    if settings.get("command_prompt_source") in {"slash_command", "trigger_phrase"}:
        command_args = parse_command_args(command, user_prompt)
        user_prompt = command_args.user_prompt
        settings.update(command_args.overrides)
        settings["command_arg_overrides"] = command_args.overrides
        settings["command_arg_keys"] = command_args.parsed_args
        settings["command_arg_warnings"] = command_args.warnings
    else:
        settings["command_arg_overrides"] = {}
        settings["command_arg_keys"] = []
        settings["command_arg_warnings"] = []
    settings["resolved_user_prompt"] = user_prompt

    enabled, message = ensure_command_enabled(command, settings)
    if not enabled:
        rendered = f"{message}\n"
        ci_policy = evaluate_ci_policy(78, "[]", settings)
        set_output("summary", rendered)
        set_output("findings_json", "[]")
        set_output("ci_policy_json", ci_policy_json(ci_policy))
        set_output("exit_code", "78")
        set_output("diff_truncated", "false")
        set_output("should_comment", "true")
        write_step_summary(rendered)
        return int(ci_policy["workflow_exit_code"])

    if args.dry_run:
        result = run_local_dry_run(settings, args.dry_run_output or None)
        write_local_dry_run_artifacts(result)
        set_output("summary", result.rendered)
        set_output("findings_json", result.findings_json)
        set_output("ci_policy_json", ci_policy_json(result.ci_policy))
        set_output("exit_code", "0")
        set_output("diff_truncated", str(result.diff_truncated).lower())
        set_output("should_comment", "false")
        write_step_summary(result.rendered)
        return 0

    trigger_decision = evaluate_trigger_trust(settings)
    settings["trigger_trust"] = trigger_decision.diagnostics
    if not trigger_decision.allowed:
        rendered = render_trigger_skip(trigger_decision.diagnostics, settings)
        ci_policy = evaluate_ci_policy(78, "[]", settings)
        Path("cursor_review.md").write_text(rendered, encoding="utf-8")
        Path("findings.json").write_text("[]", encoding="utf-8")
        set_output("summary", rendered)
        set_output("findings_json", "[]")
        set_output("ci_policy_json", ci_policy_json(ci_policy))
        set_output("exit_code", "78")
        set_output("diff_truncated", "false")
        set_output("should_comment", str(trigger_decision.should_comment).lower())
        write_step_summary(rendered)
        return int(ci_policy["workflow_exit_code"])

    context = build_review_context(settings)
    settings["prompt_template_version"] = prompt_template_version()
    prompt = build_prompt(
        command,
        user_prompt,
        context.diff_text,
        context.stat,
        context.truncated,
        context.meta,
        settings,
    )
    if settings.get("debug_artifacts"):
        Path("cursor_review_prompt.txt").write_text(redact_text(prompt).text, encoding="utf-8")

    runner_result = run_cursor_result(prompt, settings)
    exit_code = runner_result.exit_code
    stdout = runner_result.raw_text
    stderr = runner_result.stderr
    raw_output = stdout + ("\n\nSTDERR:\n" + stderr if stderr else "")

    parse_result = parse_agent_output_result(stdout, command)
    markdown = parse_result.markdown
    findings_json = parse_result.findings_json
    parsed_ok = parse_result.parsed_ok
    parser_diagnostics = dict(parse_result.diagnostics)
    parser_diagnostics["repair_retry_count"] = 0
    runner_diagnostics = dict(runner_result.diagnostics)

    max_cursor_calls = normalized_budget_settings(settings)["max_cursor_calls"]
    cursor_calls_attempted = int(runner_diagnostics.get("cursor_calls_attempted", 1))
    if exit_code == 0 and not parsed_ok:
        if cursor_calls_attempted < max_cursor_calls:
            repair_prompt = build_repair_prompt(command, stdout)
            repair_result = run_cursor_result(repair_prompt, settings)
            repair_parse_result = parse_agent_output_result(repair_result.raw_text, command)
            cursor_calls_attempted += 1
            raw_output = (
                f"{raw_output}\n\nPARSER_REPAIR_STDOUT:\n{repair_result.raw_text}"
                + ("\n\nPARSER_REPAIR_STDERR:\n" + repair_result.stderr if repair_result.stderr else "")
            )
            if repair_result.stderr:
                stderr = (stderr + "\n\n" if stderr else "") + "Parser repair retry stderr:\n" + repair_result.stderr
            if repair_result.exit_code == 0 and repair_parse_result.parsed_ok:
                markdown = repair_parse_result.markdown
                findings_json = repair_parse_result.findings_json
                parsed_ok = True
                parser_diagnostics = dict(repair_parse_result.diagnostics)
                parser_diagnostics["repair_succeeded"] = True
            else:
                parser_diagnostics["repair_succeeded"] = False
                parser_diagnostics["repair_failure_kind"] = repair_result.failure_kind
                parser_diagnostics["repair_exit_code"] = repair_result.exit_code
            parser_diagnostics["repair_retry_count"] = 1
        else:
            parser_diagnostics["repair_skipped_reason"] = "max_cursor_calls_exhausted"

    runner_diagnostics["cursor_calls_attempted"] = cursor_calls_attempted
    runner_diagnostics["retry_count"] = parser_diagnostics.get("repair_retry_count", 0)
    grounding_result = ground_findings_json(findings_json, context.meta.get("diff_index") or {}, command)
    findings_json = grounding_result.findings_json
    parser_diagnostics["grounding"] = grounding_result.diagnostics
    findings_result = postprocess_findings_json(findings_json, settings, command)
    findings_json = findings_result.findings_json
    parser_diagnostics["findings"] = findings_result.diagnostics
    runner_diagnostics["parser"] = parser_diagnostics
    ci_policy = evaluate_ci_policy(exit_code, findings_json, settings)
    runner_diagnostics["ci_policy"] = ci_policy
    markdown_redaction = redact_text(markdown)
    findings_redaction = redact_text(findings_json)
    stderr_redaction = redact_text(stderr)
    raw_output_redaction = redact_text(raw_output)
    runner_diagnostics["redaction"] = combine_results(
        [
            markdown_redaction,
            findings_redaction,
            stderr_redaction,
            raw_output_redaction if settings.get("debug_artifacts") else redact_text(""),
        ]
    )
    markdown = markdown_redaction.text
    findings_json = findings_redaction.text
    stderr = stderr_redaction.text
    if settings.get("debug_artifacts"):
        Path("cursor_review_raw.txt").write_text(raw_output_redaction.text, encoding="utf-8")
    rendered = render_comment(
        markdown,
        findings_json,
        exit_code,
        stderr,
        context.truncated,
        parsed_ok,
        context.meta,
        settings,
        runner_diagnostics,
    )
    Path("cursor_review.md").write_text(rendered, encoding="utf-8")
    Path("findings.json").write_text(findings_json, encoding="utf-8")

    set_output("summary", rendered)
    set_output("findings_json", findings_json)
    set_output("ci_policy_json", ci_policy_json(ci_policy))
    set_output("exit_code", str(exit_code))
    set_output("diff_truncated", str(context.truncated).lower())
    set_output("should_comment", "true")
    write_step_summary(rendered)

    return int(ci_policy["workflow_exit_code"])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
