# Non-Goals and Deferred Features

Capability IDs: `NON-GOALS-P0`, `DEFERRED-FEATURES-P1`

This document keeps the clean-room Cursor-native PR Agent engine focused on the
stable review product. It documents what is intentionally not part of the v1
surface, why it is deferred or out of scope, and what evidence is required before
the decision can be revisited.

These decisions do not prohibit future work. They prevent accidental scope creep,
public parity claims, or high-risk features from being added without fixtures,
diagnostics, and release-gate evidence.

## Rules for deferred work

- Do not auto-merge, auto-release, create tags, or publish releases from this
  automation.
- Do not copy PR-Agent source code, prompts, schemas, tests, fixtures, or golden
  outputs.
- Do not expose raw prompts, raw diffs, token-like strings, or secrets in logs,
  PR comments, or release notes.
- Do not change public action inputs, outputs, command behavior, or diagnostics
  silently.
- Classify new feature requests as P0, P1, P2, or out-of-scope before
  implementation.
- Require at least one no-Cursor test, fixture, diagnostic check, or documented
  dogfooding record before moving a deferred feature into implementation.

## v1 non-goals and deferred features

| Feature | Classification | v1 decision | Reason | Revisit evidence required |
| --- | --- | --- | --- | --- |
| GitHub App server or app identity | P2 after stable v1 | Do not implement for v1 | Requires a different permission model, app installation flow, webhook security model, and deployment surface. | Security design, app permission matrix, fork/untrusted trigger fixtures, and maintainer approval for a hosted or app-based surface. |
| Multi-platform providers such as GitLab, Bitbucket, Azure DevOps, or Gitea | Out of scope | Do not implement | The current engine is GitHub Actions-specific and depends on GitHub PR metadata, comments, and tokens. | A separate provider abstraction plan and dedicated fixtures for every supported platform. |
| Auto-fix, auto-commit, or automatic code modification | Out of scope for v1 | Do not implement | The stable product goal is advisory review, not autonomous code mutation. Auto-fix would need write permissions, safety review, rollback behavior, and human approval semantics. | Explicit product approval, safety model, patch review workflow, and fixtures proving no untrusted input can modify code. |
| Full inline comments or inline suggestions | P2 after stable v1 | Do not implement for v1 | Summary comments and structured findings already provide safer review output. Inline publishing requires exact GitHub line anchors, outdated diff handling, batching, and fallback behavior. | Reporter contract, anchor fixtures for new/old/renamed/deleted lines, GitHub API failure diagnostics, and noise-control dogfooding. |
| Labels derived from findings or taxonomy | P2 after stable v1 | Do not implement for v1 | Labels can affect maintainer workflows and branch policies. The current action remains advisory and non-blocking by default. | Label policy docs, opt-in config, taxonomy confidence thresholds, and tests proving labels are never applied by default. |
| Blocking merge policies based on findings | P2 after stable v1 | Do not implement for v1 | Findings can be wrong and must remain subject to human judgment. `fail-on-findings` is reserved until a stricter severity-threshold contract exists. | CI policy update, threshold config, fixture evidence for high-confidence findings, and documented human override path. |
| `/cursor-describe` PR body mutation by default | Deferred from v1 default surface | Keep comment-only describe output | Updating the PR body risks overwriting human-authored content. The current stable behavior should not mutate author text. | User-content preservation marker design, opt-in config, compatibility tests, and rollback behavior for GitHub API failures. |
| Multi-call chunking for huge PRs | P2 after stable v1 | Do not implement for v1 | Multiple Cursor calls increase cost, latency, retry complexity, and nondeterminism. The v1 path uses one call with explicit partial-review diagnostics. | Budget policy, per-chunk fixtures, dedup across chunks, timeout tests, and cost diagnostics. |
| Second Cursor critique call or multi-model consensus | P2 after stable v1 | Do not implement for v1 | Deterministic local quality gates are required before adding expensive or nondeterministic self-critique flows. | Quality-gate baseline metrics, budget controls, fixtures showing measurable false-positive reduction, and explicit opt-in config. |
| Persistent finding suppression or "ignore this finding" state | P2 after stable v1 | Do not implement for v1 | Same-run deduplication is enough for v1. Persistent suppression requires identity, storage, stale-state handling, and clear auditability. | Storage design, stale suppression diagnostics, maintainer controls, and fixtures for repeated PR updates. |
| Organization-level or global config repository | P2 after stable v1 | Do not implement for v1 | Repository-local `.cursor-review.yml` is simpler, auditable, and enough for the current action surface. | Config precedence design, provenance diagnostics, failure behavior, and tests for repo/org override conflicts. |
| Ticket system or external issue/customer context integration | P2 or out of scope unless explicitly selected later | Do not implement for v1 | External systems introduce authentication, privacy, rate limits, and unsupported-claim risks. | Product decision, privacy review, connector-specific fixtures, and diagnostics proving external claims are attributed. |
| Ask on images or non-code media review | Out of scope | Do not implement | The current context builder, fixtures, and Cursor prompt contracts are text/diff-based. | A separate media-context design and fixtures that do not rely on copied external tool behavior. |
| Docs smart search or broad knowledge-base lookup | Out of scope | Do not implement | The action should review PR context and repository guidance, not become a general documentation search product. | Separate product scope and privacy model. |
| Public "full PR-Agent parity" claims | Out of scope | Do not publish | This project is clean-room and Cursor-native. It can claim documented behavioral parity for implemented capability IDs, not full product equivalence. | Completed scorecard, fixture regression, dogfooding evidence, and maintainer-reviewed release notes with limitations. |
| `pull_request_target` default workflow support | Out of scope for default examples | Do not use by default | `pull_request_target` can expose secrets to untrusted code when combined with unsafe checkout patterns. | Separate advanced security documentation, explicit opt-in examples, and fork PR threat-model fixtures. |

## Revisit process

Before implementing a deferred feature:

1. Add or update the capability mapping with the target parity level.
2. Record the reason the feature is moving from non-goal/deferred into backlog.
3. Add tests or fixtures before enabling public behavior.
4. Add diagnostics that explain the feature's decision path without exposing raw
   prompts, raw diffs, secrets, or token-like strings.
5. Update the README only after behavior is implemented and verified.
6. Keep default behavior advisory, non-blocking, comment-safe, and clean-room.

## Compatibility note

The current README describes a GitHub Actions based, Cursor CLI powered advisory
review action. It does not promise GitHub App behavior, automatic fixes, inline
comments, labels, ticket integration, multi-platform support, or full PR-Agent
product equivalence. Those limitations are intentional until the relevant
capability IDs have implementation, tests or fixtures, diagnostics, and
maintainer-reviewed release evidence.
