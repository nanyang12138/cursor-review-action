# Cursor Review Fixture Inventory

Fixture regression tests live under `tests/fixtures/pr_regression/*/fixture.json`.
They exercise the no-Cursor engine path for prompt construction, structured output
parsing, and rendered diagnostics.

Each concrete fixture must declare capability IDs so product parity claims can be
traced back to repeatable evidence in `docs/parity-scorecard.md`. The initial
review harness covers:

- `docs_only_no_findings`: docs-only PR with no findings.
- `security_finding`: high-risk review finding with structured JSON.
- `style_noise_suppressed`: review noise-control fixture that routes style
  feedback toward `/cursor-improve` instead of treating it as a high-confidence
  review finding.
- `large_partial_review`: partial review diagnostics for budget-limited diffs.
- `ask_question`: command-specific ask schema and answer rendering.
- `describe_summary`: command-specific describe schema and comment-only summary.
- `invalid_finding_anchor`: selected-diff grounding fixture that keeps an
  anchored finding while downgrading a skipped-file finding.
- `duplicate_findings`: same-run deduplication fixture that collapses duplicate
  same-line findings before applying `max_findings`.

Output quality gate fixtures live under `tests/fixtures/quality_gate/*` and cover
deterministic publish-decision behavior. The initial quality gate fixture is:

- `unsupported_claim`: downgrades an unsupported external "tests passed" claim
  before it can be treated as a high-confidence review finding.

The comparison protocol lives in `docs/parity-reports/` and uses these
repository-owned fixtures as initial samples. The fixtures intentionally do not
copy PR-Agent prompts, schemas, output, or golden text.
