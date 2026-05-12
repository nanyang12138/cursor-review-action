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

## Current Slice

Execute Phase 1: Engine Split only.

Scope:

- Refactor `scripts/cursor_review.py` into clean engine modules.
- Preserve existing `/cursor-review` behavior and public action inputs/outputs.
- Add module boundaries for command, config, context, diff, prompt, runner, parser, and render.
- Add no-Cursor regression tests for current behavior where practical.
- Add only lightweight interfaces or skeletons for future P0 verifier layers if needed.

Do not implement in this slice:

- `/cursor-ask`
- `/cursor-improve`
- `/cursor-describe`
- Inline comments
- PR body update
- Multi-call chunking
- Second Cursor critique
- Multi-model consensus
- GitHub App
- Release or tagging

## Automation Rules

- Execute only one bounded slice per run.
- Prefer pending P0 tasks before P1.
- Do not implement P2 features unless all P0/P1 gates explicitly allow it.
- Do not create releases.
- Do not merge PRs.
- Do not silently change public action behavior.
- Preserve existing `/cursor-review` behavior unless the current slice explicitly changes it.
- Run available no-Cursor tests and lints.
- Update docs, plan, or parity scorecard only when evidence supports it.
- Stop and write a blocker report if requirements are ambiguous, tests fail repeatedly, or security boundaries are unclear.

## Per-Run Process

1. Inspect current git state and any existing goal branch or PR.
2. Read the primary plan files.
3. Select the next highest-priority task allowed by the current slice.
4. Implement only that slice.
5. Add or update focused tests and fixtures.
6. Run available tests and lints.
7. Update planning docs only when evidence supports the update.
8. Commit changes to the goal branch and open or update a PR.
9. Summarize completed capability IDs, evidence, tests, and remaining blockers.

## Stop Condition

Stop when all P0 parity items have implementation, fixture coverage, diagnostics, and release-gate evidence. Report readiness for human review instead of continuing into P2 work.
