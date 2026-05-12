import json
import re
from typing import Tuple


def extract_tag(text: str, tag: str) -> str:
    pattern = re.compile(rf"<{tag}>\s*(.*?)\s*</{tag}>", re.DOTALL | re.IGNORECASE)
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def parse_agent_output(raw: str) -> Tuple[str, str, bool]:
    markdown = extract_tag(raw, "review_markdown") or raw.strip()
    findings_raw = extract_tag(raw, "findings_json")
    parsed_ok = False

    if findings_raw:
        try:
            parsed = json.loads(findings_raw)
            if isinstance(parsed, (dict, list)):
                findings_raw = json.dumps(parsed, ensure_ascii=False, indent=2)
                parsed_ok = True
        except Exception:
            parsed_ok = False
    if not findings_raw:
        findings_raw = "[]"
        parsed_ok = True

    return markdown, findings_raw, parsed_ok
