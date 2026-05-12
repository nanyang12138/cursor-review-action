import os
from typing import Any, Dict, Optional


def render_trigger_skip(trigger_diagnostics: Dict[str, Any], settings: Dict[str, Any]) -> str:
    diagnostics = [
        f"- Command: `{settings.get('resolved_command')}`",
        "- Trigger decision: `skipped`",
        f"- Trigger reason: `{trigger_diagnostics.get('reason', 'unknown')}`",
        f"- Trigger trust level: `{trigger_diagnostics.get('trust_level', 'unknown')}`",
        f"- Event name: `{trigger_diagnostics.get('event_name', 'unknown')}`",
        f"- Command source: `{trigger_diagnostics.get('command_prompt_source', 'unknown')}`",
        f"- Comment author association: `{trigger_diagnostics.get('comment_author_association', 'unknown')}`",
        f"- PR is fork: `{str(trigger_diagnostics.get('pr_is_fork', False)).lower()}`",
        f"- Cursor API key present: `{str(trigger_diagnostics.get('cursor_api_key_present', False)).lower()}`",
    ]
    return f"""Cursor review skipped before contacting Cursor.

Reason: `{trigger_diagnostics.get('reason', 'unknown')}`.

<details>
<summary>Cursor Review Diagnostics</summary>

{chr(10).join(diagnostics)}

</details>
"""


def render_comment(markdown: str, findings_json: str, exit_code: int, stderr: str, truncated: bool, parsed_ok: bool, meta: Dict[str, Any], settings: Dict[str, Any], runner_diagnostics: Optional[Dict[str, Any]] = None) -> str:
    runner_diagnostics = runner_diagnostics or {}
    budget = meta.get("budget") or {}
    reviewed_files = meta.get("reviewed_files")
    skipped_files = meta.get("skipped_files") or []
    reviewed_count = len(reviewed_files) if reviewed_files is not None else len(meta.get("files", []))
    diagnostics = [
        f"- Command: `{settings.get('resolved_command')}`",
        f"- Model: `{settings.get('model')}`",
        f"- Runner: `{runner_diagnostics.get('runner', 'cursor_cli')}`",
        f"- Runner failure kind: `{runner_diagnostics.get('failure_kind', 'none')}`",
        f"- Runner timeout seconds: `{runner_diagnostics.get('timeout_seconds', settings.get('timeout_seconds', 600))}`",
        f"- Runner retry count: `{runner_diagnostics.get('retry_count', 0)}`",
        f"- Cursor calls attempted: `{runner_diagnostics.get('cursor_calls_attempted', 1)}`",
        f"- Max Cursor calls: `{runner_diagnostics.get('max_cursor_calls', budget.get('max_cursor_calls', settings.get('max_cursor_calls', 1)))}`",
        f"- Filter mode: `{settings.get('filter_mode')}`",
        f"- Diff truncated: `{str(truncated).lower()}`",
        f"- Findings JSON parsed: `{str(parsed_ok).lower()}`",
        f"- Cursor exit code: `{exit_code}`",
    ]
    if budget:
        diagnostics.append(f"- Budget max diff bytes: `{budget.get('max_diff_bytes')}`")
        diagnostics.append(f"- Budget max files: `{budget.get('max_files')}`")
        diagnostics.append(f"- Budget max hunks: `{budget.get('max_hunks')}`")
        diagnostics.append(f"- Diff bytes reviewed: `{meta.get('diff_bytes', 0)}`")
        diagnostics.append(f"- Diff hunks reviewed: `{meta.get('hunks', 0)}`")
    if settings.get("command_arg_keys"):
        diagnostics.append(f"- Command args applied: `{', '.join(settings.get('command_arg_keys', []))}`")
    for warning in settings.get("command_arg_warnings", []):
        diagnostics.append(f"- Command args warning: `{warning}`")
    trigger_trust = settings.get("trigger_trust") or {}
    if trigger_trust:
        diagnostics.append(f"- Trigger trust level: `{trigger_trust.get('trust_level', 'unknown')}`")
        diagnostics.append(f"- Trigger reason: `{trigger_trust.get('reason', 'unknown')}`")
    if settings.get("config_loaded"):
        diagnostics.append(f"- Config: `{settings.get('config_loaded')}`")
    diagnostics.append(f"- Files reviewed: `{reviewed_count}`")
    diagnostics.append(f"- Files skipped: `{len(skipped_files)}`")
    pull_request_context = meta.get("pull_request_context") or {}
    if pull_request_context:
        commit_count = len(pull_request_context.get("commit_messages") or [])
        diagnostics.append(f"- PR title provided: `{str(bool(pull_request_context.get('title'))).lower()}`")
        diagnostics.append(f"- PR body provided: `{str(bool(pull_request_context.get('body'))).lower()}`")
        diagnostics.append(f"- Commit messages provided: `{commit_count}`")

    if exit_code != 0:
        markdown = f"""Cursor review failed before producing a reliable result.

```text
{stderr.strip() or 'No stderr captured.'}
```
"""

    warning = ""
    if truncated:
        reasons = ", ".join(meta.get("truncation_reasons") or ["budget"])
        warning = f"\n> Note: The selected diff was limited by `{reasons}`, so this review may not cover every changed line.\n"

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
