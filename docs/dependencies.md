# Dependency Inventory

Capability ID: `SUPPLY-CHAIN-P0`

Cursor Review Action keeps its clean-room engine dependency surface deliberately
small. The Python engine is stdlib-only unless a future dependency has a clear
stability or security payoff and is reviewed through the release checklist.

## Runtime dependency inventory

| Surface | Dependency | Purpose | Policy |
| --- | --- | --- | --- |
| Python engine | Python standard library | Command parsing, config loading, diff selection, prompts, parsing, rendering, diagnostics, and dry-run | No third-party imports in `scripts/` by default. |
| AI execution | Cursor CLI / `agent` | Executes the generated Cursor-native review prompt | Installed by `scripts/install-cursor.sh` when `install-cursor: true`; failures are diagnosed by the runner contract. |
| GitHub workflow checkout | `actions/checkout@v4` | Checks out the PR head SHA in example workflows | Keep on a supported major version; review before changing. |
| PR metadata and comments | `actions/github-script@v7` | Resolves PR metadata and creates or updates PR comments | Keep on a supported major version; do not grant broader token permissions than required. |
| Shell tools | `git`, `bash`, `python3` on `ubuntu-latest` | Builds local diffs and runs the composite action | Document failures in troubleshooting before stable release. |

## Stdlib-only engine rule

- New engine code under `scripts/` must use Python stdlib modules or internal
  `engine.*` modules only.
- Adding a third-party Python package requires:
  - a written rationale in this file;
  - license and maintenance review;
  - a package-manager managed lock or pin strategy;
  - focused tests that fail without the dependency behavior;
  - release checklist acknowledgement.
- Generated dependency caches, virtual environments, downloaded CLIs, and debug
  artifacts must not be committed.

The unit test suite scans Python imports through
`scripts/engine/supply_chain.py` so accidental third-party imports are caught
without contacting external services.

## Action reference policy

- Before the first stable release, README examples may use
  `nanyang12138/cursor-review-action@main` and must clearly state that this is a
  pre-stable reference.
- Stable release examples must use a maintained tag such as
  `nanyang12138/cursor-review-action@v1`.
- A pinned commit SHA is acceptable for audited internal examples, but public
  onboarding should prefer a maintained version tag after stable release.
- Do not use unreviewed branch names in stable documentation.

## Dependency update policy

Dependency changes are treated as product changes because they can affect the
security model, runtime compatibility, and release reproducibility.

For each dependency update:

1. Record the reason for the update in the PR description or release notes.
2. Re-run no-Cursor unit tests and local dry-run checks.
3. Verify examples still use supported GitHub Action major versions.
4. Re-check the release checklist before tagging a stable release.
5. Keep clean-room boundaries intact; do not vendor or copy PR-Agent source,
   prompts, schemas, tests, or fixtures.
