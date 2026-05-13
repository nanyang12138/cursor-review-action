# Review Lifecycle Diagnostics

Capability IDs: `REVIEW-LIFECYCLE-P0`, `RUN-STATE-P0`.

Cursor Review Action tracks a deterministic lifecycle for every run so users can
tell whether the engine published a complete result, published a degraded result,
failed, or skipped before contacting Cursor.

This lifecycle is diagnostic-only. It does not approve PRs, merge PRs, publish
progress comments, create releases, or change public action inputs.

## States

| State | Meaning |
| --- | --- |
| `queued` | The command and run metadata were resolved. |
| `collecting_context` | The engine is building PR metadata and repository context. |
| `selecting_diff` | The selected diff, coverage metadata, and skipped-file diagnostics are available. |
| `calling_cursor` | The engine is calling Cursor CLI. |
| `parsing_output` | Cursor output, local dry-run output, or repair output is being parsed and gated. |
| `published` | A complete final comment or static help result was rendered. |
| `partial` | A final result was rendered with degraded coverage or parser/quality diagnostics. |
| `failed` | The engine could not produce a reliable normal result, or the quality gate blocked publishing raw output. |
| `skipped` | The trigger policy stopped the run before Cursor was contacted. |

P0 requires the final terminal state to appear in diagnostics. P1 progress
comments remain deferred and are only planned for long-running or large/partial
reviews.

## Terminal Decision Rules

- `published`: Cursor/local output parsed successfully, the selected diff was not
  truncated, and the output quality gate returned `publish`.
- `partial`: the diff was truncated, parser fallback was needed, or the output
  quality gate returned `publish_partial`, `publish_with_diagnostics`, or
  `suppress_findings`.
- `failed`: Cursor returned a non-zero exit code or the output quality gate
  returned `fail_before_publish`.
- `skipped`: trigger trust rejected the event before context construction or
  Cursor execution.

The lifecycle does not claim model findings are correct. It only describes the
engine's execution and publication quality.

## Diagnostics Surfaces

Rendered PR comments, trigger-skip summaries, static help, and local dry-run
diagnostics include:

- lifecycle schema version
- final state
- reason
- state sequence
- terminal flag
- whether Cursor was contacted
- whether a PR comment should be published
- publish decision when an output quality gate ran
- partial reason or failed stage when applicable

Local dry-run also writes the lifecycle object to
`cursor_review_diagnostics.json`.

## Compatibility

Lifecycle diagnostics are additive. They do not change stable JSON schema keys
for model output, do not translate diagnostic keys with `language`, and do not
change existing action inputs or public command semantics.

## Deferred P1/P2 Work

- P1: `progress_comment: auto` for runs expected to be long-running or partial.
- P1: final update message metadata for persistent comment updates.
- P2: cancellation or superseded-run detection through GitHub API state.
