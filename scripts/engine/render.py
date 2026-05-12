import os
from typing import Any, Dict, Optional


def render_comment(markdown: str, findings_json: str, exit_code: int, stderr: str, truncated: bool, parsed_ok: bool, meta: Dict[str, Any], settings: Dict[str, Any], runner_diagnostics: Optional[Dict[str, Any]] = None) -> str:
    runner_diagnostics = runner_diagnostics or {}
    diagnostics = [
        f"- Command: `{settings.get('resolved_command')}`",
        f"- Model: `{settings.get('model')}`",
        f"- Runner: `{runner_diagnostics.get('runner', 'cursor_cli')}`",
        f"- Runner failure kind: `{runner_diagnostics.get('failure_kind', 'none')}`",
        f"- Runner timeout seconds: `{runner_diagnostics.get('timeout_seconds', settings.get('timeout_seconds', 600))}`",
        f"- Runner retry count: `{runner_diagnostics.get('retry_count', 0)}`",
        f"- Filter mode: `{settings.get('filter_mode')}`",
        f"- Diff truncated: `{str(truncated).lower()}`",
        f"- Findings JSON parsed: `{str(parsed_ok).lower()}`",
        f"- Cursor exit code: `{exit_code}`",
    ]
    if settings.get("command_arg_keys"):
        diagnostics.append(f"- Command args applied: `{', '.join(settings.get('command_arg_keys', []))}`")
    for warning in settings.get("command_arg_warnings", []):
        diagnostics.append(f"- Command args warning: `{warning}`")
    if settings.get("config_loaded"):
        diagnostics.append(f"- Config: `{settings.get('config_loaded')}`")
    diagnostics.append(f"- Files reviewed: `{len(meta.get('files', []))}`")

    if exit_code != 0:
        markdown = f"""Cursor review failed before producing a reliable result.

```text
{stderr.strip() or 'No stderr captured.'}
```
"""

    warning = ""
    if truncated:
        warning = "\n> Note: The diff was truncated by `max_diff_bytes`, so this review may not cover every changed line.\n"

    return f"""{markdown.strip()}
{warning}
<details>
<summary>Cursor Review Diagnostics</summary>

{chr(10).join(diagnostics)}

</details>
"""


def set_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        print(f"{name}={value}")
        return
    delimiter = f"EOF_{name}_{os.getpid()}"
    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")


def write_step_summary(summary: str) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write(summary)
            handle.write("\n")
