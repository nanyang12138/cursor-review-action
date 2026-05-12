# Cursor Review Fixture Inventory

Fixture regression tests live under `tests/fixtures/pr_regression/*/fixture.json`.
They exercise the no-Cursor engine path for prompt construction, structured output
parsing, and rendered diagnostics.

Each concrete fixture must declare capability IDs so product parity claims can be
traced back to repeatable evidence in `docs/parity-scorecard.md`. The harness
currently has 17 concrete no-Cursor fixtures, satisfying the `v0.5` fixture
volume gate while the `v1` target remains 20 fixtures. The review harness covers:

- `docs_only_no_findings`: docs-only PR with no findings.
- `security_finding`: high-risk review finding with structured JSON.
- `style_noise_suppressed`: review noise-control fixture that routes style
  feedback toward `/cursor-improve` instead of treating it as a high-confidence
  review finding.
- `large_partial_review`: partial review diagnostics for budget-limited diffs.
- `ask_question`: command-specific ask schema and answer rendering.
- `describe_summary`: command-specific describe schema and comment-only summary.
- `improve_suggestions`: command-specific improve schema, author-facing
  suggestion rendering, and repo guidance diagnostics for general plus
  improve-only guidance files.
- `invalid_finding_anchor`: selected-diff grounding fixture that keeps an
  anchored finding while downgrading a skipped-file finding.
- `deleted_line_anchor`: deleted-only diff fixture that validates `old_line` /
  `line_side: old` grounding without requiring a new-side line anchor.
- `generated_lockfile_skipped`: generated asset and lockfile fixture that keeps
  review evidence on the source wrapper while recording skipped generated files.
- `renamed_file_anchor`: renamed-file fixture that verifies old/new path aliases
  in the selected-diff index can still anchor a new-side finding.
- `config_only_review`: configuration-only PR fixture that keeps `.cursor-review.yml`
  reviewable and verifies effective config diagnostics in rendered output.
- `duplicate_findings`: same-run deduplication fixture that collapses duplicate
  same-line findings before applying `max_findings`.
- `invalid_model_output`: invalid model `<findings_json>` fixture that preserves
  readable markdown while routing malformed structured output through parser
  fallback and quality-gate diagnostics.
- `empty_cursor_output`: empty Cursor stdout fixture that emits a safe markdown
  fallback, runner `output` diagnostics, retry-exhaustion diagnostics, and a
  `publish_with_diagnostics` quality-gate decision.

Output quality gate fixtures live under `tests/fixtures/quality_gate/*` and cover
deterministic publish-decision behavior. The initial quality gate fixture is:

- `unsupported_claim`: downgrades an unsupported external "tests passed" claim
  before it can be treated as a high-confidence review finding.

Invalid config fixtures live under `tests/fixtures/config_invalid/*` and cover
schema diagnostics plus safe fallback behavior before Cursor is contacted:

- `bad_values`: unknown config keys are ignored, invalid numeric/boolean/filter
  values fall back safely, and rendered diagnostics expose the warnings.

The comparison protocol lives in `docs/parity-reports/` and uses these
repository-owned fixtures as initial samples. The fixtures intentionally do not
copy PR-Agent prompts, schemas, output, or golden text.
