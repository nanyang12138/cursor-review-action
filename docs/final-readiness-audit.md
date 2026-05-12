# Final Product Readiness Audit

Capability IDs: `SUPPLY-CHAIN-P0`, `TRACEABILITY-SCORECARD-P0`,
`FIXTURE-HARNESS-P0`, `ACCEPTANCE-RUBRIC-P1`,
`COMPARISON-PROTOCOL-P1`, `DOCS-POSITIONING-P1`

This audit records the automation-owned final product hardening evidence for the
clean-room Cursor-native PR Agent engine. It is a readiness report for human
review; it does not authorize automation to merge, tag, publish, or release.

## Audit scope

- Date: 2026-05-12
- Goal PR: `#29` / `cursor/cursor-pr-agent-engine-goal-5865`
- Active phase: Final Product Hardening
- Selected milestone: release-readiness evidence audit
- Release policy: no auto-merge, no auto-release, no tag creation

## Release gate evidence

| Gate | Status | Evidence |
| --- | --- | --- |
| Fixture regression | Ready for human review | `tests/fixtures/README.md` records 20 concrete no-Cursor fixtures; `FIXTURE-HARNESS-P0` is tracked in `docs/parity-scorecard.md`. |
| Release blockers | Ready for human review | `docs/parity-scorecard.md` lists no unresolved P0 release blocker at the scorecard layer. |
| Compatibility | Ready for human review | README and `PR_AGENT_ENGINE_MAPPING.md` document stable action inputs, outputs, config keys, command behavior, diagnostics, and experimental surfaces. |
| Security model | Ready for human review | `docs/privacy-and-logging.md`, `docs/non-goals.md`, trigger fixtures, and `SEC-TRIGGER-P0` / `SEC-PRIVACY-P0` scorecard entries cover fork PR handling, author gating, redaction, and no default `pull_request_target`. |
| Supply chain | Ready for human review | `docs/dependencies.md`, `docs/release-checklist.md`, and `SUPPLY-CHAIN-P0` tests require a stdlib-only engine, supported action majors, and no committed caches or generated debug artifacts. |
| Cursor CLI diagnostics | Ready for human review | `CURSOR-RUNNER-P0` tests cover install, auth, model, runtime, timeout, and output failure diagnostics. |
| Dogfooding and acceptance | Ready for human review | The long-lived goal PR has been used as the self-review integration surface; every PR regression fixture has a `human_eval.md` record, and `docs/parity-reports/2026-05-12-initial-gap-log.md` records 12 clean-room comparison samples with acceptance-rubric fields. |
| Documentation | Ready for human review | README links the compatibility contract, release checklist, non-goals, local dry-run, privacy/logging, and user-facing command behavior without claiming full PR-Agent product parity. |
| Release notes | Ready for human review | `docs/release-notes.md` contains release target placeholders, capability IDs, verification evidence, known limitations, dependency and security notes, upgrade notes, and remaining human release gates. |

## Required verification commands

Before a maintainer creates any stable tag, run the strongest available no-Cursor
checks on the exact target commit:

```bash
python3 -m unittest tests/test_engine.py
python3 -m compileall scripts tests
git diff --check HEAD~1 HEAD
```

For this goal branch, the final hardening audit also supports a no-Cursor local
dogfooding dry-run of the PR branch against `origin/main`:

```bash
INPUT_BASE_SHA="$(git rev-parse origin/main)" \
INPUT_HEAD_SHA="$(git rev-parse HEAD)" \
INPUT_PR_NUMBER="29" \
INPUT_PR_TITLE="Continue cursor PR-agent engine goal" \
INPUT_BASE_REF="main" \
INPUT_HEAD_REF="cursor/cursor-pr-agent-engine-goal-5865" \
INPUT_EVENT_NAME="pull_request" \
INPUT_ENABLED_COMMANDS="review,ask,improve,describe" \
python3 scripts/cursor_review.py --dry-run
```

The dry-run must report `Cursor contacted: false`, parse deterministic stored or
synthetic output, render lifecycle and quality-gate diagnostics, and avoid
publishing a PR comment.

## Human release review checklist

Human maintainers still own the final stable release decision:

1. Review this audit, `docs/release-checklist.md`, `docs/release-notes.md`, and
   `docs/parity-scorecard.md` against the exact target commit.
2. Confirm no P0 blocker has reappeared after the final verification run.
3. Review the dogfooding and acceptance-rubric records for false positives,
   missed issues, evidence quality, diagnostics usefulness, and privacy safety.
4. Confirm known limitations and deferred non-goals remain accurate.
5. Manually create any stable tag or release only after human approval.

## Remaining automation work

- No remaining allowed implementation work is identified in the current plan
  layer after this audit.
- Remaining actions are human release-review actions only: final checklist
  review, optional live PR dogfooding rerun, stable tag selection, and release
  publication.
- Automation must continue to avoid auto-merge, auto-release, release tags, and
  destructive repository operations.
