# Cursor Review Fixture Inventory

Fixture regression tests live under `tests/fixtures/pr_regression/*/fixture.json`.
They exercise the no-Cursor engine path for prompt construction, structured output
parsing, and rendered diagnostics.

Each concrete fixture must declare capability IDs so product parity claims can be
traced back to repeatable evidence in `docs/parity-scorecard.md`. The initial
review harness covers:

- `docs_only_no_findings`: docs-only PR with no findings.
- `security_finding`: high-risk review finding with structured JSON.
- `large_partial_review`: partial review diagnostics for budget-limited diffs.
- `ask_question`: command-specific ask schema and answer rendering.
- `describe_summary`: command-specific describe schema and comment-only summary.

The comparison protocol and larger release inventory remain separate follow-up
work; these fixtures intentionally do not copy PR-Agent prompts, schemas, output,
or golden text.
