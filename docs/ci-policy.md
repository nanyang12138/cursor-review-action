# CI Status Policy

Cursor Review Action separates action execution status from review opinion.

## Defaults

- Review comments are advisory and non-blocking.
- Findings do not fail CI by default, including high-severity findings.
- The action does not approve, merge, label, or otherwise enforce merge policy.
- The `ci-policy-json` output records the deterministic status decision for each
  run.

## `fail-on-error`

`fail-on-error` controls whether Cursor execution failures fail the workflow.

| Setting | Cursor exits 0 | Cursor exits non-zero |
| --- | --- | --- |
| `false` (default) | workflow succeeds | workflow succeeds with diagnostics |
| `true` | workflow succeeds | workflow fails with Cursor exit code |

Use `fail-on-error: true` only when the repository wants the automation itself
to be required. Cursor outages, authentication failures, timeout failures, and
model/runtime failures can then block the GitHub Actions job.

## `fail-on-findings`

`fail-on-findings` is intentionally not enforced yet.

The boolean input is preserved for compatibility, but setting it to `true`
currently produces `findings_gate_status: reserved_no_threshold` in
`ci-policy-json` and the rendered diagnostics. It does not fail the workflow.

Finding-based merge blocking needs a later explicit severity-threshold contract,
fixture evidence, grounding validation, same-run deduplication, and human
override guidance before it can be safe enough for stable use.

## Diagnostics

The rendered PR comment includes compact CI policy diagnostics:

- CI policy schema
- default policy
- `fail-on-error`
- `fail-on-findings`
- findings gate status
- workflow exit code
- high-severity finding count

The machine-readable output has the same data in `ci-policy-json`.

## Maintainer guidance

If a repository wants blocking behavior today, keep it outside this action:

1. Read the advisory review comment.
2. Let maintainers decide whether the PR should be blocked.
3. Use branch protection, required checks, or labels maintained by humans.

Do not treat an AI finding as a merge blocker without human review.
