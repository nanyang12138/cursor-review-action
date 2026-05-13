# Initial PR-Agent Comparison Gap Log

## Clean-room statement

This report records behavior-level comparison observations for the clean-room
Cursor-native engine. It does not copy PR-Agent source code, prompts, schemas,
tests, fixtures, exact generated output, or golden results.

## 2026-05-12 readiness refresh

This refresh updates the initial gap log against the current implementation
evidence on the long-lived cursor PR-agent engine branch. The sample suite uses
repository-owned synthetic fixtures and trigger fixtures only. PR-Agent behavior
is summarized as product-behavior classes so the report remains clean-room.

## Sample coverage

The comparison protocol requires at least 5 concrete samples before `v0.5` and
10-20 common or high-risk samples before `v1`. This report now covers 12
samples, meeting the lower bound for the `v1` comparison-sample gate without
claiming full PR-Agent product parity.

| Sample | Fixture | Command / path | PR-Agent behavior class | Cursor-native evidence | Gap disposition |
| --- | --- | --- | --- | --- | --- |
| sample-docs-only | `tests/fixtures/pr_regression/docs_only_no_findings` | review | Avoids noisy review comments when no actionable issue exists | No-finding review fixture renders compact diagnostics and passes the output quality gate | Completed backlog item: `OUTPUT-QUALITY-GATE-P0` |
| sample-security | `tests/fixtures/pr_regression/security_finding` | review | Surfaces concrete security risk with evidence | Structured review fixture covers taxonomy, severity, confidence, grounding, and publishable diagnostics | Completed backlog items: `FINDING-TAXONOMY-P0`, `FINDING-GROUNDING-P0` |
| sample-large-partial | `tests/fixtures/pr_regression/large_partial_review` | review | Explains partial coverage on large PRs | Budget-limited fixture renders reviewed/skipped coverage and human-eval notes | Completed backlog item: `ACCEPTANCE-RUBRIC-P1` |
| sample-ask | `tests/fixtures/pr_regression/ask_question` | ask | Answers the user's PR question without broad review | Ask fixture uses command-specific prompt/schema/rendering and static help documents command enablement | Completed backlog item: `HELP-DISCOVERABILITY-P1` |
| sample-describe | `tests/fixtures/pr_regression/describe_summary` | describe | Produces PR summary, risk, and test-plan style output | Describe fixture renders comment-only summary; metadata cache is validated separately for safe reuse | Deferred: PR body mutation, labels, and diagrams remain non-default |
| sample-improve-guidance | `tests/fixtures/pr_regression/improve_suggestions` | improve | Provides author-facing improvements without duplicating review findings | Improve fixture verifies command schema, repo guidance injection diagnostics, and quality-gate publish decision | Completed backlog items: `CMD-IMPROVE-P1`, `REPO-GUIDANCE-P1` |
| sample-invalid-output | `tests/fixtures/pr_regression/invalid_model_output` | review parser fallback | Recovers from malformed model output without publishing unsafe claims | Invalid-output fixture covers parser retry, markdown fallback, and diagnostic-only degradation | Completed backlog items: `PARSER-FALLBACK-P0`, `PARSER-RETRY-P1` |
| sample-empty-output | `tests/fixtures/pr_regression/empty_cursor_output` | review runner/parser fallback | Reports empty model output as a degraded run instead of silently succeeding | Empty-output fixture reports runner failure kind, parser reason, repair exhaustion, and partial publish decision | Completed backlog items: `CURSOR-RUNNER-P0`, `OUTPUT-QUALITY-GATE-P0` |
| sample-generated-lockfile | `tests/fixtures/pr_regression/generated_lockfile_skipped` | review diff selection | Avoids spending review budget on generated files while explaining skipped coverage | Generated/lockfile fixture records skipped-file reasons and keeps the selected source diff reviewable | Completed backlog item: `DIFF-GENERATED-P0` |
| sample-invalid-anchor | `tests/fixtures/pr_regression/invalid_finding_anchor` | review grounding | Does not present findings on unreviewed or ungrounded lines as high-confidence actionable review | Invalid-anchor fixture downgrades skipped-file claims and records invalid-anchor diagnostics | Completed backlog item: `FINDING-GROUNDING-P0` |
| sample-duplicate-findings | `tests/fixtures/pr_regression/duplicate_findings` | review dedup | Prevents duplicate lower-value findings from crowding out more severe issues | Duplicate fixture verifies fingerprinting, duplicate count, severity-aware sorting, and capped output | Completed backlog item: `FINDING-DEDUP-P0` |
| sample-config-only | `tests/fixtures/pr_regression/config_only_review` | review config change | Reviews configuration-only changes and reports effective configuration safely | Config-only fixture verifies repo config diagnostics and schema evidence without leaking PR body text | Completed backlog item: `CONFIG-SCHEMA-P1` |

