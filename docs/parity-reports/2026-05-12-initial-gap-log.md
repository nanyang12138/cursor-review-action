# Initial PR-Agent Comparison Gap Log

## Clean-room statement

This report records behavior-level comparison observations for the clean-room
Cursor-native engine. It does not copy PR-Agent source code, prompts, schemas,
tests, fixtures, or exact generated output.

## Sample coverage

The initial comparison suite uses repository-owned synthetic fixtures. PR-Agent
behavior is described only as a product-behavior class.

| Sample | Fixture | Command | PR-Agent behavior class | Cursor-native evidence | Gaps |
| --- | --- | --- | --- | --- | --- |
| sample-docs-only | `tests/fixtures/pr_regression/docs_only_no_findings` | review | Avoids noisy review comments when no actionable issue exists | No-finding review fixture renders a compact result | Quality gate still needed for deterministic suppression policy |
| sample-security | `tests/fixtures/pr_regression/security_finding` | review | Surfaces concrete security risk with evidence | Structured review fixture renders a high-risk finding | Taxonomy and grounding are not yet enforced |
| sample-large-partial | `tests/fixtures/pr_regression/large_partial_review` | review | Explains partial coverage on large PRs | Budget-limited fixture renders reviewed/skipped diagnostics | No comparison acceptance rubric yet |
| sample-ask | `tests/fixtures/pr_regression/ask_question` | ask | Answers the user's PR question without broad review | Ask fixture uses command-specific schema and rendering | Command remains opt-in pending stable UX evidence |
| sample-describe | `tests/fixtures/pr_regression/describe_summary` | describe | Produces PR summary, walkthrough, risk, and test plan style output | Describe fixture renders comment-only summary | PR body update, labels, and diagrams are deferred |

## Gap log

### GAP-2026-05-12-001

- Sample: sample-docs-only
- Gap: Cursor-native output can currently render parsed content without a single
  deterministic publish decision that suppresses low-value or unsupported
  findings.
- Evidence: `docs/plans/cursor-pr-agent-engine.plan.md` still lists
  `output-quality-gate` as pending.
- Decision: backlog
- Capability/status target: `output-quality-gate`, `OUTPUT-QUALITY-GATE-P0`
- Follow-up document or issue: `docs/output-quality-gate.md` and
  `scripts/engine/quality_gate.py`
- Release impact: Required before stable release readiness.

### GAP-2026-05-12-002

- Sample: sample-security
- Gap: Security findings are parsed and rendered, but stable taxonomy,
  severity/confidence normalization, and noise-control rules are not enforced
  before `max_findings`.
- Evidence: implemented in `scripts/engine/taxonomy.py` and
  `docs/finding-taxonomy.md`; fixtures cover security taxonomy and review
  noise-control downgrade. Grounding, dedup, and output quality gate remain
  separate backlog gaps.
- Decision: backlog
- Capability/status target: `finding-taxonomy`, `FINDING-TAXONOMY-P0`
- Follow-up document or issue: `scripts/engine/taxonomy.py` and
  `docs/finding-taxonomy.md`
- Release impact: Required before stable release readiness.

### GAP-2026-05-12-003

- Sample: sample-large-partial
- Gap: Partial coverage diagnostics exist, but there is no human acceptance
  rubric for comparing false positives, missed issues, evidence quality, and
  usefulness across comparison runs.
- Evidence: `acceptance-rubric` remains pending in the plan.
- Decision: backlog
- Capability/status target: `acceptance-rubric`, `ACCEPTANCE-RUBRIC-P1`
- Follow-up document or issue: `docs/acceptance-rubric.md`
- Release impact: Required for final product hardening and dogfooding evidence.

### GAP-2026-05-12-004

- Sample: sample-ask
- Gap: `/cursor-ask` has a command-specific schema, but it remains opt-in until
  help/discoverability and stable command documentation are in place.
- Evidence: `help-discoverability` remains pending in the plan.
- Decision: backlog
- Capability/status target: `help-discoverability`, `HELP-DISCOVERABILITY-P1`
- Follow-up document or issue: README command docs and static help renderer.
- Release impact: Required before promoting ask/improve/describe UX as stable.

### GAP-2026-05-12-005

- Sample: sample-describe
- Gap: PR-Agent-like body updates, labels, diagrams, and inline suggestions are
  intentionally not part of the current comment-only describe implementation.
- Evidence: GOAL.md lists inline comments and PR body update as global deferrals
  unless specifically allowed; the plan keeps labels and inline suggestions as
  P2 or out of initial scope.
- Decision: deferred
- Capability/status target: `metadata-cache`, `non-goals`,
  `PUB-DESCRIBE-BODY-P1`, `PUB-INLINE-P2`
- Follow-up document or issue: `docs/metadata-cache.md` and `docs/non-goals.md`
- Release impact: Not a blocker for comment-only describe; must remain clearly
  documented before stable release.

### GAP-2026-05-12-006

- Sample: all samples
- Gap: GitHub App server behavior, multi-platform providers, auto-fix flows, and
  ticket integrations are outside this action's clean-room Cursor-native engine.
- Evidence: GOAL.md and PR_AGENT_ENGINE_MAPPING.md list these capabilities as
  global deferrals or out of scope.
- Decision: non-goal
- Capability/status target: `non-goals`
- Follow-up document or issue: `docs/non-goals.md`
- Release impact: Must be documented so final release notes do not imply full
  PR-Agent platform parity.

## Next comparison samples

- Improve suggestion fixture covering author-facing recommendations.
- Invalid model output fixture covering repair retry and markdown downgrade.
- Fork PR trigger fixture covering safe skip diagnostics.
- Repo-guidance fixture once `.cursor-review-instructions.md` is implemented.
- Grounding fixture covering valid, file-only, and invalid anchors.
