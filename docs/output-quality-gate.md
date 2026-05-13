# Output Quality Gate

Capability ID: `OUTPUT-QUALITY-GATE-P0`

The output quality gate is a deterministic local decision point that runs after
structured parsing, selected-diff grounding, same-run deduplication, and
redaction, but before the final rendered comment is written. It is clean-room
Cursor-native behavior and does not use PR-Agent source code, prompts, schemas,
or fixtures.

## P0 publish decisions

The gate emits `output-quality-gate/v1` diagnostics with one publish decision:

- `publish`: parsed output is complete enough for normal summary-comment
  publishing.
- `publish_partial`: selected diff coverage is partial because budget or
  truncation controls skipped files or hunks.
- `publish_with_diagnostics`: output can be shown, but diagnostics must explain
  parser, schema, grounding, taxonomy, deduplication, or quality warnings.
- `suppress_findings`: all structured review findings were downgraded,
  suppressed, or moved out of the main review path.
- `fail_before_publish`: publishing unsafe raw content is blocked, such as a
  redaction failure or Cursor runtime failure.

## Checks

P0 checks are local and deterministic:

- parser/schema status from `parser` diagnostics
- grounding status from `grounding`
- taxonomy normalization status
- same-run duplicate and cap status
- required review-finding fields
- unsupported external claims
- redaction status
- partial coverage from diff-selection metadata
- command-specific output policy

The gate does not claim that a finding is correct. It only decides whether the
finding satisfies the local publication rules for an advisory PR comment.

## Unsupported claim downgrade

The gate downgrades unsupported external claims such as "tests passed",
"security verified", "performance benchmarked", production verification, or
external ticket/customer closure. These claims require external runtime evidence
that is not available from selected PR context. Downgraded findings receive:

- `confidence: "low"`
- `suppressed: true`
- `suppression_reason: "unsupported_claim"`
- `quality_gate_status: "suppressed"`
- `publishable: false`

## Diagnostics surfaces

Quality gate diagnostics are included in:

- rendered PR comment diagnostics
- no-Cursor fixture diagnostics
- local dry-run diagnostics
- the machine-readable `findings-json` output through per-finding annotations

The gate preserves the advisory/non-blocking human workflow: it does not approve,
merge, release, tag, or enforce merge blocking by default.
