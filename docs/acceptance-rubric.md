# Human Acceptance Rubric

This rubric records whether Cursor Review Action output is useful to human
reviewers during dogfooding and clean-room PR-Agent behavior comparisons. It is
maintainer-facing evidence, not a public claim of complete PR-Agent parity.

## Capability

- Plan todo: `acceptance-rubric`
- Capability ID: `ACCEPTANCE-RUBRIC-P1`
- Parity level: P1
- Scope: dogfooding records, comparison records, and fixture-backed human
  acceptance notes.

## Clean-room boundary

Evaluations may summarize product behavior classes and reviewer observations.
Do not copy PR-Agent source code, prompts, schemas, tests, fixtures, or exact
generated output into this repository. Use repository-owned fixtures, public
sample PRs, or maintainer-written observations.

## Required dimensions

Each dogfooding or comparison record must score or record these dimensions:

| Field | Required value | Purpose |
| --- | --- | --- |
| `real_issue_found` | `yes`, `no`, or `not_applicable` | Whether the output found a concrete issue a maintainer would act on. |
| `false_positive_count` | Integer >= 0 | Counts findings that should not be shown as actionable review findings. |
| `missed_issue_count` | Integer >= 0 | Counts known important issues the output failed to mention. |
| `evidence_quality` | `0`, `1`, `2`, or `3` | Rates whether cited file, line, and explanation evidence is enough for review. |
| `command_intent_respected` | `yes` or `no` | Verifies `/cursor-review`, `/cursor-ask`, `/cursor-improve`, or `/cursor-describe` behavior stayed on task. |
| `output_conciseness` | `0`, `1`, `2`, or `3` | Rates whether the answer is compact enough for PR comments. |
| `diagnostics_usefulness` | `0`, `1`, `2`, or `3` | Rates coverage, parser, trust, budget, and lifecycle diagnostics. |
| `skipped_content_transparency` | `0`, `1`, `2`, `3`, or `not_applicable` | Rates whether skipped files, partial review, or safe skips are clear. |
| `follow_up_action` | `none`, `fixture`, `prompt`, `parser`, `docs`, `backlog`, or `non_goal` | Converts observations into maintainable work. |

Score meaning for 0-3 fields:

- `0`: missing or misleading.
- `1`: present but insufficient for reviewer trust.
- `2`: acceptable with minor follow-up.
- `3`: release-ready for this scenario.

## Minimum acceptance for stable release readiness

Before claiming stable release readiness:

- Every high-risk dogfooding or comparison run has a `human_eval.md` record or a
  parity report section using the same fields.
- False positives with actionable impact become fixture cases, prompt changes,
  parser fixes, docs, backlog items, or documented non-goals.
- Missed issues in security, correctness, tests, or release safety become
  fixture cases or release blockers unless explicitly downgraded with evidence.
- Quality claims in README or release notes are backed by fixture and rubric
  records.
- A record never includes private code, raw prompts, raw diffs from private
  repositories, secrets, or token-like strings.

## Fixture record format

Fixture records live next to fixture inputs:

```text
tests/fixtures/pr_regression/<case>/human_eval.md
```

Use this compact format:

```markdown
# Human Evaluation

- Evaluation type: fixture
- Capability IDs:
  - ACCEPTANCE-RUBRIC-P1
- Command:
- Scenario:
- real_issue_found:
- false_positive_count:
- missed_issue_count:
- evidence_quality:
- command_intent_respected:
- output_conciseness:
- diagnostics_usefulness:
- skipped_content_transparency:
- follow_up_action:

## Notes

-
```

## Follow-up routing

- `fixture`: add or update a concrete regression fixture.
- `prompt`: update prompt templates through `docs/prompt-governance.md`.
- `parser`: update structured parsing, schema compatibility, or fallback tests.
- `docs`: update user-facing or maintainer-facing documentation.
- `backlog`: add or keep a plan item with release impact.
- `non_goal`: document the deferral in `docs/non-goals.md`.
