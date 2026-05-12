# Pre-Stable Release Notes Draft

Capability IDs: `SUPPLY-CHAIN-P0`, `TRACEABILITY-SCORECARD-P0`,
`DOCS-POSITIONING-P1`, `NON-GOALS-P0`

These release notes are maintainer-facing draft evidence for the first stable
Cursor Review Action release. They do not authorize automation to merge, tag,
publish, or release. A maintainer must review the final checklist and choose the
release tag and target commit.

## Release target

- Release tag: `TBD by maintainer`
- Target commit: `TBD by maintainer`
- Release authority: human-reviewed only
- Automation policy: no auto-merge, no auto-release, no tag creation

## Completed capability IDs

The current scorecard records implementation, fixture or unit evidence,
diagnostics, and release-blocker status for these stable-release surfaces:

- P0 review engine: `CMD-REVIEW-P0`, `CTX-METADATA-P0`, `DIFF-LARGE-P0`,
  `DIFF-GENERATED-P0`, `DIFF-INDEX-P0`, `PROMPT-REVIEW-P0`,
  `PARSER-FALLBACK-P0`, `PUB-PERSISTENT-P0`, `CURSOR-RUNNER-P0`
- P0 quality and safety: `FINDING-GROUNDING-P0`, `FINDING-DEDUP-P0`,
  `OUTPUT-QUALITY-GATE-P0`, `FINDING-TAXONOMY-P0`, `CI-POLICY-P0`,
  `SEC-TRIGGER-P0`, `SEC-PRIVACY-P0`
- P0 product gates: `LOCAL-DRY-RUN-P0`, `LOCALIZATION-P0`,
  `FIXTURE-HARNESS-P0`, `TRACEABILITY-SCORECARD-P0`, `NON-GOALS-P0`,
  `SUPPLY-CHAIN-P0`
- P1 stable-product support: `CMD-ASK-P1`, `CMD-IMPROVE-P1`,
  `CMD-DESCRIBE-P1`, `PARSER-COMMAND-SCHEMA-P1`, `PARSER-RETRY-P1`,
  `SCHEMA-EVOLUTION-P1`, `METADATA-CACHE-P1`, `HUMAN-WORKFLOW-P1`,
  `CONFIG-SCHEMA-P1`, `ACCEPTANCE-RUBRIC-P1`, `BUDGET-CONTROLS-P1`,
  `COMPARISON-PROTOCOL-P1`, `PROMPT-GOVERNANCE-P1`,
  `REPO-GUIDANCE-P1`, `HELP-DISCOVERABILITY-P1`,
  `DOCS-POSITIONING-P1`

## Verification evidence

- No-Cursor unit tests cover command routing, config loading, context
  construction, diff selection, prompt rendering, parser fallback, grounding,
  finding deduplication, output quality gates, rendering, local dry-run,
  trigger trust, privacy redaction, supply-chain checks, and documentation
  contracts.
- Fixture regression includes 20 concrete no-Cursor cases across normal review,
  command-specific output, large/partial coverage, generated-file skipping,
  invalid anchors, deleted-line evidence, duplicate findings, config-only
  changes, invalid config, parser fallback, empty output, quality-gate
  downgrade, and untrusted trigger policy.
- `docs/parity-scorecard.md` is the release-blocker authority for capability
  status. It intentionally avoids public full PR-Agent parity claims.
- `docs/parity-reports/2026-05-12-initial-gap-log.md` records clean-room
  behavior-level comparison evidence and gap dispositions.

## Known limitations and deferred non-goals

The stable surface is a Cursor-native GitHub Action that publishes advisory
summary comments. The following features are intentionally not part of the v1
default surface unless a later maintainer-reviewed plan promotes them:

- GitHub App server or app identity.
- Multi-platform providers outside GitHub Actions.
- Auto-fix, auto-commit, or automatic code mutation.
- Full inline comments or inline suggestions.
- Labels derived from findings or taxonomy.
- Blocking merge policies based on findings.
- Default `/cursor-describe` PR body mutation.
- Multi-call chunking for huge PRs.
- Second Cursor critique calls or multi-model consensus.
- Persistent cross-run finding suppression state.
- Organization-level config repositories.
- Ticket, customer, or external issue context integrations.
- Full PR-Agent product equivalence claims.

See `docs/non-goals.md` for revisit evidence required before implementing any
deferred feature.

## Dependency and supply-chain notes

- The Python engine under `scripts/` remains stdlib-only by policy.
- Cursor execution continues to depend on the Cursor CLI installed by
  `scripts/install-cursor.sh`; installer and runner failures must stay
  diagnostic rather than silent.
- Example workflows use supported GitHub Action majors:
  `actions/checkout@v4` and `actions/github-script@v7`.
- Pre-stable examples may reference
  `nanyang12138/cursor-review-action@main`. Stable public examples should use a
  maintainer-created tag such as `nanyang12138/cursor-review-action@v1`.
- Generated caches, virtual environments, downloaded CLIs, debug artifacts, and
  copied PR-Agent source, prompts, schemas, tests, or fixtures must not be
  committed.

## Security and privacy notes

- Trigger trust is evaluated before context construction or Cursor calls.
- Fork PRs without secrets and untrusted issue comments skip Cursor calls by
  default and produce diagnostics.
- Published comments are advisory and non-blocking by default; the action does
  not approve, merge, or create releases.
- Raw prompts, raw diffs, token-like strings, and secrets must not appear in PR
  comments, Actions logs, or release notes.
- Redaction failures block raw comment publishing.
- Unsupported external claims are downgraded before publishing.

## Upgrade and compatibility notes

- Stable action inputs, outputs, config keys, diagnostics keys, and schema
  versions are governed by the compatibility contract in
  `PR_AGENT_ENGINE_MAPPING.md` and README.
- `/cursor-review` remains the default command. `/cursor-ask`,
  `/cursor-improve`, and `/cursor-describe` remain opt-in experimental command
  surfaces until maintainers promote them.
- The current output schema is `cursor-review-action/v1`; unsupported schema
  versions enter retry or fallback with diagnostics.
- `language` affects human-readable content only and does not localize JSON
  schema keys or diagnostics keys.

## Remaining human release gates

- Review `docs/release-checklist.md` against the exact target commit.
- Review dogfooding and human acceptance rubric records for false positives,
  missed issues, evidence quality, and diagnostics usefulness.
- Confirm no unresolved P0 blocker remains in `docs/parity-scorecard.md`.
- Confirm final release notes preserve known limitations and deferred non-goals.
- Manually create any stable tag or release only after human approval.
