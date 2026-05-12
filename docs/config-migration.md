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
- New config keys must have safe defaults and remain optional for at least one
  stable minor release before they can become required.
- Renames must keep the old key working until a documented major version.
- Automated migration scripts are a P2 non-goal until real user data shows that
  manual notes are not enough.

## Maintainer checklist for schema changes

1. Bump the schema version only when a stable field is removed, renamed, or has
   incompatible semantics.
2. Update `scripts/engine/schemas.py` supported-version lists and stable fields.
3. Add or update parser compatibility tests.
4. Update fixture expectations and parity scorecard evidence.
5. Mention the schema/config change in release notes before tagging.
