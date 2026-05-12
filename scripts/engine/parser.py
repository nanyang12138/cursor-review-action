import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

from .schemas import schema_text


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


def parse_agent_output_result(raw: str) -> ParseResult:
    markdown = extract_tag(raw, "review_markdown") or raw.strip()
    findings_raw = extract_tag(raw, "findings_json")

    if findings_raw:
        try:
            parsed = json.loads(findings_raw)
            if isinstance(parsed, (dict, list)):
                findings_raw = json.dumps(parsed, ensure_ascii=False, indent=2)
                return ParseResult(markdown, findings_raw, True, _diagnostics(True, "valid_json"))
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


def parse_agent_output(raw: str) -> Tuple[str, str, bool]:
    result = parse_agent_output_result(raw)
    return result.markdown, result.findings_json, result.parsed_ok
