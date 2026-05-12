import os
from typing import Any, Dict, List, Optional

from .redaction import combine_results, privacy_diagnostics, redact_text
from .taxonomy import taxonomy_summary


HUMAN_REVIEW_NOTICE = (
    "> Cursor Review is advisory and non-blocking. A human reviewer decides whether "
    "to accept, dismiss, or follow up on findings; this action does not approve, "
    "merge, or block PRs by default."
)


def _run_state_diagnostics(settings: Dict[str, Any]) -> List[str]:
    run_state = settings.get("run_state") or {}
    if not run_state:
        return []
    diagnostics = [
        f"- Run state schema: `{run_state.get('schema_version', 'unknown')}`",
        f"- Run generated at: `{run_state.get('generated_at', 'unknown')}`",
        f"- Run event name: `{run_state.get('event_name', 'unknown')}`",
        f"- Run command source: `{run_state.get('command_source', 'unknown')}`",
        f"- Run id: `{run_state.get('run_id', '') or 'unknown'}`",
        f"- Run attempt: `{run_state.get('run_attempt', '') or 'unknown'}`",
        f"- Base SHA: `{run_state.get('base_sha', '') or 'unknown'}`",
        f"- Head SHA: `{run_state.get('head_sha', '') or 'unknown'}`",
        f"- Stale run status: `{run_state.get('stale_status', 'unknown')}`",
        f"- Idempotency key: `{run_state.get('idempotency_key', 'unknown')}`",
    ]
    return diagnostics


def _localization_diagnostics(settings: Dict[str, Any]) -> List[str]:
    localization = settings.get("language_diagnostics") or {}
    if not localization:
        return [f"- Language: `{settings.get('language', 'unknown')}`"]
    return [
        f"- Localization schema: `{localization.get('schema_version', 'unknown')}`",
        f"- Language: `{localization.get('effective_language', settings.get('language', 'unknown'))}`",
        f"- Language fallback used: `{str(localization.get('fallback_used', False)).lower()}`",
        f"- Language reason: `{localization.get('reason', 'unknown')}`",
    ]


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
    diagnostics.extend(_localization_diagnostics(settings))
    diagnostics.extend(_run_state_diagnostics(settings))
    return f"""Cursor review skipped before contacting Cursor.

Reason: `{trigger_diagnostics.get('reason', 'unknown')}`.

<details>
<summary>Cursor Review Diagnostics</summary>

{chr(10).join(diagnostics)}

</details>
"""


