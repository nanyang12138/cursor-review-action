from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CommandArgParseResult:
    user_prompt: str
    overrides: Dict[str, Any]
    parsed_args: List[str]
    warnings: List[str]


Token = Tuple[str, int, int]


FOCUS_VALUE_RE = re.compile(r"^[A-Za-z0-9_-]+$")
MAX_FINDINGS_MIN = 1
MAX_FINDINGS_MAX = 50


def _tokens_with_positions(text: str) -> List[Token]:
    tokens: List[Token] = []
    index = 0
    length = len(text)
    while index < length:
        while index < length and text[index].isspace():
            index += 1
        if index >= length:
            break
        start = index
        while index < length and not text[index].isspace():
            index += 1
        tokens.append((text[start:index], start, index))
    return tokens


def _split_option(token: str) -> Tuple[str, Optional[str]]:
    raw = token[2:]
    if "=" in raw:
        name, value = raw.split("=", 1)
        return name.strip().replace("-", "_"), value
    return raw.strip().replace("-", "_"), None


def _display_option(token: str) -> str:
    option = token.split("=", 1)[0]
    if not option.startswith("--"):
        return "--"
    safe = re.sub(r"[^A-Za-z0-9_-]", "", option[2:])
    return f"--{safe}" if safe else "--"


def _read_value(tokens: List[Token], index: int, inline_value: Optional[str]) -> Tuple[Optional[str], int, int]:
    token, _start, end = tokens[index]
    if inline_value is not None:
        return inline_value, index + 1, end

    next_index = index + 1
    if next_index >= len(tokens):
        return None, index + 1, end

    next_token, _next_start, next_end = tokens[next_index]
    if next_token.startswith("--"):
        return None, index + 1, end

    return next_token, next_index + 1, next_end


def _parse_focus(value: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if value is None or value.strip() == "":
        return None, "--focus requires a comma-separated value."

    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        return None, "--focus requires at least one focus item."
    invalid = [item for item in items if not FOCUS_VALUE_RE.fullmatch(item)]
    if invalid:
        return None, "--focus contains unsupported characters and was ignored."
    return ",".join(items), None


def _parse_max_findings(value: Optional[str]) -> Tuple[Optional[int], Optional[str]]:
    if value is None or value.strip() == "":
        return None, "--max-findings requires an integer value."
    if not re.fullmatch(r"\d+", value.strip()):
        return None, "--max-findings must be an integer and was ignored."

    parsed = int(value.strip())
    if parsed < MAX_FINDINGS_MIN or parsed > MAX_FINDINGS_MAX:
        return (
            None,
            f"--max-findings must be between {MAX_FINDINGS_MIN} and {MAX_FINDINGS_MAX} and was ignored.",
        )
    return parsed, None


def parse_command_args(command: str, text: str) -> CommandArgParseResult:
    """Parse a small allowlist of leading slash-command arguments.

    The parser is deliberately not a shell parser. It consumes only known leading
    options and returns the remaining text as prompt context.
    """
    del command
    tokens = _tokens_with_positions(text)
    overrides: Dict[str, Any] = {}
    parsed_args: List[str] = []
    warnings: List[str] = []
    consumed_end = 0
    index = 0

    while index < len(tokens):
        token, _start, end = tokens[index]
        if not token.startswith("--"):
            break

        name, inline_value = _split_option(token)
        if name in {"focus", "review_focus"}:
            raw_value, next_index, value_end = _read_value(tokens, index, inline_value)
            parsed, warning = _parse_focus(raw_value)
            if warning:
                warnings.append(warning)
            else:
                overrides["review_focus"] = parsed
                parsed_args.append("--focus")
            index = next_index
            consumed_end = value_end
            continue

        if name == "max_findings":
            raw_value, next_index, value_end = _read_value(tokens, index, inline_value)
            parsed_max, warning = _parse_max_findings(raw_value)
            if warning:
                warnings.append(warning)
            else:
                overrides["max_findings"] = parsed_max
                parsed_args.append("--max-findings")
            index = next_index
            consumed_end = value_end
            continue

        warnings.append(
            f"Unknown command argument `{_display_option(token)}` was left in the user prompt and did not override config."
        )
        break

    prompt = text[consumed_end:].lstrip()
    return CommandArgParseResult(
        user_prompt=prompt,
        overrides=overrides,
        parsed_args=parsed_args,
        warnings=warnings,
    )