## Gap disposition log

### GAP-2026-05-12-001

- Sample: sample-docs-only
- Gap: Early output rendering lacked a single deterministic publish decision for
  low-value findings, unsupported claims, schema diagnostics, grounding,
  deduplication, and redaction status.
- Evidence: `scripts/engine/quality_gate.py`, `docs/output-quality-gate.md`,
  `tests/fixtures/quality_gate/unsupported_claim`, and the PR regression
  fixtures record quality-gate decisions and publishable finding counts.
- Status: completed
- Decision: backlog
- Capability/status target: `output-quality-gate`, `OUTPUT-QUALITY-GATE-P0`
- Follow-up document or issue: `docs/output-quality-gate.md` and
  `scripts/engine/quality_gate.py`
- Release impact: Closed for the current stable-readiness audit; maintainers
  must still review the final release checklist before tagging.

### GAP-2026-05-12-002

- Sample: sample-security
- Gap: Early security findings needed deterministic taxonomy,
  severity/confidence normalization, selected-diff grounding, and review
  noise-control before `max_findings`.
- Evidence: `scripts/engine/taxonomy.py`, `scripts/engine/grounding.py`,
  `docs/finding-taxonomy.md`, `docs/finding-grounding.md`, and fixtures for
  security, invalid anchors, deleted-line anchors, and style-noise suppression.
- Status: completed
- Decision: backlog
- Capability/status target: `finding-taxonomy`, `FINDING-TAXONOMY-P0`,
  `FINDING-GROUNDING-P0`
- Follow-up document or issue: `docs/finding-taxonomy.md` and
  `docs/finding-grounding.md`
- Release impact: Closed for fixture-backed review findings; future inline
  publishing remains a deferred reporter-surface decision.

### GAP-2026-05-12-003

- Sample: sample-large-partial
- Gap: Partial coverage diagnostics needed human acceptance tracking for false
  positives, missed issues, evidence quality, diagnostics usefulness, and
  skipped-content transparency.
- Evidence: `docs/acceptance-rubric.md` defines the fields, and every
  `tests/fixtures/pr_regression/*/human_eval.md` record includes the rubric and
  fixture capability IDs.
- Status: completed
- Decision: backlog
- Capability/status target: `acceptance-rubric`, `ACCEPTANCE-RUBRIC-P1`
- Follow-up document or issue: `docs/acceptance-rubric.md`
- Release impact: Protocol gap closed for current fixtures; real PR dogfooding
  review remains a human stable-release gate.

### GAP-2026-05-12-004

- Sample: sample-ask
- Gap: `/cursor-ask` needed stable discoverability and command documentation
  before ask/improve/describe UX could be treated as release-gate evidence.
- Evidence: `scripts/engine/help.py`, README command documentation, static help
  rendering tests, and command-specific ask/improve/describe fixtures.
- Status: completed
- Decision: backlog
- Capability/status target: `help-discoverability`, `HELP-DISCOVERABILITY-P1`
- Follow-up document or issue: README command docs and static help renderer
- Release impact: Closed for opt-in command UX documentation. Commands other
  than review remain explicitly enabled by configuration.

### GAP-2026-05-12-005

