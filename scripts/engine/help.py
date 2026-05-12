from typing import Any, Dict, List

from .config import split_csv
from .lifecycle import lifecycle_diagnostics


COMMANDS = [
    (
        "review",
        "/cursor-review",
        "Review the selected PR diff for correctness, security, tests, and risky edge cases.",
    ),
    (
        "ask",
        "/cursor-ask",
        "Answer a specific question about the PR using available diff and PR context.",
    ),
    (
        "improve",
        "/cursor-improve",
        "Suggest prioritized improvements without duplicating review findings.",
    ),
    (
        "describe",
        "/cursor-describe",
        "Create a comment-only PR summary with walkthrough, risk, and test-plan notes.",
    ),
]

HELP_ALIASES = ["/cursor-help", "/cursor-review help"]
EXAMPLES = {
    "review": "/cursor-review --focus=security,tests --max-findings=3",
    "ask": "/cursor-ask Why did the auth flow change?",
    "improve": "/cursor-improve --files src/auth.py,tests/test_auth.py",
    "describe": "/cursor-describe",
}


def enabled_command_names(settings: Dict[str, Any]) -> List[str]:
    configured = {item.lower() for item in split_csv(settings.get("enabled_commands"))}
    return [name for name, _slash, _description in COMMANDS if name in configured]


def render_help(settings: Dict[str, Any]) -> str:
    enabled = enabled_command_names(settings)
    enabled_set = set(enabled)
    command_lines = [
        f"- `{slash}` - {description}"
        for name, slash, description in COMMANDS
        if name in enabled_set
    ]
    example_lines = [EXAMPLES[name] for name in enabled if name in EXAMPLES]
    if not command_lines:
        command_lines = ["- No review commands are enabled for this run."]
    if not example_lines:
        example_lines = ["/cursor-help"]

    aliases = ", ".join(f"`{alias}`" for alias in HELP_ALIASES)
    config_path = str(settings.get("config_path") or ".cursor-review.yml")
    trigger_source = str(settings.get("command_prompt_source") or "unknown")
    language = str(settings.get("language") or "zh-CN")
    lifecycle = lifecycle_diagnostics(settings.get("lifecycle") or {})
    lifecycle_stages = " -> ".join(lifecycle.get("state_sequence") or []) or "unknown"

    return f"""# Cursor Review Action Help

This static help response did not contact Cursor.

## Available commands

{chr(10).join(command_lines)}

Help is always available through {aliases}.

## Examples

```text
{chr(10).join(example_lines)}
```

## Allowlisted per-run arguments

- `--focus=<items>` narrows review focus, for example `security,tests`.
- `--max-findings=<1-50>` caps actionable findings.
- `--scope=full|files` controls whether the full selected diff or named files are reviewed.
- `--files=<path-or-glob,...>` reviews only matching repository-relative files.

Unknown arguments are treated as prompt text and are never executed as shell.

## Configuration and troubleshooting

- Repo config path: `{config_path}`
- Enable commands with `enabled-commands` in the workflow or `enabled_commands` in `.cursor-review.yml`.
- Manual PR comments must be posted on the PR conversation and allowed by the workflow trigger policy.
- The recommended workflow trusts `OWNER`, `MEMBER`, and `COLLABORATOR` for slash commands.
- The workflow needs `pull-requests: write` and `issues: write` permissions to publish comments.

<details>
<summary>Cursor Help Diagnostics</summary>

- Help schema: `help/v1`
- Command: `help`
- Command source: `{trigger_source}`
- Enabled commands: `{", ".join(enabled) or "none"}`
- Language: `{language}`
- Cursor contacted: `false`
- Lifecycle schema: `{lifecycle.get("schema_version", "unknown")}`
- Lifecycle final state: `{lifecycle.get("final_state", "unknown")}`
- Lifecycle reason: `{lifecycle.get("reason", "unknown")}`
- Lifecycle stages: `{lifecycle_stages}`

</details>
"""
