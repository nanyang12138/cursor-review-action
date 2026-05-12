# Local Development

This project keeps a no-Cursor path for contributors who want to validate engine
behavior without GitHub Actions, a `CURSOR_API_KEY`, or PR comment publishing.

## Run tests

```bash
python3 -m unittest tests/test_engine.py
python3 -m compileall scripts tests
```

These tests cover command routing, config loading, trigger policy, diff
selection, prompt construction, structured output parsing, rendering, fixture
regression, and CI policy diagnostics.

## Local dry-run

Use `scripts/cursor_review.py --dry-run` from a git checkout:

```bash
python3 scripts/cursor_review.py --dry-run
```

The dry-run path:

- loads `.cursor-review.yml` or the configured `INPUT_CONFIG_PATH`;
- builds local git context from `HEAD~1...HEAD` when explicit base/head SHAs are
  not provided;
- applies include/exclude, scope, diff byte, file, and hunk budgets;
- renders the command prompt to `cursor_review_prompt.txt`;
- parses deterministic stored output without contacting Cursor;
- renders `cursor_review.md`, `findings.json`, and
  `cursor_review_diagnostics.json`.

No `CURSOR_API_KEY` is required, and the generated outputs set
`should_comment=false` so this mode cannot publish PR comments.

## Parse stored model output

To validate parser/render behavior against a captured Cursor-like response,
store the response with the normal tags:

```text
<review_markdown>...</review_markdown>
<findings_json>...</findings_json>
```

Then run:

```bash
python3 scripts/cursor_review.py --dry-run --dry-run-output stored-output.txt
```

The stored file is parsed locally. If `--dry-run-output` is omitted, the engine
uses a deterministic synthetic sample for the selected command.

## Useful local inputs

The dry-run entrypoint uses the same environment variables as the GitHub Action.
For example:

```bash
INPUT_COMMAND=review \
INPUT_ENABLED_COMMANDS=review,ask,improve,describe \
INPUT_LANGUAGE=en \
INPUT_MAX_DIFF_BYTES=60000 \
python3 scripts/cursor_review.py --dry-run
```

For command prompts, pass the same comment body the action would receive:

```bash
INPUT_COMMENT_BODY="/cursor-review --focus=security --max-findings=2" \
python3 scripts/cursor_review.py --dry-run
```

The dry-run skips trigger trust enforcement because it never contacts Cursor and
never publishes a comment; trigger trust remains enforced for normal action runs.
