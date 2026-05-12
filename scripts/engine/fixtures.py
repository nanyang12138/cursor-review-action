import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .budget import normalized_budget_settings
from .config import DEFAULTS
from .diff_index import build_diff_index
from .findings import postprocess_findings_json
from .grounding import ground_findings_json
from .parser import parse_agent_output_result
from .prompts import build_prompt
from .quality_gate import evaluate_output_quality
from .redaction import combine_results, redact_text
from .render import render_comment


@dataclass
class FixtureResult:
    prompt: str
    markdown: str
    findings_json: str
    parsed_ok: bool
    rendered: str
    diagnostics: Dict[str, Any]


def discover_fixture_paths(root: Path) -> List[Path]:
    return sorted(path for path in root.rglob("fixture.json") if path.is_file())


def load_fixture(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _settings_for_fixture(fixture: Dict[str, Any]) -> Dict[str, Any]:
    command = fixture.get("command", "review")
    settings = DEFAULTS.copy()
    settings.update(fixture.get("settings") or {})
    settings["resolved_command"] = command
    settings.setdefault("model", "auto")
    settings.setdefault("language", "en")
    return settings


def run_fixture(fixture: Dict[str, Any]) -> FixtureResult:
    command = fixture.get("command", "review")
    context = fixture.get("context") or {}
    settings = _settings_for_fixture(fixture)
    meta = copy.deepcopy(context.get("meta") or {})
    meta.setdefault("diff_index", build_diff_index(context.get("diff_text", ""), meta.get("skipped_files") or []))
    prompt = build_prompt(
        command,
        fixture.get("user_prompt", ""),
        context.get("diff_text", ""),
        context.get("stat", ""),
        bool(context.get("truncated", False)),
        meta,
        settings,
    )
    parse_result = parse_agent_output_result(fixture.get("agent_output", ""), command)
    grounding_result = ground_findings_json(parse_result.findings_json, meta.get("diff_index") or {}, command)
    findings_json = grounding_result.findings_json
    findings_result = postprocess_findings_json(findings_json, settings, command)
    findings_json = findings_result.findings_json
    runner_diagnostics = dict(fixture.get("runner_diagnostics") or {})
    if parse_result.diagnostics:
        parser_diagnostics = dict(parse_result.diagnostics)
        parser_diagnostics.setdefault("repair_retry_count", 0)
        cursor_calls_attempted = int(runner_diagnostics.get("cursor_calls_attempted", 1) or 1)
        max_cursor_calls = normalized_budget_settings(settings)["max_cursor_calls"]
        if (
            int(fixture.get("exit_code", 0)) == 0
            and not parse_result.parsed_ok
            and cursor_calls_attempted >= max_cursor_calls
        ):
            parser_diagnostics.setdefault("repair_skipped_reason", "max_cursor_calls_exhausted")
        parser_diagnostics["grounding"] = grounding_result.diagnostics
        parser_diagnostics["findings"] = findings_result.diagnostics
        runner_diagnostics.setdefault("parser", parser_diagnostics)
    else:
        parser_diagnostics = runner_diagnostics.setdefault("parser", {})
    markdown_redaction = redact_text(parse_result.markdown)
    findings_redaction = redact_text(findings_json)
    stderr_redaction = redact_text(fixture.get("stderr", ""))
    redaction_summary = combine_results([markdown_redaction, findings_redaction, stderr_redaction])
    runner_diagnostics["redaction"] = redaction_summary
    quality_result = evaluate_output_quality(
        markdown_redaction.text,
        findings_redaction.text,
        int(fixture.get("exit_code", 0)),
        parse_result.parsed_ok,
        bool(context.get("truncated", False)),
        meta,
        settings,
        runner_diagnostics,
        redaction_summary,
    )
    findings_json = quality_result.findings_json
    parser_diagnostics["quality_gate"] = quality_result.diagnostics
    runner_diagnostics["quality_gate"] = quality_result.diagnostics
    rendered = render_comment(
        markdown_redaction.text,
        findings_json,
        int(fixture.get("exit_code", 0)),
        stderr_redaction.text,
        bool(context.get("truncated", False)),
        parse_result.parsed_ok,
        meta,
        settings,
        runner_diagnostics,
    )
    return FixtureResult(
        prompt=prompt,
        markdown=parse_result.markdown,
        findings_json=findings_json,
        parsed_ok=parse_result.parsed_ok,
        rendered=rendered,
        diagnostics={
            "fixture_name": fixture.get("name", ""),
            "capability_ids": fixture.get("capability_ids") or [],
            "parser": runner_diagnostics.get("parser", parse_result.diagnostics),
            "quality_gate": quality_result.diagnostics,
        },
    )


def _missing_snippets(label: str, text: str, snippets: Iterable[str]) -> List[str]:
    return [f"{label} missing expected snippet: {snippet}" for snippet in snippets if snippet not in text]


def validate_fixture(fixture: Dict[str, Any], result: FixtureResult) -> List[str]:
    expected = fixture.get("expected") or {}
    errors: List[str] = []
    if not fixture.get("capability_ids"):
        errors.append("fixture must declare at least one capability id")
    if "parsed_ok" in expected and result.parsed_ok is not bool(expected["parsed_ok"]):
        errors.append(f"parsed_ok expected {expected['parsed_ok']} got {result.parsed_ok}")

    try:
        parsed_findings = json.loads(result.findings_json)
    except Exception as exc:
        errors.append(f"findings_json is not valid JSON: {exc}")
        parsed_findings = None

    if "findings_count" in expected and isinstance(parsed_findings, list):
        actual_count = len(parsed_findings)
        if actual_count != int(expected["findings_count"]):
            errors.append(f"findings_count expected {expected['findings_count']} got {actual_count}")
    if "findings_type" in expected and parsed_findings is not None:
        expected_type = expected["findings_type"]
        actual_type = "array" if isinstance(parsed_findings, list) else "object" if isinstance(parsed_findings, dict) else type(parsed_findings).__name__
        if actual_type != expected_type:
            errors.append(f"findings_type expected {expected_type} got {actual_type}")

    errors.extend(_missing_snippets("prompt", result.prompt, expected.get("prompt_contains") or []))
    errors.extend(_missing_snippets("markdown", result.markdown, expected.get("markdown_contains") or []))
    errors.extend(_missing_snippets("rendered", result.rendered, expected.get("rendered_contains") or []))
    errors.extend(_missing_snippets("findings_json", result.findings_json, expected.get("findings_json_contains") or []))
    for snippet in expected.get("rendered_not_contains") or []:
        if snippet in result.rendered:
            errors.append(f"rendered included forbidden snippet: {snippet}")
    return errors