def render_comment(markdown: str, findings_json: str, exit_code: int, stderr: str, truncated: bool, parsed_ok: bool, meta: Dict[str, Any], settings: Dict[str, Any], runner_diagnostics: Optional[Dict[str, Any]] = None) -> str:
    runner_diagnostics = runner_diagnostics or {}
    markdown_redaction = redact_text(markdown)
    stderr_redaction = redact_text(stderr)
    markdown = markdown_redaction.text
    stderr = stderr_redaction.text
    redaction_summary = combine_results(
        [
            markdown_redaction,
            stderr_redaction,
            runner_diagnostics.get("redaction") or redact_text(""),
        ]
    )
    budget = meta.get("budget") or {}
    reviewed_files = meta.get("reviewed_files")
    skipped_files = meta.get("skipped_files") or []
    reviewed_count = len(reviewed_files) if reviewed_files is not None else len(meta.get("files", []))
    diagnostics = [
        f"- Command: `{settings.get('resolved_command')}`",
        "- Review policy: `advisory_non_blocking`",
        "- Human decision required: `true`",
        f"- Prompt template version: `{settings.get('prompt_template_version', 'unknown')}`",
        f"- Model: `{settings.get('model')}`",
        *_localization_diagnostics(settings),
        f"- Runner: `{runner_diagnostics.get('runner', 'cursor_cli')}`",
        f"- Cursor contacted: `{str(runner_diagnostics.get('cursor_contacted', True)).lower()}`",
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
    diagnostics.extend(_run_state_diagnostics(settings))
    parser_diagnostics = runner_diagnostics.get("parser") or {}
    if parser_diagnostics:
        diagnostics.append(f"- Parser reason: `{parser_diagnostics.get('reason', 'unknown')}`")
        diagnostics.append(f"- Parser fallback: `{parser_diagnostics.get('fallback', 'unknown')}`")
        diagnostics.append(f"- Parser repair retry count: `{parser_diagnostics.get('repair_retry_count', 0)}`")
        schema_diagnostics = parser_diagnostics.get("schema") or {}
        if schema_diagnostics:
            diagnostics.append(
                f"- Output schema compatibility: `{schema_diagnostics.get('schema_compatibility', 'unknown')}`"
            )
            diagnostics.append(
                f"- Output schema status: `{schema_diagnostics.get('payload_schema_status', 'unknown')}`"
            )
            diagnostics.append(
                f"- Output schema version: `{schema_diagnostics.get('payload_schema_version', 'unknown') or 'missing'}`"
            )
            diagnostics.append(f"- Output schema command match: `{str(schema_diagnostics.get('command_match', True)).lower()}`")
        for label, value in taxonomy_summary(parser_diagnostics.get("taxonomy") or {}):
            diagnostics.append(f"- {label}: `{str(value).lower() if isinstance(value, bool) else value}`")
        grounding = parser_diagnostics.get("grounding") or {}
        if grounding:
            diagnostics.append(f"- Grounding schema: `{grounding.get('schema_version', 'unknown')}`")
            diagnostics.append(f"- Grounding applied: `{str(grounding.get('applied', False)).lower()}`")
            diagnostics.append(f"- Diff index schema: `{grounding.get('diff_index_schema_version', 'unknown')}`")
            diagnostics.append(f"- Grounding anchored findings: `{grounding.get('anchored_count', 0)}`")
            diagnostics.append(f"- Grounding file-only findings: `{grounding.get('file_only_count', 0)}`")
            diagnostics.append(f"- Grounding unanchored findings: `{grounding.get('unanchored_count', 0)}`")
            diagnostics.append(f"- Invalid anchor count: `{grounding.get('invalid_anchor_count', 0)}`")
            diagnostics.append(f"- Skipped-file finding count: `{grounding.get('skipped_file_finding_count', 0)}`")
        findings = parser_diagnostics.get("findings") or {}
        if findings:
            diagnostics.append(f"- Finding dedup schema: `{findings.get('schema_version', 'unknown')}`")
            diagnostics.append(f"- Finding dedup applied: `{str(findings.get('applied', False)).lower()}`")
            diagnostics.append(f"- Finding input count: `{findings.get('input_count', 0)}`")
            diagnostics.append(f"- Finding duplicate count: `{findings.get('duplicate_count', 0)}`")
            diagnostics.append(f"- Finding capped count: `{findings.get('capped_count', 0)}`")
            diagnostics.append(f"- Finding output count: `{findings.get('output_count', 0)}`")
        if parser_diagnostics.get("repair_skipped_reason"):
            diagnostics.append(f"- Parser repair skipped: `{parser_diagnostics.get('repair_skipped_reason')}`")
        if "repair_succeeded" in parser_diagnostics:
            diagnostics.append(f"- Parser repair succeeded: `{str(parser_diagnostics.get('repair_succeeded')).lower()}`")
        if parser_diagnostics.get("dry_run_output_source"):
            diagnostics.append(f"- Dry-run output source: `{parser_diagnostics.get('dry_run_output_source')}`")
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
    scope = meta.get("scope") or {}
    if scope:
        diagnostics.append(f"- Review scope schema: `{scope.get('schema_version', 'unknown')}`")
        diagnostics.append(f"- Review scope mode: `{scope.get('mode', 'full')}`")
        diagnostics.append(f"- Review scope reason: `{scope.get('reason', 'unknown')}`")
        diagnostics.append(f"- Review scope selected files: `{scope.get('selected_file_count', reviewed_count)}`")
        diagnostics.append(f"- Review scope skipped files: `{scope.get('skipped_file_count', 0)}`")
        for warning in scope.get("warnings") or []:
            diagnostics.append(f"- Review scope warning: `{warning}`")
    trigger_trust = settings.get("trigger_trust") or {}
    if trigger_trust:
        diagnostics.append(f"- Trigger trust level: `{trigger_trust.get('trust_level', 'unknown')}`")
        diagnostics.append(f"- Trigger reason: `{trigger_trust.get('reason', 'unknown')}`")
    ci_policy = runner_diagnostics.get("ci_policy") or {}
    if ci_policy:
        diagnostics.append(f"- CI policy schema: `{ci_policy.get('schema_version', 'unknown')}`")
        diagnostics.append(f"- CI default: `{ci_policy.get('default', 'unknown')}`")
        diagnostics.append(f"- CI fail on error: `{str(ci_policy.get('fail_on_error', False)).lower()}`")
        diagnostics.append(f"- CI fail on findings: `{str(ci_policy.get('fail_on_findings', False)).lower()}`")
        diagnostics.append(f"- CI findings gate status: `{ci_policy.get('findings_gate_status', 'unknown')}`")
        diagnostics.append(f"- CI workflow exit code: `{ci_policy.get('workflow_exit_code', 0)}`")
        diagnostics.append(f"- CI policy reason: `{ci_policy.get('reason', 'unknown')}`")
        diagnostics.append(f"- CI gating eligible findings: `{ci_policy.get('gating_eligible_finding_count', ci_policy.get('finding_count', 0))}`")
        diagnostics.append(f"- CI high severity findings: `{ci_policy.get('high_severity_finding_count', 0)}`")
    if settings.get("config_loaded"):
        diagnostics.append(f"- Config: `{settings.get('config_loaded')}`")
    privacy = privacy_diagnostics(settings, redaction_summary)
    diagnostics.append(f"- Privacy redaction schema: `{privacy.get('schema_version')}`")
    diagnostics.append(f"- Redaction status: `{privacy.get('redaction_status')}`")
    diagnostics.append(f"- Redaction replacements: `{privacy.get('redacted_count')}`")
    diagnostics.append(f"- Secret value replacements: `{privacy.get('secret_value_count')}`")
    diagnostics.append(f"- Debug artifacts enabled: `{str(privacy.get('debug_artifacts_enabled', False)).lower()}`")
    diagnostics.append(f"- Cursor data sent: `{privacy.get('cursor_data')}`")
    diagnostics.append(f"- Actions log policy: `{privacy.get('actions_log_policy')}`")
    diagnostics.append(f"- PR comment policy: `{privacy.get('pr_comment_policy')}`")
    repo_guidance = meta.get("repo_guidance") or {}
    guidance_diagnostics = repo_guidance.get("diagnostics") or {}
    if guidance_diagnostics:
        loaded_guidance = guidance_diagnostics.get("loaded") or []
        skipped_guidance = guidance_diagnostics.get("skipped") or []
        diagnostics.append(f"- Repo guidance enabled: `{str(guidance_diagnostics.get('enabled', False)).lower()}`")
        diagnostics.append(f"- Repo guidance bytes used: `{guidance_diagnostics.get('bytes_used', 0)}`")
        diagnostics.append(
            "- Repo guidance loaded files: `"
            + (", ".join(item.get("path", "") for item in loaded_guidance if item.get("path")) or "none")
            + "`"
        )
        if skipped_guidance:
            diagnostics.append(
                "- Repo guidance skipped files: `"
                + ", ".join(
                    f"{item.get('path', '')}:{item.get('reason', 'unknown')}"
                    for item in skipped_guidance
                    if item.get("path")
                )
                + "`"
            )
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

    rendered = f"""{HUMAN_REVIEW_NOTICE}

{markdown.strip()}
{warning}
<details>
<summary>Cursor Review Diagnostics</summary>

{chr(10).join(diagnostics)}

</details>
"""
    return redact_text(rendered).text


def set_output(name: str, value: str) -> None:
    value = redact_text(value).text
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        print(f"{name}={value}")
        return
    delimiter = f"EOF_{name}_{os.getpid()}"
    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")


def write_step_summary(summary: str) -> None:
    summary = redact_text(summary).text
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write(summary)
            handle.write("\n")
