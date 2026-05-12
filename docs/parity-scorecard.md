# Cursor PR Agent Engine Parity Scorecard

This maintainer-facing scorecard tracks clean-room Cursor-native capabilities from
planning ID to implementation evidence, fixture coverage, diagnostics, and release
readiness. It is intentionally not a public claim of full PR-Agent parity.

## Capability status

| Capability ID | Level | Implementation status | Fixture / test evidence | Diagnostics status | Release blocker | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| CMD-REVIEW-P0 | P0 | Implemented in `scripts/engine/commands.py` and `scripts/engine/prompts.py` | `tests/fixtures/pr_regression/docs_only_no_findings`, `tests/fixtures/pr_regression/security_finding`; `tests/test_engine.py::CommandTests` | Command name and run metadata render in PR diagnostics | No | Preserves `/cursor-review` as the default command. |
| CMD-ASK-P1 | P1 | Implemented behind command enablement in `scripts/engine/commands.py` and prompt templates | `tests/fixtures/pr_regression/ask_question`; command routing unit tests | Command marker and schema diagnostics are available when enabled | No for v0.5; verify UX before stable v1 | P1 command remains opt-in through `enabled_commands`. |
| CMD-IMPROVE-P1 | P1 | Template and schema are present in `scripts/engine/prompt_templates/improve.md` and `scripts/engine/schemas.py` | Unit coverage through command schema construction; no concrete PR fixture yet | Command marker and schema diagnostics are available when enabled | Yes for final stable product | Needs a concrete improve fixture and dogfooding evidence before stable release. |
| CMD-DESCRIBE-P1 | P1 | Implemented as comment-only describe output | `tests/fixtures/pr_regression/describe_summary` | Command marker and schema diagnostics are available when enabled | No for comment-only mode | PR body mutation remains deferred. |
| CTX-METADATA-P0 | P0 | Implemented in `scripts/engine/context.py` | `tests/fixtures/pr_regression/docs_only_no_findings`; `tests/test_engine.py::ContextBuilderTests` | Diagnostics show metadata presence without leaking PR body | No | Includes PR title/body presence, commit messages, changed files, and diff stat. |
| DIFF-LARGE-P0 | P0 | Implemented in `scripts/engine/diff_selector.py` | `tests/fixtures/pr_regression/large_partial_review`; diff selector unit tests | Reviewed/skipped file counts and truncation state render in diagnostics | No | Byte-aware selection exists; token-aware fitting remains a later improvement. |
| PROMPT-REVIEW-P0 | P0 | Implemented in `scripts/engine/prompts.py` and `scripts/engine/prompt_templates/review.md` | `tests/fixtures/pr_regression/docs_only_no_findings`, `tests/fixtures/pr_regression/security_finding` | Prompt diagnostics include command, model, config, diff coverage, and schema version | No | Clean-room prompt text is versioned in this repository. |
| PROMPT-COMMAND-SCHEMA-P0 | P0 | Implemented in `scripts/engine/prompt_templates/*.md` and `scripts/engine/schemas.py` | `tests/fixtures/pr_regression/ask_question`, `tests/fixtures/pr_regression/describe_summary`; prompt parser tests | Diagnostics include command-specific schema contract and prompt template version | Partial | Add improve fixture before marking command-template evidence complete for all commands. |
| PARSER-FALLBACK-P0 | P0 | Implemented in `scripts/engine/parser.py` | Review fixtures and parser unit tests | Parser diagnostics are attached to rendered comment diagnostics | No | Invalid JSON degrades to markdown while preserving diagnostics. |
| PARSER-RETRY-P1 | P1 | Implemented in `scripts/engine/parser.py` and orchestrated by `scripts/cursor_review.py` | Parser retry unit tests | Retry count and parser failure kind are available in diagnostics | No for P1; add invalid-output fixture before v1 | One repair prompt is used before markdown fallback. |
| PUB-PERSISTENT-P0 | P0 | Implemented through command-specific markers in `scripts/engine/run_state.py` and rendering outputs | Review and large-partial fixtures; entrypoint unit tests | Outputs include comment marker and run metadata JSON | No | Summary comment publishing remains the P0 surface; inline comments are deferred. |
| CURSOR-RUNNER-P0 | P0 | Implemented in `scripts/engine/runner.py` | `tests/test_engine.py::RunnerContractTests` | Failure kind, requested model, timeout, retry count, and cursor-call budget are reported | No | Cursor CLI remains the execution layer. |
| BUDGET-CONTROLS-P1 | P1 | Implemented in `scripts/engine/budget.py`, `scripts/engine/diff_selector.py`, and `scripts/engine/runner.py` | `tests/fixtures/pr_regression/large_partial_review`; budget and runner unit tests | Budget limits, skipped files, and cursor-call attempts are visible | No | `max_cursor_calls` defaults to one. |
| RUN-STATE-P0 | P0 | Implemented in `scripts/engine/run_state.py` and entrypoint outputs | `tests/test_engine.py::RunStateTests` and entrypoint tests | Run id, command marker, lifecycle state, head SHA, event name, and stale diagnostics are output | No | P0 stale-run support is diagnostic-only. |
| SEC-TRIGGER-P0 | P0 | Implemented in `scripts/engine/trust_policy.py` before context construction or Cursor calls | `tests/fixtures/triggers/*.json`; trigger policy unit tests | Skip reason, trust level, event, fork state, and secret availability are reported | No | Untrusted issue comments and fork PRs without secrets do not call Cursor. |
| FIXTURE-HARNESS-P0 | P0 | Implemented in `scripts/engine/fixtures.py` | `tests/test_engine.py::FixtureRegressionTests` | Fixture diagnostics record fixture name, parser status, and capability IDs | Partial | Current harness has 5 concrete PR fixtures; v0.5 requires 10. |
| TRACEABILITY-SCORECARD-P0 | P0 | Implemented in this scorecard and validated by unit tests | `tests/test_engine.py::FixtureRegressionTests` scorecard coverage test | Capability IDs now connect fixture evidence to release blockers | No | Keep this file updated with each capability PR. |

## Current release blockers

These blockers are not failures of the scorecard itself; they are remaining final
product gates from `docs/plans/cursor-pr-agent-engine.plan.md`.

- `comparison-protocol`: no PR-Agent comparison report template or sample gap log yet.
- `prompt-governance`: prompt change checklist and quality metrics are not documented.
- `finding-taxonomy`: stable taxonomy and noise-control rules are not implemented.
- `repo-guidance`: `.cursor-review-instructions.md` / `best_practices.md` injection is not implemented.
- `local-dry-run`: no dedicated local dry-run command or documentation exists yet.
- `privacy-logging`: redaction policy and token-like diagnostic safeguards are incomplete.
- `review-lifecycle`: final lifecycle state diagnostics exist but lifecycle documentation and state model are incomplete.
- `fixture-inventory`: the current suite has 5 concrete PR fixtures; v0.5 requires 10 and v1 targets 20.
- `finding-grounding`: selected-diff line index and anchor validation are not implemented.
- `finding-dedup`: same-run finding normalization and deduplication are not implemented.
- `output-quality-gate`: deterministic publish decision is not implemented.
- `docs-positioning`: README positioning for clean-room Cursor-native behavior is not updated.

## Maintenance rules

- Add every new fixture capability ID to the scorecard before marking the related
  plan item complete.
- Do not mark a P0 capability as release-ready unless implementation, fixture or
  unit evidence, diagnostics, and release-blocker status are all recorded here.
- Keep P2/public parity claims out of the README until the stable-release checklist
  is complete.
