# PR-Agent Comparison Protocol

This directory holds maintainer-facing comparison reports for the clean-room
Cursor-native PR Agent engine.

## Clean-room boundary

Comparison reports may describe PR-Agent behavior only at a high level. Do not
copy PR-Agent source code, prompts, schemas, tests, fixtures, or exact generated
output into this repository. Reports should compare product behavior, coverage,
diagnostics, and user usefulness.

Allowed evidence:

- Public product behavior summarized in our own words.
- Synthetic or public PR scenarios owned by this repository.
- Cursor-native action output from this repository.
- Maintainer observations such as missed issues, false positives, or missing
  diagnostics.

Disallowed evidence:

- Verbatim PR-Agent prompts, schemas, source code, tests, fixtures, or output.
- Golden files derived from PR-Agent output.
- Private repository code or customer data.

## Report workflow

1. Select a synthetic or public sample PR scenario.
2. Run the Cursor-native no-Cursor fixture path when possible.
3. Optionally observe PR-Agent product behavior from public usage or a separate
   clean-room environment, then summarize only behavior classes.
4. Record gaps as `GAP-*` entries.
5. Classify every gap as one of:
   - `backlog`: should become or link to a plan item.
   - `deferred`: valuable, but blocked by release, cost, security, or product
     sequencing constraints.
   - `non-goal`: explicitly outside the current product scope.
6. Link each gap to a capability ID, plan todo ID, or documented non-goal.

## Required report fields

Use `template.md` for new reports. Each report must include:

- Sample identity and source fixture, if any.
- Command under comparison.
- High-level PR-Agent behavior class.
- Cursor-native evidence.
- Observed gaps.
- Gap decision and owner document.
- Fixture or regression coverage status.
- Release impact.
- Human acceptance rubric fields from `docs/acceptance-rubric.md`, including
  false positives, missed issues, evidence quality, command intent, diagnostic
  usefulness, skipped-content transparency, and follow-up action.

## Release gates

- Before `v0.5`: at least 5 concrete comparison samples must be logged.
- Before `v1`: 10-20 comparison samples should cover common and high-risk PRs.
- Every comparison gap must be converted to backlog, deferred rationale, or
  explicit non-goal before release readiness can be claimed.
- Quality claims require matching fixture or dogfooding records using the human
  acceptance rubric.
