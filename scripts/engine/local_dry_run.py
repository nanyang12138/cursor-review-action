import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .budget import normalized_budget_settings
from .ci_policy import evaluate_ci_policy
from .context import build_review_context
from .findings import postprocess_findings_json
from .grounding import ground_findings_json
from .parser import parse_agent_output_result
from .prompts import build_prompt, prompt_template_version
from .render import render_comment
from .schemas import SCHEMA_VERSION


@dataclass
class LocalDryRunResult:
    rendered: str
    findings_json: str
    prompt: str
    raw_output: str
    parsed_ok: bool
    diff_truncated: bool
    ci_policy: Dict[str, Any]
    diagnostics: Dict[str, Any]


def _sample_payload(command: str) -> Any:
    if command == "ask":
        return {
            "schema_version": SCHEMA_VERSION,
            "command": "ask",
            "answer": "Local dry-run parsed this stored answer without contacting Cursor.",
            "evidence": ["local selected diff"],
            "limitations": ["This is deterministic dry-run output, not model analysis."],
            "follow_up_questions": [],
        }
    if command == "improve":
        return {
            "schema_version": SCHEMA_VERSION,
            "command": "improve",
            "suggestions": [],
        }
    if command == "describe":
        return {
            "schema_version": SCHEMA_VERSION,
            "command": "describe",
            "summary": "Local dry-run summary generated without contacting Cursor.",
            "walkthrough": ["Built context, selected diff, rendered prompt, parsed output, and rendered comment."],
            "risks": ["No live Cursor model analysis was performed."],
            "tests": ["Run the unit tests for engine behavior."],
            "changelog": "",
        }
    return []


def sample_agent_output(command: str) -> str:
    payload = _sample_payload(command)
    return f"""<review_markdown>Local dry-run completed without contacting Cursor.

This validates configuration loading, local git context, diff selection, prompt rendering, structured output parsing, and comment rendering. It is not a live AI review.</review_markdown>
<findings_json>{json.dumps(payload, ensure_ascii=False)}</findings_json>
"""


def load_dry_run_agent_output(command: str, output_path: Optional[str] = None) -> Dict[str, str]:
    if output_path:
        path = Path(output_path)
        return {
            "source": "stored_file",
            "path": str(path),
            "raw_output": path.read_text(encoding="utf-8"),
        }
    return {
        "source": "synthetic_sample",
        "path": "",
        "raw_output": sample_agent_output(command),
    }


def run_local_dry_run(settings: Dict[str, Any], output_path: Optional[str] = None) -> LocalDryRunResult:
    command = str(settings.get("resolved_command") or settings.get("command") or "review")
    settings["resolved_command"] = command
    settings["local_dry_run"] = True
    settings["cursor_api_key_present"] = False
    settings["prompt_template_version"] = prompt_template_version()

    context = build_review_context(settings)
    prompt = build_prompt(
        command,
        str(settings.get("resolved_user_prompt") or ""),
        context.diff_text,
        context.stat,
        context.truncated,
        context.meta,
        settings,
    )
    output = load_dry_run_agent_output(command, output_path)
    parse_result = parse_agent_output_result(output["raw_output"], command)
    grounding_result = ground_findings_json(parse_result.findings_json, context.meta.get("diff_index") or {}, command)
    findings_json = grounding_result.findings_json
    findings_result = postprocess_findings_json(findings_json, settings, command)
    findings_json = findings_result.findings_json
    parser_diagnostics = dict(parse_result.diagnostics)
    parser_diagnostics["grounding"] = grounding_result.diagnostics
    parser_diagnostics["findings"] = findings_result.diagnostics
    parser_diagnostics["repair_retry_count"] = 0
    parser_diagnostics["dry_run_output_source"] = output["source"]
    if output["path"]:
        parser_diagnostics["dry_run_output_path"] = output["path"]

    budgets = normalized_budget_settings(settings)
    ci_policy = evaluate_ci_policy(0, findings_json, settings)
    runner_diagnostics = {
        "runner": "local_dry_run",
        "failure_kind": "none",
        "timeout_seconds": settings.get("timeout_seconds", 600),
        "retry_count": 0,
        "cursor_calls_attempted": 0,
        "max_cursor_calls": budgets["max_cursor_calls"],
        "cursor_contacted": False,
        "parser": parser_diagnostics,
        "ci_policy": ci_policy,
        "dry_run": {
            "enabled": True,
            "output_source": output["source"],
            "output_path": output["path"],
        },
    }
    rendered = render_comment(
        parse_result.markdown,
        findings_json,
        0,
        "",
        context.truncated,
        parse_result.parsed_ok,
        context.meta,
        settings,
        runner_diagnostics,
    )
    diagnostics = {
        "mode": "local_dry_run",
        "cursor_contacted": False,
        "command": command,
        "prompt_template_version": settings["prompt_template_version"],
        "diff_truncated": context.truncated,
        "files_reviewed": len(context.meta.get("reviewed_files") or context.meta.get("files") or []),
        "files_skipped": len(context.meta.get("skipped_files") or []),
        "dry_run_output_source": output["source"],
        "parser": parser_diagnostics,
        "ci_policy": ci_policy,
    }
    return LocalDryRunResult(
        rendered=rendered,
        findings_json=findings_json,
        prompt=prompt,
        raw_output=output["raw_output"],
        parsed_ok=parse_result.parsed_ok,
        diff_truncated=context.truncated,
        ci_policy=ci_policy,
        diagnostics=diagnostics,
    )


def write_local_dry_run_artifacts(result: LocalDryRunResult, output_dir: Path = Path(".")) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "cursor_review_prompt.txt").write_text(result.prompt, encoding="utf-8")
    (output_dir / "cursor_review_raw.txt").write_text(result.raw_output, encoding="utf-8")
    (output_dir / "cursor_review.md").write_text(result.rendered, encoding="utf-8")
    (output_dir / "findings.json").write_text(result.findings_json, encoding="utf-8")
    (output_dir / "cursor_review_diagnostics.json").write_text(
        json.dumps(result.diagnostics, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