- Sample: sample-describe
- Gap: PR-Agent-like PR body updates, labels, diagrams, and inline suggestions
  are intentionally outside the current comment-only describe surface.
- Evidence: `docs/non-goals.md`, README limitations, and
  `docs/metadata-cache.md` document the comment-only describe path and hidden
  metadata cache boundary.
- Status: deferred
- Decision: deferred
- Capability/status target: `metadata-cache`, `NON-GOALS-P0`,
  `DEFERRED-FEATURES-P1`, `PUB-DESCRIBE-BODY-P1`, `PUB-INLINE-P2`
- Follow-up document or issue: `docs/metadata-cache.md` and `docs/non-goals.md`
- Release impact: Not a blocker for comment-only stable readiness; release
  notes must not imply default PR body mutation, labels, diagrams, or inline
  publishing.

### GAP-2026-05-12-006

- Sample: all samples
- Gap: GitHub App server behavior, multi-platform providers, auto-fix flows,
  labels, ticket integrations, and full PR-Agent platform equivalence are beyond
  this action's clean-room Cursor-native engine.
- Evidence: `GOAL.md`, `PR_AGENT_ENGINE_MAPPING.md`, `docs/non-goals.md`, and
  README limitations classify these as non-goals or deferred P2 surfaces.
- Status: non-goal documented
- Decision: non-goal
- Capability/status target: `NON-GOALS-P0`, `DEFERRED-FEATURES-P1`
- Follow-up document or issue: `docs/non-goals.md`
- Release impact: Not a blocker when release notes preserve the documented
  limitations and avoid full PR-Agent parity claims.

### GAP-2026-05-12-007

- Sample: sample-invalid-output and sample-empty-output
- Gap: Parser and runner failures needed visible diagnostics and safe markdown
  fallback so malformed or empty Cursor output would not look like a successful
  high-confidence review.
- Evidence: `scripts/engine/parser.py`, `scripts/engine/runner.py`,
  `tests/fixtures/pr_regression/invalid_model_output`, and
  `tests/fixtures/pr_regression/empty_cursor_output` cover parser retry,
  fallback reason, empty-output diagnostics, and repair-budget exhaustion.
- Status: completed
- Decision: backlog
- Capability/status target: `PARSER-FALLBACK-P0`, `PARSER-RETRY-P1`,
  `CURSOR-RUNNER-P0`
- Follow-up document or issue: parser/runner tests and fixture inventory
- Release impact: Closed for no-Cursor regression evidence; live Cursor service
  incidents still require maintainer review of action logs.

### GAP-2026-05-12-008

- Sample: sample-generated-lockfile
- Gap: Generated assets and lockfiles could consume review budget and obscure
  the source files humans most need reviewed.
- Evidence: `scripts/engine/diff_selector.py` and
  `tests/fixtures/pr_regression/generated_lockfile_skipped` record
  `generated_or_lockfile` skip diagnostics while preserving selected source
  review context.
- Status: completed
- Decision: backlog
- Capability/status target: `DIFF-GENERATED-P0`, `DIFF-LARGE-P0`
- Follow-up document or issue: fixture inventory and diff selector tests
- Release impact: Closed for default generated/lockfile filtering; users can
  opt out through documented configuration.

### GAP-2026-05-12-009

- Sample: sample-invalid-anchor
- Gap: Findings referencing skipped files or lines outside the selected diff
  needed deterministic downgrade so they would not become high-confidence review
  findings or CI-gating input.
- Evidence: `scripts/engine/diff_index.py`, `scripts/engine/grounding.py`,
  `docs/finding-grounding.md`, and invalid-anchor/deleted-line fixtures.
- Status: completed
- Decision: backlog
- Capability/status target: `DIFF-INDEX-P0`, `FINDING-GROUNDING-P0`,
  `OUTPUT-QUALITY-GATE-P0`
- Follow-up document or issue: grounding docs and fixture inventory
- Release impact: Closed for summary-comment findings. Inline comment placement
  remains out of the current stable surface.

