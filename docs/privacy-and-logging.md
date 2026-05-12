# Privacy and Logging Policy

Capability ID: `SEC-PRIVACY-P0`

Cursor Review Action handles PR metadata, selected diffs, user command text, and
repo-local configuration. This policy defines where that data goes and which
surfaces must be redacted before publication.

## Data sent to Cursor

For Cursor-backed commands, the action sends one prompt to Cursor CLI containing:

- selected PR diff text and diff stat;
- PR title, PR body presence/content, branch names, commit messages, and changed
  file paths supplied by the workflow;
- user slash-command instructions or `user-prompt`;
- repo guidance files that are enabled and within the configured guidance budget;
- command schema and stable prompt template text.

The action never intentionally sends `CURSOR_API_KEY` or `github-token` to the
prompt. Fork PRs without secrets and untrusted issue comments are skipped before
context construction and before Cursor is contacted.

## Data written to PR comments and summaries

PR comments and `GITHUB_STEP_SUMMARY` include:

- model-produced human-readable markdown after local redaction;
- compact diagnostics such as command, model, parser state, diff coverage, trigger
  decision, CI policy, and redaction status;
- counts and booleans about PR context presence rather than raw PR body content in
  diagnostics.

They must not include raw prompt text, raw selected diff, secret values, or
token-like strings. Redaction is best-effort deterministic masking implemented in
`scripts/engine/redaction.py`.

## Action outputs and files

The `summary` and `findings-json` outputs are redacted before they are written to
`GITHUB_OUTPUT`. `cursor_review.md` and `findings.json` contain the same redacted
published surfaces.

Live runs do not write `cursor_review_prompt.txt` or `cursor_review_raw.txt` by
default. Set `debug-artifacts: true` only when a maintainer needs a short-lived
debug artifact; even then, the prompt and raw output files are redacted before
they are written.

Local `--dry-run` remains a developer tool and writes prompt/render artifacts in
the working directory so contributors can inspect deterministic engine behavior
without contacting Cursor. Do not run local dry-run in a directory where generated
debug files will be uploaded automatically.

## Redaction behavior

The redaction layer masks:

- exact values from environment variables whose names look secret-bearing, such
  as `CURSOR_API_KEY`, `GITHUB_TOKEN`, `*_TOKEN`, `*_KEY`, and `*_SECRET`;
- common token prefixes such as GitHub, OpenAI-style `sk-`, GitLab, npm, PyPI,
  Hugging Face, Slack, and JWT-like strings;
- assignment-style values such as `secret=...`, `token: ...`, and
  `Authorization: Bearer ...`.

Rendered diagnostics include:

- `Privacy redaction schema`;
- `Redaction status`;
- `Redaction replacements`;
- `Secret value replacements`;
- `Debug artifacts enabled`;
- Cursor, Actions log, and PR comment policy summaries.

If a redaction gap is found, add a focused fixture under `tests/fixtures/privacy/`
and extend `scripts/engine/redaction.py` without logging the real secret value.
