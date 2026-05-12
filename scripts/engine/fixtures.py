import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .config import DEFAULTS
from .parser import parse_agent_output_result
from .prompts import build_prompt
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
    prompt = build_prompt(
        command,
        fixture.get("user_prompt", ""),
        context.get("diff_text", ""),
        context.get("stat", ""),
        bool(context.get("truncated", False)),
        context.get("meta") or {},
        settings,
    )
    parse_result = parse_agent_output_result(fixture.get("agent_output", ""), command)
    runner_diagnostics = dict(fixture.get("runner_diagnostics") or {})
    if parse_result.diagnostics:
        runner_diagnostics.setdefault("parser", parse_result.diagnostics)
    rendered = render_comment(
        parse_result.markdown,
        parse_result.findings_json,
        int(fixture.get("exit_code", 0)),
        fixture.get("stderr", ""),
        bool(context.get("truncated", False)),
        parse_result.parsed_ok,
        context.get("meta") or {},
        settings,
        runner_diagnostics,
    )
    return FixtureResult(
        prompt=prompt,
        markdown=parse_result.markdown,
        findings_json=parse_result.findings_json,
        parsed_ok=parse_result.parsed_ok,
        rendered=rendered,
        diagnostics={
            "fixture_name": fixture.get("name", ""),
            "capability_ids": fixture.get("capability_ids") or [],
            "parser": parse_result.diagnostics,
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