### GAP-2026-05-12-010

- Sample: sample-duplicate-findings
- Gap: Same-run duplicate findings needed normalization, fingerprinting,
  severity/confidence/grounding ordering, and capping before `max_findings`
  was applied.
- Evidence: `scripts/engine/findings.py`,
  `tests/fixtures/pr_regression/duplicate_findings`, rendered diagnostics for
  duplicate counts, and findings JSON fingerprints.
- Status: completed
- Decision: backlog
- Capability/status target: `FINDING-DEDUP-P0`, `FINDING-GROUNDING-P0`
- Follow-up document or issue: finding dedup tests and fixture inventory
- Release impact: Closed for same-run deduplication; cross-run suppression is
  not part of the current product goal.

### GAP-2026-05-12-011

- Sample: sample-config-only
- Gap: Configuration-only changes and invalid repo config needed safe schema
  evidence, unknown-key diagnostics, fallback diagnostics, and a documented
  repo-local config surface.
- Evidence: `scripts/engine/config.py`, `.cursor-review.schema.json`,
  `tests/fixtures/pr_regression/config_only_review`, and
  `tests/fixtures/config_invalid/bad_values`.
- Status: completed
- Decision: backlog
- Capability/status target: `CONFIG-SCHEMA-P1`
- Follow-up document or issue: `.cursor-review.schema.json` and
  `docs/config-migration.md`
- Release impact: Closed for the stable repo-local config surface; workflow-only
  metadata remains action-input driven.

### GAP-2026-05-12-012

- Sample: fork and untrusted-command trigger fixtures
- Gap: Untrusted triggers, fork PRs without secrets, and issue comments from
  untrusted associations needed a pre-Cursor trust decision.
- Evidence: `scripts/engine/trust_policy.py`, `docs/trigger-policy.md`, and
  `tests/fixtures/triggers/{fork_pr_without_secret,trusted_issue_comment,untrusted_issue_comment}.json`.
- Status: completed
- Decision: backlog
- Capability/status target: `SEC-TRIGGER-P0`
- Follow-up document or issue: trigger policy docs and trigger fixtures
- Release impact: Closed for default trigger-safety policy. Advanced
  `pull_request_target` behavior remains outside default examples.

## Human acceptance rubric summary

The detailed fixture-level records live in
`tests/fixtures/pr_regression/*/human_eval.md`. This comparison refresh records
the same rubric dimensions in aggregate for the 12 samples above:

- real_issue_found: mixed by scenario; actionable bug, security, test-gap, and
  maintainability samples record real issues, while docs-only/config-only and
  degraded-output samples are intentionally diagnostic.
- false_positive_count: 0 known false positives in the fixture expectations.
- missed_issue_count: 0 known fixture-defined missed issues.
- evidence_quality: 3 for anchored finding samples; 2-3 for diagnostic-only
  degraded-output samples where no actionable finding should be published.
- command_intent_respected: yes for review, ask, improve, describe, parser
  fallback, and trigger-safety scenarios.
- output_conciseness: 2-3; large/partial and diagnostics-heavy cases prioritize
  transparent coverage over minimal output.
- diagnostics_usefulness: 3 for coverage, parser, quality-gate, config,
  grounding, dedup, and trigger trust scenarios covered by fixtures.
- skipped_content_transparency: 3 where generated files, large PR budgets, fork
  trust decisions, or invalid anchors are part of the scenario; not_applicable
  for fully reviewed small diffs.
- follow_up_action: none for completed fixture-backed gaps; docs/non_goal for
  intentionally deferred PR body mutation, inline publishing, GitHub App,
  multi-platform, labels, ticket integration, and full PR-Agent parity claims.

## Stable-release readiness note

This report closes the stale comparison-report gaps that were already resolved
by implementation and fixture evidence, and it satisfies the comparison-sample
volume floor for `v1`. It does not authorize an automated release. Stable
release readiness still requires human review of the release checklist, final PR
dogfooding evidence, release notes, and the no-auto-release policy.
