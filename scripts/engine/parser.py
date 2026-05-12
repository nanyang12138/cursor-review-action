import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

from .schemas import output_schema_diagnostics, schema_text
from .taxonomy import apply_finding_taxonomy


@dataclass
class ParseResult:
    markdown: str
    findings_json: str
    parsed_ok: bool
    diagnostics: Dict[str, Any] = field(default_factory=dict)


def extract_tag(text: str, tag: str) -> str:
    pattern = re.compile(rf"<{tag}>\s*(.*?)\s*</{tag}>", re.DOTALL | re.IGNORECASE)
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def _diagnostics(parsed_ok: bool, reason: str, detail: str = "") -> Dict[str, Any]:
    diagnostics = {
        "parser": "structured_json",
        "parsed": parsed_ok,
        "fallback": "none" if parsed_ok else "markdown",
        "reason": reason,
    }
    if detail:
        diagnostics["detail"] = detail
    return diagnostics


def parse_agent_output_result(raw: str, command: str = "review") -> ParseResult:
    markdown = extract_tag(raw, "review_markdown") or raw.strip()
    findings_raw = extract_tag(raw, "findings_json")

    if findings_raw:
        try:
            parsed = json.loads(findings_raw)
            if isinstance(parsed, (dict, list)):
                taxonomy_result = apply_finding_taxonomy(parsed, command)
                schema_diagnostics = output_schema_diagnostics(taxonomy_result.payload, command)
                if not schema_diagnostics.get("compatible", False):
                    diagnostics = _diagnostics(
                        False,
                        str(schema_diagnostics.get("reason", "unsupported_schema_version")),
                        str(schema_diagnostics.get("payload_schema_status", "unknown")),
                    )
                    diagnostics["schema"] = schema_diagnostics
                    diagnostics["taxonomy"] = taxonomy_result.diagnostics
                    return ParseResult(markdown, "[]", False, diagnostics)
                findings_raw = json.dumps(taxonomy_result.payload, ensure_ascii=False, indent=2)
                diagnostics = _diagnostics(True, "valid_json")
                diagnostics["schema"] = schema_diagnostics
                diagnostics["taxonomy"] = taxonomy_result.diagnostics
                return ParseResult(markdown, findings_raw, True, diagnostics)
            return ParseResult(
                markdown,
                "[]",
                False,
                _diagnostics(False, "invalid_json_type", f"Expected JSON object or array, got {type(parsed).__name__}."),
            )
        except Exception:
            return ParseResult(markdown, "[]", False, _diagnostics(False, "invalid_json"))

    return ParseResult(markdown, "[]", False, _diagnostics(False, "missing_findings_json"))


def build_repair_prompt(command: str, raw_output: str) -> str:
    return f"""Repair the previous Cursor review response so it follows the required output contract.

Do not add new claims. Preserve the original human-readable content when possible.
Return only these two XML-style sections:
<review_markdown>...</review_markdown>
<findings_json>...</findings_json>

The JSON inside <findings_json> must be valid JSON and match this schema:
{schema_text(command)}

Previous response to repair:
```text
{raw_output[-20000:]}
```
"""


def parse_agent_output(raw: str, command: str = "review") -> Tuple[str, str, bool]:
    result = parse_agent_output_result(raw, command)
    return result.markdown, result.findings_json, result.parsed_ok
