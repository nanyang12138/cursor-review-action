# Release Checklist

Capability ID: `SUPPLY-CHAIN-P0`

This checklist gates human-reviewed releases. It documents readiness; it does
not authorize automation to merge, tag, publish, or release.

## Release authority

- Never auto-merge release PRs.
- Never auto-create release tags.
- A maintainer must review release evidence before any stable tag is created.
- Clean-room boundaries remain mandatory: do not copy PR-Agent source code,
  prompts, schemas, tests, fixtures, or generated outputs as golden truth.

## Required checks before a stable tag

| Gate | Required evidence |
| --- | --- |
| Fixture regression | No-Cursor tests pass and fixture inventory meets the release target. |
| Release blockers | `docs/parity-scorecard.md` has no unresolved P0 blocker for the target release. |
| Compatibility | Action inputs, outputs, config keys, command behavior, diagnostics keys, and schema versions are reviewed for compatibility. |
| Security model | Trigger trust, fork PR handling, secret redaction, and debug artifact defaults are verified. |
| Supply chain | `scripts/` remains stdlib-only or every exception is documented in `docs/dependencies.md`. |
| Dependency versions | Example workflows use supported `actions/checkout` and `actions/github-script` major versions. |
| Action reference | Stable public examples use a maintained tag such as `@v1`, not `@main`. |
| Cursor CLI | Installer and runner failure diagnostics are still covered by tests. |
| Dogfooding | Human acceptance rubric records are reviewed for false positives, missed issues, evidence quality, and diagnostics usefulness. |
| Documentation | README, troubleshooting, local dry-run, privacy/logging, CI policy, and non-goals are current. |
| Release notes | `docs/release-notes.md` lists capability IDs, known limitations, dependency risks, and deferred non-goals. |

Use `docs/final-readiness-audit.md` as the automation-produced evidence index
when reviewing these gates for the first stable release. It does not replace
maintainer review and does not authorize automation to create tags or releases.

## Pre-stable references

Before the first stable release, README examples may use:

```yaml
uses: nanyang12138/cursor-review-action@main
```

That reference must be described as pre-stable. After a stable release, public
onboarding examples should prefer:

```yaml
uses: nanyang12138/cursor-review-action@v1
```

## Supply-chain review steps

1. Run the stdlib-only import scan through the unit tests.
2. Check that no dependency caches, virtual environments, Cursor CLI downloads,
   or generated debug artifacts are staged.
3. Review any changes to `scripts/install-cursor.sh`, `action.yml`, workflow
   examples, or GitHub token permissions.
4. Confirm `docs/dependencies.md` lists all runtime dependency surfaces.
5. Confirm release notes mention dependency or installer risks that remain.

## Release notes minimum fields

- Release tag and target commit.
- Capability IDs completed since the previous release.
- Tests and fixture suites run.
- Known limitations and deferred non-goals.
- Dependency and supply-chain changes.
- Security or privacy changes.
- Upgrade notes for action inputs, outputs, config keys, and schema versions.

Use `docs/release-notes.md` as the pre-stable draft. It remains advisory until a
maintainer reviews the exact target commit and manually creates a release.
