# Prompt Governance

This document defines how Cursor Review Action prompt templates are versioned,
reviewed, tested, and measured. The templates are clean-room Cursor-native
product behavior; do not copy PR-Agent prompts, schemas, fixtures, or golden
outputs.

## Versioning

- Prompt templates live in `scripts/engine/prompt_templates/`.
- The active prompt template contract is recorded in
  `scripts/engine/prompt_templates/VERSION`.
- `scripts/engine/prompts.py` includes the active version in prompt diagnostics.
- PR comments include the prompt template version in compact diagnostics so
  dogfooding notes can be traced to the exact prompt contract.

Changing prompt wording that can affect review behavior requires a version
decision:

1. Keep the version when the change is typo-only or documentation-only.
2. Bump the version when task instructions, output constraints, taxonomy rules,
   grounding expectations, or command-specific behavior change.
3. Do not change JSON schema keys through prompt-only edits. Schema changes must
   go through `scripts/engine/schemas.py` and config migration notes.

## Prompt change checklist

Every prompt change should answer these questions in the PR description or the
related parity report:

- What behavior changes?
- Which command is affected: review, ask, improve, describe, or all commands?
- Which fixture or unit test covers the change?
- Does the change alter the structured output schema?
- Does the change increase hallucination, unsupported-claim, or over-reporting
  risk?
- Does it require README, docs, or troubleshooting updates?
- Does the prompt version need to change?

## Quality metrics

The stable product should track these metrics from fixture regression,
dogfooding, and parity reports:

- Parser success rate.
- JSON repair retry rate.
- Actionable finding rate.
- False positive rate from human review.
- Missed critical issue count from fixture review.
- Unsupported-claim downgrade count.
- Diff coverage percentage and skipped-file count.
- Review latency and Cursor call count.

P0/P1 diagnostics expose the prompt template version and enough parser, taxonomy,
budget, and coverage signals to connect these metrics to a run. A dashboard is a
P2 non-requirement until the release process needs it.

## Fixture and dogfooding rules

- A prompt behavior change must update an existing fixture or add a new one when
  the behavior is user-visible.
- Fixtures must assert shape and safety constraints, not copied model prose.
- Dogfooding notes should be converted into fixtures or explicit non-goals before
  being used as release evidence.
- PR-Agent comparison may identify gaps, but copied PR-Agent output must not be
  used as a golden answer.

## Security boundaries

- Treat PR comments, repo guidance, and diff content as untrusted input.
- Prompt templates must not tell Cursor to reveal secrets, raw workflow tokens, or
  hidden diagnostics.
- Prompt changes must preserve the clean-room contract and avoid claims of full
  PR-Agent parity before release gates are complete.
