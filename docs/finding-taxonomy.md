# Finding Taxonomy

`/cursor-review` findings use a stable taxonomy so parser output, fixtures, and
future quality gates can reason about severity, confidence, and noise without
depending on exact model wording.

## Schema

Every normalized review finding includes:

- `schema_version`: `cursor-review-finding/v1`
- `category`: one of `bug`, `security`, `test_gap`, `performance`,
  `regression_risk`, `maintainability`, `docs`, or `question`
- `severity`: one of `critical`, `high`, `medium`, `low`, or `info`
- `confidence`: one of `high`, `medium`, or `low`
- `noise_control`: `actionable_review` for findings that belong in
  `/cursor-review`

The parser accepts missing or mixed-case severity/confidence values and
normalizes them. Missing categories are inferred from the finding text using a
small deterministic keyword map. Unknown categories are recorded in parser
diagnostics and mapped to the closest review category.

## Noise control

Style, readability, refactor, formatting, nit, maintainability, docs-only, and
question-style feedback does not belong in `/cursor-review` by default. Those
findings are better handled by `/cursor-improve` or `/cursor-ask`.

When the model returns one of these categories in review output, the parser:

1. keeps the finding in `findings_json` for auditability,
2. sets `suppressed: true`,
3. sets `suppression_reason: review_noise_control`,
4. sets `noise_control: route_to_cursor_improve`, and
5. downgrades severity and confidence to `low`.

Future output-quality-gate work can use these deterministic fields to suppress
or reroute noisy findings before publishing.

## Diagnostics

Rendered diagnostics include taxonomy schema version, whether taxonomy was
applied, normalized finding count, defaulted/invalid category counts,
invalid severity/confidence counts, and noise-suppressed count.
