# Cursor Review Action Goal

This repository is working toward a clean-room Cursor-native PR Agent engine.

## Primary Plan Files

Cloud Automations must read these files first:

1. `PR_AGENT_ENGINE_MAPPING.md`
2. `docs/plans/cursor-pr-agent-engine.plan.md`

## Goal

Upgrade `cursor-review-action` from a lightweight GitHub Action into a clean-room Cursor-native PR Agent engine.

The design may learn from PR-Agent's public product behavior and engine concepts, but must not copy PR-Agent source code, prompts, schemas, tests, fixtures, or implementation details.

Cursor CLI / Cursor Agent remains the AI execution layer.

## Current Mode

Product Completion Mode.

The automation should continue until the final product goal is complete. It should not stop at P0, P1, or the first stable release gate if the plan still allows final-product work.

Phase order:

1. Phase 1: Engine Split
2. Phase 2: Context and Diff Upgrade
3. Phase 3: Command Templates and Schemas
4. Phase 4: Parser Retry and Publisher Strategy
5. Phase 5: Regression Harness
6. Phase 6: Stability and Release Gates
7. Final Product Hardening

At the start of each run, inspect:

- `GOAL.md`
- `PR_AGENT_ENGINE_MAPPING.md`
- `docs/plans/cursor-pr-agent-engine.plan.md`
- Current git state
- Existing goal branches and open PRs
- Available tests and lints

Select the earliest phase that is not complete. Within that phase, select one coherent milestone.

Do not start a later phase until the current phase has:

- Implementation complete for its required scope
- Tests or fixtures updated where required
- Diagnostics updated where required
- Docs, plan, or parity scorecard updated where evidence supports it
- Existing open goal PR updated, or the current branch clean and ready for review

If a phase is complete, advance to the next phase automatically.

If an open PR for this goal already exists, continue updating that PR or its branch instead of creating unrelated PRs. Do not block forever waiting for a PR to merge when more work can safely continue on the same goal branch.

After P0 is complete, continue to P1. After P1 is complete, continue to selected P2/final hardening work only when the plan or parity mapping marks it as required for the final product experience or when it is needed to close release, security, dogfooding, compatibility, or documentation gaps.

Phase 1 guardrails:

- Refactor `scripts/cursor_review.py` into clean engine modules.
- Preserve existing `/cursor-review` behavior and public action inputs/outputs.
- Add module boundaries for command, config, context, diff, prompt, runner, parser, and render.
- Add no-Cursor regression tests for current behavior where practical.
- Add only lightweight interfaces or skeletons for future P0 verifier layers if needed.

Global deferrals unless explicitly allowed by the current phase, the plan, or final-product hardening:

- Inline comments
- PR body update
- Multi-call chunking
- Second Cursor critique
- Multi-model consensus
- GitHub App
- Release or tagging

## Automation Rules

- Execute one coherent milestone per run.
- A milestone may include multiple tightly related files or tasks when they share the same capability IDs and can be tested together.
- Do not mix unrelated phases in one run.
- Prefer pending P0 tasks before P1.
- After P0 is complete, continue to P1.
- After P1 is complete, continue to selected P2/final hardening work only when it is required for the final product and does not violate security, cost, release, or clean-room constraints.
- Do not implement unrelated P2 features just because they exist in the backlog.
- Do not create releases.
- Do not merge PRs.
- Do not silently change public action behavior.
- Preserve existing `/cursor-review` behavior unless the selected milestone explicitly changes it.
- Run available no-Cursor tests and lints.
- Update docs, plan, or parity scorecard only when evidence supports it.
- Stop and write a blocker report if requirements are ambiguous, tests fail repeatedly, or security boundaries are unclear.

## Per-Run Process

1. Inspect current git state and any existing goal branch or PR.
2. Read the primary plan files.
3. Select the earliest incomplete phase and the next highest-priority coherent milestone allowed by that phase.
4. Implement only that milestone.
5. Add or update focused tests and fixtures.
6. Run available tests and lints.
7. Update planning docs only when evidence supports the update.
8. Commit changes to the goal branch and open or update a PR.
9. Summarize completed capability IDs, evidence, tests, and remaining blockers.

## Stop Condition

Continue executing until the final product goal is complete.

The final product goal is complete only when:

- All P0 capabilities have implementation, fixture coverage, diagnostics, and release-gate evidence.
- All P1 capabilities required for stable PR-Agent-like product behavior are implemented or explicitly downgraded with evidence.
- Selected P2 capabilities that are necessary for the final product experience are implemented or explicitly marked as deferred non-goals.
- Fixture regression, release gates, security model, compatibility contract, dogfooding loop, and documentation are complete.
- The action is ready for a human-reviewed stable release.

Do not stop merely because P0 is complete.
Do not stop merely because v1 gates are complete if this file or the plan still lists allowed final-product work.
Only stop when `GOAL.md`, `PR_AGENT_ENGINE_MAPPING.md`, and `docs/plans/cursor-pr-agent-engine.plan.md` indicate no remaining allowed implementation work.

Never auto-merge or auto-release. Report readiness for human review instead.
