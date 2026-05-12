# Config and Schema Migration Notes

This document records the stable compatibility contract for the clean-room
Cursor-native engine. It is maintainer-facing until the stable release gates are
complete.

## Current structured-output versions

- Output object schema: `cursor-review-action/v1`
- Review finding schema: `cursor-review-finding/v1`
- Schema compatibility diagnostics: `schema-compatibility/v1`

The parser accepts the current output schema version for object-shaped command
outputs such as `/cursor-ask`, `/cursor-improve`, and `/cursor-describe`.
`/cursor-review` returns an array of findings, so compatibility is tracked at the
finding level.

## Backward compatibility rules

- Keep stable fields until a future major schema version.
- Treat missing `schema_version` on object outputs as legacy-compatible while
  recording `legacy_missing_schema_version` diagnostics.
- Reject unsupported future or unknown schema versions before publishing
  structured findings; the existing parser retry and markdown fallback path then
  handles the response safely.
- Reject command/schema mismatches, for example a `describe` parse receiving
  `"command": "ask"`.
- Do not localize JSON keys, diagnostic keys, or schema version strings.

## Config migration policy

- `.cursor-review.yml` remains the only required configuration file.
- `.cursor-review.schema.json` documents the stable repository configuration
  surface for editors and maintainers. It is an advisory schema for repo-local
  config, not a replacement for runtime diagnostics or workflow event inputs.
- New config keys must have safe defaults and remain optional for at least one
  stable minor release before they can become required.
- Renames must keep the old key working until a documented major version.
- Automated migration scripts are a P2 non-goal until real user data shows that
  manual notes are not enough.

## Current repository config schema

Capability ID: `CONFIG-SCHEMA-P1`

The current schema covers stable repo-local keys for:

- model, language, review focus, command enablement, and trigger trust defaults.
- finding, diff, file, hunk, Cursor-call, timeout, and scope budgets.
- include/exclude patterns, generated-file skipping, and comment publishing mode.
- repo guidance files and guidance budgets.
- metadata-cache, debug artifact, and CI policy toggles.

Workflow-only event metadata such as PR title, PR body, commit messages, author
association, base/head SHAs, and GitHub tokens stays in `action.yml` inputs and
is intentionally not part of the repo config schema. Runtime loading still emits
`config/v1` diagnostics for unknown keys, invalid integer/boolean/filter values,
and safe fallbacks before Cursor is contacted.

## Maintainer checklist for schema changes

1. Bump the schema version only when a stable field is removed, renamed, or has
   incompatible semantics.
2. Update `scripts/engine/schemas.py` supported-version lists and stable fields.
3. Add or update parser compatibility tests.
4. Update fixture expectations and parity scorecard evidence.
5. Update `.cursor-review.schema.json` when stable repo config keys change.
6. Mention the schema/config change in release notes before tagging.
